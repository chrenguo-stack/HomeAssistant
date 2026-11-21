from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any

BROKER_RECOVERY_SCHEMA = "gh.n3w-t1-core-updater-broker-recovery-point/1"
BROKER_DATA_ROOT = Path("/var/lib/n3wfc4-broker")
BROKER_RECOVERY_ROOT = Path("/var/lib/n3w-t1-core-updater/broker-recovery")
BROKER_REQUIRED_STATE = frozenset({"dynamic-security.json", "mosquitto.db"})
BROKER_RECOVERY_RESERVE_BYTES = 16 * 1024 * 1024
_RECOVERY_KEY = re.compile(r"^[0-9a-f]{16}-[0-9]{1,20}$")


class BrokerRecoveryError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise BrokerRecoveryError("broker_recovery_file_invalid")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(
        path,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
    )
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _safe_source_mode(mode: int) -> bool:
    return (
        mode & 0o600 == 0o600
        and mode & 0o022 == 0
    )


class LocalBrokerRecoveryPoint:
    def __init__(
        self,
        source_root: Path = BROKER_DATA_ROOT,
        recovery_root: Path = BROKER_RECOVERY_ROOT,
        *,
        expected_source_uid: int = 1883,
        expected_source_gid: int = 1883,
        reserve_bytes: int = BROKER_RECOVERY_RESERVE_BYTES,
    ) -> None:
        self.source_root = source_root
        self.recovery_root = recovery_root
        self.expected_source_uid = expected_source_uid
        self.expected_source_gid = expected_source_gid
        self.reserve_bytes = reserve_bytes

    def _validate_source_root(self) -> os.stat_result:
        if self.source_root.is_symlink() or not self.source_root.is_dir():
            raise BrokerRecoveryError("broker_recovery_source_root_invalid")
        metadata = self.source_root.stat()
        mode = stat.S_IMODE(metadata.st_mode)
        if (
            metadata.st_uid != self.expected_source_uid
            or metadata.st_gid != self.expected_source_gid
            or mode & 0o700 != 0o700
            or mode & 0o022
        ):
            raise BrokerRecoveryError("broker_recovery_source_root_metadata_invalid")
        return metadata

    def _scan_source(self, *, include_hashes: bool) -> dict[str, Any]:
        root = self._validate_source_root()
        rows: list[dict[str, Any]] = []
        names: set[str] = set()
        for path in sorted(self.source_root.iterdir(), key=lambda item: item.name):
            if path.name.startswith(".n3w-broker-restore-"):
                continue
            if path.is_symlink() or not path.is_file():
                raise BrokerRecoveryError("broker_recovery_source_entry_invalid")
            metadata = path.stat()
            mode = stat.S_IMODE(metadata.st_mode)
            if (
                metadata.st_uid != self.expected_source_uid
                or metadata.st_gid != self.expected_source_gid
                or not _safe_source_mode(mode)
            ):
                raise BrokerRecoveryError("broker_recovery_source_file_metadata_invalid")
            names.add(path.name)
            row: dict[str, Any] = {
                "name": path.name,
                "size": metadata.st_size,
                "mode": mode,
                "uid": metadata.st_uid,
                "gid": metadata.st_gid,
            }
            if include_hashes:
                row["sha256"] = _sha256_file(path)
            rows.append(row)
        if not BROKER_REQUIRED_STATE.issubset(names):
            raise BrokerRecoveryError("broker_recovery_required_state_missing")
        total = sum(int(row["size"]) for row in rows)
        largest = max((int(row["size"]) for row in rows), default=0)
        return {
            "root": {
                "mode": stat.S_IMODE(root.st_mode),
                "uid": root.st_uid,
                "gid": root.st_gid,
            },
            "files": rows,
            "total_bytes": total,
            "largest_file_bytes": largest,
        }

    def _usage_path(self) -> Path:
        candidate = self.recovery_root
        while not candidate.exists():
            if candidate.parent == candidate:
                raise BrokerRecoveryError("broker_recovery_capacity_path_missing")
            candidate = candidate.parent
        if candidate.is_symlink():
            raise BrokerRecoveryError("broker_recovery_capacity_path_invalid")
        return candidate

    def preflight(self) -> dict[str, Any]:
        inventory = self._scan_source(include_hashes=False)
        usage = shutil.disk_usage(self._usage_path())
        required = (
            int(inventory["total_bytes"])
            + int(inventory["largest_file_bytes"])
            + self.reserve_bytes
        )
        if usage.free < required:
            raise BrokerRecoveryError("broker_recovery_capacity_insufficient")
        return {
            "schema": BROKER_RECOVERY_SCHEMA,
            "status": "PASS",
            "source_total_bytes": inventory["total_bytes"],
            "largest_file_bytes": inventory["largest_file_bytes"],
            "required_free_bytes": required,
            "observed_free_bytes": usage.free,
            "file_count": len(inventory["files"]),
        }

    def _ensure_recovery_root(self) -> None:
        if self.recovery_root.is_symlink():
            raise BrokerRecoveryError("broker_recovery_root_invalid")
        if not self.recovery_root.exists():
            self.recovery_root.mkdir(parents=True, mode=0o700)
        if not self.recovery_root.is_dir():
            raise BrokerRecoveryError("broker_recovery_root_invalid")
        metadata = self.recovery_root.stat()
        if (
            metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise BrokerRecoveryError("broker_recovery_root_metadata_invalid")

    @staticmethod
    def _validate_key(key: str) -> None:
        if _RECOVERY_KEY.fullmatch(key) is None:
            raise BrokerRecoveryError("broker_recovery_key_invalid")

    def _manifest_document(self, key: str, inventory: dict[str, Any]) -> dict[str, Any]:
        source_tree = {
            "root": inventory["root"],
            "files": inventory["files"],
        }
        return {
            "schema": BROKER_RECOVERY_SCHEMA,
            "key": key,
            "source_root": str(self.source_root),
            "source_tree": source_tree,
            "source_tree_sha256": _sha256_bytes(_canonical(source_tree)),
            "total_bytes": inventory["total_bytes"],
            "largest_file_bytes": inventory["largest_file_bytes"],
        }

    def _record_from_manifest(
        self,
        key: str,
        manifest: dict[str, Any],
        manifest_bytes: bytes,
    ) -> dict[str, Any]:
        return {
            "schema": BROKER_RECOVERY_SCHEMA,
            "key": key,
            "manifest_sha256": _sha256_bytes(manifest_bytes),
            "source_tree_sha256": manifest["source_tree_sha256"],
            "total_bytes": manifest["total_bytes"],
            "file_count": len(manifest["source_tree"]["files"]),
        }

    def create(self, key: str) -> dict[str, Any]:
        self._validate_key(key)
        self.preflight()
        self._ensure_recovery_root()
        final = self.recovery_root / key
        if final.exists() or final.is_symlink():
            manifest_path = final / "manifest.json"
            if manifest_path.is_file() and not manifest_path.is_symlink():
                manifest_bytes = manifest_path.read_bytes()
                try:
                    manifest = json.loads(manifest_bytes)
                except json.JSONDecodeError as error:
                    raise BrokerRecoveryError("broker_recovery_manifest_invalid") from error
                record = self._record_from_manifest(key, manifest, manifest_bytes)
                self.verify(record)
                return record
            raise BrokerRecoveryError("broker_recovery_destination_collision")

        staging = self.recovery_root / f".{key}.staging"
        if staging.exists() or staging.is_symlink():
            raise BrokerRecoveryError("broker_recovery_staging_present")
        staging.mkdir(mode=0o700)
        state = staging / "state"
        state.mkdir(mode=0o700)
        try:
            inventory = self._scan_source(include_hashes=True)
            for row in inventory["files"]:
                source = self.source_root / row["name"]
                destination = state / row["name"]
                flags = (
                    os.O_WRONLY
                    | os.O_CREAT
                    | os.O_EXCL
                    | getattr(os, "O_NOFOLLOW", 0)
                )
                descriptor = os.open(destination, flags, 0o600)
                try:
                    source_descriptor = os.open(
                        source,
                        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                    )
                    try:
                        observed = os.fstat(source_descriptor)
                        if not stat.S_ISREG(observed.st_mode):
                            raise BrokerRecoveryError("broker_recovery_source_entry_invalid")
                        with os.fdopen(source_descriptor, "rb", closefd=False) as input_stream:
                            with os.fdopen(descriptor, "wb", closefd=False) as output_stream:
                                shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
                                output_stream.flush()
                                os.fsync(output_stream.fileno())
                    finally:
                        os.close(source_descriptor)
                finally:
                    os.close(descriptor)
                if (
                    destination.stat().st_size != row["size"]
                    or _sha256_file(destination) != row["sha256"]
                ):
                    raise BrokerRecoveryError("broker_recovery_snapshot_verify_failed")
            _fsync_directory(state)
            manifest = self._manifest_document(key, inventory)
            manifest_bytes = (
                json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8") + b"\n"
            )
            manifest_path = staging / "manifest.json"
            descriptor = os.open(
                manifest_path,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0),
                0o600,
            )
            try:
                with os.fdopen(descriptor, "wb", closefd=False) as stream:
                    stream.write(manifest_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                os.close(descriptor)
            _fsync_directory(staging)
            os.replace(staging, final)
            _fsync_directory(self.recovery_root)
            record = self._record_from_manifest(key, manifest, manifest_bytes)
            self.verify(record)
            return record
        except Exception:
            if staging.exists() and not staging.is_symlink():
                shutil.rmtree(staging)
            raise

    def _load_verified_manifest(self, record: dict[str, Any]) -> dict[str, Any]:
        if (
            not isinstance(record, dict)
            or record.get("schema") != BROKER_RECOVERY_SCHEMA
            or not isinstance(record.get("key"), str)
        ):
            raise BrokerRecoveryError("broker_recovery_record_invalid")
        key = record["key"]
        self._validate_key(key)
        directory = self.recovery_root / key
        manifest_path = directory / "manifest.json"
        state = directory / "state"
        if (
            directory.is_symlink()
            or not directory.is_dir()
            or state.is_symlink()
            or not state.is_dir()
            or manifest_path.is_symlink()
            or not manifest_path.is_file()
        ):
            raise BrokerRecoveryError("broker_recovery_snapshot_invalid")
        manifest_bytes = manifest_path.read_bytes()
        if _sha256_bytes(manifest_bytes) != record.get("manifest_sha256"):
            raise BrokerRecoveryError("broker_recovery_manifest_digest_mismatch")
        try:
            manifest = json.loads(manifest_bytes)
        except json.JSONDecodeError as error:
            raise BrokerRecoveryError("broker_recovery_manifest_invalid") from error
        if (
            not isinstance(manifest, dict)
            or manifest.get("schema") != BROKER_RECOVERY_SCHEMA
            or manifest.get("key") != key
            or manifest.get("source_root") != str(self.source_root)
            or manifest.get("source_tree_sha256") != record.get("source_tree_sha256")
        ):
            raise BrokerRecoveryError("broker_recovery_manifest_binding_invalid")
        tree = manifest.get("source_tree")
        rows = tree.get("files") if isinstance(tree, dict) else None
        if not isinstance(rows, list) or not rows:
            raise BrokerRecoveryError("broker_recovery_manifest_shape_invalid")
        expected_names: set[str] = set()
        for row in rows:
            if (
                not isinstance(row, dict)
                or not isinstance(row.get("name"), str)
                or "/" in row["name"]
                or row["name"] in {"", ".", ".."}
                or not isinstance(row.get("size"), int)
                or not isinstance(row.get("mode"), int)
                or not isinstance(row.get("uid"), int)
                or not isinstance(row.get("gid"), int)
                or not isinstance(row.get("sha256"), str)
            ):
                raise BrokerRecoveryError("broker_recovery_manifest_shape_invalid")
            expected_names.add(row["name"])
            snapshot = state / row["name"]
            if (
                snapshot.is_symlink()
                or not snapshot.is_file()
                or snapshot.stat().st_size != row["size"]
                or _sha256_file(snapshot) != row["sha256"]
            ):
                raise BrokerRecoveryError("broker_recovery_snapshot_digest_mismatch")
        if not BROKER_REQUIRED_STATE.issubset(expected_names):
            raise BrokerRecoveryError("broker_recovery_required_state_missing")
        actual_names = {
            path.name
            for path in state.iterdir()
            if path.is_file() and not path.is_symlink()
        }
        if actual_names != expected_names or any(
            path.is_symlink() or not path.is_file()
            for path in state.iterdir()
        ):
            raise BrokerRecoveryError("broker_recovery_snapshot_shape_invalid")
        if _sha256_bytes(_canonical(tree)) != manifest["source_tree_sha256"]:
            raise BrokerRecoveryError("broker_recovery_source_tree_digest_mismatch")
        return manifest

    def verify(self, record: dict[str, Any]) -> dict[str, Any]:
        manifest = self._load_verified_manifest(record)
        return {
            "schema": BROKER_RECOVERY_SCHEMA,
            "status": "PASS",
            "key": manifest["key"],
            "source_tree_sha256": manifest["source_tree_sha256"],
            "total_bytes": manifest["total_bytes"],
            "file_count": len(manifest["source_tree"]["files"]),
        }

    def restore(self, record: dict[str, Any]) -> dict[str, Any]:
        manifest = self._load_verified_manifest(record)
        self._validate_source_root()
        key = manifest["key"]
        state = self.recovery_root / key / "state"
        prefix = f".n3w-broker-restore-{key}-"

        for path in list(self.source_root.iterdir()):
            if path.name.startswith(prefix):
                if path.is_symlink() or not path.is_file():
                    raise BrokerRecoveryError("broker_recovery_restore_temp_invalid")
                path.unlink()
        existing = list(self.source_root.iterdir())
        if any(path.is_symlink() or not path.is_file() for path in existing):
            raise BrokerRecoveryError("broker_recovery_restore_source_shape_invalid")

        expected_names = {
            row["name"] for row in manifest["source_tree"]["files"]
        }
        for row in manifest["source_tree"]["files"]:
            snapshot = state / row["name"]
            descriptor, raw = tempfile.mkstemp(
                prefix=prefix,
                dir=self.source_root,
            )
            temporary = Path(raw)
            try:
                os.fchmod(descriptor, int(row["mode"]))
                current = os.fstat(descriptor)
                if (
                    current.st_uid != int(row["uid"])
                    or current.st_gid != int(row["gid"])
                ):
                    os.fchown(descriptor, int(row["uid"]), int(row["gid"]))
                with snapshot.open("rb") as input_stream:
                    with os.fdopen(descriptor, "wb", closefd=False) as output_stream:
                        shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
                        output_stream.flush()
                        os.fsync(output_stream.fileno())
                os.replace(temporary, self.source_root / row["name"])
                _fsync_directory(self.source_root)
            finally:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                temporary.unlink(missing_ok=True)

        for path in list(self.source_root.iterdir()):
            if path.name not in expected_names:
                if path.is_symlink() or not path.is_file():
                    raise BrokerRecoveryError("broker_recovery_restore_extra_entry_invalid")
                path.unlink()
        _fsync_directory(self.source_root)

        restored = self._scan_source(include_hashes=True)
        restored_tree = {
            "root": restored["root"],
            "files": restored["files"],
        }
        restored_sha = _sha256_bytes(_canonical(restored_tree))
        if restored_sha != manifest["source_tree_sha256"]:
            raise BrokerRecoveryError("broker_recovery_restore_verify_failed")
        return {
            "schema": BROKER_RECOVERY_SCHEMA,
            "status": "PASS",
            "key": key,
            "source_tree_sha256": restored_sha,
            "file_count": len(restored["files"]),
        }


    def retire(self, record: dict[str, Any]) -> dict[str, Any]:
        if (
            not isinstance(record, dict)
            or record.get("schema") != BROKER_RECOVERY_SCHEMA
            or not isinstance(record.get("key"), str)
        ):
            raise BrokerRecoveryError("broker_recovery_record_invalid")
        key = record["key"]
        self._validate_key(key)
        if self.recovery_root.is_symlink():
            raise BrokerRecoveryError("broker_recovery_root_invalid")
        if self.recovery_root.exists():
            if not self.recovery_root.is_dir():
                raise BrokerRecoveryError("broker_recovery_root_invalid")
            root_meta = self.recovery_root.stat()
            if (
                root_meta.st_uid != os.geteuid()
                or stat.S_IMODE(root_meta.st_mode) & 0o077
            ):
                raise BrokerRecoveryError(
                    "broker_recovery_root_metadata_invalid"
                )
        directory = self.recovery_root / key
        if not directory.exists():
            if directory.is_symlink():
                raise BrokerRecoveryError("broker_recovery_snapshot_invalid")
            return {
                "schema": BROKER_RECOVERY_SCHEMA,
                "status": "PASS",
                "key": key,
                "retired": True,
                "already_absent": True,
            }
        self._load_verified_manifest(record)
        if directory.is_symlink() or not directory.is_dir():
            raise BrokerRecoveryError("broker_recovery_snapshot_invalid")
        if {path.name for path in directory.iterdir()} != {
            "manifest.json",
            "state",
        }:
            raise BrokerRecoveryError("broker_recovery_snapshot_shape_invalid")
        shutil.rmtree(directory)
        if directory.exists() or directory.is_symlink():
            raise BrokerRecoveryError("broker_recovery_retire_failed")
        _fsync_directory(self.recovery_root)
        return {
            "schema": BROKER_RECOVERY_SCHEMA,
            "status": "PASS",
            "key": key,
            "retired": True,
            "already_absent": False,
        }
