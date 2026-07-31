#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "tools/h3_n2_stage2d9r_g3r_d2_17_g14_target_mac_static_check_acceptance_contract_20260731_v1.py"
spec = importlib.util.spec_from_file_location("g14_acceptance", TARGET)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
raise SystemExit(module.main())
