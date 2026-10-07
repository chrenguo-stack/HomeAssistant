from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_product_core"
RC2 = ROOT / "firmware/esphome_rc/f1_0_rc2"
DISPLAY = RC2 / "packages/display.yml"
BASE_CORE = RC2 / "packages/core.yml"
TRANSPORT = RC2 / "packages/n3w_product_transport.yml"
PAIRING_CLI = (
    ROOT
    / "host/greenhouse-manager/src/greenhouse_manager/ops/n3w_pairing_cli.py"
)
PREFLIGHT = (
    ROOT
    / "tools/execution_packages/n3w/auto_safe_fallback/"
    "clean_board_eligibility_readonly_preflight/executor.py"
)
MANAGER_HISTORY = (
    ROOT
    / "tools/execution_packages/n3w/auto_safe_fallback/"
    "clean_board_eligibility_readonly_preflight/manager_history_readonly.py"
)


def test_pairing_qr_is_gated_by_successful_hello() -> None:
    header = (CORE / "n3w_simple_pairing_client.h").read_text(encoding="utf-8")
    source = (CORE / "n3w_simple_pairing_client.cpp").read_text(encoding="utf-8")
    component = (CORE / "n3w_simple_product_component.h").read_text(encoding="utf-8")

    assert "bool handoff_ready() const" in header
    assert "bool handoff_ready_{false};" in header
    assert "handoff_ready_ = true;" in source
    assert "handoff_ready_ = false;" in source
    assert "bool pairing_handoff_ready() const" in component

    hello = source[
        source.index("SimplePairingClient::send_hello_"):
        source.index("SimplePairingClient::pair_with_")
    ]
    proceed = hello.index("handoff_ready_ = true;")
    parsed = hello.index("parse_hello_result")
    assert proceed > parsed
    assert "HelloNextAction::WAIT" in hello
    assert "HelloNextAction::RENEW" in hello


def test_lcd_page_five_has_three_product_states() -> None:
    display = DISPLAY.read_text(encoding="utf-8")
    base = BASE_CORE.read_text(encoding="utf-8")
    transport = TRANSPORT.read_text(encoding="utf-8")

    assert "id(display_page) = (id(display_page) + 1) % 5;" in (
        RC2 / "packages/control.yml"
    ).read_text(encoding="utf-8")
    assert "PAGE 4：配网 / 首次配对 / 已联网状态" in display
    assert "n3w_pairing_display_enabled" in base
    assert "n3w_pairing_display_ready" in base
    assert "n3w_product_provisioned" in base
    assert '"扫码添加节点"' in display
    assert '"正在查找主机"' in display
    assert '"网络离线"' in display
    assert "const int scale = 1;" in display

    assert "pairing_handoff_ready()" in transport
    assert "pairing_qr_payload()" in transport
    assert "id(setup_qr).set_value(payload);" in transport
    assert "ESP_LOG" not in transport
    assert "GHN3W2:" not in transport


def test_complete_pairing_payload_uses_existing_manager_socket() -> None:
    cli = PAIRING_CLI.read_text(encoding="utf-8")

    assert '"import-payload"' in cli
    assert '"--payload-stdin"' in cli
    assert "PAIRING_PAYLOAD_RE.fullmatch" in cli
    assert "import_setup_secret_over_socket(" in cli
    assert "setup_secret=setup_secret" in cli
    assert "print(PAYLOAD" not in cli
    assert "print(setup_secret" not in cli


def test_clean_board_preflight_does_not_claim_product_identity_from_rom_mac() -> None:
    preflight = PREFLIGHT.read_text(encoding="utf-8")
    history = MANAGER_HISTORY.read_text(encoding="utf-8")

    assert "silicon_binding_from_rom_mac" in preflight
    assert '"silicon_binding_sha256": silicon_binding_hash' in preflight
    assert '"product_hardware_id_sha256": None' in preflight
    assert "DEFERRED_UNTIL_RUNTIME_QR_MANAGER_BINDING" in preflight
    assert "PRODUCT_RUNTIME_IDENTITY_BINDING_AFTER_FIRST_BOOT" in preflight
    assert '"hardware_id_sha256": identity_hash' not in preflight

    assert "--product-hardware-id-sha256" in history
    assert "RUNTIME_QR_EQUALS_MANAGER_PENDING" in history
    assert "--hardware-id-sha256" not in history
