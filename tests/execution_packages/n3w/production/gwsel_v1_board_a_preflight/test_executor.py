from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
MODULE_PATH = (
    ROOT
    / "tools/execution_packages/n3w/production/gwsel_v1_board_a_preflight/executor.py"
)

spec = importlib.util.spec_from_file_location(
    "n3w_gwsel_v1_board_a_preflight_executor", MODULE_PATH
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_exact_r2_production_artifact_binding() -> None:
    assert module.BOARD_LABEL == "A"
    assert module.PRODUCT_SOURCE == "8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c"
    assert module.PRODUCT_TREE == "e9c0216c4a25e99038ff81e54036455cb32b4181"
    assert module.ARTIFACT_ID == 10693728323
    assert module.ARTIFACT_ZIP_SIZE == 4281423
    assert (
        module.ARTIFACT_ZIP_SHA256
        == "e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814"
    )
    assert (
        module.RELEASE_BUNDLE_SHA256
        == "f7c7ac703e6b23040235020c92e480f08c602076d32afa18c8a37e5da3882598"
    )
    assert (
        module.MEMBER_BINDINGS["firmware.bin"][1]
        == "c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a"
    )
    assert (
        module.PARTITION_TABLE_SHA256
        == "6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca"
    )
    assert module.EXPECTED_MANIFEST["GATEWAY_SELECTION_R2_LINK_PROOF"] == "PASS"


def test_wrong_target_artifact_is_not_referenced() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "10691518958" not in source
    assert "5e0dc5d950061dd6685b11ee972090036a5af6d576920621550582d216ce38e6" not in source
    assert "board_lab/n3w_phase4_physical/generic.yml" not in source


def test_operator_confirmation_stops_before_artifact_or_board_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    touched = False

    def should_not_run(*args: object, **kwargs: object) -> object:
        nonlocal touched
        touched = True
        raise AssertionError("must not run before target confirmation")

    monkeypatch.setattr(module, "validate_artifact", should_not_run)

    args = argparse.Namespace(
        confirm_target="WRONG",
        artifact_zip="/tmp/not-used.zip",
        port="/dev/not-used",
        output="/tmp/not-used.json",
    )
    with pytest.raises(module.StopExecution, match="target confirmation"):
        module.run_preflight(args)
    assert touched is False


def test_probe_is_read_only_and_records_partition_and_otadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_mac = ":".join(f"{value:02x}" for value in (2, 0, 0, 0, 0, 66))
    partition = bytes((index % 251 for index in range(96)))
    otadata = bytes((index % 239 for index in range(128)))

    monkeypatch.setattr(module, "PARTITION_TABLE_SIZE", len(partition))
    monkeypatch.setattr(
        module,
        "PARTITION_TABLE_SHA256",
        hashlib.sha256(partition).hexdigest(),
    )
    monkeypatch.setattr(module, "OTADATA_SIZE", len(otadata))

    calls: list[list[str]] = []

    def fake_run(args: list[str], *, port: str | None = None) -> str:
        calls.append(args)
        if args[-1] == "get-security-info":
            return (
                "Chip is ESP32-C6 (QFN40)\n"
                f"MAC: {raw_mac}\n"
                "Secure Boot: Disabled\n"
                "Flash Encryption: Disabled\n"
            )
        if args[-1] == "flash-id":
            return "Detected flash size: 8 MB\n"
        if "read-flash" in args:
            idx = args.index("read-flash")
            offset = int(args[idx + 1], 16)
            destination = Path(args[idx + 3])
            if offset == module.PARTITION_TABLE_OFFSET:
                destination.write_bytes(partition)
            elif offset == module.OTADATA_OFFSET:
                destination.write_bytes(otadata)
            else:
                raise AssertionError(args)
            return "Read complete\n"
        raise AssertionError(args)

    monkeypatch.setattr(module, "run_capture", fake_run)

    result = module.probe_board("/dev/cu.synthetic")
    assert result["operator_board_label"] == "A"
    assert result["chip"] == "ESP32-C6"
    assert result["flash_size"] == "8MB"
    assert result["secure_boot"] is False
    assert result["flash_encryption"] is False
    assert result["partition_table_sha256"] == hashlib.sha256(partition).hexdigest()
    assert result["otadata_sha256"] == hashlib.sha256(otadata).hexdigest()
    assert raw_mac not in json.dumps(result, sort_keys=True)

    flattened = [token for call in calls for token in call]
    assert flattened.count("read-flash") == 2
    assert all("--no-stub" in call for call in calls)

    forbidden = {
        "write-flash",
        "erase-flash",
        "erase-region",
        "write-mem",
        "write-flash-status",
    }
    assert forbidden.isdisjoint(flattened)


def test_partition_mismatch_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_mac = ":".join(f"{value:02x}" for value in (2, 0, 0, 0, 0, 67))
    partition = b"partition-readback"
    otadata = b"ota-readback"

    monkeypatch.setattr(module, "PARTITION_TABLE_SIZE", len(partition))
    monkeypatch.setattr(module, "PARTITION_TABLE_SHA256", "0" * 64)
    monkeypatch.setattr(module, "OTADATA_SIZE", len(otadata))

    def fake_run(args: list[str], *, port: str | None = None) -> str:
        if args[-1] == "get-security-info":
            return (
                "Chip is ESP32-C6 (QFN40)\n"
                f"MAC: {raw_mac}\n"
                "Secure Boot: Disabled\n"
                "Flash Encryption: Disabled\n"
            )
        if args[-1] == "flash-id":
            return "Detected flash size: 8 MB\n"
        if "read-flash" in args:
            idx = args.index("read-flash")
            destination = Path(args[idx + 3])
            destination.write_bytes(partition)
            return "Read complete\n"
        raise AssertionError(args)

    monkeypatch.setattr(module, "run_capture", fake_run)

    with pytest.raises(module.StopExecution, match="partition table binding mismatch"):
        module.probe_board("/dev/cu.synthetic")
