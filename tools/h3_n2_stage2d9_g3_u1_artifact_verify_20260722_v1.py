#!/usr/bin/env python3
"""Host-only U1 verifier for a frozen Stage2D9 G3 Artifact ZIP.

The verifier performs no serial, device, flash, eFuse, network, Broker or
production operation. It extracts to a temporary directory, validates exact
bindings and deletes the temporary directory automatically.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
import zipfile

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def find_root(extracted: Path) -> Path:
    direct = extracted / "stage2d9-g3-artifact-manifest-v67.json"
    if direct.is_file():
        return extracted
    manifests = list(extracted.rglob("stage2d9-g3-artifact-manifest-v67.json"))
    require(len(manifests) == 1, "Artifact manifest is not unique")
    return manifests[0].parent


def verify_checksums(root: Path) -> None:
    sums = root / "SHA256SUMS"
    require(sums.is_file(), "SHA256SUMS missing")
    for raw_line in sums.read_text(encoding="utf-8").splitlines():
        digest, relative = raw_line.split("  ", 1)
        require(HEX64.fullmatch(digest) is not None, "invalid checksum line")
        target = root / relative
        require(target.is_file(), f"checksum member missing: {relative}")
        require(sha256(target) == digest, f"checksum mismatch: {relative}")


def scan_private_material(root: Path) -> None:
    forbidden = (
        b"usbmodem",
        b"/users/",
        b"unlock_token_hex",
        b"persistence_key_hex",
        b"gh2d9_prepare_v1 ",
        b"gh2d9_verify_v1 ",
        b"begin private key",
    )
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        data = path.read_bytes().lower()
        for marker in forbidden:
            require(marker not in data, f"private marker found in {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--expected-zip-sha256", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-g3-merged-sha256", required=True)
    parser.add_argument("--expected-recovery-merged-sha256", required=True)
    parser.add_argument("--expected-seed-sha256", required=True)
    parser.add_argument("--expected-unlock-digest", required=True)
    args = parser.parse_args()

    print("BATCH_PACKAGE_ID=U1_STAGE2D9_G3_ARTIFACT_VERIFY_V1")
    print("BOARD_ACCESSED=false")
    print("SERIAL_ACCESS_ATTEMPTED=false")
    print("FLASH_OPERATION_ATTEMPTED=false")
    print("EFUSE_COMMAND_ATTEMPTED=false")
    print("NETWORK_OPERATION_ATTEMPTED=false")
    print("PRODUCTION_ENVIRONMENT_MODIFIED=false")

    try:
        for value, pattern, label in (
            (args.expected_zip_sha256, HEX64, "ZIP SHA"),
            (args.expected_source_commit, HEX40, "source commit"),
            (args.expected_g3_merged_sha256, HEX64, "G3 SHA"),
            (args.expected_recovery_merged_sha256, HEX64, "recovery SHA"),
            (args.expected_seed_sha256, HEX64, "seed SHA"),
            (args.expected_unlock_digest, HEX64, "unlock digest"),
        ):
            require(pattern.fullmatch(value) is not None, f"invalid {label}")

        zip_path = args.zip.expanduser().resolve()
        actual_zip_sha = sha256(zip_path)
        print(f"ARTIFACT_ZIP_SHA256={actual_zip_sha}")
        require(actual_zip_sha == args.expected_zip_sha256, "ZIP SHA mismatch")

        with tempfile.TemporaryDirectory(prefix="stage2d9-u1-") as temporary:
            temp = Path(temporary)
            with zipfile.ZipFile(zip_path) as archive:
                for name in archive.namelist():
                    member = Path(name)
                    require(not member.is_absolute(), "absolute ZIP member")
                    require(".." not in member.parts, "parent traversal ZIP member")
                archive.extractall(temp)
            root = find_root(temp)
            verify_checksums(root)
            scan_private_material(root)

            manifest_path = root / "stage2d9-g3-artifact-manifest-v67.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            require(manifest.get("gate") == "LOCKED", "Artifact gate is not LOCKED")
            require(
                manifest.get("source_commit") == args.expected_source_commit,
                "source commit mismatch",
            )
            require(
                manifest.get("unlock_digest_sha256") == args.expected_unlock_digest,
                "unlock digest mismatch",
            )
            require(
                manifest.get("unlock_preimage_in_artifact") is False,
                "unlock preimage present",
            )
            require(
                manifest.get("build_tools", {}).get("byte_identical") is True,
                "reproducibility missing",
            )
            partition = manifest.get("partition_table", {})
            require(partition.get("label") == "gh2d8_p2d9", "partition mismatch")
            require(partition.get("namespace") == "gh2d8_s2d9", "namespace mismatch")
            require(partition.get("offset") == "0x400000", "partition offset mismatch")
            require(partition.get("size") == "0x10000", "partition size mismatch")
            require(partition.get("writable_capable") is True, "partition not writable-capable")
            require(partition.get("target_namespace_absent_from_seed") is True, "seed target namespace present")
            require(partition.get("seed_image_sha256") == args.expected_seed_sha256, "seed SHA mismatch")

            packages = manifest.get("packages", {})
            g3_name = "stage2d9-g3-merged-v67.bin"
            recovery_name = "stage2d9-recovery-merged-v67.bin"
            require(
                packages.get("g3", {}).get(g3_name, {}).get("sha256")
                == args.expected_g3_merged_sha256,
                "G3 merged SHA mismatch",
            )
            require(
                packages.get("recovery", {}).get(recovery_name, {}).get("sha256")
                == args.expected_recovery_merged_sha256,
                "recovery merged SHA mismatch",
            )
            execution = manifest.get("execution", {})
            require(not any(bool(value) for value in execution.values()), "Artifact authorizes execution")

            print(f"MANIFEST_SHA256={sha256(manifest_path)}")
            print(f"SOURCE_COMMIT={manifest['source_commit']}")
            print(f"G3_MERGED_SHA256={args.expected_g3_merged_sha256}")
            print(f"RECOVERY_MERGED_SHA256={args.expected_recovery_merged_sha256}")
            print(f"SEED_SHA256={args.expected_seed_sha256}")
            print(f"UNLOCK_DIGEST_SHA256={args.expected_unlock_digest}")

        print("U1_STAGE2D9_G3_ARTIFACT_VERIFY=PASS")
        return 0
    except Exception as exc:
        print(f"FAILURE_CLASS={type(exc).__name__}")
        print(f"FAILURE_MESSAGE={str(exc).replace(chr(10), ' ')}")
        print("U1_STAGE2D9_G3_ARTIFACT_VERIFY=FAIL")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
