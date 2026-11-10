#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Sequence

import n3w_t1_fresh_product_staging_host as staging_host
from n3w_t1_ssh_transport import SSHTransport
from n3w_t1_storage_image_lifecycle import (
    StorageLifecycleError,
    archive_import_worst_case_bytes,
    capacity_report,
    load_policy,
    validate_storage_topology,
)

SCHEMA = "gh.n3w-t1-kf147-fresh-capacity-preflight/1"
POLICY_PATH = Path("infra/n3w-t1/updater-releases/storage-image-lifecycle-policy.json")
EXPECTED_MANAGER_SOURCE_HEAD = "44e7d74727147975de88e85c4b18ba3f7493fd76"
EXPECTED_MANAGER_IMAGE = "local/greenhouse-manager:fresh-44e7d7472714"
EXPECTED_MANAGER_IMAGE_ID = "sha256:fd5104d610645347fe47137dbb24121851fa8a48530df3e3c905704607c5e3d4"
EXPECTED_MANAGER_TAR_SHA256 = "9316817590c4fe74498629d0451a4897c2e11bef7bc4b423b66e47bb846099c5"
EXPECTED_MANAGER_TAR_SIZE_BYTES = 62957568

EXPECTED_LIVE_IMAGES = {
    "manager": "local/greenhouse-manager:fresh-7807271e4c48",
    "homeassistant": "local/n3w-homeassistant:2026.10.0-0c73235a",
    "broker": "local/n3w-mosquitto:2.1.2-3184566d",
}
EXPECTED_LIVE_IMAGE_IDS = {
    "manager": "sha256:7e3f09ed47010a18de215faa426113b7faba4e220b41bb9dcafd8ee1d4acf20b",
    "homeassistant": "sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306",
    "broker": "sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563",
}
EXPECTED_U1_PHASE = "U1_PREPARE_REQUESTED"
EXPECTED_USB_MODEL = "Extreme"
EXPECTED_USB_CAPACITY_BYTES = 32017047552
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

MUTABLE_RUNTIME_PROBE = r"""
import hashlib
import json
import os
import subprocess
from pathlib import Path

PROJECT = "n3wfc4"
SERVICES = ("broker", "manager", "homeassistant")
UNITS = (
    "n3wfc4-broker-activation.service",
    "n3wfc4-services-activation.service",
)
MUTABLE_PATHS = (
    "/var/lib/n3wfc4-homeassistant",
    "/var/lib/greenhouse-manager",
    "/var/lib/n3wfc4-broker",
    "/var/lib/n3w-t1-core-updater",
    "/var/log",
    "/var/cache/apt",
)
TX = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json")
PREPARE = Path("/var/lib/n3w-t1-core-updater/homeassistant-usb-prepare.json")

def run(argv):
    completed = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=120,
    )
    if completed.returncode != 0:
        raise RuntimeError("command_failed:" + Path(argv[0]).name)
    return completed.stdout.strip()

def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def path_allocated(path):
    target = Path(path)
    if not target.exists():
        return 0
    return int(run(["du", "-s", "-x", "-B1", "--", path]).split()[0])

def unit_snapshot():
    result = {}
    for unit in UNITS:
        raw = run([
            "systemctl", "show", unit,
            "--property=ActiveState,SubState,NRestarts,ExecMainStartTimestampMonotonic",
        ])
        record = {}
        for line in raw.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                record[key] = value
        result[unit] = record
    return result

def containers():
    raw = run([
        "docker", "ps", "-a",
        "--filter", "label=com.docker.compose.project=" + PROJECT,
        "--format", '{{.ID}}\t{{.Label "com.docker.compose.service"}}',
    ])
    found = {name: [] for name in SERVICES}
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            raise RuntimeError("container_listing_invalid")
        cid, service = parts
        if service in found:
            found[service].append(cid)
    if any(len(found[name]) != 1 for name in SERVICES):
        raise RuntimeError("container_identity_invalid")

    result = {}
    for service in SERVICES:
        cid = found[service][0]
        doc = json.loads(run(["docker", "container", "inspect", "--size", cid]))
        if not isinstance(doc, list) or len(doc) != 1:
            raise RuntimeError("container_inspect_invalid")
        item = doc[0]
        config = item.get("Config") or {}
        state = item.get("State") or {}
        result[service] = {
            "id": item.get("Id"),
            "image_ref": config.get("Image"),
            "image_id": item.get("Image"),
            "running": state.get("Running"),
            "restart_count": item.get("RestartCount"),
            "started_at": state.get("StartedAt"),
            "size_rw_bytes": item.get("SizeRw"),
        }
    return result

def public_json_state(path, kind):
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(kind + "_missing")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise RuntimeError(kind + "_invalid")
    result = {
        "sha256": sha256_file(path),
        "schema": doc.get("schema"),
        "status": doc.get("status"),
        "phase": doc.get("phase"),
        "confirmation_required": doc.get("confirmation_required"),
        "confirmation_consumed": doc.get("confirmation_consumed"),
    }
    if kind == "prepare":
        candidate = doc.get("candidate")
        if isinstance(candidate, dict):
            result["candidate_model"] = candidate.get("display_model")
            result["candidate_capacity_bytes"] = candidate.get("display_capacity_bytes")
    return result

def stable_containers(snapshot):
    result = {}
    for service in SERVICES:
        item = snapshot[service]
        result[service] = {
            "id": item.get("id"),
            "image_ref": item.get("image_ref"),
            "image_id": item.get("image_id"),
            "running": item.get("running"),
            "restart_count": item.get("restart_count"),
            "started_at": item.get("started_at"),
        }
    return result

before = {
    "units": unit_snapshot(),
    "containers": containers(),
}
mutable_paths = {path: path_allocated(path) for path in MUTABLE_PATHS}
after = {
    "units": unit_snapshot(),
    "containers": containers(),
}
if (
    before["units"] != after["units"]
    or stable_containers(before["containers"]) != stable_containers(after["containers"])
):
    raise RuntimeError("runtime_changed_during_probe")

writable = 0
for record in before["containers"].values():
    value = record.get("size_rw_bytes")
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RuntimeError("container_size_rw_invalid")
    writable += value

print(json.dumps({
    "schema": "gh.n3w-t1-kf147-fresh-capacity-remote/1",
    "runtime_stable": True,
    "units": before["units"],
    "containers": before["containers"],
    "mutable_paths_allocated_bytes": mutable_paths,
    "selected_persistent_and_maintenance_allocated_bytes": sum(mutable_paths.values()),
    "container_writable_layer_allocated_bytes": writable,
    "observed_mutable_allocated_bytes": sum(mutable_paths.values()) + writable,
    "transaction": public_json_state(TX, "transaction"),
    "prepare": public_json_state(PREPARE, "prepare"),
}, sort_keys=True))
"""

STORAGE_RECLAIM_AUDIT_PROBE = r"""
import json
import os
import subprocess
from pathlib import Path

SCHEMA = "gh.n3w-t1-kf147-storage-reclaim-audit/1"
LARGE_FILE_MIN_BYTES = 16 * 1024 * 1024
TOP_PATHS = (
    "/var/lib/containerd",
    "/var/lib/docker",
    "/var/lib",
    "/var/cache",
    "/var/log",
    "/var/tmp",
    "/tmp",
    "/opt",
    "/usr",
    "/home",
    "/root",
    "/boot",
)
CHILD_ROOTS = (
    "/var/lib/containerd",
    "/var/lib/docker",
    "/var/cache",
    "/var/log",
    "/var/tmp",
    "/tmp",
    "/opt",
)
SCAN_ROOTS = ("/var", "/opt", "/usr", "/home", "/root", "/tmp", "/boot")
SKIP_PREFIXES = ("/proc", "/sys", "/dev", "/run")

def run(argv, timeout=180):
    try:
        completed = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "rc": 124,
            "stdout": stdout,
            "stderr": ("timeout:" + stderr)[:500],
        }
    except OSError as error:
        return {
            "rc": 127,
            "stdout": "",
            "stderr": ("command_unavailable:" + type(error).__name__)[:500],
        }
    return {
        "rc": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr[:500],
    }

def du_bytes(path):
    target = Path(path)
    if not target.exists() or target.is_symlink():
        return None
    result = run(["du", "-s", "-x", "-B1", "--", str(target)], timeout=600)
    if result["rc"] != 0:
        return None
    try:
        return int(result["stdout"].split()[0])
    except (IndexError, ValueError):
        return None

def runtime_state():
    containers = run([
        "docker", "ps", "-a", "--no-trunc",
        "--format", "{{.ID}}\\t{{.Image}}\\t{{.State}}",
    ])
    units = {}
    for unit in (
        "n3wfc4-broker-activation.service",
        "n3wfc4-services-activation.service",
    ):
        units[unit] = run([
            "systemctl", "show", unit,
            "--property=ActiveState,SubState,NRestarts,ExecMainStartTimestampMonotonic",
        ])["stdout"]
    return {"containers": containers, "units": units}

def container_inventory():
    listed = run(["docker", "ps", "-aq", "--no-trunc"])
    ids = sorted(set(listed["stdout"].split())) if listed["rc"] == 0 else []
    if not ids:
        return {"records": [], "list": listed}
    inspected = run(["docker", "container", "inspect", "--", *ids], timeout=300)
    records = []
    if inspected["rc"] == 0:
        for item in json.loads(inspected["stdout"]):
            config = item.get("Config") or {}
            state = item.get("State") or {}
            labels = config.get("Labels") or {}
            records.append({
                "id": item.get("Id"),
                "name": item.get("Name"),
                "image_id": item.get("Image"),
                "image_ref": config.get("Image"),
                "running": state.get("Running"),
                "status": state.get("Status"),
                "compose_project": labels.get("com.docker.compose.project"),
                "compose_service": labels.get("com.docker.compose.service"),
            })
    return {"records": records, "list": listed, "inspect_error": inspected["stderr"]}

def image_inventory():
    listed = run(["docker", "image", "ls", "-aq", "--no-trunc"])
    ids = sorted(set(listed["stdout"].split())) if listed["rc"] == 0 else []
    if not ids:
        return {"records": [], "list": listed}
    inspected = run(["docker", "image", "inspect", "--", *ids], timeout=300)
    records = []
    if inspected["rc"] == 0:
        for item in json.loads(inspected["stdout"]):
            rootfs = item.get("RootFS") or {}
            records.append({
                "id": item.get("Id"),
                "repo_tags": item.get("RepoTags") or [],
                "repo_digests": item.get("RepoDigests") or [],
                "created": item.get("Created"),
                "size_bytes": item.get("Size"),
                "virtual_size_bytes": item.get("VirtualSize"),
                "rootfs_layers": rootfs.get("Layers") or [],
            })
    return {"records": records, "list": listed, "inspect_error": inspected["stderr"]}

def volume_inventory():
    listed = run(["docker", "volume", "ls", "-q"])
    names = sorted(set(listed["stdout"].split())) if listed["rc"] == 0 else []
    if not names:
        return {"records": [], "list": listed}
    inspected = run(["docker", "volume", "inspect", "--", *names], timeout=300)
    records = []
    if inspected["rc"] == 0:
        for item in json.loads(inspected["stdout"]):
            mountpoint = item.get("Mountpoint")
            records.append({
                "name": item.get("Name"),
                "driver": item.get("Driver"),
                "mountpoint": mountpoint,
                "allocated_bytes": du_bytes(mountpoint) if mountpoint else None,
            })
    return {"records": records, "list": listed, "inspect_error": inspected["stderr"]}

def directory_usage():
    top = {path: du_bytes(path) for path in TOP_PATHS}
    children = {}
    for root_text in CHILD_ROOTS:
        root = Path(root_text)
        entries = []
        if root.is_dir() and not root.is_symlink():
            try:
                children_snapshot = sorted(root.iterdir(), key=lambda value: value.name)
            except OSError:
                children_snapshot = []
            for child in children_snapshot:
                entries.append({"path": str(child), "allocated_bytes": du_bytes(child)})
        children[root_text] = entries
    return {"top": top, "children": children}

def large_files():
    root_device = os.stat("/").st_dev
    records = []
    for scan_root in SCAN_ROOTS:
        if not Path(scan_root).exists():
            continue
        for current, directories, files in os.walk(scan_root, topdown=True, followlinks=False):
            directories[:] = [
                name for name in directories
                if not os.path.islink(os.path.join(current, name))
                and not os.path.join(current, name).startswith(SKIP_PREFIXES)
            ]
            try:
                if os.stat(current, follow_symlinks=False).st_dev != root_device:
                    directories[:] = []
                    continue
            except OSError:
                directories[:] = []
                continue
            for name in files:
                path = os.path.join(current, name)
                try:
                    info = os.stat(path, follow_symlinks=False)
                except OSError:
                    continue
                if info.st_dev == root_device and info.st_size >= LARGE_FILE_MIN_BYTES:
                    records.append({"path": path, "size_bytes": info.st_size})
    return sorted(records, key=lambda item: (-item["size_bytes"], item["path"]))[:200]

before = runtime_state()
document = {
    "schema": SCHEMA,
    "read_only": True,
    "mutation": False,
    "containers": container_inventory(),
    "images": image_inventory(),
    "volumes": volume_inventory(),
    "docker_system_df_verbose": run(["docker", "system", "df", "-v"], timeout=300),
    "containerd_namespaces": run(["ctr", "namespaces", "list", "-q"]),
    "journal_disk_usage": run(["journalctl", "--disk-usage"]),
    "directory_usage": directory_usage(),
    "large_files": large_files(),
}
after = runtime_state()
if before != after:
    raise RuntimeError("runtime_changed_during_reclaim_audit")
document["runtime_stable"] = True
print(json.dumps(document, sort_keys=True))
"""


class CapacityPreflightError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_output(value: str, reason: str) -> dict[str, Any]:
    try:
        document = json.loads(value)
    except json.JSONDecodeError as error:
        raise CapacityPreflightError(reason) from error
    if not isinstance(document, dict):
        raise CapacityPreflightError(reason)
    return document


def candidate_material(manager_tar: Path) -> dict[str, Any]:
    if manager_tar.is_symlink() or not manager_tar.is_file():
        raise CapacityPreflightError("manager_tar_invalid")
    size = manager_tar.stat().st_size
    digest = _sha256_file(manager_tar)
    if size != EXPECTED_MANAGER_TAR_SIZE_BYTES:
        raise CapacityPreflightError("manager_tar_size_mismatch")
    if digest != EXPECTED_MANAGER_TAR_SHA256:
        raise CapacityPreflightError("manager_tar_sha256_mismatch")
    try:
        import_bytes = archive_import_worst_case_bytes(manager_tar)
    except StorageLifecycleError as error:
        raise CapacityPreflightError(str(error)) from error
    return {
        "manager_source_head": EXPECTED_MANAGER_SOURCE_HEAD,
        "target_manager_image": EXPECTED_MANAGER_IMAGE,
        "target_manager_image_id": EXPECTED_MANAGER_IMAGE_ID,
        "manager_tar_sha256": digest,
        "manager_tar_size_bytes": size,
        "staged_transport_bytes": size,
        "image_import_worst_case_bytes": import_bytes,
        "persistent_control_source_staged": False,
    }


def validate_live_baseline(remote: dict[str, Any]) -> dict[str, Any]:
    if remote.get("schema") != "gh.n3w-t1-kf147-fresh-capacity-remote/1":
        raise CapacityPreflightError("remote_schema_invalid")
    if remote.get("runtime_stable") is not True:
        raise CapacityPreflightError("runtime_unstable")

    units = remote.get("units")
    if not isinstance(units, dict):
        raise CapacityPreflightError("units_invalid")
    for name in (
        "n3wfc4-broker-activation.service",
        "n3wfc4-services-activation.service",
    ):
        item = units.get(name)
        if not isinstance(item, dict) or item.get("ActiveState") != "active":
            raise CapacityPreflightError("service_not_active")

    containers = remote.get("containers")
    if not isinstance(containers, dict) or set(containers) != {
        "broker",
        "manager",
        "homeassistant",
    }:
        raise CapacityPreflightError("containers_invalid")
    for component, expected_ref in EXPECTED_LIVE_IMAGES.items():
        item = containers.get(component)
        if not isinstance(item, dict):
            raise CapacityPreflightError("container_invalid")
        if item.get("running") is not True:
            raise CapacityPreflightError("container_not_running")
        if item.get("image_ref") != expected_ref:
            raise CapacityPreflightError(f"live_image_ref_drift:{component}")
        if item.get("image_id") != EXPECTED_LIVE_IMAGE_IDS[component]:
            raise CapacityPreflightError(f"live_image_id_drift:{component}")

    mutable = remote.get("observed_mutable_allocated_bytes")
    if not isinstance(mutable, int) or isinstance(mutable, bool) or mutable < 0:
        raise CapacityPreflightError("mutable_allocated_invalid")

    transaction = remote.get("transaction")
    prepare = remote.get("prepare")
    if not isinstance(transaction, dict) or not isinstance(prepare, dict):
        raise CapacityPreflightError("u1_state_invalid")
    if transaction.get("phase") != EXPECTED_U1_PHASE:
        raise CapacityPreflightError("u1_phase_drift")
    if prepare.get("candidate_model") != EXPECTED_USB_MODEL:
        raise CapacityPreflightError("usb_candidate_model_drift")
    if prepare.get("candidate_capacity_bytes") != EXPECTED_USB_CAPACITY_BYTES:
        raise CapacityPreflightError("usb_candidate_capacity_drift")
    if prepare.get("confirmation_required") is not True:
        raise CapacityPreflightError("usb_confirmation_not_required")
    if prepare.get("confirmation_consumed") is not False:
        raise CapacityPreflightError("usb_confirmation_already_consumed")
    for record in (transaction, prepare):
        digest = record.get("sha256")
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            raise CapacityPreflightError("u1_state_sha256_invalid")

    return {
        "observed_mutable_allocated_bytes": mutable,
        "transaction_sha256": transaction["sha256"],
        "prepare_sha256": prepare["sha256"],
        "u1_phase": transaction.get("phase"),
        "usb_candidate_model": prepare.get("candidate_model"),
        "usb_candidate_capacity_bytes": prepare.get("candidate_capacity_bytes"),
        "confirmation_required": True,
        "confirmation_consumed": False,
    }


def evaluate(
    *,
    manager_tar: Path,
    storage_report: dict[str, Any],
    remote_report: dict[str, Any],
    policy_path: Path = POLICY_PATH,
) -> dict[str, Any]:
    try:
        policy = load_policy(policy_path)
        topology = validate_storage_topology(storage_report)
    except StorageLifecycleError as error:
        raise CapacityPreflightError(str(error)) from error

    candidate = candidate_material(manager_tar)
    live = validate_live_baseline(remote_report)

    total = storage_report.get("staging_total_bytes")
    if not isinstance(total, int) or isinstance(total, bool) or total <= 0:
        raise CapacityPreflightError("staging_total_bytes_invalid")

    report = capacity_report(
        filesystem_total_bytes=total,
        free_bytes=topology["free_bytes"],
        observed_mutable_allocated_bytes=live["observed_mutable_allocated_bytes"],
        staged_transport_bytes=candidate["staged_transport_bytes"],
        image_import_worst_case_bytes=candidate["image_import_worst_case_bytes"],
        policy=policy,
    )
    return {
        "schema": SCHEMA,
        "status": "PASS" if report["capacity_pass"] else "STOP",
        "operation": "kf147_fresh_capacity_preflight",
        "mutation": False,
        "remote_staging": False,
        "manager_tar_streamed_to_t1": False,
        "candidate": candidate,
        "storage_topology": topology,
        "live_baseline": live,
        "capacity": report,
        "next_action": (
            "NEW_PACKAGE_MANIFEST_BINDING"
            if report["capacity_pass"]
            else "STOP_CAPACITY_INSUFFICIENT"
        ),
    }


def probe_t1(
    *,
    target: str,
    known_hosts: Path,
    expected_host_key_sha256: str,
    collect_reclaim_audit: bool = False,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    transport = SSHTransport(
        target=target,
        known_hosts=known_hosts,
        expected_host_key_sha256=expected_host_key_sha256,
    )
    transport.start_epoch()
    try:
        storage = _json_output(
            transport.run_remote(
                ["sudo", "-n", "python3", "-c", staging_host._remote_storage_probe_script()],
                timeout=120,
            ).stdout,
            "storage_report_invalid",
        )
        stage_root = storage.get("staging_root")
        if stage_root != "/var/tmp":
            raise CapacityPreflightError("staging_root_invalid")
        total_raw = transport.run_remote(
            ["python3", "-c", "import shutil; print(shutil.disk_usage('/var/tmp').total)"],
            timeout=30,
        ).stdout.strip()
        try:
            storage["staging_total_bytes"] = int(total_raw)
        except ValueError as error:
            raise CapacityPreflightError("staging_total_bytes_invalid") from error

        remote = _json_output(
            transport.run_remote(
                ["sudo", "-n", "python3", "-c", MUTABLE_RUNTIME_PROBE],
                timeout=300,
            ).stdout,
            "remote_report_invalid",
        )
        reclaim_audit = None
        if collect_reclaim_audit:
            reclaim_audit = _json_output(
                transport.run_remote(
                    ["sudo", "-n", "python3", "-c", STORAGE_RECLAIM_AUDIT_PROBE],
                    timeout=1200,
                ).stdout,
                "storage_reclaim_audit_invalid",
            )
            if (
                reclaim_audit.get("schema")
                != "gh.n3w-t1-kf147-storage-reclaim-audit/1"
                or reclaim_audit.get("read_only") is not True
                or reclaim_audit.get("mutation") is not False
                or reclaim_audit.get("runtime_stable") is not True
            ):
                raise CapacityPreflightError("storage_reclaim_audit_invalid")
        return storage, remote, reclaim_audit
    finally:
        transport.close_epoch()


def _private_evidence_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if root.exists():
        if root.is_symlink() or not root.is_dir() or any(root.iterdir()):
            raise CapacityPreflightError("evidence_root_invalid")
    else:
        root.mkdir(parents=True, mode=0o700)
    os.chmod(root, 0o700)
    return root


def _write_private(path: Path, value: Any) -> None:
    data = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        os.write(descriptor, data)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="n3w-t1-kf147-fresh-capacity")
    command.add_argument("--manager-tar", type=Path, required=True)
    command.add_argument("--t1-ssh-target", required=True)
    command.add_argument("--known-hosts", type=Path, required=True)
    command.add_argument("--expected-host-key-sha256", required=True)
    command.add_argument("--evidence-root", type=Path, required=True)
    command.add_argument("--reclaim-audit-on-stop", action="store_true")
    return command


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root: Path | None = None
    try:
        root = _private_evidence_root(args.evidence_root)
        storage, remote, reclaim_audit = probe_t1(
            target=args.t1_ssh_target,
            known_hosts=args.known_hosts,
            expected_host_key_sha256=args.expected_host_key_sha256,
            collect_reclaim_audit=args.reclaim_audit_on_stop,
        )
        result = evaluate(
            manager_tar=args.manager_tar,
            storage_report=storage,
            remote_report=remote,
        )
        _write_private(root / "storage-report.json", storage)
        _write_private(root / "runtime-mutable-report.json", remote)
        if reclaim_audit is not None and result["status"] == "STOP":
            _write_private(root / "storage-reclaim-audit.json", reclaim_audit)
        _write_private(root / "capacity-result.json", result)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "PASS" else 2
    except Exception as error:
        reason = str(error)
        if (
            not reason
            or len(reason) > 180
            or "/" in reason
            or "\\" in reason
            or "@" in reason
        ):
            reason = type(error).__name__
        result = {
            "schema": SCHEMA,
            "status": "STOP",
            "operation": "kf147_fresh_capacity_preflight",
            "mutation": False,
            "remote_staging": False,
            "manager_tar_streamed_to_t1": False,
            "reason": reason,
        }
        if root is not None:
            try:
                _write_private(root / "capacity-stop.json", result)
            except Exception:
                pass
        print(json.dumps(result, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
