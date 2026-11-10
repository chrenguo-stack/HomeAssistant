from __future__ import annotations

import fcntl
import json
import os
import stat
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from n3w_t1_core_updater_common import TX_SCHEMA as LEGACY_TX_SCHEMA
from n3w_t1_core_updater_v2_common import (
    TERMINAL_TX_V2,
    TX_SCHEMA_V2,
    UpdaterV2Error,
    canonical,
    sha256_bytes,
)

STATE_ROOT_V2 = Path("/var/lib/n3w-t1-core-updater")
HA_USB_TX_SCHEMA_GUARD = "gh.n3w-t1-core-updater-homeassistant-usb-transaction/1"
HA_USB_ACTIVE_FILE_GUARD = "homeassistant-usb-upgrade.json"


class V2StateStore:
    def __init__(self, root: Path = STATE_ROOT_V2) -> None:
        self.root = root
        self.path = root / "upgrade.json"
        self.legacy_path = root / "manager-upgrade.json"
        self.ha_usb_path = root / HA_USB_ACTIVE_FILE_GUARD
        self.history = root / "history"

    def _validate_private_dir(self, path: Path) -> None:
        if path.is_symlink() or not path.is_dir():
            raise UpdaterV2Error("transaction_directory_invalid")
        metadata = path.stat()
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise UpdaterV2Error("transaction_directory_not_private")
        if metadata.st_uid != os.getuid():
            raise UpdaterV2Error("transaction_directory_owner_invalid")

    def _existing_root(self) -> bool:
        if self.root.is_symlink():
            raise UpdaterV2Error("transaction_root_symlink")
        if not self.root.exists():
            return False
        self._validate_private_dir(self.root)
        return True

    def _ensure_root(self) -> None:
        if not self._existing_root():
            self.root.mkdir(parents=True, mode=0o700)
        self._validate_private_dir(self.root)

    @contextmanager
    def lock(self) -> Iterator[None]:
        self._ensure_root()
        descriptor = os.open(
            self.root,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise UpdaterV2Error("upgrade_transaction_busy") from error
            yield
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(descriptor)

    def _read_path(self, path: Path, schema: str) -> dict[str, Any] | None:
        if not self._existing_root() or not path.exists():
            return None
        if path.is_symlink() or not path.is_file():
            raise UpdaterV2Error("transaction_invalid")
        metadata = path.stat()
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise UpdaterV2Error("transaction_metadata_invalid")
        if metadata.st_uid != os.getuid():
            raise UpdaterV2Error("transaction_owner_invalid")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise UpdaterV2Error("transaction_invalid") from error
        if not isinstance(document, dict) or document.get("schema") != schema:
            raise UpdaterV2Error("transaction_schema_invalid")
        return document

    def read(self) -> dict[str, Any] | None:
        return self._read_path(self.path, TX_SCHEMA_V2)

    def read_legacy(self) -> dict[str, Any] | None:
        return self._read_path(self.legacy_path, LEGACY_TX_SCHEMA)

    def read_ha_usb_guard(self) -> dict[str, Any] | None:
        return self._read_path(self.ha_usb_path, HA_USB_TX_SCHEMA_GUARD)

    def _ensure_history(self) -> None:
        if self.history.is_symlink():
            raise UpdaterV2Error("transaction_history_symlink")
        if not self.history.exists():
            self.history.mkdir(mode=0o700)
        self._validate_private_dir(self.history)

    def _archive_path(self, source: Path, document: dict[str, Any], prefix: str) -> None:
        self._ensure_history()
        digest = sha256_bytes(canonical(document))[:16]
        destination = self.history / f"{int(time.time())}-{prefix}-{digest}.json"
        if destination.exists() or destination.is_symlink():
            raise UpdaterV2Error("transaction_history_collision")
        os.replace(source, destination)
        os.chmod(destination, 0o600)
        for path in (self.history, self.root):
            descriptor = os.open(
                path,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)

    def prepare_new(self) -> None:
        self._ensure_root()

        current = self.read()
        legacy = self.read_legacy()
        ha_usb = self.read_ha_usb_guard()

        if (
            current is not None
            and current.get("status") not in TERMINAL_TX_V2
        ):
            raise UpdaterV2Error("upgrade_transaction_active")
        if (
            current is not None
            and current.get("status") == "COMMITTED"
            and current.get("component") in {"manager", "broker"}
            and current.get("cleanup_state") != "ACCEPTED_CLEANUP_COMPLETE"
        ):
            raise UpdaterV2Error("post_acceptance_cleanup_required")
        if (
            legacy is not None
            and legacy.get("status") not in {"COMMITTED", "ROLLED_BACK"}
        ):
            raise UpdaterV2Error("legacy_transaction_reconciliation_required")
        if (
            ha_usb is not None
            and ha_usb.get("status") not in {"COMMITTED", "ROLLED_BACK"}
        ):
            raise UpdaterV2Error("ha_usb_transaction_active")

        if current is not None:
            self._archive_path(self.path, current, "v2")
        if legacy is not None:
            self._archive_path(self.legacy_path, legacy, "legacy-v1")

    def write(self, document: dict[str, Any]) -> None:
        if document.get("schema") != TX_SCHEMA_V2:
            raise UpdaterV2Error("transaction_schema_invalid")
        self._ensure_root()
        payload = json.dumps(document, sort_keys=True, indent=2) + "\n"
        fd, raw = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.root)
        temporary = Path(raw)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            descriptor = os.open(
                self.root,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        finally:
            temporary.unlink(missing_ok=True)
