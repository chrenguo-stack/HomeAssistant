#!/usr/bin/env python3
"""Verified loader for the frozen D2-17 G04 physical-decision driver."""
from __future__ import annotations

import hashlib
from pathlib import Path

_PARTS = ['h3_n2_stage2d9r_g3r_d2_17_g04_physical_execution_decision_driver_20260730_v1.part1.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g04_physical_execution_decision_driver_20260730_v1.part2.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g04_physical_execution_decision_driver_20260730_v1.part3.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g04_physical_execution_decision_driver_20260730_v1.part4.pyfrag']
_EXPECTED = {'h3_n2_stage2d9r_g3r_d2_17_g04_physical_execution_decision_driver_20260730_v1.part1.pyfrag': 'ffa88625d02164545ad3d241a40a40f2ed380d84f45c989ee2734685105fdc43', 'h3_n2_stage2d9r_g3r_d2_17_g04_physical_execution_decision_driver_20260730_v1.part2.pyfrag': 'a4d863986eec3422b74a3cc1dbc97b0ec74e1374096bfcb456cb9badea41d0b9', 'h3_n2_stage2d9r_g3r_d2_17_g04_physical_execution_decision_driver_20260730_v1.part3.pyfrag': '10f675122cd5f5c863b3ff5ebe331176eb7c667230e9463ccc6ea50d8cdb7b2d', 'h3_n2_stage2d9r_g3r_d2_17_g04_physical_execution_decision_driver_20260730_v1.part4.pyfrag': '2c95430563541138bbf325e4d31963e18854712c96359f502a454321822b9a04'}
_ASSEMBLED_SHA256 = '3a5d7b636f4283d45793097a008f1b0adfded27158277fcaa1026262f10661ff'
_root = Path(__file__).resolve().parent
_payload = bytearray()
for _name in _PARTS:
    _path = _root / _name
    _data = _path.read_bytes()
    if hashlib.sha256(_data).hexdigest() != _EXPECTED[_name]:
        raise SystemExit("PHYSICAL_DECISION_DRIVER_PART_DIGEST_DRIFT:" + _name)
    _payload.extend(_data)
if hashlib.sha256(_payload).hexdigest() != _ASSEMBLED_SHA256:
    raise SystemExit("PHYSICAL_DECISION_DRIVER_ASSEMBLED_DIGEST_DRIFT")
exec(compile(bytes(_payload), str(_root / "assembled_physical_decision_driver.py"), "exec"), globals())
