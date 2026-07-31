#!/usr/bin/env python3
"""Load the content-bound G09 physical decision driver fragments."""
from __future__ import annotations
import hashlib
from pathlib import Path
PARTS = [('h3_n2_stage2d9r_g3r_d2_17_g09_physical_execution_decision_driver_20260731_v1.part1.pyfrag', 'f871defa5bc606d67445b30db13afcd92acbbb9397b02a689a83c952792b21fc'), ('h3_n2_stage2d9r_g3r_d2_17_g09_physical_execution_decision_driver_20260731_v1.part2.pyfrag', 'c51922f02c662610417f0317e687e8bc5a54147b94ea15839ab7896d4ebaea47'), ('h3_n2_stage2d9r_g3r_d2_17_g09_physical_execution_decision_driver_20260731_v1.part3.pyfrag', '97e6b121099a046ec7e408df5880fb471e6ad0005dd924ea009fbac969a5f597'), ('h3_n2_stage2d9r_g3r_d2_17_g09_physical_execution_decision_driver_20260731_v1.part4.pyfrag', '893a78dd055b65b7a78868194af91873fc48a3d8876db1426ab51035d3948a4c'), ('h3_n2_stage2d9r_g3r_d2_17_g09_physical_execution_decision_driver_20260731_v1.part5.pyfrag', '7a93058abf5167b705bf018e630f1824eb2b4921fba964cea9f93b20f69625bf'), ('h3_n2_stage2d9r_g3r_d2_17_g09_physical_execution_decision_driver_20260731_v1.part6.pyfrag', 'f72800104c0153339873e796af9788e8be1dad0d7a0b8f77f421313d8b01ae6f')]

def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def main() -> int:
    root=Path(__file__).resolve().parent; chunks=[]
    for name,expected in PARTS:
        path=root/name
        if path.is_symlink() or not path.is_file(): raise SystemExit('DRIVER_FRAGMENT_NOT_REGULAR:'+name)
        if digest(path)!=expected: raise SystemExit('DRIVER_FRAGMENT_DIGEST_DRIFT:'+name)
        chunks.append(path.read_text(encoding='utf-8'))
    ns={'__name__':'g09_physical_decision_core','__file__':str(root/'<g09-physical-decision-core>')}
    exec(compile(''.join(chunks),ns['__file__'],'exec'),ns)
    return int(ns['main']())
if __name__=='__main__': raise SystemExit(main())
