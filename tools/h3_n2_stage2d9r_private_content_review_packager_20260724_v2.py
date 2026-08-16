#!/usr/bin/env python3
"""Hardened Stage 2D-9R U1-04 review packager with complete inventory binding."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil

_BASE_PATH = Path(__file__).with_name(
    "h3_n2_stage2d9r_private_content_review_packager_20260724_v1.py"
)
_SPEC = importlib.util.spec_from_file_location("stage2d9r_review_packager_v1", _BASE_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("unable to load V1 review packager")
_base = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_base)

LAUNCHER = "run_stage2d9r_private_content_binding_toolchain_probe_20260724_v6_91e4b7c2.sh"


def rebuild_inventory(output: Path) -> None:
    for cache in output.rglob("__pycache__"):
        if cache.is_dir():
            shutil.rmtree(cache)
    for bytecode in output.rglob("*.py[co]"):
        bytecode.unlink()
    sums = output / "SHA256SUMS"
    lines = []
    for path in sorted(item for item in output.rglob("*") if item.is_file() and item != sums):
        lines.append(f"{_base.sha256_file(path)}  {path.relative_to(output).as_posix()}")
    sums.write_text("\n".join(lines) + "\n")
    os.chmod(sums, 0o600)


def verify_complete_inventory(output: Path) -> None:
    sums = output / "SHA256SUMS"
    covered: dict[str, str] = {}
    for line in sums.read_text().splitlines():
        digest, relative = line.split("  ", 1)
        _base.require(relative not in covered, "DUPLICATE_INVENTORY_PATH")
        covered[relative] = digest
    observed = {
        path.relative_to(output).as_posix(): _base.sha256_file(path)
        for path in output.rglob("*")
        if path.is_file() and path != sums
    }
    _base.require(set(covered) == set(observed), "INVENTORY_FILE_SET_MISMATCH")
    _base.require(covered == observed, "INVENTORY_DIGEST_MISMATCH")
    _base.require(not any(output.rglob("__pycache__")), "BYTECODE_CACHE_PRESENT")
    _base.require(not any(output.rglob("*.py[co]")), "BYTECODE_FILE_PRESENT")


def assemble(repository: Path, output: Path, source_sha: str, main_sha: str):
    result = _base.assemble(repository, output, source_sha, main_sha)

    old_launcher = output / result["launcher"]
    if old_launcher.exists():
        old_launcher.unlink()

    binding_path = output / "PROBE_PACKAGE_BINDING.json"
    binding = json.loads(binding_path.read_text())
    binding["state"] = "PENDING_EXACT_U1_TOOLCHAIN_PROBE_V6"
    binding.pop("review_binding_sha256", None)
    binding["review_binding_sha256"] = _base.canonical_json_sha256(binding)
    binding_path.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    os.chmod(binding_path, 0o600)

    readme = output / "README.md"
    readme.write_text(
        "# Stage 2D-9R private-content binding preauthorization review V6\n\n"
        "Review-only package for request U1-04. It uses the corrected DER certificate "
        "digest verifier, binds the retired U1-03 CONSUMED_FAILED marker, and requires "
        "an exact complete-file inventory. It contains no authorization record and no "
        "authorized execution launcher.\n"
    )
    os.chmod(readme, 0o600)

    launcher = output / LAUNCHER
    launcher.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "umask 077\n"
        "export PYTHONDONTWRITEBYTECODE=1\n"
        "ROOT=\"$(CDPATH= cd -- \"$(dirname -- \"$0\")\" && pwd -P)\"\n"
        "cd \"$ROOT\"\n"
        "shasum -a 256 -c SHA256SUMS\n"
        "echo PRIVATE_CONTENT_BINDING_TOOLCHAIN_PROBE_V6_BEGIN\n"
        "set +e\n"
        "\"$(command -v python3)\" \"$ROOT/tools/h3_n2_stage2d9r_private_content_binding_probe_20260724_v3.py\" --package-root \"$ROOT\" --probe-toolchain\n"
        "rc=$?\n"
        "set -e\n"
        "echo PRIVATE_CONTENT_BINDING_TOOLCHAIN_PROBE_V6_END\n"
        "exit \"$rc\"\n"
    )
    os.chmod(launcher, 0o700)

    rebuild_inventory(output)
    verify_complete_inventory(output)

    result.update(
        state=binding["state"],
        review_binding_sha256=binding["review_binding_sha256"],
        launcher=LAUNCHER,
        complete_inventory_bound=True,
        bytecode_cache_included=False,
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--main-sha", required=True)
    args = parser.parse_args()
    result = assemble(
        args.repository_root.resolve(strict=True),
        args.output.resolve(strict=False),
        args.source_sha,
        args.main_sha,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
