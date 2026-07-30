#!/usr/bin/env python3
"""Verified loader for the frozen D2-17 G02 physical-decision driver."""
from __future__ import annotations

import hashlib
from pathlib import Path

_PARTS = ['h3_n2_stage2d9r_g3r_d2_17_g02_physical_execution_decision_driver_20260730_v1.part1.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g02_physical_execution_decision_driver_20260730_v1.part2.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g02_physical_execution_decision_driver_20260730_v1.part3.pyfrag', 'h3_n2_stage2d9r_g3r_d2_17_g02_physical_execution_decision_driver_20260730_v1.part4.pyfrag']
_EXPECTED = {'h3_n2_stage2d9r_g3r_d2_17_g02_physical_execution_decision_driver_20260730_v1.part1.pyfrag': 'e398b17c45069ba0f0fccc8452103308074573e5e3e6a3eb6e46852ab8f90b96', 'h3_n2_stage2d9r_g3r_d2_17_g02_physical_execution_decision_driver_20260730_v1.part2.pyfrag': '7e0277e4a3f5e1442772a0a008d85b35e8ac1a6236aaf0daf33421248fd37b81', 'h3_n2_stage2d9r_g3r_d2_17_g02_physical_execution_decision_driver_20260730_v1.part3.pyfrag': 'a34cf7cf17c7becad01c6a61c0e783dd7ecd5ab00e69ddff9df3c3ff6197f7a4', 'h3_n2_stage2d9r_g3r_d2_17_g02_physical_execution_decision_driver_20260730_v1.part4.pyfrag': '5bf86976c851805875e46fda3a95c876ca0179fd8fccb2a0f6cb194d9582367f'}
_ASSEMBLED_SHA256 = 'b2eed827390fe918a0b4a40c0ca040cec5a5d1976e43aca5eccd3220f882b594'
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
