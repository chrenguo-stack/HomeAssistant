from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

A1_CLASSIFICATION_SHA256 = "e664ced300ea2bb743b116550b7a3e22237e7f556f54400a060eef30671d30e7"
TARGET_SCHEMA_V2 = "gh.n3w-t1-core-updater-target/2"
TX_SCHEMA_V2 = "gh.n3w-t1-core-updater-transaction/2"
STATUS_SCHEMA_V2 = "gh.n3w-t1-core-updater-status/2"
INSPECT_SCHEMA_V2 = "gh.n3w-t1-core-updater-inspect/2"
PLAN_SCHEMA_V2 = "gh.n3w-t1-core-updater-plan/2"
BASELINE_SCHEMA_V1 = "gh.n3w-t1-core-updater-baseline/1"
APPLY_CONFIRMATION_V2 = "T1_CORE_UPDATER_APPLY"
ROLLBACK_CONFIRMATION_V2 = "T1_CORE_UPDATER_ROLLBACK"
MUTATION_PROFILE_IMAGE_ONLY = "IMAGE_ONLY_V1"
SUPPORTED_PLATFORM = "linux/arm64"

COMPONENTS = ("manager", "homeassistant", "broker")
IMAGE_BINDINGS = {
    "manager": "GH_MANAGER_IMAGE",
    "homeassistant": "GH_HOMEASSISTANT_IMAGE",
    "broker": "GH_BROKER_IMAGE",
}
IMAGE_PREFIXES = {
    "manager": "local/greenhouse-manager:",
    "homeassistant": "local/n3w-homeassistant:",
    "broker": "local/n3w-mosquitto:",
}

SHA256 = re.compile(r"^[0-9a-f]{64}$")
AUTHORIZATION_ID = re.compile(r"^N3W_T1_CORE_UPDATER_[A-Za-z0-9_-]{1,160}$")
TERMINAL_TX_V2 = frozenset({"COMMITTED", "ROLLED_BACK"})


class UpdaterV2Error(RuntimeError):
    pass


def safe_error_code(error: Exception) -> str:
    value = str(error)
    if (
        not value
        or len(value) > 200
        or any(character in value for character in ("/", "\\", "@"))
    ):
        return type(error).__name__
    return value


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise UpdaterV2Error("file_invalid")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _nonempty_string(value: Any, reason: str) -> str:
    if not isinstance(value, str) or not value:
        raise UpdaterV2Error(reason)
    return value


@dataclass(frozen=True)
class UpgradeBaseline:
    stack_images: dict[str, str]
    image_binding_modes: dict[str, str]
    platforms: dict[str, str]
    runtime_contract_sha256: dict[str, str]
    a1_hard_authority: dict[str, Any]
    a1_classification_sha256: str

    @classmethod
    def load(cls, path: Path) -> "UpgradeBaseline":
        if path.is_symlink() or not path.is_file():
            raise UpdaterV2Error("baseline_manifest_invalid")
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise UpdaterV2Error("baseline_manifest_invalid") from error
        if not isinstance(doc, dict) or doc.get("schema") != BASELINE_SCHEMA_V1:
            raise UpdaterV2Error("baseline_manifest_schema_invalid")
        if doc.get("a1_classification_sha256") != A1_CLASSIFICATION_SHA256:
            raise UpdaterV2Error("baseline_a1_authority_mismatch")
        images = doc.get("stack_images")
        modes = doc.get("image_binding_modes")
        platforms = doc.get("platforms")
        contracts = doc.get("runtime_contract_sha256")
        hard = doc.get("a1_hard_authority")
        if (
            not isinstance(images, dict)
            or set(images) != set(COMPONENTS)
            or not isinstance(modes, dict)
            or set(modes) != set(COMPONENTS)
            or not isinstance(platforms, dict)
            or set(platforms) != set(COMPONENTS)
            or not isinstance(contracts, dict)
            or set(contracts) != set(COMPONENTS)
            or not isinstance(hard, dict)
            or not hard
        ):
            raise UpdaterV2Error("baseline_manifest_shape_invalid")
        for component in COMPONENTS:
            image = images.get(component)
            mode = modes.get(component)
            platform = platforms.get(component)
            contract = contracts.get(component)
            if (
                not isinstance(image, str)
                or not image.startswith(IMAGE_PREFIXES[component])
                or mode not in {"dynamic", "legacy_static"}
                or platform != SUPPORTED_PLATFORM
                or not isinstance(contract, str)
                or SHA256.fullmatch(contract) is None
            ):
                raise UpdaterV2Error("baseline_component_authority_invalid")
        return cls(
            stack_images=copy.deepcopy(images),
            image_binding_modes=copy.deepcopy(modes),
            platforms=copy.deepcopy(platforms),
            runtime_contract_sha256=copy.deepcopy(contracts),
            a1_hard_authority=copy.deepcopy(hard),
            a1_classification_sha256=A1_CLASSIFICATION_SHA256,
        )

    def public(self) -> dict[str, Any]:
        return {
            "schema": BASELINE_SCHEMA_V1,
            "a1_classification_sha256": self.a1_classification_sha256,
            "stack_images": copy.deepcopy(self.stack_images),
            "image_binding_modes": copy.deepcopy(self.image_binding_modes),
            "platforms": copy.deepcopy(self.platforms),
            "runtime_contract_sha256": copy.deepcopy(
                self.runtime_contract_sha256
            ),
            "a1_hard_authority": copy.deepcopy(self.a1_hard_authority),
        }


@dataclass(frozen=True)
class ComponentTarget:
    component: str
    mutation_profile: str
    target_image_ref: str
    target_platform: str
    target_archive_sha256: str
    artifact_identity: dict[str, Any]
    expected_predecessor_image_ref: str
    rollback_compatible: bool
    compatibility_evidence: dict[str, Any]
    a1_classification_sha256: str

    @classmethod
    def load(cls, path: Path) -> "ComponentTarget":
        if path.is_symlink() or not path.is_file():
            raise UpdaterV2Error("target_manifest_invalid")
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise UpdaterV2Error("target_manifest_invalid") from error
        if not isinstance(doc, dict) or doc.get("schema") != TARGET_SCHEMA_V2:
            raise UpdaterV2Error("target_manifest_schema_invalid")

        component = doc.get("component")
        if component not in COMPONENTS:
            raise UpdaterV2Error("target_component_invalid")
        if doc.get("mutation_profile") != MUTATION_PROFILE_IMAGE_ONLY:
            raise UpdaterV2Error("target_mutation_profile_invalid")

        target_image = _nonempty_string(
            doc.get("target_image_ref"), "target_image_invalid"
        )
        predecessor = _nonempty_string(
            doc.get("expected_predecessor_image_ref"),
            "target_predecessor_image_invalid",
        )
        prefix = IMAGE_PREFIXES[component]
        if not target_image.startswith(prefix) or not predecessor.startswith(prefix):
            raise UpdaterV2Error("target_image_namespace_invalid")
        if target_image == predecessor:
            raise UpdaterV2Error("target_not_advanced")
        if doc.get("target_platform") != SUPPORTED_PLATFORM:
            raise UpdaterV2Error("target_platform_invalid")

        archive_sha = doc.get("target_archive_sha256")
        if not isinstance(archive_sha, str) or SHA256.fullmatch(archive_sha) is None:
            raise UpdaterV2Error("target_archive_sha256_invalid")

        artifact = doc.get("artifact_identity")
        if not isinstance(artifact, dict):
            raise UpdaterV2Error("target_artifact_identity_invalid")
        artifact_id = artifact.get("artifact_id")
        artifact_digest = artifact.get("artifact_digest_sha256")
        artifact_name = artifact.get("artifact_name")
        if (
            not isinstance(artifact_id, int)
            or isinstance(artifact_id, bool)
            or artifact_id <= 0
            or not isinstance(artifact_digest, str)
            or SHA256.fullmatch(artifact_digest) is None
            or not isinstance(artifact_name, str)
            or not artifact_name
        ):
            raise UpdaterV2Error("target_artifact_identity_invalid")

        compatibility = doc.get("compatibility_evidence")
        if (
            not isinstance(compatibility, dict)
            or compatibility.get("schema")
            != "gh.n3w-t1-core-updater-compatibility/1"
            or compatibility.get("mutation_profile")
            != MUTATION_PROFILE_IMAGE_ONLY
            or compatibility.get("peer_contracts_compatible") is not True
            or compatibility.get("persistent_schema_compatible") is not True
            or not isinstance(
                compatibility.get("review_evidence_sha256"), str
            )
            or SHA256.fullmatch(
                compatibility["review_evidence_sha256"]
            )
            is None
        ):
            raise UpdaterV2Error("target_compatibility_evidence_invalid")
        if doc.get("rollback_compatible") is not True:
            raise UpdaterV2Error("target_rollback_compatibility_not_proven")
        if doc.get("a1_classification_sha256") != A1_CLASSIFICATION_SHA256:
            raise UpdaterV2Error("target_a1_authority_mismatch")

        return cls(
            component=component,
            mutation_profile=MUTATION_PROFILE_IMAGE_ONLY,
            target_image_ref=target_image,
            target_platform=SUPPORTED_PLATFORM,
            target_archive_sha256=archive_sha,
            artifact_identity=copy.deepcopy(artifact),
            expected_predecessor_image_ref=predecessor,
            rollback_compatible=True,
            compatibility_evidence=copy.deepcopy(compatibility),
            a1_classification_sha256=A1_CLASSIFICATION_SHA256,
        )

    def public(self) -> dict[str, Any]:
        return {
            "schema": TARGET_SCHEMA_V2,
            "component": self.component,
            "mutation_profile": self.mutation_profile,
            "target_image_ref": self.target_image_ref,
            "target_platform": self.target_platform,
            "target_archive_sha256": self.target_archive_sha256,
            "artifact_identity": copy.deepcopy(self.artifact_identity),
            "expected_predecessor_image_ref": self.expected_predecessor_image_ref,
            "rollback_compatible": True,
            "compatibility_evidence": copy.deepcopy(self.compatibility_evidence),
            "a1_classification_sha256": self.a1_classification_sha256,
        }


def parse_image_bindings(payload: bytes) -> dict[str, str]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UpdaterV2Error("compose_env_encoding_invalid") from error
    values: dict[str, str] = {}
    for component, key in IMAGE_BINDINGS.items():
        matches = [
            line.split("=", 1)[1]
            for line in text.splitlines()
            if line.startswith(f"{key}=")
        ]
        if len(matches) != 1:
            raise UpdaterV2Error(f"{component}_image_env_line_count_invalid")
        value = matches[0]
        if not value.startswith(IMAGE_PREFIXES[component]):
            raise UpdaterV2Error(f"{component}_image_env_invalid")
        values[component] = value
    return values


def rewrite_component_env(
    payload: bytes,
    component: str,
    expected: str,
    replacement: str,
) -> bytes:
    if component not in COMPONENTS:
        raise UpdaterV2Error("component_invalid")
    prefix = IMAGE_PREFIXES[component]
    if not expected.startswith(prefix) or not replacement.startswith(prefix):
        raise UpdaterV2Error("component_image_namespace_invalid")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UpdaterV2Error("compose_env_encoding_invalid") from error
    key = IMAGE_BINDINGS[component]
    lines = text.splitlines(keepends=True)
    indexes = [i for i, line in enumerate(lines) if line.startswith(f"{key}=")]
    if len(indexes) != 1:
        raise UpdaterV2Error(f"{component}_image_env_line_count_invalid")
    index = indexes[0]
    raw = lines[index]
    ending = "\n" if raw.endswith("\n") else ""
    observed = raw.rstrip("\r\n").split("=", 1)[1]
    if observed != expected:
        raise UpdaterV2Error(f"{component}_image_env_predecessor_drift")
    lines[index] = f"{key}={replacement}{ending}"
    updated = "".join(lines).encode("utf-8")
    try:
        verify_text = updated.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UpdaterV2Error("compose_env_encoding_invalid") from error
    verified = [
        line.split("=", 1)[1]
        for line in verify_text.splitlines()
        if line.startswith(f"{key}=")
    ]
    if verified != [replacement]:
        raise UpdaterV2Error("compose_env_replace_verify_failed")
    return updated



HA_DYNAMIC_IMAGE_BINDING = '"\${GH_HOMEASSISTANT_IMAGE:?GH_HOMEASSISTANT_IMAGE required}"'
HA_DYNAMIC_IMAGE_VALUE = "\${GH_HOMEASSISTANT_IMAGE:?GH_HOMEASSISTANT_IMAGE required}"


def _unquote_yaml_scalar(value: str) -> str:
    value = value.strip()
    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in {'"', "'"}
    ):
        return value[1:-1]
    return value


def _homeassistant_image_line(
    payload: bytes,
) -> tuple[list[str], int, str, str]:
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UpdaterV2Error("compose_encoding_invalid") from error
    lines = text.splitlines(keepends=True)
    service_starts = [
        index
        for index, line in enumerate(lines)
        if re.fullmatch(r"  [A-Za-z0-9_.-]+:\s*(?:#.*)?\r?\n?", line)
    ]
    ha_starts = [
        index
        for index in service_starts
        if re.match(r"^  homeassistant:", lines[index])
    ]
    if len(ha_starts) != 1:
        raise UpdaterV2Error("homeassistant_service_block_invalid")
    start = ha_starts[0]
    end = len(lines)
    for index in service_starts:
        if index > start:
            end = index
            break
    for index in range(start + 1, len(lines)):
        if re.match(r"^[A-Za-z0-9_.-]+:\s*(?:#.*)?\r?\n?$", lines[index]):
            end = min(end, index)
            break
    image_indexes = [
        index
        for index in range(start + 1, end)
        if re.match(r"^    image:\s*", lines[index])
    ]
    if len(image_indexes) != 1:
        raise UpdaterV2Error("homeassistant_image_line_count_invalid")
    index = image_indexes[0]
    raw = lines[index]
    ending = "\r\n" if raw.endswith("\r\n") else ("\n" if raw.endswith("\n") else "")
    observed = _unquote_yaml_scalar(raw.split(":", 1)[1].rstrip("\r\n"))
    return lines, index, ending, observed


def converge_homeassistant_compose(
    payload: bytes,
    expected_predecessor: str,
) -> bytes:
    if not expected_predecessor.startswith(IMAGE_PREFIXES["homeassistant"]):
        raise UpdaterV2Error("component_image_namespace_invalid")
    lines, index, ending, observed = _homeassistant_image_line(payload)
    if observed != expected_predecessor:
        raise UpdaterV2Error("homeassistant_compose_predecessor_drift")
    lines[index] = f"    image: {HA_DYNAMIC_IMAGE_BINDING}{ending}"
    return "".join(lines).encode("utf-8")


def converge_homeassistant_env(
    payload: bytes,
    expected_predecessor: str,
    replacement: str,
) -> bytes:
    prefix = IMAGE_PREFIXES["homeassistant"]
    if not expected_predecessor.startswith(prefix) or not replacement.startswith(prefix):
        raise UpdaterV2Error("component_image_namespace_invalid")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UpdaterV2Error("compose_env_encoding_invalid") from error
    key = IMAGE_BINDINGS["homeassistant"]
    lines = text.splitlines(keepends=True)
    indexes = [
        index for index, line in enumerate(lines) if line.startswith(f"{key}=")
    ]
    if len(indexes) > 1:
        raise UpdaterV2Error("homeassistant_image_env_line_count_invalid")
    if not indexes:
        ending = "" if not text or text.endswith(("\n", "\r")) else "\n"
        updated = (
            payload
            + ending.encode("utf-8")
            + f"{key}={replacement}\n".encode("utf-8")
        )
    else:
        index = indexes[0]
        raw = lines[index]
        observed = raw.rstrip("\r\n").split("=", 1)[1]
        if observed not in {expected_predecessor, replacement}:
            raise UpdaterV2Error("homeassistant_image_env_predecessor_drift")
        if observed == replacement:
            updated = payload
        else:
            line_ending = (
                "\r\n"
                if raw.endswith("\r\n")
                else ("\n" if raw.endswith("\n") else "")
            )
            lines[index] = f"{key}={replacement}{line_ending}"
            updated = "".join(lines).encode("utf-8")
    try:
        verify_text = updated.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UpdaterV2Error("compose_env_encoding_invalid") from error
    verified = [
        line.split("=", 1)[1]
        for line in verify_text.splitlines()
        if line.startswith(f"{key}=")
    ]
    if verified != [replacement]:
        raise UpdaterV2Error("compose_env_replace_verify_failed")
    return updated


def restore_homeassistant_compose(
    payload: bytes,
    predecessor: str,
) -> bytes:
    if not predecessor.startswith(IMAGE_PREFIXES["homeassistant"]):
        raise UpdaterV2Error("component_image_namespace_invalid")
    lines, index, ending, observed = _homeassistant_image_line(payload)
    if observed == predecessor:
        return payload
    if observed != HA_DYNAMIC_IMAGE_VALUE:
        raise UpdaterV2Error("homeassistant_compose_binding_unknown")
    lines[index] = f"    image: {predecessor}{ending}"
    return "".join(lines).encode("utf-8")


def restore_homeassistant_env(
    payload: bytes,
    predecessor: str,
    target: str,
) -> bytes:
    prefix = IMAGE_PREFIXES["homeassistant"]
    if not predecessor.startswith(prefix) or not target.startswith(prefix):
        raise UpdaterV2Error("component_image_namespace_invalid")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise UpdaterV2Error("compose_env_encoding_invalid") from error
    key = IMAGE_BINDINGS["homeassistant"]
    lines = text.splitlines(keepends=True)
    indexes = [
        index for index, line in enumerate(lines) if line.startswith(f"{key}=")
    ]
    if len(indexes) > 1:
        raise UpdaterV2Error("homeassistant_image_env_line_count_invalid")
    if not indexes:
        return payload
    index = indexes[0]
    observed = lines[index].rstrip("\r\n").split("=", 1)[1]
    if observed not in {predecessor, target}:
        raise UpdaterV2Error("homeassistant_image_env_rollback_drift")
    del lines[index]
    updated = "".join(lines).encode("utf-8")
    if any(
        line.startswith(f"{key}=")
        for line in updated.decode("utf-8").splitlines()
    ):
        raise UpdaterV2Error("homeassistant_image_env_remove_verify_failed")
    return updated


def validate_component_candidate(
    before: dict[str, Any],
    after: dict[str, Any],
    component: str,
    old: str,
    new: str,
) -> None:
    if component not in COMPONENTS:
        raise UpdaterV2Error("component_invalid")
    expected = copy.deepcopy(before)
    services = expected.get("services")
    service = services.get(component) if isinstance(services, dict) else None
    if not isinstance(service, dict) or service.get("image") != old:
        raise UpdaterV2Error("candidate_predecessor_invalid")
    service["image"] = new
    if expected != after:
        raise UpdaterV2Error("candidate_non_target_drift")


class V2Host(Protocol):
    def observe_v2(self) -> dict[str, Any]: ...
    def observe_state_v2(self) -> dict[str, Any]: ...
    def inspect_v2(self) -> dict[str, Any]: ...
    def wait_services(self, timeout: int = 120) -> None: ...
    def assert_mutation_safe(self, component: str) -> None: ...
    def assert_component_upgradeable(self, component: str) -> None: ...
    def release_component_guard(self) -> None: ...
    def component_binding_v2(self, component: str) -> str: ...
    def image_id(self, reference: str) -> str | None: ...
    def verify_image_archive(
        self, reference: str, tar_path: Path, expected_sha256: str
    ) -> str: ...
    def load_image(self, tar_path: Path) -> None: ...
    def rewrite_component_image(
        self, component: str, expected: str, replacement: str
    ) -> str: ...
    def restore_component_binding(
        self,
        component: str,
        expected_current: str,
        predecessor: str,
        predecessor_mode: str,
    ) -> None: ...
    def render_compose(self) -> dict[str, Any]: ...
    def quiesce_component(self, component: str) -> None: ...
    def activate_component(self, component: str) -> None: ...
