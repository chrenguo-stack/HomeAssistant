#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def canonical(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
dec=json.loads((ROOT/"docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g13-physical-execution-decision-20260731-v1.json").read_text())
pending=json.loads((ROOT/"docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g13-physical-execution-authorized-pending-20260731-v1.json").read_text())
for value,field,expected in ((dec,"physical_decision_binding_sha256",'313280a26f193a36fbb4c4af5bbcb9af953cbf8551d16c4145b823849b5cf6b5'),(pending,"authorized_pending_binding_sha256",'af5e0918ab2f20effbf8e33d259208156b41992bef054c59a81fc92529a770a4')):
 core=dict(value);supplied=core.pop(field);assert supplied==expected==canonical(core)
assert dec["decision_id"]=='D1-H3N2-STAGE2D9R-G3R-D2-17-G13-PHYSICAL-EXECUTION-20260731-01'
assert dec["authorization_record_sha256"]=='5eb016ae2ac929dcb5d407aaf16a1ffdbdffea743a60a376d244be03b398c75a'
assert dec["acceptance_binding_sha256"]=='80d85d4e44eaeff5f0eaaa979fd34651547f4aa5b055cc2d5ddfe9d46d4ae92a'
assert dec["physical_pending_binding_sha256"]=='c87b17599c3c7e20182ca2c8ddc5abba0c49d8bfb7cda46bba48f2acf5b1ab03'
assert dec["g13_repair_lineage_binding_sha256"]=='6b55377ca34d2c71e9653ef1708ce4ad8a2c06ef5b936b7c2ce1e715561ae596'
assert dec["g12_disposition_binding_sha256"]=='bbc16258410a53363349c7b71323f0b7fcb33548f561dfa3b0dc71be5fcb7bc3'
assert dec["physical_execution_authorized"] is True
assert dec["activate_authorized"] is False and dec["cleanup_authorized"] is False
assert dec["replay_permitted"] is False and dec["automatic_retry_permitted"] is False
assert pending["physical_decision_binding_sha256"]=='313280a26f193a36fbb4c4af5bbcb9af953cbf8551d16c4145b823849b5cf6b5'
for name in ('h3_n2_stage2d9r_g3r_d2_17_g13_physical_execution_decision_driver_20260731_v1.py','h3_n2_stage2d9r_g3r_d2_17_g13_physical_runtime_adapter_entry_20260731_v1.py','h3_n2_stage2d9r_g3r_d2_17_g13_physical_decision_marker_finalizer_20260731_v1.py','run_h3_n2_stage2d9r_g3r_d2_17_g13_physical_execution_decision_20260731_v1.sh'):
 data=(ROOT/"tools"/name).read_text();assert "/Users/" not in data
loader=(ROOT/"tools"/'h3_n2_stage2d9r_g3r_d2_17_g13_physical_execution_decision_driver_20260731_v1.py').read_text();assert "PHYSICAL_DRIVER_FRAGMENT_DIGEST_DRIFT" in loader
parts=sorted((ROOT/"tools").glob("h3_n2_stage2d9r_g3r_d2_17_g13_physical_execution_decision_driver_20260731_v1.part*.pyfrag"));assert len(parts)==6
logical="".join(p.read_text() for p in parts);compile(logical,"<g13-logical>","exec")
assert "derive_authorization_state" in logical and "G13_BASELINE_COMPATIBILITY_INSTALL_FAILED" in logical
print("G13_PHYSICAL_DECISION_PUBLIC_TEST_PASS")
