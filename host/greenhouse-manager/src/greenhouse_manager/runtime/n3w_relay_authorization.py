from __future__ import annotations

import re
import sqlite3
import stat
import threading
from pathlib import Path

from .n3w_relay_ingress import RelayIngressRejected

_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
_KEY_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SCHEMA_VERSION = 1
_EXPECTED_TABLES = {
    "n3w_relay_meta",
    "n3w_relay_nodes",
    "n3w_relay_gateway_nodes",
    "n3w_relay_key_epochs",
}


class RelayAuthorizationStoreUnavailable(RuntimeError):
    """Durable relay authorization metadata or private key material is unusable."""


def _require_private_path(path: Path, *, directory: bool, code: str) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise RelayAuthorizationStoreUnavailable(code)
    if directory:
        if not path.is_dir():
            raise RelayAuthorizationStoreUnavailable(code)
    elif not path.is_file():
        raise RelayAuthorizationStoreUnavailable(code)
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise RelayAuthorizationStoreUnavailable(code)


class SqliteRelayAuthorizationProvider:
    """Read-only production-shaped N3-W authorization and key-file adapter.

    The SQLite database contains authorization metadata only. Application keys
    remain in separate 0600 raw 32-byte files beneath one 0700 private directory.
    This adapter never provisions, rotates, or writes either store.
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
            self._require_schema()
            self._require_integrity()
        except (OSError, sqlite3.Error, RelayAuthorizationStoreUnavailable) as exc:
            connection = getattr(self, "_connection", None)
            if connection is not None:
                connection.close()
            self._closed = True
            if isinstance(exc, RelayAuthorizationStoreUnavailable):
                raise
            raise RelayAuthorizationStoreUnavailable("authorization_store_unavailable") from exc

    def _require_open(self) -> None:
        if self._closed:
            raise RelayAuthorizationStoreUnavailable("authorization_store_unavailable")

    def _require_schema(self) -> None:
        rows = self._connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name LIKE 'n3w_relay_%'
            """
        ).fetchall()
        names = {row["name"] for row in rows}
        if names != _EXPECTED_TABLES:
            raise RelayAuthorizationStoreUnavailable("authorization_store_schema_mismatch")
        versions = self._connection.execute(
            "SELECT schema_version FROM n3w_relay_meta"
        ).fetchall()
        if len(versions) != 1 or versions[0]["schema_version"] != _SCHEMA_VERSION:
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

    def _load_key_file(self, key_file: object) -> bytes:
        if not isinstance(key_file, str) or _KEY_FILE.fullmatch(key_file) is None:
            raise RelayAuthorizationStoreUnavailable("key_file_reference_invalid")
        path = self.key_dir / key_file
        _require_private_path(
            path,
            directory=False,
            code="key_file_permissions_invalid",
        )
        try:
            if path.resolve().parent != self.key_dir.resolve():
                raise RelayAuthorizationStoreUnavailable("key_file_reference_invalid")
            key = path.read_bytes()
        except OSError as exc:
            raise RelayAuthorizationStoreUnavailable("key_file_unavailable") from exc
        if len(key) != 32:
            raise RelayAuthorizationStoreUnavailable("key_material_invalid")
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

                epoch = self._connection.execute(
                    """
                    SELECT key_file, enabled
                    FROM n3w_relay_key_epochs
                    WHERE node_id = ? AND key_epoch = ?
                    """,
                    (node_id, key_epoch),
                ).fetchone()
                if epoch is None or epoch["enabled"] != 1:
                    raise RelayIngressRejected("key_epoch_rejected", node_id=node_id)
                try:
                    return self._load_key_file(epoch["key_file"])
                except RelayAuthorizationStoreUnavailable as exc:
                    raise RelayIngressRejected(str(exc), node_id=node_id) from exc
            except sqlite3.Error as exc:
                raise RelayIngressRejected(
                    "authorization_store_unavailable",
                    node_id=node_id,
                ) from exc

    def audit(self) -> dict[str, int | str | bool]:
        """Validate all enabled metadata/key references without exposing secrets."""
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

                key_rows = self._connection.execute(
                    """
                    SELECT node_id, key_epoch, key_file, enabled
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
                    if row["enabled"] == 1:
                        self._load_key_file(row["key_file"])
                        enabled_epochs += 1

                return {
                    "schema": "gh.n3w-relay-authorization-audit/1",
                    "status": "passed",
                    "schema_version": _SCHEMA_VERSION,
                    "node_count": len(nodes),
                    "active_node_count": sum(value == 1 for value in nodes.values()),
                    "enabled_gateway_grant_count": enabled_grants,
                    "enabled_key_epoch_count": enabled_epochs,
                    "secret_values_included": False,
                    "mutated": False,
                }
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
