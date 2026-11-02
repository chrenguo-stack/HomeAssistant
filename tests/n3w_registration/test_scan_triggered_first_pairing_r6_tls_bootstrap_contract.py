from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"


def text(name: str) -> str:
    return (CORE / name).read_text(encoding="utf-8")


def function_block(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


def test_r6_tls_pin_is_proven_before_any_http_request_is_constructed() -> None:
    source = text("n3w_registration_bootstrap_transport.cpp")

    assert "verify_pinned_leaf" in source
    assert "certificate->raw.p" in source
    assert "certificate->raw.len" in source
    assert "constant_time_equal(observed, verify->expected)" in source
    assert "MBEDTLS_SSL_VERIFY_NONE" not in source
    assert (
        "mbedtls_ssl_conf_authmode(&config, MBEDTLS_SSL_VERIFY_OPTIONAL)"
        in source
    )
    assert (
        "mbedtls_ssl_conf_authmode(&config, MBEDTLS_SSL_VERIFY_REQUIRED)"
        not in source
    )
    assert "mbedtls_ssl_conf_ca_chain" not in source
    assert "mbedtls_ssl_conf_ca_cb" not in source
    assert "MBEDTLS_ERR_X509_FATAL_ERROR" in source
    assert "mbedtls_ssl_conf_verify(&config, verify_pinned_leaf, &verify)" in source

    setup = source.index("mbedtls_ssl_setup(&ssl, &config)")
    hostname = source.index("mbedtls_ssl_set_hostname(&ssl, host.c_str())")
    handshake = source.index("mbedtls_ssl_handshake(&ssl)")
    pin_gate = source.index("!verify.leaf_seen || !verify.leaf_matched")
    request = source.index('std::string request =\n        "POST "')
    write = source.index("tls_write_all(&ssl, &bio, request)")
    assert setup < hostname < handshake < pin_gate < request < write
    assert "request_json;" in source[request:write]
    assert "esp_http_client" not in source

    assert "(status >= 300 && status <= 399)" in source
    assert 'key == "transfer-encoding" || key == "location"' in source
    assert "kMaxResponseBytes = 8192" in source
    assert "kMaxRequestBodyBytes = 2048" in source

    # ESP-IDF's documented bounded-connect pattern is non-blocking connect
    # followed by select(); do not rely on SO_SNDTIMEO to bound connect().
    assert "original_flags | O_NONBLOCK" in source
    assert "::select(" in source
    assert "SO_ERROR" in source
    connect_start = source.index("int connected = ::connect(")
    select_wait = source.index("const int selected = ::select(", connect_start)
    so_error = source.index("SO_ERROR", select_wait)
    restore_blocking = source.index(
        "::fcntl(socket_fd, F_SETFL, original_flags)", so_error
    )
    assert connect_start < select_wait < so_error < restore_blocking


def test_r6_pin_mismatch_remains_fatal_under_optional_ca_verification() -> None:
    source = text("n3w_registration_bootstrap_transport.cpp")
    verify = function_block(
        source,
        "int verify_pinned_leaf(",
        "struct SocketBio",
    )

    assert "verify->leaf_seen = true;" in verify
    assert "verify->pin_mismatch = true;" in verify
    assert "return MBEDTLS_ERR_X509_FATAL_ERROR;" in verify
    assert "*flags = 0U;" in verify
    assert "verify->leaf_matched = true;" in verify

    handshake = source.index("mbedtls_ssl_handshake(&ssl)")
    pin_gate = source.index("!verify.leaf_seen || !verify.leaf_matched")
    request = source.index('std::string request =\n        "POST "')
    assert handshake < pin_gate < request


def test_r6_confirm_contract_is_exact_and_keeps_server_deadline_authoritative() -> None:
    header = text("n3w_registration_bootstrap_client.h")
    source = text("n3w_registration_bootstrap_client.cpp")

    assert '"gh.registration.confirm/1"' in header
    assert '"gh.registration.confirm-result/1"' in header
    assert "kRegistrationPairingPort = 47112" in header
    assert 'kRegistrationPairingPath[] = "/v2/pairing"' in header
    assert "kRegistrationTransactionMaxSeconds = 1800" in header

    for token in (
        'root.size() != 9U',
        'manager_id != selected.manager_id',
        'system_id != selected.system_id',
        'root["pairing_port"].as<uint16_t>() != kRegistrationPairingPort',
        'pairing_path != kRegistrationPairingPath',
        "expires > kRegistrationTransactionMaxSeconds",
        "pairing_host_allowed(pairing_host, local_ipv4, subnet_mask)",
        "kRegistrationDeadlineSafetyMs = 1000ULL",
        "parsed.transaction_deadline_ms = received_ms + safe_delta_ms",
    ):
        assert token in source

    assert 'disposition != "terminal"' in source
    assert 'reason != "expired" && reason != "replay_detected"' in source


def test_r6_selected_candidate_is_the_only_product_bootstrap_entry() -> None:
    component = text("n3w_simple_product_component.cpp")

    loop = function_block(
        component,
        "void SimpleProductComponent::loop()",
        "TelemetrySubmitDisposition SimpleProductComponent::submit_telemetry_json",
    )
    assert "advance_registration_discovery_();" in loop
    assert "advance_registration_bootstrap_();" in loop
    assert loop.index("advance_registration_discovery_();") < loop.index(
        "advance_registration_bootstrap_();"
    )

    discovery = function_block(
        component,
        "void SimpleProductComponent::advance_registration_discovery_()",
        "void SimpleProductComponent::advance_registration_bootstrap_()",
    )
    assert "take_selected_candidate_id(&selected_id)" in discovery
    assert "registration_candidate_selected_ = true;" in discovery
    assert "setup_secret" not in discovery.lower()
    assert "registration_bootstrap_post_(" not in discovery

    bootstrap = function_block(
        component,
        "void SimpleProductComponent::advance_registration_bootstrap_()",
        "void SimpleProductComponent::advance_pairing_()",
    )
    assert "build_registration_confirm_request(" in bootstrap
    assert "pairing_client_.setup_secret_base64url()" in bootstrap
    assert "registration_bootstrap_post_(" in bootstrap
    assert "parse_registration_confirm_response(" in bootstrap
    assert "pairing_client_.run_selected_candidate(" in bootstrap
    assert "pairing_client_.run_once(" not in bootstrap

    # A missing confirm response does not renew identity: the same durable
    # pairing ID must be used by the next explicit user scan.
    posted_failure = bootstrap.index("if (!posted)")
    terminal = bootstrap.index(
        "confirmed.action == RegistrationBootstrapConfirmAction::TERMINAL"
    )
    renewal = bootstrap.index("pairing_client_.renew_pairing_intent()", terminal)
    assert posted_failure < terminal < renewal
    assert "renew_pairing_intent" not in bootstrap[posted_failure:terminal]


def test_r6_reuses_existing_pairing_crypto_after_47110() -> None:
    source = text("n3w_simple_pairing_client.cpp")
    header = text("n3w_simple_pairing_client.h")

    assert "run_selected_candidate(" in header
    selected = function_block(
        source,
        "SimplePairingClientError SimplePairingClient::run_selected_candidate(",
        "SimplePairingClientError SimplePairingClient::renew_pairing_intent()",
    )
    assert "send_hello_(candidate)" in selected
    assert "pair_with_(candidate, &recovery)" in selected
    assert "discover_(&candidate)" not in selected

    pair = function_block(
        source,
        "SimplePairingClientError SimplePairingClient::pair_with_(",
        "SimplePairingClientError SimplePairingClient::persist_bundle_(",
    )
    for token in (
        '"gh.pair.simple-begin/1"',
        "derive_bootstrap_key(",
        "decrypt_simple_credential_bundle(",
        "parse_bundle(",
    ):
        assert token in pair


def test_r6_final_ack_requires_consumed_session_and_node_binding() -> None:
    source = text("n3w_simple_pairing_client.cpp")

    parser = function_block(
        source,
        "bool parse_final_ack_response(",
        "RegistrationBootstrapRecoveryBinding recovery_binding_from_pending(",
    )
    for token in (
        '"gh.pair.simple-status/1"',
        'session_id == pending.session_id',
        'state == "consumed"',
        "node_id == expected_node_id",
        "root.size() == 5U",
    ):
        assert token in parser

    ack = function_block(
        source,
        "SimplePairingClientError SimplePairingClient::acknowledge_(",
        "SimplePairingClientError SimplePairingClient::finalize_committed_()",
    )
    assert "status == 200" in ack
    assert "parse_final_ack_response(" in ack
    assert ack.index("status == 200") < ack.index("parse_final_ack_response(")
    assert "post_registration_status(" in ack
    assert "build_registration_status_request(" in ack


def test_r6_pending_ack_v2_is_crash_safe_and_v1_remains_readable() -> None:
    header = text("n3w_esp32_pairing_nvs.h")
    nvs = text("n3w_esp32_pairing_nvs.cpp")
    client = text("n3w_simple_pairing_client.cpp")

    assert "kPendingPairingAckLegacyVersion = 1U" in header
    assert "kPendingPairingAckCurrentVersion = 2U" in header
    assert "TERMINAL_CLEANUP" in header
    for token in (
        "struct PersistedPendingAckV1",
        "struct PersistedPendingAckV2",
        "size == sizeof(PersistedPendingAckV1)",
        "size != sizeof(PersistedPendingAckV2)",
        "candidate.format_version = kPendingPairingAckLegacyVersion",
        "candidate.format_version = kPendingPairingAckCurrentVersion",
    ):
        assert token in nvs

    load_existing = function_block(
        client,
        "SimplePairingClientError SimplePairingClient::load_existing_()",
        "SimplePairingClientError SimplePairingClient::prepare_bootstrap_()",
    )
    assert "PendingPairingAckState::TERMINAL_CLEANUP" in load_existing
    assert load_existing.index("PendingPairingAckState::TERMINAL_CLEANUP") < (
        load_existing.index("if (credentials_present)")
    )

    ack = function_block(
        client,
        "SimplePairingClientError SimplePairingClient::acknowledge_(",
        "SimplePairingClientError SimplePairingClient::finalize_committed_()",
    )
    marker = ack.index(
        "pending.state = PendingPairingAckState::TERMINAL_CLEANUP;"
    )
    persist = ack.index("ack_store_->save(pending)", marker)
    cleanup = ack.index("complete_terminal_cleanup_(pending)", persist)
    assert marker < persist < cleanup

    terminal = function_block(
        client,
        "SimplePairingClientError SimplePairingClient::complete_terminal_cleanup_(",
        "bool SimplePairingClient::fill_(",
    )
    assert terminal.index("renew_pairing_intent_()") < terminal.index(
        "broker_store_->erase()"
    )
    assert "if (!setup_secret_ready_)" in terminal
    assert "prepare_bootstrap_()" in terminal
    assert terminal.index("broker_store_->erase()") < terminal.index(
        "peer_store_->erase()"
    )
    assert terminal.index("peer_store_->erase()") < terminal.index(
        "ack_store_->erase()"
    )


def test_r6_status_recovery_relocates_only_exact_original_tls_identity() -> None:
    component = text("n3w_simple_product_component.cpp")
    bootstrap = text("n3w_registration_bootstrap_client.cpp")

    status = function_block(
        component,
        "bool SimpleProductComponent::post_registration_status(",
        "}  // namespace esphome::greenhouse_n3w_core",
    )
    assert "registration_discovery_.discover(" in status
    assert "registration_relocation_matches(candidate, binding)" in status
    assert "if (relocated != nullptr)" in status
    assert "return false;" in status
    assert "pending->bootstrap_host = relocated->host;" in status

    match = function_block(
        bootstrap,
        "bool registration_relocation_matches(",
        "}  // namespace esphome::greenhouse_n3w_core",
    )
    assert "candidate.manager_id == binding.manager_id" in match
    assert "candidate.system_id == binding.system_id" in match
    assert (
        "candidate.bootstrap_tls_sha256 == binding.bootstrap_tls_sha256"
        in match
    )
    assert "candidate.bootstrap_port == binding.bootstrap_port" in match


def test_r6_browser_handoff_never_exposes_bootstrap_secrets_or_locator() -> None:
    portal = text("n3w_registration_portal.cpp")
    page_start = portal.index("const char kPortalPage[]")
    page_end = portal.index("std::string base64url_encode", page_start)
    page = portal[page_start:page_end]

    confirm = function_block(
        portal,
        "esp_err_t RegistrationPortal::handle_confirm_",
        "esp_err_t RegistrationPortal::handle_retry_",
    )
    assert '"202 Accepted"' in confirm
    assert '"next\\":\\"bootstrap\\"' in confirm
    for forbidden in (
        "setup_secret",
        "bootstrap_tls_sha256",
        "manager_id",
        "system_id",
        "mqtt_password",
    ):
        assert forbidden not in page.lower()
        assert forbidden not in confirm.lower()
