from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol

from .t1_broker_identity_activation_handoff import (
    BrokerIdentityActivationHandoffError,
    verify_broker_identity_activation_handoff,
)

Verifier = Callable[..., dict[str, object]]


class Runner(Protocol):
    def run(
        self,
        command: Sequence[str],
        *,
        input_text: str | None = None,
    ) -> tuple[int, str]: ...


class BrokerIdentityActivationCheckError(RuntimeError):
    pass


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise BrokerIdentityActivationCheckError(f"{label} is missing or unsafe")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BrokerIdentityActivationCheckError(f"{label} is invalid") from error
    if not isinstance(value, dict):
        raise BrokerIdentityActivationCheckError(f"{label} must be an object")
    return value


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_success(
    runner: Runner,
    command: Sequence[str],
    message: str,
    *,
    input_text: str | None = None,
) -> str:
    code, output = runner.run(tuple(command), input_text=input_text)
    if code != 0:
        raise BrokerIdentityActivationCheckError(message)
    return output


def container_runtime(runner: Runner, name: str) -> dict[str, object]:
    template = json.dumps(
        {
            "state": "{{.State.Status}}",
            "restarts": "{{.RestartCount}}",
            "image_id": "{{.Image}}",
        },
        separators=(",", ":"),
    )
    output = require_success(
        runner,
        ("docker", "inspect", "-f", template, name),
        f"container cannot be inspected: {name}",
    )
    try:
        value = json.loads(output)
    except json.JSONDecodeError as error:
        raise BrokerIdentityActivationCheckError(
            f"container inspection returned invalid JSON: {name}"
        ) from error
    if not isinstance(value, dict):
        raise BrokerIdentityActivationCheckError(f"container inspection is invalid: {name}")
    return {
        "state": str(value.get("state", "unknown")),
        "restart_count": int(value.get("restarts", -1)),
        "image_id": str(value.get("image_id", "unknown")),
    }


def runtime_summary(runner: Runner) -> dict[str, dict[str, object]]:
    return {
        name: container_runtime(runner, name) for name in ("mosquitto", "greenhouse-manager", "homeassistant")
    }


def runtime_healthy(runtime: dict[str, dict[str, object]]) -> bool:
    return all(item.get("state") == "running" and item.get("restart_count") == 0 for item in runtime.values())


def validated_handoff(
    root: Path,
    verifier: Verifier = verify_broker_identity_activation_handoff,
) -> tuple[dict[str, Any], dict[str, Any]]:
    verified = verifier(root)
    required = {
        "fresh_rollback_verified": True,
        "candidate_rehearsal_verified": True,
        "preserve_anonymous": True,
        "apply_enabled": False,
        "operator_action_authorized": False,
        "ready_for_live_activation": False,
        "current_services_modified": False,
    }
    for field, expected in required.items():
        if verified.get(field) != expected:
            raise BrokerIdentityActivationCheckError(f"activation handoff verification failed: {field}")
    manifest = read_json(root / "manifest.json", "activation handoff manifest")
    plan = read_json(root / "activation-plan.json", "activation handoff plan")
    if (
        manifest.get("schema") != "gh.m2.t1-broker-identity-activation-handoff/1"
        or plan.get("schema") != "gh.m2.t1-broker-identity-activation-plan/1"
    ):
        raise BrokerIdentityActivationCheckError("activation handoff schema is invalid")
    return manifest, plan


__all__ = [
    "BrokerIdentityActivationCheckError",
    "BrokerIdentityActivationHandoffError",
    "Runner",
    "Verifier",
    "read_json",
    "require_success",
    "runtime_healthy",
    "runtime_summary",
    "sha256_path",
    "validated_handoff",
]
