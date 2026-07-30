#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class G08AcceptanceError(RuntimeError):
    pass


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise G08AcceptanceError("JSON_NOT_REGULAR")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G08AcceptanceError("JSON_NOT_OBJECT")
    return value


def verify_acceptance(value: dict[str, Any]) -> None:
    expected_binding = "7e260a96ac1812fdf18730657c78d9d7d7c17c8a3fb0f9e7afb2b1a2b0357d4c"
    embedded = value.get("acceptance_binding_sha256")
    core = dict(value)
    core.pop("acceptance_binding_sha256", None)
    if embedded != expected_binding or canonical_sha256(core) != expected_binding:
        raise G08AcceptanceError("ACCEPTANCE_BINDING_DRIFT")

    required = {
        "status": "PASS",
        "state": "TARGET_MAC_STATIC_CHECK_ACCEPTED_AUTHORIZATION_UNCLAIMED_UNCONSUMED",
        "d2_request_id": "D2-H3N2-STAGE2D9R-G3R-EXECUTION-IDENTITY-FROZEN-PREFLIGHT-STABILIZED-PHYSICAL-20260730-17",
        "static_check_decision_id": "D1-H3N2-STAGE2D9R-G3R-D2-17-G08-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01",
        "acceptance_decision_id": "D1-H3N2-STAGE2D9R-G3R-D2-17-G08-TARGET-MAC-STATIC-CHECK-ACCEPTANCE-20260731-01",
        "package_generation": "G08",
        "private_source_sha": "13da1725a1abef398fec2edf6c053a34911b02d3",
        "private_delivery_binding_sha256": "de29e81f317c09a8ca6c330e35ae492f10408ff3f2e42e1f0587b0f228c366e6",
        "terminal_record_sha256": "18557a68c6be29710bc65d681b7aa83ff293835acf7389cbebf0e23d5fca297b",
        "authorization_file_sha256": "938b6cfe18e1ed365a15614e6e5735220ad13f730c4796a9d6e9d383be07626e",
        "authorization_record_sha256": "76e089d31b40b0fefd1fd6613592e9be3d71ae03e1b063d26e7c1701430b46bb",
        "execution_identity_sha256": "9e234234aed566752ab8feb771e4cb84c3946d83857ee13d3d211d6c7e11f00c",
        "runtime_identity_adapter_sha256": "4b421d626e313a26c4815ef502b6aa76105a8685414ed2be3b4062a0387ef5ff",
        "configured_runtime_validator_file_sha256": "8289d8daefd3941a52a1ef4e3e17cac9ccd9da14f803fc94569b9efe855e3fa8",
        "configured_runtime_validator_check_sha256": "73b4f52441643b4b7209745abdcb7357dbff16e68c20c780ce5b1ac21e472561",
        "g07_failure_refinement_binding_sha256": "4b5c6d7af0202a13325c3a620fd971eee16fe70e4d4c024f91ba0a1b25a14339",
        "g07_identity_adapter_repair_decision_binding_sha256": "d35a84162a8900222eff08dc7b8df6776caa336cc58e367a122ea685678163ba",
        "authorization_created": True,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_decision_created": False,
        "all_physical_operation_flags_false": True,
        "identity_adapter_installed": True,
        "configured_core_validate_authorization_executed": True,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise G08AcceptanceError("FIELD_DRIFT:" + key)

    expected_tools = {
        "esptool": "ab727aa71b9bbf794aab424eca706cb4b340be491ab28ba8fe17ef6d7962c267",
        "mosquitto": "4d53cf9654852472c9839e178848987603e16abd41622d197440945307227763",
        "openssl": "04ad05ce2e7eaf92116dac99a984cc0e589040a103589f93a9fe452832766973",
        "python": "4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a",
    }
    if value.get("target_tool_sha256") != expected_tools:
        raise G08AcceptanceError("TARGET_TOOL_DIGEST_DRIFT")


def verify_pending(value: dict[str, Any]) -> None:
    expected_binding = "665a418114a4f8ef274bc264505f366ffffe8be93b879640999a7936720a4abb"
    embedded = value.get("physical_pending_binding_sha256")
    core = dict(value)
    core.pop("physical_pending_binding_sha256", None)
    if embedded != expected_binding or canonical_sha256(core) != expected_binding:
        raise G08AcceptanceError("PHYSICAL_PENDING_BINDING_DRIFT")

    required = {
        "base_pr": 231,
        "base_head_sha": "13da1725a1abef398fec2edf6c053a34911b02d3",
        "decision_id": "D1-H3N2-STAGE2D9R-G3R-D2-17-G08-TARGET-MAC-STATIC-CHECK-ACCEPTANCE-20260731-01",
        "g08_acceptance_binding_sha256": "7e260a96ac1812fdf18730657c78d9d7d7c17c8a3fb0f9e7afb2b1a2b0357d4c",
        "authorization_record_sha256": "76e089d31b40b0fefd1fd6613592e9be3d71ae03e1b063d26e7c1701430b46bb",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_execution_authorized": False,
        "next_gate": "D1-H3N2-STAGE2D9R-G3R-D2-17-G08-PHYSICAL-EXECUTION-20260731-01",
        "state": "PHYSICAL_EXECUTION_PENDING_EXPLICIT_AUTHORIZATION",
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise G08AcceptanceError("PENDING_FIELD_DRIFT:" + key)
    for key in ("ready", "merge", "release", "tag", "deployment"):
        if value.get(key) is not False:
            raise G08AcceptanceError("FORBIDDEN_STATE:" + key)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    verify_acceptance(
        load_json(
            root
            / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g08-target-mac-static-check-pass-20260731-v1.json"
        )
    )
    verify_pending(
        load_json(
            root
            / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g08-physical-execution-pending-20260731-v1.json"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
