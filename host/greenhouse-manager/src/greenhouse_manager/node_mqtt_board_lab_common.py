from __future__ import annotations

import hashlib
import ipaddress
import json
import stat
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

SCHEMA = "gh.m2.node-mqtt-board-lab/1"
MANIFEST_SCHEMA = "gh.m2.node-mqtt-board-lab-manifest/1"
OBSERVATION_SCHEMA = "gh.m2.node-mqtt-board-lab-observation/1"
SUMMARY_SCHEMA = "gh.m2.node-mqtt-board-lab-summary/1"
DEFAULT_IMAGE = "eclipse-mosquitto:2.0.22"
CONFIRMATION = "M2-NONPRODUCTION-BOARD-LAB"
CONTAINER_PREFIX = "gh-m2-board-lab-"
MARKER_NAME = ".gh-node-mqtt-board-lab"
MANIFEST_NAME = "manifest.json"
SECRETS_NAME = "lab-secrets.json"
ESPHOME_SECRETS_NAME = "secrets.yaml"
CONFIG_NAME = "mosquitto.conf"
ACL_NAME = "acl"
PASSWORD_NAME = "passwd"
MATRIX_NAME = "fault-matrix.jsonl"

CANDIDATE_USERNAME = "ghn_lab-board"
CANDIDATE_CLIENT_ID = "lab-board"
ANONYMOUS_CLIENT_ID = "lab-board-anon"
OBSERVER_USERNAME = "gho_lab-observer"

REQUIRED_CASE_IDS = (
    "boot.first_flash_anonymous",
    "boot.local_functions_without_broker",
    "boot.anonymous_persists_after_restart",
    "candidate.activate_and_reboot",
    "candidate.fixed_client_id",
    "candidate.valid_connect_and_heartbeat",
    "candidate.failure_counter_clears",
    "candidate.enters_observation",
    "candidate.observation_one_of_three",
    "candidate.observation_three_of_three",
    "candidate.ready_without_auto_commit",
    "candidate.commit_requires_authorization",
    "invalid.generic_failure_classification",
    "invalid.failure_counter_persists",
    "invalid.threshold_selects_anonymous",
    "invalid.safe_reboot_to_anonymous",
    "invalid.anonymous_client_id",
    "invalid.candidate_material_retained",
    "invalid.local_functions_continue",
    "network.wifi_loss_candidate",
    "network.broker_stop_candidate",
    "network.broker_restore_candidate",
    "network.wifi_loss_anonymous",
    "network.broker_stop_anonymous",
    "network.broker_restore_anonymous",
    "power.reboot_hold_hook",
    "power.candidate_staged_before_reboot",
    "power.candidate_connecting",
    "power.observation_one_of_three",
    "power.ready_uncommitted",
    "power.committed",
    "power.fallback_state_written",
    "power.rollback_state_written",
    "rollback.candidate_lease_expired",
    "rollback.during_observation",
    "rollback.after_commit",
    "rollback.while_broker_unreachable",
    "rollback.anonymous_recovers",
    "rollback.no_secret_disclosure",
    "rollback.no_secure_erase_claim",
    "logs.esphome_config",
    "logs.compile",
    "logs.serial",
    "logs.heartbeat",
    "logs.preferences_diagnostic",
    "logs.ota",
    "logs.crash",
    "local.lcd_continuity",
    "local.sensors_continuity",
    "local.rs485_continuity",
)


class NodeMqttBoardLabError(RuntimeError):
    """Raised when a board-lab operation fails closed."""


class Runner(Protocol):
    def __call__(
        self,
        command: Sequence[str],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]: ...


class Waiter(Protocol):
    def __call__(self, host: str, port: int, timeout_s: float) -> None: ...


@dataclass(frozen=True, slots=True)
class BoardLabIdentity:
    lab_id: str
    container_name: str
    image: str
    bind_host: str
    port: int
    candidate_username: str
    candidate_client_id: str
    anonymous_client_id: str
    observer_username: str


def _run(
    command: Sequence[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=check,
        text=True,
        capture_output=True,
    )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise NodeMqttBoardLabError(message)


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _private_write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _private_json(path: Path, value: Mapping[str, Any]) -> None:
    _private_write(path, _canonical_json(value) + "\n")


def _validate_port(port: int) -> int:
    _require(1024 <= port <= 65535, "board-lab port must be between 1024 and 65535")
    return port


def _validate_bind_host(bind_host: str) -> str:
    try:
        address = ipaddress.ip_address(bind_host)
    except ValueError as error:
        raise NodeMqttBoardLabError("board-lab bind host must be a literal IP address") from error
    _require(not address.is_unspecified, "board-lab bind host cannot be an unspecified address")
    _require(not address.is_multicast, "board-lab bind host cannot be multicast")
    _require(not address.is_global, "board-lab bind host cannot be globally routable")
    _require(address.version == 4, "board-lab currently requires an IPv4 bind host")
    return str(address)


def _validate_workspace_for_create(workspace: Path) -> Path:
    resolved = workspace.expanduser().resolve()
    _require(resolved != Path("/"), "workspace cannot be filesystem root")
    _require(resolved != Path("/tmp"), "workspace cannot be /tmp itself")
    _require(len(resolved.parts) >= 3, "workspace path is too broad")
    if resolved.exists():
        _require(resolved.is_dir(), "workspace exists and is not a directory")
        _require(not any(resolved.iterdir()), "workspace must be empty")
    else:
        resolved.mkdir(parents=True, mode=0o700)
    resolved.chmod(0o700)
    return resolved


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise NodeMqttBoardLabError(f"invalid private board-lab file: {path.name}") from error
    _require(isinstance(value, dict), f"{path.name} root must be an object")
    return value


def _load_manifest(workspace: Path) -> tuple[Path, dict[str, Any]]:
    resolved = workspace.expanduser().resolve()
    marker = resolved / MARKER_NAME
    manifest_path = resolved / MANIFEST_NAME
    _require(resolved.is_dir(), "board-lab workspace does not exist")
    _require(marker.is_file(), "board-lab marker is missing")
    manifest = _load_json(manifest_path)
    _require(manifest.get("schema") == MANIFEST_SCHEMA, "board-lab manifest schema mismatch")
    lab_id = manifest.get("lab_id")
    _require(isinstance(lab_id, str) and len(lab_id) == 16, "board-lab ID is invalid")
    _require(marker.read_text(encoding="utf-8").strip() == lab_id, "board-lab marker mismatch")
    _require(
        manifest.get("workspace_fingerprint") == _fingerprint(str(resolved)),
        "workspace binding mismatch",
    )
    container_name = manifest.get("container_name")
    _require(
        isinstance(container_name, str) and container_name.startswith(CONTAINER_PREFIX),
        "container name is invalid",
    )
    bind_host = manifest.get("bind_host")
    _require(isinstance(bind_host, str), "board-lab bind host is invalid")
    _validate_bind_host(bind_host)
    port = manifest.get("port")
    _require(isinstance(port, int), "board-lab port is invalid")
    _validate_port(port)
    return resolved, manifest


def _load_secrets(workspace: Path) -> dict[str, Any]:
    document = _load_json(workspace / SECRETS_NAME)
    for key in ("candidate_password", "observer_password"):
        value = document.get(key)
        _require(isinstance(value, str) and len(value) >= 24, f"{key} is invalid")
    return document


def _identity_from_manifest(manifest: Mapping[str, Any]) -> BoardLabIdentity:
    return BoardLabIdentity(
        lab_id=str(manifest["lab_id"]),
        container_name=str(manifest["container_name"]),
        image=str(manifest["image"]),
        bind_host=str(manifest["bind_host"]),
        port=int(manifest["port"]),
        candidate_username=str(manifest["candidate_username"]),
        candidate_client_id=str(manifest["candidate_client_id"]),
        anonymous_client_id=str(manifest["anonymous_client_id"]),
        observer_username=str(manifest["observer_username"]),
    )
