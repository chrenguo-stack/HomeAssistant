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
        "/api/v1/register/begin",
        "/api/v1/register/retry",
    ):
        assert path in html

    assert "candidate.id" in html
    assert "candidate.label" in html
    assert "candidate_id: candidate.id" in html

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
    assert "addButton(candidate.label, () => selectCandidate(candidate))" in html
    assert 'addButton("开始注册", beginRegistration)' in html
    assert 'post("/api/v1/register/begin")' in html

    wait = html.index('body.status === "wait_confirm"')
    select = html.index("selectCandidate(candidate)", wait)
    begin = html.index('addButton("开始注册", beginRegistration)', select)
    assert wait < select < begin

    assert "candidates[0]" not in html
    assert "autoSelect" not in html
    assert "auto_select" not in html
    assert "取消注册" not in html
    assert "/api/v1/register/cancel" not in html

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


def test_r8_keeps_r6_tls_contract_as_a_required_predecessor() -> None:
    r6 = read(
        ROOT
        / "tests"
        / "n3w_registration"
        / "test_scan_triggered_first_pairing_r6_tls_bootstrap_contract.py"
    )
    workflow = read(ROOT / ".github" / "workflows" / "greenhouse-manager-ci.yml")

    assert (
        "def test_r6_tls_pin_is_proven_before_any_http_request_is_constructed"
        in r6
    )
    assert "mbedtls_ssl_handshake(&ssl)" in r6
    assert "!verify.leaf_seen || !verify.leaf_matched" in r6
    assert "tls_write_all(&ssl, &bio, request)" in r6

    r6_step = workflow.index(
        "N3-W scan-triggered first-registration R6 TLS bootstrap contracts"
    )
    r8_step = workflow.index(
        "N3-W scan-triggered first-registration R8 E2E safety contracts"
    )
    assert r6_step < r8_step


def test_manager_durable_attempt_precedes_window_open_and_accept_response() -> None:
    source = read(MANAGER / "n3w_first_registration_transaction.py")
    start = function_block(
        source,
        "    def start(",
        "    def status(",
    )

    create = start.index("self.ledger.create_active(")
    activate = start.index("self.intents.activate(intent)")
    open_window = start.index("self.window.open_first_registration(intent)")
    accepted = start.index("return FirstRegistrationStartResult(")

    assert create < activate < open_window < accepted


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


def test_r8_keeps_r7_success_authority_contract_as_a_predecessor() -> None:
    r7 = read(
        ROOT
        / "tests"
        / "n3w_registration"
        / "test_scan_triggered_first_pairing_r7_lcd_state_contract.py"
    )
    workflow = read(ROOT / ".github" / "workflows" / "greenhouse-manager-ci.yml")

    assert (
        "def test_r7_component_is_the_only_display_authority_and_success_is_commit_bound"
        in r7
    )
    assert 'if (pairing_client_.provisioned())' in r7
    assert "show_registration_success_();" in r7

    r7_step = workflow.index(
        "N3-W scan-triggered first-registration R7 LCD state contracts"
    )
    r8_step = workflow.index(
        "N3-W scan-triggered first-registration R8 E2E safety contracts"
    )
    assert r7_step < r8_step
