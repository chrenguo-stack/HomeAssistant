#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

REPOSITORY = "chrenguo-stack/HomeAssistant"
SCHEMA = "gh.n3w-t1-f5-release-archive/1"
INDEX_SCHEMA = "gh.n3w-t1-f5-approved-release-file-index/1"
DEFAULT_ARCHIVE_ROOT = "~/Documents/N3W/approved-releases"
ARCHIVE_FILES = frozenset(("artifact.zip", "binding.json"))
REQUIRED_RELEASE_FILES = frozenset(
    (
        "approved-release.json",
        "approved-release.sha256",
        "release-file-index.json",
        "release-file-index.sha256",
        "release-provenance.json",
    )
)


class ReleaseArchiveError(RuntimeError):
    pass


def _sha256_stream(stream: Any) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return _sha256_stream(stream)


def _hex(value: str, length: int, code: str) -> str:
    if (
        len(value) != length
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ReleaseArchiveError(code)
    return value


def _sidecar(raw: bytes, code: str) -> str:
    try:
        text = raw.decode("utf-8").strip()
    except UnicodeError as error:
        raise ReleaseArchiveError(code) from error
    token = text.split()[0] if text else ""
    return _hex(token, 64, code)


def _run(
    command: Sequence[str],
    *,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        tuple(command),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if completed.returncode != 0:
        reason = completed.stderr.strip() or completed.stdout.strip()
        raise ReleaseArchiveError(
            f"command_failed:{command[0]}:{completed.returncode}:{reason[:300]}"
        )
    return completed


def _github_token() -> str:
    token = _run(("gh", "auth", "token"), timeout=30).stdout.strip()
    if not token:
        raise ReleaseArchiveError("github_token_unavailable")
    return token


def _artifact_metadata(
    *,
    run_id: str,
    artifact_name: str,
    artifact_id: int,
    artifact_zip_sha256: str,
) -> dict[str, Any]:
    token = _github_token()
    completed = _run(
        (
            "curl",
            "-4",
            "-fsS",
            "--http1.1",
            "--retry",
            "3",
            "--retry-all-errors",
            "--retry-delay",
            "2",
            "--connect-timeout",
            "20",
            "--max-time",
            "120",
            "-H",
            f"Authorization: Bearer {token}",
            "-H",
            "Accept: application/vnd.github+json",
            "-H",
            "X-GitHub-Api-Version: 2022-11-28",
            f"https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{artifact_id}",
        ),
        timeout=150,
    )
    try:
        document = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ReleaseArchiveError("artifact_metadata_invalid") from error
    workflow_run = document.get("workflow_run")
    if (
        document.get("id") != artifact_id
        or document.get("name") != artifact_name
        or document.get("expired") is not False
        or document.get("digest") != f"sha256:{artifact_zip_sha256}"
        or not isinstance(workflow_run, dict)
        or str(workflow_run.get("id")) != str(run_id)
    ):
        raise ReleaseArchiveError("artifact_metadata_binding_invalid")
    return document


def _download_artifact(destination: Path, *, artifact_id: int) -> None:
    token = _github_token()
    headers = destination.parent / "artifact-download.headers"
    try:
        _run(
            (
                "curl",
                "-4",
                "-fsS",
                "--http1.1",
                "--retry",
                "3",
                "--retry-all-errors",
                "--retry-delay",
                "2",
                "--connect-timeout",
                "20",
                "--max-time",
                "120",
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
            timeout=150,
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
            raise ReleaseArchiveError("artifact_redirect_missing")
        _run(
            (
                "curl",
                "-4",
                "-fL",
                "--http1.1",
                "--retry",
                "5",
                "--retry-all-errors",
                "--retry-delay",
                "2",
                "--connect-timeout",
                "20",
                "--speed-time",
                "120",
                "--speed-limit",
                "1024",
                "-o",
                str(destination),
                location,
            ),
            timeout=7200,
        )
    finally:
        headers.unlink(missing_ok=True)


def _safe_name(name: str) -> str:
    if not name or "\x00" in name or "\\" in name:
        raise ReleaseArchiveError("release_zip_member_unsafe")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ReleaseArchiveError("release_zip_member_unsafe")
    return path.as_posix()


def _zip_files(bundle: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    result: dict[str, zipfile.ZipInfo] = {}
    for item in bundle.infolist():
        if item.is_dir():
            continue
        name = _safe_name(item.filename)
        mode = (item.external_attr >> 16) & 0o170000
        if mode == 0o120000 or name in result:
            raise ReleaseArchiveError("release_zip_member_unsafe")
        result[name] = item
    return result


def _read_json(bundle: zipfile.ZipFile, name: str, code: str) -> dict[str, Any]:
    try:
        value = json.loads(bundle.read(name).decode("utf-8"))
    except (KeyError, UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseArchiveError(code) from error
    if not isinstance(value, dict):
        raise ReleaseArchiveError(code)
    return value


def _verify_release_zip(
    archive: Path,
    *,
    release_id: str,
    release_sha256: str,
    file_index_sha256: str,
    source_head: str,
    source_tree: str,
    builder_head: str,
) -> dict[str, Any]:
    if archive.is_symlink() or not archive.is_file():
        raise ReleaseArchiveError("archive_file_invalid")
    try:
        with zipfile.ZipFile(archive) as bundle:
            files = _zip_files(bundle)
            if not REQUIRED_RELEASE_FILES.issubset(files):
                raise ReleaseArchiveError("release_required_file_missing")

            release_raw = bundle.read("approved-release.json")
            if hashlib.sha256(release_raw).hexdigest() != release_sha256:
                raise ReleaseArchiveError("approved_release_sha256_mismatch")
            if _sidecar(
                bundle.read("approved-release.sha256"),
                "approved_release_sidecar_invalid",
            ) != release_sha256:
                raise ReleaseArchiveError("approved_release_sidecar_mismatch")
            try:
                release = json.loads(release_raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as error:
                raise ReleaseArchiveError("approved_release_invalid") from error
            if (
                not isinstance(release, dict)
                or release.get("release_id") != release_id
                or release.get("source_head") != source_head
            ):
                raise ReleaseArchiveError("approved_release_binding_invalid")

            index_raw = bundle.read("release-file-index.json")
            if hashlib.sha256(index_raw).hexdigest() != file_index_sha256:
                raise ReleaseArchiveError("release_index_sha256_mismatch")
            if _sidecar(
                bundle.read("release-file-index.sha256"),
                "release_index_sidecar_invalid",
            ) != file_index_sha256:
                raise ReleaseArchiveError("release_index_sidecar_mismatch")
            try:
                index = json.loads(index_raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as error:
                raise ReleaseArchiveError("release_index_invalid") from error
            records = index.get("files") if isinstance(index, dict) else None
            if index.get("schema") != INDEX_SCHEMA or not isinstance(records, list):
                raise ReleaseArchiveError("release_index_invalid")

            expected_names = set(files) - {
                "release-file-index.json",
                "release-file-index.sha256",
            }
            observed_names: set[str] = set()
            for record in records:
                if (
                    not isinstance(record, dict)
                    or set(record) != {"path", "sha256", "size"}
                    or not isinstance(record.get("path"), str)
                    or not isinstance(record.get("sha256"), str)
                    or not isinstance(record.get("size"), int)
                    or isinstance(record.get("size"), bool)
                ):
                    raise ReleaseArchiveError("release_index_record_invalid")
                name = _safe_name(record["path"])
                if name in observed_names or name not in files:
                    raise ReleaseArchiveError("release_index_record_invalid")
                _hex(
                    record["sha256"],
                    64,
                    "release_index_record_sha256_invalid",
                )
                info = files[name]
                if info.file_size != record["size"]:
                    raise ReleaseArchiveError(
                        f"release_index_size_mismatch:{name}"
                    )
                with bundle.open(info) as stream:
                    observed = _sha256_stream(stream)
                if observed != record["sha256"]:
                    raise ReleaseArchiveError(
                        f"release_index_file_sha256_mismatch:{name}"
                    )
                observed_names.add(name)
            if observed_names != expected_names:
                raise ReleaseArchiveError("release_index_file_set_mismatch")

            provenance = _read_json(
                bundle,
                "release-provenance.json",
                "release_provenance_invalid",
            )
            if (
                provenance.get("source_head") != source_head
                or provenance.get("source_tree") != source_tree
                or provenance.get("builder_head") != builder_head
            ):
                raise ReleaseArchiveError("release_provenance_binding_invalid")
    except zipfile.BadZipFile as error:
        raise ReleaseArchiveError("release_zip_invalid") from error

    return {
        "release_id": release_id,
        "release_sha256": release_sha256,
        "file_index_sha256": file_index_sha256,
        "source_head": source_head,
        "source_tree": source_tree,
        "builder_head": builder_head,
    }


def _binding(
    *,
    run_id: str,
    artifact_name: str,
    artifact_id: int,
    artifact_zip_sha256: str,
    release_id: str,
    release_sha256: str,
    file_index_sha256: str,
    source_head: str,
    source_tree: str,
    builder_head: str,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "repository": REPOSITORY,
        "workflow_run_id": str(run_id),
        "artifact_name": artifact_name,
        "artifact_id": artifact_id,
        "artifact_zip_sha256": artifact_zip_sha256,
        "release_id": release_id,
        "release_sha256": release_sha256,
        "file_index_sha256": file_index_sha256,
        "source_head": source_head,
        "source_tree": source_tree,
        "builder_head": builder_head,
    }


def _entry(
    root: Path,
    *,
    release_id: str,
    artifact_id: int,
    artifact_zip_sha256: str,
) -> Path:
    _hex(release_id, 64, "release_id_invalid")
    _hex(artifact_zip_sha256, 64, "artifact_sha256_invalid")
    if artifact_id <= 0:
        raise ReleaseArchiveError("artifact_id_invalid")
    expanded = root.expanduser()
    if expanded.exists() and (expanded.is_symlink() or not expanded.is_dir()):
        raise ReleaseArchiveError("archive_root_unsafe")
    release_root = expanded / release_id
    if release_root.exists() and (
        release_root.is_symlink() or not release_root.is_dir()
    ):
        raise ReleaseArchiveError("archive_release_root_unsafe")
    artifact_root = release_root / str(artifact_id)
    if artifact_root.exists() and (
        artifact_root.is_symlink() or not artifact_root.is_dir()
    ):
        raise ReleaseArchiveError("archive_artifact_root_unsafe")
    return artifact_root / artifact_zip_sha256


def _verify_entry(
    entry: Path,
    *,
    expected_binding: dict[str, Any],
) -> dict[str, Any]:
    if entry.is_symlink() or not entry.is_dir():
        raise ReleaseArchiveError("archive_entry_unsafe")
    if {item.name for item in entry.iterdir()} != ARCHIVE_FILES:
        raise ReleaseArchiveError("archive_file_set_invalid")
    archive = entry / "artifact.zip"
    binding_path = entry / "binding.json"
    if (
        archive.is_symlink()
        or not archive.is_file()
        or binding_path.is_symlink()
        or not binding_path.is_file()
    ):
        raise ReleaseArchiveError("archive_file_unsafe")
    try:
        binding = json.loads(binding_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseArchiveError("archive_binding_invalid") from error
    if binding != expected_binding:
        raise ReleaseArchiveError("archive_binding_mismatch")
    expected_zip = expected_binding["artifact_zip_sha256"]
    if _sha256_file(archive) != expected_zip:
        raise ReleaseArchiveError("archive_zip_sha256_mismatch")
    return _verify_release_zip(
        archive,
        release_id=expected_binding["release_id"],
        release_sha256=expected_binding["release_sha256"],
        file_index_sha256=expected_binding["file_index_sha256"],
        source_head=expected_binding["source_head"],
        source_tree=expected_binding["source_tree"],
        builder_head=expected_binding["builder_head"],
    )


def _arguments(args: argparse.Namespace) -> tuple[Path, dict[str, Any], Path]:
    for name in (
        "artifact_zip_sha256",
        "release_id",
        "release_sha256",
        "file_index_sha256",
    ):
        _hex(getattr(args, name), 64, f"{name}_invalid")
    for name in ("source_head", "source_tree", "builder_head"):
        _hex(getattr(args, name), 40, f"{name}_invalid")
    if args.artifact_id <= 0 or not args.run_id or not args.artifact_name:
        raise ReleaseArchiveError("archive_argument_invalid")
    root = Path(args.archive_root).expanduser()
    binding = _binding(
        run_id=args.run_id,
        artifact_name=args.artifact_name,
        artifact_id=args.artifact_id,
        artifact_zip_sha256=args.artifact_zip_sha256,
        release_id=args.release_id,
        release_sha256=args.release_sha256,
        file_index_sha256=args.file_index_sha256,
        source_head=args.source_head,
        source_tree=args.source_tree,
        builder_head=args.builder_head,
    )
    entry = _entry(
        root,
        release_id=args.release_id,
        artifact_id=args.artifact_id,
        artifact_zip_sha256=args.artifact_zip_sha256,
    )
    return root, binding, entry


def archive(args: argparse.Namespace) -> dict[str, Any]:
    root, binding, entry = _arguments(args)
    if entry.exists():
        verified = _verify_entry(entry, expected_binding=binding)
        return {
            "status": "PASS",
            "archive_status": "HIT",
            **verified,
            "t1_access": False,
            "board_access": False,
        }

    _artifact_metadata(
        run_id=args.run_id,
        artifact_name=args.artifact_name,
        artifact_id=args.artifact_id,
        artifact_zip_sha256=args.artifact_zip_sha256,
    )
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink() or not root.is_dir():
        raise ReleaseArchiveError("archive_root_unsafe")
    release_root = root / args.release_id
    release_root.mkdir(exist_ok=True, mode=0o700)
    artifact_root = release_root / str(args.artifact_id)
    artifact_root.mkdir(exist_ok=True, mode=0o700)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{args.artifact_zip_sha256[:12]}.",
            dir=artifact_root,
        )
    )
    published = False
    try:
        archive_path = staging / "artifact.zip"
        _download_artifact(
            archive_path,
            artifact_id=args.artifact_id,
        )
        if _sha256_file(archive_path) != args.artifact_zip_sha256:
            raise ReleaseArchiveError("artifact_zip_sha256_mismatch")
        verified = _verify_release_zip(
            archive_path,
            release_id=args.release_id,
            release_sha256=args.release_sha256,
            file_index_sha256=args.file_index_sha256,
            source_head=args.source_head,
            source_tree=args.source_tree,
            builder_head=args.builder_head,
        )
        (staging / "binding.json").write_text(
            json.dumps(binding, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        if {item.name for item in staging.iterdir()} != ARCHIVE_FILES:
            raise ReleaseArchiveError("archive_staging_file_set_invalid")
        if entry.exists():
            raise ReleaseArchiveError("archive_publish_target_exists")
        staging.rename(entry)
        published = True
    finally:
        if not published and staging.exists():
            shutil.rmtree(staging)
    return {
        "status": "PASS",
        "archive_status": "MISS_POPULATED",
        **verified,
        "t1_access": False,
        "board_access": False,
    }


def verify(args: argparse.Namespace) -> dict[str, Any]:
    _root, binding, entry = _arguments(args)
    if not entry.exists():
        raise ReleaseArchiveError("archive_entry_missing")
    verified = _verify_entry(entry, expected_binding=binding)
    return {
        "status": "PASS",
        "archive_status": "VERIFY_ONLY",
        **verified,
        "t1_access": False,
        "board_access": False,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("archive", "verify"):
        current = subparsers.add_parser(name)
        current.add_argument("--run-id", required=True)
        current.add_argument("--artifact-name", required=True)
        current.add_argument("--artifact-id", required=True, type=int)
        current.add_argument("--artifact-zip-sha256", required=True)
        current.add_argument("--release-id", required=True)
        current.add_argument("--release-sha256", required=True)
        current.add_argument("--file-index-sha256", required=True)
        current.add_argument("--source-head", required=True)
        current.add_argument("--source-tree", required=True)
        current.add_argument("--builder-head", required=True)
        current.add_argument(
            "--archive-root",
            default=DEFAULT_ARCHIVE_ROOT,
        )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        report = archive(args) if args.command == "archive" else verify(args)
    except ReleaseArchiveError as error:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_code": str(error),
                    "t1_access": False,
                    "board_access": False,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 2
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
