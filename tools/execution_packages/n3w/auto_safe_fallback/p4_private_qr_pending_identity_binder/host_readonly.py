import ast
import hashlib
import ipaddress
import json
import subprocess
from pathlib import Path


def build_remote_program(bridge_source: str, probe_source: str, baseline: frozenset[str]) -> str:
    if len(baseline)!=5 or any(len(x)!=64 for x in baseline):
        raise ValueError('INVALID_BASELINE')
    root=ast.parse(bridge_source)
    probe=ast.parse(probe_source)
    if any(isinstance(x,ast.ImportFrom) and x.module=='__future__' for x in probe.body):
        raise ValueError('SECOND_FUTURE_NOT_ALLOWED')
    assert root
    block='\nBASELINE_HASHES = '+json.dumps(sorted(baseline))+'\n'
    combined=bridge_source.rstrip()+'\n'+block+probe_source
    ast.parse(combined)
    return combined


def remote_snapshot_once(target: str, expected_target_sha: str, program: str, *, runner=subprocess.run) -> dict:
    try:
        user,ip=target.split('@',1)
        addr=ipaddress.IPv4Address(ip)
    except (ValueError,TypeError):
        raise ValueError('INVALID_TARGET')
    if user!='root' or addr.is_loopback or not addr.is_private or hashlib.sha256(target.encode()).hexdigest()!=expected_target_sha:
        raise ValueError('TARGET_BINDING_INVALID')
    cmd=['ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=5',target,'python3','-']
    result=runner(cmd,input=program.encode(),capture_output=True,timeout=15,check=False)
    if result.returncode!=0 or len(result.stdout)>8192:
        raise ValueError('REMOTE_READONLY_STOP')
    try:
        data=json.loads(result.stdout)
    except (ValueError,UnicodeError):
        raise ValueError('REMOTE_RESPONSE_INVALID')
    required={'schema','hardware_sha256','pairing_sha256','expires_at','preboot_count','preboot_hashes','new_count','read_at','container_continuity_pass','manager_socket_pass','tls_live_reprobe_pass'}
    if not isinstance(data,dict) or set(data)!=required or data.get('container_continuity_pass') is not True or data.get('manager_socket_pass') is not True or data.get('tls_live_reprobe_pass') is not True:
        raise ValueError('REMOTE_AUTHORITY_INVALID')
    return data
