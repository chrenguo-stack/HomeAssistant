from __future__ import annotations

import json
import stat
import subprocess
from pathlib import Path

import pytest

from greenhouse_manager.node_mqtt_board_lab import (
    CONFIRMATION,
    ESPHOME_SECRETS_NAME,
    MANIFEST_NAME,
    MATRIX_NAME,
    PASSWORD_NAME,
    REQUIRED_CASE_IDS,
    SECRETS_NAME,
    NodeMqttBoardLabError,
    _control_topic,
    check_serial_log,
    create_board_lab,
    init_fault_matrix,
    plan_board_lab,
    summarize_fault_matrix,
)


def _fake_runner(
    command: list[str] | tuple[str, ...],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = list(command)
    if "mosquitto_passwd" in command:
        mount_index = command.index("-v") + 1
        workspace = Path(command[mount_index].split(":", 1)[0])
        password_path = workspace / PASSWORD_NAME
        rows = []
        for line in password_path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            username, _ = line.split(":", 1)
            rows.append(f"{username}:$7$101$redacted-hash")
        password_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return subprocess.CompletedProcess(command, 0, "", "")


def _fake_waiter(host: str, port: int, timeout_s: float) -> None:
    assert host in {"127.0.0.1", "192.0.2.10"}
    assert port == 18883
    assert timeout_s == 20.0


def _create(tmp_path: Path) -> Path:
    workspace = tmp_path / "board-lab"
    report = create_board_lab(
        workspace,
        confirmation=CONFIRMATION,
        bind_host="127.0.0.1",
        runner=_fake_runner,
        waiter=_fake_waiter,
    )
    assert report["status"] == "node_mqtt_board_lab_created"
    assert report["secret_values_included"] is False
    assert report["production_endpoint_used"] is False
    return workspace


def test_plan_rejects_global_or_unspecified_bind_hosts(tmp_path: Path) -> None:
    with pytest.raises(NodeMqttBoardLabError, match="globally routable"):
        plan_board_lab(tmp_path / "x", bind_host="8.8.8.8")
    with pytest.raises(NodeMqttBoardLabError, match="unspecified"):
        plan_board_lab(tmp_path / "x", bind_host="0.0.0.0")
    report = plan_board_lab(tmp_path / "x", bind_host="192.0.2.10")
    assert report["bind_host_class"] == "non_global"
    assert report["ready_for_live_apply"] is False


def test_create_requires_confirmation_and_writes_private_nonproduction_files(tmp_path: Path) -> None:
    with pytest.raises(NodeMqttBoardLabError, match="confirmation mismatch"):
        create_board_lab(
            tmp_path / "rejected",
            confirmation="wrong",
            runner=_fake_runner,
            waiter=_fake_waiter,
        )

    workspace = _create(tmp_path)
    assert workspace.stat().st_mode & 0o777 == 0o700
    for name in (MANIFEST_NAME, SECRETS_NAME, ESPHOME_SECRETS_NAME, PASSWORD_NAME):
        assert (workspace / name).stat().st_mode & 0o777 == 0o600

    private_document = json.loads((workspace / SECRETS_NAME).read_text(encoding="utf-8"))
    manifest = (workspace / MANIFEST_NAME).read_text(encoding="utf-8")
    assert private_document["candidate_password"] not in manifest
    assert private_document["observer_password"] not in manifest
    password_file = (workspace / PASSWORD_NAME).read_text(encoding="utf-8")
    assert private_document["candidate_password"] not in password_file
    assert "REPLACE_IN_PRIVATE_WORKSPACE" in (workspace / ESPHOME_SECRETS_NAME).read_text(encoding="utf-8")


def test_serial_log_check_fails_closed_on_raw_secret(tmp_path: Path) -> None:
    workspace = _create(tmp_path)
    secrets_document = json.loads((workspace / SECRETS_NAME).read_text(encoding="utf-8"))
    clean = tmp_path / "clean.log"
    manifest = json.loads((workspace / MANIFEST_NAME).read_text(encoding="utf-8"))
    clean.write_text(
        "profile=anonymous phase=legacy_anonymous "
        f"candidate_secret_fingerprint={manifest['candidate_password_fingerprint']}\n",
        encoding="utf-8",
    )
    report = check_serial_log(workspace, log_path=clean)
    assert report["secret_match_count"] == 0

    leaked = tmp_path / "leaked.log"
    leaked.write_text(f"password={secrets_document['candidate_password']}\n", encoding="utf-8")
    with pytest.raises(NodeMqttBoardLabError, match="raw secret"):
        check_serial_log(workspace, log_path=leaked)


def test_control_topics_are_fixed_to_nonproduction_client_ids() -> None:
    assert _control_topic("activate") == ("lab/control/lab-board-anon/activate", "activate")
    assert _control_topic("commit") == ("lab/control/lab-board/commit", "commit")
    assert _control_topic("hold-reboot-anonymous") == (
        "lab/control/lab-board-anon/reboot-hold",
        "hold",
    )
    assert _control_topic("release-reboot-candidate") == (
        "lab/control/lab-board/reboot-hold",
        "release",
    )
    with pytest.raises(NodeMqttBoardLabError, match="unsupported"):
        _control_topic("production-migrate")


def test_fault_matrix_initializes_private_blocked_records(tmp_path: Path) -> None:
    matrix = tmp_path / MATRIX_NAME
    report = init_fault_matrix(matrix, run_id="boardlab-test-01")
    assert report["required_case_count"] == len(REQUIRED_CASE_IDS)
    assert matrix.stat().st_mode & 0o777 == stat.S_IRUSR | stat.S_IWUSR
    documents = [json.loads(line) for line in matrix.read_text(encoding="utf-8").splitlines()]
    assert len(documents) == len(REQUIRED_CASE_IDS)
    assert {document["case_id"] for document in documents} == set(REQUIRED_CASE_IDS)
    assert all(document["outcome"] == "blocked" for document in documents)

    summary = summarize_fault_matrix(matrix)
    assert summary["status"] == "node_mqtt_board_lab_fault_matrix_incomplete"
    assert summary["real_board_test_complete"] is False
    assert summary["failed_or_blocked_case_count"] == len(REQUIRED_CASE_IDS)


def test_fault_matrix_summary_requires_all_passed_evidence(tmp_path: Path) -> None:
    matrix = tmp_path / MATRIX_NAME
    init_fault_matrix(matrix, run_id="boardlab-test-02")
    documents = [json.loads(line) for line in matrix.read_text(encoding="utf-8").splitlines()]
    for index, document in enumerate(documents):
        document["outcome"] = "pass"
        document["operator_observed"] = True
        document["evidence_fingerprints"] = [f"deadbeef{index:08x}"]
        document["local_functions"] = {
            "lcd": "pass",
            "sensors": "pass",
            "rs485": "pass",
            "local_calculations": "pass",
            "low_power_protection": "pass",
        }
    matrix.write_text(
        "".join(json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n" for document in documents),
        encoding="utf-8",
    )
    summary = summarize_fault_matrix(matrix)
    assert summary["status"] == "node_mqtt_board_lab_fault_matrix_succeeded"
    assert summary["real_board_test_complete"] is True
    assert summary["passed_case_count"] == len(REQUIRED_CASE_IDS)


def test_fault_matrix_schema_rejects_unsafe_claim(tmp_path: Path) -> None:
    matrix = tmp_path / MATRIX_NAME
    init_fault_matrix(matrix, run_id="boardlab-test-03")
    documents = [json.loads(line) for line in matrix.read_text(encoding="utf-8").splitlines()]
    documents[0]["production_endpoint_used"] = True
    matrix.write_text(
        "".join(json.dumps(document, separators=(",", ":"), sort_keys=True) + "\n" for document in documents),
        encoding="utf-8",
    )
    with pytest.raises(NodeMqttBoardLabError, match="schema validation"):
        summarize_fault_matrix(matrix)
