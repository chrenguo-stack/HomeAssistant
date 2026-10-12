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
TRANSPORT_SCHEMA = "gh.n3w-t1-fresh-transport/1"
MIN_POST_PEAK_FREE_BYTES = 5 * 1024 * 1024 * 1024
IMAGE_LABELS = ("homeassistant", "manager", "broker")
AUTHORIZATION_LEDGER_ROOT = "/var/lib/n3w-fresh-bootstrap-authorizations"
ARTIFACT_OUTER_FILES = frozenset(
    (
        "executor.sha256",
        "host-wrapper.py",
        "host-wrapper.sha256",
        "payload-archive.sha256",
        "payload-archive.tar.gz",
        "payload-manifest.sha256",
    )
)


class FreshHostTransportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TransportPlan:
    archive_size_bytes: int
    payload_uncompressed_bytes: int
    extraction_peak_bytes: int
    image_load_peak_bytes: int
    content_store_estimate_bytes: int
    snapshot_store_estimate_bytes: int
    storage_model: str
    required_peak_bytes: int
    minimum_post_peak_free_bytes: int
    required_free_bytes: int
    remote_free_bytes: int
    free_after_estimated_peak_bytes: int
    image_load_order: tuple[str, ...]
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
    except FreshHostTransportError:
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
                "--retry-all-errors",
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

    archive = work / "payload-archive.tar.gz"
    actual_archive_sha = _sha256_file(archive)
    if actual_archive_sha != archive_sha256:
        raise FreshHostTransportError("payload_archive_sha256_mismatch")
    if _read_sidecar(work / "payload-archive.sha256") != actual_archive_sha:
        raise FreshHostTransportError("payload_archive_sidecar_mismatch")
    if _read_sidecar(work / "payload-manifest.sha256") != manifest_sha256:
        raise FreshHostTransportError("payload_manifest_sidecar_mismatch")

    downloaded_wrapper = work / "host-wrapper.py"
    wrapper_sha = _sha256_file(downloaded_wrapper)
    if _read_sidecar(work / "host-wrapper.sha256") != wrapper_sha:
        raise FreshHostTransportError("host_wrapper_sidecar_mismatch")
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


def _transport_contract(manifest: dict[str, Any]) -> dict[str, Any]:
    transport = manifest.get("transport")
    if not isinstance(transport, dict) or transport.get("schema") != TRANSPORT_SCHEMA:
        raise FreshHostTransportError("transport_contract_missing")
    if transport.get("remote_staging_root") != REMOTE_STAGING_ROOT:
        raise FreshHostTransportError("transport_staging_root_invalid")
    if transport.get("minimum_post_peak_free_bytes") != MIN_POST_PEAK_FREE_BYTES:
        raise FreshHostTransportError("transport_reserve_invalid")

    order = transport.get("image_load_order")
    images = transport.get("images")
    payload_bytes = transport.get("payload_uncompressed_bytes")
    if order != list(IMAGE_LABELS) or not isinstance(images, dict):
        raise FreshHostTransportError("transport_image_order_invalid")
    if not isinstance(payload_bytes, int) or isinstance(payload_bytes, bool) or payload_bytes <= 0:
        raise FreshHostTransportError("transport_payload_size_invalid")

    file_records = manifest.get("files")
    if not isinstance(file_records, list):
        raise FreshHostTransportError("payload_manifest_files_invalid")
    file_sizes = {
        record.get("path"): record.get("size")
        for record in file_records
        if isinstance(record, dict)
    }

    for label in IMAGE_LABELS:
        record = images.get(label)
        if not isinstance(record, dict):
            raise FreshHostTransportError(f"transport_image_missing:{label}")
        path = record.get("path")
        tar_size = record.get("tar_size_bytes")
        loaded_size = record.get("loaded_size_bytes")
        image_ref = record.get("image_ref")
        if not isinstance(path, str) or not path.startswith("artifact/"):
            raise FreshHostTransportError(f"transport_image_path_invalid:{label}")
        if file_sizes.get(path) != tar_size:
            raise FreshHostTransportError(f"transport_image_tar_size_invalid:{label}")
        if (
            not isinstance(loaded_size, int)
            or isinstance(loaded_size, bool)
            or loaded_size <= 0
            or not isinstance(image_ref, str)
            or not image_ref
        ):
            raise FreshHostTransportError(f"transport_image_metadata_invalid:{label}")
    return transport


def _plan_transport(
    manifest: dict[str, Any],
    *,
    archive_size_bytes: int,
    remote_free_bytes: int,
) -> TransportPlan:
    transport = _transport_contract(manifest)
    payload_bytes = int(transport["payload_uncompressed_bytes"])
    extraction_peak = archive_size_bytes + payload_bytes

    current_payload = payload_bytes
    content_bytes = 0
    snapshot_bytes = 0
    image_peak = current_payload
    images = transport["images"]
    for label in IMAGE_LABELS:
        record = images[label]
        loaded_size = int(record["loaded_size_bytes"])
        tar_size = int(record["tar_size_bytes"])
        content_bytes += tar_size
        snapshot_bytes += loaded_size
        image_peak = max(
            image_peak,
            current_payload + content_bytes + snapshot_bytes,
        )
        current_payload -= tar_size

    required_peak = max(extraction_peak, image_peak)
    required_free = required_peak + MIN_POST_PEAK_FREE_BYTES
    return TransportPlan(
        archive_size_bytes=archive_size_bytes,
        payload_uncompressed_bytes=payload_bytes,
        extraction_peak_bytes=extraction_peak,
        image_load_peak_bytes=image_peak,
        content_store_estimate_bytes=content_bytes,
        snapshot_store_estimate_bytes=snapshot_bytes,
        storage_model="tar_plus_containerd_content_plus_snapshot",
        required_peak_bytes=required_peak,
        minimum_post_peak_free_bytes=MIN_POST_PEAK_FREE_BYTES,
        required_free_bytes=required_free,
        remote_free_bytes=remote_free_bytes,
        free_after_estimated_peak_bytes=remote_free_bytes - required_peak,
        image_load_order=IMAGE_LABELS,
        capacity_pass=remote_free_bytes >= required_free,
    )


def _remote_storage_report(t1: str) -> dict[str, object]:
    script = (
        "import json,os,shutil,subprocess;"
        "stage='/var/tmp';"
        "docker_root=subprocess.check_output("
        "['docker','info','--format','{{.DockerRootDir}}'],text=True).strip();"
        "containerd_root=os.path.join(docker_root,'containerd');"
        "containerd_probe=containerd_root if os.path.exists(containerd_root) else docker_root;"
        "stage_stat=os.stat(stage);docker_stat=os.stat(docker_root);"
        "containerd_stat=os.stat(containerd_probe);"
        "stage_fs=subprocess.check_output("
        "['findmnt','-n','-o','FSTYPE','--target',stage],text=True).strip();"
        "print(json.dumps({"
        "'staging_root':stage,'docker_root':docker_root,"
        "'containerd_root':containerd_probe,"
        "'containerd_root_present':os.path.exists(containerd_root),"
        "'staging_device':stage_stat.st_dev,'docker_device':docker_stat.st_dev,"
        "'containerd_device':containerd_stat.st_dev,"
        "'staging_free_bytes':shutil.disk_usage(stage).free,"
        "'docker_free_bytes':shutil.disk_usage(docker_root).free,"
        "'containerd_free_bytes':shutil.disk_usage(containerd_probe).free,"
        "'staging_fstype':stage_fs}))"
    )
    completed = _run(
        ("ssh", "-n", t1, _remote_command(("python3", "-c", script))),
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
    if not (
        report.get("staging_device")
        == report.get("docker_device")
        == report.get("containerd_device")
    ):
        raise FreshHostTransportError("staging_docker_containerd_filesystems_differ")
    free = report.get("staging_free_bytes")
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
archive = root / "payload.tar.gz"

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
    _run(("scp", str(archive), f"{t1}:{remote_dir}/payload.tar.gz"), timeout=900)
    script = _remote_payload_extract_script()
    command = _remote_command(
        ("python3", "-c", script, remote_dir, archive_sha256, manifest_sha256)
    )
    _run(("ssh", "-n", t1, command), timeout=600)


def _remote_load_images_sequentially(
    t1: str,
    remote_dir: str,
    manifest: dict[str, Any],
) -> None:
    transport = _transport_contract(manifest)
    for label in IMAGE_LABELS:
        relative = str(transport["images"][label]["path"])
        remote_tar = f"{remote_dir}/{relative}"
        _run(
            (
                "ssh",
                "-n",
                t1,
                _remote_command(("docker", "load", "--input", remote_tar)),
            ),
            timeout=1800,
        )
        _run(
            ("ssh", "-n", t1, _remote_command(("rm", "-f", remote_tar))),
            timeout=60,
        )


def _authorization_record_remote_path(authorization_id: str) -> str:
    digest = hashlib.sha256(authorization_id.encode("utf-8")).hexdigest()
    return f"{AUTHORIZATION_LEDGER_ROOT}/{digest}.json"


def _emit(value: dict[str, object]) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")), flush=True)


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
        storage = _remote_storage_report(args.t1)
        plan = _plan_transport(
            manifest,
            archive_size_bytes=archive.stat().st_size,
            remote_free_bytes=min(
                int(storage["staging_free_bytes"]),
                int(storage["docker_free_bytes"]),
                int(storage["containerd_free_bytes"]),
            ),
        )
        if not plan.capacity_pass:
            raise FreshHostTransportError("remote_capacity_insufficient")
        if args.phase == "preflight":
            _emit(
                {
                    "schema": "gh.n3w-t1-fresh-host-preflight/1",
                    "status": "PASS",
                    "phase": "preflight",
                    "storage": storage,
                    "transport": plan.to_dict(),
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
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            if (
                '"event":"authorization_claimed"' in line
                and authorization in line
            ):
                claim_seen = True
        return_code = process.wait()

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
                    "fresh_product_staged": True,
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
                    "fresh_product_staged": True,
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
