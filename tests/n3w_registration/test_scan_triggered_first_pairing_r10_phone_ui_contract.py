from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = (
    ROOT
    / "firmware"
    / "esphome_rc"
    / "components"
    / "greenhouse_n3w_core"
)
PORTAL_CPP = CORE / "n3w_registration_portal.cpp"
PORTAL_H = CORE / "n3w_registration_portal.h"
COMPONENT_CPP = CORE / "n3w_simple_product_component.cpp"
COMPONENT_H = CORE / "n3w_simple_product_component.h"
DISPLAY = ROOT / "firmware/esphome_rc/f1_0_rc2/packages/display.yml"
TARGET = ROOT / "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def function_block(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


def portal_html() -> str:
    source = text(PORTAL_CPP)
    match = re.search(
        r'const char kPortalPage\[\] = R"HTML\((.*?)\)HTML";',
        source,
        flags=re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def test_r10_qr_page_load_is_passive_until_find_host_click() -> None:
    html = portal_html()

    assert 'addButton("寻找主机"' in html
    assert 'post("/api/v1/register/start")' in html
    assert "poll();" in html

    tail = html.rsplit("poll();", 1)[1]
    assert "/api/v1/register/start" not in tail
    assert 'post("/api/v1/register/start").then' not in html

    find_button = html.index('addButton("寻找主机"')
    start_post = html.index('post("/api/v1/register/start")', find_button)
    assert find_button < start_post


def test_r10_candidate_selection_is_not_registration_start() -> None:
    portal = text(PORTAL_CPP)

    confirm = function_block(
        portal,
        "esp_err_t RegistrationPortal::handle_confirm_",
        "esp_err_t RegistrationPortal::handle_begin_",
    )
    begin = function_block(
        portal,
        "esp_err_t RegistrationPortal::handle_begin_",
        "esp_err_t RegistrationPortal::handle_retry_",
    )
    take_selected = function_block(
        portal,
        "bool RegistrationPortal::take_selected_candidate_id(",
        "bool RegistrationPortal::rotate_token_()",
    )

    assert "RegistrationPortalStage::CANDIDATE_SELECTED" in confirm
    assert "RegistrationPortalStage::SELECTED_PENDING_BOOTSTRAP" not in confirm
    assert '"next\\":\\"user_confirm\\"' in confirm

    assert "RegistrationPortalStage::CANDIDATE_SELECTED" in begin
    assert "RegistrationPortalStage::SELECTED_PENDING_BOOTSTRAP" in begin
    assert '"next\\":\\"bootstrap\\"' in begin

    assert "RegistrationPortalStage::SELECTED_PENDING_BOOTSTRAP" in take_selected


def test_r10_duplicate_phone_actions_do_not_overwrite_active_state() -> None:
    portal = text(PORTAL_CPP)
    html = portal_html()

    confirm = function_block(
        portal,
        "esp_err_t RegistrationPortal::handle_confirm_",
        "esp_err_t RegistrationPortal::handle_begin_",
    )
    begin = function_block(
        portal,
        "esp_err_t RegistrationPortal::handle_begin_",
        "esp_err_t RegistrationPortal::handle_retry_",
    )

    assert "selected_candidate_id_ == candidate_id" in confirm
    assert '"reason\\":\\"selection_not_ready\\"' in confirm
    assert "candidate_stale_event_pending_.store" in confirm

    assert "bool already_started = false;" in begin
    assert "RegistrationPortalStage::SELECTED_PENDING_BOOTSTRAP" in begin
    assert "already_started = true;" in begin
    assert '"reason\\":\\"registration_in_progress\\"' in begin

    assert 'result.body.reason === "registration_in_progress"' in html
    assert 'result.body.reason === "selection_not_ready"' in html
    assert '"正在读取当前注册状态"' in html
    assert "pollSoon" in html


def test_r10_local_rate_limit_is_not_rendered_as_terminal_failure() -> None:
    html = portal_html()

    assert "result.response.status === 429" in html
    assert '"请稍候"' in html
    assert "pollSoon(150)" in html


def test_r10_phone_page_has_no_user_cancel_path() -> None:
    html = portal_html()
    portal = text(PORTAL_CPP) + "\n" + text(PORTAL_H)

    assert "取消注册" not in html
    assert "/api/v1/register/cancel" not in portal
    assert "handle_cancel_" not in portal
    assert '"开始注册（" + remaining + "s）"' in html
    assert "body.expires_in_s" in html
    assert "注册过程不能主动终止" in html


def test_r10_begin_button_countdown_tracks_full_post_selection_window() -> None:
    portal = text(PORTAL_CPP)
    header = text(PORTAL_H)
    component = text(COMPONENT_CPP)
    html = portal_html()
    status = function_block(
        portal,
        "esp_err_t RegistrationPortal::handle_status_",
        "esp_err_t RegistrationPortal::handle_confirm_",
    )
    confirm = function_block(
        portal,
        "esp_err_t RegistrationPortal::handle_confirm_",
        "esp_err_t RegistrationPortal::handle_begin_",
    )
    begin = function_block(
        portal,
        "esp_err_t RegistrationPortal::handle_begin_",
        "esp_err_t RegistrationPortal::handle_retry_",
    )
    discovery = function_block(
        component,
        "void SimpleProductComponent::advance_registration_discovery_()",
        "void SimpleProductComponent::advance_registration_bootstrap_()",
    )
    bootstrap = function_block(
        component,
        "void SimpleProductComponent::advance_registration_bootstrap_()",
        "void SimpleProductComponent::advance_pairing_()",
    )

    assert "kRegistrationUserConfirmMs = 60000ULL" in header
    assert "found->expires_at_ms = now_ms + kRegistrationUserConfirmMs;" in confirm

    assert "uint32_t selected_expires_in_s = 0;" in status
    assert "const uint64_t remaining_ms = found->expires_at_ms - now_ms;" in status
    assert "(remaining_ms - 1U) / 1000U" in status
    assert 'root["expires_in_s"] = selected_expires_in_s;' in status

    assert 'Number.isInteger(body.expires_in_s)' in html
    assert '"开始注册（" + remaining + "s）"' in html
    assert "countdownTimer = setInterval" in html
    assert 'button.textContent = "开始注册（0s）";' in html
    assert "button.disabled = true;" in html
    assert "pollSoon(0);" in html

    assert "candidate.expires_at_ms > now_ms" in begin
    assert "registration_candidates_[selected_index].expired(now_ms())" not in discovery
    assert "selected_registration_candidate_.expired(now)" not in bootstrap
    assert "irreversible boundary is crossed" in bootstrap


def test_r10_phone_page_owns_terminal_feedback() -> None:
    html = portal_html()
    header = text(PORTAL_H)
    component = text(COMPONENT_CPP)

    assert "SUCCESS" in header
    assert "ERROR" in header
    assert 'body.status === "success"' in html
    assert '"联机注册成功"' in html
    assert 'body.status === "error"' in html
    assert "body.error_code" in html
    assert "body.message" in html

    assert "registration_portal_.set_registration_success()" in component
    assert "registration_portal_.set_registration_error(code, message)" in component


def test_r10_lcd_never_locks_page_for_registration() -> None:
    display = text(DISPLAY)

    assert "const int page = id(display_page);" in display
    assert "force_registration_page" not in display

    page4 = display.split("// ─── PAGE 4：", 1)[1].split(
        "// ─── 底部页码与时间 ───", 1
    )[0]
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
    ):
        assert transient not in page4


def test_r10_success_page_delivery_grace_is_bounded() -> None:
    header = text(COMPONENT_H)
    component = text(COMPONENT_CPP)

    assert "kRegistrationPortalSuccessGraceMs = 15000" in header
    assert "registration_portal_success_until_ms_" in header
    assert "registration_portal_.set_registration_success()" in component
    assert "portal_now < registration_portal_success_until_ms_" in component
    assert "registration_portal_success_until_ms_ = 0U;" in component


def test_r10_transient_pairing_retries_do_not_publish_false_terminal_error() -> None:
    component = text(COMPONENT_CPP)

    bootstrap = function_block(
        component,
        "void SimpleProductComponent::advance_registration_bootstrap_()",
        "void SimpleProductComponent::advance_pairing_()",
    )
    http_wait = function_block(
        bootstrap,
        "if (result == SimplePairingClientError::HTTP_FAILED)",
        "if (result == SimplePairingClientError::NOT_READY)",
    )
    assert "show_registration_error_" not in http_wait
    assert "waiting after transient HTTP failure" in http_wait

    recovery = function_block(
        component,
        "void SimpleProductComponent::advance_pairing_()",
        "void SimpleProductComponent::advance_recovery_()",
    )
    unresolved = recovery.rsplit("ESP_LOGW(", 1)[1]
    assert "recovery still unresolved" in unresolved
    assert "show_registration_error_" not in unresolved


def test_r10_product_ui_source_does_not_embed_bench_low_battery_bypass() -> None:
    target = text(TARGET)

    assert 'battery_low_threshold: "-1.00"' not in target
    assert "PHYSICAL_ACCEPTANCE_ONLY" not in target
    assert "LOW_BATTERY_PROTECTION_BYPASSED" not in target
