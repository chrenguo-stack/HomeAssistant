#!/usr/bin/env python3
"""Package and private-custody validators for repaired host final preflight."""
from __future__ import annotations

from h3_n2_stage2d9r_g3r_repaired_host_final_preflight_probe_common_20260728_v1 import *

def validate_review_archive(root: Path, sums: Mapping[str, str]) -> str:
    archive_path = root / packager.REVIEW_ARCHIVE_NAME
    regular(archive_path, "0600", "REVIEW_ARCHIVE_INVALID")
    with tarfile.open(archive_path, "r") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        require(len(names) == len(set(names)), "REVIEW_ARCHIVE_DUPLICATE_MEMBER")
        require(set(names) == set(sums) | {packager.SUMS_FILE}, "REVIEW_ARCHIVE_INVENTORY_MISMATCH")
        for member in members:
            pure = PurePosixPath(member.name)
            require(
                member.isfile()
                and not pure.is_absolute()
                and ".." not in pure.parts,
                "REVIEW_ARCHIVE_MEMBER_INVALID",
            )
            require(member.mode == 0o644, "REVIEW_ARCHIVE_MODE_MISMATCH")
            require(member.uid == 0 and member.gid == 0, "REVIEW_ARCHIVE_OWNER_MISMATCH")
            require(member.uname == "" and member.gname == "", "REVIEW_ARCHIVE_OWNER_MISMATCH")
            require(member.mtime == 0, "REVIEW_ARCHIVE_MTIME_MISMATCH")
            handle = archive.extractfile(member)
            require(handle is not None, "REVIEW_ARCHIVE_MEMBER_UNREADABLE")
            data = handle.read()
            if member.name == packager.SUMS_FILE:
                require(data == (root / packager.SUMS_FILE).read_bytes(), "REVIEW_ARCHIVE_SUMS_MISMATCH")
            else:
                require(sha256_bytes(data) == sums[member.name], "REVIEW_ARCHIVE_DIGEST_MISMATCH")
    return sha256_file(archive_path)


def validate_execution_package(root: Path, binding: Mapping[str, Any]) -> dict[str, str]:
    package = root / packager.EXECUTION_DIR
    require(package.is_dir() and not package.is_symlink(), "EXECUTION_PACKAGE_INVALID")
    sums = packager.parse_sums((package / packager.SUMS_FILE).read_bytes())
    observed = {
        path.name for path in package.iterdir()
        if path.is_file() and path.name != packager.SUMS_FILE
    }
    require(set(sums) == observed, "EXECUTION_PACKAGE_SUMS_COVERAGE_MISMATCH")
    for name, digest in sums.items():
        regular(package / name, "0600", "EXECUTION_PACKAGE_MEMBER_INVALID")
        require(sha256_file(package / name) == digest, "EXECUTION_PACKAGE_MEMBER_DIGEST_MISMATCH")
    package_sha = packager.canonical_execution_package_digest(package)
    require(
        package_sha == binding.get("execution_package_sha256"),
        "EXECUTION_PACKAGE_BINDING_MISMATCH",
    )
    result = {
        "execution_package_sha256": package_sha,
        "execution_wrapper_sha256": sha256_file(
            package / "h3_n2_stage2d9r_g3r_repaired_physical_d2_wrapper_20260728_v1.py"
        ),
        "execution_launcher_sha256": sha256_file(
            package / "run_stage2d9r_g3r_repaired_physical_d2_20260728_v1.sh"
        ),
        "repaired_host_controller_sha256": sha256_file(
            package / "h3_n2_stage2d9r_serial_handshake_repair_20260727_v1.py"
        ),
    }
    for key, observed_digest in result.items():
        require(binding.get(key) == observed_digest, "EXECUTION_" + key.upper() + "_MISMATCH")
    wrapper_text = (
        package / "h3_n2_stage2d9r_g3r_repaired_physical_d2_wrapper_20260728_v1.py"
    ).read_text(encoding="utf-8")
    require('"erase_region"' in wrapper_text, "RECOVERY_REGION_ERASE_MISSING")
    require("LOCKED_RECOVERY_PRE_READ_FAILED" in wrapper_text, "RECOVERY_PRE_READ_MISSING")
    require("LOCKED_RECOVERY_POST_READ_FAILED" in wrapper_text, "RECOVERY_POST_READ_MISSING")
    return result


def validate_package(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    root = root.expanduser().resolve(strict=True)
    require(root.is_dir() and not root.is_symlink(), "PACKAGE_ROOT_INVALID")
    require(file_mode(root) == "0700", "PACKAGE_ROOT_MODE_INVALID")
    sums = verify_recursive_sums(root)
    archive_sha = validate_review_archive(root, sums)
    binding = load_json(root / packager.BINDING_FILE, "0600", "REVIEW_BINDING_INVALID")
    request = load_json(root / packager.REQUEST_FILE, "0600", "REQUEST_DRAFT_INVALID")
    require(binding.get("schema") == packager.REVIEW_SCHEMA, "REVIEW_BINDING_SCHEMA_MISMATCH")
    require(
        binding.get("state") == "HOST_FINAL_PREFLIGHT_SOURCE_FROZEN_UNAUTHORIZED",
        "REVIEW_BINDING_STATE_MISMATCH",
    )
    observed_binding = dict(binding)
    supplied = observed_binding.pop("review_binding_sha256", None)
    require(supplied == canonical_sha256(observed_binding), "REVIEW_BINDING_DIGEST_MISMATCH")
    exact = {
        "base_pr": contract.BASE_PR,
        "base_head_sha": contract.BASE_HEAD_SHA,
        "baseline_original_main_sha": contract.BASELINE_ORIGINAL_MAIN_SHA,
        "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
        "immutable_artifact_id": contract.IMMUTABLE_ARTIFACT_ID,
        "immutable_artifact_sha256": contract.IMMUTABLE_ARTIFACT_SHA256,
        "final_execution_binding": contract.FINAL_EXECUTION_BINDING,
        "final_execution_binding_sha256": contract.FINAL_EXECUTION_BINDING_SHA256,
        "baseline_result_sha256": contract.BASELINE_RESULT_SHA256,
    }
    for key, expected in exact.items():
        require(binding.get(key) == expected, "REVIEW_BINDING_" + key.upper() + "_MISMATCH")
    require(request.get("schema") == contract.REQUEST_SCHEMA, "REQUEST_SCHEMA_MISMATCH")
    require(request.get("authorized") is False, "REQUEST_AUTHORIZED_PREMATURELY")
    require(request.get("host_preflight_result_sha256") is None, "REQUEST_PREFLIGHT_PREPOPULATED")
    require(request.get("review_binding_sha256") == supplied, "REQUEST_REVIEW_BINDING_MISMATCH")
    immutable_path = root / packager.IMMUTABLE_ZIP_NAME
    baseline_path = root / packager.BASELINE_ARCHIVE_NAME
    require(sha256_file(immutable_path) == contract.IMMUTABLE_ARTIFACT_SHA256, "PACKAGE_IMMUTABLE_DIGEST_MISMATCH")
    require(sha256_file(baseline_path) == contract.BASELINE_PUBLIC_ARCHIVE_SHA256, "PACKAGE_BASELINE_DIGEST_MISMATCH")
    packager.validate_immutable_zip(immutable_path)
    execution = validate_execution_package(root, binding)
    return binding, request, {
        "review_archive_sha256": archive_sha,
        **execution,
    }


def validate_authorization(
    path: Path,
    *,
    package_root: Path,
    binding: Mapping[str, Any],
    package_digests: Mapping[str, str],
    toolchain: Mapping[str, Any],
    custody_root: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    value = load_json(path, "0600", "AUTHORIZATION_RECORD_INVALID")
    require(value.get("schema") == AUTH_SCHEMA, "AUTHORIZATION_SCHEMA_MISMATCH")
    require(value.get("authorization_id") == contract.FUTURE_HOST_AUTHORIZATION_ID, "AUTHORIZATION_ID_MISMATCH")
    require(value.get("operation") == AUTH_OPERATION, "AUTHORIZATION_OPERATION_MISMATCH")
    require(value.get("authorized") is True, "AUTHORIZATION_NOT_GRANTED")
    require(value.get("one_shot") is True, "AUTHORIZATION_NOT_ONE_SHOT")
    require(value.get("replay_permitted") is False, "AUTHORIZATION_REPLAY_EXPANDED")
    require(value.get("automatic_retry_permitted") is False, "AUTHORIZATION_RETRY_EXPANDED")
    issued = utc(value.get("issued_at"), "AUTHORIZATION_ISSUED_AT_INVALID")
    expires = utc(value.get("expires_at"), "AUTHORIZATION_EXPIRES_AT_INVALID")
    current = now or datetime.now(timezone.utc)
    require(issued <= current <= expires, "AUTHORIZATION_NOT_CURRENT")
    require(0 < (expires - issued).total_seconds() <= 7200, "AUTHORIZATION_WINDOW_INVALID")
    exact = {
        "source_sha": binding["source_sha"],
        "base_pr": contract.BASE_PR,
        "base_head_sha": contract.BASE_HEAD_SHA,
        "baseline_original_main_sha": contract.BASELINE_ORIGINAL_MAIN_SHA,
        "accepted_current_main_sha": contract.ACCEPTED_CURRENT_MAIN_SHA,
        "review_binding_sha256": binding["review_binding_sha256"],
        "review_archive_sha256": package_digests["review_archive_sha256"],
        "execution_package_sha256": package_digests["execution_package_sha256"],
        "immutable_artifact_id": contract.IMMUTABLE_ARTIFACT_ID,
        "immutable_artifact_sha256": contract.IMMUTABLE_ARTIFACT_SHA256,
        "baseline_public_archive_sha256": contract.BASELINE_PUBLIC_ARCHIVE_SHA256,
        "final_execution_binding_sha256": contract.FINAL_EXECUTION_BINDING_SHA256,
        "python_executable_sha256": toolchain["python_executable_sha256"],
        "openssl_executable_sha256": toolchain["openssl_executable_sha256"],
        "esptool_executable_sha256": toolchain["esptool_executable_sha256"],
        "esptool_module_sha256": toolchain["esptool_module_sha256"],
        "pyserial_module_sha256": toolchain["pyserial_module_sha256"],
        "mosquitto_executable_sha256": toolchain["mosquitto_executable_sha256"],
        "custody_root_digest_sha256": sha256_bytes(str(custody_root).encode("utf-8")),
    }
    for key, expected in exact.items():
        require(value.get(key) == expected, "AUTHORIZATION_" + key.upper() + "_MISMATCH")
    for key in (
        "board_operation_authorized",
        "usb_enumeration_authorized",
        "serial_operation_authorized",
        "esptool_operation_authorized",
        "flash_operation_authorized",
        "physical_nvs_operation_authorized",
        "network_operation_authorized",
        "broker_operation_authorized",
        "prepare_authorized",
        "verify_authorized",
        "activate_authorized",
        "cleanup_authorized",
        "ready_authorized",
        "merge_authorized",
        "release_authorized",
        "tag_authorized",
        "deployment_authorized",
    ):
        require(value.get(key) is False, "AUTHORIZATION_BOUNDARY_" + key.upper())
    without = dict(value)
    observed = without.pop("authorization_record_sha256", None)
    require(observed == canonical_sha256(without), "AUTHORIZATION_RECORD_DIGEST_MISMATCH")
    return value


def material_digest(materials: Mapping[str, Mapping[str, str]]) -> str:
    normalized: dict[str, dict[str, str]] = {}
    require(set(materials) == set(REQUIRED_PRIVATE_FILES), "PRIVATE_INVENTORY_MISMATCH")
    for name in sorted(materials):
        metadata = materials[name]
        require(metadata.get("relative_path") == name, "PRIVATE_RELATIVE_PATH_MISMATCH")
        require(metadata.get("mode") == "0600", "PRIVATE_MODE_MISMATCH")
        digest = metadata.get("sha256")
        require(isinstance(digest, str) and HEX64.fullmatch(digest), "PRIVATE_DIGEST_INVALID")
        normalized[name] = {
            "relative_path": name,
            "mode": "0600",
            "sha256": digest,
        }
    return canonical_sha256(
        {
            "schema": private_contract.MATERIAL_SCHEMA,
            "run_suffix": contract.RUN_SUFFIX,
            "materials": normalized,
        }
    )


def validate_private_custody(root: Path, openssl: Path) -> dict[str, str]:
    root = root.expanduser().resolve(strict=True)
    require(root.is_dir() and not root.is_symlink(), "CUSTODY_ROOT_INVALID")
    require(file_mode(root) == "0700", "CUSTODY_ROOT_MODE_INVALID")
    private_path = root / PRIVATE_DESCRIPTOR
    public_path = root / PUBLIC_DESCRIPTOR
    private = load_json(private_path, "0600", "PRIVATE_DESCRIPTOR_INVALID")
    public = load_json(public_path, "0600", "PUBLIC_DESCRIPTOR_INVALID")
    require(sha256_file(private_path) == contract.PRIVATE_DESCRIPTOR_SHA256, "PRIVATE_DESCRIPTOR_DIGEST_MISMATCH")
    require(sha256_file(public_path) == contract.PUBLIC_DESCRIPTOR_SHA256, "PUBLIC_DESCRIPTOR_DIGEST_MISMATCH")
    require(private.get("private_package_sha256") == contract.PRIVATE_PACKAGE_SHA256, "PRIVATE_PACKAGE_MISMATCH")
    require(private.get("public_descriptor_sha256") == contract.PUBLIC_DESCRIPTOR_SHA256, "PRIVATE_PUBLIC_DESCRIPTOR_MISMATCH")
    require(private.get("run_suffix") == contract.RUN_SUFFIX, "PRIVATE_RUN_SUFFIX_MISMATCH")
    require(private.get("state") == "REPAIRED_SUCCESSOR_PRIVATE_MATERIAL_FROZEN", "PRIVATE_STATE_MISMATCH")
    require(
        private.get("current_main_sha") == contract.BASELINE_ORIGINAL_MAIN_SHA,
        "PRIVATE_ORIGINAL_MAIN_MISMATCH",
    )
    require(
        private.get("source_sha") == "2ed70e3292e5b6522ac3a5bc279c94535cd7b784",
        "PRIVATE_MATERIAL_SOURCE_MISMATCH",
    )
    materials = private.get("materials")
    require(isinstance(materials, dict), "PRIVATE_MATERIALS_INVALID")
    for name in REQUIRED_PRIVATE_FILES:
        path = root / name
        regular(path, "0600", "PRIVATE_MATERIAL_FILE_INVALID")
        metadata = materials.get(name)
        require(isinstance(metadata, dict), "PRIVATE_MATERIAL_METADATA_MISSING")
        require(metadata.get("sha256") == sha256_file(path), "PRIVATE_MATERIAL_FILE_DIGEST_MISMATCH")
    require(material_digest(materials) == contract.PRIVATE_PACKAGE_SHA256, "PRIVATE_PACKAGE_RECOMPUTE_MISMATCH")

    public_exact = {
        "current_main_sha": contract.BASELINE_ORIGINAL_MAIN_SHA,
        "source_sha": "2ed70e3292e5b6522ac3a5bc279c94535cd7b784",
        "private_package_sha256": contract.PRIVATE_PACKAGE_SHA256,
        "candidate_digest_sha256": contract.CANDIDATE_DIGEST_SHA256,
        "unlock_digest_sha256": contract.UNLOCK_DIGEST_SHA256,
        "ca_pem_sha256": contract.CA_PEM_SHA256,
        "broker_certificate_der_sha256": contract.BROKER_CERTIFICATE_DER_SHA256,
        "broker_spki_sha256": contract.BROKER_SPKI_SHA256,
        "prepare_command_sha256": contract.PREPARE_COMMAND_SHA256,
        "verify_command_sha256": contract.VERIFY_COMMAND_SHA256,
        "run_suffix": contract.RUN_SUFFIX,
    }
    for key, expected in public_exact.items():
        require(public.get(key) == expected, "PUBLIC_" + key.upper() + "_MISMATCH")
    require(public.get("private_values_included") is False, "PUBLIC_PRIVATE_VALUES_INCLUDED")
    require(public.get("private_paths_included") is False, "PUBLIC_PRIVATE_PATHS_INCLUDED")

    mqtt_password = (root / "mqtt-password.hex").read_text(encoding="ascii").strip()
    persistence_key = (root / "persistence-key.hex").read_text(encoding="ascii").strip()
    unlock_token = (root / "unlock-token.hex").read_text(encoding="ascii").strip()
    ca_pem = (root / "root-ca.cert.pem").read_text(encoding="ascii")
    password_line = (root / "mosquitto.password").read_text(encoding="ascii").strip()
    require(
        private_contract.verify_mosquitto_sha512_pbkdf2(mqtt_password, password_line),
        "PASSWORD_DATABASE_CROSS_BINDING_FAILED",
    )
    prepare, verify, candidate, unlock_digest = private_contract.render_commands(
        unlock_token, persistence_key, mqtt_password, ca_pem
    )
    require(candidate == contract.CANDIDATE_DIGEST_SHA256, "CANDIDATE_RECOMPUTE_MISMATCH")
    require(unlock_digest == contract.UNLOCK_DIGEST_SHA256, "UNLOCK_DIGEST_RECOMPUTE_MISMATCH")
    require((root / "prepare-command.txt").read_text(encoding="utf-8") == prepare, "PREPARE_COMMAND_RECOMPUTE_MISMATCH")
    require((root / "verify-command.txt").read_text(encoding="utf-8") == verify, "VERIFY_COMMAND_RECOMPUTE_MISMATCH")
    require(sha256_file(root / "prepare-command.txt") == contract.PREPARE_COMMAND_SHA256, "PREPARE_COMMAND_DIGEST_MISMATCH")
    require(sha256_file(root / "verify-command.txt") == contract.VERIFY_COMMAND_SHA256, "VERIFY_COMMAND_DIGEST_MISMATCH")

    run_checked([
        str(openssl), "verify", "-CAfile", str(root / "root-ca.cert.pem"),
        "-verify_hostname", "stage2d9r.local", str(root / "broker.cert.pem"),
    ])
    cert_der = run_checked([
        str(openssl), "x509", "-in", str(root / "broker.cert.pem"), "-outform", "DER",
    ])
    cert_pub_pem = run_checked([
        str(openssl), "x509", "-in", str(root / "broker.cert.pem"), "-pubkey", "-noout",
    ])
    cert_spki = run_checked([
        str(openssl), "pkey", "-pubin", "-outform", "DER",
    ], input_bytes=cert_pub_pem)
    require(sha256_bytes(cert_der) == contract.BROKER_CERTIFICATE_DER_SHA256, "BROKER_CERT_DER_MISMATCH")
    require(sha256_bytes(cert_spki) == contract.BROKER_SPKI_SHA256, "BROKER_SPKI_MISMATCH")

    mqtt_password = "0" * len(mqtt_password)
    persistence_key = "0" * len(persistence_key)
    unlock_token = "0" * len(unlock_token)
    return {
        "private_descriptor_sha256": contract.PRIVATE_DESCRIPTOR_SHA256,
        "public_descriptor_sha256": contract.PUBLIC_DESCRIPTOR_SHA256,
        "private_package_sha256": contract.PRIVATE_PACKAGE_SHA256,
        "prepare_command_sha256": contract.PREPARE_COMMAND_SHA256,
        "verify_command_sha256": contract.VERIFY_COMMAND_SHA256,
        "candidate_digest_sha256": contract.CANDIDATE_DIGEST_SHA256,
        "ca_pem_sha256": contract.CA_PEM_SHA256,
        "broker_certificate_der_sha256": contract.BROKER_CERTIFICATE_DER_SHA256,
        "broker_spki_sha256": contract.BROKER_SPKI_SHA256,
    }
