from __future__ import annotations

import json
import os
import secrets
import stat
from pathlib import Path
from typing import Any

from b1i1_contract import Authority, GateStop, JOURNAL_NAME, SCHEMA, require


def private_root(root: Path) -> Path:
    require(root.is_absolute() and root.is_dir() and not root.is_symlink(), "PRIVATE_ROOT_INVALID")
    require(stat.S_IMODE(root.stat().st_mode) == 0o700, "PRIVATE_ROOT_PERMISSIONS_INVALID")
    return root


def _fsync_directory(root: Path) -> None:
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write(path: Path, doc: dict[str, Any], *, create: bool) -> None:
    raw = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    root = private_root(path.parent)
    require(not path.is_symlink(), "JOURNAL_SYMLINK_FORBIDDEN")
    if create:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            _fsync_directory(root)
        return
    require(path.is_file() and stat.S_IMODE(path.stat().st_mode) == 0o600, "JOURNAL_UNSAFE")
    temp = root / (".b1i1-journal-" + secrets.token_hex(12))
    fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
        _fsync_directory(root)
    finally:
        if temp.exists():
            temp.unlink()


class Journal:
    def __init__(self, root: Path, doc: dict[str, Any]):
        self.path = private_root(root) / JOURNAL_NAME
        self.doc = doc
        self.uncertain = False

    @classmethod
    def create(cls, root: Path, authority: Authority, token: str) -> "Journal":
        authority.validate()
        require(isinstance(token, str) and len(token) >= 32, "TOKEN_INVALID")
        doc = {
            "schema": SCHEMA, "phase": "PREPARE_INTENT", "committed": False,
            "old_manager_id": authority.old_manager_id,
            "old_image": authority.old_image,
            "broker_id": authority.broker_id,
            "broker_started_at": authority.broker_started_at,
            "broker_restart_count": authority.broker_restart_count,
            "candidate_image_id": authority.candidate_image_id,
            "source_ref": authority.source_ref,
            "transaction_token": token,
            "candidate_id": None,
            "rollback_result": None,
        }
        new = cls(root, doc)
        _write(new.path, doc, create=True)
        return new

    @classmethod
    def load(cls, root: Path) -> "Journal":
        path = private_root(root) / JOURNAL_NAME
        require(path.is_file() and not path.is_symlink(), "JOURNAL_MISSING")
        require(stat.S_IMODE(path.stat().st_mode) == 0o600, "JOURNAL_MODE_INVALID")
        doc = json.loads(path.read_text(encoding="utf-8"))
        require(isinstance(doc, dict) and doc.get("schema") == SCHEMA, "JOURNAL_SCHEMA_INVALID")
        require(isinstance(doc.get("transaction_token"), str) and len(doc["transaction_token"]) >= 32, "JOURNAL_TOKEN_INVALID")
        require(doc.get("committed") is True or doc.get("committed") is False, "JOURNAL_COMMIT_INVALID")
        require(
            doc.get("phase") in (
                "PREPARE_INTENT", "PREPARE_STOP", "OLD_STOP_INTENT",
                "OLD_PARK_INTENT", "CANDIDATE_CREATE_INTENT",
                "CANDIDATE_START_INTENT", "POSTFLIGHT_INTENT",
                "COMMIT_INTENT", "CANDIDATE_VERIFIED", "FINALIZED",
                "FAIL_ROLLED_BACK", "FAIL_ROLLBACK_INCOMPLETE",
            ),
            "JOURNAL_PHASE_INVALID",
        )
        if doc["phase"] in ("CANDIDATE_VERIFIED", "FINALIZED"):
            require(doc["committed"] is True, "JOURNAL_COMMIT_PHASE_MISMATCH")
            require(bool(doc.get("candidate_id")), "COMMITTED_CANDIDATE_NOT_BOUND")
        if doc["phase"] in ("FAIL_ROLLED_BACK", "FAIL_ROLLBACK_INCOMPLETE"):
            require(doc["committed"] is False, "JOURNAL_ROLLBACK_COMMIT_DRIFT")
            expected = "PASS" if doc["phase"] == "FAIL_ROLLED_BACK" else "INCOMPLETE"
            require(doc.get("rollback_result") == expected, "JOURNAL_ROLLBACK_RESULT_DRIFT")
        return cls(root, doc)

    def save(self, **changes: Any) -> None:
        require(not self.uncertain, "JOURNAL_DURABILITY_UNKNOWN_FROZEN")
        before = dict(self.doc)
        self.doc.update(changes)
        try:
            _write(self.path, self.doc, create=False)
        except Exception as error:
            self.doc = before
            self.uncertain = True
            raise GateStop("JOURNAL_DURABILITY_UNKNOWN_FROZEN") from error

    def intent(self, phase: str) -> None:
        require(phase.endswith("_INTENT"), "NOT_DURABLE_INTENT")
        self.save(phase=phase)

    def bind_candidate(self, candidate_id: str) -> None:
        require(bool(candidate_id), "CANDIDATE_ID_INVALID")
        existing = self.doc.get("candidate_id")
        require(existing is None or existing == candidate_id, "CANDIDATE_ID_REBIND_FORBIDDEN")
        self.save(candidate_id=candidate_id)

    def check_authority(self, authority: Authority) -> None:
        authority.validate()
        for key in (
            "old_manager_id", "old_image", "broker_id", "broker_started_at",
            "broker_restart_count", "candidate_image_id", "source_ref"
        ):
            require(self.doc.get(key) == getattr(authority, key), "JOURNAL_AUTHORITY_DRIFT")
