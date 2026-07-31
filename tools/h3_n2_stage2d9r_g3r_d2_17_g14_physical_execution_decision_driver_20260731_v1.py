#!/usr/bin/env python3
"""Content-bound fragment loader for the one-shot G14 physical driver."""
from __future__ import annotations
import hashlib
from pathlib import Path
PARTS=['h3_n2_stage2d9r_g3r_d2_17_g14_physical_execution_decision_driver_20260731_v1.part1.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g14_physical_execution_decision_driver_20260731_v1.part2.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g14_physical_execution_decision_driver_20260731_v1.part3.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g14_physical_execution_decision_driver_20260731_v1.part4.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g14_physical_execution_decision_driver_20260731_v1.part5.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g14_physical_execution_decision_driver_20260731_v1.part6.pyfrag']
EXPECTED=['e4c7b1488fa545b3a3ab195eeda0c113deb47a5f4d948c877d9b9f0e8188b713', '400a8857a7fb471ab2da6140b033c044422f19da2b43ff0c0ae6df3aa5a71387', 'e6ecc0c1cea8b3c2a7a1371366d21a33b5a0b06f181d35409477809e2a33d5d8', '5b1a13ec4322aef316d55b5277b62a94a889006b4bfb17da866e2d654298ec0a', '505198675d7eaf95aac1b9705241a48f422c3295a1508df1bffd22d062612e45', 'ee72f41c59a7d52a4835285afc807802261ce1312bbb572baa47aa85080adae4']
root=Path(__file__).resolve().parent
chunks=[]
for name,digest in zip(PARTS,EXPECTED,strict=True):
 path=root/name;payload=path.read_bytes()
 if not path.is_file() or path.is_symlink() or hashlib.sha256(payload).hexdigest()!=digest:raise SystemExit("PHYSICAL_DRIVER_FRAGMENT_DIGEST_DRIFT:"+name)
 chunks.append(payload)
source=b"".join(chunks)
exec(compile(source,str(Path(__file__).resolve())+"<assembled>","exec"),{"__name__":"__main__","__file__":str(Path(__file__).resolve())})
