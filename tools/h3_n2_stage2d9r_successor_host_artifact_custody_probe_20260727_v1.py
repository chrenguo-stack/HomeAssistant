#!/usr/bin/env python3
"""Read-only host Artifact and successor private-custody metadata probe.

The probe validates the frozen public immutable Artifact byte-for-byte. In local
mode it additionally reads only the successor private descriptor, redacted public
descriptor, and consumed-marker metadata. It never reads secret material files,
prints private paths, opens a socket/serial port, or performs firmware commands.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tarfile
from typing import Any, Mapping

SCHEMA = "gh.h3.n2.stage2d9r-successor-host-artifact-custody-preauth-probe/1"
STAGE = "H3/N2 Stage 2D-9R G3R successor"
RUN_SUFFIX = "tlsvalid02"
AUTHORIZATION_ID = "U1-H3N2-STAGE2D9R-PRIVATE-EXECUTION-MATERIAL-20260725-01"
AUTH_RECORD_SHA256 = "99d5f8cf5a0a12d921497ce04b7dc95161fc77ee79e79ddf50d6cb2535473817"
CONSUMED_MARKER_SHA256 = "428231f9e0e6a26c39701427b3e32531e18d08b54e341736b1189a78a06848a5"
PRIVATE_PACKAGE_SHA256 = "7b585fc53b9201fd2c6161e544ac062d4223f509bfc86a10052d97907e4f55bb"
PUBLIC_DESCRIPTOR_SHA256 = "7021279f141f00cbf7e64fe8a20e89dd8b8ef3b9c4c7625ec28b79f6d65db2b6"
SOURCE_SHA = "0cd9eeb5fd567d47a29bddee83159ac9570aa3dd"
BUILD_SOURCE_SHA = "ac1d2a7a92323988c9cd946a3e018e4f1ba9463b"
BUILD_BINDING = "742f663333837366a42da92b984a3b05c643f571"
PYTHON_EXECUTABLE_SHA256 = "4e28e811a89aeac6eed668ae641c7f85f5831e42e8dc6cd9a85a3bcc032ec46a"

CUSTODY_RELATIVE = Path(
    ".local/state/greenhouse-stage2d9r/private-execution-material-tlsvalid02"
)
AUTH_RELATIVE = Path(".local/state/greenhouse-stage2d9r/authorizations")
PRIVATE_DESCRIPTOR = "private-custody-descriptor.json"
PUBLIC_DESCRIPTOR = "public-descriptor.redacted.json"

GENERATOR_SHA256 = "38f7609030fcbeb33b2000bc3db0af3179dac0ed993484f2b22d0990f7720abd"
CONTRACT_SHA256 = "95c33d9d1cbb051e23621264a51c1b77bf674c0d403e2e813d1936ab9f9dbfb0"
PROTOCOL_SHA256 = "2520c292151b240827083272673df82441fd68b4e022ab0320311866d2bd4f18"
OPENSSL_SHA256 = "04ad05ce2e7eaf92116dac99a984cc0e589040a103589f93a9fe452832766973"
MOSQUITTO_PASSWD_SHA256 = "d6fdc23fa4bb09198bf74925207aa2b69b1455970e31fefc6157dfe4be2b07ee"

CA_PEM_SHA256 = "9d98b4aa1d87604e8c37aaa50892bf4cd47b8b8a0479acdabe78d41d39b36096"
BROKER_PEM_SHA256 = "d862dfe123f8d9ce755bb65e556cc064404b4d37f6b760295c94129ae1815384"
BROKER_FULLCHAIN_SHA256 = "0ad309c0048530287330b7edd8dd99da3f6816015355169b878116314863ff9a"
BROKER_DER_SHA256 = "4ca8731424c87ba61336f4bc4fb743137ed83c127ed1a214198b65e5b33b40f9"
BROKER_SPKI_SHA256 = "0ae2d32c2ddfb7b4b63c9ee4049291d9725a42a55721b0e78d53fcf5c9e1f72e"
CANDIDATE_DIGEST_SHA256 = "a0ff758217a1769c1876336c131cb85e64dcb2369758c649f36798cd8083aaf2"
UNLOCK_DIGEST_SHA256 = "727db669e17634b6d66fc1d8bd4f4d9e4e4e196401806c9b56c7eed6b8a7d9e9"
PERSISTENCE_KEY_FILE_SHA256 = "661a5cf28173d481ddb8bc4e239fb5aced6e67ec574a79c774f238dbb4d0b882"
PREPARE_COMMAND_SHA256 = "294df853b85fd86ae31ae05dc68b44fa3deac0cbffdbb8c24f62ca8175ef641f"
VERIFY_COMMAND_SHA256 = "53965a7dc1ec4265cc21eee11a03a22e0bc20ff6c8e3ffa56f42b4043da8c347"

ARTIFACT = {
    "tar": "14e882f550ca92d14cf6776e518eb083b7344683b5534487bd28e95d93b29747",
    "record": "1f28fe8128406b7cce7bb3c481d28db563a4098b43cd3d6118005169627e43ad",
    "sha_file": "66483aa995669032575f2ad1265172e8a86eb9ad67dcd8398c811cfa5d1280a1",
    "payload_json": "3bff1da3e8634b5634c587bb39f54c7da06e79e5f7cbf1257ee5d9824871b4d3",
    "application": "a75e440c90aa5f050ac55086d1f1c614f113a7b66bd31ffc748fee95b9d26e1b",
    "bootloader": "c7cd7c7f49e4a5bb3dc510d64b40eb92ff5b252ee81f3c0ed36eab02b17a5439",
    "partition": "b3964cbbd811d5fa5866638585fa410b53fc74e70a8f92491f43fce0b7a70268",
    "merged": "925ae87831a259d5a477fba9dde009b4d6a218e43735638521d4a10a38fe95bf",
}
REQUIRED_PRIVATE_FILES = (
    "mqtt-password.hex",
    "mosquitto.password",
    "persistence-key.hex",
    "unlock-token.hex",
    "prepare-command.txt",
    "verify-command.txt",
    "root-ca.key.pem",
    "root-ca.cert.pem",
    "broker.key.pem",
    "broker.cert.pem",
    "broker.fullchain.pem",
    "mosquitto.stage2d9r.conf",
    "mosquitto.stage2d9r.acl",
)
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FALSE_PUBLIC_FIELDS = (
    "private_values_included",
    "private_paths_included",
    "secret_values_included",
    "execution_authorized",
    "board_operation_authorized",
    "serial_operation_authorized",
    "flash_operation_authorized",
    "physical_nvs_operation_authorized",
    "network_operation_authorized",
    "broker_start_authorized",
    "prepare_authorized",
    "verify_authorized",
    "activate_authorized",
    "cleanup_authorized",
    "production_operation_authorized",
)


class ProbeError(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ProbeError(code)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def file_mode(path: Path) -> str:
    return f"{stat.S_IMODE(path.stat().st_mode):04o}"


def require_regular(path: Path, mode: str, code: str) -> None:
    require(path.is_file() and not path.is_symlink(), code)
    require(file_mode(path) == mode, code)


def canonical_json_sha256(value: object) -> str:
    return sha256_bytes(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    )


def private_material_digest(materials: Mapping[str, Mapping[str, str]]) -> str:
    require(set(materials) == set(REQUIRED_PRIVATE_FILES), "PRIVATE_INVENTORY_MISMATCH")
    ordered: dict[str, dict[str, str]] = {}
    for name in sorted(materials):
        metadata = materials[name]
        require(metadata.get("relative_path") == name, "PRIVATE_RELATIVE_PATH_MISMATCH")
        require(metadata.get("mode") == "0600", "PRIVATE_MODE_MISMATCH")
        digest = metadata.get("sha256")
        require(isinstance(digest, str) and HEX64.fullmatch(digest) is not None,
                "PRIVATE_DIGEST_INVALID")
        ordered[name] = {
            "relative_path": name,
            "mode": "0600",
            "sha256": digest,
        }
    return canonical_json_sha256(
        {
            "schema": "gh.h3.n2.stage2d9r-private-execution-material-set/1",
            "materials": ordered,
        }
    )


def parse_sums(data: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in data.decode("utf-8").splitlines():
        if not line:
            continue
        parts = line.split("  ", 1)
        require(len(parts) == 2, "SHA256SUMS_INVALID")
        digest, name = parts
        require(
            HEX64.fullmatch(digest) is not None and name not in result,
            "SHA256SUMS_INVALID",
        )
        result[name] = digest
    return result


def validate_immutable(root: Path) -> dict[str, object]:
    require(root.is_dir() and not root.is_symlink(), "ARTIFACT_ROOT_INVALID")
    expected_outer = {
        "build-record.json",
        "payload-tar.sha256",
        "stage2d9r-g3r-successor-immutable-payload-v1.tar",
    }
    require({p.name for p in root.iterdir()} == expected_outer, "ARTIFACT_OUTER_INVENTORY_MISMATCH")
    record_path = root / "build-record.json"
    digest_path = root / "payload-tar.sha256"
    tar_path = root / "stage2d9r-g3r-successor-immutable-payload-v1.tar"
    for path in (record_path, digest_path, tar_path):
        require_regular(path, "0600", "ARTIFACT_OUTER_FILE_INVALID")
    require(sha256_file(record_path) == ARTIFACT["record"], "ARTIFACT_RECORD_DIGEST_MISMATCH")
    require(sha256_file(digest_path) == ARTIFACT["sha_file"], "ARTIFACT_DIGEST_FILE_MISMATCH")
    require(sha256_file(tar_path) == ARTIFACT["tar"], "ARTIFACT_TAR_DIGEST_MISMATCH")
    require(digest_path.read_text().strip() == ARTIFACT["tar"], "ARTIFACT_DIGEST_TEXT_MISMATCH")

    expected_members = {
        "SHA256SUMS",
        "application.bin",
        "bootloader.bin",
        "firmware-payload.json",
        "merged-image.bin",
        "partition-table.bin",
    }
    files: dict[str, bytes] = {}
    with tarfile.open(tar_path, "r") as archive:
        members = archive.getmembers()
        require({m.name for m in members} == expected_members, "ARTIFACT_TAR_INVENTORY_MISMATCH")
        require(len(members) == len(expected_members), "ARTIFACT_TAR_DUPLICATE_MEMBER")
        for member in members:
            require(
                member.isfile()
                and member.mode == 0o600
                and member.uid == 0
                and member.gid == 0
                and member.mtime == 0
                and member.uname == ""
                and member.gname == "",
                "ARTIFACT_TAR_METADATA_MISMATCH",
            )
            handle = archive.extractfile(member)
            require(handle is not None, "ARTIFACT_TAR_MEMBER_UNREADABLE")
            files[member.name] = handle.read()

    sums = parse_sums(files["SHA256SUMS"])
    require(set(sums) == expected_members - {"SHA256SUMS"}, "ARTIFACT_SUMS_COVERAGE_MISMATCH")
    for name, digest in sums.items():
        require(sha256_bytes(files[name]) == digest, "ARTIFACT_MEMBER_DIGEST_MISMATCH")
    expected_hashes = {
        "application.bin": ARTIFACT["application"],
        "bootloader.bin": ARTIFACT["bootloader"],
        "partition-table.bin": ARTIFACT["partition"],
        "merged-image.bin": ARTIFACT["merged"],
        "firmware-payload.json": ARTIFACT["payload_json"],
    }
    for name, digest in expected_hashes.items():
        require(sha256_bytes(files[name]) == digest, "ARTIFACT_FROZEN_DIGEST_MISMATCH")

    payload = json.loads(files["firmware-payload.json"])
    require(
        payload.get("schema")
        == "gh.h3.n2.stage2d9r-successor-immutable-firmware-payload/1",
        "ARTIFACT_PAYLOAD_SCHEMA_MISMATCH",
    )
    require(payload.get("stage") == STAGE, "ARTIFACT_PAYLOAD_STAGE_MISMATCH")
    require(payload.get("source_sha") == BUILD_SOURCE_SHA, "ARTIFACT_SOURCE_SHA_MISMATCH")
    require(payload.get("build_binding") == BUILD_BINDING, "ARTIFACT_BUILD_BINDING_MISMATCH")
    require(
        payload.get("candidate_bindings")
        == {
            "broker_certificate_der_sha256": BROKER_DER_SHA256,
            "broker_host": "stage2d9r.local",
            "broker_spki_sha256": BROKER_SPKI_SHA256,
            "broker_tls_server_name": "stage2d9r.local",
            "ca_pem_sha256": CA_PEM_SHA256,
            "candidate_digest_sha256": CANDIDATE_DIGEST_SHA256,
            "unlock_digest_sha256": UNLOCK_DIGEST_SHA256,
        },
        "ARTIFACT_CANDIDATE_BINDING_MISMATCH",
    )
    for key in (
        "private_values_included",
        "private_paths_included",
        "secret_values_included",
        "execution_authorized",
        "board_operation_authorized",
        "serial_operation_authorized",
        "flash_operation_authorized",
        "physical_nvs_operation_authorized",
        "network_operation_authorized",
        "broker_operation_authorized",
        "prepare_authorized",
        "verify_authorized",
        "activate_authorized",
        "cleanup_authorized",
        "production_operation_authorized",
        "ready_authorized",
        "merge_authorized",
        "release_authorized",
    ):
        require(payload.get(key) is False, "ARTIFACT_AUTHORIZATION_EXPANDED")
    return {
        "source_sha": BUILD_SOURCE_SHA,
        "build_binding": BUILD_BINDING,
        "payload_tar_sha256": ARTIFACT["tar"],
        "application_sha256": ARTIFACT["application"],
        "merged_image_sha256": ARTIFACT["merged"],
        "candidate_digest_sha256": CANDIDATE_DIGEST_SHA256,
        "ca_pem_sha256": CA_PEM_SHA256,
    }


def validate_public_descriptor(path: Path) -> dict[str, Any]:
    require_regular(path, "0600", "PUBLIC_DESCRIPTOR_INVALID")
    data = path.read_bytes()
    require(sha256_bytes(data) == PUBLIC_DESCRIPTOR_SHA256, "PUBLIC_DESCRIPTOR_DIGEST_MISMATCH")
    value = json.loads(data)
    require(
        value.get("schema")
        == "gh.h3.n2.stage2d9r-private-execution-material-successor-public/1",
        "PUBLIC_DESCRIPTOR_SCHEMA_MISMATCH",
    )
    require(value.get("stage") == STAGE, "PUBLIC_DESCRIPTOR_STAGE_MISMATCH")
    require(value.get("state") == "SUCCESSOR_EXECUTION_MATERIAL_FROZEN",
            "PUBLIC_DESCRIPTOR_STATE_MISMATCH")
    require(value.get("source_sha") == SOURCE_SHA, "PUBLIC_DESCRIPTOR_SOURCE_MISMATCH")
    require(value.get("run_suffix") == RUN_SUFFIX, "PUBLIC_DESCRIPTOR_SUFFIX_MISMATCH")
    require(value.get("broker_host") == "stage2d9r.local", "PUBLIC_DESCRIPTOR_HOST_MISMATCH")
    require(value.get("broker_tls_server_name") == "stage2d9r.local",
            "PUBLIC_DESCRIPTOR_TLS_NAME_MISMATCH")
    require(value.get("broker_port") == 8883, "PUBLIC_DESCRIPTOR_PORT_MISMATCH")
    expected = {
        "private_package_sha256": PRIVATE_PACKAGE_SHA256,
        "unlock_digest_sha256": UNLOCK_DIGEST_SHA256,
        "persistence_key_file_sha256": PERSISTENCE_KEY_FILE_SHA256,
        "ca_pem_sha256": CA_PEM_SHA256,
        "broker_certificate_der_sha256": BROKER_DER_SHA256,
        "broker_spki_sha256": BROKER_SPKI_SHA256,
        "candidate_digest_sha256": CANDIDATE_DIGEST_SHA256,
        "prepare_command_sha256": PREPARE_COMMAND_SHA256,
        "verify_command_sha256": VERIFY_COMMAND_SHA256,
    }
    for key, digest in expected.items():
        require(value.get(key) == digest, "PUBLIC_DESCRIPTOR_BINDING_MISMATCH")
    for key in FALSE_PUBLIC_FIELDS:
        require(value.get(key) is False, "PUBLIC_DESCRIPTOR_AUTHORIZATION_EXPANDED")
    return value


def validate_custody(home: Path) -> dict[str, object]:
    home = home.expanduser().resolve(strict=True)
    root = (home / CUSTODY_RELATIVE).resolve(strict=False)
    require(root.exists() and root.is_dir() and not root.is_symlink(), "CUSTODY_ROOT_INVALID")
    require(file_mode(root) == "0700", "CUSTODY_ROOT_MODE_MISMATCH")
    require(root == (home / CUSTODY_RELATIVE).resolve(strict=False), "CUSTODY_SELECTION_RULE_MISMATCH")

    expected_inventory = set(REQUIRED_PRIVATE_FILES) | {PRIVATE_DESCRIPTOR, PUBLIC_DESCRIPTOR}
    require({p.name for p in root.iterdir()} == expected_inventory, "CUSTODY_INVENTORY_MISMATCH")
    for name in REQUIRED_PRIVATE_FILES:
        path = root / name
        require_regular(path, "0600", "PRIVATE_MATERIAL_METADATA_INVALID")
        require(path.stat().st_size > 0, "PRIVATE_MATERIAL_EMPTY")
    for name in ("mqtt-password.hex", "persistence-key.hex", "unlock-token.hex"):
        require((root / name).stat().st_size == 65, "SECRET_FILE_SIZE_MISMATCH")

    private_path = root / PRIVATE_DESCRIPTOR
    require_regular(private_path, "0600", "PRIVATE_DESCRIPTOR_INVALID")
    private_data = private_path.read_bytes()
    private = json.loads(private_data)
    require(
        private.get("schema")
        == "gh.h3.n2.stage2d9r-private-execution-material-successor-custody/1",
        "PRIVATE_DESCRIPTOR_SCHEMA_MISMATCH",
    )
    require(private.get("stage") == STAGE, "PRIVATE_DESCRIPTOR_STAGE_MISMATCH")
    require(private.get("state") == "SUCCESSOR_EXECUTION_MATERIAL_FROZEN",
            "PRIVATE_DESCRIPTOR_STATE_MISMATCH")
    require(private.get("source_sha") == SOURCE_SHA, "PRIVATE_DESCRIPTOR_SOURCE_MISMATCH")
    require(private.get("run_suffix") == RUN_SUFFIX, "PRIVATE_DESCRIPTOR_SUFFIX_MISMATCH")
    require(private.get("custody_root") == str(root), "PRIVATE_DESCRIPTOR_ROOT_MISMATCH")
    require(private.get("custody_root_mode") == "0700", "PRIVATE_DESCRIPTOR_ROOT_MODE_MISMATCH")
    toolchain = {
        "generator_sha256": GENERATOR_SHA256,
        "contract_sha256": CONTRACT_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "python_executable_sha256": PYTHON_EXECUTABLE_SHA256,
        "openssl_executable_sha256": OPENSSL_SHA256,
        "mosquitto_passwd_executable_sha256": MOSQUITTO_PASSWD_SHA256,
    }
    for key, digest in toolchain.items():
        require(private.get(key) == digest, "PRIVATE_DESCRIPTOR_TOOLCHAIN_MISMATCH")

    materials = private.get("materials")
    require(isinstance(materials, dict), "PRIVATE_DESCRIPTOR_MATERIALS_INVALID")
    observed_package = private_material_digest(materials)
    require(observed_package == PRIVATE_PACKAGE_SHA256, "PRIVATE_PACKAGE_DIGEST_MISMATCH")
    require(private.get("private_package_sha256") == observed_package,
            "PRIVATE_DESCRIPTOR_PACKAGE_BINDING_MISMATCH")
    require(private.get("public_descriptor_sha256") == PUBLIC_DESCRIPTOR_SHA256,
            "PRIVATE_DESCRIPTOR_PUBLIC_BINDING_MISMATCH")
    expected_material_digests = {
        "persistence-key.hex": PERSISTENCE_KEY_FILE_SHA256,
        "prepare-command.txt": PREPARE_COMMAND_SHA256,
        "verify-command.txt": VERIFY_COMMAND_SHA256,
        "root-ca.cert.pem": CA_PEM_SHA256,
        "broker.cert.pem": BROKER_PEM_SHA256,
        "broker.fullchain.pem": BROKER_FULLCHAIN_SHA256,
    }
    for name, digest in expected_material_digests.items():
        require(materials[name]["sha256"] == digest, "PRIVATE_PUBLIC_DIGEST_CROSS_BINDING_MISMATCH")

    authorization = private.get("authorization")
    require(isinstance(authorization, dict), "PRIVATE_DESCRIPTOR_AUTHORIZATION_INVALID")
    require(authorization.get("authorization_id") == AUTHORIZATION_ID,
            "PRIVATE_DESCRIPTOR_AUTHORIZATION_ID_MISMATCH")
    require(authorization.get("record_sha256") == AUTH_RECORD_SHA256,
            "PRIVATE_DESCRIPTOR_RECORD_MISMATCH")
    require(authorization.get("one_shot") is True, "PRIVATE_DESCRIPTOR_ONE_SHOT_MISMATCH")
    require(authorization.get("replay_permitted") is False,
            "PRIVATE_DESCRIPTOR_REPLAY_BOUNDARY_MISMATCH")
    require(authorization.get("automatic_retry_permitted") is False,
            "PRIVATE_DESCRIPTOR_RETRY_BOUNDARY_MISMATCH")
    require(authorization.get("consumed") is True, "PRIVATE_DESCRIPTOR_CONSUMED_MISMATCH")
    for key in (
        "private_values_included",
        "raw_private_values_in_descriptor",
        "board_operation_authorized",
        "network_operation_authorized",
        "broker_start_authorized",
        "flash_operation_authorized",
        "physical_nvs_operation_authorized",
        "prepare_authorized",
        "verify_authorized",
        "activate_authorized",
        "cleanup_authorized",
        "production_operation_authorized",
    ):
        require(private.get(key) is False, "PRIVATE_DESCRIPTOR_AUTHORIZATION_EXPANDED")
    proofs = private.get("offline_proofs")
    require(
        isinstance(proofs, dict)
        and proofs
        and all(value is True for value in proofs.values()),
        "PRIVATE_DESCRIPTOR_OFFLINE_PROOF_MISMATCH",
    )

    public = validate_public_descriptor(root / PUBLIC_DESCRIPTOR)
    require(public["private_package_sha256"] == observed_package,
            "PUBLIC_PRIVATE_PACKAGE_CROSS_BINDING_MISMATCH")

    marker = (
        home
        / AUTH_RELATIVE
        / f"{AUTHORIZATION_ID}.consumed.json"
    ).resolve(strict=False)
    require_regular(marker, "0600", "CONSUMED_MARKER_INVALID")
    marker_before = sha256_file(marker)
    require(marker_before == CONSUMED_MARKER_SHA256, "CONSUMED_MARKER_DIGEST_MISMATCH")
    marker_value = json.loads(marker.read_text(encoding="utf-8"))
    require(
        marker_value.get("schema")
        == "gh.h3.n2.stage2d9r-private-execution-material-successor-u1-consumption/1",
        "CONSUMED_MARKER_SCHEMA_MISMATCH",
    )
    require(marker_value.get("authorization_id") == AUTHORIZATION_ID,
            "CONSUMED_MARKER_AUTHORIZATION_MISMATCH")
    require(marker_value.get("status") == "CONSUMED", "CONSUMED_MARKER_STATUS_MISMATCH")
    require(marker_value.get("record_sha256") == AUTH_RECORD_SHA256,
            "CONSUMED_MARKER_RECORD_MISMATCH")
    require(marker_value.get("public_descriptor_sha256") == PUBLIC_DESCRIPTOR_SHA256,
            "CONSUMED_MARKER_PUBLIC_DESCRIPTOR_MISMATCH")
    require(marker_value.get("failure_code") is None, "CONSUMED_MARKER_FAILURE_PRESENT")
    require(marker_value.get("one_shot") is True, "CONSUMED_MARKER_ONE_SHOT_MISMATCH")
    require(marker_value.get("replay_permitted") is False,
            "CONSUMED_MARKER_REPLAY_BOUNDARY_MISMATCH")
    require(marker_value.get("automatic_retry_permitted") is False,
            "CONSUMED_MARKER_RETRY_BOUNDARY_MISMATCH")
    require(marker_value.get("secret_values_included") is False,
            "CONSUMED_MARKER_SECRET_FLAG_MISMATCH")
    require(sha256_file(marker) == marker_before, "CONSUMED_MARKER_CHANGED_DURING_PROBE")

    return {
        "authorization_id": AUTHORIZATION_ID,
        "authorization_status": "CONSUMED",
        "authorization_record_sha256": AUTH_RECORD_SHA256,
        "consumed_marker_sha256": CONSUMED_MARKER_SHA256,
        "private_descriptor_sha256": sha256_bytes(private_data),
        "private_package_sha256": observed_package,
        "public_descriptor_sha256": PUBLIC_DESCRIPTOR_SHA256,
        "candidate_digest_sha256": CANDIDATE_DIGEST_SHA256,
        "metadata_file_count": len(expected_inventory),
        "root_mode": "0700",
        "all_material_modes": "0600",
        "marker_modified": False,
        "private_descriptor_metadata_read": True,
        "public_descriptor_read": True,
        "private_material_content_read": False,
        "private_paths_included": False,
        "secret_values_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--public-artifacts-only", action="store_true")
    args = parser.parse_args()
    failure_stage = "ARGUMENT_RESOLUTION"
    try:
        package_root = args.package_root.expanduser().resolve(strict=True)
        failure_stage = "PYTHON_TOOLCHAIN"
        python_sha = sha256_file(Path(sys.executable).resolve(strict=True))
        if not args.public_artifacts_only:
            require(python_sha == PYTHON_EXECUTABLE_SHA256, "PYTHON_EXECUTABLE_SHA256_MISMATCH")
            require(sys.version.startswith("3.11.9 "), "PYTHON_VERSION_MISMATCH")
        failure_stage = "IMMUTABLE_ARTIFACT"
        immutable = validate_immutable(package_root / "public-artifacts/immutable")
        failure_stage = "SUCCESSOR_PRIVATE_CUSTODY_METADATA"
        custody: object = (
            "NOT_EXECUTED_PUBLIC_ARTIFACT_MODE"
            if args.public_artifacts_only
            else validate_custody(args.home)
        )
        result = {
            "schema": SCHEMA,
            "stage": STAGE,
            "result": (
                "PASS_PUBLIC_ARTIFACTS_ONLY"
                if args.public_artifacts_only
                else "PASS_READ_ONLY_PREAUTH"
            ),
            "python_executable_sha256": python_sha,
            "immutable_artifact": immutable,
            "successor_private_custody": custody,
            "private_material_content_binding": (
                "DEFERRED_REQUIRES_SEPARATE_EXACT_U1"
                if not args.public_artifacts_only
                else "NOT_EXECUTED_PUBLIC_ARTIFACT_MODE"
            ),
            "authorization_created": False,
            "authorization_claimed": False,
            "authorization_consumed_by_probe": False,
            "private_material_content_read": False,
            "private_paths_included": False,
            "secret_values_included": False,
            "repository_required": False,
            "network_operation": False,
            "broker_started": False,
            "board_operation": False,
            "serial_operation": False,
            "flash_operation": False,
            "physical_nvs_operation": False,
            "prepare_executed": False,
            "verify_executed": False,
            "activate_executed": False,
            "cleanup_executed": False,
            "production_operation": False,
        }
        print("STAGE2D9R_SUCCESSOR_HOST_ARTIFACT_CUSTODY_PREAUTH_PROBE=PASS")
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        code = exc.args[0] if isinstance(exc, ProbeError) and exc.args else type(exc).__name__
        print("STAGE2D9R_SUCCESSOR_HOST_ARTIFACT_CUSTODY_PREAUTH_PROBE=FAIL")
        print(f"FAILURE_STAGE={failure_stage}")
        print(f"FAILURE_CODE={code}")
        for key in (
            "AUTHORIZATION_CREATED",
            "AUTHORIZATION_CLAIMED",
            "AUTHORIZATION_CONSUMED_BY_PROBE",
            "PRIVATE_MATERIAL_CONTENT_READ",
            "PRIVATE_PATHS_INCLUDED",
            "SECRET_VALUES_INCLUDED",
            "NETWORK_OPERATION",
            "BROKER_STARTED",
            "BOARD_OPERATION",
            "SERIAL_OPERATION",
            "FLASH_OPERATION",
            "PHYSICAL_NVS_OPERATION",
            "PREPARE_EXECUTED",
            "VERIFY_EXECUTED",
        ):
            print(f"{key}=false")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
