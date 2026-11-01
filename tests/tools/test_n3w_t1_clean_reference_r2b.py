from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import n3w_t1_clean_reference_r2b as r2b
from tools import n3w_t1_clean_reference_r2b_package_builder as builder

CONTROL_HEAD = "2" * 40


def test_package_builder_emits_single_exact_executor(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    destination = tmp_path / "package"

    report = builder.build_package(repo_root, destination, CONTROL_HEAD)

    assert report["status"] == "PASS"
    assert report["product_source_head"] == r2b.PRODUCT_SOURCE_HEAD
    assert report["r2a_control_head"] == r2b.R2A_CONTROL_HEAD
    assert report["control_plane_head"] == CONTROL_HEAD
    assert report["file_count"] == 1

    manifest = json.loads(
        (destination / "package-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema"] == r2b.PACKAGE_SCHEMA
    assert manifest["files"][0]["path"] == "tools/n3w_t1_clean_reference_r2b.py"


def test_claim_requires_exact_confirmation() -> None:
    with pytest.raises(r2b.R2BError, match="confirmation_invalid"):
        r2b.claim(
            Path("/does-not-matter"),
            "WRONG",
            "N3W_T1_CORE_STACK_CLEAN_REFERENCE_R2B_TEST_20261101_01",
        )


def test_claim_persists_one_shot_reboot_pending(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    transaction = state_root / "transaction.json"

    monkeypatch.setattr(r2b, "STATE_ROOT", state_root)
    monkeypatch.setattr(r2b, "TRANSACTION", transaction)
    monkeypatch.setattr(r2b.os, "chown", lambda *_args: None)

    monkeypatch.setattr(
        r2b,
        "_package",
        lambda _root: {
            "control_plane_head": CONTROL_HEAD,
            "files": [
                {
                    "path": "tools/n3w_t1_clean_reference_r2b.py",
                    "sha256": "a" * 64,
                    "size": 1,
                    "mode": 0o755,
                }
            ],
        },
    )
    monkeypatch.setattr(
        r2b,
        "_pre_reboot_state",
        lambda: {
            "r2a_transaction": {"stage": "RUNTIME_STARTED"},
            "r2a_transaction_sha256": "b" * 64,
            "boot_id": "11111111-1111-1111-1111-111111111111",
            "containers": {
                "broker": {"id": "b", "started_at": "before-b", "restart_count": 0},
                "manager": {"id": "m", "started_at": "before-m", "restart_count": 0},
                "homeassistant": {
                    "id": "h",
                    "started_at": "before-h",
                    "restart_count": 0,
                },
            },
            "certificates": {"/cert": "c" * 64},
            "homeassistant_http_status": 401,
        },
    )

    authorization = (
        "N3W_T1_CORE_STACK_CLEAN_REFERENCE_R2B_"
        "CONTROLLED_REBOOT_20261101_01"
    )
    report = r2b.claim(
        tmp_path / "package",
        r2b.CONFIRMATION,
        authorization,
    )

    assert report["status"] == "PASS"
    assert report["state"] == "REBOOT_PENDING"
    assert report["authorization_consumed"] is True
    assert report["authorization_replay_allowed"] is False
    assert report["reboot_executed"] is False

    persisted = json.loads(transaction.read_text(encoding="utf-8"))
    assert persisted["stage"] == "REBOOT_PENDING"
    assert persisted["authorization_id"] == authorization
    assert persisted["authorization_consumed"] is True
    assert persisted["authorization_replay_allowed"] is False
    assert persisted["reboot_acceptance_passed"] is False


def test_verify_rejects_when_boot_did_not_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        r2b,
        "_package",
        lambda _root: {
            "control_plane_head": CONTROL_HEAD,
            "files": [{"sha256": "a" * 64}],
        },
    )
    monkeypatch.setattr(
        r2b,
        "_read_json",
        lambda _path, mode=None: {
            "schema": r2b.TRANSACTION_SCHEMA,
            "stage": "REBOOT_PENDING",
            "authorization_claimed": True,
            "authorization_consumed": True,
            "authorization_replay_allowed": False,
            "reboot_acceptance_passed": False,
            "product_source_head": r2b.PRODUCT_SOURCE_HEAD,
            "r2a_control_head": r2b.R2A_CONTROL_HEAD,
            "control_plane_head": CONTROL_HEAD,
            "executor_sha256": "a" * 64,
            "board_access": False,
            "pre_boot_id": "11111111-1111-1111-1111-111111111111",
        },
    )
    monkeypatch.setattr(
        r2b,
        "_boot_id",
        lambda: "11111111-1111-1111-1111-111111111111",
    )

    with pytest.raises(r2b.R2BError, match="reboot_not_observed"):
        r2b.verify(Path("/package"))


def test_verify_accepts_changed_boot_and_refreshes_start_times(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    transaction_path = state_root / "transaction.json"
    r2a_path = tmp_path / "r2a.json"
    r2a_path.write_text('{"ok":true}\n', encoding="utf-8")

    transaction = {
        "schema": r2b.TRANSACTION_SCHEMA,
        "stage": "REBOOT_PENDING",
        "authorization_id": (
            "N3W_T1_CORE_STACK_CLEAN_REFERENCE_R2B_"
            "CONTROLLED_REBOOT_20261101_01"
        ),
        "authorization_claimed": True,
        "authorization_consumed": True,
        "authorization_replay_allowed": False,
        "reboot_acceptance_passed": False,
        "product_source_head": r2b.PRODUCT_SOURCE_HEAD,
        "r2a_control_head": r2b.R2A_CONTROL_HEAD,
        "control_plane_head": CONTROL_HEAD,
        "executor_sha256": "a" * 64,
        "r2a_transaction_sha256": r2b._sha256(r2a_path),
        "pre_boot_id": "11111111-1111-1111-1111-111111111111",
        "pre_containers": {
            "broker": {"id": "b", "started_at": "before-b", "restart_count": 0},
            "manager": {"id": "m", "started_at": "before-m", "restart_count": 0},
            "homeassistant": {
                "id": "h",
                "started_at": "before-h",
                "restart_count": 0,
            },
        },
        "pre_certificate_sha256": {"/cert": "c" * 64},
        "board_access": False,
    }
    transaction_path.write_text(json.dumps(transaction), encoding="utf-8")
    transaction_path.chmod(0o600)

    monkeypatch.setattr(r2b, "STATE_ROOT", state_root)
    monkeypatch.setattr(r2b, "TRANSACTION", transaction_path)
    monkeypatch.setattr(r2b, "R2A_TRANSACTION", r2a_path)
    monkeypatch.setattr(r2b.os, "chown", lambda *_args: None)

    real_read_json = r2b._read_json

    def relaxed_read_json(path: Path, *, mode=None):
        return real_read_json(path, mode=None)

    monkeypatch.setattr(r2b, "_read_json", relaxed_read_json)

    monkeypatch.setattr(
        r2b,
        "_package",
        lambda _root: {
            "control_plane_head": CONTROL_HEAD,
            "files": [{"sha256": "a" * 64}],
        },
    )
    monkeypatch.setattr(
        r2b,
        "_r2a_transaction",
        lambda: {"stage": "RUNTIME_STARTED"},
    )
    monkeypatch.setattr(r2b, "_wait_post_reboot", lambda: None)
    monkeypatch.setattr(
        r2b,
        "_systemctl",
        lambda mode, unit: (
            "enabled"
            if mode == "is-enabled"
            else ("inactive" if unit == r2b.CERT_SERVICE else "active")
        ),
    )
    monkeypatch.setattr(
        r2b,
        "_running_services",
        lambda: r2b.EXPECTED_SERVICES,
    )

    def fake_run(argv, **_kwargs):
        if tuple(argv[:3]) == ("docker", "network", "ls"):
            return "bridge\nhost\nnone\nn3wfc4-private\nn3wfc4-services\n"
        return ""

    monkeypatch.setattr(r2b, "_run", fake_run)

    snapshots = [
        {
            "broker": {"id": "b", "started_at": "after-b", "restart_count": 0},
            "manager": {"id": "m", "started_at": "after-m", "restart_count": 0},
            "homeassistant": {
                "id": "h",
                "started_at": "after-h",
                "restart_count": 0,
            },
        },
        {
            "broker": {"id": "b", "started_at": "after-b", "restart_count": 0},
            "manager": {"id": "m", "started_at": "after-m", "restart_count": 0},
            "homeassistant": {
                "id": "h",
                "started_at": "after-h",
                "restart_count": 0,
            },
        },
    ]
    monkeypatch.setattr(r2b, "_container_snapshot", lambda: snapshots.pop(0))
    monkeypatch.setattr(
        r2b,
        "_certificate_snapshot",
        lambda: {"/cert": "c" * 64},
    )
    monkeypatch.setattr(r2b, "_broker_readiness", lambda: None)
    monkeypatch.setattr(r2b, "_ha_readiness", lambda: 401)
    monkeypatch.setattr(r2b.time, "sleep", lambda _seconds: None)

    boots = iter(
        [
            "22222222-2222-2222-2222-222222222222",
            "22222222-2222-2222-2222-222222222222",
        ]
    )
    monkeypatch.setattr(r2b, "_boot_id", lambda: next(boots))

    report = r2b.verify(tmp_path / "package")

    assert report["status"] == "PASS"
    assert report["state"] == "REBOOT_ACCEPTED"
    assert report["reboot_observed"] is True
    assert report["r2a_transaction_unchanged"] is True
    assert report["certificate_identity_unchanged"] is True
    assert report["reboot_acceptance_passed"] is True

    persisted = json.loads(transaction_path.read_text(encoding="utf-8"))
    assert persisted["stage"] == "REBOOT_ACCEPTED"
    assert persisted["reboot_acceptance_passed"] is True
    assert persisted["post_boot_id"] == "22222222-2222-2222-2222-222222222222"


def test_r2b_source_does_not_actuate_reboot_or_touch_boards() -> None:
    source = Path(r2b.__file__).read_text(encoding="utf-8")
    executable = source.split("\ndef _parser(", 1)[0]

    assert '("systemctl", "reboot"' not in executable
    assert '"reboot", "now"' not in executable
    assert '"docker", "build"' not in executable
    assert '"docker", "pull"' not in executable
    assert '"buildx"' not in executable
    assert "esptool" not in executable
