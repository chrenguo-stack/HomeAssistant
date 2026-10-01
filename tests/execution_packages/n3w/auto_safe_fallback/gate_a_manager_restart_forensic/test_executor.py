from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "tools/execution_packages/n3w/auto_safe_fallback/gate_a_manager_restart_forensic/executor.py"

spec = importlib.util.spec_from_file_location("gate_a_manager_restart_forensic", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_remote_forensic_is_readonly() -> None:
    source = module.REMOTE_FORENSIC
    required = (
        '"docker", "inspect"',
        '"docker", "events"',
        '"/proc/uptime"',
    )
    for token in required:
        assert token in source
    forbidden = (
        '"docker", "run"',
        '"docker", "rm"',
        '"docker", "restart"',
        '"docker", "stop"',
        '"docker", "kill"',
        '"ip", "addr", "add"',
        '"ip", "addr", "del"',
        '"systemctl"',
        '"chmod"',
        '"chown"',
    )
    for token in forbidden:
        assert token not in source


def test_forensic_reports_restart_evidence() -> None:
    source = module.REMOTE_FORENSIC
    for token in (
        '"manager_restart_count"',
        '"manager_started_at"',
        '"manager_finished_at"',
        '"manager_oom_killed"',
        '"manager_current_exit_code"',
        '"manager_restart_policy"',
        '"manager_events_72h"',
        '"broker_restart_count"',
    ):
        assert token in source


def test_public_output_has_no_credentials_or_private_addresses() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    for token in (
        "mqtt_username",
        "mqtt_password",
        "mqtt_client_id",
        "restore_host",
        "live_alias",
        "blackhole_ip",
        "server.key",
        "profile.json",
    ):
        assert token not in source


def test_no_board_transport() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8").lower()
    for token in ("esptool", "write-flash", "/dev/cu.", "/dev/tty"):
        assert token not in source
