from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import stat
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

from .n3w_relay_ingress import RelayIngressRejected

_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
_KEY_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RUNTIME_KEY_STATES = {"ACTIVE", "GRACE"}


class NodeApplicationKeyStoreUnavailable(RuntimeError):
    """Raised when the transitional per-node application-key store is unusable."""


def _require_private_path(path: Path, *, directory: bool, code: str) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise NodeApplicationKeyStoreUnavailable(code)
    try:
        info = path.stat()
    except OSError as error:
        raise NodeApplicationKeyStoreUnavailable(code) from error
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise NodeApplicationKeyStoreUnavailable(code)
    elif not stat.S_ISREG(info.st_mode):
        raise NodeApplicationKeyStoreUnavailable(code)
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise NodeApplicationKeyStoreUnavailable(code)
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise NodeApplicationKeyStoreUnavailable(code)


class SqliteNodeApplicationKeyProvider:
    """Migration adapter for node application keys without gateway grants.

    The adapter intentionally reuses the existing private node/key tables while
    ignoring `n3w_relay_gateway_nodes`. It is read-only and can be deleted once the
    old finite-grant store is retired after clean E2E.
    """

    def __init__(self, database: str | Path, key_dir: str | Path) -> None:
        self.database = Path(database).expanduser()
        self.key_dir = Path(key_dir).expanduser()
        self._lock = threading.RLock()
        self._closed = False
        try:
            _require_private_path(
                self.database,
                directory=False,
                code="node_key_store_permissions_invalid",
            )
            _require_private_path(
                self.key_dir,
                directory=True,
                code="node_key_directory_permissions_invalid",
            )
            uri = f"{self.database.resolve().as_uri()}?mode=ro"
            self._connection = sqlite3.connect(
                uri,
                uri=True,
                isolation_level=None,
                check_same_thread=False,
                timeout=5.0,
            )
            self._connection.row_factory = sqlite3.Row
            self._schema_version = self._require_schema()
            self._require_integrity()
        except (OSError, sqlite3.Error, NodeApplicationKeyStoreUnavailable) as error:
            connection = getattr(self, "_connection", None)
            if connection is not None:
                connection.close()
            self._closed = True
            if isinstance(error, NodeApplicationKeyStoreUnavailable):
                raise
            raise NodeApplicationKeyStoreUnavailable("node_key_store_unavailable") from error

    def _require_schema(self) -> int:
        versions = self._connection.execute(
            "SELECT schema_version FROM n3w_relay_meta"
        ).fetchall()
        if len(versions) != 1 or versions[0]["schema_version"] not in {1, 2}:
            raise NodeApplicationKeyStoreUnavailable("node_key_store_schema_mismatch")
        names = {
            row["name"]
            for row in self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        required = {"n3w_relay_nodes", "n3w_relay_key_epochs"}
        if not required <= names:
            raise NodeApplicationKeyStoreUnavailable("node_key_store_schema_mismatch")
        return int(versions[0]["schema_version"])

    def _require_integrity(self) -> None:
        row = self._connection.execute("PRAGMA quick_check").fetchone()
        if row is None or row[0] != "ok":
            raise NodeApplicationKeyStoreUnavailable("node_key_store_corrupt")

    def _require_open(self) -> None:
        if self._closed:
            raise NodeApplicationKeyStoreUnavailable("node_key_store_unavailable")

    def _load_key_file(self, key_file: object, expected_sha256: object = None) -> bytes:
        if not isinstance(key_file, str) or _KEY_FILE.fullmatch(key_file) is None:
            raise NodeApplicationKeyStoreUnavailable("node_key_file_reference_invalid")
        if expected_sha256 is not None and (
            not isinstance(expected_sha256, str) or _SHA256.fullmatch(expected_sha256) is None
        ):
            raise NodeApplicationKeyStoreUnavailable("node_key_store_corrupt")

        directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        file_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        dir_fd: int | None = None
        fd: int | None = None
        try:
            dir_fd = os.open(self.key_dir, directory_flags)
            directory_info = os.fstat(dir_fd)
            if (
                not stat.S_ISDIR(directory_info.st_mode)
                or stat.S_IMODE(directory_info.st_mode) & 0o077
                or (hasattr(os, "getuid") and directory_info.st_uid != os.getuid())
            ):
                raise NodeApplicationKeyStoreUnavailable("node_key_directory_permissions_invalid")
            fd = os.open(key_file, file_flags, dir_fd=dir_fd)
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) & 0o077
                or (hasattr(os, "getuid") and info.st_uid != os.getuid())
            ):
                raise NodeApplicationKeyStoreUnavailable("node_key_file_permissions_invalid")
            chunks: list[bytes] = []
            total = 0
            while total <= 32:
                chunk = os.read(fd, 33 - total)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            material = b"".join(chunks)
        except OSError as error:
            raise NodeApplicationKeyStoreUnavailable("node_key_file_unavailable") from error
        finally:
            if fd is not None:
                os.close(fd)
            if dir_fd is not None:
                os.close(dir_fd)

        if len(material) != 32:
            raise NodeApplicationKeyStoreUnavailable("node_key_material_invalid")
        if expected_sha256 is not None and hashlib.sha256(material).hexdigest() != expected_sha256:
            raise NodeApplicationKeyStoreUnavailable("node_key_material_binding_invalid")
        return material

    def resolve_key(self, *, node_id: str, key_epoch: int) -> bytes:
        if not isinstance(node_id, str) or _ID.fullmatch(node_id) is None:
            raise RelayIngressRejected("outer_identity_invalid", node_id=node_id)
        if not isinstance(key_epoch, int) or isinstance(key_epoch, bool) or key_epoch < 1:
            raise RelayIngressRejected("key_epoch_rejected", node_id=node_id)
        with self._lock:
            self._require_open()
            try:
                node = self._connection.execute(
                    "SELECT active FROM n3w_relay_nodes WHERE node_id = ?",
                    (node_id,),
                ).fetchone()
                if node is None or node["active"] != 1:
                    raise RelayIngressRejected("node_not_active", node_id=node_id)
                if self._schema_version == 1:
                    epoch = self._connection.execute(
                        """
                        SELECT key_file, enabled
                        FROM n3w_relay_key_epochs
                        WHERE node_id = ? AND key_epoch = ?
                        """,
                        (node_id, key_epoch),
                    ).fetchone()
                    accepted = epoch is not None and epoch["enabled"] == 1
                    expected_sha256 = None
                else:
                    epoch = self._connection.execute(
                        """
                        SELECT key_file, enabled, state, key_sha256
                        FROM n3w_relay_key_epochs
                        WHERE node_id = ? AND key_epoch = ?
                        """,
                        (node_id, key_epoch),
                    ).fetchone()
                    accepted = (
                        epoch is not None
                        and epoch["enabled"] == 1
                        and epoch["state"] in _RUNTIME_KEY_STATES
                    )
                    expected_sha256 = epoch["key_sha256"] if epoch is not None else None
                if not accepted or epoch is None:
                    raise RelayIngressRejected("key_epoch_rejected", node_id=node_id)
                return self._load_key_file(epoch["key_file"], expected_sha256)
            except sqlite3.Error as error:
                raise RelayIngressRejected("node_key_store_unavailable", node_id=node_id) from error
            except NodeApplicationKeyStoreUnavailable as error:
                raise RelayIngressRejected(str(error), node_id=node_id) from error

    def audit(self) -> dict[str, int | str | bool]:
        with self._lock:
            self._require_open()
            self._require_integrity()
            active_nodes = int(
                self._connection.execute(
                    "SELECT COUNT(*) FROM n3w_relay_nodes WHERE active = 1"
                ).fetchone()[0]
            )
            return {
                "schema": "gh.n3w-node-application-key-audit/1",
                "status": "passed",
                "active_node_count": active_nodes,
                "gateway_grant_dependency": False,
                "read_only": True,
            }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._connection.close()
            self._closed = True

    def __enter__(self) -> SqliteNodeApplicationKeyProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

class SqliteNodeApplicationKeyAdmin:
    """Grant-free writer for per-node N3-W application keys.

    This writer shares only the node/key tables consumed by
    SqliteNodeApplicationKeyProvider. It never creates, reads, or mutates
    gateway grants or path authority.
    """

    _SCHEMA_VERSION = 2
    _KEY_STATES = {"STAGED", "ACTIVE", "GRACE", "REVOKED"}

    def __init__(
        self,
        database: str | Path,
        key_dir: str | Path,
        *,
        node_state: Callable[[str], object | None],
    ) -> None:
        self.database = Path(database).expanduser()
        self.key_dir = Path(key_dir).expanduser()
        self.node_state = node_state
        self._lock = threading.RLock()
        self._closed = False

        self._prepare_paths()

        try:
            self._connection = sqlite3.connect(
                str(self.database),
                isolation_level=None,
                check_same_thread=False,
                timeout=5.0,
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA busy_timeout = 5000")
            self._initialize_schema()
            self._require_integrity()
            self.recover()
        except Exception:
            connection = getattr(self, "_connection", None)
            if connection is not None:
                connection.close()
            self._closed = True
            raise

    @staticmethod
    def _state_value(value: object) -> str | None:
        raw = getattr(value, "value", value)
        return raw if isinstance(raw, str) else None

    @staticmethod
    def _require_private_parent(path: Path, *, code: str) -> None:
        if (
            not path.is_absolute()
            or path.is_symlink()
            or not path.is_dir()
        ):
            raise NodeApplicationKeyStoreUnavailable(code)

        info = path.stat()
        if (
            stat.S_IMODE(info.st_mode) & 0o077
            or (
                hasattr(os, "getuid")
                and info.st_uid != os.getuid()
            )
        ):
            raise NodeApplicationKeyStoreUnavailable(code)

    def _prepare_paths(self) -> None:
        if not self.database.is_absolute() or not self.key_dir.is_absolute():
            raise NodeApplicationKeyStoreUnavailable(
                "node_key_store_path_invalid"
            )

        if self.database.exists():
            _require_private_path(
                self.database,
                directory=False,
                code="node_key_store_permissions_invalid",
            )
        else:
            self._require_private_parent(
                self.database.parent,
                code="node_key_store_parent_invalid",
            )
            fd = os.open(
                self.database,
                os.O_RDWR | os.O_CREAT | os.O_EXCL,
                0o600,
            )
            os.close(fd)

        os.chmod(self.database, 0o600)

        if self.key_dir.exists():
            _require_private_path(
                self.key_dir,
                directory=True,
                code="node_key_directory_permissions_invalid",
            )
        else:
            self._require_private_parent(
                self.key_dir.parent,
                code="node_key_directory_parent_invalid",
            )
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

    def _initialize_schema(self) -> None:
        names = {
            row["name"]
            for row in self._connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

        required = {
            "n3w_relay_meta",
            "n3w_relay_nodes",
            "n3w_relay_key_epochs",
        }

        if not (required & names):
            with self._transaction() as connection:
                connection.execute(
                    "CREATE TABLE n3w_relay_meta "
                    "(schema_version INTEGER NOT NULL)"
                )
                connection.execute(
                    """
                    CREATE TABLE n3w_relay_nodes (
                        node_id TEXT PRIMARY KEY,
                        active INTEGER NOT NULL
                            CHECK (active IN (0,1))
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE n3w_relay_key_epochs (
                        node_id TEXT NOT NULL,
                        key_epoch INTEGER NOT NULL
                            CHECK (key_epoch >= 1),
                        key_file TEXT NOT NULL,
                        enabled INTEGER NOT NULL
                            CHECK (enabled IN (0,1)),
                        state TEXT NOT NULL
                            CHECK (
                                state IN (
                                    'STAGED',
                                    'ACTIVE',
                                    'GRACE',
                                    'REVOKED'
                                )
                            ),
                        key_sha256 TEXT NOT NULL,
                        PRIMARY KEY (node_id,key_epoch)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE n3w_node_key_operations (
                        operation_key TEXT PRIMARY KEY,
                        node_id TEXT NOT NULL,
                        key_epoch INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL
                            DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL
                            DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO n3w_relay_meta(schema_version) VALUES (?)",
                    (self._SCHEMA_VERSION,),
                )
            self._fsync_database()
            return

        if not required <= names:
            raise NodeApplicationKeyStoreUnavailable(
                "node_key_store_schema_mismatch"
            )

        versions = self._connection.execute(
            "SELECT schema_version FROM n3w_relay_meta"
        ).fetchall()

        if (
            len(versions) != 1
            or versions[0]["schema_version"] != self._SCHEMA_VERSION
        ):
            raise NodeApplicationKeyStoreUnavailable(
                "node_key_store_schema_mismatch"
            )

        columns = {
            row["name"]
            for row in self._connection.execute(
                "PRAGMA table_info(n3w_relay_key_epochs)"
            ).fetchall()
        }

        if not {
            "node_id",
            "key_epoch",
            "key_file",
            "enabled",
            "state",
            "key_sha256",
        } <= columns:
            raise NodeApplicationKeyStoreUnavailable(
                "node_key_store_schema_mismatch"
            )

        if "n3w_node_key_operations" not in names:
            with self._transaction() as connection:
                connection.execute(
                    """
                    CREATE TABLE n3w_node_key_operations (
                        operation_key TEXT PRIMARY KEY,
                        node_id TEXT NOT NULL,
                        key_epoch INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL
                            DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL
                            DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            self._fsync_database()

    def _require_integrity(self) -> None:
        row = self._connection.execute(
            "PRAGMA quick_check"
        ).fetchone()
        if row is None or row[0] != "ok":
            raise NodeApplicationKeyStoreUnavailable(
                "node_key_store_corrupt"
            )

    def _require_open(self) -> None:
        if self._closed:
            raise NodeApplicationKeyStoreUnavailable(
                "node_key_store_unavailable"
            )

    def _require_active_node(self, node_id: str) -> str:
        if not isinstance(node_id, str) or _ID.fullmatch(node_id) is None:
            raise NodeApplicationKeyStoreUnavailable("node_id_invalid")

        try:
            state = self.node_state(node_id)
        except Exception as error:
            raise NodeApplicationKeyStoreUnavailable(
                "registration_state_unavailable"
            ) from error

        if self._state_value(state) != "active":
            raise NodeApplicationKeyStoreUnavailable(
                "node_id_not_active"
            )

        return node_id

    @staticmethod
    def _require_epoch(key_epoch: object) -> int:
        if (
            not isinstance(key_epoch, int)
            or isinstance(key_epoch, bool)
            or key_epoch < 1
        ):
            raise NodeApplicationKeyStoreUnavailable(
                "key_epoch_invalid"
            )
        return key_epoch

    def _key_row(
        self,
        node_id: str,
        key_epoch: int,
    ) -> sqlite3.Row:
        row = self._connection.execute(
            """
            SELECT *
            FROM n3w_relay_key_epochs
            WHERE node_id=? AND key_epoch=?
            """,
            (node_id, key_epoch),
        ).fetchone()

        if row is None:
            raise NodeApplicationKeyStoreUnavailable(
                "key_epoch_unknown"
            )

        return row

    @staticmethod
    def _operation_key(node_id: str, key_epoch: int) -> str:
        return f"stage-key:{node_id}:{key_epoch}"

    def _record_operation(
        self,
        connection: sqlite3.Connection,
        *,
        node_id: str,
        key_epoch: int,
        status: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO n3w_node_key_operations(
                operation_key,
                node_id,
                key_epoch,
                status
            )
            VALUES (?,?,?,?)
            ON CONFLICT(operation_key) DO UPDATE SET
                status=excluded.status,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                self._operation_key(node_id, key_epoch),
                node_id,
                key_epoch,
                status,
            ),
        )

    def _directory_fd(self) -> int:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )

        try:
            fd = os.open(self.key_dir, flags)
        except OSError as error:
            raise NodeApplicationKeyStoreUnavailable(
                "node_key_directory_permissions_invalid"
            ) from error

        info = os.fstat(fd)

        if (
            not stat.S_ISDIR(info.st_mode)
            or stat.S_IMODE(info.st_mode) & 0o077
            or (
                hasattr(os, "getuid")
                and info.st_uid != os.getuid()
            )
        ):
            os.close(fd)
            raise NodeApplicationKeyStoreUnavailable(
                "node_key_directory_permissions_invalid"
            )

        return fd

    def _write_key(
        self,
        key_file: str,
        key_material: bytes,
    ) -> None:
        if _KEY_FILE.fullmatch(key_file) is None:
            raise NodeApplicationKeyStoreUnavailable(
                "node_key_file_reference_invalid"
            )

        dir_fd = self._directory_fd()
        fd: int | None = None

        try:
            flags = (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0)
            )

            fd = os.open(
                key_file,
                flags,
                0o600,
                dir_fd=dir_fd,
            )

            offset = 0
            while offset < len(key_material):
                offset += os.write(
                    fd,
                    key_material[offset:],
                )

            os.fsync(fd)

            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) != 0o600
                or (
                    hasattr(os, "getuid")
                    and info.st_uid != os.getuid()
                )
            ):
                raise NodeApplicationKeyStoreUnavailable(
                    "node_key_file_permissions_invalid"
                )

            os.fsync(dir_fd)
        except Exception:
            with suppress(FileNotFoundError):
                os.unlink(key_file, dir_fd=dir_fd)
                os.fsync(dir_fd)
            raise
        finally:
            if fd is not None:
                os.close(fd)
            os.close(dir_fd)

    def _read_admin_key(
        self,
        key_file: object,
        *,
        expected_sha256: object,
    ) -> bytes:
        if (
            not isinstance(key_file, str)
            or _KEY_FILE.fullmatch(key_file) is None
        ):
            raise NodeApplicationKeyStoreUnavailable(
                "node_key_file_reference_invalid"
            )

        if (
            not isinstance(expected_sha256, str)
            or _SHA256.fullmatch(expected_sha256) is None
        ):
            raise NodeApplicationKeyStoreUnavailable(
                "node_key_material_binding_invalid"
            )

        dir_fd = self._directory_fd()
        fd: int | None = None

        try:
            fd = os.open(
                key_file,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=dir_fd,
            )

            info = os.fstat(fd)

            if (
                not stat.S_ISREG(info.st_mode)
                or stat.S_IMODE(info.st_mode) & 0o077
                or (
                    hasattr(os, "getuid")
                    and info.st_uid != os.getuid()
                )
            ):
                raise NodeApplicationKeyStoreUnavailable(
                    "node_key_file_permissions_invalid"
                )

            material = b""
            while len(material) <= 32:
                chunk = os.read(
                    fd,
                    33 - len(material),
                )
                if not chunk:
                    break
                material += chunk
        except OSError as error:
            raise NodeApplicationKeyStoreUnavailable(
                "node_key_file_unavailable"
            ) from error
        finally:
            if fd is not None:
                os.close(fd)
            os.close(dir_fd)

        if len(material) != 32:
            raise NodeApplicationKeyStoreUnavailable(
                "node_key_material_invalid"
            )

        if hashlib.sha256(material).hexdigest() != expected_sha256:
            raise NodeApplicationKeyStoreUnavailable(
                "node_key_material_binding_invalid"
            )

        return material

    def _unlink_key(self, key_file: object) -> None:
        if (
            not isinstance(key_file, str)
            or _KEY_FILE.fullmatch(key_file) is None
        ):
            return

        dir_fd = self._directory_fd()

        try:
            with suppress(FileNotFoundError):
                os.unlink(key_file, dir_fd=dir_fd)
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    def _fsync_database(self) -> None:
        fd = os.open(self.database, os.O_RDONLY)

        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def stage_key(
        self,
        *,
        node_id: str,
        key_material: bytes,
    ) -> dict[str, object]:
        node_id = self._require_active_node(node_id)

        if (
            not isinstance(key_material, bytes)
            or len(key_material) != 32
        ):
            raise NodeApplicationKeyStoreUnavailable(
                "key_material_invalid"
            )

        digest = hashlib.sha256(key_material).hexdigest()

        with self._lock:
            maximum = self._connection.execute(
                """
                SELECT MAX(key_epoch)
                FROM n3w_relay_key_epochs
                WHERE node_id=?
                """,
                (node_id,),
            ).fetchone()[0]

            key_epoch = int(maximum or 0) + 1
            key_file = f"{node_id}-epoch-{key_epoch}.key"

            with self._transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO n3w_relay_nodes(node_id,active)
                    VALUES (?,1)
                    ON CONFLICT(node_id) DO UPDATE SET active=1
                    """,
                    (node_id,),
                )
                connection.execute(
                    """
                    INSERT INTO n3w_relay_key_epochs(
                        node_id,
                        key_epoch,
                        key_file,
                        enabled,
                        state,
                        key_sha256
                    )
                    VALUES (?,?,?,0,'STAGED',?)
                    """,
                    (
                        node_id,
                        key_epoch,
                        key_file,
                        digest,
                    ),
                )
                self._record_operation(
                    connection,
                    node_id=node_id,
                    key_epoch=key_epoch,
                    status="FILE_PENDING",
                )

            self._fsync_database()

            try:
                self._write_key(
                    key_file,
                    key_material,
                )
            except Exception as error:
                with self._transaction() as connection:
                    connection.execute(
                        """
                        UPDATE n3w_relay_key_epochs
                        SET state='REVOKED',enabled=0
                        WHERE node_id=? AND key_epoch=?
                        """,
                        (node_id, key_epoch),
                    )
                    self._record_operation(
                        connection,
                        node_id=node_id,
                        key_epoch=key_epoch,
                        status="RECOVERED",
                    )
                self._fsync_database()
                raise NodeApplicationKeyStoreUnavailable(
                    "node_key_file_write_failed"
                ) from error

            with self._transaction() as connection:
                self._record_operation(
                    connection,
                    node_id=node_id,
                    key_epoch=key_epoch,
                    status="DONE",
                )

            self._fsync_database()

        return self._result(
            "stage_key",
            node_id=node_id,
            key_epoch=key_epoch,
        )

    def activate_key(
        self,
        *,
        node_id: str,
        key_epoch: int,
    ) -> dict[str, object]:
        node_id = self._require_active_node(node_id)
        key_epoch = self._require_epoch(key_epoch)

        with self._lock:
            row = self._key_row(
                node_id,
                key_epoch,
            )

            if row["state"] == "ACTIVE":
                return self._result(
                    "activate_key",
                    node_id=node_id,
                    key_epoch=key_epoch,
                )

            if row["state"] != "STAGED":
                raise NodeApplicationKeyStoreUnavailable(
                    "key_epoch_not_staged"
                )

            grace = self._connection.execute(
                """
                SELECT 1
                FROM n3w_relay_key_epochs
                WHERE node_id=? AND state='GRACE'
                """,
                (node_id,),
            ).fetchone()

            if grace is not None:
                raise NodeApplicationKeyStoreUnavailable(
                    "rotation_already_in_progress"
                )

            self._read_admin_key(
                row["key_file"],
                expected_sha256=row["key_sha256"],
            )

            with self._transaction() as connection:
                connection.execute(
                    """
                    UPDATE n3w_relay_key_epochs
                    SET state='GRACE',enabled=1
                    WHERE node_id=? AND state='ACTIVE'
                    """,
                    (node_id,),
                )
                connection.execute(
                    """
                    UPDATE n3w_relay_key_epochs
                    SET state='ACTIVE',enabled=1
                    WHERE
                        node_id=?
                        AND key_epoch=?
                        AND state='STAGED'
                    """,
                    (node_id, key_epoch),
                )

            self._fsync_database()

        return self._result(
            "activate_key",
            node_id=node_id,
            key_epoch=key_epoch,
        )

    def revoke_key(
        self,
        *,
        node_id: str,
        key_epoch: int,
    ) -> dict[str, object]:
        node_id = self._require_active_node(node_id)
        key_epoch = self._require_epoch(key_epoch)

        with self._lock:
            row = self._key_row(node_id, key_epoch)

            if row["state"] != "REVOKED":
                with self._transaction() as connection:
                    connection.execute(
                        """
                        UPDATE n3w_relay_key_epochs
                        SET state='REVOKED',enabled=0
                        WHERE node_id=? AND key_epoch=?
                        """,
                        (node_id, key_epoch),
                    )

                self._fsync_database()

            self._unlink_key(row["key_file"])

        return self._result(
            "revoke_key",
            node_id=node_id,
            key_epoch=key_epoch,
        )

    def rollback_rotation(
        self,
        *,
        node_id: str,
        key_epoch: int,
    ) -> dict[str, object]:
        node_id = self._require_active_node(node_id)
        key_epoch = self._require_epoch(key_epoch)

        with self._lock:
            current = self._key_row(
                node_id,
                key_epoch,
            )

            if current["state"] == "REVOKED":
                return self._result(
                    "rollback_rotation",
                    node_id=node_id,
                    key_epoch=key_epoch,
                )

            if current["state"] != "ACTIVE":
                raise NodeApplicationKeyStoreUnavailable(
                    "rotation_not_active"
                )

            grace = self._connection.execute(
                """
                SELECT key_epoch
                FROM n3w_relay_key_epochs
                WHERE node_id=? AND state='GRACE'
                ORDER BY key_epoch DESC
                LIMIT 1
                """,
                (node_id,),
            ).fetchone()

            if grace is None:
                raise NodeApplicationKeyStoreUnavailable(
                    "rotation_grace_epoch_missing"
                )

            with self._transaction() as connection:
                connection.execute(
                    """
                    UPDATE n3w_relay_key_epochs
                    SET state='REVOKED',enabled=0
                    WHERE node_id=? AND key_epoch=?
                    """,
                    (node_id, key_epoch),
                )
                connection.execute(
                    """
                    UPDATE n3w_relay_key_epochs
                    SET state='ACTIVE',enabled=1
                    WHERE node_id=? AND key_epoch=?
                    """,
                    (
                        node_id,
                        grace["key_epoch"],
                    ),
                )

            self._fsync_database()
            self._unlink_key(current["key_file"])

        return self._result(
            "rollback_rotation",
            node_id=node_id,
            key_epoch=key_epoch,
        )

    def recover(self) -> dict[str, object]:
        recovered = 0

        with self._lock:
            rows = self._connection.execute(
                """
                SELECT node_id,key_epoch,status
                FROM n3w_node_key_operations
                WHERE status NOT IN ('DONE','RECOVERED')
                ORDER BY operation_key
                """
            ).fetchall()

            for row in rows:
                try:
                    key = self._key_row(
                        row["node_id"],
                        row["key_epoch"],
                    )
                except NodeApplicationKeyStoreUnavailable:
                    continue

                with self._transaction() as connection:
                    connection.execute(
                        """
                        UPDATE n3w_relay_key_epochs
                        SET state='REVOKED',enabled=0
                        WHERE node_id=? AND key_epoch=?
                        """,
                        (
                            row["node_id"],
                            row["key_epoch"],
                        ),
                    )
                    self._record_operation(
                        connection,
                        node_id=row["node_id"],
                        key_epoch=row["key_epoch"],
                        status="RECOVERED",
                    )

                self._unlink_key(key["key_file"])
                recovered += 1

            if recovered:
                self._fsync_database()

        return {
            "schema": "gh.n3w-node-application-key-recovery/1",
            "status": "passed",
            "recovered_operation_count": recovered,
            "gateway_grant_dependency": False,
            "secret_values_included": False,
        }

    def audit(self) -> dict[str, object]:
        with self._lock:
            self._require_open()
            self._require_integrity()

            counts = {
                state: 0
                for state in self._KEY_STATES
            }

            rows = self._connection.execute(
                """
                SELECT state,enabled,key_file,key_sha256
                FROM n3w_relay_key_epochs
                """
            ).fetchall()

            for row in rows:
                state = row["state"]

                if (
                    state not in counts
                    or row["enabled"]
                    != int(state in _RUNTIME_KEY_STATES)
                ):
                    raise NodeApplicationKeyStoreUnavailable(
                        "node_key_store_corrupt"
                    )

                counts[state] += 1

                if state in _RUNTIME_KEY_STATES:
                    self._read_admin_key(
                        row["key_file"],
                        expected_sha256=row["key_sha256"],
                    )

            pending = self._connection.execute(
                """
                SELECT COUNT(*)
                FROM n3w_node_key_operations
                WHERE status NOT IN ('DONE','RECOVERED')
                """
            ).fetchone()[0]

            return {
                "schema": "gh.n3w-node-application-key-admin-audit/1",
                "status": "passed",
                "staged_key_epoch_count": counts["STAGED"],
                "active_key_epoch_count": counts["ACTIVE"],
                "grace_key_epoch_count": counts["GRACE"],
                "revoked_key_epoch_count": counts["REVOKED"],
                "pending_operation_count": int(pending),
                "gateway_grant_dependency": False,
                "secret_values_included": False,
            }

    @staticmethod
    def _result(
        operation: str,
        *,
        node_id: str,
        key_epoch: int,
    ) -> dict[str, object]:
        return {
            "schema": "gh.n3w-node-application-key-admin-result/1",
            "status": "passed",
            "operation": operation,
            "node_id": node_id,
            "key_epoch": key_epoch,
            "gateway_grant_dependency": False,
            "secret_values_included": False,
        }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._connection.close()
            self._closed = True

    def __enter__(self) -> SqliteNodeApplicationKeyAdmin:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
