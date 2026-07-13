from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from .t1_migration_readiness import CommandRunner

_NUMERIC_USER = re.compile(r"^(?P<uid>[0-9]+)(?::(?P<gid>[0-9]+))?$")
_EFFECTIVE_IDENTITY = re.compile(r"^(?P<uid>[0-9]+):(?P<gid>[0-9]+)$")


class ManagerRuntimeSecretOwnershipError(RuntimeError):
    pass


def _run(runner: CommandRunner, command: tuple[str, ...], message: str) -> str:
    code, output = runner.run(command)
    if code != 0:
        raise ManagerRuntimeSecretOwnershipError(message)
    return output.strip()


def _image_user(runner: CommandRunner, image_id: str) -> str:
    output = _run(
        runner,
        ("docker", "image", "inspect", image_id),
        "greenhouse-manager image user cannot be inspected",
    )
    try:
        documents = json.loads(output)
    except json.JSONDecodeError as error:
        raise ManagerRuntimeSecretOwnershipError(
            "greenhouse-manager image inspection returned invalid JSON"
        ) from error
    if (
        not isinstance(documents, list)
        or len(documents) != 1
        or not isinstance(documents[0], dict)
        or not isinstance(documents[0].get("Config"), dict)
    ):
        raise ManagerRuntimeSecretOwnershipError(
            "greenhouse-manager image user metadata is incomplete"
        )
    raw = documents[0]["Config"].get("User", "")
    if not isinstance(raw, str):
        raise ManagerRuntimeSecretOwnershipError(
            "greenhouse-manager image user metadata is invalid"
        )
    return raw.strip()


def _candidate_identity(runner: CommandRunner, image_id: str) -> tuple[int, int]:
    output = _run(
        runner,
        (
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "32",
            "--entrypoint",
            "/bin/sh",
            image_id,
            "-c",
            'set -eu; printf "%s:%s\\n" "$(id -u)" "$(id -g)"',
        ),
        "greenhouse-manager isolated runtime user probe failed",
    )
    match = _EFFECTIVE_IDENTITY.fullmatch(output)
    if match is None:
        raise ManagerRuntimeSecretOwnershipError(
            "greenhouse-manager isolated runtime user probe returned invalid output"
        )
    uid = int(match.group("uid"))
    gid = int(match.group("gid"))
    if uid == 0:
        raise ManagerRuntimeSecretOwnershipError(
            "greenhouse-manager runtime user must not be root"
        )
    return uid, gid


def _numeric_spec(value: str) -> tuple[int, int | None] | None:
    match = _NUMERIC_USER.fullmatch(value)
    if match is None:
        return None
    gid = match.group("gid")
    return int(match.group("uid")), int(gid) if gid is not None else None


def _verify_spec(value: str, uid: int, gid: int, label: str) -> None:
    numeric = _numeric_spec(value)
    if numeric is None:
        return
    expected_uid, expected_gid = numeric
    if expected_uid != uid or (expected_gid is not None and expected_gid != gid):
        raise ManagerRuntimeSecretOwnershipError(
            f"greenhouse-manager {label} user disagrees with isolated runtime identity"
        )


def resolve_manager_runtime_identity(
    document: Mapping[str, Any],
    runner: CommandRunner,
) -> dict[str, object]:
    config = document.get("Config")
    image_id = document.get("Image")
    if not isinstance(config, dict) or not isinstance(image_id, str) or not image_id:
        raise ManagerRuntimeSecretOwnershipError(
            "greenhouse-manager runtime identity metadata is incomplete"
        )
    raw_container_user = config.get("User", "")
    if not isinstance(raw_container_user, str):
        raise ManagerRuntimeSecretOwnershipError(
            "greenhouse-manager container user metadata is invalid"
        )
    container_user = raw_container_user.strip()
    image_user = _image_user(runner, image_id)
    effective_spec = container_user or image_user
    if not effective_spec:
        raise ManagerRuntimeSecretOwnershipError(
            "greenhouse-manager image has no non-root runtime user"
        )
    if container_user and image_user and container_user != image_user:
        container_numeric = _numeric_spec(container_user)
        image_numeric = _numeric_spec(image_user)
        if container_numeric is None or image_numeric is None or container_numeric != image_numeric:
            raise ManagerRuntimeSecretOwnershipError(
                "greenhouse-manager container and image user bindings disagree"
            )
    uid, gid = _candidate_identity(runner, image_id)
    _verify_spec(effective_spec, uid, gid, "effective")
    if container_user:
        _verify_spec(container_user, uid, gid, "container")
    if image_user:
        _verify_spec(image_user, uid, gid, "image")
    return {
        "manager_runtime_uid": uid,
        "manager_runtime_gid": gid,
        "manager_runtime_user_source": "container+image+isolated-candidate",
        "manager_runtime_image_id": image_id,
        "manager_runtime_user_spec": effective_spec,
    }


def verify_bound_runtime_identity(
    binding: Mapping[str, Any],
    *,
    image_id: object,
    user_spec: object,
) -> tuple[int, int]:
    uid = binding.get("manager_runtime_uid")
    gid = binding.get("manager_runtime_gid")
    source = binding.get("manager_runtime_user_source")
    bound_image = binding.get("manager_runtime_image_id")
    bound_spec = binding.get("manager_runtime_user_spec")
    if (
        not isinstance(uid, int)
        or isinstance(uid, bool)
        or uid <= 0
        or not isinstance(gid, int)
        or isinstance(gid, bool)
        or gid < 0
        or source != "container+image+isolated-candidate"
        or not isinstance(bound_image, str)
        or not bound_image
        or not isinstance(bound_spec, str)
        or not bound_spec
    ):
        raise ManagerRuntimeSecretOwnershipError(
            "manager runtime ownership binding is incomplete or unsafe"
        )
    if image_id != bound_image:
        raise ManagerRuntimeSecretOwnershipError(
            "greenhouse-manager image drifted from runtime ownership binding"
        )
    if not isinstance(user_spec, str) or (user_spec.strip() or bound_spec) != bound_spec:
        raise ManagerRuntimeSecretOwnershipError(
            "greenhouse-manager user spec drifted from runtime ownership binding"
        )
    _verify_spec(bound_spec, uid, gid, "bound")
    return uid, gid
