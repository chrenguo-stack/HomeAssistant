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
MANAGER = (
    ROOT
    / "host"
    / "greenhouse-manager"
    / "src"
    / "greenhouse_manager"
    / "runtime"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def portal_html() -> str:
    source = read(CORE / "n3w_registration_portal.cpp")
    match = re.search(
        r'const char kPortalPage\[\] = R"HTML\((.*?)\)HTML";',
        source,
        flags=re.DOTALL,
    )
    assert match is not None
    return match.group(1)


def function_block(
    source: str,
    start: str,
    end: str,
) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


def test_actual_phone_page_is_only_a_safe_scan_selection_surface() -> None:
    html = portal_html()

    assert 'params.get("t")' in html
    assert 'history.replaceState(null, "", location.pathname)' in html
    assert 'schema: "gh.registration.portal-action/1"' in html

    for path in (
        "/api/v1/register/start",
        "/api/v1/register/status",
        "/api/v1/register/confirm",
        "/api/v1/register/retry",
    ):
        assert path in html

    assert "candidate.id" in html
    assert "candidate.label" in html
    assert "candidate_id: candidateId" in html

    forbidden = (
        "setup_secret",
        "pairing_id",
        "hardware_id",
        "manager_id",
        "system_id",
        "bootstrap_tls_sha256",
        "mqtt_password",
        "n3w_application_key",
        "system_peer_key",
        "47110",
        "47112",
    )
    lowered = html.lower()
    for token in forbidden:
        assert token not in lowered


def test_actual_phone_page_requires_explicit_candidate_click() -> None:
    html = portal_html()

    assert "list.forEach(candidate =>" in html
    assert 'document.createElement("button")' in html
    assert "button.textContent = candidate.label" in html
    assert "button.onclick = () => confirmCandidate(candidate.id)" in html

    wait = html.index('body.status === "wait_confirm"')
    confirm = html.index("confirmCandidate(candidate.id)", wait)
    assert confirm > wait

    assert "candidates[0]" not in html
    assert "autoSelect" not in html
    assert "auto_select" not in html


def test_invalid_or_stale_scan_token_cannot_reach_selection() -> None:
    source = read(CORE / "n3w_registration_portal.cpp")

    assert "constant_time_equal" in source
    assert "scan_session_invalid" in source
    assert "candidate_stale" in source

    confirm = function_block(
        source,
        "esp_err_t RegistrationPortal::handle_confirm_",
        "esp_err_t RegistrationPortal::handle_retry_",
    )
    token_check = confirm.index("read_action_request_")
    selection = confirm.index("selected_candidate_id_")
    assert token_check < selection


def test_r8_does_not_replace_r6_tls_pin_before_secret_contract() -> None:
    bootstrap = read(CORE / "n3w_registration_bootstrap.cpp")
    r6 = read(
        ROOT
        / "tests"
        / "n3w_registration"
        / "test_scan_triggered_first_pairing_r6_tls_bootstrap_contract.py"
    )

    assert "PIN_MISMATCH" in bootstrap
    assert "setup_secret" in bootstrap
    assert "PIN_MISMATCH" in r6
    assert "setup_secret" in r6

    pin = bootstrap.index("PIN_MISMATCH")
    secret = bootstrap.index("setup_secret", pin)
    assert pin < secret


def test_manager_status_recovery_cannot_open_or_refresh_47112() -> None:
    source = read(MANAGER / "n3w_first_registration_transaction.py")
    status = function_block(
        source,
        "    def status(",
        "    def window_closed(",
    )

    assert "open_first_registration" not in status
    assert "create_active" not in status
    assert "expires_at =" not in status
    assert 'status="committed"' in status
    assert 'status="unknown"' in status
    assert 'transaction_disposition="wait"' in status


def test_manager_final_ack_marks_durable_commit_before_close_callback() -> None:
    source = read(MANAGER / "n3w_simplified_pairing.py")
    acknowledge = function_block(
        source,
        "    def acknowledge(",
        "    def abort(",
    )

    claim = acknowledge.index("ledger.claim_committing")
    classify = acknowledge.index("reconciler.classify")
    durable = acknowledge.index("ledger.mark_committed")
    callback = acknowledge.index(
        "self.first_registration_complete_callback"
    )

    assert claim < classify < durable < callback
    assert (
        "classification\n"
        "                    is not "
        "FirstRegistrationCommitClassification.COMMITTED"
        in acknowledge
    )


def test_dynamic_first_registration_has_only_commit_or_deadline_close_paths() -> None:
    source = read(MANAGER / "n3w_dynamic_pairing_window.py")
    first = function_block(
        source,
        "    def open_first_registration(",
        "    def _close_locked(",
    )

    assert "_deadline_run" in source
    assert "complete_first_registration" in source
    assert 'reason="committed"' in source
    assert 'reason="deadline"' in source

    assert "close_window(" not in first
    assert "manager_shutdown" not in first


def test_r8_keeps_exact_1800_second_transaction_constant() -> None:
    source = read(MANAGER / "n3w_first_registration_transaction.py")
    assert "FIRST_REGISTRATION_TTL_SECONDS = 1800" in source
    assert (
        'raise ValueError("first registration TTL must be exactly 1800 seconds")'
        in source
    )


def test_r7_display_success_authority_remains_provisioned_only() -> None:
    source = read(CORE / "n3w_simple_product_component.cpp")
    assert "pairing_client_.provisioned()" in source
    assert "show_registration_success_" in source

    success_calls = [
        match.start()
        for match in re.finditer(
            r"show_registration_success_\(now_ms\)",
            source,
        )
    ]
    assert success_calls
    for position in success_calls:
        window = source[max(0, position - 1200) : position + 200]
        assert "pairing_client_.provisioned()" in window
