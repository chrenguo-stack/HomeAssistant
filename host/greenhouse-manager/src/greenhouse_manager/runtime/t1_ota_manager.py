from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

APPROVED_MANIFEST_SCHEMA = "gh.n3w-t1-ota-approved-manifest/1"
TARGET_MANIFEST_SCHEMA = "gh.n3w-t1-core-updater-target/2"
HOMEASSISTANT_COMPONENT = "homeassistant"
HOMEASSISTANT_PLATFORM = "linux/arm64"

_VERSION_RE = re.compile(r"^[0-9]{4}\.[0-9]{1,2}\.[0-9]{1,3}$")
_RELEASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_RE = re.compile(
    r"^local/n3w-homeassistant:(?P<version>[0-9]{4}\.[0-9]{1,2}\.[0-9]{1,3})-"
    r"(?P<revision>[0-9a-f]{8,64})$"
)

_IDLE_PHASES = {
    "DISCOVERED",
    "USB_REQUIRED",
    "USB_REQUIRED_CONFIRMATION",
    "RECOVERY_MEDIA_REQUIRED",
    "READY_TO_INSTALL",
    "COMMITTED",
    "ROLLED_BACK",
    "ERROR",
}
_IN_PROGRESS_PHASES = {
    "PREPARE_REQUESTED",
    "USB_QUALIFIED_FORMATTED_BOUND",
    "TARGET_DOWNLOADING_VERIFYING",
    "INSTALL_REQUESTED_REVALIDATING",
    "PREDECESSOR_RECOVERY_PREPARING",
    "HA_QUIESCED_DATA_BACKUP_PREPARING",
    "RECOVERY_ADMISSION_COMPLETE",
    "LIVE_AUTHORIZATION_CLAIMED",
    "INTERNAL_PREDECESSOR_CAPACITY_RELEASED",
    "TARGET_INSTALLED_STARTED",
    "TARGET_ACCEPTANCE",
}
_ALLOWED_PHASES = _IDLE_PHASES | _IN_PROGRESS_PHASES


class ApprovedManifestProvider(Protocol):
    def get_approved_homeassistant_manifest(self) -> Mapping[str, Any] | None:
        """Return one provider-verified approved manifest envelope, or None."""


class OtaIntentSink(Protocol):
    def submit_homeassistant_ota_intent(self, intent: OtaControlIntent) -> None:
        """Submit a validated, non-privileged intent to the next bounded layer."""


class OtaRuntimeStateProvider(Protocol):
    def get_homeassistant_ota_runtime_state(self) -> OtaRuntimeSnapshot:
        """Return the current public OTA transaction projection."""


class OtaControlError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class ApprovedManifest:
    manifest_schema_supported: bool
    approval_status: str
    component: str
    version: str
    platform: str
    target_archive_size_bytes: int
    target_archive_sha256: str
    target_image_identity: str
    release_identity: str
    verification_status: str


@dataclass(frozen=True, slots=True)
class OtaRuntimeSnapshot:
    phase: str = "DISCOVERED"
    progress_percent: int | None = None
    error_code: str | None = None
    installed_version: str | None = None
    usb_candidate_model: str | None = None
    usb_candidate_capacity_bytes: int | None = None
    usb_confirmation_required: bool = False

    def validate(self) -> OtaRuntimeSnapshot:
        if self.phase not in _ALLOWED_PHASES:
            raise OtaControlError("ota_runtime_phase_invalid")
        if self.progress_percent is not None and (
            type(self.progress_percent) is not int
            or not 0 <= self.progress_percent <= 100
        ):
            raise OtaControlError("ota_runtime_progress_invalid")
        if self.error_code is not None:
            _require_public_error_code(self.error_code)
        if self.installed_version is not None:
            _stable_version(
                self.installed_version,
                code="ota_runtime_installed_version_invalid",
            )
        if self.usb_candidate_model is not None and (
            not isinstance(self.usb_candidate_model, str)
            or not self.usb_candidate_model.strip()
            or len(self.usb_candidate_model) > 160
            or any(
                character in self.usb_candidate_model
                for character in ("\x00", "\n", "\r")
            )
        ):
            raise OtaControlError("ota_runtime_usb_candidate_invalid")
        if self.usb_candidate_capacity_bytes is not None and (
            type(self.usb_candidate_capacity_bytes) is not int
            or self.usb_candidate_capacity_bytes <= 0
        ):
            raise OtaControlError("ota_runtime_usb_candidate_invalid")
        if type(self.usb_confirmation_required) is not bool:
            raise OtaControlError("ota_runtime_usb_confirmation_invalid")
        if self.usb_confirmation_required and (
            self.phase != "USB_REQUIRED_CONFIRMATION"
            or self.usb_candidate_model is None
            or self.usb_candidate_capacity_bytes is None
        ):
            raise OtaControlError("ota_runtime_usb_confirmation_invalid")
        return self


@dataclass(frozen=True, slots=True)
class OtaStatus:
    installed_version: str
    latest_approved_version: str
    update_available: bool
    ota_phase: str
    progress_percent_or_null: int | None
    ready_to_install: bool
    in_progress: bool
    error_code_or_null: str | None
    usb_candidate_model_or_null: str | None = None
    usb_candidate_capacity_bytes_or_null: int | None = None
    usb_confirmation_required: bool = False


@dataclass(frozen=True, slots=True)
class OtaProjection:
    manifest: ApprovedManifest | None
    status: OtaStatus


@dataclass(frozen=True, slots=True)
class OtaControlIntent:
    action: str
    target_release_id: str


def _require_public_error_code(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9_]{3,96}", value):
        raise OtaControlError("ota_error_code_invalid")
    return value


def _require_exact_keys(
    value: Mapping[str, Any],
    expected: set[str],
    *,
    code: str,
) -> None:
    if set(value) != expected:
        raise OtaControlError(code)


def _mapping(value: object, *, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise OtaControlError(code)
    if not all(isinstance(key, str) for key in value):
        raise OtaControlError(code)
    return value


def _sha256(value: object, *, code: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise OtaControlError(code)
    return value


def _git_sha(value: object, *, code: str) -> str:
    if not isinstance(value, str) or _GIT_SHA_RE.fullmatch(value) is None:
        raise OtaControlError(code)
    return value


def _stable_version(value: object, *, code: str = "approved_manifest_version_invalid") -> str:
    if not isinstance(value, str) or _VERSION_RE.fullmatch(value) is None:
        raise OtaControlError(code)
    return value


def _release_identity(value: object, *, code: str = "approved_manifest_release_invalid") -> str:
    if not isinstance(value, str) or _RELEASE_ID_RE.fullmatch(value) is None:
        raise OtaControlError(code)
    return value


def compare_versions(left: str, right: str) -> int:
    left_parts = tuple(int(part) for part in _stable_version(left).split("."))
    right_parts = tuple(int(part) for part in _stable_version(right).split("."))
    return (left_parts > right_parts) - (left_parts < right_parts)


def normalize_approved_manifest(document: Mapping[str, Any]) -> ApprovedManifest:
    envelope = _mapping(document, code="approved_manifest_invalid")
    _require_exact_keys(
        envelope,
        {
            "schema",
            "approval_status",
            "signature_status",
            "validity_status",
            "verification_status",
            "version",
            "release_identity",
            "target_archive_size_bytes",
            "target",
        },
        code="approved_manifest_fields_invalid",
    )
    if envelope["schema"] != APPROVED_MANIFEST_SCHEMA:
        raise OtaControlError("approved_manifest_schema_unsupported")
    if envelope["approval_status"] != "APPROVED":
        raise OtaControlError("approved_manifest_not_approved")
    if envelope["signature_status"] != "VERIFIED":
        raise OtaControlError("approved_manifest_signature_unverified")
    if envelope["validity_status"] != "VALID":
        raise OtaControlError("approved_manifest_expired_or_invalid")
    if envelope["verification_status"] != "PASS":
        raise OtaControlError("approved_manifest_verification_failed")

    version = _stable_version(envelope["version"])
    release_identity = _release_identity(envelope["release_identity"])
    size = envelope["target_archive_size_bytes"]
    if type(size) is not int or size <= 0 or size > 8 * 1024 * 1024 * 1024:
        raise OtaControlError("approved_manifest_archive_size_invalid")

    target = _mapping(envelope["target"], code="approved_manifest_target_invalid")
    _require_exact_keys(
        target,
        {
            "schema",
            "component",
            "mutation_profile",
            "target_image_ref",
            "target_platform",
            "target_archive_sha256",
            "artifact_identity",
            "expected_predecessor_image_ref",
            "rollback_compatible",
            "compatibility_evidence",
            "a1_classification_sha256",
        },
        code="approved_manifest_target_fields_invalid",
    )
    if target["schema"] != TARGET_MANIFEST_SCHEMA:
        raise OtaControlError("approved_manifest_target_schema_unsupported")
    if target["component"] != HOMEASSISTANT_COMPONENT:
        raise OtaControlError("approved_manifest_component_invalid")
    if target["mutation_profile"] != "IMAGE_ONLY_V1":
        raise OtaControlError("approved_manifest_mutation_profile_invalid")
    if target["target_platform"] != HOMEASSISTANT_PLATFORM:
        raise OtaControlError("approved_manifest_platform_invalid")
    if target["rollback_compatible"] is not True:
        raise OtaControlError("approved_manifest_rollback_contract_invalid")

    image_ref = target["target_image_ref"]
    if not isinstance(image_ref, str):
        raise OtaControlError("approved_manifest_target_image_invalid")
    image_match = _IMAGE_RE.fullmatch(image_ref)
    if image_match is None or image_match.group("version") != version:
        raise OtaControlError("approved_manifest_target_image_invalid")

    target_sha = _sha256(
        target["target_archive_sha256"],
        code="approved_manifest_target_sha256_invalid",
    )
    _sha256(
        target["a1_classification_sha256"],
        code="approved_manifest_classification_sha256_invalid",
    )

    artifact = _mapping(
        target["artifact_identity"],
        code="approved_manifest_artifact_identity_invalid",
    )
    _require_exact_keys(
        artifact,
        {"artifact_id", "artifact_digest_sha256", "artifact_name"},
        code="approved_manifest_artifact_fields_invalid",
    )
    if type(artifact["artifact_id"]) is not int or artifact["artifact_id"] <= 0:
        raise OtaControlError("approved_manifest_artifact_id_invalid")
    _sha256(
        artifact["artifact_digest_sha256"],
        code="approved_manifest_artifact_digest_invalid",
    )
    if not isinstance(artifact["artifact_name"], str) or not artifact["artifact_name"]:
        raise OtaControlError("approved_manifest_artifact_name_invalid")

    predecessor = target["expected_predecessor_image_ref"]
    if not isinstance(predecessor, str) or _IMAGE_RE.fullmatch(predecessor) is None:
        raise OtaControlError("approved_manifest_predecessor_invalid")

    compatibility = _mapping(
        target["compatibility_evidence"],
        code="approved_manifest_compatibility_invalid",
    )
    _require_exact_keys(
        compatibility,
        {
            "schema",
            "mutation_profile",
            "peer_contracts_compatible",
            "persistent_schema_compatible",
            "review_evidence_sha256",
            "predecessor_source_head",
            "target_source_head",
        },
        code="approved_manifest_compatibility_fields_invalid",
    )
    if compatibility["schema"] != "gh.n3w-t1-core-updater-compatibility/1":
        raise OtaControlError("approved_manifest_compatibility_schema_invalid")
    if compatibility["mutation_profile"] != "IMAGE_ONLY_V1":
        raise OtaControlError("approved_manifest_compatibility_profile_invalid")
    if compatibility["peer_contracts_compatible"] is not True:
        raise OtaControlError("approved_manifest_peer_contract_invalid")
    if compatibility["persistent_schema_compatible"] is not True:
        raise OtaControlError("approved_manifest_persistent_schema_invalid")
    _sha256(
        compatibility["review_evidence_sha256"],
        code="approved_manifest_review_evidence_invalid",
    )
    for key in ("predecessor_source_head", "target_source_head"):
        _git_sha(
            compatibility[key],
            code="approved_manifest_source_identity_invalid",
        )

    return ApprovedManifest(
        manifest_schema_supported=True,
        approval_status="APPROVED",
        component=HOMEASSISTANT_COMPONENT,
        version=version,
        platform=HOMEASSISTANT_PLATFORM,
        target_archive_size_bytes=size,
        target_archive_sha256=target_sha,
        target_image_identity=image_ref,
        release_identity=release_identity,
        verification_status="PASS",
    )


def _no_duplicate_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise OtaControlError("ota_intent_duplicate_field")
        result[key] = value
    return result


def parse_control_intent(
    payload: bytes | bytearray | memoryview | str,
    *,
    expected_release_identity: str,
) -> OtaControlIntent:
    if isinstance(payload, str):
        payload_bytes = payload.encode("utf-8")
    else:
        try:
            payload_bytes = bytes(payload)
        except (TypeError, ValueError) as error:
            raise OtaControlError("ota_intent_payload_invalid") from error
    if not payload_bytes or len(payload_bytes) > 4096:
        raise OtaControlError("ota_intent_payload_invalid")
    try:
        raw = payload_bytes.decode("utf-8")
        document = json.loads(raw, object_pairs_hook=_no_duplicate_object)
    except OtaControlError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OtaControlError("ota_intent_payload_invalid") from error
    if not isinstance(document, dict):
        raise OtaControlError("ota_intent_payload_invalid")
    _require_exact_keys(
        document,
        {"action", "target_release_id"},
        code="ota_intent_fields_invalid",
    )
    action = document["action"]
    if action not in {"PREPARE", "INSTALL", "STATUS"}:
        raise OtaControlError("ota_intent_action_invalid")
    release = _release_identity(
        document["target_release_id"],
        code="ota_intent_release_invalid",
    )
    if release != expected_release_identity:
        raise OtaControlError("ota_intent_release_mismatch")
    return OtaControlIntent(action=action, target_release_id=release)


class T1OtaManager:
    def __init__(
        self,
        *,
        installed_version: str,
        manifest_provider: ApprovedManifestProvider,
        intent_sink: OtaIntentSink | None = None,
        runtime_state_provider: OtaRuntimeStateProvider | None = None,
    ) -> None:
        self.installed_version = _stable_version(
            installed_version,
            code="installed_version_invalid",
        )
        self.manifest_provider = manifest_provider
        self.intent_sink = intent_sink
        self.runtime_state_provider = runtime_state_provider

    def _manifest(self) -> ApprovedManifest:
        try:
            document = self.manifest_provider.get_approved_homeassistant_manifest()
        except OtaControlError:
            raise
        except Exception as error:
            raise OtaControlError("approved_manifest_provider_failed") from error
        if document is None:
            raise OtaControlError("approved_manifest_unavailable")
        return normalize_approved_manifest(document)

    def _runtime(self) -> OtaRuntimeSnapshot:
        if self.runtime_state_provider is None:
            return OtaRuntimeSnapshot()
        try:
            snapshot = self.runtime_state_provider.get_homeassistant_ota_runtime_state()
        except OtaControlError:
            raise
        except Exception as error:
            raise OtaControlError("ota_runtime_state_provider_failed") from error
        if not isinstance(snapshot, OtaRuntimeSnapshot):
            raise OtaControlError("ota_runtime_state_invalid")
        return snapshot.validate()

    def _status(
        self,
        *,
        manifest: ApprovedManifest,
        runtime: OtaRuntimeSnapshot,
    ) -> OtaStatus:
        installed_version = runtime.installed_version or self.installed_version
        available = compare_versions(manifest.version, installed_version) > 0
        return OtaStatus(
            installed_version=installed_version,
            latest_approved_version=manifest.version,
            update_available=available,
            ota_phase=runtime.phase,
            progress_percent_or_null=runtime.progress_percent,
            ready_to_install=runtime.phase == "READY_TO_INSTALL",
            in_progress=runtime.phase in _IN_PROGRESS_PHASES,
            error_code_or_null=runtime.error_code,
            usb_candidate_model_or_null=runtime.usb_candidate_model,
            usb_candidate_capacity_bytes_or_null=(
                runtime.usb_candidate_capacity_bytes
            ),
            usb_confirmation_required=runtime.usb_confirmation_required,
        )

    def project(self) -> OtaProjection:
        try:
            manifest = self._manifest()
            runtime = self._runtime()
            return OtaProjection(
                manifest=manifest,
                status=self._status(manifest=manifest, runtime=runtime),
            )
        except OtaControlError as error:
            return OtaProjection(
                manifest=None,
                status=OtaStatus(
                    installed_version=self.installed_version,
                    latest_approved_version=self.installed_version,
                    update_available=False,
                    ota_phase="ERROR",
                    progress_percent_or_null=None,
                    ready_to_install=False,
                    in_progress=False,
                    error_code_or_null=error.code,
                    usb_candidate_model_or_null=None,
                    usb_candidate_capacity_bytes_or_null=None,
                    usb_confirmation_required=False,
                ),
            )

    def handle_control(
        self,
        payload: bytes | bytearray | memoryview | str,
    ) -> OtaControlIntent:
        manifest = self._manifest()
        runtime = self._runtime()
        status = self._status(manifest=manifest, runtime=runtime)
        intent = parse_control_intent(
            payload,
            expected_release_identity=manifest.release_identity,
        )

        if intent.action == "STATUS":
            return intent
        if not status.update_available:
            raise OtaControlError("ota_update_not_available")
        if intent.action == "CONFIRM_USB_ERASE":
            if (
                status.ota_phase != "USB_REQUIRED_CONFIRMATION"
                or status.usb_confirmation_required is not True
            ):
                raise OtaControlError("ota_usb_confirmation_not_ready")
        else:
            if status.in_progress:
                raise OtaControlError("ota_transaction_in_progress")
            if intent.action == "PREPARE":
                if status.ready_to_install:
                    raise OtaControlError("ota_already_ready_to_install")
                if status.ota_phase in {
                    "USB_REQUIRED",
                    "USB_REQUIRED_CONFIRMATION",
                    "RECOVERY_MEDIA_REQUIRED",
                }:
                    raise OtaControlError("ota_prepare_already_requested")
            elif not status.ready_to_install:
                raise OtaControlError("ota_install_not_ready")

        if self.intent_sink is None:
            raise OtaControlError("ota_intent_sink_unavailable")
        try:
            self.intent_sink.submit_homeassistant_ota_intent(intent)
        except Exception as error:
            raise OtaControlError("ota_intent_sink_failed") from error
        return intent
