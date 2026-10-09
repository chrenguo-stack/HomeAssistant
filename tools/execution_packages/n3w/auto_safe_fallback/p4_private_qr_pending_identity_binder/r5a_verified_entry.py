from __future__ import annotations

import hashlib
import hmac
import os
import stat
import types
from pathlib import Path

PINNED_REVIEW_BASE = "9abb89d219475558ff80f03279362cab291ef279"
FIELD_MODULE_BLOB = "e43b4782df140527bef2f1c155cb52b8f42d36fd"
DEPENDENCY_BLOBS = {
    "bridge_handoff.py": "e277949c3db5675bd460124832a382d6a2765539",
    "remote_projection.py": "7b3ba146583b61271b41390736b67207c8d4c14e",
    "host_readonly.py": "0c62bc1b006eb2feab2e89d393cd477ad0912d83",
    "validator.py": "3b7dc0d085dcda52fda0334840d75d5f8678bc1b",
}
ENTRYPOINT_NAME = "field_preboot_readonly.py"


def _git_blob(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw
    ).hexdigest()


def _read_pinned(root: Path, name: str, blob_sha: str) -> bytes:
    path = root / name
    if not root.is_absolute() or root.is_symlink() or path.is_symlink():
        raise ValueError("R5A_ENTRY_PATH_NOT_TRUSTED")
    if any(part.is_symlink() for part in path.parents):
        raise ValueError("R5A_ENTRY_PARENT_SYMLINK")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or not (0 < info.st_size <= 131072):
                raise ValueError("R5A_ENTRY_SOURCE_TYPE_INVALID")
            raw = os.read(fd, 131073)
        finally:
            os.close(fd)
    except OSError:
        raise ValueError("R5A_ENTRY_SOURCE_UNAVAILABLE") from None
    if not hmac.compare_digest(_git_blob(raw), blob_sha):
        raise ValueError("R5A_ENTRY_SOURCE_BLOB_DRIFT")
    return raw


def load_verified_field_module(root: Path) -> types.ModuleType:
    if not isinstance(root, Path):
        raise ValueError("R5A_ENTRY_ROOT_INVALID")
    root = root.absolute()
    source = _read_pinned(root, ENTRYPOINT_NAME, FIELD_MODULE_BLOB)
    for name, expected in DEPENDENCY_BLOBS.items():
        _read_pinned(root, name, expected)
    module = types.ModuleType("_n3w_r5a_verified_field")
    module.__file__ = str(root / ENTRYPOINT_NAME)
    compiled = compile(source, str(root / ENTRYPOINT_NAME), "exec")
    exec(compiled, module.__dict__)
    if (
        module.SOURCE_BLOBS != DEPENDENCY_BLOBS
        or module.FIELD_H2_LIVE_EXECUTION_ENABLED is not False
    ):
        raise ValueError("R5A_ENTRY_POLICY_DRIFT")
    return module


def verify_mac_h1_only(root: Path, target: str, known_hosts_path: Path) -> dict:
    module = load_verified_field_module(root)
    program, baseline, _ = module.mac_static_preflight(target, known_hosts_path)
    if len(baseline) != 5 or not program:
        raise ValueError("R5A_ENTRY_H1_NOT_READY")
    return {
        "stage": "R5A_MAC_LOCAL_H1_ONLY",
        "source_pin": "PASS",
        "private_snapshot": "PASS",
        "host_key": "PASS",
        "preboot_remote_program": "COMPILED_NOT_EXECUTED",
        "live_ssh": False,
        "h2_authorized": False,
        "stop": True,
    }


if __name__ == "__main__":
    raise SystemExit("R5A_LAUNCHER_NOT_A_FIELD_EXECUTOR")
