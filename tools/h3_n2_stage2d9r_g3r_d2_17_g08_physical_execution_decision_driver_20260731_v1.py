#!/usr/bin/env python3
"""One-shot D2-17 G08 physical execution decision driver."""
from __future__ import annotations
import argparse, hashlib, json, os, stat, subprocess, sys, tempfile, zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DECISION_ID='D1-H3N2-STAGE2D9R-G3R-D2-17-G08-PHYSICAL-EXECUTION-20260731-01'; D2_REQUEST_ID='D2-H3N2-STAGE2D9R-G3R-EXECUTION-IDENTITY-FROZEN-PREFLIGHT-STABILIZED-PHYSICAL-20260730-17'
PACKAGE_NAME='D2_17_PRIVATE_PACKAGE_20260731T065700CST_G08_HEAD13DA1725'
PRIVATE_SOURCE_SHA='13da1725a1abef398fec2edf6c053a34911b02d3'; ACCEPTANCE_SOURCE_SHA='5508344b84189f42fce04721b8a70ba02cb7b933'
ACCEPTANCE_ARTIFACT_ID=8778807759; ACCEPTANCE_ARTIFACT_SHA256='811ad907e14ec6b999c09244aacb47e52f3dc3f6e423accc6abf3d23759056ff'
ACCEPTANCE_BINDING_SHA256='7e260a96ac1812fdf18730657c78d9d7d7c17c8a3fb0f9e7afb2b1a2b0357d4c'; DECISION_REQUIRED_BINDING_SHA256='665a418114a4f8ef274bc264505f366ffffe8be93b879640999a7936720a4abb'
PRIVATE_DELIVERY_BINDING_SHA256='de29e81f317c09a8ca6c330e35ae492f10408ff3f2e42e1f0587b0f228c366e6'; ROOT_MANIFEST_SHA256='c28285cd0dfc481c632d906e79fcc7af3ab967a3071b4e587f56c911dc757d95'
AUTHORIZATION_FILE_SHA256='938b6cfe18e1ed365a15614e6e5735220ad13f730c4796a9d6e9d383be07626e'; AUTHORIZATION_RECORD_SHA256='76e089d31b40b0fefd1fd6613592e9be3d71ae03e1b063d26e7c1701430b46bb'
EXECUTION_IDENTITY_SHA256='9e234234aed566752ab8feb771e4cb84c3946d83857ee13d3d211d6c7e11f00c'; STATIC_CHECK_FILE_SHA256='a42a75efe3436c7d9928c7efac67cc21edee93fa2a7bdd90f714f810e79f6aec'
IDEMPOTENCY_FILE_SHA256='8a1b8588c0648f26063139a5eb3bcbeb5275aaca8e70d2cdee5b29bcf92a9f7b'; SENTINEL_FILE_SHA256='8991644cf66d81311ffe70f4dbe702047ae7f3ce64c7ebfe5c164dfc6f894050'
CONFIGURED_VALIDATOR_FILE_SHA256='8289d8daefd3941a52a1ef4e3e17cac9ccd9da14f803fc94569b9efe855e3fa8'; CONFIGURED_VALIDATOR_CHECK_SHA256='73b4f52441643b4b7209745abdcb7357dbff16e68c20c780ce5b1ac21e472561'
TERMINAL_RECORD_SHA256='18557a68c6be29710bc65d681b7aa83ff293835acf7389cbebf0e23d5fca297b'; AUTHORIZATION_EXPIRES_AT='2026-07-31T01:53:32.629244Z'
BOARD_IDENTITY_SHA256='2607b7df80b8b636548a8d9d97c0a6b4e4ead57e9a2cc6fcb7f93643617242f8'; SERIAL_IDENTITY_SHA256='b6dba7ee0db02feba166935ae8ec2bbd946dbf66926e5421cfa1c1c8b8a4f2c3'; BASELINE_STATE_SHA256='776517efcac0c6cf03cabe0572b773dedc89e9bb2793ccb0d9f9585ea6fa601f'
ADAPTER_SHA256='4b421d626e313a26c4815ef502b6aa76105a8685414ed2be3b4062a0387ef5ff'; RUNTIME_ENTRY_SHA256='0a03523bf7ae7922a7299fb2d658e028ce57567eb301d81ce5687dee5006541c'
EXECUTION_REL=Path('public-review/d2-17-execution-identity-frozen-physical-d2-execution-package')
REQUEST_REL=Path('public-review/PHYSICAL_D2_REQUEST_17.json')
ADAPTER_NAME='h3_n2_stage2d9r_g3r_d2_17_g07_preclaim_identity_adapter_repair_20260731_v1.py'
RUNTIME_ENTRY_NAME='h3_n2_stage2d9r_g3r_d2_17_g08_physical_runtime_identity_adapter_entry_20260731_v1.py'
AUTH_MARKER_NAME=hashlib.sha256(D2_REQUEST_ID.encode()).hexdigest()+'.json'
TARGETS={'python':('/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11','4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a'),'openssl':('/usr/local/Cellar/openssl@3/3.5.0/bin/openssl','04ad05ce2e7eaf92116dac99a984cc0e589040a103589f93a9fe452832766973'),'esptool':('~/Library/Python/3.11/bin/esptool','ab727aa71b9bbf794aab424eca706cb4b340be491ab28ba8fe17ef6d7962c267'),'mosquitto':('/opt/local/sbin/mosquitto','4d53cf9654852472c9839e178848987603e16abd41622d197440945307227763')}

class DecisionError(RuntimeError): pass
def require(ok:bool,code:str)->None:
    if not ok: raise DecisionError(code)
def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def canonical(value:object)->str: return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def mode(path:Path)->str: return format(stat.S_IMODE(path.stat().st_mode),'04o')
def load_json(path:Path,code:str)->dict[str,Any]:
    require(path.is_file() and not path.is_symlink(),code)
    try: value=json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc: raise DecisionError(code) from exc
    require(isinstance(value,dict),code); return value
def exclusive_json(path:Path,value:object)->None:
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700); os.chmod(path.parent,0o700)
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,'O_NOFOLLOW'): flags|=os.O_NOFOLLOW
    fd=os.open(path,flags,0o600)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',closefd=False) as f:
            json.dump(value,f,sort_keys=True,indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
    finally: os.close(fd)
def replace_json(path:Path,value:object)->None:
    tmp=path.with_name(path.name+'.tmp'); require(not tmp.exists(),'ATOMIC_TMP_EXISTS'); exclusive_json(tmp,value); os.replace(tmp,path)
def verify_sums(root:Path,expected_manifest:str|None,prefix:str)->None:
    root=root.resolve(strict=True); require(root.is_dir() and not root.is_symlink(),prefix+'_ROOT_INVALID')
    sums=root/'SHA256SUMS'; require(sums.is_file() and not sums.is_symlink(),prefix+'_SHA256SUMS_MISSING')
    if expected_manifest: require(sha(sums)==expected_manifest,prefix+'_SHA256SUMS_DIGEST_DRIFT')
    expected={}
    for line in sums.read_text(encoding='utf-8').splitlines():
        digest,name=line.split('  ',1); rel=Path(name); require(name not in expected and not rel.is_absolute() and '..' not in rel.parts,prefix+'_SHA256SUMS_INVALID'); expected[name]=digest
    observed={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and not p.is_symlink() and p!=sums}
    require(set(expected)==observed,prefix+'_SHA256SUMS_COVERAGE_DRIFT')
    for name,digest in expected.items(): require(sha(root/name)==digest,prefix+'_MEMBER_DIGEST_DRIFT:'+name)
    require(not any(p.is_symlink() for p in root.rglob('*')),prefix+'_SYMLINK_FORBIDDEN')
def validate_terminal(v:dict[str,Any])->None:
    require(v.get('terminal_record_sha256')==TERMINAL_RECORD_SHA256,'TERMINAL_RECORD_DIGEST_BINDING_DRIFT'); c=dict(v); c.pop('terminal_record_sha256',None); require(canonical(c)==TERMINAL_RECORD_SHA256,'TERMINAL_RECORD_SEMANTIC_DIGEST_DRIFT')
    required={'status':'PASS','terminal_state':'TARGET_MAC_STATIC_CHECK_PASSED_AUTHORIZATION_UNCLAIMED_UNCONSUMED','package_generation':'G08','private_source_sha':PRIVATE_SOURCE_SHA,'private_delivery_binding_sha256':PRIVATE_DELIVERY_BINDING_SHA256,'authorization_record_sha256':AUTHORIZATION_RECORD_SHA256,'execution_identity_sha256':EXECUTION_IDENTITY_SHA256,'runtime_identity_adapter_sha256':ADAPTER_SHA256,'configured_runtime_validator_check_sha256':CONFIGURED_VALIDATOR_CHECK_SHA256,'configured_core_validate_authorization_executed':True,'identity_adapter_installed':True,'authorization_created':True,'authorization_claimed':False,'authorization_consumed':False,'physical_decision_created':False}
    for k,e in required.items(): require(v.get(k)==e,'TERMINAL_FIELD_DRIFT:'+k)
    for k in ('board_operation','usb_enumeration','serial_operation','esptool_operation','flash_operation','physical_nvs_operation','network_operation','broker_started','prepare_executed','verify_executed','recovery_executed'): require(v.get(k) is False,'TERMINAL_PHYSICAL_FLAG_DRIFT:'+k)
def validate_acceptance(path:Path)->None:
    require(path.is_file() and not path.is_symlink() and sha(path)==ACCEPTANCE_ARTIFACT_SHA256,'ACCEPTANCE_ARTIFACT_DIGEST_DRIFT')
    try:
        with zipfile.ZipFile(path) as z:
            require(z.read('SOURCE_SHA').decode().strip()==ACCEPTANCE_SOURCE_SHA,'ACCEPTANCE_ARTIFACT_SOURCE_SHA_DRIFT')
            names=[n for n in z.namelist() if n.endswith('h3-n2-stage2d9r-g3r-d2-17-g08-target-mac-static-check-pass-20260731-v1.json')]; require(len(names)==1,'ACCEPTANCE_ARTIFACT_RECORD_MISSING'); v=json.loads(z.read(names[0]).decode())
    except DecisionError: raise
    except Exception as exc: raise DecisionError('ACCEPTANCE_ARTIFACT_INVALID') from exc
    required={'acceptance_binding_sha256':ACCEPTANCE_BINDING_SHA256,'private_source_sha':PRIVATE_SOURCE_SHA,'authorization_record_sha256':AUTHORIZATION_RECORD_SHA256,'terminal_record_sha256':TERMINAL_RECORD_SHA256,'configured_runtime_validator_check_sha256':CONFIGURED_VALIDATOR_CHECK_SHA256,'authorization_claimed':False,'authorization_consumed':False}
    for k,e in required.items(): require(v.get(k)==e,'ACCEPTANCE_FIELD_DRIFT:'+k)
def resolve_targets()->dict[str,Path]:
    out={}
    for name,(raw,digest) in TARGETS.items():
        p=Path(raw).expanduser().resolve(strict=True); require(p.is_file() and not p.is_symlink() and os.access(p,os.X_OK),'TARGET_TOOL_INVALID:'+name); require(sha(p)==digest,'TARGET_TOOL_DIGEST_DRIFT:'+name); out[name]=p
    return out
def execution_env(root:Path,python:Path)->dict[str,str]:
    v=dict(os.environ); r=str(root.resolve(strict=True)); v.update({'PYTHONDONTWRITEBYTECODE':'1','GH_D2_17_DELIVERY_PROFILE':'private-package','GH_D2_17_OUTER_PACKAGE_ROOT':r,'GH_D2_17_LAUNCHER_PACKAGE_ROOT':r,'GH_D2_13_LAUNCHER_PACKAGE_ROOT':r,'GH_D2_14_LAUNCHER_PACKAGE_ROOT':r,'GH_D2_15_LAUNCHER_PACKAGE_ROOT':r,'GH_D2_16_LAUNCHER_PACKAGE_ROOT':r,'PATH':str(python.parent)+os.pathsep+v.get('PATH','')}); return v

def validate_host(package:Path,runtime:Path,decision_root:Path,targets:dict[str,Path])->tuple[dict[str,Any],dict[str,Any],Path,Any]:
    verify_sums(package,ROOT_MANIFEST_SHA256,'G08_ROOT'); terminal=load_json(runtime/'D2_17_TARGET_MAC_STATIC_CHECK_TERMINAL.json','TERMINAL_RECORD_INVALID'); validate_terminal(terminal)
    fixed=(('D2_17_AUTHORIZATION.json',AUTHORIZATION_FILE_SHA256),('D2_17_TARGET_MAC_STATIC_CHECK.json',STATIC_CHECK_FILE_SHA256),('D2_17_BIND_INSTALL_IDEMPOTENCY.json',IDEMPOTENCY_FILE_SHA256),('D2_17_HARDWARE_SENTINEL_SELF_CHECK.json',SENTINEL_FILE_SHA256),('D2_17_G08_CONFIGURED_RUNTIME_VALIDATOR_CHECK.json',CONFIGURED_VALIDATOR_FILE_SHA256))
    for name,digest in fixed:
        p=runtime/name; require(p.is_file() and not p.is_symlink() and sha(p)==digest,'RUNTIME_EVIDENCE_DIGEST_DRIFT:'+name)
    auth_path=runtime/'D2_17_AUTHORIZATION.json'; identity_path=runtime/'D2_17_EXECUTION_IDENTITY.json'; auth=load_json(auth_path,'AUTHORIZATION_RECORD_INVALID'); identity=load_json(identity_path,'EXECUTION_IDENTITY_INVALID')
    require(auth.get('authorization_record_sha256')==AUTHORIZATION_RECORD_SHA256,'AUTHORIZATION_RECORD_BINDING_DRIFT'); require(identity.get('execution_identity_sha256')==EXECUTION_IDENTITY_SHA256,'EXECUTION_IDENTITY_BINDING_DRIFT')
    require(auth.get('board_identity_sha256')==BOARD_IDENTITY_SHA256 and auth.get('serial_identity_sha256')==SERIAL_IDENTITY_SHA256 and auth.get('baseline_state_sha256')==BASELINE_STATE_SHA256,'PHYSICAL_IDENTITY_BINDING_DRIFT')
    require(auth.get('authorization_claimed') is False and auth.get('authorization_consumed') is False,'AUTHORIZATION_ALREADY_USED')
    expires=datetime.fromisoformat(str(auth.get('expires_at')).replace('Z','+00:00')).astimezone(timezone.utc); require(expires.isoformat().replace('+00:00','Z')==AUTHORIZATION_EXPIRES_AT,'AUTHORIZATION_EXPIRY_DRIFT'); require(datetime.now(timezone.utc)<=expires,'AUTHORIZATION_EXPIRED')
    execution=(package/EXECUTION_REL).resolve(strict=True); request_path=(package/REQUEST_REL).resolve(strict=True); adapter_path=(package/ADAPTER_NAME).resolve(strict=True); entry_path=(decision_root/RUNTIME_ENTRY_NAME).resolve(strict=True)
    require(sha(adapter_path)==ADAPTER_SHA256,'IDENTITY_ADAPTER_DIGEST_DRIFT'); require(sha(entry_path)==RUNTIME_ENTRY_SHA256,'RUNTIME_ENTRY_DIGEST_DRIFT')
    os.environ.update(execution_env(execution,targets['python'])); sys.path.insert(0,str(execution)); sys.path.insert(0,str(package))
    import h3_n2_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_wrapper_20260730_v1 as wrapper
    import h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_contract_20260730_v1 as contract
    import h3_n2_stage2d9r_g3r_d2_17_g07_preclaim_identity_adapter_repair_20260731_v1 as adapter
    wrapper.bind_complete_chain(); d2_11=wrapper._bound_d2_11(); install=adapter.install_runtime_identity_adapter(d2_11,contract,identity); require(install.get('installed') is True,'IDENTITY_ADAPTER_INSTALL_FAILED')
    request=contract.load_json(request_path,'PHYSICAL_REQUEST_INVALID'); contract.validate_physical_request(request,execution); core=d2_11.configure_core(); contract.validate_execution_identity(identity,execution,request=request,controller_path=Path(core.__file__),python_path=targets['python'],openssl_path=targets['openssl'],esptool_path=targets['esptool'],mosquitto_path=targets['mosquitto']); contract.validate_authorization_contract(auth,request,identity,now=datetime.now(timezone.utc)); core.validate_private_metadata(Path.home()); core.validate_authorization(auth_path,package_root=execution,python_path=targets['python'],openssl_path=targets['openssl'],esptool_path=targets['esptool'],mosquitto_path=targets['mosquitto'],now=datetime.now(timezone.utc))
    return auth,identity,execution,d2_11

def failure(code:str,flags:dict[str,bool])->dict[str,Any]:
    v={'schema':'gh.h3.n2.stage2d9r-g3r-d2-17-g08-physical-decision-terminal/1','status':'BLOCKED_BEFORE_INHERITED_CLAIM','terminal_state':'PHYSICAL_DECISION_PRECLAIM_BLOCKED_UNCLAIMED_UNCONSUMED','failure_code':code,'decision_id':DECISION_ID,'d2_request_id':D2_REQUEST_ID,'authorization_claimed':False,'authorization_consumed':False,'replay_permitted':False,'automatic_retry_permitted':False,'board_operation':flags['board'],'usb_enumeration':flags['usb'],'serial_operation':flags['serial'],'esptool_operation':flags['esptool'],'flash_operation':False,'physical_nvs_operation':flags['nvs'],'network_operation':False,'broker_started':False,'prepare_executed':False,'verify_executed':False,'recovery_executed':False,'activate_executed':False,'cleanup_executed':False,'ready':False,'merge':False,'release':False,'tag':False,'deployment':False}
    v['terminal_record_sha256']=canonical(v); return v

def run(decision_root:Path)->int:
    require(sys.platform=='darwin','TARGET_HOST_NOT_DARWIN'); package=(Path.home()/'Downloads/ActiveTestRuns'/PACKAGE_NAME).resolve(strict=True); runtime=package.parent/(PACKAGE_NAME+'_runtime'); require(runtime.is_dir() and not runtime.is_symlink(),'G08_RUNTIME_ROOT_INVALID')
    decision_root=decision_root.resolve(strict=True); verify_sums(decision_root,None,'PHYSICAL_DECISION'); validate_acceptance(decision_root/'D2_17_G08_ACCEPTANCE_ARTIFACT_8778807759.zip'); targets=resolve_targets()
    physical=runtime/'D2_17_G08_PHYSICAL_EXECUTION_20260731_01'; terminal_path=physical/'D2_17_G08_PHYSICAL_DECISION_TERMINAL.json'; result_path=physical/'D2_17_G08_PHYSICAL_RESULT.json'; decision_marker=Path.home()/'.local/state/greenhouse-stage2d9r/d2-17-g08-physical-decisions'/(DECISION_ID+'.json'); auth_state=Path.home()/'.local/state/greenhouse-stage2d9r/d2-authorizations'; auth_marker=auth_state/AUTH_MARKER_NAME
    require(not physical.exists(),'PHYSICAL_RUNTIME_ROOT_ALREADY_EXISTS'); require(not decision_marker.exists(),'PHYSICAL_DECISION_ALREADY_USED'); require(not auth_marker.exists(),'AUTHORIZATION_ALREADY_CLAIMED_OR_CONSUMED'); physical.mkdir(parents=True,mode=0o700); os.chmod(physical,0o700)
    flags={'board':False,'usb':False,'serial':False,'esptool':False,'nvs':False}
    try:
        auth,identity,execution,d2_11=validate_host(package,runtime,decision_root,targets); core=d2_11.configure_core(); work=physical/'preclaim-baseline'; work.mkdir(mode=0o700); flags.update(board=True,usb=True,serial=True); selected=core.select_serial(auth); flags.update(esptool=True,nvs=True); baseline=core.baseline(selected,targets['esptool'],work,auth); require(canonical(baseline)==BASELINE_STATE_SHA256,'PRECLAIM_BASELINE_STATE_DRIFT')
        marker={'schema':'gh.h3.n2.stage2d9r-g3r-d2-17-g08-physical-decision-marker/1','status':'PHYSICAL_DECISION_CLAIMED_BOARD_BASELINE_VERIFIED','decision_id':DECISION_ID,'d2_request_id':D2_REQUEST_ID,'private_source_sha':PRIVATE_SOURCE_SHA,'acceptance_source_sha':ACCEPTANCE_SOURCE_SHA,'acceptance_artifact_id':ACCEPTANCE_ARTIFACT_ID,'acceptance_artifact_sha256':ACCEPTANCE_ARTIFACT_SHA256,'acceptance_binding_sha256':ACCEPTANCE_BINDING_SHA256,'decision_required_binding_sha256':DECISION_REQUIRED_BINDING_SHA256,'authorization_record_sha256':AUTHORIZATION_RECORD_SHA256,'execution_identity_sha256':EXECUTION_IDENTITY_SHA256,'runtime_identity_adapter_sha256':ADAPTER_SHA256,'board_identity_sha256':BOARD_IDENTITY_SHA256,'serial_identity_sha256':SERIAL_IDENTITY_SHA256,'baseline_state_sha256':BASELINE_STATE_SHA256,'authorization_claimed':False,'authorization_consumed':False,'claimed_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'one_shot':True,'replay_permitted':False,'automatic_retry_permitted':False}; marker['marker_sha256']=canonical(marker); exclusive_json(decision_marker,marker)
        auth_state.mkdir(parents=True,exist_ok=True,mode=0o700); os.chmod(auth_state,0o700); roots={}
        for name in ('immutable-root','recovery-root','prepare-evidence','delivery-evidence','terminalization-evidence'): roots[name]=physical/name; roots[name].mkdir(mode=0o700)
        executor_args=['execute','--package-root',str(execution),'--physical-request',str(package/REQUEST_REL),'--authorization-record',str(runtime/'D2_17_AUTHORIZATION.json'),'--immutable-root',str(roots['immutable-root']),'--recovery-root',str(roots['recovery-root']),'--home',str(Path.home()),'--state-root',str(auth_state),'--result-output',str(result_path),'--prepare-evidence-root',str(roots['prepare-evidence']),'--delivery-evidence-root',str(roots['delivery-evidence']),'--terminalization-evidence-root',str(roots['terminalization-evidence']),'--openssl',str(targets['openssl']),'--esptool',str(targets['esptool']),'--mosquitto',str(targets['mosquitto'])]
        entry=(decision_root/RUNTIME_ENTRY_NAME).resolve(strict=True); command=[str(targets['python']),'-B',str(entry),'--execution-root',str(execution),'--identity-path',str(runtime/'D2_17_EXECUTION_IDENTITY.json'),'--adapter-path',str(package/ADAPTER_NAME),'--',*executor_args]
        outp,errp=physical/'physical.stdout',physical/'physical.stderr'
        with outp.open('wb') as out,errp.open('wb') as err: os.chmod(outp,0o600); os.chmod(errp,0o600); completed=subprocess.run(command,env=execution_env(execution,targets['python']),stdin=subprocess.DEVNULL,stdout=out,stderr=err,check=False)
        result=load_json(result_path,'PHYSICAL_RESULT_MISSING_OR_INVALID') if result_path.exists() else {}; auth_value=load_json(auth_marker,'AUTHORIZATION_MARKER_MISSING_OR_INVALID') if auth_marker.exists() else {}
        claimed=bool(result.get('authorization_claimed',auth_value.get('authorization_claimed',False))); consumed=bool(result.get('authorization_consumed',auth_value.get('status') in {'CONSUMED_PASS','CONSUMED_FAILED'})); passed=completed.returncode==0 and result.get('status')=='CONSUMED_PASS' and auth_value.get('status')=='CONSUMED_PASS'
        terminal={'schema':'gh.h3.n2.stage2d9r-g3r-d2-17-g08-physical-decision-terminal/1','status':'PASS' if passed else 'FAIL','terminal_state':'D2_17_G08_PHYSICAL_EXECUTION_CONSUMED_PASS' if passed else str(result.get('terminal_state') or auth_value.get('status') or 'PHYSICAL_EXECUTION_FAILED'),'failure_code':None if passed else str(result.get('failure_code') or 'PHYSICAL_EXECUTION_FAILED'),'failure_stage':result.get('failure_stage'),'decision_id':DECISION_ID,'d2_request_id':D2_REQUEST_ID,'authorization_claimed':claimed,'authorization_consumed':consumed,'authorization_record_sha256':AUTHORIZATION_RECORD_SHA256,'execution_identity_sha256':EXECUTION_IDENTITY_SHA256,'runtime_identity_adapter_sha256':ADAPTER_SHA256,'physical_result_sha256':sha(result_path) if result_path.exists() else None,'authorization_marker_sha256':sha(auth_marker) if auth_marker.exists() else None,'replay_permitted':False,'automatic_retry_permitted':False,'board_operation':bool(flags['board'] or result.get('board_operation')),'usb_enumeration':bool(flags['usb'] or result.get('usb_enumeration')),'serial_operation':bool(flags['serial'] or result.get('serial_operation')),'esptool_operation':bool(flags['esptool'] or result.get('esptool_operation')),'flash_operation':bool(result.get('flash_operation') or result.get('flash_sha256')),'physical_nvs_operation':bool(flags['nvs'] or result.get('physical_nvs_operation')),'network_operation':bool(result.get('network_operation')),'broker_started':bool(result.get('broker_started') or result.get('broker_log_sha256')),'prepare_executed':bool(result.get('prepare_executed') or int(result.get('prepare_count',0))>0),'verify_executed':bool(result.get('verify_executed') or int(result.get('verify_count',0))>0),'recovery_executed':bool(result.get('recovery_executed') or result.get('recovery_attempted')),'recovery_succeeded':bool(result.get('recovery_succeeded')),'outer_preclaim_board_baseline_verified':True,'inherited_board_operation':bool(result.get('board_operation')),'inherited_usb_enumeration':bool(result.get('usb_enumeration')),'inherited_serial_operation':bool(result.get('serial_operation')),'inherited_esptool_operation':bool(result.get('esptool_operation')),'inherited_physical_nvs_operation':bool(result.get('physical_nvs_operation')),'activate_executed':False,'cleanup_executed':False,'ready':False,'merge':False,'release':False,'tag':False,'deployment':False}; terminal['terminal_record_sha256']=canonical(terminal); exclusive_json(terminal_path,terminal)
        marker.update(status='CONSUMED_PASS' if passed else 'CONSUMED_FAILED',authorization_claimed=claimed,authorization_consumed=consumed,terminal_record_sha256=terminal['terminal_record_sha256'],completed_at=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')); replace_json(decision_marker,marker)
        print(json.dumps(terminal,sort_keys=True)); print('PHYSICAL_RUNTIME_ROOT='+str(physical)); print('PHYSICAL_TERMINAL_FILE='+str(terminal_path)); print('PHYSICAL_RESULT_FILE='+str(result_path)); print('AUTHORIZATION_MARKER_FILE='+str(auth_marker)); return 0 if passed else 2
    except Exception as exc:
        code=exc.args[0] if isinstance(exc,DecisionError) and exc.args else type(exc).__name__; terminal=failure(str(code),flags)
        if not terminal_path.exists(): exclusive_json(terminal_path,terminal)
        print(json.dumps(terminal,sort_keys=True)); print('PHYSICAL_RUNTIME_ROOT='+str(physical)); print('PHYSICAL_TERMINAL_FILE='+str(terminal_path)); print('PHYSICAL_RESULT_FILE='+str(result_path)); print('AUTHORIZATION_MARKER_FILE='+str(auth_marker)); return 2

def self_test(execution:Path,adapter:Path,entry:Path)->int:
    execution=execution.expanduser().resolve(strict=True); adapter=adapter.expanduser().resolve(strict=True); entry=entry.expanduser().resolve(strict=True); require(sha(adapter)==ADAPTER_SHA256,'SELF_TEST_ADAPTER_DIGEST_DRIFT'); require(sha(entry)==RUNTIME_ENTRY_SHA256,'SELF_TEST_ENTRY_DIGEST_DRIFT')
    with tempfile.TemporaryDirectory(prefix='d2-17-g08-adapter-entry-') as td:
        root=Path(td); identity=root/'identity.json'; identity.write_text(json.dumps({'execution_identity_sha256':EXECUTION_IDENTITY_SHA256}),encoding='utf-8'); os.chmod(identity,0o600); paths={}
        for name in ('immutable','recovery','state','prepare','delivery','terminal'): paths[name]=root/name; paths[name].mkdir(mode=0o700)
        result=root/'result.json'; args=['execute','--package-root',str(execution),'--physical-request',str(execution.parent/'PHYSICAL_D2_REQUEST_17.json'),'--authorization-record',str(root/'missing.json'),'--immutable-root',str(paths['immutable']),'--recovery-root',str(paths['recovery']),'--home',str(root),'--state-root',str(paths['state']),'--result-output',str(result),'--prepare-evidence-root',str(paths['prepare']),'--delivery-evidence-root',str(paths['delivery']),'--terminalization-evidence-root',str(paths['terminal']),'--openssl','/bin/true','--esptool','/bin/true','--mosquitto','/bin/true']
        completed=subprocess.run([sys.executable,'-B',str(entry),'--execution-root',str(execution),'--identity-path',str(identity),'--adapter-path',str(adapter),'--',*args],env=execution_env(execution,Path(sys.executable).resolve(strict=True)),text=True,capture_output=True,check=False); require(completed.returncode==2,'SELF_TEST_EXPECTED_PRECLAIM_FAILURE'); combined=completed.stdout+completed.stderr; require('TypeError' not in combined,'SELF_TEST_TYPEERROR_RECURRED'); value=load_json(result,'SELF_TEST_RESULT_MISSING'); require(value.get('failure_stage')=='PRECLAIM','SELF_TEST_FAILURE_STAGE_DRIFT'); require(value.get('authorization_claimed') is False,'SELF_TEST_AUTHORIZATION_CLAIMED'); require(all(value.get(k) is False for k in ('board_operation','usb_enumeration','serial_operation','esptool_operation','flash_operation','physical_nvs_operation')),'SELF_TEST_PHYSICAL_BOUNDARY_VIOLATED'); print(json.dumps({'status':'PASS','runtime_identity_adapter_entry_executed':True,'type_error_recurred':False,'failure_stage':'PRECLAIM','authorization_claimed':False,'authorization_consumed':bool(value.get('authorization_consumed')),'board_operation':False},sort_keys=True)); return 0

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument('--self-test-execution-root',type=Path); p.add_argument('--self-test-adapter',type=Path); p.add_argument('--self-test-entry',type=Path); p.add_argument('--decision-root',type=Path); a=p.parse_args()
    if a.self_test_execution_root is not None: require(a.self_test_adapter is not None and a.self_test_entry is not None,'SELF_TEST_PATHS_REQUIRED'); return self_test(a.self_test_execution_root,a.self_test_adapter,a.self_test_entry)
    require(a.decision_root is not None,'PHYSICAL_DECISION_ROOT_REQUIRED'); return run(a.decision_root)
if __name__=='__main__': raise SystemExit(main())
