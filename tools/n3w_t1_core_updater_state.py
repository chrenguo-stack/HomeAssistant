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

from n3w_t1_core_updater_common import (
    STATE_ROOT,
    TERMINAL_TX,
    TX_SCHEMA,
    UpdaterError,
    canonical,
    sha256_bytes,
)


class StateStore:
    def __init__(self, root: Path = STATE_ROOT) -> None:
        self.root = root
        self.path = root / "manager-upgrade.json"
        self.history = root / "history"

    def _validate_private_dir(self, path: Path) -> None:
        if path.is_symlink() or not path.is_dir():
            raise UpdaterError("transaction_directory_invalid")
        metadata = path.stat()
        if stat.S_IMODE(metadata.st_mode) & 0o077:
            raise UpdaterError("transaction_directory_not_private")
        if metadata.st_uid != os.getuid():
            raise UpdaterError("transaction_directory_owner_invalid")

    def _existing_root(self) -> bool:
        if self.root.is_symlink():
            raise UpdaterError("transaction_root_symlink")
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
                fcntl.flock(
                    descriptor,
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
            except BlockingIOError as error:
                raise UpdaterError("upgrade_transaction_busy") from error
            yield
        finally:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(descriptor)

    def read(self) -> dict[str, Any] | None:
        if not self._existing_root():
            return None
        if not self.path.exists():
            return None
        if self.path.is_symlink() or not self.path.is_file():
            raise UpdaterError("transaction_invalid")
        metadata = self.path.stat()
        if stat.S_IMODE(metadata.st_mode) != 0o600:
            raise UpdaterError("transaction_metadata_invalid")
        if metadata.st_uid != os.getuid():
            raise UpdaterError("transaction_owner_invalid")
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise UpdaterError("transaction_invalid") from error
        if not isinstance(document, dict) or document.get("schema") != TX_SCHEMA:
            raise UpdaterError("transaction_schema_invalid")
        return document

    def prepare_new(self) -> None:
        self._ensure_root()
        current = self.read()
        if current is not None and current.get("status") not in TERMINAL_TX:
            raise UpdaterError("upgrade_transaction_active")
        if current is None:
            return
        if self.history.is_symlink():
            raise UpdaterError("transaction_history_symlink")
        if not self.history.exists():
            self.history.mkdir(mode=0o700)
        self._validate_private_dir(self.history)
        digest = sha256_bytes(canonical(current))[:16]
        destination = self.history / f"{int(time.time())}-{digest}.json"
        if destination.exists() or destination.is_symlink():
            raise UpdaterError("transaction_history_collision")
        os.replace(self.path, destination)
        os.chmod(destination, 0o600)
        directory = os.open(
            self.history,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
        )
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def write(self, document: dict[str, Any]) -> None:
        if document.get("schema") != TX_SCHEMA:
            raise UpdaterError("transaction_schema_invalid")
        self._ensure_root()
        payload = json.dumps(document, sort_keys=True, indent=2) + "\n"
        fd, raw = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=self.root,
        )
        temporary = Path(raw)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            directory = os.open(
                self.root,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)
