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
_SCHEMA_VERSION_V1 = 1
_SCHEMA_VERSION_V2 = 2
_EXPECTED_TABLES_V1 = {
    "n3w_relay_meta",
    "n3w_relay_nodes",
    "n3w_relay_gateway_nodes",
    "n3w_relay_key_epochs",
}
_EXPECTED_TABLES_V2 = _EXPECTED_TABLES_V1 | {"n3w_relay_operations"}
_RUNTIME_KEY_STATES = {"ACTIVE", "GRACE"}


class RelayAuthorizationStoreUnavailable(RuntimeError):
    """Durable relay authorization metadata or private key material is unusable."""


def _require_private_path(path: Path, *, directory: bool, code: str) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise RelayAuthorizationStoreUnavailable(code)
    try:
        info = path.stat()
    except OSError as exc:
        raise RelayAuthorizationStoreUnavailable(code) from exc
    if directory:
        if not stat.S_ISDIR(info.st_mode):
            raise RelayAuthorizationStoreUnavailable(code)
    elif not stat.S_ISREG(info.st_mode):
        raise RelayAuthorizationStoreUnavailable(code)
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise RelayAuthorizationStoreUnavailable(code)
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise RelayAuthorizationStoreUnavailable(code)


class SqliteRelayAuthorizationProvider:
    """Read-only N3-W relay authorization and application-key adapter.

    Schema v1 remains readable for the preceding preflight stage. Schema v2 adds
    explicit application-key lifecycle states plus a secret-free recovery outbox.
    The provider never provisions, rotates, revokes, migrates, or writes either
    store.
    """

    def __init__(self, database: str | Path, key_dir: str | Path) -> None:
        self.database = Path(database).expanduser()
        self.key_dir = Path(key_dir).expanduser()
        self._lock = threading.RLock()
        self._closed = False
        self._schema_version = 0
        try:
            _require_private_path(
                self.database,
                directory=False,
                code="authorization_store_permissions_invalid",
            )
            _require_private_path(
                self.key_dir,
                directory=True,
                code="key_directory_permissions_invalid",
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
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA busy_timeout = 5000")
            self._schema_version = self._require_schema()
            self._require_integrity()
        except (OSError, sqlite3.Error, RelayAuthorizationStoreUnavailable) as exc:
            connection = getattr(self, "_connection", None)
            if connection is not None:
                connection.close()
            self._closed = True
            if isinstance(exc, RelayAuthorizationStoreUnavailable):
                raise
            raise RelayAuthorizationStoreUnavailable(
                "authorization_store_unavailable"
            ) from exc

    def _require_open(self) -> None:
        if self._closed:
            raise RelayAuthorizationStoreUnavailable("authorization_store_unavailable")

    def _require_schema(self) -> int:
        rows = self._connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name LIKE 'n3w_relay_%'
            """
        ).fetchall()
        names = {row["name"] for row in rows}
        if "n3w_relay_meta" not in names:
            raise RelayAuthorizationStoreUnavailable("authorization_store_schema_mismatch")
        versions = self._connection.execute(
            "SELECT schema_version FROM n3w_relay_meta"
        ).fetchall()
        if len(versions) != 1:
            raise RelayAuthorizationStoreUnavailable("authorization_store_schema_mismatch")
        version = versions[0]["schema_version"]
        if version == _SCHEMA_VERSION_V1:
            if names != _EXPECTED_TABLES_V1:
                raise RelayAuthorizationStoreUnavailable(
                    "authorization_store_schema_mismatch"
                )
            return version
        if version == _SCHEMA_VERSION_V2:
            if names != _EXPECTED_TABLES_V2:
                raise RelayAuthorizationStoreUnavailable(
                    "authorization_store_schema_mismatch"
                )
            columns = {
                row["name"]
                for row in self._connection.execute(
                    "PRAGMA table_info(n3w_relay_key_epochs)"
                ).fetchall()
            }
            if not {"state", "key_sha256"} <= columns:
                raise RelayAuthorizationStoreUnavailable(
                    "authorization_store_schema_mismatch"
                )
            return version
        raise RelayAuthorizationStoreUnavailable("authorization_store_schema_mismatch")

    def _require_integrity(self) -> None:
        row = self._connection.execute("PRAGMA quick_check").fetchone()
        if row is None or row[0] != "ok":
            raise RelayAuthorizationStoreUnavailable("authorization_store_corrupt")

    @staticmethod
    def _require_id(value: object, *, code: str) -> str:
        if not isinstance(value, str) or _ID.fullmatch(value) is None:
            raise RelayAuthorizationStoreUnavailable(code)
        return value

    def _load_key_file(
        self, key_file: object, *, expected_sha256: object = None
    ) -> bytes:
        if not isinstance(key_file, str) or _KEY_FILE.fullmatch(key_file) is None:
            raise RelayAuthorizationStoreUnavailable("key_file_reference_invalid")
        if expected_sha256 is not None and (
            not isinstance(expected_sha256, str)
            or _SHA256.fullmatch(expected_sha256) is None
        ):
            raise RelayAuthorizationStoreUnavailable("authorization_store_corrupt")

        flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        directory_flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            directory_flags |= os.O_DIRECTORY
        if hasattr(os, "O_NOFOLLOW"):
            directory_flags |= os.O_NOFOLLOW

        dir_fd: int | None = None
        fd: int | None = None
        try:
            dir_fd = os.open(self.key_dir, directory_flags)
            dir_info = os.fstat(dir_fd)
            if (
                not stat.S_ISDIR(dir_info.st_mode)
                or stat.S_IMODE(dir_info.st_mode) & 0o077
            ):
                raise RelayAuthorizationStoreUnavailable(
                    "key_directory_permissions_invalid"
                )
            if hasattr(os, "getuid") and dir_info.st_uid != os.getuid():
                raise RelayAuthorizationStoreUnavailable(
                    "key_directory_permissions_invalid"
                )

            fd = os.open(key_file, flags, dir_fd=dir_fd)
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
                raise RelayAuthorizationStoreUnavailable(
                    "key_file_permissions_invalid"
                )
            if hasattr(os, "getuid") and info.st_uid != os.getuid():
                raise RelayAuthorizationStoreUnavailable(
                    "key_file_permissions_invalid"
                )
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
            key = b"".join(chunks)
        except FileNotFoundError as exc:
            raise RelayAuthorizationStoreUnavailable("key_file_unavailable") from exc
        except OSError as exc:
            raise RelayAuthorizationStoreUnavailable("key_file_unavailable") from exc
        finally:
            if fd is not None:
                os.close(fd)
            if dir_fd is not None:
                os.close(dir_fd)

        if len(key) != 32:
            raise RelayAuthorizationStoreUnavailable("key_material_invalid")
        if (
            expected_sha256 is not None
            and hashlib.sha256(key).hexdigest() != expected_sha256
        ):
            raise RelayAuthorizationStoreUnavailable("key_material_binding_invalid")
        return key

    def resolve_key(self, *, gateway_id: str, node_id: str, key_epoch: int) -> bytes:
        if _ID.fullmatch(gateway_id) is None or _ID.fullmatch(node_id) is None:
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

                grant = self._connection.execute(
                    """
                    SELECT enabled
                    FROM n3w_relay_gateway_nodes
                    WHERE gateway_id = ? AND node_id = ?
                    """,
                    (gateway_id, node_id),
                ).fetchone()
                if grant is None or grant["enabled"] != 1:
                    raise RelayIngressRejected(
                        "gateway_node_unauthorized",
                        node_id=node_id,
                    )

                if self._schema_version == _SCHEMA_VERSION_V1:
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
                try:
                    return self._load_key_file(
                        epoch["key_file"],
                        expected_sha256=expected_sha256,
                    )
                except RelayAuthorizationStoreUnavailable as exc:
                    raise RelayIngressRejected(str(exc), node_id=node_id) from exc
            except sqlite3.Error as exc:
                raise RelayIngressRejected(
                    "authorization_store_unavailable",
                    node_id=node_id,
                ) from exc

    def audit(self) -> dict[str, int | str | bool]:
        """Validate enabled metadata/key references without exposing key material or file names."""
        with self._lock:
            self._require_open()
            try:
                self._require_integrity()
                node_rows = self._connection.execute(
                    "SELECT node_id, active FROM n3w_relay_nodes"
                ).fetchall()
                nodes: dict[str, int] = {}
                for row in node_rows:
                    node_id = self._require_id(
                        row["node_id"],
                        code="authorization_store_corrupt",
                    )
                    if row["active"] not in {0, 1}:
                        raise RelayAuthorizationStoreUnavailable(
                            "authorization_store_corrupt"
                        )
                    nodes[node_id] = row["active"]

                grant_rows = self._connection.execute(
                    "SELECT gateway_id, node_id, enabled FROM n3w_relay_gateway_nodes"
                ).fetchall()
                enabled_grants = 0
                for row in grant_rows:
                    self._require_id(
                        row["gateway_id"],
                        code="authorization_store_corrupt",
                    )
                    node_id = self._require_id(
                        row["node_id"],
                        code="authorization_store_corrupt",
                    )
                    if node_id not in nodes or row["enabled"] not in {0, 1}:
                        raise RelayAuthorizationStoreUnavailable(
                            "authorization_store_corrupt"
                        )
                    enabled_grants += int(row["enabled"] == 1)

                state_counts = {"STAGED": 0, "ACTIVE": 0, "GRACE": 0, "REVOKED": 0}
                if self._schema_version == _SCHEMA_VERSION_V1:
                    key_rows = self._connection.execute(
                        """
                        SELECT node_id, key_epoch, key_file, enabled
                        FROM n3w_relay_key_epochs
                        """
                    ).fetchall()
                else:
                    key_rows = self._connection.execute(
                        """
                        SELECT node_id, key_epoch, key_file, enabled, state, key_sha256
                        FROM n3w_relay_key_epochs
                        """
                    ).fetchall()
                enabled_epochs = 0
                for row in key_rows:
                    node_id = self._require_id(
                        row["node_id"],
                        code="authorization_store_corrupt",
                    )
                    key_epoch = row["key_epoch"]
                    if (
                        node_id not in nodes
                        or not isinstance(key_epoch, int)
                        or isinstance(key_epoch, bool)
                        or key_epoch < 1
                        or row["enabled"] not in {0, 1}
                    ):
                        raise RelayAuthorizationStoreUnavailable(
                            "authorization_store_corrupt"
                        )
                    if self._schema_version == _SCHEMA_VERSION_V2:
                        state = row["state"]
                        if state not in state_counts:
                            raise RelayAuthorizationStoreUnavailable(
                                "authorization_store_corrupt"
                            )
                        state_counts[state] += 1
                        expected_enabled = int(state in _RUNTIME_KEY_STATES)
                        if row["enabled"] != expected_enabled:
                            raise RelayAuthorizationStoreUnavailable(
                                "authorization_store_corrupt"
                            )
                        if state in _RUNTIME_KEY_STATES:
                            self._load_key_file(
                                row["key_file"],
                                expected_sha256=row["key_sha256"],
                            )
                            enabled_epochs += 1
                    elif row["enabled"] == 1:
                        self._load_key_file(row["key_file"])
                        enabled_epochs += 1

                document: dict[str, int | str | bool] = {
                    "schema": "gh.n3w-relay-authorization-audit/1",
                    "status": "passed",
                    "schema_version": self._schema_version,
                    "node_count": len(nodes),
                    "active_node_count": sum(value == 1 for value in nodes.values()),
                    "enabled_gateway_grant_count": enabled_grants,
                    "enabled_key_epoch_count": enabled_epochs,
                    "secret_values_included": False,
                    "mutated": False,
                }
                if self._schema_version == _SCHEMA_VERSION_V2:
                    pending = self._connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM n3w_relay_operations
                        WHERE status NOT IN ('DONE', 'RECOVERED')
                        """
                    ).fetchone()[0]
                    document.update(
                        {
                            "staged_key_epoch_count": state_counts["STAGED"],
                            "active_key_epoch_count": state_counts["ACTIVE"],
                            "grace_key_epoch_count": state_counts["GRACE"],
                            "revoked_key_epoch_count": state_counts["REVOKED"],
                            "pending_operation_count": int(pending),
                        }
                    )
                return document
            except sqlite3.Error as exc:
                raise RelayAuthorizationStoreUnavailable(
                    "authorization_store_unavailable"
                ) from exc

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._connection.close()
            self._closed = True

    def __enter__(self) -> SqliteRelayAuthorizationProvider:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
