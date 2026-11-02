from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

PROJECT = "n3wfc4"
BROKER_UNIT = "n3wfc4-broker-activation.service"
SERVICES_UNIT = "n3wfc4-services-activation.service"
REGISTRATION_GUARD_UNIT = "n3wfc4-registration-ingress-guard.service"
BROKER_ENV = Path("/etc/n3wfc4/broker-activation.env")
COMPOSE = Path("/etc/n3wfc4/docker-compose.yml")
COMPOSE_ENV = Path("/etc/n3wfc4/docker-compose.env")
STATE_ROOT = Path("/var/lib/n3w-t1-core-updater")

INSPECT_SCHEMA = "gh.n3w-t1-core-updater-inspect/1"
PLAN_SCHEMA = "gh.n3w-t1-core-updater-plan/1"
TX_SCHEMA = "gh.n3w-t1-core-updater-transaction/1"
STATUS_SCHEMA = "gh.n3w-t1-core-updater-status/1"
TARGET_SCHEMA = "gh.n3w-t1-core-updater-manager-target/1"
APPLY_CONFIRMATION = "T1_CORE_UPDATER_MANAGER_APPLY"
ROLLBACK_CONFIRMATION = "T1_CORE_UPDATER_MANAGER_ROLLBACK"

EXPECTED_EXECSTART = (
    "ExecStart=/usr/bin/docker compose "
    "--project-name ${N3WFC4_COMPOSE_PROJECT_NAME} "
    "--env-file ${N3WFC4_COMPOSE_ENV_FILE} "
    "-f ${N3WFC4_COMPOSE_FILE} --profile application up --no-deps "
    "--no-log-prefix --abort-on-container-exit manager homeassistant"
)
EXPECTED_EXECSTOP = (
    "ExecStop=/usr/bin/docker compose "
    "--project-name ${N3WFC4_COMPOSE_PROJECT_NAME} "
    "--env-file ${N3WFC4_COMPOSE_ENV_FILE} "
    "-f ${N3WFC4_COMPOSE_FILE} stop homeassistant manager"
)

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
MANAGER_IMAGE = re.compile(r"^local/greenhouse-manager:fresh-[0-9a-f]{12}$")
AUTHORIZATION_ID = re.compile(r"^N3W_T1_CORE_UPDATER_MANAGER_[A-Za-z0-9_-]{1,120}$")
TERMINAL_TX = frozenset({"COMMITTED", "ROLLED_BACK"})


class UpdaterError(RuntimeError):
    pass


@dataclass(frozen=True)
class Target:
    source_head: str
    image: str
    image_id: str
    tar_sha256: str
    artifact_id: int
    artifact_digest_sha256: str
    artifact_name: str
    rollback_compatible: bool
    expected_predecessor_image: str | None

    @classmethod
    def load(cls, path: Path) -> "Target":
        if path.is_symlink() or not path.is_file():
            raise UpdaterError("target_manifest_invalid")
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise UpdaterError("target_manifest_invalid") from error
        if not isinstance(doc, dict) or doc.get("schema") != TARGET_SCHEMA:
            raise UpdaterError("target_manifest_schema_invalid")
        if doc.get("component") != "manager":
            raise UpdaterError("target_component_invalid")
        source_head = doc.get("source_head")
        image = doc.get("image")
        image_id = doc.get("image_id")
        tar_sha256 = doc.get("tar_sha256")
        artifact_id = doc.get("artifact_id")
        artifact_digest = doc.get("artifact_digest_sha256")
        artifact_name = doc.get("artifact_name")
        rollback_compatible = doc.get("rollback_compatible")
        predecessor = doc.get("expected_predecessor_image")
        if not isinstance(source_head, str) or SHA40.fullmatch(source_head) is None:
            raise UpdaterError("target_source_head_invalid")
        if not isinstance(image, str) or MANAGER_IMAGE.fullmatch(image) is None:
            raise UpdaterError("target_image_invalid")
        if not isinstance(image_id, str) or IMAGE_ID.fullmatch(image_id) is None:
            raise UpdaterError("target_image_id_invalid")
        if not isinstance(tar_sha256, str) or SHA256.fullmatch(tar_sha256) is None:
            raise UpdaterError("target_tar_sha256_invalid")
        if not isinstance(artifact_id, int) or isinstance(artifact_id, bool) or artifact_id <= 0:
            raise UpdaterError("target_artifact_id_invalid")
        if not isinstance(artifact_digest, str) or SHA256.fullmatch(artifact_digest) is None:
            raise UpdaterError("target_artifact_digest_invalid")
        if not isinstance(artifact_name, str) or not artifact_name:
            raise UpdaterError("target_artifact_name_invalid")
        if rollback_compatible is not True:
            raise UpdaterError("target_rollback_compatibility_not_proven")
        if predecessor is not None and (
            not isinstance(predecessor, str)
            or MANAGER_IMAGE.fullmatch(predecessor) is None
        ):
            raise UpdaterError("target_predecessor_image_invalid")
        return cls(
            source_head=source_head,
            image=image,
            image_id=image_id,
            tar_sha256=tar_sha256,
            artifact_id=artifact_id,
            artifact_digest_sha256=artifact_digest,
            artifact_name=artifact_name,
            rollback_compatible=True,
            expected_predecessor_image=predecessor,
        )

    def public(self) -> dict[str, Any]:
        return {
            "source_head": self.source_head,
            "image": self.image,
            "image_id": self.image_id,
            "tar_sha256": self.tar_sha256,
            "artifact_id": self.artifact_id,
            "artifact_digest_sha256": self.artifact_digest_sha256,
            "artifact_name": self.artifact_name,
            "rollback_compatible": self.rollback_compatible,
            "expected_predecessor_image": self.expected_predecessor_image,
        }


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise UpdaterError("file_invalid")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def rewrite_manager_env(payload: bytes, expected: str, replacement: str) -> bytes:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UpdaterError("compose_env_encoding_invalid") from error
    lines = text.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if line.startswith("GH_MANAGER_IMAGE=")]
    if len(matches) != 1:
        raise UpdaterError("manager_image_env_line_count_invalid")
    index = matches[0]
    raw = lines[index]
    ending = "\n" if raw.endswith("\n") else ""
    value = raw.rstrip("\r\n").split("=", 1)[1]
    if value != expected:
        raise UpdaterError("manager_image_env_predecessor_drift")
    lines[index] = f"GH_MANAGER_IMAGE={replacement}{ending}"
    return "".join(lines).encode("utf-8")


def manager_env_image(payload: bytes) -> str:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UpdaterError("compose_env_encoding_invalid") from error
    values = [
        line.split("=", 1)[1]
        for line in text.splitlines()
        if line.startswith("GH_MANAGER_IMAGE=")
    ]
    if len(values) != 1 or MANAGER_IMAGE.fullmatch(values[0]) is None:
        raise UpdaterError("manager_image_env_invalid")
    return values[0]


def validate_candidate(
    before: dict[str, Any],
    after: dict[str, Any],
    old: str,
    new: str,
) -> None:
    expected = copy.deepcopy(before)
    services = expected.get("services")
    manager = services.get("manager") if isinstance(services, dict) else None
    if not isinstance(manager, dict) or manager.get("image") != old:
        raise UpdaterError("candidate_predecessor_invalid")
    manager["image"] = new
    if expected != after:
        raise UpdaterError("candidate_non_manager_drift")


class Host(Protocol):
    def inspect(self) -> dict[str, Any]: ...
    def image_id(self, reference: str) -> str | None: ...
    def load_image(self, tar_path: Path) -> None: ...
    def stop_services(self) -> None: ...
    def start_services(self) -> None: ...
    def manager_binding(self) -> str: ...
    def rewrite_manager_image(self, expected: str, replacement: str) -> str: ...
    def render_compose(self) -> dict[str, Any]: ...
    def broker_continuity(self, baseline: dict[str, Any]) -> None: ...
