from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import stat
import threading
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator, Protocol

_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
_KEY_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SCHEMA_VERSION = 2
_RUNTIME_KEY_STATES = {"ACTIVE", "GRACE"}
_KEY_STATES = {"STAGED", "ACTIVE", "GRACE", "REVOKED"}


class RelayAuthorizationAdminError(RuntimeError):
    """Unsafe or unavailable relay-authorization administration state."""


class RelayPathInvalidator(Protocol):
    def __call__(self, *, node_id: str, gateway_id: str) -> object: ...


def _timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _require_id(value: str, code: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise RelayAuthorizationAdminError(code)
    return value


def _state_value(value: object) -> str | None:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) else None


def _require_private(path: Path, *, directory: bool, code: str) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise RelayAuthorizationAdminError(code)
    try:
        info = path.stat()
    except OSError as exc:
        raise RelayAuthorizationAdminError(code) from exc
    valid_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not valid_type or stat.S_IMODE(info.st_mode) & 0o077:
        raise RelayAuthorizationAdminError(code)
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise RelayAuthorizationAdminError(code)


class RelayAuthorizationAdmin:
    """Durable host-only writer for N3-W relay grants and application keys.

    Authorization SQLite, key files, and path/replay state are separate stores.
    Operations therefore use fail-closed ordering and a secret-free recovery
    table; this class makes no cross-store ACID claim.
    """

    def __init__(
        self,
        database: str | Path,
        key_dir: str | Path,
        *,
        node_state: Callable[[str], object | None],
        path_invalidator: RelayPathInvalidator | None = None,
    ) -> None:
        self.database = Path(database).expanduser().absolute()
        self.key_dir = Path(key_dir).expanduser().absolute()
        self.node_state = node_state
        self.path_invalidator = path_invalidator
        self._lock = threading.RLock()
        self._closed = False
        self._prepare_paths()
        self._connection = sqlite3.connect(
            str(self.database),
            isolation_level=None,
            check_same_thread=False,
            timeout=5.0,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA busy_timeout = 5000")
        self._initialize_or_migrate()

    def _prepare_paths(self) -> None:
        if self.database.exists():
            _require_private(
                self.database,
                directory=False,
                code="authorization_store_permissions_invalid",
            )
        else:
            if not self.database.parent.is_dir() or self.database.parent.is_symlink():
                raise RelayAuthorizationAdminError("authorization_store_parent_invalid")
            fd = os.open(self.database, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        os.chmod(self.database, 0o600)

        if self.key_dir.exists():
            _require_private(
                self.key_dir,
                directory=True,
                code="key_directory_permissions_invalid",
            )
        else:
            if not self.key_dir.parent.is_dir() or self.key_dir.parent.is_symlink():
                raise RelayAuthorizationAdminError("key_directory_parent_invalid")
            self.key_dir.mkdir(mode=0o700)
        os.chmod(self.key_dir, 0o700)

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        self._require_open()
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            yield self._connection
        except Exception:
            self._connection.execute("ROLLBACK")
            raise
        else:
            self._connection.execute("COMMIT")

    def _initialize_or_migrate(self) -> None:
        names = {
            row[0]
            for row in self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'n3w_relay_%'"
            ).fetchall()
        }
        v1 = {
            "n3w_relay_meta",
            "n3w_relay_nodes",
            "n3w_relay_gateway_nodes",
            "n3w_relay_key_epochs",
        }
        v2 = v1 | {"n3w_relay_operations"}
        if not names:
            self._create_v2()
        elif names == v1:
            versions = self._connection.execute(
                "SELECT schema_version FROM n3w_relay_meta"
            ).fetchall()
            if len(versions) != 1 or versions[0][0] != 1:
                raise RelayAuthorizationAdminError("authorization_store_schema_mismatch")
            self._migrate_v1()
        elif names == v2:
            versions = self._connection.execute(
                "SELECT schema_version FROM n3w_relay_meta"
            ).fetchall()
            if len(versions) != 1 or versions[0][0] != _SCHEMA_VERSION:
                raise RelayAuthorizationAdminError("authorization_store_schema_mismatch")
        else:
            raise RelayAuthorizationAdminError("authorization_store_schema_mismatch")
        self._require_integrity()

    def _create_v2(self) -> None:
        statements = (
            "CREATE TABLE n3w_relay_meta (schema_version INTEGER NOT NULL)",
            """
            CREATE TABLE n3w_relay_nodes (
                node_id TEXT PRIMARY KEY,
                active INTEGER NOT NULL CHECK (active IN (0, 1))
            )
            """,
            """
            CREATE TABLE n3w_relay_gateway_nodes (
                gateway_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
                PRIMARY KEY (gateway_id, node_id)
            )
            """,
            """
            CREATE TABLE n3w_relay_key_epochs (
                node_id TEXT NOT NULL,
                key_epoch INTEGER NOT NULL CHECK (key_epoch >= 1),
                key_file TEXT NOT NULL,
                enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
                state TEXT NOT NULL CHECK (state IN ('STAGED','ACTIVE','GRACE','REVOKED')),
                key_sha256 TEXT,
                PRIMARY KEY (node_id, key_epoch)
            )
            """,
            """
            CREATE TABLE n3w_relay_operations (
                operation_key TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                node_id TEXT NOT NULL,
                gateway_id TEXT,
                key_epoch INTEGER,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
        )
        with self._transaction() as connection:
            for statement in statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO n3w_relay_meta (schema_version) VALUES (?)",
                (_SCHEMA_VERSION,),
            )
        self._fsync_database()

    def _migrate_v1(self) -> None:
        rows = self._connection.execute(
            "SELECT node_id, key_epoch, key_file, enabled FROM n3w_relay_key_epochs"
        ).fetchall()
        fingerprints: dict[tuple[str, int], str | None] = {}
        for row in rows:
            identity = (str(row["node_id"]), int(row["key_epoch"]))
            if row["enabled"] == 1:
                material = self._read_key(row["key_file"], expected_sha256=None)
                fingerprints[identity] = hashlib.sha256(material).hexdigest()
            else:
                fingerprints[identity] = None
        with self._transaction() as connection:
            connection.execute("ALTER TABLE n3w_relay_key_epochs ADD COLUMN state TEXT")
            connection.execute("ALTER TABLE n3w_relay_key_epochs ADD COLUMN key_sha256 TEXT")
            connection.execute(
                """
                UPDATE n3w_relay_key_epochs
                SET state = CASE WHEN enabled = 1 THEN 'ACTIVE' ELSE 'REVOKED' END
                """
            )
            for (node_id, key_epoch), digest in fingerprints.items():
                connection.execute(
                    """
                    UPDATE n3w_relay_key_epochs SET key_sha256 = ?
                    WHERE node_id = ? AND key_epoch = ?
                    """,
                    (digest, node_id, key_epoch),
                )
            connection.execute(
                """
                CREATE TABLE n3w_relay_operations (
                    operation_key TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    gateway_id TEXT,
                    key_epoch INTEGER,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "UPDATE n3w_relay_meta SET schema_version = ?",
                (_SCHEMA_VERSION,),
            )
        self._fsync_database()

    def _require_integrity(self) -> None:
        row = self._connection.execute("PRAGMA quick_check").fetchone()
        if row is None or row[0] != "ok":
            raise RelayAuthorizationAdminError("authorization_store_corrupt")

    def _require_open(self) -> None:
        if self._closed:
            raise RelayAuthorizationAdminError("authorization_store_unavailable")

    def _require_active_node(self, node_id: str) -> None:
        _require_id(node_id, "node_id_invalid")
        try:
            state = self.node_state(node_id)
        except Exception as exc:
            raise RelayAuthorizationAdminError("registration_state_unavailable") from exc
        if _state_value(state) != "active":
            raise RelayAuthorizationAdminError("node_id_not_active")

    @staticmethod
    def _record_operation(
        connection: sqlite3.Connection,
        *,
        operation_key: str,
        kind: str,
        node_id: str,
        gateway_id: str | None = None,
        key_epoch: int | None = None,
        status: str,
    ) -> None:
        now = _timestamp()
        connection.execute(
            """
            INSERT INTO n3w_relay_operations (
                operation_key, kind, node_id, gateway_id, key_epoch,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(operation_key) DO UPDATE SET
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                operation_key,
                kind,
                node_id,
                gateway_id,
                key_epoch,
                status,
                now,
                now,
            ),
        )

    def grant(self, *, gateway_id: str, node_id: str) -> dict[str, object]:
        gateway_id = _require_id(gateway_id, "gateway_id_invalid")
        node_id = _require_id(node_id, "node_id_invalid")
        self._require_active_node(node_id)
        revoke_key = f"revoke-grant:{gateway_id}:{node_id}"
        pending = self._connection.execute(
            """
            SELECT 1 FROM n3w_relay_operations
            WHERE operation_key = ? AND status = 'AUTH_REVOKED_PATH_PENDING'
            """,
            (revoke_key,),
        ).fetchone()
        if pending is not None:
            raise RelayAuthorizationAdminError("grant_recovery_pending")
        with self._lock, self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO n3w_relay_nodes (node_id, active) VALUES (?, 1)
                ON CONFLICT(node_id) DO UPDATE SET active = 1
                """,
                (node_id,),
            )
            connection.execute(
                """
                INSERT INTO n3w_relay_gateway_nodes (gateway_id, node_id, enabled)
                VALUES (?, ?, 1)
                ON CONFLICT(gateway_id, node_id) DO UPDATE SET enabled = 1
                """,
                (gateway_id, node_id),
            )
            self._record_operation(
                connection,
                operation_key=f"grant:{gateway_id}:{node_id}",
                kind="GRANT",
                node_id=node_id,
                gateway_id=gateway_id,
                status="DONE",
            )
        self._fsync_database()
        return self._result("grant", node_id=node_id, gateway_id=gateway_id)

    def revoke_grant(self, *, gateway_id: str, node_id: str) -> dict[str, object]:
        gateway_id = _require_id(gateway_id, "gateway_id_invalid")
        node_id = _require_id(node_id, "node_id_invalid")
        operation_key = f"revoke-grant:{gateway_id}:{node_id}"
        with self._lock, self._transaction() as connection:
            connection.execute(
                """
                INSERT INTO n3w_relay_gateway_nodes (gateway_id, node_id, enabled)
                VALUES (?, ?, 0)
                ON CONFLICT(gateway_id, node_id) DO UPDATE SET enabled = 0
                """,
                (gateway_id, node_id),
            )
            self._record_operation(
                connection,
                operation_key=operation_key,
                kind="REVOKE_GRANT",
                node_id=node_id,
                gateway_id=gateway_id,
                status="AUTH_REVOKED_PATH_PENDING",
            )
        self._fsync_database()
        return self._finish_path_revoke(operation_key, node_id, gateway_id)

    def _finish_path_revoke(
        self, operation_key: str, node_id: str, gateway_id: str
    ) -> dict[str, object]:
        if self.path_invalidator is None:
            return self._result(
                "revoke_grant",
                node_id=node_id,
                gateway_id=gateway_id,
                recovery_pending=True,
            )
        try:
            self.path_invalidator(node_id=node_id, gateway_id=gateway_id)
        except Exception:
            return self._result(
                "revoke_grant",
                node_id=node_id,
                gateway_id=gateway_id,
                recovery_pending=True,
            )
        with self._lock, self._transaction() as connection:
            self._record_operation(
                connection,
                operation_key=operation_key,
                kind="REVOKE_GRANT",
                node_id=node_id,
                gateway_id=gateway_id,
                status="DONE",
            )
        self._fsync_database()
        return self._result(
            "revoke_grant",
            node_id=node_id,
            gateway_id=gateway_id,
        )

    def stage_key(self, *, node_id: str, key_material: bytes) -> dict[str, object]:
        node_id = _require_id(node_id, "node_id_invalid")
        self._require_active_node(node_id)
        if not isinstance(key_material, bytes) or len(key_material) != 32:
            raise RelayAuthorizationAdminError("key_material_invalid")
        digest = hashlib.sha256(key_material).hexdigest()
        with self._lock, self._transaction() as connection:
            row = connection.execute(
                "SELECT MAX(key_epoch) FROM n3w_relay_key_epochs WHERE node_id = ?",
                (node_id,),
            ).fetchone()
            key_epoch = int(row[0] or 0) + 1
            key_file = f"{node_id}-epoch-{key_epoch}.key"
            connection.execute(
                """
                INSERT INTO n3w_relay_nodes (node_id, active) VALUES (?, 1)
                ON CONFLICT(node_id) DO UPDATE SET active = 1
                """,
                (node_id,),
            )
            connection.execute(
                """
                INSERT INTO n3w_relay_key_epochs (
                    node_id, key_epoch, key_file, enabled, state, key_sha256
                ) VALUES (?, ?, ?, 0, 'STAGED', ?)
                """,
                (node_id, key_epoch, key_file, digest),
            )
            self._record_operation(
                connection,
                operation_key=f"stage-key:{node_id}:{key_epoch}",
                kind="STAGE_KEY",
                node_id=node_id,
                key_epoch=key_epoch,
                status="FILE_PENDING",
            )
        self._fsync_database()
        try:
            self._write_key(key_file, key_material)
        except Exception as exc:
            raise RelayAuthorizationAdminError("key_file_write_failed") from exc
        with self._lock, self._transaction() as connection:
            self._record_operation(
                connection,
                operation_key=f"stage-key:{node_id}:{key_epoch}",
                kind="STAGE_KEY",
                node_id=node_id,
                key_epoch=key_epoch,
                status="DONE",
            )
        self._fsync_database()
        return self._result("stage_key", node_id=node_id, key_epoch=key_epoch)

    def activate_key(self, *, node_id: str, key_epoch: int) -> dict[str, object]:
        node_id = _require_id(node_id, "node_id_invalid")
        self._require_active_node(node_id)
        self._require_epoch(key_epoch)
        with self._lock:
            row = self._key_row(node_id, key_epoch)
            if row["state"] == "ACTIVE":
                return self._result("activate_key", node_id=node_id, key_epoch=key_epoch)
            if row["state"] != "STAGED":
                raise RelayAuthorizationAdminError("key_epoch_not_staged")
            if self._connection.execute(
                "SELECT 1 FROM n3w_relay_key_epochs WHERE node_id=? AND state='GRACE'",
                (node_id,),
            ).fetchone():
                raise RelayAuthorizationAdminError("rotation_already_in_progress")
            self._read_key(row["key_file"], expected_sha256=row["key_sha256"])
            with self._transaction() as connection:
                connection.execute(
                    """
                    UPDATE n3w_relay_key_epochs SET state='GRACE', enabled=1
                    WHERE node_id=? AND state='ACTIVE'
                    """,
                    (node_id,),
                )
                connection.execute(
                    """
                    UPDATE n3w_relay_key_epochs SET state='ACTIVE', enabled=1
                    WHERE node_id=? AND key_epoch=? AND state='STAGED'
                    """,
                    (node_id, key_epoch),
                )
                self._record_operation(
                    connection,
                    operation_key=f"activate-key:{node_id}:{key_epoch}",
                    kind="ACTIVATE_KEY",
                    node_id=node_id,
                    key_epoch=key_epoch,
                    status="DONE",
                )
        self._fsync_database()
        return self._result("activate_key", node_id=node_id, key_epoch=key_epoch)

    def rollback_rotation(self, *, node_id: str, key_epoch: int) -> dict[str, object]:
        node_id = _require_id(node_id, "node_id_invalid")
        self._require_epoch(key_epoch)
        with self._lock, self._transaction() as connection:
            current = self._key_row(node_id, key_epoch)
            if current["state"] == "REVOKED":
                return self._result(
                    "rollback_rotation", node_id=node_id, key_epoch=key_epoch
                )
            if current["state"] != "ACTIVE":
                raise RelayAuthorizationAdminError("rotation_not_active")
            grace = connection.execute(
                """
                SELECT key_epoch FROM n3w_relay_key_epochs
                WHERE node_id=? AND state='GRACE'
                ORDER BY key_epoch DESC LIMIT 1
                """,
                (node_id,),
            ).fetchone()
            if grace is None:
                raise RelayAuthorizationAdminError("rotation_grace_epoch_missing")
            connection.execute(
                """
                UPDATE n3w_relay_key_epochs SET state='REVOKED', enabled=0
                WHERE node_id=? AND key_epoch=?
                """,
                (node_id, key_epoch),
            )
            connection.execute(
                """
                UPDATE n3w_relay_key_epochs SET state='ACTIVE', enabled=1
                WHERE node_id=? AND key_epoch=?
                """,
                (node_id, grace["key_epoch"]),
            )
            self._record_operation(
                connection,
                operation_key=f"rollback-key:{node_id}:{key_epoch}",
                kind="ROLLBACK_KEY",
                node_id=node_id,
                key_epoch=key_epoch,
                status="DONE",
            )
        self._fsync_database()
        self._unlink_key_for_revoked(node_id, key_epoch)
        return self._result("rollback_rotation", node_id=node_id, key_epoch=key_epoch)

    def revoke_key(self, *, node_id: str, key_epoch: int) -> dict[str, object]:
        node_id = _require_id(node_id, "node_id_invalid")
        self._require_epoch(key_epoch)
        with self._lock, self._transaction() as connection:
            self._key_row(node_id, key_epoch)
            connection.execute(
                """
                UPDATE n3w_relay_key_epochs SET state='REVOKED', enabled=0
                WHERE node_id=? AND key_epoch=?
                """,
                (node_id, key_epoch),
            )
            self._record_operation(
                connection,
                operation_key=f"revoke-key:{node_id}:{key_epoch}",
                kind="REVOKE_KEY",
                node_id=node_id,
                key_epoch=key_epoch,
                status="DONE",
            )
        self._fsync_database()
        self._unlink_key_for_revoked(node_id, key_epoch)
        return self._result("revoke_key", node_id=node_id, key_epoch=key_epoch)

    def recover(self) -> dict[str, object]:
        recovered = 0
        rows = self._connection.execute(
            """
            SELECT * FROM n3w_relay_operations
            WHERE status NOT IN ('DONE','RECOVERED')
            ORDER BY created_at, operation_key
            """
        ).fetchall()
        for row in rows:
            if row["kind"] == "REVOKE_GRANT":
                result = self._finish_path_revoke(
                    row["operation_key"], row["node_id"], row["gateway_id"]
                )
                recovered += int(result["recovery_pending"] is False)
                continue
            if row["kind"] != "STAGE_KEY" or row["status"] != "FILE_PENDING":
                continue
            epoch = self._key_row(row["node_id"], row["key_epoch"])
            try:
                self._read_key(
                    epoch["key_file"], expected_sha256=epoch["key_sha256"]
                )
            except RelayAuthorizationAdminError:
                with self._lock, self._transaction() as connection:
                    connection.execute(
                        """
                        UPDATE n3w_relay_key_epochs SET state='REVOKED', enabled=0
                        WHERE node_id=? AND key_epoch=?
                        """,
                        (row["node_id"], row["key_epoch"]),
                    )
            with self._lock, self._transaction() as connection:
                self._record_operation(
                    connection,
                    operation_key=row["operation_key"],
                    kind="STAGE_KEY",
                    node_id=row["node_id"],
                    key_epoch=row["key_epoch"],
                    status="RECOVERED",
                )
            recovered += 1
        self._cleanup_revoked_keys()
        self._fsync_database()
        return {
            "schema": "gh.n3w-relay-authorization-recovery/1",
            "status": "passed",
            "recovered_operation_count": recovered,
            "secret_values_included": False,
        }

    def audit(self) -> dict[str, object]:
        self._require_integrity()
        counts = {state: 0 for state in _KEY_STATES}
        for row in self._connection.execute(
            "SELECT state, enabled, key_file, key_sha256 FROM n3w_relay_key_epochs"
        ).fetchall():
            state = row["state"]
            if state not in counts or row["enabled"] != int(state in _RUNTIME_KEY_STATES):
                raise RelayAuthorizationAdminError("authorization_store_corrupt")
            counts[state] += 1
            if state in _RUNTIME_KEY_STATES:
                self._read_key(row["key_file"], expected_sha256=row["key_sha256"])
        pending = self._connection.execute(
            """
            SELECT COUNT(*) FROM n3w_relay_operations
            WHERE status NOT IN ('DONE','RECOVERED')
            """
        ).fetchone()[0]
        grants = self._connection.execute(
            "SELECT COUNT(*) FROM n3w_relay_gateway_nodes WHERE enabled=1"
        ).fetchone()[0]
        return {
            "schema": "gh.n3w-relay-authorization-admin-audit/1",
            "status": "passed",
            "schema_version": _SCHEMA_VERSION,
            "enabled_gateway_grant_count": int(grants),
            "staged_key_epoch_count": counts["STAGED"],
            "active_key_epoch_count": counts["ACTIVE"],
            "grace_key_epoch_count": counts["GRACE"],
            "revoked_key_epoch_count": counts["REVOKED"],
            "pending_operation_count": int(pending),
            "secret_values_included": False,
            "mutated": False,
        }

    def _key_row(self, node_id: str, key_epoch: int) -> sqlite3.Row:
        row = self._connection.execute(
            "SELECT * FROM n3w_relay_key_epochs WHERE node_id=? AND key_epoch=?",
            (node_id, key_epoch),
        ).fetchone()
        if row is None:
            raise RelayAuthorizationAdminError("key_epoch_unknown")
        return row

    @staticmethod
    def _require_epoch(key_epoch: int) -> None:
        if not isinstance(key_epoch, int) or isinstance(key_epoch, bool) or key_epoch < 1:
            raise RelayAuthorizationAdminError("key_epoch_invalid")

    def _directory_fd(self) -> int:
        flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            flags |= os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(self.key_dir, flags)
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
            os.close(fd)
            raise RelayAuthorizationAdminError("key_directory_permissions_invalid")
        return fd

    def _write_key(self, key_file: str, key_material: bytes) -> None:
        if _KEY_FILE.fullmatch(key_file) is None:
            raise RelayAuthorizationAdminError("key_file_reference_invalid")
        dir_fd = self._directory_fd()
        fd: int | None = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(key_file, flags, 0o600, dir_fd=dir_fd)
            offset = 0
            while offset < len(key_material):
                offset += os.write(fd, key_material[offset:])
            os.fsync(fd)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
                raise RelayAuthorizationAdminError("key_file_permissions_invalid")
            os.fsync(dir_fd)
        finally:
            if fd is not None:
                os.close(fd)
            os.close(dir_fd)

    def _read_key(self, key_file: str, *, expected_sha256: str | None) -> bytes:
        if not isinstance(key_file, str) or _KEY_FILE.fullmatch(key_file) is None:
            raise RelayAuthorizationAdminError("key_file_reference_invalid")
        dir_fd = self._directory_fd()
        fd: int | None = None
        try:
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(key_file, flags, dir_fd=dir_fd)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
                raise RelayAuthorizationAdminError("key_file_permissions_invalid")
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = os.read(fd, 64)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if total > 32:
                    break
        except OSError as exc:
            raise RelayAuthorizationAdminError("key_file_unavailable") from exc
        finally:
            if fd is not None:
                os.close(fd)
            os.close(dir_fd)
        material = b"".join(chunks)
        if len(material) != 32:
            raise RelayAuthorizationAdminError("key_material_invalid")
        if expected_sha256 is not None and hashlib.sha256(material).hexdigest() != expected_sha256:
            raise RelayAuthorizationAdminError("key_material_binding_invalid")
        return material

    def _unlink_key_for_revoked(self, node_id: str, key_epoch: int) -> None:
        row = self._key_row(node_id, key_epoch)
        if row["state"] == "REVOKED":
            self._unlink(row["key_file"])

    def _cleanup_revoked_keys(self) -> None:
        for row in self._connection.execute(
            "SELECT key_file FROM n3w_relay_key_epochs WHERE state='REVOKED'"
        ).fetchall():
            self._unlink(row["key_file"])

    def _unlink(self, key_file: str) -> None:
        if not isinstance(key_file, str) or _KEY_FILE.fullmatch(key_file) is None:
            return
        dir_fd = self._directory_fd()
        try:
            try:
                os.unlink(key_file, dir_fd=dir_fd)
            except FileNotFoundError:
                pass
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    def _fsync_database(self) -> None:
        fd = os.open(self.database, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @staticmethod
    def _result(
        operation: str,
        *,
        node_id: str,
        gateway_id: str | None = None,
        key_epoch: int | None = None,
        recovery_pending: bool = False,
    ) -> dict[str, object]:
        return {
            "schema": "gh.n3w-relay-authorization-admin-result/1",
            "status": "passed",
            "operation": operation,
            "node_id": node_id,
            "gateway_id": gateway_id,
            "key_epoch": key_epoch,
            "recovery_pending": recovery_pending,
            "secret_values_included": False,
        }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._connection.close()
            self._closed = True

    def __enter__(self) -> RelayAuthorizationAdmin:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
