from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = ROOT / "tools/execution_packages/n3w/board_d/scoped_pairing_nvs_reset/executor.py"
spec = importlib.util.spec_from_file_location("board_d_scoped_pairing_nvs_reset", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_frozen_board_d_scope() -> None:
    assert module.EXPECTED_HARDWARE_ID_SHA256 == "3a76b39f066e09de0a285b81319eec20f29c8fd4136b61dc5a86ace01c1e1d55"
    assert module.EXPECTED_BOOTLOADER_SHA256 == "ae9656d4a6fca0f1149d443b8ced537efe3b68af8fe600ef9ad9b8c9c7b2ca46"
    assert module.EXPECTED_PARTITION_TABLE_SHA256 == "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"
    assert module.NVS_OFFSET == 0x790000
    assert module.NVS_SIZE == 0x70000
    assert module.ERASED_SHA256


def test_executor_forbids_broad_flash_mutation() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "erase-flash" not in source
    assert "write-flash" not in source
    assert "FULL_FLASH_ERASE=false" in source
    assert "APPLICATION_FLASH_REWRITE=false" in source
    assert '"--evidence-root"' not in source
    assert "AUTHORIZATION_STATE_RELATIVE" in source


def test_claim_precedes_exact_scoped_erase() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    claim = source.index("write_private_json(claim_path, claim)")
    durable_claim = source.index("fsync_directory(run_root)", claim)
    erase = source.index("erase_nvs_noreset(args.port)")
    erased_readback = source.index(
        "noreset_read(args.port, NVS_OFFSET, NVS_SIZE, erased, before_no_reset=True)"
    )
    oracle = source.index('raise StopExecution("preboot erased NVS oracle failed")')
    closed = source.index('"status": "CLOSED_PASS_PREBOOT"')
    assert claim < durable_claim < erase < erased_readback < oracle < closed


def test_erase_command_uses_exact_range_and_no_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run_capture(args: list[str], *, port: str | None = None) -> str:
        calls.append(args)
        return "PASS"

    monkeypatch.setattr(module.base, "run_capture", fake_run_capture)
    monkeypatch.setattr(module.base, "esptool_base", lambda: ["python3", "-m", "esptool"])

    module.erase_nvs_noreset("/dev/cu.usbmodem14101")

    assert len(calls) == 1
    command = calls[0]
    assert "--after" in command
    assert command[command.index("--after") + 1] == "no-reset"
    assert "erase-region" in command
    position = command.index("erase-region")
    assert command[position + 1 : position + 3] == ["0x790000", "0x70000"]
    assert "erase-flash" not in command
    assert "write-flash" not in command


def test_preboot_readback_does_not_start_application(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[list[str]] = []

    def fake_run_capture(args: list[str], *, port: str | None = None) -> str:
        calls.append(args)
        destination = Path(args[-1])
        size = int(args[-2], 0)
        destination.write_bytes(b"\xff" * size)
        return "PASS"

    monkeypatch.setattr(module.base, "run_capture", fake_run_capture)
    monkeypatch.setattr(module.base, "esptool_base", lambda: ["python3", "-m", "esptool"])

    output = tmp_path / "readback.bin"
    observed = module.noreset_read(
        "/dev/cu.usbmodem14101",
        module.NVS_OFFSET,
        module.NVS_SIZE,
        output,
        before_no_reset=True,
    )

    assert observed == module.ERASED_SHA256
    assert module.non_ff_count(output) == 0
    command = calls[0]
    assert command[command.index("--before") + 1] == "no-reset"
    assert command[command.index("--after") + 1] == "no-reset"
    assert "read-flash" in command


def test_preflight_rejects_reused_or_mismatched_board_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    preflight = tmp_path / "preflight.json"
    payload = {
        "schema": module.PREFLIGHT_SCHEMA,
        "status": "PASS",
        "created_at": "2026-10-25T15:06:08+00:00",
        "persistent_mutation": False,
        "flash_write": False,
        "nvs_write": False,
        "write_command_present": False,
        "write_authorization_granted": False,
        "replay_permitted": False,
        "artifact": module.base.artifact_binding_payload(),
        "board": {
            "hardware_id_sha256": "0" * 64,
            "bootloader_sha256": module.EXPECTED_BOOTLOADER_SHA256,
            "partition_table_sha256": module.EXPECTED_PARTITION_TABLE_SHA256,
            "bootloader_matches_release": True,
            "partition_table_matches_release": True,
            "port_sha256": module.hashlib.sha256(
                b"/dev/cu.usbmodem14101"
            ).hexdigest(),
        },
    }
    preflight.write_text(
        module.json.dumps(payload),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        module,
        "utc_now",
        lambda: module.dt.datetime(
            2026,
            10,
            25,
            15,
            7,
            tzinfo=module.dt.timezone.utc,
        ),
    )

    with pytest.raises(module.StopExecution, match="Board D identity"):
        module.require_preflight(preflight, "/dev/cu.usbmodem14101")


def test_authorization_claim_is_not_bypassable_by_alternate_work_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixed_state = tmp_path / "fixed-state"
    monkeypatch.setattr(module, "authorization_state_root", lambda: fixed_state)

    root = module.prepare_authorization_state_root()
    first = module.require_authorization_unclaimed(root)
    module.claim_authorization(first)

    unrelated_work = tmp_path / "alternate-work"
    unrelated_work.mkdir()
    assert unrelated_work != root

    with pytest.raises(module.StopExecution, match="authorization already claimed"):
        module.require_authorization_unclaimed(
            module.prepare_authorization_state_root()
        )


def test_cli_does_not_accept_caller_selected_evidence_root() -> None:
    parser = module.build_parser()
    actions = parser._subparsers._group_actions[0].choices["execute"]._actions
    destinations = {action.dest for action in actions}
    assert "evidence_root" not in destinations
    assert "authorization_id" in destinations
    assert "confirm" in destinations


def test_preflight_requires_exact_artifact_and_no_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    port = "/dev/cu.usbmodem14101"
    preflight = tmp_path / "preflight.json"
    artifact = module.base.artifact_binding_payload()
    payload = {
        "schema": module.PREFLIGHT_SCHEMA,
        "status": "PASS",
        "created_at": "2026-10-25T15:06:08+00:00",
        "persistent_mutation": False,
        "flash_write": False,
        "nvs_write": False,
        "write_command_present": False,
        "write_authorization_granted": False,
        "replay_permitted": False,
        "artifact": artifact,
        "board": {
            "hardware_id_sha256": module.EXPECTED_HARDWARE_ID_SHA256,
            "bootloader_sha256": module.EXPECTED_BOOTLOADER_SHA256,
            "partition_table_sha256": module.EXPECTED_PARTITION_TABLE_SHA256,
            "bootloader_matches_release": True,
            "partition_table_matches_release": True,
            "port_sha256": module.hashlib.sha256(port.encode()).hexdigest(),
        },
    }
    preflight.write_text(module.json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        module,
        "utc_now",
        lambda: module.dt.datetime(
            2026,
            10,
            25,
            15,
            7,
            tzinfo=module.dt.timezone.utc,
        ),
    )
    assert module.require_preflight(preflight, port)["artifact"] == artifact

    payload["replay_permitted"] = True
    preflight.write_text(module.json.dumps(payload), encoding="utf-8")
    with pytest.raises(module.StopExecution, match="replay boundary"):
        module.require_preflight(preflight, port)

    payload["replay_permitted"] = False
    payload["artifact"] = dict(artifact)
    payload["artifact"]["artifact_id"] = -1
    preflight.write_text(module.json.dumps(payload), encoding="utf-8")
    with pytest.raises(module.StopExecution, match="artifact binding"):
        module.require_preflight(preflight, port)


def test_authorization_state_root_ignores_HOME_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    real_home = tmp_path / "account-home"
    fake_home = tmp_path / "env-home"
    real_home.mkdir()
    fake_home.mkdir()

    class Account:
        pw_dir = str(real_home)

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(module.pwd, "getpwuid", lambda uid: Account())

    observed = module.authorization_state_root()

    assert observed == real_home / module.AUTHORIZATION_STATE_RELATIVE
    assert not str(observed).startswith(str(fake_home))


def test_claim_directory_is_fsynced_before_return(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = tmp_path / "state"
    root.mkdir(mode=0o700)
    run_root = module.authorization_run_root(root)
    synced: list[Path] = []

    monkeypatch.setattr(module, "fsync_directory", lambda path: synced.append(path))

    module.claim_authorization(run_root)

    assert run_root.is_dir()
    assert synced == [root]


def test_preflight_stops_after_authorization_is_claimed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fixed_state = tmp_path / "fixed-state"
    fixed_state.mkdir(mode=0o700)
    monkeypatch.setattr(module, "authorization_state_root", lambda: fixed_state)

    run_root = module.require_authorization_unclaimed_readonly()
    module.claim_authorization(run_root)

    with pytest.raises(module.StopExecution, match="authorization already claimed"):
        module.require_authorization_unclaimed_readonly()


def test_run_preflight_checks_authorization_state_before_reporting_pass() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    start = source.index("def run_preflight")
    end = source.index("def run_execute", start)
    body = source[start:end]

    claim_guard = body.index("require_authorization_unclaimed_readonly()")
    pass_print = body.index('print("SCOPED_NVS_RESET_PREEXECUTION=PASS")')

    assert claim_guard < pass_print


def test_terminal_result_is_fsynced_before_pass_output() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    result_write = source.index("write_private_json(result_path, result)")
    result_sync = source.index("fsync_directory(run_root)", result_write)
    pass_output = source.index('print("SCOPED_NVS_ERASE=PASS")')

    assert result_write < result_sync < pass_output
