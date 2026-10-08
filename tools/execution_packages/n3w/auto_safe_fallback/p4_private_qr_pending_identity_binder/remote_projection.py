import hashlib
import json
import re
import os
import socket
import ssl
import ipaddress
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

MANAGER_ID_SHA = "7b3c2a4de642e8a57da9d3f1652c9c35a27533c16f056736ecc89e289463bccc"
BROKER_ID_SHA = "54a343cf903f5c73fd5b646c233e59cf0313b25d3f2caa55061fc64bc30741cd"
MANAGER_STARTED = "2026-10-06T15:08:36.478286093Z"
BROKER_STARTED = "2026-10-06T05:01:47.110364692Z"
EXPECTED_TLS_CA = "11ff133cdab8bf5f3093f6b488f8fa7e2579a1b5e383d066b1a1da56ad5dae9f"
EXPECTED_TLS_LEAF = "8272aa061d70bf0b5ed41a94a1b6fdc5065bd6b51f6751aa7b7a2059803d74cb"
EXPECTED_T1_IP_SHA = "6257bd5c713a053e9efa4c9b036119a068dba2ddb8145e8288e89ad470822338"


def _cmd(args, error):
    try:
        r = subprocess.run(args, capture_output=True, timeout=6, check=False)
        if r.returncode != 0:
            reject(error)
        return r.stdout.decode('utf-8')
    except (OSError, subprocess.TimeoutExpired, UnicodeDecodeError):
        reject(error)


def _container(name):
    raw = json.loads(_cmd(['docker','inspect',name], 'RUNTIME_PROBE_FAILED'))
    if not isinstance(raw,list) or len(raw) != 1:
        reject('RUNTIME_PROBE_INVALID')
    return raw[0]


def _env(doc):
    entries=doc['Config']['Env']
    if not isinstance(entries,list):reject('RUNTIME_ENV_INVALID')
    result={}
    for entry in entries:
        if '=' in entry:
            key,value=entry.split('=',1)
            result[key]=value
    return result


def _path(doc, dest):
    path=PurePosixPath(dest)
    if not path.is_absolute():reject('RUNTIME_MOUNT_INVALID')
    found=[]
    for mount in doc['Mounts']:
        try:
            rest=path.relative_to(PurePosixPath(mount['Destination']))
        except ValueError:
            continue
        found.append(Path(mount['Source']).joinpath(*rest.parts))
    if len(found)!=1 or found[0].is_symlink() or not found[0].is_file():
        reject('RUNTIME_MOUNT_INVALID')
    return found[0]


def _assert_runtime():
    manager=_container('greenhouse-manager')
    broker_ids=[x for x in _cmd(['docker','ps','-q','--no-trunc','--filter','label=com.docker.compose.project=n3wfc4', '--filter','label=com.docker.compose.service=broker'], 'BROKER_SELECTOR_FAILED').splitlines() if x]
    if len(broker_ids)!=1:reject('BROKER_SELECTOR_AMBIGUOUS')
    broker=_container(broker_ids[0])
    for instance,expected_id,started in ((manager,MANAGER_ID_SHA,MANAGER_STARTED),(broker,BROKER_ID_SHA,BROKER_STARTED)):
        if sha(instance['Id'])!=expected_id or instance['State'].get('Running') is not True or instance['State'].get('StartedAt')!=started or instance['RestartCount']!=0:
            reject('CONTAINER_CONTINUITY_DRIFT')
    if manager['HostConfig']['NetworkMode']!='host' or manager['HostConfig'].get('PortBindings') not in (None,{}):
        reject('MANAGER_NETWORK_DRIFT')
    labels=broker['Config'].get('Labels') or {}
    if labels.get('com.docker.compose.project')!='n3wfc4' or labels.get('com.docker.compose.service')!='broker':
        reject('BROKER_SELECTOR_DRIFT')
    env=_env(manager)
    if env.get('GH_N3W_PAIRING_ADVERTISED_HOST')!='auto' or int(env.get('GH_PAIRING_PENDING_TTL_S','120'))!=120:
        reject('PAIRING_CONFIG_DRIFT')
    registration=_path(manager,env.get('GH_PAIRING_DB_PATH','/var/lib/greenhouse-manager/registration.sqlite3'))
    credential=_path(manager,env.get('GH_N3W_CREDENTIAL_LIFECYCLE_DB_PATH','/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3'))
    replay=_path(manager,env.get('GH_N3W_REPLAY_DB_PATH','/var/lib/greenhouse-manager/n3w/replay.sqlite3'))
    with contextlib.closing(_ro(replay)) as c:
        _query(c,'SELECT node_id FROM n3w_replay_state LIMIT 1')
    sock_path=env.get('GH_N3W_PAIRING_SOCKET_PATH','/tmp/greenhouse-manager/pairing.sock')
    ipc_inspect='import json,os,stat; p=os.getenv("GH_N3W_PAIRING_SOCKET_PATH","/tmp/greenhouse-manager/pairing.sock"); a=os.stat(p); print(json.dumps({"socket":stat.S_ISSOCK(a.st_mode),"mode":stat.S_IMODE(a.st_mode)}))'
    ipc=json.loads(_cmd(['docker','exec','greenhouse-manager','python3','-c',ipc_inspect],'MANAGER_UDS_PROBE_FAILED'))
    if ipc!={'socket':True,'mode':384}:
        reject('PAIRING_UDS_DRIFT')
    host=env.get('GH_N3W_NODE_BROKER_HOST')
    name=env.get('GH_N3W_NODE_BROKER_TLS_SERVER_NAME')
    ca_container=env.get('GH_N3W_NODE_BROKER_CA_FILE')
    if not host or not name or not ca_container or sha(host)!=EXPECTED_T1_IP_SHA or int(env.get('GH_N3W_NODE_BROKER_PORT','8883'))!=8883:
        reject('TLS_RUNTIME_BINDING_DRIFT')
    try:
        ipaddress.IPv4Address(host)
    except ValueError:
        reject('TLS_RUNTIME_BINDING_DRIFT')
    ca_file=_path(manager,ca_container)
    ca_data=ca_file.read_bytes()
    if hashlib.sha256(ca_data).hexdigest()!=EXPECTED_TLS_CA:
        reject('TLS_CA_DRIFT')
    try:
        ctx=ssl.create_default_context(cafile=str(ca_file))
        with socket.create_connection((host,8883),timeout=3) as connection:
            with ctx.wrap_socket(connection,server_hostname=name) as tls:
                certificate=tls.getpeercert(binary_form=True)
    except (OSError,ssl.SSLError):
        reject('TLS_RUNTIME_REPROBE_FAILED')
    if hashlib.sha256(certificate).hexdigest()!=EXPECTED_TLS_LEAF:
        reject('TLS_LEAF_DRIFT')
    return registration,credential


def main_remote(preboot_hashes):
    if not isinstance(preboot_hashes,list) or len(preboot_hashes)!=5 or sorted(set(preboot_hashes))!=preboot_hashes or not all(re.fullmatch('[0-9a-f]{64}',value) for value in preboot_hashes):
        reject('PREBOOT_AUTHORITY_INVALID')
    registration,credential=_assert_runtime()
    projection=project_readonly(registration,credential,frozenset(preboot_hashes))
    projection['read_at']=datetime.now(UTC).isoformat()
    projection['container_continuity_pass']=True
    projection['manager_socket_pass']=True
    projection['tls_live_reprobe_pass']=True
    return projection


if __name__ == '__main__':
    try:
        result=main_remote(BASELINE_HASHES)
        print(json.dumps(result,sort_keys=True))
    except (GateStop,KeyError,ValueError,TypeError,sqlite3.Error):
        print(json.dumps({'status':'STOP_REMOTE_PROBE_FAILED'}))
        sys.exit(2)
