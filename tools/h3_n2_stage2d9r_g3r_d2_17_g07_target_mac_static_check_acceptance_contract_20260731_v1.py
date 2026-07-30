#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any

class G07AcceptanceError(RuntimeError): pass

def canonical_sha256(value: Any) -> str:
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()

def load_json(path: Path) -> dict[str,Any]:
    if path.is_symlink() or not path.is_file(): raise G07AcceptanceError("JSON_NOT_REGULAR")
    value=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value,dict): raise G07AcceptanceError("JSON_NOT_OBJECT")
    return value

def verify_acceptance(value: dict[str,Any]) -> None:
    embedded=value.get("acceptance_binding_sha256")
    core=dict(value); core.pop("acceptance_binding_sha256",None)
    if embedded!="0f2e281c6ed0669ebc6629aefdaeab7e5382b84d17372b75cf2ab434eaac643e" or canonical_sha256(core)!="0f2e281c6ed0669ebc6629aefdaeab7e5382b84d17372b75cf2ab434eaac643e":
        raise G07AcceptanceError("ACCEPTANCE_BINDING_DRIFT")
    required={"status":"PASS","state":"TARGET_MAC_STATIC_CHECK_ACCEPTED_AUTHORIZATION_UNCLAIMED_UNCONSUMED",
    "d2_request_id":"D2-H3N2-STAGE2D9R-G3R-EXECUTION-IDENTITY-FROZEN-PREFLIGHT-STABILIZED-PHYSICAL-20260730-17","static_check_decision_id":"D1-H3N2-STAGE2D9R-G3R-D2-17-G07-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260730-01",
    "acceptance_decision_id":"D1-H3N2-STAGE2D9R-G3R-D2-17-G07-TARGET-MAC-STATIC-CHECK-ACCEPTANCE-20260731-01","package_generation":"G07",
    "private_source_sha":"662406f97a023c4edc71d6bc17841828d0cc7c36",
    "private_delivery_binding_sha256":"b1b213b82f8e7b3b954fc2c37eeb0e1d0da22d1c4c54731f9014555f32c329d7",
    "terminal_record_sha256":"7916d2ac33f9010a215b4f5f8698eb7b4d2c9a833b27aa8697cc2ddf83f2d029",
    "authorization_record_sha256":"37fa9803c4ce96083f2b58d4b973c8373326c179d609645f35af1ec72076a601",
    "authorization_created":True,"authorization_claimed":False,"authorization_consumed":False,
    "physical_decision_created":False,"all_physical_operation_flags_false":True,
    "canonical_outer_sha256":"2083652dfeedb93c71ac589300b155c1102fd6354dbeb31ecd588669a97b7994",
    "inner_launcher_sha256":"2dfe1e1118e37c9abc539a800c06e45901dd40966697d4e00b9d542f37db531e"}
    for k,e in required.items():
        if value.get(k)!=e: raise G07AcceptanceError("FIELD_DRIFT:"+k)
    tools={"esptool":"ab727aa71b9bbf794aab424eca706cb4b340be491ab28ba8fe17ef6d7962c267",
    "mosquitto":"4d53cf9654852472c9839e178848987603e16abd41622d197440945307227763",
    "openssl":"04ad05ce2e7eaf92116dac99a984cc0e589040a103589f93a9fe452832766973",
    "python":"4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a"}
    if value.get("target_tool_sha256")!=tools: raise G07AcceptanceError("TARGET_TOOL_DIGEST_DRIFT")

def verify_pending(value: dict[str,Any]) -> None:
    embedded=value.get("physical_pending_binding_sha256")
    core=dict(value); core.pop("physical_pending_binding_sha256",None)
    if embedded!="597edc89d0cda2dfa4effb0345560d974953b209dc4084728bea4e704f3f6691" or canonical_sha256(core)!="597edc89d0cda2dfa4effb0345560d974953b209dc4084728bea4e704f3f6691":
        raise G07AcceptanceError("PHYSICAL_PENDING_BINDING_DRIFT")
    if value.get("next_gate")!="D1-H3N2-STAGE2D9R-G3R-D2-17-G07-PHYSICAL-EXECUTION-20260731-01": raise G07AcceptanceError("NEXT_GATE_DRIFT")
    if value.get("physical_execution_authorized") is not False:
        raise G07AcceptanceError("PHYSICAL_EXECUTION_ALREADY_AUTHORIZED")
    for k in ("ready","merge","release","tag","deployment"):
        if value.get(k) is not False: raise G07AcceptanceError("FORBIDDEN_STATE:"+k)

def main() -> int:
    root=Path(__file__).resolve().parents[1]
    verify_acceptance(load_json(root/"docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g07-target-mac-static-check-pass-20260731-v1.json"))
    verify_pending(load_json(root/"docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g07-physical-execution-pending-20260731-v1.json"))
    return 0
if __name__=="__main__": raise SystemExit(main())
