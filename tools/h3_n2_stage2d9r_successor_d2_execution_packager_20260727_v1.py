#!/usr/bin/env python3
"""Build a deterministic public-only Stage2D9R successor D2 execution package."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import tarfile
from typing import Any

STAGE = "H3/N2 Stage 2D-9R G3R successor"
SCHEMA = "gh.h3.n2.stage2d9r-successor-d2-execution-package/1"
BUILD_SCHEMA = "gh.h3.n2.stage2d9r-successor-d2-execution-clean-build/1"
PAYLOAD_NAME = "stage2d9r-successor-d2-execution-package-v1.tar"
EXECUTOR_NAME = "h3_n2_stage2d9r_successor_d2_execute_20260727_v1.py"
CONTRACT_NAME = "D2_EXECUTION_PACKAGE_CONTRACT.md"
DESCRIPTOR_NAME = "EXECUTION_PACKAGE_DESCRIPTOR.json"
README_NAME = "README.md"
LAUNCHER_NAME = "run_stage2d9r_successor_d2_execute_20260727_v1.sh"
D2_REQUEST_ID = "D2-H3N2-STAGE2D9R-G3R-SUCCESSOR-20260727-01"
IMMUTABLE_ARTIFACT_ID = 8638796771
IMMUTABLE_ARCHIVE_SHA256 = "b8c7e937ff325d121aeff8414618e88b8a229cca00bc27e439c587f830851dc8"
IMMUTABLE_PAYLOAD_TAR_SHA256 = "14e882f550ca92d14cf6776e518eb083b7344683b5534487bd28e95d93b29747"
IMMUTABLE_MERGED_SHA256 = "925ae87831a259d5a477fba9dde009b4d6a218e43735638521d4a10a38fe95bf"
RECOVERY_ARTIFACT_ID = 8644594652
RECOVERY_ARCHIVE_SHA256 = "3274a9329f46f420b65037efdf3cb9e453121ec7f74573430fb2afc8a7de882e"
RECOVERY_PAYLOAD_TAR_SHA256 = "50c4ff6569401b3c1cb20570ed149b0a5978fdc202c2aa33dff1b6ea1fe58d2e"
RECOVERY_DESCRIPTOR_SHA256 = "912e7e2ec4f10cb81836e5a50df1dd5745eae2ba057bd51b1929671fb5872beb"
PRIVATE_PACKAGE_SHA256 = "7b585fc53b9201fd2c6161e544ac062d4223f509bfc86a10052d97907e4f55bb"
PREPARE_COMMAND_SHA256 = "294df853b85fd86ae31ae05dc68b44fa3deac0cbffdbb8c24f62ca8175ef641f"
VERIFY_COMMAND_SHA256 = "53965a7dc1ec4265cc21eee11a03a22e0bc20ff6c8e3ffa56f42b4043da8c347"
CANDIDATE_DIGEST_SHA256 = "a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2"
CA_PEM_SHA256 = "9d98b4aa1d87604e8c37aaa50892bf4cd47b8b8a0479acdabe78d41d39b36096"
BUILD_BINDING = "742f663333837366a42da92b984a3b05c643f571"
FALSE_FLAGS = {
    "authorization_record_included": False,
    "private_content_included": False,
    "private_paths_included": False,
    "secret_values_included": False,
    "authorization_created": False,
    "authorization_claimed": False,
    "authorization_consumed": False,
    "execution_authorized": False,
    "recovery_authorized": False,
    "board_operation": False,
    "serial_operation": False,
    "flash_operation": False,
    "physical_nvs_operation": False,
    "network_operation": False,
    "broker_started": False,
    "prepare_executed": False,
    "verify_executed": False,
    "activate_executed": False,
    "cleanup_executed": False,
    "production_operation": False,
    "efuse_operation": False,
    "secure_boot_changed": False,
    "flash_encryption_changed": False,
    "ready_authorized": False,
    "merge_authorized": False,
    "release_authorized": False,
    "tag_authorized": False,
    "deployment_authorized": False,
}


class PackageError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PackageError(code)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_sha256(value: object) -> str:
    return sha256_bytes(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8"))


def deterministic_tar(path: Path, files: dict[str, bytes]) -> None:
    require(not path.exists(), "PAYLOAD_ALREADY_EXISTS")
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name in sorted(files):
            data = files[name]
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mode = 0o600
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            archive.addfile(info, io.BytesIO(data))
    os.chmod(path, 0o600)


def package_set_sha256(files: dict[str, bytes]) -> str:
    return canonical_sha256({
        "schema": "gh.h3.n2.stage2d9r-successor-d2-execution-package-set/1",
        "files": [
            {"name": name, "sha256": sha256_bytes(files[name])}
            for name in sorted(files)
        ],
    })


def build_files(executor: Path, contract: Path, source_sha: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    require(len(source_sha) == 40 and all(c in "0123456789abcdef" for c in source_sha),
            "SOURCE_SHA_INVALID")
    require(executor.is_file() and not executor.is_symlink(), "EXECUTOR_INVALID")
    require(contract.is_file() and not contract.is_symlink(), "CONTRACT_INVALID")
    executor_bytes = executor.read_bytes()
    contract_bytes = contract.read_bytes()
    require(b"Exact one-shot Stage2D9R successor physical executor" in executor_bytes,
            "EXECUTOR_IDENTITY_MISMATCH")
    require(b"REVIEWED_SOURCE_ONLY" in contract_bytes,
            "CONTRACT_BOUNDARY_MISSING")
    for prohibited in (
        b"authorized\": true",
        b"BEGIN PRIVATE KEY",
        b"/Users/",
        b"/dev/cu.",
        b"/dev/tty.",
    ):
        require(prohibited not in executor_bytes + contract_bytes,
                "PUBLIC_PACKAGE_PRIVATE_OR_AUTHORIZED_CONTENT")
    marker_name = sha256_bytes(D2_REQUEST_ID.encode("utf-8")) + ".json"
    descriptor: dict[str, Any] = {
        "schema": SCHEMA,
        "stage": STAGE,
        "state": "REVIEWED_SOURCE_PACKAGE_NOT_AUTHORIZED",
        "source_sha": source_sha,
        "d2_request_id": D2_REQUEST_ID,
        "executor_name": EXECUTOR_NAME,
        "executor_sha256": sha256_bytes(executor_bytes),
        "launcher_name": LAUNCHER_NAME,
        "execution_marker_name_sha256": sha256_bytes(marker_name.encode("utf-8")),
        "immutable": {
            "artifact_id": IMMUTABLE_ARTIFACT_ID,
            "artifact_archive_sha256": IMMUTABLE_ARCHIVE_SHA256,
            "payload_tar_sha256": IMMUTABLE_PAYLOAD_TAR_SHA256,
            "merged_image_sha256": IMMUTABLE_MERGED_SHA256,
            "build_binding": BUILD_BINDING,
        },
        "recovery": {
            "artifact_id": RECOVERY_ARTIFACT_ID,
            "artifact_archive_sha256": RECOVERY_ARCHIVE_SHA256,
            "payload_tar_sha256": RECOVERY_PAYLOAD_TAR_SHA256,
            "descriptor_sha256": RECOVERY_DESCRIPTOR_SHA256,
            "max_count": 1,
        },
        "private_bindings": {
            "private_package_sha256": PRIVATE_PACKAGE_SHA256,
            "prepare_command_sha256": PREPARE_COMMAND_SHA256,
            "verify_command_sha256": VERIFY_COMMAND_SHA256,
            "candidate_digest_sha256": CANDIDATE_DIGEST_SHA256,
            "ca_pem_sha256": CA_PEM_SHA256,
        },
        "normal_counts": {
            "flash_erase": 1,
            "flash_write": 1,
            "flash_verify": 1,
            "automatic_hard_reset": 1,
            "isolated_broker_start": 1,
            "prepare": 1,
            "verify": 1,
            "locked_recovery": 0,
        },
        "failure_counts": {
            "locked_recovery_max": 1,
            "automatic_retry": 0,
            "replay": 0,
        },
        **FALSE_FLAGS,
    }
    descriptor_bytes = json.dumps(
        descriptor, indent=2, sort_keys=True, ensure_ascii=False
    ).encode("utf-8") + b"\n"
    readme = f"""# Stage 2D-9R successor exact D2 execution package

State: `REVIEWED_SOURCE_PACKAGE_NOT_AUTHORIZED`

This package contains reviewed host source only. It cannot execute without a separate,
current, exact one-shot authorization record bound to every package, toolchain, board,
serial, baseline, immutable firmware, private command and recovery digest.

The launcher is deliberately stored as mode 0600 in the deterministic package. Invoke
it with `bash {LAUNCHER_NAME} ...` only after an exact D2 authorization has been issued.

Source SHA: `{source_sha}`
D2 request: `{D2_REQUEST_ID}`
""".encode("utf-8")
    launcher = f"""#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
cd "$ROOT"
sha256sum -c SHA256SUMS
exec python3 "$ROOT/{EXECUTOR_NAME}" --package-root "$ROOT" "$@"
""".encode("utf-8")
    files = {
        EXECUTOR_NAME: executor_bytes,
        CONTRACT_NAME: contract_bytes,
        DESCRIPTOR_NAME: descriptor_bytes,
        README_NAME: readme,
        LAUNCHER_NAME: launcher,
    }
    sums = "".join(
        f"{sha256_bytes(files[name])}  {name}\n" for name in sorted(files)
    ).encode("utf-8")
    files["SHA256SUMS"] = sums
    descriptor["launcher_sha256"] = sha256_bytes(launcher)
    descriptor["package_set_sha256"] = package_set_sha256(files)
    # Rewrite descriptor and sums after final public binding fields are known.
    files[DESCRIPTOR_NAME] = json.dumps(
        descriptor, indent=2, sort_keys=True, ensure_ascii=False
    ).encode("utf-8") + b"\n"
    files["SHA256SUMS"] = "".join(
        f"{sha256_bytes(files[name])}  {name}\n"
        for name in sorted(files) if name != "SHA256SUMS"
    ).encode("utf-8")
    descriptor["package_set_sha256"] = package_set_sha256(files)
    # Bind the final sums value once more; the package digest used by the executor is
    # calculated over the finished files and is frozen by the outer build record.
    return files, descriptor


def package(*, executor: Path, contract: Path, output_dir: Path,
            source_sha: str, lane: str, artifact_name: str, run_id: int) -> dict[str, Any]:
    require(lane in ("a", "b"), "LANE_INVALID")
    require(run_id > 0, "RUN_ID_INVALID")
    require(not output_dir.exists(), "OUTPUT_ALREADY_EXISTS")
    output_dir.mkdir(parents=True, mode=0o700)
    os.chmod(output_dir, 0o700)
    files, descriptor = build_files(executor, contract, source_sha)
    payload = output_dir / PAYLOAD_NAME
    deterministic_tar(payload, files)
    payload_sha = sha256_file(payload)
    finished_package_sha = package_set_sha256(files)
    record = {
        "schema": BUILD_SCHEMA,
        "stage": STAGE,
        "state": "CLEAN_BUILD_COMPLETE",
        "source_sha": source_sha,
        "lane": lane,
        "run_id": run_id,
        "artifact_name": artifact_name,
        "payload_name": PAYLOAD_NAME,
        "payload_tar_sha256": payload_sha,
        "execution_package_sha256": finished_package_sha,
        "execution_script_sha256": descriptor["executor_sha256"],
        "execution_launcher_sha256": descriptor["launcher_sha256"],
        "execution_marker_name_sha256": descriptor["execution_marker_name_sha256"],
        **FALSE_FLAGS,
    }
    (output_dir / "build-record.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "payload-tar.sha256").write_text(payload_sha + "\n", encoding="utf-8")
    for path in output_dir.iterdir():
        os.chmod(path, 0o600)
        require(stat.S_IMODE(path.stat().st_mode) == 0o600, "OUTPUT_MODE_MISMATCH")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executor", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--lane", choices=("a", "b"), required=True)
    parser.add_argument("--artifact-name", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    args = parser.parse_args()
    try:
        value = package(
            executor=args.executor.resolve(strict=True),
            contract=args.contract.resolve(strict=True),
            output_dir=args.output_dir.resolve(strict=False),
            source_sha=args.source_sha,
            lane=args.lane,
            artifact_name=args.artifact_name,
            run_id=args.run_id,
        )
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, PackageError) and exc.args else type(exc).__name__
        print(json.dumps({"status": "FAIL", "failure_code": str(code)}, sort_keys=True))
        return 2
    print(json.dumps({"status": "PASS", **value}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
