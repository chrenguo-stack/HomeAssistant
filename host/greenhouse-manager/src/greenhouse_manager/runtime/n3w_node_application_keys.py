from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import stat
import threading
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
