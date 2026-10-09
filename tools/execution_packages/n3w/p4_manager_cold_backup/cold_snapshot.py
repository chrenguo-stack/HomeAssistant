from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

REVISION = "gh.n3w.p4.manager.cold-backup/1"
EXPECTED_MOUNTS = {
    "/var/lib/greenhouse-manager-registration": True,
    "/var/lib/greenhouse-manager/n3w": True,
    "/var/lib/greenhouse-manager/n3w/relay-keys": True,
    "/run/secrets/provisioning_password": False,
    "/run/secrets/broker-ca.pem": False,
    "/run/secrets/gh_manager_mqtt_password": False,
}
RW = {
    "registration": "/var/lib/greenhouse-manager-registration",
    "n3w": "/var/lib/greenhouse-manager/n3w",
    "relay_keys": "/var/lib/greenhouse-manager/n3w/relay-keys",
}
DATABASES = (
    ("registration", "registration.sqlite3"),
    ("n3w", "credential-lifecycle.sqlite3"),
    ("n3w", "replay.sqlite3"),
)


class Stop(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise Stop(code)


def command(*argv: str, allow_absent: bool = False) -> str:
    p = subprocess.run(argv, capture_output=True, text=True, check=False)
    if p.returncode:
        if allow_absent:
            return ""
        raise Stop("REQUIRED_LOCAL_COMMAND_FAILED")
    return p.stdout.strip()


def inspect(name: str) -> dict[str, Any]:
    data = json.loads(command("docker", "inspect", "--type", "container", name))
    require(isinstance(data, list) and len(data) == 1, "DOCKER_INSPECT_UNEXPECTED")
    return data[0]


def mount_sources(manager: dict[str, Any]) -> dict[str, Path]:
    mounts = manager.get("Mounts")
    require(isinstance(mounts, list) and len(mounts) == 6, "MOUNT_COUNT_DRIFT")
    found: dict[str, Path] = {}
    for item in mounts:
        dest = item.get("Destination")
        require(dest in EXPECTED_MOUNTS and dest not in found, "MOUNT_DEST_DRIFT")
        require(item.get("Type") == "bind", "MOUNT_TYPE_DRIFT")
        require(item.get("RW") is EXPECTED_MOUNTS[dest], "MOUNT_RW_DRIFT")
        raw = item.get("Source")
        require(isinstance(raw, str) and raw.startswith("/"), "SOURCE_NOT_ABSOLUTE")
        src = Path(raw)
        require(not src.is_symlink() and src.resolve(strict=True) == src, "SOURCE_SYMLINK_OR_ALIAS")
        require(src.is_dir() if item["RW"] else src.is_file(), "SOURCE_KIND_DRIFT")
        found[dest] = src
    for a in RW.values():
        for b in RW.values():
            if a >= b:
                continue
            x, y = str(found[a]), str(found[b])
            require(
                os.path.commonpath([x, y]) not in (x, y),
                "HOST_SOURCE_OVERLAP",
            )
    return found


def assert_no_other_container_writers(manager: dict[str, Any], sources: dict[str, Path]) -> None:
    manager_id = manager["Id"]
    ids = command("docker", "ps", "-q", "--no-trunc").splitlines()
    targets = tuple(str(sources[d]) for d in RW.values())
    for cid in ids:
        if cid == manager_id:
            continue
        other = inspect(cid)
        for m in other.get("Mounts", []):
            if not m.get("RW"):
                continue
            path = m.get("Source", "")
            if not path.startswith("/"):
                continue
            actual = os.path.realpath(path)
            for target in targets:
                if os.path.commonpath([actual, target]) in (actual, target):
                    raise Stop("OTHER_RUNNING_CONTAINER_RW_OVERLAP")


def validate_runtime(original: dict[str, Any], broker_saved: dict[str, Any], phase: str) -> dict[str, Path]:
    current = inspect("greenhouse-manager")
    broker = inspect("n3wfc4-broker-1")
    require(current.get("Id") == original.get("Id"), "MANAGER_CONTAINER_CHANGED")
    require(current.get("Image") == original.get("Image"), "MANAGER_IMAGE_CHANGED")
    for key in ("Config", "HostConfig"):
        require(current.get(key) == original.get(key), "MANAGER_CREATE_CONFIG_DRIFT")
    require(broker.get("Id") == broker_saved.get("Id"), "BROKER_CONTAINER_CHANGED")
    require(broker.get("State", {}).get("Running") is True, "BROKER_NOT_RUNNING")
    running = current.get("State", {}).get("Running")
    require(running is (phase == "preflight"), "MANAGER_RUNNING_STATE_BLOCKS_PHASE")
    sources = mount_sources(current)
    assert_no_other_container_writers(current, sources)
    return sources


def no_open_db_files(sources: dict[str, Path]) -> None:
    require(shutil.which("fuser") is not None, "FUSER_REQUIRED")
    for label, name in DATABASES:
        database = sources[RW[label]] / name
        require(database.is_file() and not database.is_symlink(), "DB_MAIN_MISSING_OR_SYMLINK")
        probe = subprocess.run(
            ("fuser", "-s", str(database)),
            capture_output=True,
            check=False,
        )
        require(probe.returncode == 1, "DB_FILE_BUSY_OR_PROBE_FAILED")


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path) -> list[dict[str, Any]]:
    result = []
    for path in sorted(root.rglob("*")):
        metadata = path.lstat()
        require(not stat.S_ISLNK(metadata.st_mode), "SYMLINK_IN_PERSISTENT_DATA")
        require(stat.S_ISREG(metadata.st_mode) or stat.S_ISDIR(metadata.st_mode), "SPECIAL_FILE_IN_DATA")
        entry: dict[str, Any] = {
            "path": path.relative_to(root).as_posix(),
            "mode": stat.S_IMODE(metadata.st_mode),
            "uid": metadata.st_uid,
            "gid": metadata.st_gid,
            "type": "file" if stat.S_ISREG(metadata.st_mode) else "dir",
        }
        if entry["type"] == "file":
            entry["bytes"] = metadata.st_size
            entry["sha256"] = file_hash(path)
        result.append(entry)
    return result


def validate_sqlite(root: Path) -> None:
    for label, name in DATABASES:
        database = root / label / name
        require(database.is_file(), "ISOLATED_DB_MISSING")
        uri = database.as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        try:
            rows = connection.execute("PRAGMA integrity_check").fetchall()
            require(rows == [("ok",)], "ISOLATED_SQLITE_INTEGRITY_FAIL")
        finally:
            connection.close()


def copy_data(sources: dict[str, Path], dest: Path) -> None:
    for label, mount in RW.items():
        original = sources[mount]
        require(not any(p.is_symlink() for p in original.rglob("*")), "SOURCE_SYMLINK_INSIDE")
        subprocess.run(
            ("cp", "-a", "--", str(original), str(dest / label)),
            check=True,
            stdout=subprocess.DEVNULL,
        )


def restored_clone_and_verify(snapshot: Path, expected: list[dict[str, Any]], private: Path) -> None:
    isolated = private / "isolated-restoration"
    require(not isolated.exists(), "RESTORATION_ALREADY_EXISTS")
    isolated.mkdir(mode=0o700)
    for label in RW:
        subprocess.run(
            ("cp", "-a", "--", str(snapshot / label), str(isolated / label)),
            check=True,
            stdout=subprocess.DEVNULL,
        )
    require(inventory(isolated) == expected, "RESTORE_HASH_MODE_OWNER_MISMATCH")
    validate_sqlite(isolated)


def capture(sources: dict[str, Path], private: Path) -> None:
    snapshot = private / "cold-snapshot"
    require(not snapshot.exists(), "SNAPSHOT_ALREADY_EXISTS")
    no_open_db_files(sources)
    snapshot.mkdir(mode=0o700)
    copy_data(sources, snapshot)
    no_open_db_files(sources)
    files = inventory(snapshot)
    require(len(files) > 0, "EMPTY_SNAPSHOT")
    manifest = private / "cold-snapshot-manifest-private.json"
    require(not manifest.exists(), "MANIFEST_ALREADY_EXISTS")
    manifest.write_text(json.dumps({"schema": REVISION, "files": files}, indent=2) + "\n")
    manifest.chmod(0o600)
    restored_clone_and_verify(snapshot, files, private)
    require(inventory(snapshot) == files, "SNAPSHOT_CHANGED_DURING_RESTORATION")
    print("THREE_RW_DATA_SOURCES_COLD_COPY=PASS")
    print("ALL_SNAPSHOT_FILE_SHA256_MODE_OWNER=PASS")
    print("THREE_SQLITE_INTEGRITY=PASS")
    print("ISOLATED_RESTORE_FILE_AND_DB_PROOF=PASS")


def private_root(value: str) -> Path:
    require(os.geteuid() == 0, "REQUIRES_ROOT")
    path = Path(value)
    require(
        path.is_absolute()
        and path.parent == Path("/root")
        and path.name.startswith("n3w-p4-manager-rollback-prep-")
        and not path.is_symlink()
        and path.is_dir(),
        "PRIVATE_ROOT_INVALID",
    )
    require(stat.S_IMODE(path.stat().st_mode) == 0o700, "PRIVATE_ROOT_MODE_DRIFT")
    return path


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "capture"))
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--permit-cold-copy", action="store_true")
    args = parser.parse_args()
    private = private_root(args.private_root)
    manager_file = private / "manager-inspect-private.json"
    broker_file = private / "broker-inspect-private.json"
    for path in (manager_file, broker_file):
        require(path.is_file() and stat.S_IMODE(path.stat().st_mode) == 0o600, "PRIVATE_INSPECT_INVALID")
    manager_saved = json.loads(manager_file.read_text())[0]
    broker_saved = json.loads(broker_file.read_text())[0]
    sources = validate_runtime(manager_saved, broker_saved, args.phase)
    if args.phase == "preflight":
        print("CURRENT_MANAGER_IDENTITY_AND_MOUNTS=PASS")
        print("BROKER_RUNNING=PASS")
        print("OTHER_RUNNING_CONTAINER_WRITERS=NONE_DETECTED")
        print("COLD_BACKUP=NOT_STARTED")
        return
    require(args.permit_cold_copy, "EXPLICIT_COLD_COPY_FLAG_REQUIRED")
    no_open_db_files(sources)
    capture(sources, private)


if __name__ == "__main__":
    try:
        run()
    except (Stop, OSError, subprocess.CalledProcessError, sqlite3.Error, ValueError, KeyError) as error:
        name = error.args[0] if isinstance(error, Stop) else error.__class__.__name__
        print(f"P4_COLD_BACKUP=STOP:{name}", file=sys.stderr)
        raise SystemExit(1)
