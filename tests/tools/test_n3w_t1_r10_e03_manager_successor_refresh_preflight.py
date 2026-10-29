from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pytest

TOOL_PATH = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "n3w_t1_r10_e03_manager_successor_refresh_preflight.py"
)
SPEC = importlib.util.spec_from_file_location("r10_e03_preflight", TOOL_PATH)
assert SPEC is not None and SPEC.loader is not None
tool = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = tool
SPEC.loader.exec_module(tool)

SOURCE_HEAD = "f8876fd87165df731d792690a8288867c3eeef55"
MANAGER_IMAGE_ID = (
    "sha256:089153fa4bbc823a1357427083f23ef96933a119c6ae150c143b62d7b40859e4"
)
MANAGER_TAR_SHA256 = (
    "d129a33ea628d8bdd1361e0b1bf727175515b4a2afc1851e6ac14ec510895fb5"
)
ARTIFACT_DIGEST = (
    "c94568f740b911eee0f4238207249b1e98f84748c17a902938ccc35293e4b183"
)
PAIRING_HASH = tool.EXPECTED_FAILED_PAIRING_ID_SHA256
HARDWARE_HASH = tool.EXPECTED_FAILED_HARDWARE_ID_SHA256


def _args() -> argparse.Namespace:
    return argparse.Namespace(
        expected_current_manager_image=tool.EXPECTED_CURRENT_MANAGER_IMAGE,
        expected_registration_count=1,
        expected_attempt_count=1,
        expected_unresolved_count=1,
        target_source_head=SOURCE_HEAD,
        target_manager_image_id=MANAGER_IMAGE_ID,
        target_manager_tar_sha256=MANAGER_TAR_SHA256,
        artifact_id=12900601779,
        artifact_digest_sha256=ARTIFACT_DIGEST,
    )


def _inspect(service: str) -> dict[str, object]:
    container_id = f"{service}-container-id"
    image_ref = {
        "manager": tool.EXPECTED_CURRENT_MANAGER_IMAGE,
        "broker": "local/n3w-mosquitto:2.1.2-3184566d",
        "homeassistant": "local/n3w-homeassistant:2026.10.0-0c73235a",
    }[service]
    network_mode = "host" if service in {"manager", "homeassistant"} else "n3wfc4-private"
    return {
        "Id": container_id,
        "Image": "sha256:" + service[0] * 64,
        "RestartCount": 0,
        "State": {
            "Running": True,
            "StartedAt": "2026-10-29T00:00:00Z",
        },
        "Config": {
            "Image": image_ref,
            "Labels": {
                "com.docker.compose.project": tool.PROJECT,
                "com.docker.compose.service": service,
            },
        },
        "HostConfig": {
            "NetworkMode": network_mode,
        },
    }


def _ledger(*, expired: bool = True, unresolved: int = 1) -> dict[str, object]:
    return {
        "registration_count": 1,
        "attempt_count": 1,
        "unresolved_count": unresolved,
        "attempts": [
            {
                "pairing_id_sha256": PAIRING_HASH,
                "hardware_id_sha256": HARDWARE_HASH,
                "opened_at": "2026-10-29T00:00:00Z",
                "expires_at": "2026-10-29T00:30:00Z",
                "state": "ACTIVE",
                "phase": "BOOTSTRAP_ACCEPTED",
                "cleanup_state": "NONE",
                "node_id_present": False,
                "terminal_at_present": False,
                "terminal_reason": None,
                "expired_by_clock": expired,
                "registration_match_count": 0,
            }
        ],
    }


class FakeRunner:
    def __init__(
        self,
        *,
        tcp_47112: int = 0,
        ledger: dict[str, object] | None = None,
        manager_restart_count: int = 0,
    ) -> None:
        self.tcp_47112 = tcp_47112
        self.ledger = ledger or _ledger()
        self.manager_restart_count = manager_restart_count
        self.calls: list[tuple[str, ...]] = []

    def run(self, argv, *, timeout=30):
        args = tuple(argv)
        self.calls.append(args)

        if args[:2] == ("systemctl", "is-active"):
            return tool.CommandResult("active\n", "", 0)
        if args[:2] == ("systemctl", "is-enabled"):
            return tool.CommandResult("enabled\n", "", 0)

        if args[:3] == ("docker", "ps", "-q"):
            service_filter = next(
                value
                for value in args
                if value.startswith("label=com.docker.compose.service=")
            )
            service = service_filter.rsplit("=", 1)[1]
            return tool.CommandResult(f"{service}-container-id\n", "", 0)

        if args[:2] == ("docker", "inspect"):
            service = args[2].removesuffix("-container-id")
            document = _inspect(service)
            if service == "manager":
                document["RestartCount"] = self.manager_restart_count
            return tool.CommandResult(json.dumps([document]), "", 0)

        if args[:2] == ("ss", "-H"):
            port = int(args[-1].removeprefix(":"))
            count = {
                8883: 1,
                47110: 1,
                47111: 1,
                47112: self.tcp_47112,
            }[port]
            return tool.CommandResult("listener\n" * count, "", 0)

        if args[:3] == ("docker", "exec", "manager-container-id"):
            return tool.CommandResult(json.dumps(self.ledger), "", 0)

        raise AssertionError(f"unexpected command: {args}")


def test_preflight_passes_exact_failed_attempt_and_target_binding() -> None:
    runner = FakeRunner()
    report = tool.preflight(_args(), runner)

    assert report["status"] == "PASS"
    assert report["mutation"] is False
    assert report["authorization_claimed"] is False
    assert report["authorization_consumed"] is False
    assert report["t1_mutation"] is False
    assert report["board_access"] is False
    assert report["ledger"]["registration_count"] == 1
    assert report["ledger"]["attempt_count"] == 1
    assert report["ledger"]["unresolved_count"] == 1
    assert report["ledger"]["failed_attempt"]["pairing_id_sha256"] == PAIRING_HASH
    assert report["ledger"]["failed_attempt"]["hardware_id_sha256"] == HARDWARE_HASH
    assert report["target"]["source_head"] == SOURCE_HEAD
    assert report["target"]["manager_image"] == tool.EXPECTED_TARGET_MANAGER_IMAGE
    assert report["target"]["manager_image_id"] == MANAGER_IMAGE_ID
    assert report["target"]["manager_tar_sha256"] == MANAGER_TAR_SHA256
    assert report["target"]["artifact_id"] == 12900601779
    assert report["target"]["artifact_digest_sha256"] == ARTIFACT_DIGEST
    assert report["refresh_contract"]["manager_only_compose_recreate_forbidden"] is True
    assert report["refresh_contract"]["manager_and_homeassistant_restart_together"] is True

    flattened = "\n".join(" ".join(call) for call in runner.calls)
    assert "systemctl stop" not in flattened
    assert "systemctl start" not in flattened
    assert "systemctl restart" not in flattened
    assert "docker load" not in flattened
    assert "docker compose" not in flattened


def test_preflight_rejects_open_47112() -> None:
    with pytest.raises(tool.PreflightError, match="pairing_47112_must_be_closed"):
        tool.preflight(_args(), FakeRunner(tcp_47112=1))


def test_preflight_rejects_nonexpired_active_attempt() -> None:
    with pytest.raises(tool.PreflightError, match="failed_attempt_state_drift"):
        tool.preflight(_args(), FakeRunner(ledger=_ledger(expired=False)))


def test_preflight_rejects_unresolved_count_drift() -> None:
    with pytest.raises(tool.PreflightError, match="unresolved_count_drift"):
        tool.preflight(_args(), FakeRunner(ledger=_ledger(unresolved=0)))


def test_preflight_rejects_manager_restart_drift() -> None:
    with pytest.raises(tool.PreflightError, match="manager_restart_count_drift"):
        tool.preflight(_args(), FakeRunner(manager_restart_count=1))


def test_preflight_rejects_failed_attempt_pairing_identity_drift() -> None:
    ledger = _ledger()
    ledger["attempts"][0]["pairing_id_sha256"] = "1" * 64
    with pytest.raises(
        tool.PreflightError,
        match="failed_attempt_pairing_identity_drift",
    ):
        tool.preflight(_args(), FakeRunner(ledger=ledger))


def test_preflight_rejects_failed_attempt_hardware_identity_drift() -> None:
    ledger = _ledger()
    ledger["attempts"][0]["hardware_id_sha256"] = "2" * 64
    with pytest.raises(
        tool.PreflightError,
        match="failed_attempt_hardware_identity_drift",
    ):
        tool.preflight(_args(), FakeRunner(ledger=ledger))


def test_preflight_rejects_successor_artifact_binding_drift() -> None:
    args = _args()
    args.artifact_id += 1
    with pytest.raises(tool.PreflightError, match="target_artifact_id_drift"):
        tool.preflight(args, FakeRunner())


def test_preflight_rejects_successor_source_binding_drift() -> None:
    args = _args()
    args.target_source_head = "0" * 40
    with pytest.raises(tool.PreflightError, match="target_source_head_drift"):
        tool.preflight(args, FakeRunner())


def test_ledger_probe_is_readonly_and_secret_safe() -> None:
    source = tool._LEDGER_PROBE
    assert "?mode=ro" in source
    assert "PRAGMA query_only=ON" in source
    assert "INSERT " not in source
    assert "UPDATE " not in source
    assert "DELETE " not in source
    assert '"pairing_id":' not in source
    assert "pairing_id_sha256" in source


def test_source_has_no_live_refresh_mutation_commands() -> None:
    source = TOOL_PATH.read_text(encoding="utf-8")
    forbidden = (
        "docker load",
        "--force-recreate",
        "systemctl\", \"stop",
        "systemctl\", \"start",
        "systemctl\", \"restart",
        "docker\", \"compose",
    )
    assert all(token not in source for token in forbidden)
