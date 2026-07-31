#!/usr/bin/env python3
"""Content-bound fragment loader for the one-shot G13 physical driver."""
from __future__ import annotations
import hashlib
from pathlib import Path
PARTS=['h3_n2_stage2d9r_g3r_d2_17_g13_physical_execution_decision_driver_20260731_v1.part1.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g13_physical_execution_decision_driver_20260731_v1.part2.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g13_physical_execution_decision_driver_20260731_v1.part3.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g13_physical_execution_decision_driver_20260731_v1.part4.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g13_physical_execution_decision_driver_20260731_v1.part5.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g13_physical_execution_decision_driver_20260731_v1.part6.pyfrag']
EXPECTED=['ed1d31b39fd690988abcee74b81b7cfdca4705577a76a2e48877dcde6f63fbf8', 'df2c784bfd59fd49c6350774418cbca2cf1372fe62692da2161f2f5d23aa35fe', '0106c5b67097d9eda206bbd2f0078f32709e816e74b0b047de5907661abf24ff', '9a429d0034a6ea4a9717bd0775d96f47332d28b24cbaed3068a23fd7626ca2a0', '4d5382ea35e7aa6e951691bbd9957825ca8d816ab82a403c2c6ed3c2484d312f', '3d83b4a9b14ca1e282d2ef09114852bdc30c92aeb6f4216c6d82b893ce00743e']
root=Path(__file__).resolve().parent
chunks=[]
for name,digest in zip(PARTS,EXPECTED,strict=True):
 path=root/name;payload=path.read_bytes()
 if not path.is_file() or path.is_symlink() or hashlib.sha256(payload).hexdigest()!=digest:raise SystemExit("PHYSICAL_DRIVER_FRAGMENT_DIGEST_DRIFT:"+name)
 chunks.append(payload)
source=b"".join(chunks)
exec(compile(source,str(Path(__file__).resolve())+"<assembled>","exec"),{"__name__":"__main__","__file__":str(Path(__file__).resolve())})
