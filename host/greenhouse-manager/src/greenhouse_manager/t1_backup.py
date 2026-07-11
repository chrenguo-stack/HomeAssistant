from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Protocol

MANIFEST_NAME = "manifest.json"
COPY_SOURCES = (
    ("mosquitto", "/mosquitto/config", "mosquitto-config"),
    ("mosquitto", "/mosquitto/data", "mosquitto-data"),
    (
        "greenhouse-manager",
        "/var/lib/greenhouse-manager",
        "greenhouse-manager-data",
    ),
)


class BackupError(RuntimeError):
    pass


class CommandRunner(Protocol):
    def run(self, command: Sequence[str]) -> tuple[int, str]: ...


class SubprocessRunner:
    def run(self, command: Sequence[str]) -> tuple[int, str]:
        completed = subprocess.run(
            tuple(command),
            check=False,
            capture_output=True,
            text=True,
        )
        output = completed.stdout if completed.stdout else completed.stderr
        return completed.returncode, output


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        raise BackupError("backup directory must not be accessible by group or other")


def _sha256_stream(stream: BinaryIO) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _source_identity(runner: CommandRunner, container: str) -> dict[str, str]:
    template = '{"image_id":"{{.Image}}","image_ref":"{{.Config.Image}}"}'
    return_code, output = runner.run(
        ("docker", "inspect", "-f", template, container)
    )
    if return_code != 0:
        raise BackupError(f"required container is unavailable: {container}")
    try:
        document = json.loads(output)
    except json.JSONDecodeError as error:
        raise BackupError(f"container identity is invalid: {container}") from error
    return {
        "image_id": str(document["image_id"]),
        "image_ref": str(document["image_ref"]),
    }


def _regular_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise BackupError("backup source contains a symbolic link")
        if path.is_file():
            files.append(path)
    return tuple(files)


def _tar_filter(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mode = 0o600
    return info


def create_backup(
    output_directory: str | Path,
    *,
    runner: CommandRunner | None = None,
    now: datetime | None = None,
) -> Path:
    command_runner = runner or SubprocessRunner()
    output = Path(output_directory).expanduser().resolve()
    _private_directory(output)
    observed_at = (now or datetime.now(UTC)).astimezone(UTC)
    filename = (
        "greenhouse-t1-rollback-"
        + observed_at.strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + secrets.token_hex(4)
        + ".tar.gz"
    )
    destination = output / filename

    identities = {
        "mosquitto": _source_identity(command_runner, "mosquitto"),
        "greenhouse_manager": _source_identity(
            command_runner, "greenhouse-manager"
        ),
    }
    with tempfile.TemporaryDirectory(prefix=".gh-backup-", dir=output) as temporary:
        staging = Path(temporary)
        for container, source, archive_name in COPY_SOURCES:
            target = staging / archive_name
            return_code, _output = command_runner.run(
                ("docker", "cp", f"{container}:{source}/.", str(target))
            )
            if return_code != 0:
                raise BackupError(f"failed to copy required data from {container}")

        records: list[dict[str, Any]] = []
        for path in _regular_files(staging):
            relative = path.relative_to(staging).as_posix()
            with path.open("rb") as stream:
                checksum = _sha256_stream(stream)
            records.append(
                {
                    "path": relative,
                    "size": path.stat().st_size,
                    "sha256": checksum,
                }
            )
        manifest = {
            "schema": "gh.m2.t1-backup/1",
            "created_at": observed_at.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
            "classification": "sensitive-local-rollback",
            "portable_off_host": False,
            "sources": identities,
            "files": records,
        }
        manifest_path = staging / MANIFEST_NAME
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
            + "\n",
            encoding="utf-8",
        )
        manifest_path.chmod(0o600)

        file_descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        try:
            with os.fdopen(file_descriptor, "wb") as raw:
                with tarfile.open(fileobj=raw, mode="w:gz") as archive:
                    archive.add(
                        manifest_path,
                        arcname=MANIFEST_NAME,
                        recursive=False,
                        filter=_tar_filter,
                    )
                    for path in _regular_files(staging):
                        if path == manifest_path:
                            continue
                        archive.add(
                            path,
                            arcname=path.relative_to(staging).as_posix(),
                            recursive=False,
                            filter=_tar_filter,
                        )
        except Exception:
            destination.unlink(missing_ok=True)
            raise
    return destination


def _safe_member_name(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def verify_backup(path: str | Path) -> dict[str, Any]:
    archive_path = Path(path)
    if archive_path.stat().st_mode & 0o077:
        raise BackupError("backup archive permissions are not private")
    with tarfile.open(archive_path, mode="r:gz") as archive:
        members = archive.getmembers()
        if any(
            not member.isfile() or not _safe_member_name(member.name)
            for member in members
        ):
            raise BackupError("backup contains an unsafe archive member")
        by_name = {member.name: member for member in members}
        manifest_member = by_name.get(MANIFEST_NAME)
        if manifest_member is None:
            raise BackupError("backup manifest is missing")
        manifest_stream = archive.extractfile(manifest_member)
        if manifest_stream is None:
            raise BackupError("backup manifest cannot be read")
        try:
            manifest = json.load(manifest_stream)
        except json.JSONDecodeError as error:
            raise BackupError("backup manifest is invalid") from error
        if manifest.get("schema") != "gh.m2.t1-backup/1":
            raise BackupError("backup schema is unsupported")
        expected = {record["path"]: record for record in manifest.get("files", [])}
        if set(by_name) != set(expected) | {MANIFEST_NAME}:
            raise BackupError("backup file inventory does not match manifest")
        for name, record in expected.items():
            stream = archive.extractfile(by_name[name])
            if stream is None:
                raise BackupError("backup file cannot be read")
            checksum = _sha256_stream(stream)
            if checksum != record["sha256"]:
                raise BackupError("backup checksum verification failed")
            if by_name[name].size != record["size"]:
                raise BackupError("backup size verification failed")
    return manifest


def _extract_verified(path: Path, destination: Path) -> dict[str, Any]:
    manifest = verify_backup(path)
    with tarfile.open(path, mode="r:gz") as archive:
        for member in archive.getmembers():
            target = destination / member.name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            stream = archive.extractfile(member)
            if stream is None:
                raise BackupError("backup file cannot be extracted")
            with target.open("wb") as output:
                shutil.copyfileobj(stream, output)
            target.chmod(0o600)
    return manifest


def _sqlite_integrity(root: Path) -> dict[str, str]:
    results: dict[str, str] = {}
    for database in root.rglob("*.sqlite3"):
        relative = database.relative_to(root).as_posix()
        try:
            connection = sqlite3.connect(
                f"file:{database}?mode=ro", uri=True
            )
            result = connection.execute("PRAGMA integrity_check").fetchone()
            connection.close()
        except sqlite3.Error:
            results[relative] = "invalid"
        else:
            results[relative] = str(result[0]) if result else "invalid"
    return results


def restore_drill(
    path: str | Path,
    *,
    runner: CommandRunner | None = None,
    name_factory: Callable[[], str] | None = None,
) -> dict[str, Any]:
    command_runner = runner or SubprocessRunner()
    archive_path = Path(path).expanduser().resolve()
    container_name = (
        name_factory() if name_factory else f"gh-m2-restore-{secrets.token_hex(4)}"
    )
    created = False
    with tempfile.TemporaryDirectory(prefix="gh-m2-restore-") as temporary:
        staging = Path(temporary)
        staging.chmod(0o700)
        manifest = _extract_verified(archive_path, staging)
        sqlite_results = _sqlite_integrity(staging / "greenhouse-manager-data")
        if any(result != "ok" for result in sqlite_results.values()):
            raise BackupError("manager database integrity check failed")

        image_id = manifest["sources"]["mosquitto"]["image_id"]
        return_code, output = command_runner.run(
            (
                "docker",
                "create",
                "--network",
                "none",
                "--name",
                container_name,
                image_id,
            )
        )
        if return_code != 0:
            raise BackupError("isolated restore container could not be created")
        created = True
        container_id = output.strip() or container_name
        try:
            for source_name, target in (
                ("mosquitto-config", "/mosquitto/config"),
                ("mosquitto-data", "/mosquitto/data"),
            ):
                return_code, _output = command_runner.run(
                    (
                        "docker",
                        "cp",
                        f"{staging / source_name}/.",
                        f"{container_id}:{target}",
                    )
                )
                if return_code != 0:
                    raise BackupError("isolated restore data copy failed")
            return_code, _output = command_runner.run(
                ("docker", "start", container_id)
            )
            if return_code != 0:
                raise BackupError("isolated restored broker did not start")
            return_code, state = command_runner.run(
                (
                    "docker",
                    "inspect",
                    "-f",
                    "{{.State.Status}}",
                    container_id,
                )
            )
            if return_code != 0 or state.strip() != "running":
                raise BackupError("isolated restored broker is not running")
        finally:
            if created:
                command_runner.run(("docker", "rm", "-f", container_id))
    return {
        "schema": "gh.m2.t1-restore-drill/1",
        "archive": archive_path.name,
        "network": "none",
        "broker_started": True,
        "sqlite_integrity": sqlite_results,
        "current_services_modified": False,
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: CommandRunner | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        description="Create and verify private T1 rollback backups"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--output", required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("archive")
    drill = subparsers.add_parser("drill")
    drill.add_argument("archive")
    args = parser.parse_args(argv)

    try:
        if args.command == "create":
            result: object = {
                "archive": str(create_backup(args.output, runner=runner))
            }
        elif args.command == "verify":
            manifest = verify_backup(args.archive)
            result = {
                "verified": True,
                "schema": manifest["schema"],
                "files": len(manifest["files"]),
            }
        else:
            result = restore_drill(args.archive, runner=runner)
    except (BackupError, OSError, tarfile.TarError) as error:
        print(f"T1 backup operation failed: {error}", file=sys.stderr)
        return 2
    json.dump(result, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
