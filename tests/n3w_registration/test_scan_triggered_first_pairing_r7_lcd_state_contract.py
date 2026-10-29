from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
DISPLAY = ROOT / "firmware/esphome_rc/f1_0_rc2/packages/display.yml"
TRANSPORT = ROOT / "firmware/esphome_rc/f1_0_rc2/packages/n3w_product_transport.yml"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def function_block(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


def test_r7_display_model_and_timers_are_display_only() -> None:
    header = text(CORE / "n3w_registration_display.h")
    source = text(CORE / "n3w_registration_display.cpp")

    for token in (
        "IDLE_UNREGISTERED",
        "DISCOVERING",
        "WAIT_CONFIRM",
        "REGISTERING",
        "SUCCESS",
        "ERROR",
        "E01_NO_HOST = 1",
        "E02_HOST_UNAVAILABLE = 2",
        "E03_HOST_BUSY = 3",
        "E04_NETWORK_INTERRUPTED = 4",
        "E05_REGISTRATION_TIMEOUT = 5",
        "E06_REGISTRATION_FAILED = 6",
        "E07_QR_INVALID = 7",
        "kRegistrationSuccessDisplayMs = 3000ULL",
        "kRegistrationErrorDisplayMs = 5000ULL",
    ):
        assert token in header

    scope = header + source
    for forbidden in (
        "nvs_",
        "renew_pairing",
        "erase()",
        "registration_bootstrap",
        "47110",
        "47112",
        "setup_secret",
    ):
        assert forbidden not in scope.lower()

    assert "latch_kind_ == LatchKind::SUCCESS && latch_active_(now_ms)" in source
    assert "latch_kind_ == LatchKind::ERROR && error_ == error" in source


def test_r7_component_is_the_only_display_authority_and_success_is_commit_bound() -> None:
    header = text(CORE / "n3w_simple_product_component.h")
    source = text(CORE / "n3w_simple_product_component.cpp")

    assert "RegistrationDisplayState registration_display_state() const;" in header
    assert "RegistrationDisplayError registration_display_error() const;" in header
    assert "RegistrationDisplayController registration_display_controller_" in header

    base = function_block(
        source,
        "RegistrationDisplayState\nSimpleProductComponent::registration_display_base_state_() const",
        "RegistrationDisplayState SimpleProductComponent::registration_display_state() const",
    )
    assert "pairing_ack_pending_" in base
    assert "registration_candidate_selected_" in base
    assert "registration_bootstrap_accepted_" in base
    assert "RegistrationPortalStage::SELECTED_PENDING_BOOTSTRAP" in base
    assert "RegistrationPortalStage::DISCOVERING" in base
    assert "RegistrationPortalStage::WAIT_CONFIRM" in base
    assert "pairing_handoff_ready" not in base

    bootstrap = function_block(
        source,
        "void SimpleProductComponent::advance_registration_bootstrap_()",
        "void SimpleProductComponent::advance_pairing_()",
    )
    success = bootstrap.index("show_registration_success_();")
    provisioned = bootstrap.rfind("if (pairing_client_.provisioned())", 0, success)
    assert provisioned >= 0

    pairing = function_block(
        source,
        "void SimpleProductComponent::advance_pairing_()",
        "void SimpleProductComponent::advance_recovery_()",
    )
    success = pairing.index("show_registration_success_();")
    provisioned = pairing.rfind("if (pairing_client_.provisioned())", 0, success)
    assert provisioned >= 0

    display_helpers = function_block(
        source,
        "void SimpleProductComponent::show_registration_error_(",
        "void SimpleProductComponent::setup()",
    )
    for forbidden in ("renew_pairing", ".erase(", "ack_store", "peer_store", "broker_store"):
        assert forbidden not in display_helpers


def test_r7_exact_event_to_error_mapping_is_present() -> None:
    source = text(CORE / "n3w_simple_product_component.cpp")

    discovery = function_block(
        source,
        "void SimpleProductComponent::advance_registration_discovery_()",
        "void SimpleProductComponent::advance_registration_bootstrap_()",
    )
    assert "take_candidate_stale_event()" in discovery
    assert "E07_QR_INVALID" in discovery
    assert "take_candidate_list_expired_event()" in discovery
    assert "E01_NO_HOST" in discovery
    assert "if (!completed)" in discovery
    assert "E06_REGISTRATION_FAILED" in discovery
    assert "if (discovered.empty())" in discovery

    bootstrap = function_block(
        source,
        "void SimpleProductComponent::advance_registration_bootstrap_()",
        "void SimpleProductComponent::advance_pairing_()",
    )
    for token in (
        "CONNECT_FAILED",
        "TLS_FAILED",
        "PIN_MISMATCH",
        "E02_HOST_UNAVAILABLE",
        'confirmed.reason == "registration_busy"',
        "E03_HOST_BUSY",
        "E04_NETWORK_INTERRUPTED",
        "E05_REGISTRATION_TIMEOUT",
        "E06_REGISTRATION_FAILED",
        "E07_QR_INVALID",
    ):
        assert token in bootstrap

    loop = function_block(
        source,
        "void SimpleProductComponent::loop()",
        "TelemetrySubmitDisposition SimpleProductComponent::submit_telemetry_json",
    )
    assert "registration_wifi_loss_reported_" in loop
    assert "E04_NETWORK_INTERRUPTED" in loop


def test_r7_stale_qr_event_requires_a_valid_current_portal_action() -> None:
    portal = text(CORE / "n3w_registration_portal.cpp")
    confirm = function_block(
        portal,
        "esp_err_t RegistrationPortal::handle_confirm_",
        "esp_err_t RegistrationPortal::handle_retry_",
    )

    validation = confirm.index("read_action_request_(request, true, &candidate_id)")
    stale_event = confirm.index("candidate_stale_event_pending_.store")
    assert validation < stale_event

    forbidden_return = confirm.index('"403 Forbidden"')
    assert forbidden_return < stale_event

    assert "candidate_list_expired_event_pending_.store" in portal


def test_r7_lcd_uses_hardware_spi_and_preserves_five_page_cycle() -> None:
    display = text(DISPLAY)
    transport = text(TRANSPORT)

    assert "interface: hardware" in display
    assert "data_rate: 1MHz" in display
    assert "update_interval: 1s" in display
    assert "n3w_registration_qr_ready" in display
    assert "registration_display_state_code()" in transport
    assert "registration_display_error_code()" in transport

    assert "id(display_page) = 4;" not in transport
    assert "const int page = id(display_page);" in display
    assert "force_registration_page" not in display

    page4 = display.split("// ─── PAGE 4：", 1)[1].split(
        "// ─── 底部页码与时间 ───", 1
    )[0]
    assert "!id(wifi_component).is_connected()" in page4
    assert "id(n3w_registration_qr_ready)" in page4
    assert '"联机注册"' in page4
    assert '"扫码注册"' in page4
    assert '"已联机注册"' in page4

    for transient in (
        "正在搜索",
        "等待确认",
        "联机注册中",
        "注册成功",
        "E01",
        "E02",
        "E03",
        "E04",
        "E05",
        "E06",
        "E07",
        "registration_state",
        "registration_error",
    ):
        assert transient not in page4

def test_r7_required_copy_has_glyph_coverage_and_fits_64px_monospaced_width() -> None:
    display = text(DISPLAY)
    glyph_lines = re.findall(r'^\s*glyphs: "(.*)"$', display, flags=re.MULTILINE)
    assert len(glyph_lines) >= 2
    f10_glyphs, f12_glyphs = glyph_lines[:2]

    f10_lines = (
        "手机相机扫码",
        "配置节点网络",
        "联机注册",
        "扫码注册",
        "请稍候",
    )
    f12_lines = (
        "联机注册",
        "已联机注册",
    )

    for line in f10_lines:
        assert set(line) <= set(f10_glyphs)
        assert len(line) * 10 <= 64

    for line in f12_lines:
        assert set(line) <= set(f12_glyphs)
        assert len(line) * 12 <= 64

def test_r7_display_copy_is_secret_free() -> None:
    display = text(DISPLAY)
    page4 = display.split("// ─── PAGE 4：", 1)[1].split("// ─── 底部页码与时间 ───", 1)[0]
    for forbidden in (
        "setup_secret",
        "pairing_id",
        "hardware_id",
        "manager_id",
        "system_id",
        "bootstrap_tls_sha256",
        "mqtt_password",
    ):
        assert forbidden not in page4.lower()
, display, flags=re.MULTILINE)
    assert len(glyph_lines) >= 2
    f10_glyphs, f12_glyphs = glyph_lines[:2]

    f10_lines = (
        "手机相机扫码",
        "配置节点网络",
        "联机注册",
        "扫码注册",
        "请稍候",
    )
    f12_lines = (
        "联机注册",
        "已联机注册",
    )

    for line in f10_lines:
        assert set(line) <= set(f10_glyphs)
        assert len(line) * 10 <= 64

    for line in f12_lines:
        assert set(line) <= set(f12_glyphs)
        assert len(line) * 12 <= 64

def test_r7_display_copy_is_secret_free() -> None:
    display = text(DISPLAY)
    page4 = display.split("// ─── PAGE 4：", 1)[1].split("// ─── 底部页码与时间 ───", 1)[0]
    for forbidden in (
        "setup_secret",
        "pairing_id",
        "hardware_id",
        "manager_id",
        "system_id",
        "bootstrap_tls_sha256",
        "mqtt_password",
    ):
        assert forbidden not in page4.lower()
, display, flags=re.MULTILINE)
    assert len(glyph_lines) >= 2
    f10_glyphs, f12_glyphs = glyph_lines[:2]

    f10_lines = (
        "手机相机扫码",
        "配置节点网络",
        "联机注册",
        "扫码注册",
        "请稍候",
    )
    f12_lines = (
        "联机注册",
        "已联机注册",
    )

    for line in f10_lines:
        assert set(line) <= set(f10_glyphs)
        assert len(line) * 10 <= 64

    for line in f12_lines:
        assert set(line) <= set(f12_glyphs)
        assert len(line) * 12 <= 64

def test_r7_display_copy_is_secret_free() -> None:
    display = text(DISPLAY)
    page4 = display.split("// ─── PAGE 4：", 1)[1].split("// ─── 底部页码与时间 ───", 1)[0]
    for forbidden in (
        "setup_secret",
        "pairing_id",
        "hardware_id",
        "manager_id",
        "system_id",
        "bootstrap_tls_sha256",
        "mqtt_password",
    ):
        assert forbidden not in page4.lower()
, display, flags=re.MULTILINE)
    assert len(glyph_lines) >= 2
    f10_glyphs, f12_glyphs = glyph_lines[:2]

    f10_lines = (
        "手机相机扫码",
        "配置节点网络",
        "联机注册",
        "扫码注册",
        "请稍候",
    )
    f12_lines = (
        "联机注册",
        "已联机注册",
    )

    for line in f10_lines:
        assert set(line) <= set(f10_glyphs)
        assert len(line) * 10 <= 64

    for line in f12_lines:
        assert set(line) <= set(f12_glyphs)
        assert len(line) * 12 <= 64

def test_r7_display_copy_is_secret_free() -> None:
    display = text(DISPLAY)
    page4 = display.split("// ─── PAGE 4：", 1)[1].split("// ─── 底部页码与时间 ───", 1)[0]
    for forbidden in (
        "setup_secret",
        "pairing_id",
        "hardware_id",
        "manager_id",
        "system_id",
        "bootstrap_tls_sha256",
        "mqtt_password",
    ):
        assert forbidden not in page4.lower()
