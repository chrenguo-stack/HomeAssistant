from __future__ import annotations

import json
import os
import re
import signal
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from n3w_t1_core_updater_ha_ipc import (
    HaUsbIpcDispatcher,
    HaUsbIpcExecutor,
    HostOtaAdmission,
    UnixSocketHaOtaServer,
)
from n3w_t1_core_updater_ha_prepare import (
    HaUsbPrepareController,
    PrepareStateStore,
)
from n3w_t1_core_updater_ha_prepare_host import (
    SubprocessPrepareBackend,
)
from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore
from n3w_t1_core_updater_v2_common import (
    A1_CLASSIFICATION_SHA256,
    SHA256,
    UpdaterV2Error,
    canonical,
    sha256_bytes,
)

APPROVED_MANIFEST_SCHEMA = "gh.n3w-t1-ota-approved-manifest/1"
TARGET_SCHEMA = "gh.n3w-t1-core-updater-target/2"
APPROVED_MANIFEST_SOURCE = Path(
    "/etc/n3w-t1-ota/approved-homeassistant.json"
)
RUNTIME_ROOT = Path("/run/n3w-t1-ota")
RUNTIME_MANIFEST = RUNTIME_ROOT / "approved-homeassistant.json"
SOCKET_PATH = RUNTIME_ROOT / "ha-ota.sock"
STATE_ROOT = Path("/var/lib/n3w-t1-core-updater")
EXPECTED_MANAGER_UID = 999
EXPECTED_MANAGER_GID = 999
MAX_MANIFEST_BYTES = 64 * 1024
HOMEASSISTANT_CONTAINER = "n3wfc4-homeassistant-1"
_HA_IMAGE_RE = re.compile(r"^local/n3w-homeassistant:(?P<version>[0-9]{4}\\.[0-9]{1,2}\\.[0-9]{1,3})-[0-9a-f]{8,64}$")
_VERSION_RE = re.compile(r"^[0-9]{4}\\.[0-9]{1,2}\\.[0-9]{1,3}$")
_RELEASE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _reject_duplicate_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise UpdaterV2Error("ha_ota_approved_manifest_duplicate_field")
        result[key] = value
    return result


def _path_contains_symlink(path: Path) -> bool:
    current = path
    while True:
        if current.is_symlink():
            return True
        if current == current.parent:
            return False
        current = current.parent


def _root_owned_manifest(path: Path) -> dict[str, Any]:
    if (
        not path.is_absolute()
        or _path_contains_symlink(path)
        or not path.is_file()
    ):
        raise UpdaterV2Error("ha_ota_approved_manifest_path_invalid")
    metadata = path.stat()
    if (
        metadata.st_uid != 0
        or stat.S_IMODE(metadata.st_mode) & 0o022
        or metadata.st_size <= 0
        or metadata.st_size > MAX_MANIFEST_BYTES
    ):
        raise UpdaterV2Error("ha_ota_approved_manifest_metadata_invalid")
    try:
        document = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise UpdaterV2Error("ha_ota_approved_manifest_invalid") from error
    if not isinstance(document, dict):
        raise UpdaterV2Error("ha_ota_approved_manifest_invalid")
    return document


def _validated_manifest(path: Path) -> dict[str, Any]:
    document = _root_owned_manifest(path)
    expected = {
        "schema",
        "approval_status",
        "signature_status",
        "validity_status",
        "verification_status",
        "version",
        "release_identity",
        "target_archive_size_bytes",
        "target",
    }
    if set(document) != expected or document.get("schema") != APPROVED_MANIFEST_SCHEMA:
        raise UpdaterV2Error("ha_ota_approved_manifest_schema_invalid")
    if (
        document.get("approval_status") != "APPROVED"
        or document.get("signature_status") != "VERIFIED"
        or document.get("validity_status") != "VALID"
        or document.get("verification_status") != "PASS"
    ):
        raise UpdaterV2Error("ha_ota_approved_manifest_not_approved")
    version = document.get("version")
    release = document.get("release_identity")
    size = document.get("target_archive_size_bytes")
    target = document.get("target")
    if (
        not isinstance(version, str)
        or _VERSION_RE.fullmatch(version) is None
        or not isinstance(release, str)
        or _RELEASE_RE.fullmatch(release) is None
        or type(size) is not int
        or size <= 0
        or size > 8 * 1024 * 1024 * 1024
        or not isinstance(target, dict)
    ):
        raise UpdaterV2Error("ha_ota_approved_manifest_invalid")
    target_expected = {
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
    }
    if set(target) != target_expected or target.get("schema") != TARGET_SCHEMA:
        raise UpdaterV2Error("ha_ota_target_manifest_invalid")
    if (
        target.get("component") != "homeassistant"
        or target.get("mutation_profile") != "IMAGE_ONLY_V1"
        or target.get("target_platform") != "linux/arm64"
        or target.get("rollback_compatible") is not True
    ):
        raise UpdaterV2Error("ha_ota_target_manifest_invalid")
    image_ref = target.get("target_image_ref")
    predecessor = target.get("expected_predecessor_image_ref")
    image_match = (
        _HA_IMAGE_RE.fullmatch(image_ref)
        if isinstance(image_ref, str)
        else None
    )
    if (
        image_match is None
        or image_match.group("version") != version
        or not isinstance(predecessor, str)
        or _HA_IMAGE_RE.fullmatch(predecessor) is None
        or predecessor == image_ref
    ):
        raise UpdaterV2Error("ha_ota_target_image_invalid")

    archive_sha = target.get("target_archive_sha256")
    if not isinstance(archive_sha, str) or SHA256.fullmatch(archive_sha) is None:
        raise UpdaterV2Error("ha_ota_target_manifest_invalid")
    if target.get("a1_classification_sha256") != A1_CLASSIFICATION_SHA256:
        raise UpdaterV2Error("ha_ota_target_a1_authority_mismatch")

    artifact = target.get("artifact_identity")
    if (
        not isinstance(artifact, dict)
        or set(artifact)
        != {"artifact_id", "artifact_digest_sha256", "artifact_name"}
        or type(artifact.get("artifact_id")) is not int
        or artifact["artifact_id"] <= 0
        or not isinstance(artifact.get("artifact_digest_sha256"), str)
        or SHA256.fullmatch(artifact["artifact_digest_sha256"]) is None
        or not isinstance(artifact.get("artifact_name"), str)
        or not artifact["artifact_name"]
    ):
        raise UpdaterV2Error("ha_ota_target_artifact_identity_invalid")

    compatibility = target.get("compatibility_evidence")
    if (
        not isinstance(compatibility, dict)
        or set(compatibility)
        != {
            "schema",
            "mutation_profile",
            "peer_contracts_compatible",
            "persistent_schema_compatible",
            "review_evidence_sha256",
            "predecessor_source_head",
            "target_source_head",
        }
        or compatibility.get("schema")
        != "gh.n3w-t1-core-updater-compatibility/1"
        or compatibility.get("mutation_profile") != "IMAGE_ONLY_V1"
        or compatibility.get("peer_contracts_compatible") is not True
        or compatibility.get("persistent_schema_compatible") is not True
        or not isinstance(compatibility.get("review_evidence_sha256"), str)
        or SHA256.fullmatch(compatibility["review_evidence_sha256"]) is None
        or not isinstance(compatibility.get("predecessor_source_head"), str)
        or _GIT_SHA_RE.fullmatch(compatibility["predecessor_source_head"]) is None
        or not isinstance(compatibility.get("target_source_head"), str)
        or _GIT_SHA_RE.fullmatch(compatibility["target_source_head"]) is None
    ):
        raise UpdaterV2Error("ha_ota_target_compatibility_invalid")
    return document


def _docker_container() -> dict[str, Any]:
    try:
        result = subprocess.run(
            ("docker", "inspect", "--type", "container", HOMEASSISTANT_CONTAINER),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
    except FileNotFoundError as error:
        raise UpdaterV2Error("ha_ota_docker_cli_unavailable") from error
    except subprocess.TimeoutExpired as error:
        raise UpdaterV2Error("ha_ota_docker_inspect_timeout") from error
    if result.returncode:
        raise UpdaterV2Error("ha_ota_homeassistant_container_unavailable")
    try:
        value = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UpdaterV2Error("ha_ota_docker_inspect_invalid") from error
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise UpdaterV2Error("ha_ota_docker_inspect_invalid")
    return value[0]


class FixedHostOtaAdmissionResolver:
    """Resolve release + current runtime from fixed host-owned authorities."""

    def __init__(
        self,
        manifest_path: Path = APPROVED_MANIFEST_SOURCE,
    ) -> None:
        self.manifest_path = manifest_path

    def resolve_homeassistant_release(
        self,
        release_identity: str,
    ) -> HostOtaAdmission:
        manifest = _validated_manifest(self.manifest_path)
        if manifest["release_identity"] != release_identity:
            raise UpdaterV2Error("ha_ota_ipc_release_binding_invalid")
        target = manifest["target"]
        container = _docker_container()
        config = container.get("Config")
        current_ref = config.get("Image") if isinstance(config, dict) else None
        runtime_id = container.get("Image")
        if (
            not isinstance(current_ref, str)
            or current_ref != target.get("expected_predecessor_image_ref")
            or not isinstance(runtime_id, str)
            or not runtime_id.startswith("sha256:")
        ):
            raise UpdaterV2Error("ha_ota_current_runtime_drift")
        target_identity = {
            "release_identity": release_identity,
            "target_manifest_sha256": sha256_bytes(canonical(target)),
            "target_image_ref": target["target_image_ref"],
            "target_archive_sha256": target["target_archive_sha256"],
        }
        return HostOtaAdmission(
            release_identity=release_identity,
            current_image_ref=current_ref,
            current_image_identity={
                "runtime_image_id": runtime_id,
                "platform": "linux/arm64",
            },
            target_manifest_identity=target_identity,
            target_image_ref=target["target_image_ref"],
            target_archive_sha256=target["target_archive_sha256"],
            target_archive_size=manifest["target_archive_size_bytes"],
        ).validate()


def publish_manager_manifest(
    source: Path = APPROVED_MANIFEST_SOURCE,
    destination: Path = RUNTIME_MANIFEST,
) -> bool:
    if source.is_symlink():
        raise UpdaterV2Error("ha_ota_approved_manifest_path_invalid")
    if not source.exists():
        if destination.is_symlink():
            raise UpdaterV2Error("ha_ota_runtime_manifest_path_invalid")
        destination.unlink(missing_ok=True)
        return False
    document = _validated_manifest(source)
    payload = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8") + b"\n"
    if destination.is_symlink():
        raise UpdaterV2Error("ha_ota_runtime_manifest_path_invalid")
    descriptor, raw = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        dir=destination.parent,
    )
    temporary = Path(raw)
    try:
        os.fchmod(descriptor, 0o640)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        os.chmod(destination, 0o640)
        directory = os.open(
            destination.parent,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def build_server() -> UnixSocketHaOtaServer:
    if os.geteuid() != 0:
        raise UpdaterV2Error("ha_ota_daemon_requires_root")
    if os.getegid() != EXPECTED_MANAGER_GID:
        raise UpdaterV2Error("ha_ota_daemon_group_invalid")
    if not RUNTIME_ROOT.is_dir() or RUNTIME_ROOT.is_symlink():
        raise UpdaterV2Error("ha_ota_runtime_root_invalid")
    metadata = RUNTIME_ROOT.stat()
    if (
        metadata.st_uid != 0
        or metadata.st_gid != EXPECTED_MANAGER_GID
        or stat.S_IMODE(metadata.st_mode) != 0o750
    ):
        raise UpdaterV2Error("ha_ota_runtime_root_metadata_invalid")
    publish_manager_manifest()
    transaction_store = HaUsbStateStore(STATE_ROOT)
    prepare_store = PrepareStateStore(STATE_ROOT)
    backend = SubprocessPrepareBackend(runtime_root=RUNTIME_ROOT)
    controller = HaUsbPrepareController(
        transaction_store=transaction_store,
        prepare_store=prepare_store,
        backend=backend,
    )
    executor = HaUsbIpcExecutor(
        store=transaction_store,
        admission_resolver=FixedHostOtaAdmissionResolver(),
        prepare_controller=controller,
    )
    executor.start_background_recovery()
    return UnixSocketHaOtaServer(
        dispatcher=HaUsbIpcDispatcher(executor),
        path=SOCKET_PATH,
        expected_peer_uid=EXPECTED_MANAGER_UID,
        mode=0o660,
    )


def main() -> int:
    server = build_server()
    stopping = False

    def stop_handler(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    server.start()
    try:
        while not stopping:
            time.sleep(0.25)
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
