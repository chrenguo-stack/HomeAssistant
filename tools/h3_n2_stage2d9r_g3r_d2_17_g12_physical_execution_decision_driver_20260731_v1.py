#!/usr/bin/env python3
"""Content-bound fragment loader for the one-shot G12 physical driver."""
from __future__ import annotations
import hashlib
from pathlib import Path
PARTS=['h3_n2_stage2d9r_g3r_d2_17_g12_physical_execution_decision_driver_20260731_v1.part1.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g12_physical_execution_decision_driver_20260731_v1.part2.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g12_physical_execution_decision_driver_20260731_v1.part3.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g12_physical_execution_decision_driver_20260731_v1.part4.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g12_physical_execution_decision_driver_20260731_v1.part5.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g12_physical_execution_decision_driver_20260731_v1.part6.pyfrag']
EXPECTED=['a590f0897357a2e7e13f22e6aabf2b58a8d75d1217cea0831d7e17b9192180cb', 'e13eb986cc7a03b32f11eebad5f3f6cffd646daeadce4a0e3af510d70c682280', 'b4954dfd4edfc50b614977d0017ac3fe9039240e715c2681476e940405432891', '3ac39c4d46660fc839a1be824fcdee69bbd699be81afd0fb9f0c666e511bf5f6', '185f3ed58c7737c5e1d95c66757115fc3e6d4c74689407ede50e026761765017', '1013e48036448a21ed92144dbccd90d903ed238d2480b7cdd98b698360ea8115']
root=Path(__file__).resolve().parent
chunks=[]
for name,digest in zip(PARTS,EXPECTED,strict=True):
 path=root/name;payload=path.read_bytes()
 if not path.is_file() or path.is_symlink() or hashlib.sha256(payload).hexdigest()!=digest:raise SystemExit("PHYSICAL_DRIVER_FRAGMENT_DIGEST_DRIFT:"+name)
 chunks.append(payload)
source=b"".join(chunks)
exec(compile(source,str(Path(__file__).resolve())+"<assembled>","exec"),{"__name__":"__main__","__file__":str(Path(__file__).resolve())})
