#!/usr/bin/env python3
"""Content-bound G12 physical runtime entry."""
from __future__ import annotations
import argparse, importlib, json, os, sys
from pathlib import Path
D2_REQUEST_ID='D2-H3N2-STAGE2D9R-G3R-EXECUTION-IDENTITY-FROZEN-PREFLIGHT-STABILIZED-PHYSICAL-20260730-17'
WRAPPER="h3_n2_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_wrapper_20260730_v1"
CONTRACT="h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_contract_20260730_v1"
IDENTITY_ADAPTER="h3_n2_stage2d9r_g3r_d2_17_g07_preclaim_identity_adapter_repair_20260731_v1"
MARKER_ADAPTER="h3_n2_stage2d9r_g3r_d2_17_g10_marker_name_digest_compatibility_repair_20260731_v1"
G12_REPAIR="h3_n2_stage2d9r_g3r_d2_17_g12_preclaim_baseline_directory_and_error_code_repair_20260731_v1"
def load(path:Path)->dict:
 v=json.loads(path.read_text(encoding="utf-8"))
 if not isinstance(v,dict): raise RuntimeError("JSON_OBJECT_REQUIRED")
 return v
def main()->int:
 p=argparse.ArgumentParser();p.add_argument("--execution-root",type=Path,required=True);p.add_argument("--physical-request",type=Path,required=True);p.add_argument("--identity-path",type=Path,required=True);p.add_argument("--identity-adapter-path",type=Path,required=True);p.add_argument("--marker-adapter-path",type=Path,required=True);p.add_argument("--g12-repair-path",type=Path,required=True);p.add_argument("--prepare-evidence-root",type=Path,required=True);p.add_argument("--delivery-evidence-root",type=Path,required=True);p.add_argument("--terminalization-evidence-root",type=Path,required=True);p.add_argument("remainder",nargs=argparse.REMAINDER);a=p.parse_args()
 args=list(a.remainder)
 if args and args[0]=="--":args=args[1:]
 if not args or args[0]!="execute":raise RuntimeError("EXECUTE_COMMAND_REQUIRED")
 execution=a.execution_root.expanduser().resolve(strict=True);paths=[a.identity_adapter_path,a.marker_adapter_path,a.g12_repair_path];resolved=[]
 for raw in paths:
  path=raw.expanduser().resolve(strict=True)
  if not path.is_file() or path.is_symlink():raise RuntimeError("ADAPTER_PATH_INVALID")
  resolved.append(path)
 sys.path[:0]=[str(execution),*(str(x.parent) for x in resolved)]
 os.environ.update({"PYTHONDONTWRITEBYTECODE":"1","GH_D2_17_DELIVERY_PROFILE":"private-package","GH_D2_17_OUTER_PACKAGE_ROOT":str(execution),"GH_D2_17_LAUNCHER_PACKAGE_ROOT":str(execution),"GH_D2_13_LAUNCHER_PACKAGE_ROOT":str(execution),"GH_D2_14_LAUNCHER_PACKAGE_ROOT":str(execution),"GH_D2_15_LAUNCHER_PACKAGE_ROOT":str(execution),"GH_D2_16_LAUNCHER_PACKAGE_ROOT":str(execution)})
 wrapper=importlib.import_module(WRAPPER);contract=importlib.import_module(CONTRACT);identity_adapter=importlib.import_module(IDENTITY_ADAPTER);marker_adapter=importlib.import_module(MARKER_ADAPTER);g12_repair=importlib.import_module(G12_REPAIR)
 request=contract.load_json(a.physical_request.expanduser().resolve(strict=True),"PHYSICAL_REQUEST_INVALID");request=contract.validate_physical_request(request,execution);identity=load(a.identity_path.expanduser().resolve(strict=True))
 wrapper.bind_complete_chain();d2_11=wrapper._bound_d2_11();d2_11._BOUND_PHYSICAL_REQUEST=request
 for attr,path in (("_EVIDENCE_ROOT",a.prepare_evidence_root),("_DELIVERY_EVIDENCE_ROOT",a.delivery_evidence_root),("_TERMINALIZATION_EVIDENCE_ROOT",a.terminalization_evidence_root)):setattr(d2_11,attr,path.expanduser().resolve(strict=True))
 first=identity_adapter.install_runtime_identity_adapter(d2_11,contract,identity);second=marker_adapter.install_runtime_marker_digest_adapter(d2_11,D2_REQUEST_ID)
 if not first.get("installed") or not second.get("installed"):raise RuntimeError("RUNTIME_ADAPTER_INSTALL_FAILED")
 original=d2_11.configure_core
 def configured():
  core=original();g12_repair.install_baseline_work_directory_repair(core);return core
 d2_11.configure_core=configured
 if getattr(d2_11,"handoff",None) is not None:d2_11.handoff.configure_core=configured
 sys.argv=[sys.argv[0],"execute",*args[1:]];return int(wrapper.main())
if __name__=="__main__":raise SystemExit(main())
