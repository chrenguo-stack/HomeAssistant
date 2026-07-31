#!/usr/bin/env python3
"""Run the frozen D2-17 executor with the verified execution-identity adapter."""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path

class EntryError(RuntimeError): pass

def require(ok: bool, code: str) -> None:
    if not ok: raise EntryError(code)

def load_json(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink(), 'EXECUTION_IDENTITY_INVALID')
    value=json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(value,dict), 'EXECUTION_IDENTITY_INVALID')
    return value

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--execution-root',type=Path,required=True)
    parser.add_argument('--identity-path',type=Path,required=True)
    parser.add_argument('--adapter-path',type=Path,required=True)
    parser.add_argument('executor_args',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    rest=list(args.executor_args)
    if rest and rest[0]=='--': rest=rest[1:]
    require(rest and rest[0]=='execute','EXECUTOR_COMMAND_INVALID')
    root=args.execution_root.expanduser().resolve(strict=True)
    adapter_path=args.adapter_path.expanduser().resolve(strict=True)
    require(adapter_path.is_file() and not adapter_path.is_symlink(),'IDENTITY_ADAPTER_NOT_REGULAR')
    sys.path.insert(0,str(root)); sys.path.insert(0,str(adapter_path.parent))
    os.environ.update({
      'PYTHONDONTWRITEBYTECODE':'1',
      'GH_D2_17_DELIVERY_PROFILE':'private-package',
      'GH_D2_17_OUTER_PACKAGE_ROOT':str(root),
      'GH_D2_17_LAUNCHER_PACKAGE_ROOT':str(root),
      'GH_D2_13_LAUNCHER_PACKAGE_ROOT':str(root),
      'GH_D2_14_LAUNCHER_PACKAGE_ROOT':str(root),
      'GH_D2_15_LAUNCHER_PACKAGE_ROOT':str(root),
      'GH_D2_16_LAUNCHER_PACKAGE_ROOT':str(root),
    })
    import h3_n2_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_wrapper_20260730_v1 as frozen
    import h3_n2_stage2d9r_g3r_d2_17_execution_identity_freeze_contract_20260730_v1 as contract
    import h3_n2_stage2d9r_g3r_d2_17_g07_preclaim_identity_adapter_repair_20260731_v1 as adapter
    identity=load_json(args.identity_path.expanduser().resolve(strict=True))
    frozen.bind_complete_chain()
    installed=adapter.install_runtime_identity_adapter(frozen._bound_d2_11(),contract,identity)
    require(installed.get('installed') is True,'IDENTITY_ADAPTER_INSTALL_FAILED')
    sys.argv=[str(root/'h3_n2_stage2d9r_g3r_d2_17_execution_identity_frozen_physical_d2_wrapper_20260730_v1.py'),*rest]
    return frozen.main()

if __name__=='__main__': raise SystemExit(main())
