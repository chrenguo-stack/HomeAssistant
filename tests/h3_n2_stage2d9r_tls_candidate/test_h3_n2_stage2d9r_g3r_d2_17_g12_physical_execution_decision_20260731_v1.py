#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def canonical(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
dec=json.loads((ROOT/"docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g12-physical-execution-decision-20260731-v1.json").read_text())
pending=json.loads((ROOT/"docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g12-physical-execution-authorized-pending-20260731-v1.json").read_text())
for value,field,expected in ((dec,"physical_decision_binding_sha256","a97131f4a2e6e42d73992b029a5bf3e9ee3d6ab6778d212fe9ececdfd5fc5ac8"),(pending,"authorized_pending_binding_sha256","85dc4f789e85bbf415955027e4e7eb1bd4933be833a1e940d5842b039d4fd74d")):
 core=dict(value);supplied=core.pop(field);assert supplied==expected==canonical(core)
assert dec["decision_id"]=="D1-H3N2-STAGE2D9R-G3R-D2-17-G12-PHYSICAL-EXECUTION-20260731-01"
assert dec["authorization_record_sha256"]=="f670b5f5b637445a09975de1f9e0d23c3eda0d6c8910ec50a4e64a440b8a8963"
assert dec["acceptance_binding_sha256"]=="f7bcfce8d3c10f337076fbaba916526fde54f152fda3876e321ab304bdcc37ff"
assert dec["physical_pending_binding_sha256"]=="b7b1d4b71e815b28a2bb7468715abcdd5b9977962890f207a36c723122a3c64f"
assert dec["g12_repair_lineage_binding_sha256"]=="741fb6de67f9dd0722835827e249c49d0498d1b2b1966c118efd1f183c54e8a6"
assert dec["physical_execution_authorized"] is True
assert dec["activate_authorized"] is False and dec["cleanup_authorized"] is False
assert dec["replay_permitted"] is False and dec["automatic_retry_permitted"] is False
assert pending["physical_decision_binding_sha256"]=="a97131f4a2e6e42d73992b029a5bf3e9ee3d6ab6778d212fe9ececdfd5fc5ac8"
for name in ("h3_n2_stage2d9r_g3r_d2_17_g12_physical_execution_decision_driver_20260731_v1.py","h3_n2_stage2d9r_g3r_d2_17_g12_physical_runtime_adapter_entry_20260731_v1.py","h3_n2_stage2d9r_g3r_d2_17_g12_physical_decision_marker_finalizer_20260731_v1.py","run_h3_n2_stage2d9r_g3r_d2_17_g12_physical_execution_decision_20260731_v1.sh"):
 data=(ROOT/"tools"/name).read_text();assert "/Users/" not in data
loader=(ROOT/"tools"/"h3_n2_stage2d9r_g3r_d2_17_g12_physical_execution_decision_driver_20260731_v1.py").read_text();assert "PHYSICAL_DRIVER_FRAGMENT_DIGEST_DRIFT" in loader
parts=sorted((ROOT/"tools").glob("h3_n2_stage2d9r_g3r_d2_17_g12_physical_execution_decision_driver_20260731_v1.part*.pyfrag"));assert len(parts)==6
compile("".join(p.read_text() for p in parts),"<g12-logical>","exec")
print("G12_PHYSICAL_DECISION_PUBLIC_TEST_PASS")
