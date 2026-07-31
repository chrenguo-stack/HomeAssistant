#!/usr/bin/env python3
from __future__ import annotations
import hashlib, importlib.util, json, os, stat, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MODULE=ROOT/'tools/h3_n2_stage2d9r_g3r_d2_17_g13_existing_empty_baseline_and_claim_state_repair_20260731_v1.py'
ACCEPT=ROOT/'docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g12-consumed-repairerror-main-zero-net-drift-disposition-20260731-v1.json'
DECISION=ROOT/'docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g13-private-package-static-check-authorization-pending-20260731-v1.json'

def canonical(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def require(ok, code):
    if not ok: raise AssertionError(code)

spec=importlib.util.spec_from_file_location('g13',MODULE);g13=importlib.util.module_from_spec(spec);spec.loader.exec_module(g13)
accept=json.loads(ACCEPT.read_text());decision=json.loads(DECISION.read_text())
main=dict(accept['main_zero_net_drift']);main_binding=main.pop('main_zero_net_drift_binding_sha256')
require(canonical(main)==main_binding=='12a7f715cef504ba8d92ee17e1e40e4b51a20a4b6a4b1bb4f12d3e20ab0899ce','MAIN_DRIFT_BINDING')
g12=dict(accept);nested=g12.pop('main_zero_net_drift');binding=g12.pop('g12_disposition_binding_sha256')
require(canonical(g12)==binding=='bbc16258410a53363349c7b71323f0b7fcb33548f561dfa3b0dc71be5fcb7bc3','G12_BINDING')
g13_value=dict(decision);g13_binding=g13_value.pop('g13_pending_binding_sha256')
require(canonical(g13_value)==g13_binding=='6b55377ca34d2c71e9653ef1708ce4ad8a2c06ef5b936b7c2ce1e715561ae596','G13_BINDING')

class ExecutionError(RuntimeError): pass
class Core:
    ExecutionError=ExecutionError
    def __init__(self):
        def raw(selected, esptool, work, auth):
            require(Path(work).is_dir(),'RAW_WORK_MISSING')
            (Path(work)/'baseline-test-partition.bin').write_bytes(b'x'*4096)
            return {'ok':True}
        self.raw=raw;self.baseline=raw

with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    missing=root/'missing'
    core=Core();info=g13.install_baseline_work_directory_compatibility_repair(core)
    require(info['installed'] and not info['physical_operation'],'INSTALL')
    require(core.baseline(None,Path('/bin/true'),missing,{})=={'ok':True},'MISSING_ACCEPT')
    require(stat.S_IMODE(missing.stat().st_mode)==0o700,'MISSING_MODE')

with tempfile.TemporaryDirectory() as td:
    existing=Path(td);os.chmod(existing,0o700)
    core=Core();g13.install_baseline_work_directory_compatibility_repair(core)
    require(core.baseline(None,Path('/bin/true'),existing,{})=={'ok':True},'EXISTING_EMPTY_ACCEPT')

with tempfile.TemporaryDirectory() as td:
    existing=Path(td);os.chmod(existing,0o700)
    core=Core()
    def g12_wrapper(*args,**kwargs): raise RuntimeError('G12_SHOULD_BE_BYPASSED')
    g12_wrapper._g12_original_baseline=core.raw
    core.baseline=g12_wrapper
    info=g13.install_baseline_work_directory_compatibility_repair(core)
    require(info['bypasses_g12_incompatible_wrapper'],'G12_NOT_BYPASSED')
    require(core.baseline(None,Path('/bin/true'),existing,{})=={'ok':True},'G12_BYPASS_FAILED')

with tempfile.TemporaryDirectory() as td:
    nonempty=Path(td);os.chmod(nonempty,0o700);(nonempty/'x').write_text('x')
    core=Core();g13.install_baseline_work_directory_compatibility_repair(core)
    try: core.baseline(None,Path('/bin/true'),nonempty,{})
    except ExecutionError as exc: require(str(exc)=='G13_BASELINE_WORK_DIRECTORY_NOT_EMPTY','NONEMPTY_CODE')
    else: raise AssertionError('NONEMPTY_ACCEPTED')

with tempfile.TemporaryDirectory() as td:
    root=Path(td);target=root/'target';target.mkdir();os.chmod(target,0o700);link=root/'link';link.symlink_to(target, target_is_directory=True)
    core=Core();g13.install_baseline_work_directory_compatibility_repair(core)
    try: core.baseline(None,Path('/bin/true'),link,{})
    except ExecutionError as exc: require(str(exc)=='G13_BASELINE_WORK_DIRECTORY_SYMLINK','SYMLINK_CODE')
    else: raise AssertionError('SYMLINK_ACCEPTED')

state=g13.derive_authorization_state({'authorization_claimed':False,'authorization_consumed':True},{'status':'CONSUMED_FAILED','authorization_claimed':False})
require(state=={'authorization_claimed':True,'authorization_consumed':True},'CLAIM_STATE')
source='def execute():\n    claim(marker, authorization)\n    with tempfile.TemporaryDirectory(prefix="stage2d9r-successor-d2-") as td:\n        work = Path(td)\n        os.chmod(work, 0o700)\n        baseline_value = baseline(selected, esptool_path, work, authorization)\n'
classification=g13.inspect_frozen_executor_source(source)
require(classification['uses_existing_temporary_directory'],'TEMP_DIRECTORY_CLASSIFICATION')
require(classification['claim_precedes_inherited_baseline'],'CLAIM_ORDER_CLASSIFICATION')
print(json.dumps({'status':'PASS','main_zero_net_drift_verified':True,'g12_consumed_disposition_verified':True,'g13_missing_directory_supported':True,'g13_existing_empty_0700_directory_supported':True,'g12_wrapper_bypassed':True,'exact_subcode_preserved':True,'claim_state_corrected':True,'all_physical_operation_flags_false':True},sort_keys=True))
