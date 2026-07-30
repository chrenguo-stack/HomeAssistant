#!/usr/bin/env python3
"""Recompute the G07 physical-decision marker semantic digest after terminal update."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

DECISION_ID = "D1-H3N2-STAGE2D9R-G3R-D2-17-G07-PHYSICAL-EXECUTION-20260731-01"


def canonical(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def main() -> int:
    path = Path.home() / ".local/state/greenhouse-stage2d9r/d2-17-g07-physical-decisions" / (DECISION_ID + ".json")
    if not path.exists():
        return 0
    if not path.is_file() or path.is_symlink():
        raise SystemExit("PHYSICAL_DECISION_MARKER_NOT_REGULAR")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("decision_id") != DECISION_ID:
        raise SystemExit("PHYSICAL_DECISION_MARKER_IDENTITY_DRIFT")
    value.pop("marker_sha256", None)
    value["marker_sha256"] = canonical(value)
    tmp = path.with_name(path.name + ".finalize.tmp")
    if tmp.exists():
        raise SystemExit("PHYSICAL_DECISION_MARKER_FINALIZER_TMP_EXISTS")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(tmp, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as handle:
            json.dump(value, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)
    os.replace(tmp, path)
    os.chmod(path, 0o600)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
