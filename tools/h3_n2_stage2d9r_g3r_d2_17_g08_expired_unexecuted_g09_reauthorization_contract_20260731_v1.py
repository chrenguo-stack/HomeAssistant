#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

DISPOSITION_BINDING = "ad6dcc2ab884a358ae07d90ed157b27f5943757c85898a5440cf06f5b2c12795"
PENDING_BINDING = "abc99085817be35138d7ab0b121831f85a88a4d869e8d81a2365b373b822bc9a"
NEXT_GATE = "D1-H3N2-STAGE2D9R-G3R-D2-17-G09-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01"


class G08ExpiryContractError(RuntimeError):
    pass


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise G08ExpiryContractError("JSON_NOT_REGULAR")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G08ExpiryContractError("JSON_NOT_OBJECT")
    return value


def verify_disposition(value: dict[str, Any]) -> None:
    embedded = value.get("disposition_binding_sha256")
    core = dict(value)
    core.pop("disposition_binding_sha256", None)
    if embedded != DISPOSITION_BINDING or canonical_sha256(core) != DISPOSITION_BINDING:
        raise G08ExpiryContractError("DISPOSITION_BINDING_DRIFT")

    required = {
        "state": "EXPIRED_UNEXECUTED_RETIRED_NO_REPLAY",
        "package_generation": "G08",
        "operator_reported_not_executed": True,
        "authorization_expires_at": "2026-07-31T01:53:32.629244Z",
        "authorization_claimed": False,
        "authorization_consumed": False,
        "physical_runtime_created": False,
        "replay_permitted": False,
        "automatic_retry_permitted": False,
        "physical_decision_source_sha": "3abffa37397d05d1e8cf3b801c2c1f3b766269be",
        "physical_decision_artifact_id": 8779498017,
        "physical_decision_artifact_sha256": "f22043a49b692c647a97d517693f9567ed8589d9504b871297d4ee30a6d4037d",
        "operator_package_sha256": "a97913eedbb267989904a018b8e5fe987b5ff89bfafb989ccbbd945d69b1e46d",
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise G08ExpiryContractError("DISPOSITION_FIELD_DRIFT:" + key)

    for key in (
        "board_operation",
        "usb_enumeration",
        "serial_operation",
        "esptool_operation",
        "flash_operation",
        "physical_nvs_operation",
        "broker_started",
        "prepare_executed",
        "verify_executed",
        "recovery_executed",
    ):
        if value.get(key) is not False:
            raise G08ExpiryContractError("UNEXECUTED_FLAG_DRIFT:" + key)


def verify_pending(value: dict[str, Any]) -> None:
    embedded = value.get("pending_binding_sha256")
    core = dict(value)
    core.pop("pending_binding_sha256", None)
    if embedded != PENDING_BINDING or canonical_sha256(core) != PENDING_BINDING:
        raise G08ExpiryContractError("PENDING_BINDING_DRIFT")

    required = {
        "base_pr": 233,
        "base_head_sha": "3abffa37397d05d1e8cf3b801c2c1f3b766269be",
        "g08_expired_disposition_binding_sha256": DISPOSITION_BINDING,
        "g08_authorization_reusable": False,
        "g08_operator_package_reusable": False,
        "g08_private_runtime_reusable": False,
        "g08_static_check_replay_permitted": False,
        "next_package_generation": "G09",
        "next_gate": NEXT_GATE,
        "g09_private_package_created": False,
        "g09_authorization_created": False,
        "g09_physical_execution_authorized": False,
        "state": "G09_PRIVATE_PACKAGE_AND_STATIC_CHECK_EXPLICIT_AUTHORIZATION_PENDING",
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise G08ExpiryContractError("PENDING_FIELD_DRIFT:" + key)

    for key in (
        "board_operation",
        "usb_enumeration",
        "serial_operation",
        "esptool_operation",
        "flash_operation",
        "physical_nvs_operation",
        "broker_started",
        "prepare_executed",
        "verify_executed",
        "recovery_executed",
        "ready",
        "merge",
        "release",
        "tag",
        "deployment",
    ):
        if value.get(key) is not False:
            raise G08ExpiryContractError("FORBIDDEN_STATE:" + key)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    disposition = load_json(
        root
        / "docs/acceptance/h3-n2-stage2d9r-g3r-d2-17-g08-expired-unexecuted-disposition-20260731-v1.json"
    )
    pending = load_json(
        root
        / "docs/decisions/h3-n2-stage2d9r-g3r-d2-17-g09-private-package-static-check-authorization-pending-20260731-v1.json"
    )
    verify_disposition(disposition)
    verify_pending(pending)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
