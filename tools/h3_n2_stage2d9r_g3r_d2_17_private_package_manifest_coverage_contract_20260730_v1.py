from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable

ROOT_MANIFEST_NAME = "SHA256SUMS"
SCHEMA = "gh.h3.n2.stage2d9r-g3r-d2-17-private-package-manifest-coverage/1"


class CoverageError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise CoverageError(code)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalized_root(root: Path) -> Path:
    resolved = root.expanduser().resolve(strict=True)
    require(resolved.is_dir() and not resolved.is_symlink(), "PRIVATE_ROOT_INVALID")
    return resolved


def _root_manifest(root: Path, name: str = ROOT_MANIFEST_NAME) -> Path:
    require(name == ROOT_MANIFEST_NAME, "ROOT_MANIFEST_NAME_INVALID")
    return root / name


def iter_covered_regular_files(root: Path) -> Iterable[Path]:
    """Yield every regular file except the one root-level SHA256SUMS file.

    A nested file named SHA256SUMS is ordinary payload and must be covered. The
    historical G01 defect compared ``p.name`` and accidentally excluded every
    nested manifest with that basename.
    """

    resolved = _normalized_root(root)
    manifest = _root_manifest(resolved)
    for path in sorted(resolved.rglob("*"), key=lambda item: item.as_posix()):
        require(not path.is_symlink(), "PRIVATE_SYMLINK_FORBIDDEN")
        if path.is_file() and path != manifest:
            yield path


def build_root_sha256sums(root: Path) -> list[str]:
    resolved = _normalized_root(root)
    lines: list[str] = []
    for path in iter_covered_regular_files(resolved):
        relative = path.relative_to(resolved).as_posix()
        lines.append(f"{sha256_file(path)}  {relative}")
    return lines


def write_root_sha256sums(root: Path) -> Path:
    resolved = _normalized_root(root)
    manifest = _root_manifest(resolved)
    require(not manifest.exists(), "ROOT_SHA256SUMS_ALREADY_EXISTS")
    lines = build_root_sha256sums(resolved)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(manifest, flags, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=False) as handle:
            handle.write("\n".join(lines) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    verify_root_sha256sums(resolved)
    return manifest


def parse_root_sha256sums(root: Path) -> dict[str, str]:
    resolved = _normalized_root(root)
    manifest = _root_manifest(resolved)
    require(manifest.is_file() and not manifest.is_symlink(), "PRIVATE_SHA256SUMS_MISSING")
    expected: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        require("  " in line, "PRIVATE_SHA256SUMS_INVALID")
        digest, relative = line.split("  ", 1)
        candidate = Path(relative)
        require(
            len(digest) == 64
            and all(character in "0123456789abcdef" for character in digest)
            and relative not in expected
            and not candidate.is_absolute()
            and ".." not in candidate.parts
            and candidate.as_posix() == relative,
            "PRIVATE_SHA256SUMS_INVALID",
        )
        expected[relative] = digest
    return expected


def coverage_snapshot(root: Path) -> dict[str, object]:
    resolved = _normalized_root(root)
    expected = parse_root_sha256sums(resolved)
    observed_paths = [
        path.relative_to(resolved).as_posix()
        for path in iter_covered_regular_files(resolved)
    ]
    expected_paths = sorted(expected)
    observed_set = set(observed_paths)
    expected_set = set(expected_paths)
    nested_manifest_paths = sorted(
        path for path in observed_paths if Path(path).name == ROOT_MANIFEST_NAME
    )
    value: dict[str, object] = {
        "schema": SCHEMA,
        "expected_count": len(expected_paths),
        "observed_count": len(observed_paths),
        "nested_sha256sums_count": len(nested_manifest_paths),
        "nested_sha256sums_paths": nested_manifest_paths,
        "missing_paths": sorted(observed_set - expected_set),
        "extra_paths": sorted(expected_set - observed_set),
    }
    value["coverage_binding_sha256"] = canonical_sha256(value)
    return value


def verify_root_sha256sums(root: Path) -> dict[str, object]:
    resolved = _normalized_root(root)
    expected = parse_root_sha256sums(resolved)
    snapshot = coverage_snapshot(resolved)
    require(
        not snapshot["missing_paths"] and not snapshot["extra_paths"],
        "PRIVATE_SHA256SUMS_COVERAGE_MISMATCH",
    )
    for relative, digest in expected.items():
        path = resolved / relative
        require(
            path.is_file() and not path.is_symlink(),
            "PRIVATE_MEMBER_INVALID:" + relative,
        )
        require(
            sha256_file(path) == digest,
            "PRIVATE_MEMBER_DIGEST_MISMATCH:" + relative,
        )
    result = dict(snapshot)
    result["status"] = "PASS"
    result["root_manifest_sha256"] = sha256_file(_root_manifest(resolved))
    result["verification_binding_sha256"] = canonical_sha256(result)
    return result
