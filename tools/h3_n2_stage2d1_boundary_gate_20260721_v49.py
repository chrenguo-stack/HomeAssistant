#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

DIAGNOSTIC = Path("/tmp/stage2d1-boundary-diagnostic-v49.txt")


def fail(message: str) -> None:
    text = f"STAGE2D1_BOUNDARY_FAILURE={message}\n"
    DIAGNOSTIC.write_text(text, encoding="utf-8")
    raise SystemExit(text.rstrip())


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def main() -> int:
    component = Path("firmware/esphome_rc/components/greenhouse_pairing_client")
    lab = Path("firmware/esphome_rc/components/greenhouse_pairing_persistence_lab")
    sources = [
        component / "pairing_persistence_backend.h",
        component / "pairing_persistence_backend.cpp",
        component / "pairing_persistence_crypto.h",
        component / "pairing_persistence_crypto.cpp",
        component / "pairing_credential_codec.h",
        component / "pairing_credential_codec.cpp",
        component / "pairing_persistent_store.h",
        component / "pairing_persistent_store.cpp",
        component
        / "tests/pairing_stage2d1_persistent_store_fault_matrix_20260721_v49.cpp",
        *[path for path in lab.rglob("*") if path.is_file()],
    ]
    missing_files = [str(path) for path in sources if not path.is_file()]
    require(not missing_files, f"missing_files:{missing_files}")

    encoded = "\n".join(
        path.read_text(encoding="utf-8", errors="replace") for path in sources
    )
    forbidden = (
        "nvs_flash_erase",
        "nvs_erase_all",
        "nvs_erase_partition",
        "esp_efuse_write",
        "esp_efuse_batch_write",
        "set_username(",
        "set_password(",
        "greenhouse_mqtt_auth",
        "/opt/greenhouse-h3-n2-acceptance",
    )
    present = [value for value in forbidden if value in encoded]
    require(not present, f"forbidden_source_values:{present}")

    required = (
        "nvs_set_blob",
        "nvs_commit",
        "esp_hmac_calculate",
        "mbedtls_chachapoly",
        "mbedtls_md_hmac",
        "gh-persist-encryption-v1",
        "gh-persist-digest-v1",
        "slot_a",
        "slot_b",
        "ACTIVE_WITH_COMMITTED_ORPHAN",
        "ACTIVE_WITH_INVALID_INACTIVE",
        "NO_ACTIVE_COMMITTED_ORPHAN",
        "MARKER_PLAINTEXT_BYTES",
        "this->crypto_->seal(",
        "this->crypto_->open(",
        "poisoned_",
        "Automatic NVS access at boot: NO",
        "NVS writes at boot: NO",
        "Production MQTT mutation: NO",
        "NVS_READONLY",
        "PersistenceOpenMode::READ_ONLY",
        "namespace_missing",
        "ESP_ERR_NVS_NOT_FOUND",
        "Missing read-only namespace: EMPTY",
        "stage2d1 persistent store fault matrix passed",
    )
    missing = [value for value in required if value not in encoded]
    require(not missing, f"missing_source_evidence:{missing}")

    store = (component / "pairing_persistent_store.cpp").read_text(
        encoding="utf-8"
    )
    committed = store.find("CredentialRecordState::COMMITTED, candidate")
    marker = store.find("write_marker_(recovery.candidate_slot")
    require(
        committed >= 0 and marker >= 0 and committed < marker,
        f"marker_order:committed={committed}:marker={marker}",
    )
    require("crc32_" not in store, "active_marker_still_uses_crc32")
    require(
        "const auto set_conflict" in store
        and "active_credentials->clear();" in store
        and "candidate_credentials->clear();" in store,
        "conflict_output_clear_missing",
    )

    codec = (component / "pairing_credential_codec.cpp").read_text(
        encoding="utf-8"
    )
    encode_clear = codec.find("wipe_vector(output);")
    encode_validate = codec.find("if (!bundle.valid())")
    require(
        encode_clear >= 0 and encode_validate >= 0 and encode_clear < encode_validate,
        "encode_output_not_cleared_before_validation",
    )
    decode_start = codec.find("bool PairingCredentialCodec::decode")
    decode_clear = codec.find("output->clear();", decode_start)
    decode_validate = codec.find("if (input.size() < 32", decode_start)
    require(
        decode_start >= 0
        and decode_clear >= 0
        and decode_validate >= 0
        and decode_clear < decode_validate,
        "decode_output_not_cleared_before_validation",
    )

    lab_python = (lab / "__init__.py").read_text(encoding="utf-8")
    require(
        'include_builtin_idf_component("mdns")' not in lab_python,
        "managed_mdns_treated_as_builtin",
    )
    lab_cpp = (lab / "greenhouse_pairing_persistence_lab.cpp").read_text(
        encoding="utf-8"
    )
    try:
        setup = lab_cpp.split(
            "void GreenhousePairingPersistenceLab::setup()", 1
        )[1].split("void GreenhousePairingPersistenceLab::dump_config()", 1)[0]
        recovery_probe = lab_cpp.split(
            "bool GreenhousePairingPersistenceLab::recover_for_lab()", 1
        )[1].split(
            "const char *GreenhousePairingPersistenceLab::recovery_status_name()",
            1,
        )[0]
    except IndexError as error:
        fail(f"lab_function_boundary_missing:{error}")
    require("->open" not in setup, "lab_opens_nvs_during_setup")
    require("recover_for_lab()" not in setup, "lab_recovers_during_setup")
    require(
        "PersistenceOpenMode::READ_ONLY" in recovery_probe
        and "PersistenceOpenMode::READ_WRITE" not in recovery_probe,
        "manual_recovery_probe_not_read_only",
    )

    minimal = Path(
        "firmware/esphome_rc/board_lab/h3_node_pairing_persistence/"
        "greenhouse_pairing_persistence_board_lab_20260721_v49.yml"
    )
    product = Path(
        "firmware/esphome_rc/f1_0_rc2/"
        "f1_0_rc2_h3_node_pairing_persistence_board_lab_20260721_v49.yml"
    )
    core = Path("firmware/esphome_rc/f1_0_rc2/packages/core.yml")
    production = Path("firmware/esphome_rc/f1_0_rc2/f1_0_rc2.yaml")
    for target in (minimal, product):
        require(target.is_file(), f"missing_compile_target:{target}")
        text = target.read_text(encoding="utf-8")
        has_on_boot_action = any(
            line.lstrip().startswith("on_boot:") for line in text.splitlines()
        )
        require(not has_on_boot_action, f"automatic_boot_action:{target}")
        require("recover_for_lab();" in text, f"manual_probe_missing:{target}")
        for dependency in ("nvs_flash", "esp_hw_support"):
            require(
                "include_builtin_idf_components:" in text
                and f"- {dependency}" in text,
                f"idf_dependency_missing:{dependency}:{target}",
            )

    minimal_text = minimal.read_text(encoding="utf-8")
    require("wifi:" in minimal_text, "minimal_wifi_missing")
    require(
        "enable_on_boot: false" in minimal_text,
        "minimal_wifi_not_disabled_at_boot",
    )
    require("mdns:" in minimal_text, "minimal_managed_mdns_missing")

    core_text = core.read_text(encoding="utf-8")
    require("wifi:" in core_text, "rc2_core_wifi_missing")
    require("mdns:" in core_text, "rc2_core_managed_mdns_missing")
    require(
        "greenhouse_pairing_persistence_lab" not in production.read_text(
            encoding="utf-8"
        ),
        "production_rc2_persistence_integration_detected",
    )

    DIAGNOSTIC.write_text(
        "STAGE2D1_BOUNDARY_STATUS=success\n",
        encoding="utf-8",
    )
    print("stage2d1 source and production boundaries passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
