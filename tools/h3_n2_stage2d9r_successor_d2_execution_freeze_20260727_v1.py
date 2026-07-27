#!/usr/bin/env python3
"""Compare two clean D2 execution package builds and freeze a canonical package."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tarfile
from typing import Any

STAGE = "H3/N2 Stage 2D-9R G3R successor"
PAYLOAD_NAME = "stage2d9r-successor-d2-execution-package-v1.tar"
BUILD_SCHEMA = "gh.h3.n2.stage2d9r-successor-d2-execution-clean-build/1"
DESCRIPTOR_SCHEMA = "gh.h3.n2.stage2d9r-successor-d2-execution-package/1"
FREEZE_SCHEMA = "gh.h3.n2.stage2d9r-successor-d2-execution-freeze/1"
EXPECTED_OUTER = {"build-record.json", "payload-tar.sha256", PAYLOAD_NAME}
EXPECTED_MEMBERS = {
    "D2_EXECUTION_PACKAGE_CONTRACT.md",
    "EXECUTION_PACKAGE_DESCRIPTOR.json",
    "README.md",
    "SHA256SUMS",
    "h3_n2_stage2d9r_successor_d2_execute_20260727_v1.py",
    "run_stage2d9r_successor_d2_execute_20260727_v1.sh",
}
FALSE_KEYS = (
    "authorization_record_included", "private_content_included",
    "private_paths_included", "secret_values_included",
    "authorization_created", "authorization_claimed", "authorization_consumed",
    "execution_authorized", "recovery_authorized", "board_operation",
    "serial_operation", "flash_operation", "physical_nvs_operation",
    "network_operation", "broker_started", "prepare_executed",
    "verify_executed", "activate_executed", "cleanup_executed",
    "production_operation", "efuse_operation", "secure_boot_changed",
    "flash_encryption_changed", "ready_authorized", "merge_authorized",
    "release_authorized", "tag_authorized", "deployment_authorized",
)


class FreezeError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise FreezeError(code)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: object) -> str:
    return sha256_bytes(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8"))


def package_set_sha256(files: dict[str, bytes]) -> str:
    return canonical_sha256({
        "schema": "gh.h3.n2.stage2d9r-successor-d2-execution-package-set/1",
        "files": [
            {"name": name, "sha256": sha256_bytes(files[name])}
            for name in sorted(files)
        ],
    })


def parse_sums(value: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in value.decode("utf-8").splitlines():
        if not line:
            continue
        parts = line.split("  ", 1)
        require(len(parts) == 2, "SHA256SUMS_INVALID")
        digest, name = parts
        require(len(digest) == 64 and name not in result and "/" not in name,
                "SHA256SUMS_INVALID")
        result[name] = digest
    return result


def validate_build(root: Path) -> tuple[dict[str, Any], bytes, dict[str, bytes]]:
    require(root.is_dir() and not root.is_symlink(), "BUILD_ROOT_INVALID")
    require({p.name for p in root.iterdir()} == EXPECTED_OUTER,
            "BUILD_OUTER_INVENTORY_MISMATCH")
    record = json.loads((root / "build-record.json").read_text(encoding="utf-8"))
    require(record.get("schema") == BUILD_SCHEMA, "BUILD_SCHEMA_MISMATCH")
    require(record.get("stage") == STAGE, "BUILD_STAGE_MISMATCH")
    require(record.get("state") == "CLEAN_BUILD_COMPLETE", "BUILD_STATE_MISMATCH")
    for key in FALSE_KEYS:
        require(record.get(key) is False, f"BUILD_BOUNDARY_EXPANDED_{key.upper()}")
    payload = (root / PAYLOAD_NAME).read_bytes()
    payload_sha = sha256_bytes(payload)
    require((root / "payload-tar.sha256").read_text().strip() == payload_sha,
            "PAYLOAD_DIGEST_TEXT_MISMATCH")
    require(record.get("payload_tar_sha256") == payload_sha,
            "BUILD_PAYLOAD_DIGEST_MISMATCH")
    files: dict[str, bytes] = {}
    with tarfile.open(fileobj=None, name=str(root / PAYLOAD_NAME), mode="r") as archive:
        members = archive.getmembers()
        require({m.name for m in members} == EXPECTED_MEMBERS,
                "PAYLOAD_INVENTORY_MISMATCH")
        require(len(members) == len(EXPECTED_MEMBERS), "PAYLOAD_DUPLICATE_MEMBER")
        for member in members:
            require(
                member.isfile() and member.mode == 0o600 and member.uid == 0
                and member.gid == 0 and member.mtime == 0 and member.uname == ""
                and member.gname == "",
                "PAYLOAD_TAR_METADATA_MISMATCH",
            )
            handle = archive.extractfile(member)
            require(handle is not None, "PAYLOAD_MEMBER_UNREADABLE")
            files[member.name] = handle.read()
    sums = parse_sums(files["SHA256SUMS"])
    require(set(sums) == EXPECTED_MEMBERS - {"SHA256SUMS"},
            "SHA256SUMS_COVERAGE_MISMATCH")
    for name, digest in sums.items():
        require(sha256_bytes(files[name]) == digest,
                "PAYLOAD_MEMBER_DIGEST_MISMATCH")
    descriptor = json.loads(files["EXECUTION_PACKAGE_DESCRIPTOR.json"])
    require(descriptor.get("schema") == DESCRIPTOR_SCHEMA,
            "DESCRIPTOR_SCHEMA_MISMATCH")
    require(descriptor.get("stage") == STAGE, "DESCRIPTOR_STAGE_MISMATCH")
    require(descriptor.get("state") == "REVIEWED_SOURCE_PACKAGE_NOT_AUTHORIZED",
            "DESCRIPTOR_STATE_MISMATCH")
    for key in FALSE_KEYS:
        require(descriptor.get(key) is False,
                f"DESCRIPTOR_BOUNDARY_EXPANDED_{key.upper()}")
    package_sha = package_set_sha256(files)
    require(record.get("execution_package_sha256") == package_sha,
            "BUILD_PACKAGE_SET_DIGEST_MISMATCH")
    require(record.get("execution_script_sha256")
            == sha256_bytes(files["h3_n2_stage2d9r_successor_d2_execute_20260727_v1.py"]),
            "BUILD_SCRIPT_DIGEST_MISMATCH")
    require(record.get("execution_launcher_sha256")
            == sha256_bytes(files["run_stage2d9r_successor_d2_execute_20260727_v1.sh"]),
            "BUILD_LAUNCHER_DIGEST_MISMATCH")
    joined = b"\n".join(files.values())
    for forbidden in (
        b"BEGIN PRIVATE KEY", b"/Users/", b"/dev/cu.", b"/dev/tty.",
        b"authorized\": true",
    ):
        require(forbidden not in joined, "PUBLIC_PACKAGE_PRIVATE_CONTENT")
    return record, payload, files


def freeze(build_a: Path, build_b: Path, output: Path, source_sha: str) -> dict[str, Any]:
    require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
    record_a, payload_a, files_a = validate_build(build_a)
    record_b, payload_b, files_b = validate_build(build_b)
    require(record_a.get("source_sha") == source_sha == record_b.get("source_sha"),
            "SOURCE_SHA_MISMATCH")
    require(record_a.get("lane") == "a" and record_b.get("lane") == "b",
            "LANE_MISMATCH")
    require(record_a.get("run_id") != record_b.get("run_id"),
            "RUN_ID_NOT_INDEPENDENT")
    require(record_a.get("artifact_name") != record_b.get("artifact_name"),
            "ARTIFACT_NAME_NOT_INDEPENDENT")
    require(payload_a == payload_b and files_a == files_b,
            "INDEPENDENT_BUILDS_NOT_IDENTICAL")
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    (output / PAYLOAD_NAME).write_bytes(payload_a)
    (output / "payload-tar.sha256").write_text(
        sha256_bytes(payload_a) + "\n", encoding="utf-8"
    )
    (output / "build-a-record.json").write_text(
        json.dumps(record_a, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "build-b-record.json").write_text(
        json.dumps(record_b, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest = {
        "schema": FREEZE_SCHEMA,
        "stage": STAGE,
        "state": "D2_EXECUTION_PACKAGE_REPRODUCIBLE_AND_FROZEN",
        "source_sha": source_sha,
        "payload_tar_sha256": sha256_bytes(payload_a),
        "execution_package_sha256": record_a["execution_package_sha256"],
        "execution_script_sha256": record_a["execution_script_sha256"],
        "execution_launcher_sha256": record_a["execution_launcher_sha256"],
        "execution_marker_name_sha256": record_a["execution_marker_name_sha256"],
        "clean_build_count": 2,
        "payloads_byte_identical": True,
        "build_a": {"run_id": record_a["run_id"], "artifact_name": record_a["artifact_name"]},
        "build_b": {"run_id": record_b["run_id"], "artifact_name": record_b["artifact_name"]},
        **{key: False for key in FALSE_KEYS},
    }
    (output / "freeze-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    entries = []
    for path in sorted(output.iterdir(), key=lambda p: p.name):
        os.chmod(path, 0o600)
        entries.append(f"{sha256_file(path)}  {path.name}")
    (output / "SHA256SUMS").write_text("\n".join(entries) + "\n", encoding="utf-8")
    os.chmod(output / "SHA256SUMS", 0o600)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-a", type=Path, required=True)
    parser.add_argument("--build-b", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args()
    try:
        value = freeze(
            args.build_a.resolve(strict=True),
            args.build_b.resolve(strict=True),
            args.output_dir.resolve(strict=False),
            args.source_sha,
        )
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, FreezeError) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps({"status": "PASS", **value}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
