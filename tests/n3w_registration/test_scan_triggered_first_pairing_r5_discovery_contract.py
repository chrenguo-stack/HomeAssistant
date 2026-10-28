from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "firmware/esphome_rc/components/greenhouse_n3w_core"
MANAGER_DISCOVERY = (
    ROOT
    / "host/greenhouse-manager/src/greenhouse_manager/runtime"
    / "n3w_registration_discovery.py"
)


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def function_block(source: str, start: str, end: str) -> str:
    begin = source.index(start)
    finish = source.index(end, begin)
    return source[begin:finish]


def test_r5_reuses_registration_candidate_contract_and_bounded_transports() -> None:
    header = text(CORE / "n3w_registration_discovery.h")
    source = text(CORE / "n3w_registration_discovery.cpp")
    manager_h = text(CORE / "n3w_manager_discovery.h")
    manager_cpp = text(CORE / "n3w_manager_discovery.cpp")

    assert 'kRegistrationDiscoveryProtocol[] =\n    "gh.n3w.first-registration/1"' in header
    assert '"gh.registration.candidate/1"' in header
    assert '"gh.registration.discovery-result/1"' in header
    assert "kRegistrationDiscoveryMaxCandidates = 4" in header
    assert "kRegistrationBootstrapPort = 47110" in header
    assert "kRegistrationCandidateTtlSeconds = 30" in header

    assert 'mdns_query_ptr(\n      "_greenhouse-reg",\n      "_tcp"' in source
    assert "kRegistrationMdnsTimeoutMs = 1500" in source
    assert "#ifdef GH_N3W_PRODUCTION_DEHARNESS" in source
    init_py = text(CORE / "__init__.py")
    assert 'AUTO_LOAD = ["json"]' in init_py
    assert '"mdns"' not in init_py.split("AUTO_LOAD =", 1)[1].split("\n", 1)[0]
    assert "kRegistrationUdpAttempts = 3" in source
    assert "Esp32ManagerDiscoveryNetwork network;" in source
    assert "network.collect_manager_discovery(" in source
    assert "kRegistrationQueryPaddedBytes = 1400" in source
    assert "if (candidates->empty()) {" in source
    assert source.index("collect_mdns_(") < source.rindex("collect_udp_(")

    assert "build_discovery_query_for_protocol(" in manager_h
    assert "build_discovery_query_for_protocol(" in manager_cpp
    assert "return build_discovery_query_for_protocol(" in manager_cpp
    assert "kSimplePairingProtocol" in manager_cpp


def test_r5_node_contract_matches_existing_r1_manager_contract() -> None:
    manager = text(MANAGER_DISCOVERY)
    header = text(CORE / "n3w_registration_discovery.h")
    source = text(CORE / "n3w_registration_discovery.cpp")

    assert 'REGISTRATION_PROTOCOL = "gh.n3w.first-registration/1"' in manager
    assert 'CANDIDATE_SCHEMA = "gh.registration.candidate/1"' in manager
    assert 'RESPONSE_SCHEMA = "gh.registration.discovery-result/1"' in manager
    assert 'REGISTRATION_SERVICE_TYPE = "_greenhouse-reg._tcp.local."' in manager
    assert 'bootstrap_scheme: str = "https"' in manager
    assert "bootstrap_port: int = 47110" in manager
    assert 'bootstrap_path: str = "/v1/registration/confirm"' in manager
    assert "ttl_s: int = 30" in manager

    assert '"gh.n3w.first-registration/1"' in header
    assert '"gh.registration.candidate/1"' in header
    assert '"gh.registration.discovery-result/1"' in header
    assert "kRegistrationBootstrapPort = 47110" in header
    assert "kRegistrationCandidateTtlSeconds = 30" in header
    assert 'bootstrap_path == "/v1/registration/confirm"' in source


def test_r5_candidate_parser_is_exact_and_fail_closed() -> None:
    source = text(CORE / "n3w_registration_discovery.cpp")

    for token in (
        'schema != kRegistrationCandidateSchema',
        'scheme != "https"',
        'protocol != kRegistrationDiscoveryProtocol',
        'bootstrap_port == kRegistrationBootstrapPort',
        'bootstrap_path == "/v1/registration/confirm"',
        'ttl_s == kRegistrationCandidateTtlSeconds',
        "lowercase_sha256(bootstrap_tls_sha256)",
        'std::string(root["request_id"] | "") != request_id',
        'std::string(root["nonce"] | "") != nonce_text',
        "source == candidate",
    ):
        assert token in source

    assert "value.size() != 12U" in source
    assert "root.size() != 4U" in source
    assert "candidates->size() >= kRegistrationDiscoveryMaxCandidates" in source
    assert "existing.manager_id == candidate.manager_id" in source
    assert "existing.system_id == candidate.system_id" in source
    assert "existing.host == candidate.host" in source
    assert "existing.bootstrap_port == candidate.bootstrap_port" in source


def test_r5_discovery_is_only_consumed_after_scan_trigger() -> None:
    component = text(CORE / "n3w_simple_product_component.cpp")
    portal = text(CORE / "n3w_registration_portal.cpp")

    loop = function_block(
        component,
        "void SimpleProductComponent::loop()",
        "TelemetrySubmitDisposition SimpleProductComponent::submit_telemetry_json",
    )
    assert "advance_registration_portal_();" in loop
    assert "advance_registration_discovery_();" in loop

    discovery = function_block(
        component,
        "void SimpleProductComponent::advance_registration_discovery_()",
        "void SimpleProductComponent::advance_registration_bootstrap_()",
    )
    trigger = "if (registration_portal_.take_scan_trigger())"
    call = "registration_discovery_.discover("
    assert trigger in discovery
    assert call in discovery
    assert discovery.index(trigger) < discovery.index(call)
    assert "pairing_client_.run_once(" not in discovery
    assert "post_json(" not in discovery
    assert "http_post_(" not in discovery

    assert "scan_trigger_pending_.store(true" in portal
    assert "RegistrationPortalStage::DISCOVERING" in portal


def test_r5_browser_exposes_only_opaque_candidate_id_and_label() -> None:
    portal = text(CORE / "n3w_registration_portal.cpp")

    page_start = portal.index("const char kPortalPage[]")
    page_end = portal.index("std::string base64url_encode", page_start)
    page = portal[page_start:page_end]

    assert "candidate.label" in page
    assert "candidate.id" in page
    assert "candidate_id: candidateId" in page

    for forbidden in (
        "setup_secret",
        "hardware_id",
        "pairing_id",
        "bootstrap_tls_sha256",
        "manager_id",
        "system_id",
        "mqtt_password",
    ):
        assert forbidden not in page.lower()

    status = function_block(
        portal,
        "esp_err_t RegistrationPortal::handle_status_",
        "esp_err_t RegistrationPortal::handle_confirm_",
    )
    assert 'item["id"] = candidate.id;' in status
    assert 'item["label"] = candidate.label;' in status
    assert 'root["node_label"] = node_label;' in status
    assert "node.textContent = body.node_label;" in page
    for forbidden in (
        'item["host"]',
        'item["port"]',
        'item["manager_id"]',
        'item["system_id"]',
        'item["bootstrap_tls_sha256"]',
    ):
        assert forbidden not in status


def test_r5_multiple_candidates_require_explicit_browser_selection() -> None:
    component = text(CORE / "n3w_simple_product_component.cpp")
    portal = text(CORE / "n3w_registration_portal.cpp")
    header = text(CORE / "n3w_registration_portal.h")

    discovery = function_block(
        component,
        "void SimpleProductComponent::advance_registration_discovery_()",
        "void SimpleProductComponent::advance_registration_bootstrap_()",
    )
    assert "registration_portal_.set_candidates(views);" in discovery
    portal_setup = function_block(
        component,
        "void SimpleProductComponent::advance_registration_portal_()",
        "void SimpleProductComponent::clear_registration_discovery_()",
    )
    assert "hardware_id.substr(hardware_id.size() - suffix_size)" in portal_setup
    assert 'std::string("节点 ")' in portal_setup

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

    assert 'root["candidate_id"]' in portal
    assert "RegistrationPortalStage::WAIT_CONFIRM" in confirm
    assert "candidate.expires_at_ms > now_ms" in confirm
    assert "selected_candidate_id_ = candidate_id;" in confirm
    assert "RegistrationPortalStage::CANDIDATE_SELECTED" in confirm
    assert '"next\\":\\"user_confirm\\"' in confirm
    assert "RegistrationPortalStage::SELECTED_PENDING_BOOTSTRAP" not in confirm

    assert "RegistrationPortalStage::CANDIDATE_SELECTED" in begin
    assert "RegistrationPortalStage::SELECTED_PENDING_BOOTSTRAP" in begin
    assert '"next\\":\\"bootstrap\\"' in begin

    assert (
        "discovery_stage_ !=\n"
        "          RegistrationPortalStage::SELECTED_PENDING_BOOTSTRAP"
        in portal
    )
    assert "bool take_selected_candidate_id(std::string *candidate_id);" in header
    assert "take_selected_candidate_id(&selected_id)" in discovery
    assert (
        "selected_registration_candidate_ =\n"
        "      registration_candidates_[selected_index];"
    ) in discovery
    assert discovery.index("take_selected_candidate_id(&selected_id)") < discovery.index(
        "selected_registration_candidate_ ="
    )

    assert "registration_session_pairing_id_ = pairing_client_.pairing_id();" in discovery
    assert (
        "registration_session_pairing_id_ != pairing_client_.pairing_id()"
        in discovery
    )

    assert "RSSI" not in discovery
    assert "rssi" not in discovery
    assert "std::sort(" not in discovery

def test_r5_retry_rearms_discovery_without_pairing_identity_mutation() -> None:
    portal = text(CORE / "n3w_registration_portal.cpp")
    component = text(CORE / "n3w_simple_product_component.cpp")

    retry = function_block(
        portal,
        "esp_err_t RegistrationPortal::handle_retry_",
        "esp_err_t RegistrationPortal::register_page_handler_",
    )
    assert "RegistrationPortalStage::DISCOVERING" in retry
    assert "scan_trigger_pending_.store(true" in retry

    combined = retry + "\n" + function_block(
        component,
        "void SimpleProductComponent::advance_registration_discovery_()",
        "void SimpleProductComponent::advance_registration_bootstrap_()",
    )
    assert "renew_pairing" not in combined
    assert "set_pairing_id" not in combined
    assert "registration_session_pairing_id_ = pairing_client_.pairing_id();" in combined
    assert "setup_secret" not in combined.lower()


def test_r5_discovery_scope_remains_transport_free_after_r6() -> None:
    discovery = text(CORE / "n3w_registration_discovery.cpp")
    discovery_h = text(CORE / "n3w_registration_discovery.h")
    portal = text(CORE / "n3w_registration_portal.cpp")
    component = text(CORE / "n3w_simple_product_component.cpp")

    r5_scope = "\n".join((discovery, discovery_h, portal))
    for forbidden in (
        "esp_tls",
        "gh.registration.confirm/1",
        "setup_secret_base64url",
        "derive_bootstrap_key",
        "pair_with_(",
    ):
        assert forbidden not in r5_scope

    discovery_block = function_block(
        component,
        "void SimpleProductComponent::advance_registration_discovery_()",
        "void SimpleProductComponent::advance_registration_bootstrap_()",
    )
    assert "http_post_(" not in discovery_block
    assert "post_json(" not in discovery_block
    assert "pairing_client_.run_once(" not in discovery_block


def test_r5_preserves_r4_pending_ack_recovery_path() -> None:
    component = text(CORE / "n3w_simple_product_component.cpp")

    loop = function_block(
        component,
        "void SimpleProductComponent::loop()",
        "TelemetrySubmitDisposition SimpleProductComponent::submit_telemetry_json",
    )
    assert "if (pairing_ack_pending_)" in loop
    assert "advance_pairing_();" in loop
    assert loop.index("if (pairing_ack_pending_)") < loop.index(
        "advance_registration_discovery_();"
    )

    pairing = function_block(
        component,
        "void SimpleProductComponent::advance_pairing_()",
        "void SimpleProductComponent::advance_recovery_()",
    )
    assert "pairing_client_.resume_pending_ack()" in pairing
