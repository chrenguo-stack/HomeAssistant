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

    artifacts = document["private_local_artifacts"]
    assert len(artifacts) == 6
    assert all(SHA256.fullmatch(item["sha256"]) for item in artifacts)
    assert all(item["identity_binding"] == "QUARANTINED_UNBOUND" for item in artifacts)
    assert all("board-a" not in item["id"] for item in artifacts)
    assert all("board-b" not in item["id"] for item in artifacts)
    assert all("board-c" not in item["id"] for item in artifacts)
