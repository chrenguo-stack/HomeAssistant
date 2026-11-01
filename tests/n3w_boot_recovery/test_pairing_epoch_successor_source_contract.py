from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPER = (
    ROOT
    / "firmware/esphome_rc/board_lab/n3w_boot_session_recovery/"
    "pairing_epoch_successor_helper.yml"
)


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_epoch_successor_helper_is_inert_and_default_noop() -> None:
    config = text(HELPER)
    lowered = config.lower()

    assert 'recovery_floor_hex: "0000000000000000"' in config
    assert 'current_pairing_epoch: "0"' in config
    assert 'successor_pairing_epoch: "0"' in config
    assert "phase4_source_harness: false" in config
    assert "phase4_product_runtime: false" in config
    assert "priority: -200.0" in config
    assert "kCurrentPairingEpoch < 2U" in config
    assert "kSuccessorPairingEpoch <= kCurrentPairingEpoch" in config
    assert "kSuccessorPairingEpoch - kCurrentPairingEpoch != 1U" in config
    assert "no write executed" in config

    for forbidden in (
        "\nwifi:",
        "\nmqtt:",
        "\napi:",
        "\nota:",
        "\ncaptive_portal:",
        "\nweb_server:",
    ):
        assert forbidden not in lowered


def test_epoch_successor_requires_exact_current_or_already_advanced_state() -> None:
    config = text(HELPER)

    assert "NvsPairingEpochStore pairing_epoch_store;" in config
    assert "pairing_epoch_store.load(&observed_pairing_epoch)" in config
    assert "observed_status != SimpleNvsStatus::OK" in config
    assert "observed_pairing_epoch != kCurrentPairingEpoch" in config
    assert "observed_pairing_epoch != kSuccessorPairingEpoch" in config

    oracle = "provision_boot_session_repair_recovery(\n                      kRecoveryFloor,\n                      observed_pairing_epoch)"
    assert oracle in config


def test_epoch_successor_is_monotonic_restart_safe_and_verified() -> None:
    config = text(HELPER)

    assert "if (observed_pairing_epoch == kCurrentPairingEpoch)" in config
    assert "pairing_epoch_store.save(kSuccessorPairingEpoch)" in config
    assert "pairing_epoch_store.save(kCurrentPairingEpoch)" not in config
    assert "verified_pairing_epoch != kSuccessorPairingEpoch" in config
    assert "BSR_PAIRING_EPOCH_SUCCESSOR_WRITE=PASS" in config

    # The successor helper must not create/erase Setup Secret or directly touch
    # Manager/Broker/replay state.  Those remain outside this source-only gate.
    assert "NvsSetupSecretStore" not in config
    assert "setup_secret" not in config.lower()
    assert "ReplayRegistry" not in config
    assert "broker_store_" not in config
    assert "peer_store_" not in config


def test_epoch_successor_reuses_existing_recovery_oracle_before_write() -> None:
    config = text(HELPER)

    oracle_index = config.index("provision_boot_session_repair_recovery")
    write_index = config.index("pairing_epoch_store.save(kSuccessorPairingEpoch)")
    verify_index = config.index("verified_pairing_epoch != kSuccessorPairingEpoch")

    assert oracle_index < write_index < verify_index
