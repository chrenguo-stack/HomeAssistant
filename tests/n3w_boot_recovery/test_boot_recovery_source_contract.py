from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
HELPER = (
    ROOT
    / "firmware/esphome_rc/board_lab/n3w_boot_session_recovery/recovery_floor_helper.yml"
)
PROTOCOL = ROOT / "protocols/transport/gh-n3w-single-hop-v1.md"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_recovery_helper_is_inert_network_free_and_default_noop() -> None:
    config = text(HELPER)
    lowered = config.lower()

    assert 'recovery_floor_hex: "0000000000000000"' in config
    assert 'repair_pairing_epoch: "0"' in config
    assert "phase4_source_harness: false" in config
    assert "phase4_product_runtime: false" in config
    assert "priority: -200.0" in config
    assert "kRecoveryFloor == 0ULL || kRepairPairingEpoch < 2U" in config
    assert "no write executed" in config
    assert "provision_boot_session_repair_recovery" in config
    assert "provision_boot_session_recovery_floor" not in config
    assert "BSR_REPAIR_RECOVERY_WRITE=%s" in config

    for forbidden in (
        "\nwifi:",
        "\nmqtt:",
        "\napi:",
        "\nota:",
        "\ncaptive_portal:",
        "\nweb_server:",
    ):
        assert forbidden not in lowered


def test_recovery_surface_couples_floor_to_higher_pairing_epoch() -> None:
    core = text(CORE / "greenhouse_n3w_core.h")

    start = core.index("bool provision_boot_session_repair_recovery(")
    end = core.index("bool take_telemetry_identity", start)
    body = core[start:end]

    assert "floor == 0 || pairing_epoch < 2" in body
    assert "phase4_product_runtime_enabled_" in body
    assert "phase4_source_harness_enabled_" in body
    assert "runtime_ready()" in body
    assert "boot_session_manager_.ready()" in body
    assert "ack_status != SimpleNvsStatus::MISSING" in body
    assert "floor_status == StoreStatus::MISSING" in body
    assert "existing_floor == floor" in body
    assert "pairing_epoch_status == SimpleNvsStatus::MISSING" in body
    assert "existing_pairing_epoch == pairing_epoch" in body
    assert "pairing_epoch - broker.credential_generation != 1" in body
    assert "recovery_pairing_epoch_store_.save(pairing_epoch)" in body
    assert "boot_session_manager_.provision_recovery_floor" in body
    assert body.index("recovery_pairing_epoch_store_.save(pairing_epoch)") < body.index(
        "boot_session_manager_.provision_recovery_floor"
    )
    assert "broker_store_.erase()" in body
    assert "peer_store_.erase()" in body
    assert "setup_secret_store_.erase()" not in body
    assert "return true;" in body

    # The old floor-only public recovery entrypoint must not remain callable.
    assert "bool provision_boot_session_recovery_floor(" not in core


def test_pairing_epoch_store_is_durable_and_monotonic() -> None:
    header = text(CORE / "n3w_esp32_simple_nvs.h")
    source = text(CORE / "n3w_esp32_simple_nvs.cpp")

    assert "class NvsPairingEpochStore" in header
    assert 'key_name = "pair_epoch"' in header
    assert "SimpleNvsStatus load(uint32_t *epoch)" in header
    assert "SimpleNvsStatus save(uint32_t epoch)" in header
    assert "kPairingEpochMagic" in source
    assert "if (epoch < existing) return SimpleNvsStatus::INVALID_ARGUMENT" in source
    assert "if (epoch == existing) return SimpleNvsStatus::OK" in source
    assert "record.epoch == 0" in source


def test_product_pairing_client_uses_durable_random_transaction_id() -> None:
    header = text(CORE / "n3w_simple_pairing_client.h")
    source = text(CORE / "n3w_simple_pairing_client.cpp")

    assert "NvsPendingPairingIntentStore pairing_intent_store_{}" in header
    assert "NvsPairingEpochStore" not in header
    assert "pairing_id_from_secret" not in source
    assert "std::array<uint8_t, 16> pairing_random{}" in source
    assert "PendingPairingIntent replacement" in source
    saved = source.index("pairing_intent_store_.save(replacement)")
    activated = source.index("pairing_id_ = std::move(next_pairing_id)")
    assert saved < activated
    assert 'root["pairing_epoch"]' not in source
    assert "pairing_intent_store_.erase()" in source


def test_formal_protocol_requires_new_key_epoch_and_floor_above_high_water() -> None:
    protocol = text(PROTOCOL)

    assert "重新配发新 key epoch" in protocol
    assert "Manager 提供大于既有高水位的 session floor" in protocol


def test_boot_session_store_stays_on_existing_namespace_and_key() -> None:
    store = text(CORE / "n3w_esp32_nvs.h")

    assert 'namespace_name = "gh_n3w"' in store
    assert 'key_name = "boot_state"' in store
    assert "class NvsBootSessionStore final : public BootSessionStore" in store
