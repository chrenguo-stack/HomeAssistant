#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

REPOSITORY = "chrenguo-stack/HomeAssistant"
REMOTE_STAGING_ROOT = "/var/tmp"
TRANSPORT_SCHEMA = "gh.n3w-t1-fresh-transport/2"
CAPACITY_SCHEMA = "gh.n3w-t1-fresh-capacity/1"
MIN_POST_PEAK_FREE_BYTES = 5 * 1024 * 1024 * 1024
IMAGE_LABELS = ("homeassistant", "manager", "broker")
AUTHORIZATION_LEDGER_ROOT = "/var/lib/n3w-fresh-bootstrap-authorizations"
IMAGE_ARTIFACT_FILES = {
    "homeassistant": "homeassistant-arm64.tar",
    "manager": "greenhouse-manager-arm64.tar",
    "broker": "broker-arm64.tar",
}
ARTIFACT_OUTER_FILES = frozenset(
    (
        "executor.sha256",
        "host-wrapper.py",
        "host-wrapper.sha256",
        "host-baseline.py",
        "host-baseline.sha256",
        "runtime-payload.sha256",
        "runtime-payload.tar.gz",
        "payload-manifest.sha256",
        "capacity-contract.json",
        "capacity-contract.sha256",
        *IMAGE_ARTIFACT_FILES.values(),
    )
)


class FreshHostTransportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TransportPlan:
    runtime_archive_size_bytes: int
    runtime_payload_uncompressed_bytes: int
    runtime_extraction_peak_bytes: int
    worst_image_required_free_bytes: int
    minimum_post_peak_free_bytes: int
    remote_free_bytes: int
    image_load_order: tuple[str, ...]
    remote_staged_image_count_max: int
    capacity_pass: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(
    command: Sequence[str],
    *,
    timeout: float | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        tuple(command),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        reason = completed.stderr.strip() or completed.stdout.strip()
        raise FreshHostTransportError(
            f"command_failed:{command[0]}:{completed.returncode}:{reason[:500]}"
        )
    return completed


def _remote_command(parts: Sequence[str]) -> str:
    return " ".join(shlex.quote(part) for part in parts)


def _artifact_metadata(
    *,
    run_id: str,
    artifact_name: str,
    artifact_id: int,
    artifact_zip_sha256: str,
) -> dict[str, object]:
    completed = _run(
        (
            "gh",
            "api",
            f"repos/{REPOSITORY}/actions/artifacts/{artifact_id}",
        ),
        timeout=60,
    )
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise FreshHostTransportError("artifact_metadata_invalid") from error
    workflow_run = document.get("workflow_run")
    if (
        document.get("id") != artifact_id
        or document.get("name") != artifact_name
        or document.get("expired") is not False
        or document.get("digest") != f"sha256:{artifact_zip_sha256}"
        or not isinstance(workflow_run, dict)
        or str(workflow_run.get("id")) != str(run_id)
    ):
        raise FreshHostTransportError("artifact_metadata_binding_invalid")
    return document


def _safe_extract_artifact_zip(
    archive: Path,
    destination: Path,
) -> None:
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        names = {item.filename for item in infos}
        if names != ARTIFACT_OUTER_FILES:
            raise FreshHostTransportError("artifact_outer_file_set_invalid")
        for item in infos:
            path = Path(item.filename)
            mode = (item.external_attr >> 16) & 0o170000
            if (
                path.is_absolute()
                or len(path.parts) != 1
                or item.is_dir()
                or mode == 0o120000
            ):
                raise FreshHostTransportError("artifact_zip_member_unsafe")
            with bundle.open(item) as source:
                with (destination / item.filename).open("wb") as target:
                    while True:
                        block = source.read(1024 * 1024)
                        if not block:
                            break
                        target.write(block)


def _download_artifact(
    work: Path,
    *,
    run_id: str,
    artifact_name: str,
    artifact_id: int,
    artifact_zip_sha256: str,
) -> None:
    _artifact_metadata(
        run_id=run_id,
        artifact_name=artifact_name,
        artifact_id=artifact_id,
        artifact_zip_sha256=artifact_zip_sha256,
    )
    try:
        _run(
            (
                "gh",
                "run",
                "download",
                run_id,
                "-R",
                REPOSITORY,
                "-n",
                artifact_name,
                "-D",
                str(work),
            ),
            timeout=900,
        )
        return
    except (
        FreshHostTransportError,
        OSError,
        subprocess.TimeoutExpired,
    ):
        pass

    token = _run(("gh", "auth", "token"), timeout=30).stdout.strip()
    if not token:
        raise FreshHostTransportError("github_token_unavailable")
    headers = work.parent / f"{work.name}.headers"
    archive = work.parent / f"{work.name}.artifact.zip"
    try:
        _run(
            (
                "curl",
                "-sS",
                "-D",
                str(headers),
                "-o",
                "/dev/null",
                "-H",
                f"Authorization: Bearer {token}",
                "-H",
                "Accept: application/vnd.github+json",
                "-H",
                "X-GitHub-Api-Version: 2022-11-28",
                f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{artifact_id}/zip",
            ),
            timeout=60,
        )
        location = ""
        for line in headers.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines():
            if line.lower().startswith("location:"):
                location = line.split(":", 1)[1].strip()
                break
        if not location.startswith("https://"):
            raise FreshHostTransportError("artifact_redirect_missing")
        _run(
            (
                "curl",
                "-4",
                "-fL",
                "--http1.1",
                "--retry",
                "3",
                "--connect-timeout",
                "20",
                "--speed-time",
                "90",
                "--speed-limit",
                "1024",
                "-o",
                str(archive),
                location,
            ),
            timeout=1800,
        )
        if _sha256_file(archive) != artifact_zip_sha256:
            raise FreshHostTransportError("artifact_zip_sha256_mismatch")
        _safe_extract_artifact_zip(archive, work)
    finally:
        headers.unlink(missing_ok=True)
        archive.unlink(missing_ok=True)


def _read_sidecar(path: Path) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise FreshHostTransportError(f"sha256_sidecar_invalid:{path.name}")
    return value


def _verify_outer_artifact(
    work: Path,
    *,
    archive_sha256: str,
    manifest_sha256: str,
) -> Path:
    actual = {path.name for path in work.iterdir()}
    if actual != ARTIFACT_OUTER_FILES:
        raise FreshHostTransportError("artifact_outer_file_set_invalid")

    archive = work / "runtime-payload.tar.gz"
    actual_archive_sha = _sha256_file(archive)
    if actual_archive_sha != archive_sha256:
        raise FreshHostTransportError("runtime_payload_sha256_mismatch")
    if _read_sidecar(work / "runtime-payload.sha256") != actual_archive_sha:
        raise FreshHostTransportError("runtime_payload_sidecar_mismatch")
    if _read_sidecar(work / "payload-manifest.sha256") != manifest_sha256:
        raise FreshHostTransportError("payload_manifest_sidecar_mismatch")
    capacity = work / "capacity-contract.json"
    if _read_sidecar(work / "capacity-contract.sha256") != _sha256_file(capacity):
        raise FreshHostTransportError("capacity_contract_sidecar_mismatch")

    downloaded_wrapper = work / "host-wrapper.py"
    wrapper_sha = _sha256_file(downloaded_wrapper)
    if _read_sidecar(work / "host-wrapper.sha256") != wrapper_sha:
        raise FreshHostTransportError("host_wrapper_sidecar_mismatch")
    baseline = work / "host-baseline.py"
    baseline_sha = _sha256_file(baseline)
    if _read_sidecar(work / "host-baseline.sha256") != baseline_sha:
        raise FreshHostTransportError("host_baseline_sidecar_mismatch")
    current = Path(__file__).resolve()
    if current.is_file() and _sha256_file(current) != wrapper_sha:
        raise FreshHostTransportError("running_host_wrapper_not_exact_artifact_copy")
    return archive


def _normalized_member_name(name: str) -> str:
    while name.startswith("./"):
        name = name[2:]
    return name


def _read_payload_manifest(
    archive: Path,
    *,
    manifest_sha256: str,
) -> dict[str, Any]:
    matches = []
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle:
            name = _normalized_member_name(member.name)
            if not name:
                continue
            candidate = Path(name)
            if candidate.is_absolute() or ".." in candidate.parts:
                raise FreshHostTransportError("payload_member_path_unsafe")
            if member.issym() or member.islnk():
                raise FreshHostTransportError("payload_link_member_forbidden")
            if not (member.isfile() or member.isdir()):
                raise FreshHostTransportError("payload_special_member_forbidden")
            if name == "payload-manifest.json":
                if not member.isfile():
                    raise FreshHostTransportError("payload_manifest_not_regular")
                matches.append(member)
        if len(matches) != 1:
            raise FreshHostTransportError("payload_manifest_member_count_invalid")
        stream = bundle.extractfile(matches[0])
        if stream is None:
            raise FreshHostTransportError("payload_manifest_unreadable")
        payload = stream.read(4 * 1024 * 1024 + 1)
    if len(payload) > 4 * 1024 * 1024:
        raise FreshHostTransportError("payload_manifest_too_large")
    if hashlib.sha256(payload).hexdigest() != manifest_sha256:
        raise FreshHostTransportError("payload_manifest_sha256_mismatch")
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise FreshHostTransportError("payload_manifest_invalid") from error
    if not isinstance(document, dict):
        raise FreshHostTransportError("payload_manifest_invalid")
    return document


def _capacity_contract(
    work: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    path = work / "capacity-contract.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FreshHostTransportError("capacity_contract_invalid") from error
    if (
        not isinstance(document, dict)
        or document.get("schema") != CAPACITY_SCHEMA
        or document.get("source_head") != manifest.get("source_head")
        or document.get("minimum_post_peak_free_bytes")
        != MIN_POST_PEAK_FREE_BYTES
        or document.get("image_load_order") != list(IMAGE_LABELS)
    ):
        raise FreshHostTransportError("capacity_contract_binding_invalid")
    images = document.get("images")
    if not isinstance(images, dict) or set(images) != set(IMAGE_LABELS):
        raise FreshHostTransportError("capacity_contract_images_invalid")
    return document


def _transport_contract(
    manifest: dict[str, Any],
    capacity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    transport = manifest.get("transport")
    if not isinstance(transport, dict) or transport.get("schema") != TRANSPORT_SCHEMA:
        raise FreshHostTransportError("transport_contract_missing")
    if transport.get("remote_staging_root") != REMOTE_STAGING_ROOT:
        raise FreshHostTransportError("transport_staging_root_invalid")
    if transport.get("minimum_post_peak_free_bytes") != MIN_POST_PEAK_FREE_BYTES:
        raise FreshHostTransportError("transport_reserve_invalid")

    order = transport.get("image_load_order")
    images = transport.get("images")
    runtime_bytes = transport.get("runtime_payload_uncompressed_bytes")
    if order != list(IMAGE_LABELS) or not isinstance(images, dict):
        raise FreshHostTransportError("transport_image_order_invalid")
    if (
        not isinstance(runtime_bytes, int)
        or isinstance(runtime_bytes, bool)
        or runtime_bytes <= 0
    ):
        raise FreshHostTransportError("transport_runtime_payload_size_invalid")

    for label in IMAGE_LABELS:
        record = images.get(label)
        manifest_record = manifest.get("images", {}).get(label)
        if not isinstance(record, dict) or not isinstance(manifest_record, dict):
            raise FreshHostTransportError(f"transport_image_missing:{label}")
        path = record.get("path")
        artifact_file = record.get("artifact_file")
        tar_size = record.get("tar_size_bytes")
        loaded_size = record.get("loaded_size_bytes")
        required_free = record.get("required_free_bytes")
        image_ref = record.get("image_ref")
        tar_sha = record.get("tar_sha256")
        if (
            not isinstance(path, str)
            or not path.startswith("incoming/")
            or artifact_file != IMAGE_ARTIFACT_FILES[label]
            or not isinstance(tar_size, int)
            or isinstance(tar_size, bool)
            or tar_size <= 0
            or not isinstance(loaded_size, int)
            or isinstance(loaded_size, bool)
            or loaded_size <= 0
            or not isinstance(required_free, int)
            or isinstance(required_free, bool)
            or required_free != tar_size + loaded_size + MIN_POST_PEAK_FREE_BYTES
            or not isinstance(image_ref, str)
            or not image_ref
            or not isinstance(tar_sha, str)
            or len(tar_sha) != 64
            or manifest_record.get("artifact_file") != artifact_file
            or manifest_record.get("path") != path
            or manifest_record.get("tar_size_bytes") != tar_size
            or manifest_record.get("loaded_size_bytes") != loaded_size
            or manifest_record.get("required_free_bytes") != required_free
            or manifest_record.get("tar_sha256") != tar_sha
        ):
            raise FreshHostTransportError(f"transport_image_metadata_invalid:{label}")
        if capacity is not None and capacity["images"].get(label) != record:
            raise FreshHostTransportError(f"capacity_image_binding_invalid:{label}")
    return transport


def _verify_image_artifacts(
    work: Path,
    manifest: dict[str, Any],
    capacity: dict[str, Any],
) -> None:
    transport = _transport_contract(manifest, capacity)
    for label in IMAGE_LABELS:
        record = transport["images"][label]
        path = work / str(record["artifact_file"])
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size != int(record["tar_size_bytes"])
            or _sha256_file(path) != record["tar_sha256"]
        ):
            raise FreshHostTransportError(f"image_artifact_binding_invalid:{label}")


def _plan_transport(
    manifest: dict[str, Any],
    *,
    archive_size_bytes: int,
    remote_free_bytes: int,
    capacity: dict[str, Any] | None = None,
) -> TransportPlan:
    transport = _transport_contract(manifest, capacity)
    runtime_bytes = int(transport["runtime_payload_uncompressed_bytes"])
    extraction_peak = archive_size_bytes + runtime_bytes
    worst_image_required = max(
        int(transport["images"][label]["required_free_bytes"])
        for label in IMAGE_LABELS
    )
    required = max(
        extraction_peak + MIN_POST_PEAK_FREE_BYTES,
        worst_image_required,
    )
    return TransportPlan(
        runtime_archive_size_bytes=archive_size_bytes,
        runtime_payload_uncompressed_bytes=runtime_bytes,
        runtime_extraction_peak_bytes=extraction_peak,
        worst_image_required_free_bytes=worst_image_required,
        minimum_post_peak_free_bytes=MIN_POST_PEAK_FREE_BYTES,
        remote_free_bytes=remote_free_bytes,
        image_load_order=IMAGE_LABELS,
        remote_staged_image_count_max=1,
        capacity_pass=remote_free_bytes >= required,
    )


def _remote_storage_probe_script() -> str:
    return """\
import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

stage = "/var/tmp"

def run_text(argv):
    return subprocess.check_output(argv, text=True).strip()

def process_argv(pid):
    if pid <= 0:
        raise RuntimeError("process_pid_invalid")
    raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    return [part.decode() for part in raw.split(b"\\0") if part]

def option_value(argv, names):
    for index, token in enumerate(argv):
        for name in names:
            if token == name and index + 1 < len(argv):
                return argv[index + 1]
            prefix = name + "="
            if token.startswith(prefix):
                return token[len(prefix):]
    return None

def feature_value(argv, name):
    values = []
    for index, token in enumerate(argv):
        if token == "--feature" and index + 1 < len(argv):
            values.append(argv[index + 1])
        elif token.startswith("--feature="):
            values.append(token.split("=", 1)[1])
    for value in values:
        if value in {name, name + "=true"}:
            return True
        if value == name + "=false":
            return False
    return None

info = json.loads(run_text(["docker", "info", "--format", "{{json .}}"]))
docker_root = info.get("DockerRootDir")
if not isinstance(docker_root, str) or not docker_root.startswith("/"):
    raise RuntimeError("docker_root_invalid")

driver_status = info.get("DriverStatus")
containerd_store = False
if isinstance(driver_status, list):
    containerd_store = any(
        isinstance(row, list)
        and len(row) >= 2
        and row[0] == "driver-type"
        and row[1] == "io.containerd.snapshotter.v1"
        for row in driver_status
    )

dockerd_pid = int(run_text([
    "systemctl", "show", "docker", "--property=MainPID", "--value"
]))
dockerd_argv = process_argv(dockerd_pid)
daemon_path = Path("/etc/docker/daemon.json")
daemon = {}
if daemon_path.is_file():
    daemon = json.loads(daemon_path.read_text(encoding="utf-8"))
if not isinstance(daemon, dict):
    raise RuntimeError("docker_daemon_config_invalid")

features = daemon.get("features")
embedded_config = (
    isinstance(features, dict)
    and features.get("embedded-containerd") is True
)
embedded_flag = feature_value(dockerd_argv, "embedded-containerd")
embedded = embedded_flag if embedded_flag is not None else embedded_config

containerd_address = None
containerd_config_path = None

if not containerd_store:
    image_store_backend = "classic"
    image_store_root = docker_root
    image_store_root_source = "docker_root"
elif embedded:
    image_store_backend = "containerd"
    image_store_root = os.path.join(docker_root, "containerd", "daemon")
    image_store_root_source = "embedded_containerd"
else:
    image_store_backend = "containerd"
    containerd_pid = int(run_text([
        "systemctl", "show", "containerd", "--property=MainPID", "--value"
    ]))
    if containerd_pid <= 0:
        raise RuntimeError("containerd_service_not_running")
    containerd_argv = process_argv(containerd_pid)
    root_flag = option_value(containerd_argv, ("--root", "-r"))
    config_flag = option_value(containerd_argv, ("--config", "-c"))
    containerd_config_path = config_flag or "/etc/containerd/config.toml"
    config = {}
    config_path = Path(containerd_config_path)
    if config_path.is_file():
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise RuntimeError("containerd_config_invalid")
    config_imports = config.get("imports")
    if config_imports not in (None, []):
        raise RuntimeError("containerd_imports_unsupported")

    configured_root = config.get("root")
    if root_flag:
        image_store_root = root_flag
        image_store_root_source = "containerd_cli_root"
    elif isinstance(configured_root, str) and configured_root:
        image_store_root = configured_root
        image_store_root_source = "containerd_config_root"
    else:
        image_store_root = "/var/lib/containerd"
        image_store_root_source = "containerd_default_root"

    grpc = config.get("grpc")
    configured_address = grpc.get("address") if isinstance(grpc, dict) else None
    containerd_address = (
        option_value(containerd_argv, ("--address", "-a"))
        or configured_address
        or "/run/containerd/containerd.sock"
    )
    docker_containerd_address = (
        option_value(dockerd_argv, ("--containerd",))
        or daemon.get("containerd")
        or "/run/containerd/containerd.sock"
    )
    if not (
        isinstance(containerd_address, str)
        and isinstance(docker_containerd_address, str)
        and os.path.realpath(containerd_address)
        == os.path.realpath(docker_containerd_address)
    ):
        raise RuntimeError("containerd_address_mismatch")

image_store_root = os.path.realpath(image_store_root)
docker_root = os.path.realpath(docker_root)
if not image_store_root.startswith("/") or not os.path.isdir(image_store_root):
    raise RuntimeError("image_store_root_unresolved")
if not os.path.isdir(docker_root):
    raise RuntimeError("docker_root_unresolved")

stage_stat = os.stat(stage)
docker_stat = os.stat(docker_root)
image_store_stat = os.stat(image_store_root)
stage_fs = run_text(["findmnt", "-n", "-o", "FSTYPE", "--target", stage])
image_store_fs = run_text([
    "findmnt", "-n", "-o", "FSTYPE", "--target", image_store_root
])

print(json.dumps({
    "staging_root": stage,
    "docker_root": docker_root,
    "image_store_backend": image_store_backend,
    "image_store_root": image_store_root,
    "image_store_root_source": image_store_root_source,
    "containerd_address": containerd_address,
    "containerd_config_path": containerd_config_path,
    "staging_device": stage_stat.st_dev,
    "docker_device": docker_stat.st_dev,
    "image_store_device": image_store_stat.st_dev,
    "staging_free_bytes": shutil.disk_usage(stage).free,
    "docker_free_bytes": shutil.disk_usage(docker_root).free,
    "image_store_free_bytes": shutil.disk_usage(image_store_root).free,
    "staging_fstype": stage_fs,
    "image_store_fstype": image_store_fs,
}, sort_keys=True))
"""


def _remote_storage_report(t1: str) -> dict[str, object]:
    completed = _run(
        (
            "ssh",
            "-n",
            t1,
            _remote_command(
                ("python3", "-c", _remote_storage_probe_script())
            ),
        ),
        timeout=60,
    )
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise FreshHostTransportError("remote_storage_report_invalid") from error
    if not isinstance(report, dict):
        raise FreshHostTransportError("remote_storage_report_invalid")
    if report.get("staging_root") != REMOTE_STAGING_ROOT:
        raise FreshHostTransportError("remote_staging_root_invalid")
    if report.get("staging_fstype") in {"tmpfs", "ramfs"}:
        raise FreshHostTransportError("remote_staging_root_is_memory_filesystem")
    if report.get("image_store_backend") not in {"classic", "containerd"}:
        raise FreshHostTransportError("image_store_backend_unresolved")
    image_store_root = report.get("image_store_root")
    if not isinstance(image_store_root, str) or not image_store_root.startswith("/"):
        raise FreshHostTransportError("image_store_root_unresolved")
    if report.get("image_store_backend") == "containerd":
        if report.get("image_store_root_source") not in {
            "embedded_containerd",
            "containerd_cli_root",
            "containerd_config_root",
            "containerd_default_root",
        }:
            raise FreshHostTransportError("containerd_root_authority_unresolved")
    if not (
        report.get("staging_device")
        == report.get("docker_device")
        == report.get("image_store_device")
    ):
        raise FreshHostTransportError(
            "staging_docker_image_store_filesystems_differ"
        )
    for key in (
        "staging_free_bytes",
        "docker_free_bytes",
        "image_store_free_bytes",
    ):
        free = report.get(key)
        if not isinstance(free, int) or isinstance(free, bool) or free <= 0:
            raise FreshHostTransportError("remote_free_bytes_invalid")
    return report


def _remote_mktemp(t1: str, prefix: str) -> str:
    command = _remote_command(("mktemp", "-d", f"{REMOTE_STAGING_ROOT}/{prefix}.XXXXXX"))
    completed = _run(("ssh", "-n", t1, command), timeout=60)
    path = completed.stdout.strip()
    if not path.startswith(f"{REMOTE_STAGING_ROOT}/{prefix}."):
        raise FreshHostTransportError("remote_temp_path_invalid")
    return path


def _remote_payload_extract_script() -> str:
    return """\
import hashlib
import sys
import tarfile
from pathlib import Path

root = Path(sys.argv[1])
archive = root / "runtime-payload.tar.gz"

def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

if sha(archive) != sys.argv[2]:
    raise RuntimeError("payload_archive_sha256_mismatch")

with tarfile.open(archive, "r:gz") as bundle:
    members = bundle.getmembers()
    for member in members:
        path = Path(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError("payload_member_path_unsafe")
        if member.issym() or member.islnk():
            raise RuntimeError("payload_link_member_forbidden")
        if not (member.isfile() or member.isdir()):
            raise RuntimeError("payload_special_member_forbidden")
    bundle.extractall(root, members=members)

archive.unlink()
if sha(root / "payload-manifest.json") != sys.argv[3]:
    raise RuntimeError("payload_manifest_sha256_mismatch")
"""


def _remote_prepare_payload(
    t1: str,
    remote_dir: str,
    archive: Path,
    *,
    archive_sha256: str,
    manifest_sha256: str,
) -> None:
    _run(("scp", str(archive), f"{t1}:{remote_dir}/runtime-payload.tar.gz"), timeout=900)
    script = _remote_payload_extract_script()
    command = _remote_command(
        ("python3", "-c", script, remote_dir, archive_sha256, manifest_sha256)
    )
    _run(("ssh", "-n", t1, command), timeout=600)


def _remote_free_bytes(t1: str) -> int:
    report = _remote_storage_report(t1)
    return min(
        int(report["staging_free_bytes"]),
        int(report["docker_free_bytes"]),
        int(report["image_store_free_bytes"]),
    )


def _transfer_requested_image(
    t1: str,
    remote_dir: str,
    work: Path,
    manifest: dict[str, Any],
    capacity: dict[str, Any],
    label: str,
) -> None:
    if label not in IMAGE_LABELS:
        raise FreshHostTransportError("image_request_label_invalid")
    transport = _transport_contract(manifest, capacity)
    record = transport["images"][label]
    free_before = _remote_free_bytes(t1)
    if free_before < int(record["required_free_bytes"]):
        raise FreshHostTransportError(f"remote_capacity_insufficient:{label}")
    relative = str(record["path"])
    remote_tar = f"{remote_dir}/{relative}"
    local_tar = work / str(record["artifact_file"])
    parent = str(Path(remote_tar).parent)
    _run(
        (
            "ssh",
            "-n",
            t1,
            _remote_command(("mkdir", "-p", "--", parent)),
        ),
        timeout=60,
    )
    absent = _run(
        (
            "ssh",
            "-n",
            t1,
            _remote_command(("test", "!", "-e", remote_tar)),
        ),
        timeout=30,
        check=False,
    )
    if absent.returncode != 0:
        raise FreshHostTransportError(f"remote_image_tar_already_present:{label}")
    _run(("scp", str(local_tar), f"{t1}:{remote_tar}"), timeout=1800)
    verify_script = (
        "import hashlib,os,sys;"
        "p=sys.argv[1];e=sys.argv[2];n=int(sys.argv[3]);"
        "h=hashlib.sha256();"
        "f=open(p,'rb');"
        "\nwhile True:"
        "\n b=f.read(1048576);"
        "\n if not b: break;"
        "\n h.update(b);"
        "\nf.close();"
        "\nassert os.path.getsize(p)==n;"
        "\nassert h.hexdigest()==e"
    )
    _run(
        (
            "ssh",
            "-n",
            t1,
            _remote_command(
                (
                    "python3",
                    "-c",
                    verify_script,
                    remote_tar,
                    str(record["tar_sha256"]),
                    str(record["tar_size_bytes"]),
                )
            ),
        ),
        timeout=600,
    )


def _remote_baseline_report(
    t1: str,
    baseline_tool: Path,
    phase: str,
) -> dict[str, Any]:
    if phase not in {"check", "install"}:
        raise FreshHostTransportError("host_baseline_phase_invalid")
    source = baseline_tool.read_text(encoding="utf-8")
    command = _remote_command(("python3", "-c", source, "--phase", phase))
    completed = _run(
        ("ssh", "-n", t1, command),
        timeout=2400 if phase == "install" else 120,
        check=False,
    )
    output = completed.stdout.strip() or completed.stderr.strip()
    documents = []
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            documents.append(value)
    if not documents:
        raise FreshHostTransportError("host_baseline_output_invalid")
    report = documents[-1]
    if completed.returncode != 0 or report.get("status") == "STOP":
        raise FreshHostTransportError(
            f"host_baseline_{phase}_failed:{str(report.get('reason') or report.get('status'))[:200]}"
        )
    return report


def _remote_root_free_bytes(t1: str) -> int:
    completed = _run(
        (
            "ssh",
            "-n",
            t1,
            _remote_command(("df", "-B1", "--output=avail", "/")),
        ),
        timeout=30,
    )
    values = [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip().isdigit()
    ]
    if len(values) != 1:
        raise FreshHostTransportError("root_free_probe_invalid")
    return int(values[0])


def _remote_claim_authorization(
    t1: str,
    remote_dir: str,
    authorization: str,
) -> None:
    command = _remote_command(
        (
            "python3",
            f"{remote_dir}/tools/n3w_t1_fresh_product_bootstrap.py",
            "--payload-root",
            remote_dir,
            "--phase",
            "claim",
            "--authorization-id",
            authorization,
        )
    )
    completed = _run(("ssh", "-n", t1, command), timeout=120, check=False)
    claimed = False
    for line in completed.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            isinstance(event, dict)
            and event.get("event") == "authorization_claimed"
            and event.get("authorization_id") == authorization
            and event.get("authorization_consumed") is True
        ):
            claimed = True
    if completed.returncode != 0 or not claimed:
        raise FreshHostTransportError("authorization_claim_failed")


def _authorization_record_remote_path(authorization_id: str) -> str:
    digest = hashlib.sha256(authorization_id.encode("utf-8")).hexdigest()
    return f"{AUTHORIZATION_LEDGER_ROOT}/{digest}.json"


def _remote_authorization_record_state(
    t1: str,
    authorization_id: str,
) -> bool | None:
    script = (
        "import os,sys;"
        "sys.exit(0 if os.path.lexists(sys.argv[1]) else 1)"
    )
    try:
        completed = _run(
            (
                "ssh",
                "-n",
                t1,
                _remote_command(
                    (
                        "python3",
                        "-c",
                        script,
                        _authorization_record_remote_path(authorization_id),
                    )
                ),
            ),
            timeout=30,
            check=False,
        )
    except (
        FreshHostTransportError,
        OSError,
        subprocess.TimeoutExpired,
    ):
        return None
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    return None


def _emit(value: dict[str, object]) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")), flush=True)


def _stop_remote_apply_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--t1", required=True)
    parser.add_argument("--phase", choices=("preflight", "apply"), required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--artifact-id", type=int, required=True)
    parser.add_argument("--artifact-zip-sha256", required=True)
    parser.add_argument("--archive-sha256", required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--authorization-id")
    return parser


def main() -> int:
    args = _parser().parse_args()
    work = Path(tempfile.mkdtemp(prefix="n3w-fresh-host."))
    authorization: str | None = None
    remote_dir: str | None = None
    remote_apply_started = False
    claim_seen = False
    payload_transfer_started = False
    payload_transfer_complete = False
    try:
        _download_artifact(
            work,
            run_id=args.run_id,
            artifact_name=args.artifact_name,
            artifact_id=args.artifact_id,
            artifact_zip_sha256=args.artifact_zip_sha256,
        )
        archive = _verify_outer_artifact(
            work,
            archive_sha256=args.archive_sha256,
            manifest_sha256=args.manifest_sha256,
        )
        manifest = _read_payload_manifest(
            archive,
            manifest_sha256=args.manifest_sha256,
        )
        capacity = _capacity_contract(work, manifest)
        _verify_image_artifacts(work, manifest, capacity)
        baseline_tool = work / "host-baseline.py"
        baseline = _remote_baseline_report(args.t1, baseline_tool, "check")
        prebaseline_plan: TransportPlan | None = None
        if baseline.get("status") != "PASS":
            root_free = _remote_root_free_bytes(args.t1)
            prebaseline_plan = _plan_transport(
                manifest,
                archive_size_bytes=archive.stat().st_size,
                remote_free_bytes=root_free,
                capacity=capacity,
            )
            if not prebaseline_plan.capacity_pass:
                raise FreshHostTransportError(
                    "remote_capacity_insufficient_prebaseline"
                )

        if args.phase == "preflight" and baseline.get("status") != "PASS":
            assert prebaseline_plan is not None
            _emit(
                {
                    "schema": "gh.n3w-t1-fresh-host-preflight/1",
                    "status": "PASS",
                    "phase": "preflight",
                    "host_baseline": baseline,
                    "host_baseline_install_required": True,
                    "root_free_bytes": prebaseline_plan.remote_free_bytes,
                    "transport": prebaseline_plan.to_dict(),
                    "capacity_admission": "PREBASELINE_ROOT_PASS",
                    "payload_transfer": False,
                    "docker_mutation": False,
                    "production_service_start": False,
                    "authorization_claimed": False,
                    "authorization_consumed": False,
                    "board_access": False,
                }
            )
            return 0

        manifest_authorization = manifest.get("authorization_id")
        if args.phase == "apply":
            if (
                not isinstance(manifest_authorization, str)
                or not manifest_authorization
                or args.authorization_id != manifest_authorization
            ):
                raise FreshHostTransportError("authorization_id_mismatch")
            authorization = manifest_authorization
            remote_dir = _remote_mktemp(args.t1, "n3w-fresh-bootstrap")
            payload_transfer_started = True
            _remote_prepare_payload(
                args.t1,
                remote_dir,
                archive,
                archive_sha256=args.archive_sha256,
                manifest_sha256=args.manifest_sha256,
            )
            payload_transfer_complete = True
            try:
                _remote_claim_authorization(args.t1, remote_dir, authorization)
            except (
                FreshHostTransportError,
                OSError,
                subprocess.TimeoutExpired,
            ) as error:
                record_state = _remote_authorization_record_state(
                    args.t1,
                    authorization,
                )
                if record_state is True:
                    claim_seen = True
                    remote_apply_started = True
                    raise FreshHostTransportError(
                        "authorization_claim_result_lost_consumed"
                    ) from error
                if record_state is None:
                    remote_apply_started = True
                    raise FreshHostTransportError(
                        "authorization_claim_state_unknown"
                    ) from error
                raise
            claim_seen = True
            remote_apply_started = True
            if baseline.get("status") != "PASS":
                baseline = _remote_baseline_report(args.t1, baseline_tool, "install")
                if baseline.get("status") != "PASS":
                    raise FreshHostTransportError("host_baseline_install_not_ready")

        storage = _remote_storage_report(args.t1)
        plan = _plan_transport(
            manifest,
            archive_size_bytes=archive.stat().st_size,
            remote_free_bytes=min(
                int(storage["staging_free_bytes"]),
                int(storage["docker_free_bytes"]),
                int(storage["image_store_free_bytes"]),
            ),
            capacity=capacity,
        )
        if args.phase == "apply":
            if (
                plan.remote_free_bytes
                < plan.worst_image_required_free_bytes
            ):
                raise FreshHostTransportError("remote_capacity_insufficient")
        elif not plan.capacity_pass:
            raise FreshHostTransportError("remote_capacity_insufficient")
        if args.phase == "preflight":
            _emit(
                {
                    "schema": "gh.n3w-t1-fresh-host-preflight/1",
                    "status": "PASS",
                    "phase": "preflight",
                    "host_baseline": baseline,
                    "host_baseline_install_required": False,
                    "storage": storage,
                    "transport": plan.to_dict(),
                    "capacity_admission": "PASS",
                    "payload_transfer": False,
                    "docker_mutation": False,
                    "production_service_start": False,
                    "authorization_claimed": False,
                    "authorization_consumed": False,
                    "board_access": False,
                }
            )
            return 0

        assert authorization is not None
        assert remote_dir is not None
        command = _remote_command(
            (
                "python3",
                f"{remote_dir}/tools/n3w_t1_fresh_product_bootstrap.py",
                "--payload-root",
                remote_dir,
                "--phase",
                "apply",
                "--authorization-id",
                authorization,
            )
        )
        process = subprocess.Popen(
            ("ssh", "-n", args.t1, command),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        remote_apply_started = True
        requested: list[str] = []
        loaded: list[str] = []
        assert process.stdout is not None
        try:
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    event = {}
                if (
                    event.get("event") == "authorization_claimed"
                    and event.get("authorization_id") == authorization
                ):
                    claim_seen = True
                    continue
                if event.get("event") == "image_requested":
                    if not claim_seen:
                        process.terminate()
                        raise FreshHostTransportError("image_requested_before_authorization")
                    label = str(event.get("label"))
                    expected = IMAGE_LABELS[len(requested)] if len(requested) < len(IMAGE_LABELS) else None
                    if label != expected or label in requested:
                        process.terminate()
                        raise FreshHostTransportError("image_request_order_invalid")
                    _transfer_requested_image(
                        args.t1,
                        remote_dir,
                        work,
                        manifest,
                        capacity,
                        label,
                    )
                    requested.append(label)
                    continue
                if event.get("event") == "image_loaded":
                    label = str(event.get("label"))
                    expected = IMAGE_LABELS[len(loaded)] if len(loaded) < len(IMAGE_LABELS) else None
                    if (
                        label != expected
                        or label not in requested
                        or event.get("staged_tar_deleted") is not True
                    ):
                        process.terminate()
                        raise FreshHostTransportError("image_load_event_invalid")
                    if _remote_free_bytes(args.t1) < MIN_POST_PEAK_FREE_BYTES:
                        process.terminate()
                        raise FreshHostTransportError("postload_reserve_breached")
                    loaded.append(label)
            return_code = process.wait()
        except Exception:
            _stop_remote_apply_process(process)
            raise
        if return_code == 0 and (
            tuple(requested) != IMAGE_LABELS or tuple(loaded) != IMAGE_LABELS
        ):
            raise FreshHostTransportError("image_event_sequence_incomplete")

        try:
            marker_probe = _run(
                (
                    "ssh",
                    "-n",
                    args.t1,
                    _remote_command(
                        (
                            "test",
                            "-f",
                            _authorization_record_remote_path(authorization),
                        )
                    ),
                ),
                timeout=30,
                check=False,
            )
        except (
            FreshHostTransportError,
            OSError,
            subprocess.TimeoutExpired,
        ) as error:
            _emit(
                {
                    "schema": "gh.n3w-t1-fresh-host-apply/1",
                    "status": "STOP_PARTIAL" if claim_seen else "STOP_UNKNOWN",
                    "reason": str(error),
                    "authorization_id": authorization,
                    "authorization_claimed": True if claim_seen else None,
                    "authorization_consumed": True,
                    "replay_allowed": False,
                    "remote_payload_preserved": True,
                    "production_service_start": False,
                    "board_access": False,
                }
            )
            return 2

        marker_known = marker_probe.returncode in {0, 1}
        marker_present = marker_probe.returncode == 0

        if return_code != 0:
            if marker_known and not marker_present and not claim_seen:
                cleanup_probe = _run(
                    (
                        "ssh",
                        "-n",
                        args.t1,
                        _remote_command(("rm", "-rf", "--", remote_dir)),
                    ),
                    timeout=120,
                    check=False,
                )
                removed = cleanup_probe.returncode == 0
                _emit(
                    {
                        "schema": "gh.n3w-t1-fresh-host-apply/1",
                        "status": "STOP_PRECLAIM",
                        "authorization_id": authorization,
                        "authorization_claimed": False,
                        "authorization_consumed": False,
                        "remote_payload_removed": removed,
                        "remote_payload_preserved": not removed,
                        "production_service_start": False,
                        "board_access": False,
                    }
                )
                return return_code

            _emit(
                {
                    "schema": "gh.n3w-t1-fresh-host-apply/1",
                    "status": "STOP_PARTIAL"
                    if (claim_seen or marker_present)
                    else "STOP_UNKNOWN",
                    "authorization_id": authorization,
                    "authorization_claimed": (
                        True if (claim_seen or marker_present) else None
                    ),
                    "authorization_consumed": True,
                    "replay_allowed": False,
                    "remote_payload_preserved": True,
                    "production_service_start": False,
                    "board_access": False,
                }
            )
            return return_code

        if not (claim_seen and marker_present):
            _emit(
                {
                    "schema": "gh.n3w-t1-fresh-host-apply/1",
                    "status": "STOP_UNKNOWN",
                    "authorization_id": authorization,
                    "authorization_claimed": True if marker_present else None,
                    "authorization_consumed": True,
                    "replay_allowed": False,
                    "remote_payload_preserved": True,
                    "production_service_start": False,
                    "board_access": False,
                }
            )
            return 2

        try:
            cleanup_probe = _run(
                (
                    "ssh",
                    "-n",
                    args.t1,
                    _remote_command(("rm", "-rf", "--", remote_dir)),
                ),
                timeout=120,
                check=False,
            )
        except (
            FreshHostTransportError,
            OSError,
            subprocess.TimeoutExpired,
        ) as error:
            _emit(
                {
                    "schema": "gh.n3w-t1-fresh-host-apply/1",
                    "status": "STOP_POSTSUCCESS_CLEANUP",
                    "reason": str(error),
                    "apply_result": "PASS",
                    "authorization_id": authorization,
                    "authorization_claimed": True,
                    "authorization_consumed": True,
                    "replay_allowed": False,
                    "public_product_staged": True,
                    "remote_payload_preserved": True,
                    "production_service_start": False,
                    "board_access": False,
                }
            )
            return 2

        if cleanup_probe.returncode != 0:
            _emit(
                {
                    "schema": "gh.n3w-t1-fresh-host-apply/1",
                    "status": "STOP_POSTSUCCESS_CLEANUP",
                    "apply_result": "PASS",
                    "authorization_id": authorization,
                    "authorization_claimed": True,
                    "authorization_consumed": True,
                    "replay_allowed": False,
                    "public_product_staged": True,
                    "remote_payload_removed": False,
                    "remote_payload_preserved": True,
                    "production_service_start": False,
                    "board_access": False,
                }
            )
            return 2

        _emit(
            {
                "schema": "gh.n3w-t1-fresh-host-apply/1",
                "status": "PASS",
                "authorization_id": authorization,
                "authorization_claimed": True,
                "authorization_consumed": True,
                "replay_allowed": False,
                "remote_payload_removed": True,
                "production_service_start": False,
                "board_access": False,
            }
        )
        return 0
    except (FreshHostTransportError, OSError, subprocess.TimeoutExpired) as error:
        if remote_apply_started:
            _emit(
                {
                    "schema": "gh.n3w-t1-fresh-host-apply/1",
                    "status": "STOP_PARTIAL" if claim_seen else "STOP_UNKNOWN",
                    "reason": str(error),
                    "authorization_id": authorization or args.authorization_id,
                    "authorization_claimed": True if claim_seen else None,
                    "authorization_consumed": True,
                    "replay_allowed": False,
                    "remote_payload_preserved": remote_dir is not None,
                    "production_service_start": False,
                    "board_access": False,
                }
            )
            return 2
        if args.phase == "apply":
            payload_transfer: bool | None
            if payload_transfer_complete:
                payload_transfer = True
            elif payload_transfer_started:
                payload_transfer = None
            else:
                payload_transfer = False
            _emit(
                {
                    "schema": "gh.n3w-t1-fresh-host-apply/1",
                    "status": "STOP_PRECLAIM",
                    "reason": str(error),
                    "authorization_id": authorization or args.authorization_id,
                    "authorization_claimed": False,
                    "authorization_consumed": False,
                    "payload_transfer": payload_transfer,
                    "docker_mutation": False,
                    "remote_payload_preserved": remote_dir is not None,
                    "production_service_start": False,
                    "board_access": False,
                }
            )
            return 2
        _emit(
            {
                "schema": "gh.n3w-t1-fresh-host-preflight/1",
                "status": "STOP",
                "phase": "preflight",
                "reason": str(error),
                "payload_transfer": False,
                "docker_mutation": False,
                "production_service_start": False,
                "authorization_claimed": False,
                "authorization_consumed": False,
                "board_access": False,
            }
        )
        return 2
    finally:
        for path in sorted(work.rglob("*"), reverse=True):
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                path.rmdir()
        work.rmdir()

if __name__ == "__main__":
    raise SystemExit(main())
