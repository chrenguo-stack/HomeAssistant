#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def canonical(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
dec=json.loads((ROOT/"docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g14-physical-execution-decision-20260731-v1.json").read_text())
pending=json.loads((ROOT/"docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g14-physical-execution-authorized-pending-20260731-v1.json").read_text())
for value,field,expected in ((dec,"physical_decision_binding_sha256",'4eab159a58853a1e99e9e77d7aa07b6859dfda6136f8c496731946798dd7550d'),(pending,"authorized_pending_binding_sha256",'4535ec7283b110b22db62aea26b55c81f0bf4b32ad0562da4898c3ab9c29dd33')):
 core=dict(value);supplied=core.pop(field);assert supplied==expected==canonical(core)
assert dec["decision_id"]=='D1-H3N2-STAGE2D9R-G3R-D2-17-G14-PHYSICAL-EXECUTION-20260731-01'
assert dec["authorization_record_sha256"]=='47bd58b60acb94ccf3d9e470359936fd8b610987dba99cc81adcddaf09ce1b29'
assert dec["acceptance_binding_sha256"]=='44e21d03db295975439c77389f57b89b57e838db74a67c644035822d914adfe4'
assert dec["physical_pending_binding_sha256"]=='18b5d0f710ac8cd2bb1c889745795e5820a8df8ffceda0aebe1bb924cb0cc675'
assert dec["g14_repair_lineage_binding_sha256"]=='a91a3b699122ee83af663ef2c014115d1db02b28b9aa8890876a810462023d92'
assert dec["g13_disposition_binding_sha256"]=='2c37dcd807731d47c25f7a5b6a2ec0a03add0efc01ee461526cd95f86868915c'
assert dec["physical_execution_authorized"] is True
assert dec["activate_authorized"] is False and dec["cleanup_authorized"] is False
assert dec["replay_permitted"] is False and dec["automatic_retry_permitted"] is False
assert pending["physical_decision_binding_sha256"]=='4eab159a58853a1e99e9e77d7aa07b6859dfda6136f8c496731946798dd7550d'
for name in ('h3_n2_stage2d9r_g3r_d2_17_g14_physical_execution_decision_driver_20260731_v1.py','h3_n2_stage2d9r_g3r_d2_17_g14_physical_runtime_adapter_entry_20260731_v1.py','h3_n2_stage2d9r_g3r_d2_17_g14_physical_decision_marker_finalizer_20260731_v1.py','run_h3_n2_stage2d9r_g3r_d2_17_g14_physical_execution_decision_20260731_v1.sh'):
 data=(ROOT/"tools"/name).read_text();assert "/Users/" not in data
loader=(ROOT/"tools"/'h3_n2_stage2d9r_g3r_d2_17_g14_physical_execution_decision_driver_20260731_v1.py').read_text();assert "PHYSICAL_DRIVER_FRAGMENT_DIGEST_DRIFT" in loader
parts=sorted((ROOT/"tools").glob("h3_n2_stage2d9r_g3r_d2_17_g14_physical_execution_decision_driver_20260731_v1.part*.pyfrag"));assert len(parts)==6
logical="".join(p.read_text() for p in parts);compile(logical,"<g14-logical>","exec")
assert "mode-normalized-execution-package" in logical and "validate_content_equivalence" in logical
assert "derive_authorization_state" in logical and "G13_BASELINE_COMPATIBILITY_INSTALL_FAILED" in logical
assert "g14_all_execution_view_files_mode_0600" in logical
print("G14_PHYSICAL_DECISION_PUBLIC_TEST_PASS")
