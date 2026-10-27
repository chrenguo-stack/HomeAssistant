from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
TRANSPORT = ROOT / "firmware/esphome_rc/f1_0_rc2/packages/n3w_product_transport.yml"
DISPLAY = ROOT / "firmware/esphome_rc/f1_0_rc2/packages/display.yml"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def function_block(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


def test_r4_registration_portal_is_narrow_and_secret_free() -> None:
    header = text(CORE / "n3w_registration_portal.h")
    source = text(CORE / "n3w_registration_portal.cpp")

    assert "kRegistrationPortalPort = 47113" in source
    assert "kScanTokenBytes = 16" in source
    assert '"/register"' in source
    assert '"/api/v1/register/start"' in source
    assert '"/api/v1/register/status"' in source
    assert '"/api/v1/register/confirm"' in source
    assert '"/api/v1/register/retry"' in source
    assert "httpd_start" in source
    assert "httpd_stop" in source
    assert "Cache-Control" in source
    assert "no-store" in source
    assert "localStorage" not in source
    assert "document.cookie" not in source

    page_start = source.index("const char kPortalPage[]")
    page_end = source.index("std::string base64url_encode", page_start)
    page = source[page_start:page_end]
    for secret_marker in (
        "setup_secret",
        "hardware_id",
        "pairing_id",
        "mqtt_password",
        "system_peer_key",
    ):
        assert secret_marker not in page.lower()

    assert "class RegistrationPortalRandom" in header
    assert "class RegistrationPortalState" in header
    assert "registration_portal_allowed()" in header
    assert "scan_trigger_pending_" in header
    assert "take_scan_trigger()" in header


def test_r4_qr_is_actionable_local_url_and_regenerates_with_sta_ipv4() -> None:
    source = text(CORE / "n3w_registration_portal.cpp")
    component = text(CORE / "n3w_simple_product_component.cpp")
    component_h = text(CORE / "n3w_simple_product_component.h")
    transport = text(TRANSPORT)
    display = text(DISPLAY)

    assert '"/register#t=" + scan_token_' in source
    assert '"http://" + local_ipv4_' in source
    assert "local_ipv4 == local_ipv4_" in source
    assert "subnet_mask == subnet_mask_" in source
    assert "stop();" in source
    assert "return start_(local_ipv4, subnet_mask);" in source

    assert "pairing_handoff_ready()" in transport
    assert "pairing_qr_payload()" in transport
    assert "registration_qr_payload()" in component_h
    assert "#ifdef GH_N3W_PRODUCTION_DEHARNESS" in component_h
    assert "return registration_portal_.qr_payload();" in component_h
    assert "return pairing_client_.pairing_qr_payload();" in component_h
    assert "GHN3W2:pending" in display

    portal = function_block(
        component,
        "void SimpleProductComponent::advance_registration_portal_()",
        "void SimpleProductComponent::advance_pairing_()",
    )
    assert "wifi_connected()" in portal
    assert "current_wifi_ipv4_(&local_ipv4, &subnet_mask)" in portal
    assert "registration_portal_.ensure_running(local_ipv4, subnet_mask)" in portal


def test_r4_idle_unregistered_node_no_longer_auto_discovers_manager() -> None:
    component = text(CORE / "n3w_simple_product_component.cpp")
    loop = function_block(
        component,
        "void SimpleProductComponent::loop()",
        "TelemetrySubmitDisposition SimpleProductComponent::submit_telemetry_json",
    )

    assert "pairing_ack_pending_" in loop
    assert "advance_pairing_();" in loop
    assert "advance_registration_portal_();" in loop
    assert loop.index("if (pairing_ack_pending_)") < loop.index("advance_pairing_();")
    assert loop.index("} else {") < loop.index("advance_registration_portal_();")

    pairing = function_block(
        component,
        "void SimpleProductComponent::advance_pairing_()",
        "void SimpleProductComponent::advance_recovery_()",
    )
    assert "pairing_client_.run_once(now)" in pairing
    assert "pairing_client_.resume_pending_ack()" in pairing
    assert "pairing_ack_pending_" in pairing


def test_r4_pending_ack_recovery_is_preserved() -> None:
    component_h = text(CORE / "n3w_simple_product_component.h")
    component = text(CORE / "n3w_simple_product_component.cpp")

    assert "bool pairing_ack_pending_{false};" in component_h
    assert (
        "pairing_ack_pending_ = pairing == "
        "SimplePairingClientError::ACK_PENDING;"
        in component
    )
    assert "pairing_ack_pending_ = false;" in component
    assert "pairing_client_.resume_pending_ack()" in component
    assert "registration_portal_.stop();" in component


def test_r4_portal_rejects_nonlocal_and_stale_scan_actions() -> None:
    source = text(CORE / "n3w_registration_portal.cpp")

    assert "getpeername(" in source
    assert "state_->registration_portal_allowed()" in source
    component_h = text(CORE / "n3w_simple_product_component.h")
    component = text(CORE / "n3w_simple_product_component.cpp")
    assert "std::atomic<bool> registration_portal_allowed_{false};" in component_h
    assert "registration_portal_allowed_.load(std::memory_order_acquire)" in component_h
    assert "registration_portal_allowed_.store(" in component
    assert "(peer.sin_addr.s_addr & mask_addr_) ==" in source
    assert "(local_addr_ & mask_addr_)" in source
    assert "constant_time_equal(token, scan_token_)" in source
    assert "scan_session_invalid" in source
    assert "rate_limited" in source
    assert "kMaxActionBodyBytes = 512" in source


def test_r4_does_not_implement_r5_discovery_or_r6_bootstrap() -> None:
    portal = text(CORE / "n3w_registration_portal.cpp")
    header = text(CORE / "n3w_registration_portal.h")

    scope = portal + "\n" + header
    assert "discover_manager(" not in scope
    assert "RegistrationDiscovery" not in scope
    assert "bootstrap_tls_sha256" not in scope
    assert "esp_tls" not in scope
    assert "setup_secret_base64url" not in scope
    assert "discovery_stage_pending" in portal
