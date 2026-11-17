from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
PREFLIGHT_EXECUTOR = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "u13b_p3_fresh_readonly_preflight" / "executor.py"
)
SSH_TRANSPORT_SOURCE = ROOT / "tools" / "n3w_t1_ssh_transport.py"
TARGET_MANIFEST = (
    ROOT / "infra" / "n3w-t1" / "upgrades"
    / "homeassistant-2026.10.3-u13b-physical.json"
)

GATE_ID = "N3W_T1_U13B_P3_ACCEPTANCE_CLEAN_OTA_TO_U11_LIVE_20261117_01"
AUTHORIZATION_ID = "N3W_T1_U13B_P3_NEW_CLEAN_OTA_20261117_01"
PRODUCT_U9_AUTHORIZATION_ID = "N3W_T1_U13B_P3_PRODUCT_U9_20261117_01"
CONFIRMATION = "EXECUTE P3 CLEAN OTA TO U11: YES"
MANIFEST_SCHEMA = "gh.n3w-t1-u13b-p3-live-to-u11-manifest/1"
RESULT_SCHEMA = "gh.n3w-t1-u13b-p3-live-to-u11/1"


class Stop(RuntimeError):
    pass


def git_text(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("git_command_failed:" + args[0])
    return completed.stdout.strip()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Stop("module_load_failed:" + path.name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest(expected_commit: str, *, require_authorized: bool) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")
    value = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected_state = {
        "granted": bool(require_authorized),
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    if (
        value.get("schema") != MANIFEST_SCHEMA
        or value.get("gate_id") != GATE_ID
        or value.get("authorization_id") != AUTHORIZATION_ID
        or value.get("product_u9_authorization_id")
        != PRODUCT_U9_AUTHORIZATION_ID
        or value.get("confirmation") != CONFIRMATION
        or value.get("live_execution_authorized") is not require_authorized
        or value.get("new_clean_ota_mutation_authorized")
        is not require_authorized
        or value.get("authorization_state") != expected_state
        or value.get("u13b_live_execution_authorized") is not False
        or value.get("controlled_rollback_mutation_authorized") is not False
    ):
        raise Stop("manifest_gate_invalid")
    for relative, blob in {
        **value["package_source_authority"],
        **value["product_source_authority"],
    }.items():
        if git_text("rev-parse", "HEAD:" + relative) != blob:
            raise Stop("source_authority_drift:" + relative)
    return value


def build_source_bundle(manifest: dict[str, Any], root: Path) -> tuple[Path, dict[str, str]]:
    bundle = root / "exact-tools.zip"
    hashes: dict[str, str] = {}
    seen: set[str] = set()
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in sorted(manifest["product_source_authority"]):
            source = ROOT / relative
            name = source.name
            if name in seen:
                raise Stop("source_bundle_name_collision:" + name)
            seen.add(name)
            raw = source.read_bytes()
            hashes[name] = hashlib.sha256(raw).hexdigest()
            archive.writestr(name, raw)
    os.chmod(bundle, 0o600)
    return bundle, hashes


def verify_local_target_archive(path: Path, manifest: dict[str, Any]) -> None:
    target = manifest["acceptance_target"]
    if path.is_symlink() or not path.is_file():
        raise Stop("target_archive_invalid")
    if path.stat().st_size != target["target_archive_size_bytes"]:
        raise Stop("target_archive_size_drift")
    if sha_file(path) != target["target_archive_sha256"]:
        raise Stop("target_archive_sha256_drift")
    tools = str(ROOT / "tools")
    import sys
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import n3w_t1_portable_image_identity as portable
    identity = portable.parse_image_archive(
        path,
        expected_archive_sha256=target["target_archive_sha256"],
        expected_archive_size_bytes=target["target_archive_size_bytes"],
        expected_tag=target["target_image_ref"],
        platform_os="linux",
        platform_architecture="arm64",
    )
    if identity.os != "linux" or identity.architecture != "arm64":
        raise Stop("target_archive_platform_drift")


REMOTE_SCRIPT = r"""
import base64
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

STATE_ROOT_BASE = Path("/var/lib/n3w-t1-core-updater")
HA_CONTAINER = "n3wfc4-homeassistant-1"
MANAGER_CONTAINER = "n3wfc4-manager-1"
BROKER_CONTAINER = "n3wfc4-broker-1"


class Stop(RuntimeError):
    pass


def sha_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def durable_json_once(path, value):
    if path.exists() or path.is_symlink():
        raise Stop("durable_path_exists:" + path.name)
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    fsync_dir(path.parent)


def durable_json_replace(path, value):
    payload = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd, raw = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    temp = Path(raw)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        fsync_dir(path.parent)
    finally:
        temp.unlink(missing_ok=True)


def run(argv, timeout=300, check=True):
    completed = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode:
        raise Stop("command_failed:" + argv[0] + ":" + str(completed.returncode))
    return completed


def inspect_container(name):
    value = json.loads(run(["docker", "inspect", "--type", "container", name], timeout=45).stdout)
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise Stop("container_inspect_invalid:" + name)
    item = value[0]
    config = item.get("Config")
    state = item.get("State")
    return {
        "container_id": item.get("Id"),
        "image_ref": config.get("Image") if isinstance(config, dict) else None,
        "runtime_image_id": item.get("Image"),
        "state": state.get("Status") if isinstance(state, dict) else None,
        "restart_count": item.get("RestartCount"),
    }


def image_present(reference):
    return run(["docker", "image", "inspect", reference], timeout=45, check=False).returncode == 0


def validate_claim(plan):
    root = Path(plan["state_root"])
    claim = json.loads((root / "authorization_claim.json").read_text())
    if (
        claim.get("authorization_id") != plan["authorization_id"]
        or claim.get("execution_id") != plan["execution_id"]
        or claim.get("claimed") is not True
        or claim.get("consumed") is not True
        or claim.get("replay_permitted") is not False
    ):
        raise Stop("live_claim_invalid")
    return root, claim


def init_claim(plan, authorization_id, confirmation):
    if (
        authorization_id != plan["authorization_id"]
        or confirmation != plan["confirmation"]
        or plan.get("live_execution_authorized") is not True
        or plan.get("new_clean_ota_mutation_authorized") is not True
        or plan.get("authorization_state")
        != {
            "granted": True,
            "claimed": False,
            "consumed": False,
            "replay_permitted": False,
        }
    ):
        raise Stop("authorization_invalid")
    root = Path(plan["state_root"])
    if root.exists() or root.is_symlink():
        raise Stop("live_state_root_residue")

    tools = Path("/opt/HomeAssistant/tools")
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend
    from n3w_t1_core_updater_ha_usb_media import classify_candidate
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore

    store = HaUsbStateStore()
    current = store.read()
    expected = plan["expected_terminal_u13a"]
    if (
        current is None
        or current.get("phase") != "U13A_COMMITTED"
        or current.get("status") != "COMMITTED"
        or current.get("transaction_id_sha256") != expected["transaction_id_sha256"]
        or current.get("usb_filesystem_uuid") != expected["filesystem_uuid"]
        or sha_file(store.path) != expected["transaction_sha256"]
    ):
        raise Stop("preclaim_terminal_u13a_drift")

    peers = {
        "homeassistant": inspect_container(HA_CONTAINER),
        "manager": inspect_container(MANAGER_CONTAINER),
        "broker": inspect_container(BROKER_CONTAINER),
    }
    if (
        peers["homeassistant"]["image_ref"] != expected["target_image"]
        or peers["homeassistant"]["runtime_image_id"] != expected["target_runtime_image_id"]
        or peers["homeassistant"]["state"] != "running"
        or peers["manager"]["state"] != "running"
        or peers["broker"]["state"] != "running"
    ):
        raise Stop("preclaim_runtime_drift")

    old_fingerprint = current.get("usb_device_identity_public_fingerprint")
    if not isinstance(old_fingerprint, str) or len(old_fingerprint) != 64:
        raise Stop("historical_usb_fingerprint_invalid")

    fresh = []
    for candidate in SubprocessPrepareBackend().inventory():
        reasons = classify_candidate(candidate.as_media_candidate())
        if not reasons and candidate.public_fingerprint != old_fingerprint:
            fresh.append(candidate)
    expected_fresh = plan["preflight"]["fresh_usb_public_fingerprint"]
    if (
        len(fresh) != 1
        or fresh[0].public_fingerprint != expected_fresh
    ):
        raise Stop("preclaim_fresh_usb_candidate_drift")

    root.mkdir(mode=0o700)
    os.chown(root, 0, 0)
    staging = root / "staging"
    staging.mkdir(mode=0o700)
    os.chown(staging, 0, 0)
    claim = {
        "schema": "gh.n3w-t1-u13b-p3-live-authorization-claim/1",
        "gate_id": plan["gate_id"],
        "authorization_id": authorization_id,
        "execution_id": plan["execution_id"],
        "claimed": True,
        "consumed": True,
        "replay_permitted": False,
        "historical_transaction_id_sha256": current["transaction_id_sha256"],
        "historical_usb_public_fingerprint": old_fingerprint,
        "peers": peers,
    }
    durable_json_once(root / "authorization_claim.json", claim)
    return {
        "schema": "gh.n3w-t1-u13b-p3-live-init/1",
        "status": "P3_LIVE_AUTHORIZATION_CLAIMED",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_permitted": False,
        "historical_usb_public_fingerprint": old_fingerprint,
        "peers": peers,
    }


def load_exact_tools(plan):
    root, _claim = validate_claim(plan)
    bundle = root / "staging" / "exact-tools.zip"
    if bundle.is_symlink() or not bundle.is_file():
        raise Stop("source_bundle_missing")
    if sha_file(bundle) != plan["source_bundle_sha256"]:
        raise Stop("source_bundle_sha256_drift")
    destination = root / "exact-tools"
    if destination.exists() or destination.is_symlink():
        raise Stop("exact_tools_residue")
    destination.mkdir(mode=0o700)
    os.chown(destination, 0, 0)
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        if set(names) != set(plan["product_source_sha256"]):
            raise Stop("source_bundle_member_drift")
        for name in names:
            if Path(name).name != name or "/" in name or "\\" in name:
                raise Stop("source_bundle_member_invalid")
            raw = archive.read(name)
            if hashlib.sha256(raw).hexdigest() != plan["product_source_sha256"][name]:
                raise Stop("source_bundle_member_hash_drift:" + name)
            path = destination / name
            fd = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                os.write(fd, raw)
                os.fsync(fd)
            finally:
                os.close(fd)
    fsync_dir(destination)
    sys.path.insert(0, str(destination))
    return destination


def execute(plan):
    root, claim = validate_claim(plan)
    exact_tools = load_exact_tools(plan)

    from n3w_t1_core_updater_ha_backup import (
        ProtectedHaDataBackupProvider,
        backup_record_from_document,
    )
    from n3w_t1_core_updater_ha_capacity import validate_recovery_admission_capacity
    from n3w_t1_core_updater_ha_install import (
        HaUsbU6PredecessorController,
        HaUsbU7BackupController,
    )
    from n3w_t1_core_updater_ha_ipc import HaUsbIpcExecutor, HostOtaAdmission
    from n3w_t1_core_updater_ha_prepare import (
        HaUsbPrepareController,
        PrepareStateStore,
    )
    from n3w_t1_core_updater_ha_prepare_host import (
        HostReleasePolicy,
        SubprocessPrepareBackend,
    )
    from n3w_t1_core_updater_ha_recovery import (
        ImageRecoveryRecord,
        image_recovery_record_from_document,
    )
    from n3w_t1_core_updater_ha_u11 import HaUsbU11TargetInstallController
    from n3w_t1_core_updater_ha_u11_host import LocalU11RuntimeOwner
    from n3w_t1_core_updater_ha_usb import (
        claim_live_authorization,
        destructive_cutover_allowed,
        record_predecessor_capacity_released,
        record_recovery_admission,
    )
    from n3w_t1_core_updater_ha_usb_media import assess_capacity, classify_candidate
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore
    from n3w_t1_core_updater_host import LocalHost
    import n3w_t1_core_updater_ha_capacity as capacity
    import n3w_t1_portable_image_identity as portable
    from n3w_t1_core_updater_v2_common import canonical, sha256_bytes

    staged = root / "staging" / "homeassistant-arm64.tar.gz"
    target = plan["acceptance_target"]
    if (
        staged.is_symlink()
        or not staged.is_file()
        or staged.stat().st_uid != 0
        or staged.stat().st_size != target["target_archive_size_bytes"]
        or sha_file(staged) != target["target_archive_sha256"]
    ):
        raise Stop("staged_target_identity_invalid")
    portable.parse_image_archive(
        staged,
        expected_archive_sha256=target["target_archive_sha256"],
        expected_archive_size_bytes=target["target_archive_size_bytes"],
        expected_tag=target["target_image_ref"],
        platform_os="linux",
        platform_architecture="arm64",
    )

    class StaticResolver:
        def __init__(self, admission):
            self.admission = admission

        def resolve_homeassistant_release(self, release_identity):
            if release_identity != self.admission.release_identity:
                raise Stop("acceptance_release_drift")
            return self.admission

    class AcceptancePolicyProvider:
        def load(self, transaction):
            value = HostReleasePolicy(
                release_identity=plan["acceptance_release_identity"],
                artifact_url=(
                    "https://ota.hahub.top/n3w/homeassistant/releases/"
                    + plan["acceptance_release_identity"]
                    + "/homeassistant-arm64.tar.gz"
                ),
                target_archive_sha256=target["target_archive_sha256"],
                target_archive_size_bytes=target["target_archive_size_bytes"],
                expected_predecessor_image_ref=target["expected_predecessor_image_ref"],
                predecessor_recovery_budget_bytes=plan["predecessor_recovery_budget_bytes"],
                capacity_policy=capacity.CapacityPolicy.frozen(),
            ).validate()
            if (
                transaction.get("current_image_ref") != value.expected_predecessor_image_ref
                or transaction.get("target_archive_sha256") != value.target_archive_sha256
                or transaction.get("target_archive_size") != value.target_archive_size_bytes
                or transaction.get("target_manifest_identity", {}).get("release_identity")
                != value.release_identity
            ):
                raise Stop("acceptance_policy_binding_drift")
            return value

    old_fingerprint = claim["historical_usb_public_fingerprint"]

    class StagedArtifactBackend(SubprocessPrepareBackend):
        def __init__(self):
            super().__init__(policy_provider=AcceptancePolicyProvider())

        def inventory(self):
            return tuple(
                candidate
                for candidate in super().inventory()
                if candidate.public_fingerprint != old_fingerprint
            )

        def prepare_target(self, *, transaction, media):
            media.validate()
            self._require_bound_media(media)
            policy = self.policy_provider.load(transaction)
            destination_root = Path(media.mount_path) / "n3w-update" / "target"
            if destination_root.is_symlink():
                raise Stop("acceptance_target_dir_invalid")
            destination_root.mkdir(mode=0o700, exist_ok=True)
            os.chmod(destination_root, 0o700)
            destination = destination_root / "homeassistant-arm64.tar.gz"
            if destination.exists() or destination.is_symlink():
                raise Stop("acceptance_target_destination_exists")
            identity = portable.parse_image_archive(
                staged,
                expected_archive_sha256=policy.target_archive_sha256,
                expected_archive_size_bytes=policy.target_archive_size_bytes,
                expected_tag=transaction["target_image_ref"],
                platform_os="linux",
                platform_architecture="arm64",
            )
            fd, raw = tempfile.mkstemp(prefix=".p3-target.", dir=destination_root)
            temp = Path(raw)
            digest = hashlib.sha256()
            total = 0
            try:
                os.fchmod(fd, 0o600)
                with staged.open("rb") as source, os.fdopen(fd, "wb", closefd=True) as output:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        total += len(block)
                        digest.update(block)
                        output.write(block)
                    output.flush()
                    os.fsync(output.fileno())
                if (
                    total != policy.target_archive_size_bytes
                    or digest.hexdigest() != policy.target_archive_sha256
                ):
                    raise Stop("acceptance_target_copy_identity_drift")
                os.replace(temp, destination)
                fsync_dir(destination_root)
            finally:
                try:
                    os.close(fd)
                except OSError:
                    pass
                temp.unlink(missing_ok=True)
            self._require_bound_media(media)
            return ImageRecoveryRecord(
                kind="target",
                image_ref=transaction["target_image_ref"],
                archive_sha256=policy.target_archive_sha256,
                archive_size_bytes=policy.target_archive_size_bytes,
                portable_identity_sha256=sha256_bytes(canonical(identity.to_dict())),
                platform="linux/arm64",
                verified=True,
                fsynced=True,
            )

    admission = HostOtaAdmission(
        release_identity=plan["acceptance_release_identity"],
        current_image_ref=target["expected_predecessor_image_ref"],
        current_image_identity={
            "runtime_image_id": plan["expected_terminal_u13a"]["target_runtime_image_id"],
            "platform": "linux/arm64",
        },
        target_manifest_identity={
            "release_identity": plan["acceptance_release_identity"],
            "target_manifest_sha256": plan["target_manifest_sha256"],
            "target_image_ref": target["target_image_ref"],
            "target_archive_sha256": target["target_archive_sha256"],
        },
        target_image_ref=target["target_image_ref"],
        target_archive_sha256=target["target_archive_sha256"],
        target_archive_size=target["target_archive_size_bytes"],
    ).validate()

    store = HaUsbStateStore()
    before = store.read()
    if (
        before is None
        or before.get("phase") != "U13A_COMMITTED"
        or before.get("transaction_id_sha256")
        != plan["expected_terminal_u13a"]["transaction_id_sha256"]
        or sha_file(store.path) != plan["expected_terminal_u13a"]["transaction_sha256"]
    ):
        raise Stop("terminal_drift_before_prepare")

    def progress(phase, **extra):
        value = {
            "schema": "gh.n3w-t1-u13b-p3-live-progress/1",
            "phase": phase,
            "updated_at_unix": int(time.time()),
        }
        value.update(extra)
        durable_json_replace(root / "progress.json", value)

    result = {
        "schema": "gh.n3w-t1-u13b-p3-live-to-u11/1",
        "status": "STOP_POSTCLAIM",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_permitted": False,
        "transaction_mutation": False,
        "usb_mutation": False,
        "service_mutation": False,
        "image_mutation": False,
        "ha_data_mutation": False,
        "u11_reached": False,
        "u12_plus": False,
        "board_access": False,
        "merge": False,
    }

    try:
        backend = StagedArtifactBackend()
        progress("prepare_new")
        resolver = StaticResolver(admission)
        ipc = HaUsbIpcExecutor(
            store=store,
            admission_resolver=resolver,
            prepare_controller=None,
        )
        ipc.submit("PREPARE", plan["acceptance_release_identity"])
        current = store.read()
        if (
            current is None
            or current.get("phase") != "U1_PREPARE_REQUESTED"
            or current.get("transaction_id_sha256") == before.get("transaction_id_sha256")
        ):
            raise Stop("fresh_transaction_not_created")
        result["transaction_mutation"] = True

        progress("fresh_usb_candidate")
        prepare_store = PrepareStateStore(store.root)
        prepare = HaUsbPrepareController(
            transaction_store=store,
            prepare_store=prepare_store,
            backend=backend,
        )
        prepare.begin(current)
        status = prepare.refresh_candidate()
        state = prepare_store.read()
        candidate = state.get("candidate") if isinstance(state, dict) else None
        if (
            status.get("phase") != "USB_REQUIRED_CONFIRMATION"
            or status.get("usb_confirmation_required") is not True
            or not isinstance(candidate, dict)
            or candidate.get("public_fingerprint") == old_fingerprint
        ):
            raise Stop("fresh_usb_candidate_not_ready")

        progress("fresh_usb_format_and_target_prepare")
        prepare.confirm_and_prepare()
        current = store.read()
        if current is None or current.get("phase") != "U4_READY_TO_INSTALL":
            raise Stop("u4_not_reached")
        result["usb_mutation"] = True

        staged.unlink()
        fsync_dir(staged.parent)

        progress("request_install")
        prepare.revalidate_and_request_install()
        current = store.read()
        if current is None or current.get("phase") != "U5_INSTALL_REQUESTED_REVALIDATING":
            raise Stop("u5_not_reached")

        progress("u6_predecessor_recovery")
        u6 = HaUsbU6PredecessorController(
            transaction_store=store,
            backend=backend,
        )
        u6_result = u6.prepare_or_resume()
        if u6_result.transaction.get("phase") != "U6_PREDECESSOR_RECOVERY_PREPARING":
            raise Stop("u6_not_reached")

        progress("u7_backup")
        runtime_owner = LocalHost()
        backup_provider = ProtectedHaDataBackupProvider(progress=lambda phase, value=0: progress(phase, value=value))
        u7 = HaUsbU7BackupController(
            transaction_store=store,
            backend=backend,
            runtime_owner=runtime_owner,
            backup_provider=backup_provider,
            progress=lambda phase, value=0: progress(phase, value=value),
        )
        u7_result = u7.prepare_or_resume()
        current = store.read()
        if (
            current is None
            or current.get("phase") != "U7_HA_QUIESCED_DATA_BACKUP_PREPARING"
            or current.get("ha_data_backup_verified") is not True
        ):
            raise Stop("u7_not_reached")
        result["service_mutation"] = True
        result["ha_data_mutation"] = True

        progress("u8_recovery_admission")
        media = backend.resolve_transaction_media(current, write_required=True)
        if media is None:
            raise Stop("u8_media_missing")
        target_record = image_recovery_record_from_document(
            current.get("target_artifact_identity"),
            expected_kind="target",
            expected_image_ref=current["target_image_ref"],
            expected_archive_sha256=current["target_archive_sha256"],
        )
        predecessor = image_recovery_record_from_document(
            current.get("predecessor_recovery_identity"),
            expected_kind="predecessor",
            expected_image_ref=current["current_image_ref"],
        )
        backup = backup_record_from_document(current.get("ha_data_backup_identity"))
        capacity_report = assess_capacity(
            current["usb_measured_usable_bytes"],
            backend.capacity_inputs(current),
        )
        recovery_capacity = backend.recovery_admission_capacity(
            current,
            media,
            target=target_record,
            predecessor=predecessor,
            backup=backup,
        )
        validate_recovery_admission_capacity(
            recovery_capacity,
            target_archive_bytes=target_record.archive_size_bytes,
            predecessor_archive_bytes=predecessor.archive_size_bytes,
            ha_backup_archive_bytes=backup.archive_size_bytes,
        )
        host = LocalHost()
        prestate_exact = (
            host.component_binding_v2("homeassistant")
            == target["expected_predecessor_image_ref"]
            and image_present(target["expected_predecessor_image_ref"])
            and not image_present(target["target_image_ref"])
        )
        admitted = record_recovery_admission(
            current,
            target=target_record,
            predecessor=predecessor,
            backup=backup,
            capacity_report=capacity_report,
            recovery_capacity=recovery_capacity,
            production_prestate_exact=prestate_exact,
        )
        backend.sync_transaction_metadata(admitted, media)
        store.write(admitted)

        progress("u9_product_authorization")
        claimed = claim_live_authorization(
            admitted,
            plan["product_u9_authorization_id"],
        )
        if destructive_cutover_allowed(claimed) is not True:
            raise Stop("u9_destructive_cutover_not_allowed")
        backend.sync_transaction_metadata(claimed, media)
        store.write(claimed)

        progress("u10_predecessor_release")
        ha = inspect_container(HA_CONTAINER)
        expected_ha = claim["peers"]["homeassistant"]
        if (
            ha["container_id"] != expected_ha["container_id"]
            or ha["runtime_image_id"] != expected_ha["runtime_image_id"]
            or ha["image_ref"] != target["expected_predecessor_image_ref"]
        ):
            raise Stop("u10_predecessor_runtime_drift")
        if image_present(target["target_image_ref"]):
            raise Stop("u10_target_preexisting")
        run(["docker", "rm", ha["container_id"]], timeout=120)
        result["service_mutation"] = True
        run(["docker", "image", "rm", ha["runtime_image_id"]], timeout=300)
        result["image_mutation"] = True
        if image_present(target["expected_predecessor_image_ref"]):
            raise Stop("u10_predecessor_image_still_present")
        if image_present(target["target_image_ref"]):
            raise Stop("u10_target_loaded_early")
        u10 = record_predecessor_capacity_released(
            claimed,
            predecessor_runtime_released=True,
            predecessor_image_released=True,
            target_internal_image_absent=True,
        )
        backend.sync_transaction_metadata(u10, media)
        store.write(u10)

        progress("u11_target_install")
        manager = claim["peers"]["manager"]
        broker = claim["peers"]["broker"]
        owner = LocalU11RuntimeOwner(
            expected_manager_container_id=manager["container_id"],
            expected_manager_image_ref=manager["image_ref"],
            expected_manager_runtime_image_id=manager["runtime_image_id"],
            expected_broker_container_id=broker["container_id"],
            expected_broker_image_ref=broker["image_ref"],
            expected_broker_runtime_image_id=broker["runtime_image_id"],
        )
        u11 = HaUsbU11TargetInstallController(
            transaction_store=store,
            backend=backend,
            runtime_owner=owner,
        )
        installed = u11.install()
        final = store.read()
        if (
            final is None
            or final.get("phase") != "U11_TARGET_INSTALLED_STARTED"
            or final.get("status") != "ACTIVE"
            or installed.transaction.get("phase") != "U11_TARGET_INSTALLED_STARTED"
        ):
            raise Stop("u11_terminal_drift")

        result.update(
            status="P3_CLEAN_OTA_TO_U11_PASS",
            transaction_mutation=True,
            usb_mutation=True,
            service_mutation=True,
            image_mutation=True,
            ha_data_mutation=True,
            u11_reached=True,
            u12_plus=False,
            transaction_phase=final["phase"],
            transaction_id_sha256=final["transaction_id_sha256"],
            transaction_sha256=sha_file(store.path),
            usb_filesystem_uuid=final["usb_filesystem_uuid"],
            target_runtime_image_id=installed.target_runtime_image_id,
            recovery_content_manifest_sha256=final[
                "recovery_content_manifest_sha256"
            ],
        )
        progress("u11_stop_boundary")
        durable_json_once(root / "success.json", result)
        return result
    except Exception as error:
        result["reason"] = type(error).__name__ + ":" + str(error)[:300]
        result["recovery_required"] = True
        try:
            current = store.read()
            if current is not None:
                result["transaction_phase"] = current.get("phase")
                result["transaction_id_sha256"] = current.get("transaction_id_sha256")
                result["u11_reached"] = (
                    current.get("phase") == "U11_TARGET_INSTALLED_STARTED"
                )
        except Exception:
            pass
        try:
            durable_json_once(root / "failure.json", result)
        except Exception:
            pass
        return result


def status(plan):
    root = Path(plan["state_root"])
    if not root.exists():
        return {
            "schema": "gh.n3w-t1-u13b-p3-live-status/1",
            "status": "NOT_STARTED",
            "terminal": False,
            "authorization_claimed": False,
            "authorization_consumed": False,
            "replay_permitted": False,
        }
    for name in ("success.json", "failure.json"):
        path = root / name
        if path.exists():
            value = json.loads(path.read_text())
            value["terminal"] = True
            value["reconciled_from_ledger"] = True
            return value
    claim = json.loads((root / "authorization_claim.json").read_text())
    progress_path = root / "progress.json"
    progress = json.loads(progress_path.read_text()) if progress_path.exists() else None
    return {
        "schema": "gh.n3w-t1-u13b-p3-live-status/1",
        "status": "RUNNING_OR_INTERRUPTED",
        "terminal": False,
        "authorization_claimed": claim.get("claimed") is True,
        "authorization_consumed": claim.get("consumed") is True,
        "replay_permitted": False,
        "progress": progress,
    }


def main():
    mode = sys.argv[1]
    plan = json.loads(base64.b64decode(sys.argv[2]).decode("utf-8"))
    try:
        if mode == "init":
            value = init_claim(plan, sys.argv[3], sys.argv[4])
        elif mode == "execute":
            value = execute(plan)
        elif mode == "status":
            value = status(plan)
        else:
            raise Stop("mode_invalid")
    except Exception as error:
        value = {
            "schema": "gh.n3w-t1-u13b-p3-live-to-u11/1",
            "status": "STOP",
            "reason": type(error).__name__ + ":" + str(error)[:300],
            "authorization_claimed": False,
            "authorization_consumed": False,
            "replay_permitted": False,
            "u11_reached": False,
            "u12_plus": False,
            "board_access": False,
            "merge": False,
        }
    print(json.dumps(value, sort_keys=True))
    if mode == "status":
        raise SystemExit(0)
    raise SystemExit(
        0
        if value.get("status") in {
            "P3_LIVE_AUTHORIZATION_CLAIMED",
            "P3_CLEAN_OTA_TO_U11_PASS",
        }
        else 2
    )


main()
"""


def remote_mode(transport, mode: str, plan: dict[str, Any], *extra: str, timeout: int = 300):
    payload = base64.b64encode(
        json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    ).decode("ascii")
    completed = transport.run_remote(
        ["python3", "-B", "-c", REMOTE_SCRIPT, mode, payload, *extra],
        timeout=timeout,
        check=False,
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise Stop("remote_stdout_empty")
    try:
        value = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        raise Stop("remote_result_invalid") from error
    return completed, value


def build_plan(
    manifest: dict[str, Any],
    *,
    execution_id: str,
    preflight: dict[str, Any],
    source_bundle: Path,
    source_hashes: dict[str, str],
) -> dict[str, Any]:
    import sys
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from n3w_t1_core_updater_v2_common import canonical, sha256_bytes

    target_doc = json.loads(TARGET_MANIFEST.read_text(encoding="utf-8"))
    return {
        "gate_id": GATE_ID,
        "authorization_id": AUTHORIZATION_ID,
        "product_u9_authorization_id": PRODUCT_U9_AUTHORIZATION_ID,
        "confirmation": CONFIRMATION,
        "execution_id": execution_id,
        "state_root": manifest["state_root_prefix"] + execution_id,
        "live_execution_authorized": manifest["live_execution_authorized"],
        "new_clean_ota_mutation_authorized": manifest[
            "new_clean_ota_mutation_authorized"
        ],
        "authorization_state": manifest["authorization_state"],
        "acceptance_release_identity": manifest["acceptance_release_identity"],
        "acceptance_target": manifest["acceptance_target"],
        "expected_terminal_u13a": manifest["expected_terminal_u13a"],
        "predecessor_recovery_budget_bytes": manifest[
            "predecessor_recovery_budget_bytes"
        ],
        "target_manifest_sha256": sha256_bytes(canonical(target_doc)),
        "source_bundle_sha256": sha_file(source_bundle),
        "product_source_sha256": source_hashes,
        "preflight": {
            "status": preflight["status"],
            "historical_transaction_sha256": preflight[
                "historical_transaction_sha256"
            ],
            "historical_transaction_id_sha256": preflight[
                "historical_transaction_id_sha256"
            ],
            "historical_usb_filesystem_uuid": preflight[
                "historical_usb_filesystem_uuid"
            ],
            "fresh_usb_candidate_count": preflight["fresh_usb_candidate_count"],
            "fresh_usb_public_fingerprint": preflight[
                "fresh_usb_candidate"
            ]["public_fingerprint"],
        },
    }


def source_check(manifest: dict[str, Any]) -> dict[str, Any]:
    target = manifest["acceptance_target"]
    if target["target_image_ref"] == target["expected_predecessor_image_ref"]:
        raise Stop("target_not_distinct")
    if manifest["execution_contract"]["stop_at_u11_before_u12"] is not True:
        raise Stop("u11_stop_contract_missing")
    return {
        "schema": RESULT_SCHEMA,
        "gate_id": GATE_ID,
        "status": "P3_LIVE_TO_U11_SOURCE_READY",
        "live_execution_authorized": False,
        "new_clean_ota_mutation_authorized": False,
        "fresh_readonly_preflight_required": True,
        "fresh_usb_required": True,
        "historical_usb_reuse_forbidden": True,
        "exact_source_bundle_required": True,
        "exact_target_archive_required": True,
        "stop_at_u11_before_u12": True,
        "u13b_live_execution_authorized": False,
        "controlled_rollback_mutation_authorized": False,
        "board_access": False,
        "merge": False,
    }


def execute_live(
    args,
    manifest: dict[str, Any],
    access_state: dict[str, Any],
) -> dict[str, Any]:
    if args.authorization_id != AUTHORIZATION_ID or args.confirm != CONFIRMATION:
        raise Stop("local_authorization_invalid")
    target_archive = args.target_archive.expanduser()
    verify_local_target_archive(target_archive, manifest)

    preflight_module = load_module(
        PREFLIGHT_EXECUTOR,
        "n3w_u13b_p3_live_fresh_preflight",
    )
    evidence = preflight_module.prepare_evidence_root(args.evidence_root)
    preflight_access = {"t1_access": False}
    preflight = preflight_module.run_readonly(
        manifest=manifest["embedded_preflight_manifest"],
        execution_id=args.execution_id + "-preclaim",
        evidence_root=evidence,
        t1_ssh_target=args.t1_ssh_target,
        known_hosts=args.known_hosts,
        expected_host_key_sha256=args.expected_host_key_sha256,
        access_state=preflight_access,
    )
    access_state["t1_access"] = bool(preflight_access.get("t1_access"))
    if (
        preflight.get("status") != "P3_FRESH_REAL_T1_READONLY_PREFLIGHT_PASS"
        or preflight.get("prepare_new_admissible") is not True
        or preflight.get("fresh_usb_candidate_count") != 1
    ):
        raise Stop("fresh_preflight_not_ready")

    with tempfile.TemporaryDirectory(prefix="n3w-p3-live-") as raw:
        work = Path(raw)
        source_bundle, source_hashes = build_source_bundle(manifest, work)
        plan = build_plan(
            manifest,
            execution_id=args.execution_id,
            preflight=preflight,
            source_bundle=source_bundle,
            source_hashes=source_hashes,
        )

        transport_type = load_module(
            SSH_TRANSPORT_SOURCE,
            "n3w_u13b_p3_live_transport",
        ).SSHTransport
        transport = transport_type(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts.expanduser(),
            expected_host_key_sha256=args.expected_host_key_sha256,
        )
        transport.start_epoch()
        try:
            init_completed, init_value = remote_mode(
                transport,
                "init",
                plan,
                AUTHORIZATION_ID,
                CONFIRMATION,
                timeout=180,
            )
            if (
                init_completed.returncode != 0
                or init_value.get("status") != "P3_LIVE_AUTHORIZATION_CLAIMED"
            ):
                raise Stop("remote_claim_failed:" + str(init_value.get("reason", "unknown"))[:220])
            remote_root = plan["state_root"] + "/staging/"
            transport.scp_to(
                source_bundle,
                remote_root + "exact-tools.zip",
                timeout=600,
            )
            transport.scp_to(
                target_archive,
                remote_root + "homeassistant-arm64.tar.gz",
                timeout=3600,
            )
            completed, value = remote_mode(
                transport,
                "execute",
                plan,
                timeout=7200,
            )
            if completed.returncode == 0 and value.get("status") == "P3_CLEAN_OTA_TO_U11_PASS":
                return value
            status_completed, status_value = remote_mode(
                transport,
                "status",
                plan,
                timeout=180,
            )
            if status_completed.returncode == 0 and status_value.get("status") == "P3_CLEAN_OTA_TO_U11_PASS":
                return status_value
            raise Stop(
                "live_execute_failed:"
                + str(value.get("reason", status_value.get("reason", "unknown")))[:240]
            )
        finally:
            transport.close_epoch()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-package-commit", required=True)
    parser.add_argument("--mode", choices=("source-check", "execute"), default="source-check")
    parser.add_argument("--execution-id")
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--t1-ssh-target")
    parser.add_argument("--known-hosts", type=Path)
    parser.add_argument("--expected-host-key-sha256")
    parser.add_argument("--target-archive", type=Path)
    parser.add_argument("--authorization-id")
    parser.add_argument("--confirm")
    args = parser.parse_args()

    result = {
        "schema": RESULT_SCHEMA,
        "gate_id": GATE_ID,
        "status": "STOP",
        "t1_access": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
        "live_execution_authorized": False,
        "new_clean_ota_mutation_authorized": False,
        "u13b_live_execution_authorized": False,
        "controlled_rollback_mutation_authorized": False,
        "u11_reached": False,
        "u12_plus": False,
        "board_access": False,
        "merge": False,
    }
    try:
        execute = args.mode == "execute"
        manifest = read_manifest(
            args.expected_package_commit,
            require_authorized=execute,
        )
        result["live_execution_authorized"] = manifest[
            "live_execution_authorized"
        ]
        result["new_clean_ota_mutation_authorized"] = manifest[
            "new_clean_ota_mutation_authorized"
        ]
        if not execute:
            result.update(source_check(manifest))
            print(json.dumps(result, sort_keys=True))
            return 0
        if not all(
            (
                args.execution_id,
                args.evidence_root,
                args.t1_ssh_target,
                args.known_hosts,
                args.expected_host_key_sha256,
                args.target_archive,
                args.authorization_id,
                args.confirm,
            )
        ):
            raise Stop("live_arguments_missing")
        result.update(execute_live(args, manifest, result))
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        result["reason"] = type(error).__name__ + ":" + str(error)[:300]
        print(json.dumps(result, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
