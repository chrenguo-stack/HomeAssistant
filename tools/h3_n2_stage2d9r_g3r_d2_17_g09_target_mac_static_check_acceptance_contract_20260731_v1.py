#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ACCEPTANCE_BINDING = "e8eda357a8dd6a25855808344ca0ebf44c9932e382c0ec5a308ab29634e6b264"
PENDING_BINDING = "03bd4217a0cd8426a78ba79619f3e9bd7e9cb4092082d1e7ae7bd7b6e1cdee15"
NEXT_GATE = "D1-H3N2-STAGE2D9R-G3R-D2-17-G09-PHYSICAL-EXECUTION-20260731-01"


class G09AcceptanceError(RuntimeError):
    pass


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise G09AcceptanceError("JSON_NOT_REGULAR")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G09AcceptanceError("JSON_NOT_OBJECT")
    return value


def verify_acceptance(value: dict[str, Any]) -> None:
    embedded = value.get("acceptance_binding_sha256")
    core = dict(value)
    core.pop("acceptance_binding_sha256", None)
    if embedded != ACCEPTANCE_BINDING or canonical_sha256(core) != ACCEPTANCE_BINDING:
        raise G09AcceptanceError("ACCEPTANCE_BINDING_DRIFT")

    required = {
        "status": "PASS",
        "state": "TARGET_MAC_STATIC_CHECK_ACCEPTED_AUTHORIZATION_UNCLAIMED_UNCONSUMED",
        "d2_request_id": "D2-H3N2-STAGE2D9R-G3R-EXECUTION-IDENTITY-FROZEN-PREFLIGHT-STABILIZED-PHYSICAL-20260730-17",
        "static_check_decision_id": "D1-H3N2-STAGE2D9R-G3R-D2-17-G09-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01",
        "acceptance_decision_id": "D1-H3N2-STAGE2D9R-G3R-D2-17-G09-TARGET-MAC-STATIC-CHECK-ACCEPTANCE-20260731-01",
        "package_generation": "G09",
        "private_source_sha": "bc7e30535dc569a3b82be17f531c39bd9c4dfabf",
        "private_delivery_binding_sha256": "47d9ed8e27cf3df6794de6148a94dbdf0b6724c7bf9104864a6763dcb42ba19c",
        "terminal_record_sha256": "14643799387e280f4af7dd0e4b657abe8602548b98f4b5ee2f53fcc7ad7428c0",
        "authorization_file_sha256": "f2c7bc598650d8a25f66f9ec6330220b0b4c5ffc367930fce58be10f89f7cc08",
        "authorization_record_sha256": "ea4be3dcc96d9b0b2b73ce709b26fe5d29aee9ccc091f5df29c0475e30d63224",
        "execution_identity_sha256": "9e234234aed566752ab8feb771e4cb84c3946d83857ee13d3d211d6c7e11f00c",
        "runtime_identity_adapter_sha256": "4b421d626e313a26c4815ef502b6aa76105a8685414ed2be3b4062a0387ef5ff",
        "configured_runtime_validator_file_sha256": "9b3546ee138c2a0def6796cd5cfa1d30c459873c663ad8bf04c8b961dd8e742f",
        "configured_runtime_validator_check_sha256": "0bcc30695853b0ee912a0305de6e9fc748f9d4d466ad136c11cd2c6fe4b1c8b7",
        "g08_expired_disposition_binding_sha256": "ad6dcc2ab884a358ae07d90ed157b27f5943757c85898a5440cf06f5b2c12795",
        "g09_reauthorization_pending_binding_sha256": "e504021fb44ae1dd3973582cb23b0b59c4d23339c3064fc7cf1c7e28756367c7",
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
            raise G09AcceptanceError("FIELD_DRIFT:" + key)

    expected_tools = {
        "esptool": "ab727aa71b9bbf794aab424eca706cb4b340be491ab28ba8fe17ef6d7962c267",
        "mosquitto": "4d53cf9654852472c9839e178848987603e16abd41622d197440945307227763",
        "openssl": "04ad05ce2e7eaf92116dac99a984cc0e589040a103589f93a9fe452832766973",
        "python": "4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a",
    }
    if value.get("target_tool_sha256") != expected_tools:
        raise G09AcceptanceError("TARGET_TOOL_DIGEST_DRIFT")


def verify_pending(value: dict[str, Any]) -> None:
    embedded = value.get("physical_pending_binding_sha256")
    core = dict(value)
    core.pop("physical_pending_binding_sha256", None)
    if embedded != PENDING_BINDING or canonical_sha256(core) != PENDING_BINDING:
        raise G09AcceptanceError("PHYSICAL_PENDING_BINDING_DRIFT")

    required = {
        "base_pr": 234,
        "base_head_sha": "bc7e30535dc569a3b82be17f531c39bd9c4dfabf",
        "decision_id": "D1-H3N2-STAGE2D9R-G3R-D2-17-G09-TARGET-MAC-STATIC-CHECK-ACCEPTANCE-20260731-01",
        "g09_acceptance_binding_sha256": ACCEPTANCE_BINDING,
        "authorization_record_sha256": "ea4be3dcc96d9b0b2b73ce709b26fe5d29aee9ccc091f5df29c0475e30d63224",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_execution_authorized": False,
        "next_gate": NEXT_GATE,
        "state": "PHYSICAL_EXECUTION_PENDING_EXPLICIT_AUTHORIZATION",
        "automatic_retry_permitted": False,
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise G09AcceptanceError("PENDING_FIELD_DRIFT:" + key)
    for key in ("ready", "merge", "release", "tag", "deployment"):
        if value.get(key) is not False:
            raise G09AcceptanceError("FORBIDDEN_STATE:" + key)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    verify_acceptance(
        load_json(root / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g09-target-mac-static-check-pass-20260731-v1.json")
    )
    verify_pending(
        load_json(root / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g09-physical-execution-pending-20260731-v1.json")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
