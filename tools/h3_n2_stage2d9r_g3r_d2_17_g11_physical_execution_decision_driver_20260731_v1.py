#!/usr/bin/env python3
"""Content-bound fragment loader for the one-shot G11 physical driver."""
from __future__ import annotations
import hashlib
from pathlib import Path
PARTS = ['h3_n2_stage2d9r_g3r_d2_17_g11_physical_execution_decision_driver_20260731_v1.part1.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g11_physical_execution_decision_driver_20260731_v1.part2.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g11_physical_execution_decision_driver_20260731_v1.part3.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g11_physical_execution_decision_driver_20260731_v1.part4.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g11_physical_execution_decision_driver_20260731_v1.part5.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g11_physical_execution_decision_driver_20260731_v1.part6.pyfrag']
EXPECTED = ['ebd2905720125a8248c1f12e6ba2271e617012529bb35a52aba832024b57deac', '35fcd61bb756f68a2a2691ef5c560ac4aa69058357c1c07138d8c09146d2f5bf', 'f9fd86637bba5fa8335fd3dcfd11304f4023c07265873c8bddbf2e6e11f792e6', 'a59efcc6ac611e94ffd81fc81f102150627a74d4586213943354fec33c8f6090', '4cdf47662d49bcba2abf5b3a42f4bd8ff3221765cc25e59cdcbe149770898cb3', '9abe07e308653aa4e07f03deb99067fc0bdfa2516d85ca28ff43c95d570b299c']
root=Path(__file__).resolve().parent
chunks=[]
for name,digest in zip(PARTS,EXPECTED,strict=True):
    path=root/name
    payload=path.read_bytes()
    if not path.is_file() or path.is_symlink() or hashlib.sha256(payload).hexdigest()!=digest:
        raise SystemExit("PHYSICAL_DRIVER_FRAGMENT_DIGEST_DRIFT:"+name)
    chunks.append(payload)
source=b"".join(chunks)
exec(compile(source,str(Path(__file__).resolve())+"<assembled>","exec"),{"__name__":"__main__","__file__":str(Path(__file__).resolve())})
