from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (
    ROOT
    / ".github/workflows/n3w-r10-board-d-tls-pin-acceptance-artifact-ci.yml"
)
TARGET = (
    ROOT
    / "firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml"
)
TLS = (
    ROOT
    / "firmware/esphome_rc/components/greenhouse_n3w_core/"
    "n3w_registration_bootstrap_transport.cpp"
)
PORTAL_CPP = (
    ROOT
    / "firmware/esphome_rc/components/greenhouse_n3w_core/"
    "n3w_registration_portal.cpp"
)
PORTAL_H = (
    ROOT
    / "firmware/esphome_rc/components/greenhouse_n3w_core/"
    "n3w_registration_portal.h"
)
DISCOVERY_H = (
    ROOT
    / "firmware/esphome_rc/components/greenhouse_n3w_core/"
    "n3w_registration_discovery.h"
)


def test_acceptance_overlay_contains_only_intended_low_battery_bypass_marker() -> None:
    text = TARGET.read_text(encoding="utf-8")
    assert 'battery_low_threshold: "-1.00"' in text
    assert text.count('battery_low_threshold: "-1.00"') == 1


def test_repaired_tls_pin_only_contract_is_present() -> None:
    text = TLS.read_text(encoding="utf-8")
    assert (
        "mbedtls_ssl_conf_authmode(&config, MBEDTLS_SSL_VERIFY_OPTIONAL);"
        in text
    )
    assert (
        "mbedtls_ssl_conf_authmode(&config, MBEDTLS_SSL_VERIFY_NONE);"
        not in text
    )
    assert (
        "mbedtls_ssl_conf_authmode(&config, MBEDTLS_SSL_VERIFY_REQUIRED);"
        not in text
    )
    assert "return MBEDTLS_ERR_X509_FATAL_ERROR;" in text
    assert "!verify.leaf_seen || !verify.leaf_matched" in text


def test_repaired_ttl_and_confirmation_countdown_contract_is_present() -> None:
    discovery = DISCOVERY_H.read_text(encoding="utf-8")
    header = PORTAL_H.read_text(encoding="utf-8")
    portal = PORTAL_CPP.read_text(encoding="utf-8")

    assert "kRegistrationCandidateTtlSeconds = 60;" in discovery
    assert "kRegistrationUserConfirmMs = 60000ULL;" in header
    assert "found->expires_at_ms = now_ms + kRegistrationUserConfirmMs;" in portal
    assert "(remaining_ms - 1U) / 1000U" in portal
    assert '"开始注册（" + remaining + "s）"' in portal


def test_workflow_separates_source_ci_from_exact_artifact_production() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "produce_exact_artifact:" in text
    assert (
        "if: github.event_name == 'workflow_dispatch' "
        "&& inputs.produce_exact_artifact == true"
    ) in text
    assert "EXACT_ARTIFACT_PRODUCTION=false" in text
    assert "BOARD_WRITE=false" in text
    assert "T1_MUTATION=false" in text


def test_workflow_binds_new_product_acceptance_and_manager_authorities() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    required = (
        "ff750b3801a282af1667b5fa63481e2333e301b3",
        "ee6ee5e362628fa725d57fbdf50c6608e9032b17",
        "f99342f9639fa234d85c509ddf6cf41fef91d691",
        "6c53b4ef480f67d984cc9b3c8cfa0886d706dde4",
        "12877958163",
        "sha256:042a7d467287b8192edacea076c7f47b2037eef7ba3b83a966369ba0ff89d93d",
        "d31aa71635853922f816298ec0aa7aad83bb93da759c3732e3fd2b297364d406",
        "26aebbbaa783b66ca374337d701f38692774dbc4df432a93fe712759c9eaff96",
        "local/greenhouse-manager:fresh-ff750b3801a2",
        "EXACT_LEAF_SHA256_PIN",
    )
    for value in required:
        assert value in text


def test_workflow_does_not_reuse_old_acceptance_artifact_authority() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    forbidden = (
        "faf07839fcef221f9defb296eadcc7c090e12d4e",
        "40798244418",
        "12864962159",
        "b57a5af10c23344e8e03250857455898eb60640e3e18c62022af9c2b9ab7f6da",
        "9d3b7b9d6b277e06cb6eb7f3155e9c777025b0d5cdb6e40feec47d46435eafbd",
    )
    for value in forbidden:
        assert value not in text


def test_manifest_declares_nonproduction_and_no_live_authorization() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    required = (
        'echo "PHYSICAL_ACCEPTANCE_ONLY=true"',
        'echo "DEVELOPMENT_ONLY=true"',
        'echo "PRODUCTION_ELIGIBLE=false"',
        'echo "LOW_BATTERY_PROTECTION_BYPASSED=true"',
        'echo "BOARD_WRITE_AUTHORIZED=false"',
        'echo "T1_MUTATION_AUTHORIZED=false"',
    )
    for value in required:
        assert value in text


def test_redownload_verifier_rebinds_release_and_companion_manager() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "REDOWNLOAD_VERIFY=PASS" in text
    assert "REDOWNLOAD_MANIFEST_BINDING=PASS" in text
    assert '"COMPANION_MANAGER_ARTIFACT_ID": "12877958163"' in text
    assert '"REGISTRATION_CANDIDATE_TTL_SECONDS": "60"' in text
    assert '"FIRST_COUNTDOWN_DISPLAY_SECONDS": "59"' in text


def test_greenhouse_manager_ci_keeps_production_guard_but_scopes_acceptance_overlay() -> None:
    workflow = (
        ROOT / ".github/workflows/greenhouse-manager-ci.yml"
    ).read_text(encoding="utf-8")

    assert (
        "physical_acceptance_overlay: "
        "${{ steps.detect.outputs.physical_acceptance_overlay }}"
        in workflow
    )
    assert "grep -Fxc '+  battery_low_threshold: \"-1.00\"'" in workflow
    assert "grep -Fxc '  battery_low_threshold: \"-1.00\"'" in workflow
    assert '"$additions" == "1"' in workflow
    assert '"$deletions" == "0"' in workflow
    assert (
        "if: needs.scope.outputs.physical_acceptance_overlay != 'true'"
        in workflow
    )
    assert (
        "if: needs.scope.outputs.physical_acceptance_overlay == 'true'"
        in workflow
    )
    assert (
        "pytest -q tests/n3w_registration/"
        "test_scan_triggered_first_pairing_r10_phone_ui_contract.py"
        in workflow
    )
    assert (
        "-k 'not product_ui_source_does_not_embed_bench_low_battery_bypass'"
        in workflow
    )
    assert (
        "pytest -q tests/n3w_registration/"
        "test_r10_board_d_tls_pin_acceptance_artifact_source.py"
        in workflow
    )
