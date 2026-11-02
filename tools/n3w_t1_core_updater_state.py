from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

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

    def read(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        if self.path.is_symlink() or not self.path.is_file():
            raise UpdaterError("transaction_invalid")
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise UpdaterError("transaction_invalid") from error
        if not isinstance(document, dict) or document.get("schema") != TX_SCHEMA:
            raise UpdaterError("transaction_schema_invalid")
        return document

    def prepare_new(self) -> None:
        current = self.read()
        if current is not None and current.get("status") not in TERMINAL_TX:
            raise UpdaterError("upgrade_transaction_active")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        if current is None:
            return
        self.history.mkdir(mode=0o700, exist_ok=True)
        os.chmod(self.history, 0o700)
        digest = sha256_bytes(canonical(current))[:16]
        destination = self.history / f"{int(time.time())}-{digest}.json"
        if destination.exists():
            raise UpdaterError("transaction_history_collision")
        os.replace(self.path, destination)
        os.chmod(destination, 0o600)

    def write(self, document: dict[str, Any]) -> None:
        if document.get("schema") != TX_SCHEMA:
            raise UpdaterError("transaction_schema_invalid")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
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
