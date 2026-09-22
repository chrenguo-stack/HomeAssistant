from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = (
    ROOT
    / "tools/execution_packages/n3w/kf096/pr437_board_a_same_artifact_write/executor.py"
)

spec = importlib.util.spec_from_file_location("board_a_same_artifact_writer", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def synthetic_mac(last: str = "0a") -> str:
    octets = ["02", "00", "00", "00", "00", last]
    return ":".join(octets)


def synthetic_partition() -> bytes:
    return bytes(index % 251 for index in range(module.PARTITION_TABLE_SIZE))


def board_payload(port: str, hardware_hash: str) -> dict[str, object]:
    return {
        "hardware_id_sha256": hardware_hash,
        "port_sha256": module.sha256_bytes(port.encode("utf-8")),
        "chip": "ESP32-C6",
        "flash_size": "8MB",
        "secure_boot": False,
        "flash_encryption": False,
        "partition_table_offset": hex(module.PARTITION_TABLE_OFFSET),
        "partition_table_size": module.PARTITION_TABLE_SIZE,
        "partition_table_sha256": module.PARTITION_TABLE_SHA256,
    }


def preflight_payload(
    port: str,
    hardware_hash: str,
    created_at: dt.datetime,
) -> dict[str, object]:
    return {
        "schema": module.SCHEMA_PREFLIGHT,
        "status": "PASS",
        "created_at": created_at.isoformat(),
        "target_label": "BOARD_A",
        "operator_target_confirmation_required": True,
        "esptool_version": "5.1.0",
        "board": board_payload(port, hardware_hash),
        "artifact": module.artifact_binding_payload(),
        "persistent_mutation": False,
        "authorization_claimed": False,
        "authorization_consumed": False,
        "replay_permitted": False,
    }


def test_exact_board_b_physical_artifact_is_frozen() -> None:
    assert module.PRODUCT_SOURCE == "4270f24a92a87dd5239d781ebba624c2f34b7fc2"
    assert module.PRODUCT_TREE == "a2f445bf2ea60ba9994a7a467f6492975d399c4f"
    assert module.WORKFLOW_RUN_ID == 35553142523
    assert module.ARTIFACT_ID == 10619047221
    assert module.ARTIFACT_ZIP_SHA256 == (
        "33895089cf861a211f3f5569cd8f3e6729b0938787cda0d4a30d498ce0264895"
    )
    assert module.APPLICATION_SHA256 == (
        "b7836f041e8b0f68809980d516a9d9cd5c4a94f862f7d3a27515ae85d55d6843"
    )
    assert module.OTADATA_SHA256 == (
        "7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f"
    )
    assert module.TARGET_CONFIG.endswith("n3w_phase4_physical/generic.yml")


def test_probe_accepts_fresh_silicon_identity_without_prior_board_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = synthetic_mac()
    expected_hash = module.public_identity_sha256(raw)

    def fake_run(args: list[str], *, port: str | None = None) -> str:
        if args[-1] == "get-security-info":
            return (
                "Chip is ESP32-C6 (QFN40)\nMAC: "
                + raw
                + "\nSecure Boot: Disabled\nFlash Encryption: Disabled\n"
            )
        if args[-1] == "flash-id":
            return "Detected flash size: 8 MB\n"
        raise AssertionError(args)

    monkeypatch.setattr(module, "run_capture", fake_run)
    monkeypatch.setattr(
        module,
        "read_flash_hash",
        lambda *args, **kwargs: module.PARTITION_TABLE_SHA256,
    )

    board = module.probe_board("/dev/cu.synthetic")
    assert board["hardware_id_sha256"] == expected_hash


def test_write_command_is_only_otadata_plus_application() -> None:
    cmd = module.build_write_command(
        "/dev/cu.synthetic",
        Path("/tmp/ota.bin"),
        Path("/tmp/app.bin"),
    )
    write = cmd.index("write-flash")
    assert cmd[write + 1 :] == [
        hex(module.OTADATA_OFFSET),
        "/tmp/ota.bin",
        hex(module.APPLICATION_OFFSET),
        "/tmp/app.bin",
    ]
    assert "erase-flash" not in cmd
    assert hex(module.PARTITION_TABLE_OFFSET) not in cmd[write + 1 :]


def test_write_requires_explicit_board_a_confirmation() -> None:
    args = argparse.Namespace(
        confirm=module.WRITE_CONFIRMATION,
        target_confirm="WRONG",
        confirm_hardware_id_sha256="0" * 64,
        preflight="/tmp/preflight.json",
        port="/dev/cu.synthetic",
        artifact_zip="/tmp/artifact.zip",
        output="/tmp/write.json",
    )
    with pytest.raises(module.StopExecution, match="target confirmation"):
        module.run_write(args)


def test_preflight_is_bound_to_port_and_single_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = synthetic_mac("0b")
    hardware_hash = module.public_identity_sha256(raw)
    now = dt.datetime(2026, 9, 22, 3, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(module, "utc_now", lambda: now)

    port = "/dev/cu.synthetic-a"
    closure = tmp_path / "preflight.json"
    closure.write_text(
        json.dumps(preflight_payload(port, hardware_hash, now)),
        encoding="utf-8",
    )

    loaded = module.load_preflight(closure, port)
    assert loaded["board"]["hardware_id_sha256"] == hardware_hash

    with pytest.raises(module.StopExecution, match="port locator"):
        module.load_preflight(closure, "/dev/cu.synthetic-other")

    claimed, payload = module.claim_preflight(closure, port)
    assert claimed.is_file()
    assert not closure.exists()
    assert payload["authorization_claimed"] is True
    assert payload["authorization_consumed"] is True
    assert payload["replay_permitted"] is False


def test_stale_preflight_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = synthetic_mac("0c")
    hardware_hash = module.public_identity_sha256(raw)
    now = dt.datetime(2026, 9, 22, 3, 0, tzinfo=dt.timezone.utc)
    monkeypatch.setattr(module, "utc_now", lambda: now)

    path = tmp_path / "preflight.json"
    path.write_text(
        json.dumps(
            preflight_payload(
                "/dev/cu.synthetic-a",
                hardware_hash,
                now - dt.timedelta(seconds=module.PREFLIGHT_MAX_AGE_SECONDS + 1),
            )
        ),
        encoding="utf-8",
    )
    with pytest.raises(module.StopExecution, match="stale"):
        module.load_preflight(path, "/dev/cu.synthetic-a")


def test_postboot_otadata_is_not_used_as_exact_equality_oracle() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert 'post-write OTA-data readback mismatch' not in source
    assert 'otadata_postboot_byte_equality_oracle": False' in source
    assert 'OTADATA_POSTBOOT_BYTE_EQUALITY_ORACLE=false' in source
    assert 'APPLICATION_POSTWRITE_READBACK=PASS' in source
    assert 'PARTITION_TABLE_POSTWRITE_READBACK=PASS' in source


def test_preflight_does_not_require_existing_application_hash() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "prewrite_application_window_sha256" not in source
    assert '"application_window_sha256"' not in source
    assert '"prewrite"' not in source
