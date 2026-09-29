from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = (
    ROOT
    / "tools/execution_packages/n3w/auto_safe_fallback/gate_a_readonly_preflight/executor.py"
)

spec = importlib.util.spec_from_file_location("gate_a_readonly_preflight", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_ssh_transport_is_bounded_and_noninteractive() -> None:
    argv = module.ssh_argv("root@t1")
    assert "-n" in argv
    assert "BatchMode=yes" in argv
    assert "ConnectTimeout=10" in argv
    assert "ConnectionAttempts=1" in argv
    assert "ServerAliveInterval=5" in argv
    assert "ServerAliveCountMax=2" in argv


def test_remote_probe_contains_no_persistent_mutation_commands() -> None:
    source = module.REMOTE_PROBE
    forbidden = (
        "ip addr add",
        "ip addr del",
        "docker restart",
        "docker stop",
        "docker rm",
        "systemctl restart",
        "systemctl start",
        "write-flash",
        "erase-flash",
    )
    for token in forbidden:
        assert token not in source


def test_hardware_identity_hash_is_public_derivation() -> None:
    raw = ":".join(("02", "00", "00", "00", "00", "01"))
    expected = hashlib.sha256(b"ghw-c6-020000000001").hexdigest()
    assert module.hardware_id_sha256(raw) == expected


@pytest.mark.parametrize("value", ("", " root@t1", "root @t1", "<root@t1>", "placeholder"))
def test_ssh_target_validation_rejects_bad_values(value: str) -> None:
    with pytest.raises(module.StopExecution):
        module.validate_ssh_target(value)


def healthy_remote() -> dict[str, object]:
    return {
        "t1_root": True,
        "interface": "eth0",
        "current_ip": "192.0.2.10",
        "prefixlen": 24,
        "gateway": "192.0.2.1",
        "wildcard_8883": True,
        "broker_running": True,
        "manager_running": True,
        "manager_restart_count": 0,
        "live_alias": "192.0.2.250",
        "blackhole_ip": "192.0.2.249",
    }


def test_remote_result_accepts_healthy_preflight() -> None:
    result = module.parse_remote_result(__import__("json").dumps(healthy_remote()) + "\n")
    assert result["wildcard_8883"] is True
    assert result["broker_running"] is True
    assert result["live_alias"] != result["blackhole_ip"]


def test_remote_result_fails_closed_without_wildcard_8883() -> None:
    payload = healthy_remote()
    payload["wildcard_8883"] = False
    with pytest.raises(module.StopExecution):
        module.parse_remote_result(__import__("json").dumps(payload) + "\n")


def test_esptool_probe_base_has_no_flash_write_operation() -> None:
    argv = module.esptool_base("/dev/cu.synthetic")
    joined = " ".join(argv)
    assert "write-flash" not in joined
    assert "erase-flash" not in joined
    assert "--no-stub" in argv


def test_probe_board_checks_identity_security_flash_and_partition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy_mac = ":".join(("02", "00", "00", "00", "00", "01"))
    expected_identity = module.hardware_id_sha256(dummy_mac)
    monkeypatch.setattr(module, "EXPECTED_BOARD_B_HARDWARE_ID_SHA256", expected_identity)

    partition_bytes = b"P" * module.PARTITION_TABLE_SIZE
    partition_hash = hashlib.sha256(partition_bytes).hexdigest()
    monkeypatch.setattr(module, "EXPECTED_PARTITION_TABLE_SHA256", partition_hash)

    def fake_run(argv: list[str], timeout: int) -> str:
        assert timeout > 0
        joined = " ".join(argv)
        assert "write-flash" not in joined
        assert "erase-flash" not in joined
        if "get-security-info" in argv:
            return (
                "Chip type: ESP32-C6\n"
                f"MAC: {dummy_mac}\n"
                "Secure Boot: Disabled\n"
                "Flash Encryption: Disabled\n"
            )
        if "flash-id" in argv:
            return "Detected flash size: 8 MB\n"
        if "read-flash" in argv:
            Path(argv[-1]).write_bytes(partition_bytes)
            return "read ok\n"
        raise AssertionError(argv)

    monkeypatch.setattr(module, "run_capture", fake_run)
    result = module.probe_board("/dev/cu.synthetic")
    assert result["hardware_id_sha256"] == expected_identity
    assert result["partition_table_sha256"] == partition_hash
    assert result["flash_write"] is False
    assert result["persistent_mutation"] is False
