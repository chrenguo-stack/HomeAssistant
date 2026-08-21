from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / "docs"
    / "development"
    / "archive-manifests"
    / "n3w-fc4-archive-audit-20260820.json"
)
SHA256 = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
GIT_OBJECT_ID = re.compile(r"^[0-9a-f]{40}$")


def test_fc4_archive_manifest_is_public_safe_and_machine_checkable() -> None:
    document = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert document["schema"] == "gh.development-artifact-archive/1"
    assert document["public_raw_evidence_exposed"] is False
    assert document["secret_values_included"] is False
    authorization = document["live_authorization_history"]
    assert authorization["claimed"] is True
    assert authorization["consumed"] is True
    assert authorization["status"] == "CONSUMED_FAILED"
    assert authorization["replay_permitted"] is False

    source = document["authoritative_source"]
    assert GIT_OBJECT_ID.fullmatch(source["main_head"])
    assert GIT_OBJECT_ID.fullmatch(source["main_tree"])
    assert source["ci_failure"] == 0

    runtime = document["p2b3d_runtime_binding"]
    assert runtime["terminal"] == "CLOSED_HEALTHY"
    assert runtime["health"]["pairing_http_schema"] == ("gh.pair.simple-health/1")
    assert runtime["health"]["kf036_recovery_executed"] is False
    assert runtime["health"]["board_access"] is False

    for evidence in runtime["private_evidence"]:
        assert SHA256.fullmatch(evidence["sha256"])
        assert evidence["secret_values_included_in_public_binding"] is False

    failure = document["kf036_consumed_failure"]
    assert failure["status"] == "CONSUMED_FAILED"
    assert failure["replay_permitted"] is False
    assert failure["root_cause"] == "docker_run_stdin_not_attached"
    assert failure["executor_observation"]["docker_interactive_flag_present"] is False
    assert failure["executor_observation"]["result_size"] == 0
    assert failure["post_failure_state"]["registration_database_mutated"] is False
    assert failure["post_failure_state"]["credential_database_mutated"] is False
    assert failure["post_failure_state"]["manager_health"] == "PASS"
    assert failure["closure_evidence_present"] is False

    binding = failure["fc4_database_binding"]
    assert binding["registration_container_path"] == (
        "/var/lib/greenhouse-manager/manager/registration.sqlite3"
    )
    assert binding["credential_container_path"] == (
        "/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3"
    )
    assert binding["generic_registration_default_applies"] is False

    successor = failure["successor_contract"]
    assert successor["new_authorization_required"] is True
    assert successor["docker_stdin_transport"] == "--interactive"
    assert successor["python_program_source"] == "stdin"
    assert successor["nonempty_result_required_before_json_parse"] is True
    assert successor["live_container_inspection_count_minimum"] >= 2
    assert (
        successor["registration_container_path"]
        == (binding["registration_container_path"])
    )
    assert (
        successor["credential_container_path"] == binding["credential_container_path"]
    )

    for evidence in failure["private_evidence"]:
        assert SHA256.fullmatch(evidence["sha256"])
        assert evidence["mode"] == "0600"
        assert evidence["secret_values_included_in_public_binding"] is False

    recovery = document["kf036_successor_partial_success"]
    assert recovery["status"] == (
        "CONSUMED_PARTIAL_SUCCESS_STOPPED_AT_FALSE_TOMBSTONE_REASON_ORACLE"
    )
    assert recovery["replay_permitted"] is False
    assert recovery["product_recovery_succeeded"] is True
    assert recovery["executor_oracle_succeeded"] is False
    assert recovery["post_recovery_state"]["current_registration_count"] == 0
    assert recovery["post_recovery_state"]["replay_tombstone"] == {
        "state": "expired",
        "reason": "expired",
    }
    assert recovery["post_recovery_state"]["recovery_event"] == {
        "event": "expired_first_registration_abandoned",
        "reason": "expired_first_pairing_recovery",
    }
    assert recovery["closure_evidence_present"] is False
    assert recovery["continuation_contract"]["rerun_recovery_cli"] is False
    for evidence in recovery["private_evidence"]:
        assert SHA256.fullmatch(evidence["sha256"])
        assert evidence["mode"] == "0600"
        assert evidence["secret_values_included_in_public_binding"] is False

    closure = document["kf041_closure"]
    assert closure["status"] == "CLOSED_VALID_RECOVERY_STATE"
    assert closure["claimed"] is True
    assert closure["consumed"] is True
    assert closure["replay_permitted"] is False
    assert closure["recovery_replayed"] is False
    assert closure["registration_database_mutated"] is False
    assert closure["credential_database_mutated"] is False
    assert closure["container_mutated"] is False
    assert closure["board_access"] is False
    for evidence in closure["private_evidence"]:
        assert SHA256.fullmatch(evidence["sha256"])
        assert evidence["mode"] == "0600"
        assert evidence["secret_values_included_in_public_binding"] is False

    archive_recovery = document["prephysical_archive_recovery_20260821"]
    assert archive_recovery["pending_physical_authorization_claimed"] is False
    assert archive_recovery["board_access"] is False
    assert archive_recovery["serial_access"] is False
    assert archive_recovery["flash_mutated"] is False
    assert archive_recovery["setup_secret_handoff_output_present"] is False
    assert archive_recovery["unarchived_critical_result_count"] == 0
    for artifact in archive_recovery["artifacts"]:
        assert SHA256.fullmatch(artifact["sha256"])
        assert artifact["mode"] == "0600"
        assert artifact["secret_values_included_in_public_binding"] is False

    physical = document["f45c_post_kf036_physical_partial_success"]
    assert physical["status"] == (
        "CONSUMED_PARTIAL_SUCCESS_STOPPED_AT_POST_ERASE_ALL_FF_ORACLE"
    )
    assert physical["claimed"] is True
    assert physical["consumed"] is True
    assert physical["replay_permitted"] is False
    assert physical["nvs_operation"]["scoped_erase_succeeded"] is True
    assert physical["nvs_operation"]["application_flash_rewritten"] is False
    assert physical["new_pairing_observation"][
        "different_from_expired_pairing_id"
    ] is True
    assert physical["new_pairing_observation"]["secret_value_exposed"] is False
    assert physical["successor_contract"]["repeat_nvs_erase"] is False
    for evidence in physical["private_evidence"]:
        assert SHA256.fullmatch(evidence["sha256"])
        assert evidence["mode"] == "0600"
        assert evidence["secret_values_included_in_public_binding"] is False

    handoff = document["f45c_kf042_successor_handoff_capture"]
    assert handoff["status"] == (
        "CONSUMED_PARTIAL_SUCCESS_WAITING_FOR_OPERATOR_WIFI_CONFIGURATION"
    )
    assert handoff["claimed"] is True
    assert handoff["consumed"] is True
    assert handoff["replay_permitted"] is False
    assert handoff["adopted_scoped_nvs_erase"] is True
    assert handoff["repeated_nvs_erase"] is False
    assert handoff["flash_mutated"] is False
    assert handoff["secret_value_exposed"] is False
    assert handoff["continuation_gate"]["repeat_handoff_capture"] is False
    for evidence in handoff["private_evidence"]:
        assert SHA256.fullmatch(evidence["sha256"])
        assert evidence["mode"] == "0600"
        assert evidence["secret_values_included_in_public_binding"] is False

    e2e = document["f45c_final_product_e2e_closure"]
    assert e2e["status"] == "PASS_F45C_FINAL_PRODUCT_E2E"
    assert e2e["pairing_session_state"] == "approved"
    assert e2e["credential_assignment_count"] == 1
    assert e2e["board_runtime"]["serial_pairing_qr_payload_count"] == 0
    assert e2e["manager_runtime"]["accepted_telemetry_count"] > 0
    assert e2e["manager_runtime"]["rejected_telemetry_count"] == 0
    assert e2e["homeassistant_runtime"]["device_registry_match_count"] == 1
    assert e2e["homeassistant_runtime"]["entity_registry_match_count"] >= 1
    assert e2e["secret_value_exposed"] is False
    assert e2e["other_board_authorization_implied"] is False
    for evidence in e2e["private_evidence"]:
        assert SHA256.fullmatch(evidence["sha256"])
        assert evidence["mode"] == "0600"
        assert evidence["secret_values_included_in_public_binding"] is False

    preclaim = document["f350_readonly_preclaim_and_kf043_guard"]
    assert preclaim["authorization_approved"] is True
    assert preclaim["authorization_claimed"] is False
    assert preclaim["authorization_consumed"] is False
    assert preclaim["base_mac"] == "98:a3:16:a9:f3:50"
    assert preclaim["application_verify_flash"] == "PASS"
    assert preclaim["private_handoff_file_present"] is False
    assert preclaim["secret_value_exposed"] is False
    assert preclaim["flash_mutated"] is False

    guard = preclaim["kf043"]
    assert guard["status"] == "GUARDED"
    assert guard["replacement_entry_point"] == (
        "greenhouse-manager-n3w-setup-secret-capture"
    )
    assert guard["private_parent_checked_before_serial_open"] is True
    assert guard["exclusive_mode_0600_output"] is True
    assert guard["identity_mismatch_fails_before_write"] is True
    assert guard["secret_safe_stdout"] is True
    assert guard["cli_call_chain_regression_present"] is True

    f350_capture = document["f350_bound_handoff_capture"]
    assert f350_capture["status"] == (
        "CONSUMED_PARTIAL_SUCCESS_WAITING_FOR_OPERATOR_WIFI_CONFIGURATION"
    )
    assert f350_capture["claimed"] is True
    assert f350_capture["consumed"] is True
    assert f350_capture["replay_permitted"] is False
    assert f350_capture["secret_value_exposed"] is False
    assert f350_capture["flash_mutated"] is False
    assert f350_capture["nvs_erased"] is False
    assert f350_capture["t1_mutated"] is False
    assert f350_capture["continuation_gate"]["repeat_handoff_capture"] is False
    assert f350_capture["continuation_gate"]["repeat_nvs_erase"] is False
    for evidence in f350_capture["private_evidence"]:
        assert SHA256.fullmatch(evidence["sha256"])
        assert evidence["mode"] == "0600"
        assert evidence["secret_values_included_in_public_binding"] is False

    expired_stop = document["f350_expired_pending_delivery_stop"]
    assert expired_stop["status"] == (
        "CONSUMED_PARTIAL_SUCCESS_STOPPED_AT_EXPIRED_PENDING_DELIVERY_GATE"
    )
    assert expired_stop["claimed"] is True
    assert expired_stop["consumed"] is True
    assert expired_stop["replay_permitted"] is False
    assert expired_stop["pairing_session_state"] == "expired"
    assert expired_stop["pending_ttl_seconds"] == 120
    assert expired_stop["exact_pending_observed_before_transfer"] is True
    assert expired_stop["exact_pending_at_atomic_delivery"] is False
    assert expired_stop["handoff_atomic_delivery"] is False
    assert expired_stop["t1_staging_removed"] is True
    assert expired_stop["t1_final_inbox_file_present"] is False
    assert expired_stop["local_private_handoff_preserved"] is True
    assert expired_stop["secret_value_exposed"] is False
    assert expired_stop["successor_contract"]["new_authorization_required"] is True
    assert expired_stop["successor_contract"]["repeat_current_handoff_delivery"] is False
    assert expired_stop["successor_contract"]["minimum_pending_ttl_margin_gate_required"] is True
    for evidence in expired_stop["private_evidence"]:
        assert SHA256.fullmatch(evidence["sha256"])
        assert evidence["mode"] == "0600"
        assert evidence["secret_values_included_in_public_binding"] is False

    ttl_guard = document["kf044_source_ttl_margin_gate"]
    assert ttl_guard["authorization_claimed"] is True
    assert ttl_guard["authorization_consumed"] is True
    assert ttl_guard["entry_point"] == (
        "greenhouse-manager-n3w-setup-secret-delivery-gate"
    )
    assert ttl_guard["phases"] == ["pretransfer", "predelivery"]
    assert ttl_guard["registration_database_read_only"] is True
    assert ttl_guard["current_registration_binding_required"] is True
    assert ttl_guard["exact_pairing_hash_binding_required"] is True
    assert ttl_guard["explicit_minimum_remaining_seconds_required"] is True
    assert ttl_guard["predelivery_uid_gid_binding_required"] is True
    assert ttl_guard["pairing_id_raw_exposed"] is False
    assert ttl_guard["setup_secret_exposed"] is False
    assert ttl_guard["full_manager_validation"] == {
        "passed": 1115,
        "skipped": 1,
        "subtests_passed": 5,
        "failure": 0,
        "restricted_sandbox_loopback_bind_false_failures": 4,
        "unrestricted_loopback_rerun": "PASS",
    }
    assert ttl_guard["source_guard_status"] == "PASS"
    assert ttl_guard["live_acceptance_status"] == "PENDING_NEW_AUTHORIZATION"
    assert ttl_guard["t1_access"] is False
    assert ttl_guard["board_access"] is False
    assert ttl_guard["private_handoff_delivered"] is False

    kf045 = document["kf044_live_successor_kf045_consumed_failure"]
    assert kf045["status"] == (
        "CONSUMED_FAILED_AT_ISOLATED_RECOVERY_REGISTRATION_DB_BINDING"
    )
    assert kf045["claimed"] is True
    assert kf045["consumed"] is True
    assert kf045["replay_permitted"] is False
    assert kf045["manager_stopped_machine_proof"] is True
    assert kf045["database_backups_created"] is True
    assert kf045["registration_database_mutated"] is False
    assert kf045["credential_database_mutated"] is False
    assert kf045["current_registration_count"] == 1
    assert kf045["pairing_session_state"] == "expired"
    assert kf045["recovery_event_count"] == 0
    assert kf045["manager_running"] is True
    assert kf045["manager_restart_count"] == 0
    assert kf045["postclaim_board_access"] is False
    assert kf045["nvs_erased"] is False
    assert kf045["flash_mutated"] is False
    assert kf045["successor_contract"]["new_authorization_required"] is True
    assert kf045["successor_contract"][
        "registration_db_argument_uses_host_source_path"
    ] is True
    assert kf045["successor_contract"]["nonempty_result_required_before_json_parse"] is True
    for evidence in kf045["private_evidence"]:
        assert SHA256.fullmatch(evidence["sha256"])
        assert evidence["mode"] == "0600"
        assert evidence["secret_values_included_in_public_binding"] is False

    kf045_source = document["kf045_source_host_path_recovery_executor"]
    assert kf045_source["authorization_claimed"] is True
    assert kf045_source["authorization_consumed"] is True
    assert kf045_source["entry_point"] == (
        "greenhouse-manager-n3w-expired-first-recovery"
    )
    assert kf045_source["host_source_registration_path_required"] is True
    assert kf045_source["host_source_credential_path_required"] is True
    assert kf045_source["manager_destination_paths_separate"] is True
    assert kf045_source["mode_0600_stopped_inspect_required"] is True
    assert kf045_source["real_inspect_adapter_integration_regression"] is True
    assert kf045_source[
        "destination_domain_mismatch_rejected_before_mutation"
    ] is True
    assert kf045_source["mismatch_database_hash_unchanged"] is True
    assert kf045_source["empty_result_rejected_before_json_parse"] is True
    assert kf045_source["pairing_id_raw_exposed"] is False
    assert kf045_source["secret_value_exposed"] is False
    assert kf045_source["full_manager_validation"]["passed"] == 1119
    assert kf045_source["full_manager_validation"]["failure"] == 0
    assert kf045_source["source_guard_status"] == "PASS"
    assert kf045_source["live_acceptance_status"] == "PENDING_NEW_AUTHORIZATION"
    assert kf045_source["t1_access"] is False
    assert kf045_source["board_access"] is False
    assert kf045_source["recovery_executed_live"] is False

    live_recovery = document["kf045_live_recovery_closure"]
    assert live_recovery["status"] == (
        "CONSUMED_PARTIAL_SUCCESS_RECOVERY_CLOSED_BOARD_NOT_STARTED"
    )
    assert live_recovery["claimed"] is True
    assert live_recovery["consumed"] is True
    assert live_recovery["replay_permitted"] is False
    assert live_recovery["recovery_executor_result"] == "PASS"
    assert live_recovery["host_source_database_paths_verified"] is True
    assert live_recovery["raw_recovery_result_nonempty"] is True
    assert live_recovery["current_registration_count"] == 0
    assert live_recovery["replay_tombstone_state"] == "expired"
    assert live_recovery["recovery_event"] == (
        "expired_first_registration_abandoned"
    )
    assert live_recovery["credential_database_mutated"] is False
    assert live_recovery["manager_running"] is True
    assert live_recovery["manager_restart_count"] == 0
    assert live_recovery["readonly_outer_oracle"] == "PASS"
    assert live_recovery["recovery_replayed"] is False
    assert live_recovery["board_access_after_recovery"] is False
    assert live_recovery["nvs_erased"] is False
    assert live_recovery["flash_mutated"] is False
    assert live_recovery["continuation_gate"]["rerun_recovery"] is False
    assert live_recovery["continuation_gate"]["ttl_gated_delivery_required"] is True
    for evidence in live_recovery["private_evidence"]:
        assert SHA256.fullmatch(evidence["sha256"])
        assert evidence["mode"] == "0600"
        assert evidence["secret_values_included_in_public_binding"] is False

    artifacts = document["private_local_artifacts"]
    assert len(artifacts) == 6
    assert all(SHA256.fullmatch(item["sha256"]) for item in artifacts)
    assert all(item["identity_binding"] == "QUARANTINED_UNBOUND" for item in artifacts)
    assert all("board-a" not in item["id"] for item in artifacts)
    assert all("board-b" not in item["id"] for item in artifacts)
    assert all("board-c" not in item["id"] for item in artifacts)
