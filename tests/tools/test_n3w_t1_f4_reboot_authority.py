from __future__ import annotations

import hashlib
import importlib.util
import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_f4_reboot_authority.py"


def load_tool():
    name = "n3w_t1_f4_reboot_authority"
    spec = importlib.util.spec_from_file_location(name, TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_install_claim_payload_is_consumed_before_install(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    monkeypatch.setattr(tool, "INSTALL_CLAIM_PATH", tmp_path / "install.json")

    fake_module = SimpleNamespace(
        _runtime_container_snapshot=lambda: {"broker": {"id": "b"}},
        _certificate_identity_snapshot=lambda: {"server": "s"},
    )
    transaction = {
        "runtime_acceptance_authorization_id": "N3W_T1_F4_OLD_RUNTIME_ACCEPTANCE_01"
    }
    monkeypatch.setattr(
        tool,
        "_base_pre_reboot",
        lambda _sha: (fake_module, transaction),
    )
    monkeypatch.setattr(
        tool,
        "_package",
        lambda *_args, **_kwargs: {
            "root": tmp_path,
            "manifest_sha256": "b" * 64,
            "source_head": "a" * 40,
            "files": {
                relative: {"sha256": "c" * 64, "size": 10}
                for relative in tool.CONTROL_TARGETS
            },
        },
    )

    result = tool.install_claim_payload(
        package_root=tmp_path,
        source_head="a" * 40,
        manifest_sha256="b" * 64,
        authorization_id="N3W_T1_F4_REBOOT_CONTROL_REPAIR_20261016_01",
        expected_transaction_sha256="d" * 64,
    )

    assert result["stage"] == "INSTALL_CLAIMED"
    assert result["control_repair_authorization_claimed"] is True
    assert result["control_repair_authorization_consumed"] is True
    assert result["control_repair_authorization_replay_allowed"] is False
    assert result["live_runtime_mutation"] is False
    assert result["reboot_executed"] is False
    assert result["board_access"] is False


def test_reboot_claim_payload_is_one_shot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    monkeypatch.setattr(tool, "REBOOT_CLAIM_PATH", tmp_path / "reboot.json")
    transaction = {
        "certificate_timer_authorization_id": (
            "N3W_T1_F4_CERTIFICATE_TIMER_ENABLEMENT_SUCCESSOR_LIVE_20261016_01"
        )
    }
    install_claim = {
        "control_repair_authorization_id": (
            "N3W_T1_F4_REBOOT_CONTROL_REPAIR_20261016_01"
        ),
        "pre_certificate_snapshot_sha256": "f" * 64,
    }
    monkeypatch.setattr(
        tool,
        "_verify_installed_control",
        lambda **_kwargs: (SimpleNamespace(), transaction, install_claim),
    )
    monkeypatch.setattr(tool, "_boot_id_sha256", lambda: "e" * 64)

    result = tool.reboot_claim_payload(
        source_head="a" * 40,
        manifest_sha256="b" * 64,
        authorization_id="N3W_T1_F4_REBOOT_SUCCESSOR_LIVE_20261016_01",
        expected_transaction_sha256="d" * 64,
    )

    assert result["stage"] == "REBOOT_PENDING"
    assert result["reboot_authorization_claimed"] is True
    assert result["reboot_authorization_consumed"] is True
    assert result["reboot_authorization_replay_allowed"] is False
    assert result["reboot_acceptance_passed"] is False
    assert result["pre_boot_id_sha256"] == "e" * 64
    assert result["board_access"] is False


def test_fresh_authorization_rejects_prior_f4_id() -> None:
    tool = load_tool()
    transaction = {
        "runtime_acceptance_authorization_id": (
            "N3W_T1_F4_RUNTIME_ACCEPTANCE_SUCCESSOR_LIVE_20261016_01"
        )
    }
    with pytest.raises(tool.AuthorityError, match="authorization_replay_forbidden"):
        tool._fresh_authorization(
            "N3W_T1_F4_RUNTIME_ACCEPTANCE_SUCCESSOR_LIVE_20261016_01",
            f4_transaction=transaction,
        )


def test_authority_never_actuates_reboot() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert '("systemctl", "reboot")' not in source
    assert '("systemctl", "poweroff")' not in source
    assert '("shutdown"' not in source


def test_claim_install_persists_consumed_authority_before_return(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    claim_path = tmp_path / "install-claim.json"
    payload = {
        "schema": tool.SCHEMA_INSTALL,
        "stage": "INSTALL_CLAIMED",
        "control_repair_authorization_claimed": True,
        "control_repair_authorization_consumed": True,
        "control_repair_authorization_replay_allowed": False,
        "live_runtime_mutation": False,
        "reboot_executed": False,
        "board_access": False,
    }

    monkeypatch.setattr(tool, "INSTALL_CLAIM_PATH", claim_path)
    monkeypatch.setattr(tool, "_exclusive", lambda: nullcontext())
    monkeypatch.setattr(tool, "install_claim_payload", lambda **_kwargs: payload)

    def write_record(path: Path, document: dict[str, object]) -> None:
        path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        path.chmod(0o600)

    monkeypatch.setattr(tool, "_atomic_write_record", write_record)
    monkeypatch.setattr(
        tool,
        "_record",
        lambda path, _mode: json.loads(path.read_text(encoding="utf-8")),
    )

    result = tool.claim_install(
        package_root=tmp_path,
        source_head="a" * 40,
        manifest_sha256="b" * 64,
        authorization_id="N3W_T1_F4_REBOOT_CONTROL_REPAIR_20261016_01",
        expected_transaction_sha256="c" * 64,
    )

    assert claim_path.is_file()
    assert json.loads(claim_path.read_text()) == payload
    assert result["state"] == "INSTALL_CLAIMED"
    assert result["control_repair_authorization_consumed"] is True
    assert result["claim_sha256"] == hashlib.sha256(
        claim_path.read_bytes()
    ).hexdigest()


def test_install_control_marks_applying_before_any_control_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    claim_path = tmp_path / "install-claim.json"
    manifest_target = tmp_path / "installed-manifest.json"
    package_root = tmp_path / "package"
    package_root.mkdir()

    fake_targets = {
        "guard.py": (tmp_path / "guard-target.py", 0o755),
        "authority.py": (tmp_path / "authority-target.py", 0o755),
        "verify.py": (tmp_path / "verify-target.py", 0o755),
        "dropin.conf": (tmp_path / "dropin-target.conf", 0o644),
    }
    for relative in fake_targets:
        (package_root / relative).write_text(relative, encoding="utf-8")
    (package_root / tool.MANIFEST_NAME).write_text("{}", encoding="utf-8")

    fake_module = SimpleNamespace(
        _runtime_container_snapshot=lambda: {"broker": {"id": "b"}},
        _certificate_identity_snapshot=lambda: {"server": "s"},
    )
    runtime_sha = tool._canonical_sha(fake_module._runtime_container_snapshot())
    cert_sha = tool._canonical_sha(fake_module._certificate_identity_snapshot())
    claim = {
        "schema": tool.SCHEMA_INSTALL,
        "stage": "INSTALL_CLAIMED",
        "source_head": "a" * 40,
        "control_manifest_sha256": "b" * 64,
        "f4_transaction_sha256": "c" * 64,
        "pre_runtime_snapshot_sha256": runtime_sha,
        "pre_certificate_snapshot_sha256": cert_sha,
        "control_repair_authorization_claimed": True,
        "control_repair_authorization_consumed": True,
        "control_repair_authorization_replay_allowed": False,
        "board_access": False,
    }
    claim_path.write_text(json.dumps(claim), encoding="utf-8")
    claim_path.chmod(0o600)

    events: list[str] = []
    monkeypatch.setattr(tool, "INSTALL_CLAIM_PATH", claim_path)
    monkeypatch.setattr(tool, "CONTROL_MANIFEST", manifest_target)
    monkeypatch.setattr(tool, "CONTROL_TARGETS", fake_targets)
    monkeypatch.setattr(tool, "_exclusive", lambda: nullcontext())
    monkeypatch.setattr(
        tool,
        "_record",
        lambda path, _mode: json.loads(path.read_text(encoding="utf-8")),
    )

    def write_record(path: Path, document: dict[str, object]) -> None:
        events.append(f"state:{document['stage']}")
        path.write_text(json.dumps(document), encoding="utf-8")
        path.chmod(0o600)

    monkeypatch.setattr(tool, "_atomic_write_record", write_record)
    monkeypatch.setattr(
        tool,
        "_package",
        lambda *_args, **_kwargs: {
            "root": package_root,
            "source_head": "a" * 40,
            "manifest_sha256": "b" * 64,
            "files": {
                relative: {
                    "sha256": "d" * 64,
                    "size": (package_root / relative).stat().st_size,
                }
                for relative in fake_targets
            },
        },
    )
    monkeypatch.setattr(
        tool,
        "_base_pre_reboot",
        lambda _sha: (fake_module, {}),
    )

    def install_file(_source: Path, target: Path, _mode: int) -> None:
        current = json.loads(claim_path.read_text(encoding="utf-8"))
        assert current["stage"] == "CONTROL_APPLYING"
        events.append(f"install:{target.name}")

    monkeypatch.setattr(tool, "_install_exact_file", install_file)
    monkeypatch.setattr(tool, "_run", lambda *_args, **_kwargs: "")

    def verify_control(**_kwargs):
        current = json.loads(claim_path.read_text(encoding="utf-8"))
        assert current["stage"] == "CONTROL_APPLYING"
        events.append("verify")
        return fake_module, {}, current

    monkeypatch.setattr(tool, "_verify_installed_control", verify_control)

    result = tool.install_control(
        package_root=package_root,
        source_head="a" * 40,
        manifest_sha256="b" * 64,
        expected_transaction_sha256="c" * 64,
    )

    assert events[0] == "state:CONTROL_APPLYING"
    assert events[-2] == "verify"
    assert events[-1] == "state:CONTROL_READY"
    assert result["state"] == "CONTROL_READY"


def test_recovery_old_target_binding_accepts_exact_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()

    class FakeTarget:
        name = "guard-target.py"

        def is_symlink(self) -> bool:
            return False

        def is_file(self) -> bool:
            return True

        def stat(self):
            return SimpleNamespace(
                st_uid=0,
                st_gid=0,
                st_nlink=1,
                st_mode=0o755,
                st_size=7,
            )

        def __str__(self) -> str:
            return "/target/guard.py"

    target = FakeTarget()
    manifest = Path("/manifest.json")
    monkeypatch.setattr(
        tool,
        "CONTROL_TARGETS",
        {"guard.py": (target, 0o755)},
    )
    monkeypatch.setattr(tool, "CONTROL_MANIFEST", manifest)
    monkeypatch.setattr(
        tool,
        "_record",
        lambda _path, _mode: {
            "schema": tool.PACKAGE_SCHEMA,
            "source_head": "a" * 40,
        },
    )
    monkeypatch.setattr(
        tool,
        "_sha256",
        lambda path: "b" * 64 if path == manifest else "c" * 64,
    )
    claim = {
        "source_head": "a" * 40,
        "control_manifest_sha256": "b" * 64,
        "files": {
            "guard.py": {
                "sha256": "c" * 64,
                "size": 7,
                "target": "/target/guard.py",
                "mode": 0o755,
            }
        },
    }

    tool._verify_claim_installed_files(claim)


def test_recovery_old_target_binding_rejects_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()

    class FakeTarget:
        name = "guard-target.py"

        def is_symlink(self) -> bool:
            return False

        def is_file(self) -> bool:
            return True

        def stat(self):
            return SimpleNamespace(
                st_uid=0,
                st_gid=0,
                st_nlink=1,
                st_mode=0o755,
                st_size=7,
            )

        def __str__(self) -> str:
            return "/target/guard.py"

    target = FakeTarget()
    manifest = Path("/manifest.json")
    monkeypatch.setattr(
        tool,
        "CONTROL_TARGETS",
        {"guard.py": (target, 0o755)},
    )
    monkeypatch.setattr(tool, "CONTROL_MANIFEST", manifest)
    monkeypatch.setattr(
        tool,
        "_record",
        lambda _path, _mode: {
            "schema": tool.PACKAGE_SCHEMA,
            "source_head": "a" * 40,
        },
    )
    monkeypatch.setattr(
        tool,
        "_sha256",
        lambda path: "b" * 64 if path == manifest else "d" * 64,
    )
    claim = {
        "source_head": "a" * 40,
        "control_manifest_sha256": "b" * 64,
        "files": {
            "guard.py": {
                "sha256": "c" * 64,
                "size": 7,
                "target": "/target/guard.py",
                "mode": 0o755,
            }
        },
    }

    with pytest.raises(
        tool.AuthorityError,
        match="installed_target_binding_invalid",
    ):
        tool._verify_claim_installed_files(claim)


def test_recovery_identity_binding_rejects_runtime_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = load_tool()
    fake = SimpleNamespace(
        _runtime_container_snapshot=lambda: {"broker": {"id": "new"}},
        _certificate_identity_snapshot=lambda: {"server": "same"},
    )
    monkeypatch.setattr(tool, "_boot_id_sha256", lambda: "e" * 64)

    with pytest.raises(tool.AuthorityError, match="recovery_runtime_identity_drift"):
        tool._validate_recovery_identity_bindings(
            fake,
            {"certificate_status_sha256": "f" * 64},
            expected_runtime_snapshot_sha256=tool._canonical_sha(
                {"broker": {"id": "old"}}
            ),
            expected_certificate_snapshot_sha256=tool._canonical_sha(
                {"server": "same"}
            ),
            expected_boot_id_sha256="e" * 64,
        )


def test_control_recovery_rejects_original_install_authorization_replay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    monkeypatch.setattr(
        tool,
        "CONTROL_RECOVERY_CLAIM_PATH",
        tmp_path / "recovery.json",
    )
    old_authorization = "N3W_T1_F4_REBOOT_CONTROL_REPAIR_20261016_01"
    transaction = {"stage": "PERSISTENCE_ENABLED"}
    install_claim = {
        "source_head": "1" * 40,
        "control_manifest_sha256": "2" * 64,
        "pre_runtime_snapshot_sha256": "3" * 64,
        "pre_certificate_snapshot_sha256": "4" * 64,
        "control_repair_authorization_id": old_authorization,
    }
    package = {
        "root": tmp_path,
        "files": {
            relative: {"sha256": "5" * 64, "size": 10}
            for relative in tool.CONTROL_TARGETS
        },
    }
    monkeypatch.setattr(tool, "_package", lambda *_args, **_kwargs: package)
    monkeypatch.setattr(tool, "_validate_recovery_entrypoint", lambda _package: None)
    monkeypatch.setattr(
        tool,
        "_validate_control_applying_prestate",
        lambda **_kwargs: (SimpleNamespace(), transaction, install_claim),
    )

    with pytest.raises(tool.AuthorityError, match="authorization_replay_forbidden"):
        tool.control_recovery_claim_payload(
            package_root=tmp_path,
            source_head="a" * 40,
            manifest_sha256="b" * 64,
            authorization_id=old_authorization,
            expected_transaction_sha256="c" * 64,
            expected_install_claim_sha256="d" * 64,
            expected_boot_id_sha256="e" * 64,
        )


def test_control_recovery_claim_binds_old_claim_and_new_exact_package(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    monkeypatch.setattr(
        tool,
        "CONTROL_RECOVERY_CLAIM_PATH",
        tmp_path / "recovery.json",
    )
    transaction = {
        "runtime_acceptance_authorization_id": "N3W_T1_F4_OLD_RUNTIME_20261016_01"
    }
    install_claim = {
        "source_head": "1" * 40,
        "control_manifest_sha256": "2" * 64,
        "pre_runtime_snapshot_sha256": "3" * 64,
        "pre_certificate_snapshot_sha256": "4" * 64,
        "control_repair_authorization_id": (
            "N3W_T1_F4_REBOOT_CONTROL_REPAIR_20261016_01"
        ),
    }
    package = {
        "root": tmp_path,
        "files": {
            relative: {"sha256": "5" * 64, "size": index + 1}
            for index, relative in enumerate(tool.CONTROL_TARGETS)
        },
    }
    monkeypatch.setattr(tool, "_package", lambda *_args, **_kwargs: package)
    monkeypatch.setattr(tool, "_validate_recovery_entrypoint", lambda _package: None)
    monkeypatch.setattr(
        tool,
        "_validate_control_applying_prestate",
        lambda **_kwargs: (SimpleNamespace(), transaction, install_claim),
    )

    result = tool.control_recovery_claim_payload(
        package_root=tmp_path,
        source_head="a" * 40,
        manifest_sha256="b" * 64,
        authorization_id="N3W_T1_F4_CONTROL_APPLYING_RECOVERY_LIVE_20261016_01",
        expected_transaction_sha256="c" * 64,
        expected_install_claim_sha256="d" * 64,
        expected_boot_id_sha256="e" * 64,
    )

    assert result["stage"] == "RECOVERY_CLAIMED"
    assert result["recovery_from_install_claim_sha256"] == "d" * 64
    assert result["recovery_from_source_head"] == "1" * 40
    assert result["recovery_from_control_manifest_sha256"] == "2" * 64
    assert result["source_head"] == "a" * 40
    assert result["control_manifest_sha256"] == "b" * 64
    assert result["control_recovery_authorization_consumed"] is True
    assert result["control_recovery_authorization_replay_allowed"] is False
    assert result["recovery_apply_started"] is False
    assert result["recovery_verified"] is False
    assert result["installation_verified"] is False


def test_claim_control_recovery_persists_consumed_authority_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    claim_path = tmp_path / "recovery.json"
    payload = {
        "schema": tool.SCHEMA_RECOVERY,
        "stage": "RECOVERY_CLAIMED",
        "control_recovery_authorization_claimed": True,
        "control_recovery_authorization_consumed": True,
        "control_recovery_authorization_replay_allowed": False,
        "live_runtime_mutation": False,
        "reboot_executed": False,
        "board_access": False,
    }
    monkeypatch.setattr(tool, "CONTROL_RECOVERY_CLAIM_PATH", claim_path)
    monkeypatch.setattr(tool, "_exclusive", lambda: nullcontext())
    monkeypatch.setattr(
        tool,
        "control_recovery_claim_payload",
        lambda **_kwargs: payload,
    )

    def write_record(path: Path, document: dict[str, object]) -> None:
        path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        path.chmod(0o600)

    monkeypatch.setattr(tool, "_atomic_write_record", write_record)
    monkeypatch.setattr(
        tool,
        "_record",
        lambda path, _mode: json.loads(path.read_text(encoding="utf-8")),
    )

    result = tool.claim_control_recovery(
        package_root=tmp_path,
        source_head="a" * 40,
        manifest_sha256="b" * 64,
        authorization_id="N3W_T1_F4_CONTROL_APPLYING_RECOVERY_LIVE_20261016_01",
        expected_transaction_sha256="c" * 64,
        expected_install_claim_sha256="d" * 64,
        expected_boot_id_sha256="e" * 64,
    )

    assert json.loads(claim_path.read_text()) == payload
    assert result["state"] == "RECOVERY_CLAIMED"
    assert result["control_recovery_authorization_consumed"] is True
    assert result["live_runtime_mutation"] is False


def test_recovery_apply_rejects_reboot_executed_marker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    recovery_path = tmp_path / "recovery.json"
    claim = {
        "schema": tool.SCHEMA_RECOVERY,
        "stage": "RECOVERY_CLAIMED",
        "source_head": "a" * 40,
        "control_manifest_sha256": "b" * 64,
        "f4_transaction_sha256": "c" * 64,
        "recovery_from_install_claim_sha256": "d" * 64,
        "pre_boot_id_sha256": "e" * 64,
        "control_recovery_authorization_claimed": True,
        "control_recovery_authorization_consumed": True,
        "control_recovery_authorization_replay_allowed": False,
        "recovery_apply_started": False,
        "recovery_verified": False,
        "installation_verified": False,
        "live_runtime_mutation": False,
        "reboot_executed": True,
        "board_access": False,
    }
    monkeypatch.setattr(tool, "CONTROL_RECOVERY_CLAIM_PATH", recovery_path)
    monkeypatch.setattr(tool, "_record", lambda _path, _mode: claim)

    with pytest.raises(
        tool.AuthorityError,
        match="control_recovery_claim_contract_invalid",
    ):
        tool._validate_recovery_claim_for_apply(
            package_root=tmp_path,
            source_head="a" * 40,
            manifest_sha256="b" * 64,
            expected_transaction_sha256="c" * 64,
            expected_install_claim_sha256="d" * 64,
            expected_boot_id_sha256="e" * 64,
        )


def _recovery_apply_fixture(
    tool,
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    dict[str, tuple[Path, int]],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    package_root = tmp_path / "package"
    package_root.mkdir()
    recovery_path = tmp_path / "recovery.json"
    install_path = tmp_path / "install.json"
    targets = {
        "guard.py": (tmp_path / "guard-target.py", 0o755),
        "authority.py": (tmp_path / "authority-target.py", 0o755),
        "verify.py": (tmp_path / "verify-target.py", 0o755),
        "dropin.conf": (tmp_path / "dropin-target.conf", 0o644),
    }
    files: dict[str, dict[str, object]] = {}
    package_files: dict[str, dict[str, object]] = {}
    for index, (relative, (target, mode)) in enumerate(targets.items()):
        source = package_root / relative
        source.write_text(f"new-{index}", encoding="utf-8")
        target.write_text(f"old-{index}", encoding="utf-8")
        target.chmod(mode)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        files[relative] = {
            "sha256": digest,
            "size": source.stat().st_size,
            "target": str(target),
            "mode": mode,
        }
        package_files[relative] = {
            "sha256": digest,
            "size": source.stat().st_size,
        }
    manifest = package_root / tool.MANIFEST_NAME
    manifest.write_text('{"new":true}\n', encoding="utf-8")
    manifest_sha256 = hashlib.sha256(manifest.read_bytes()).hexdigest()
    manifest_target = tmp_path / "installed-manifest.json"
    manifest_target.write_text('{"old":true}\n', encoding="utf-8")
    manifest_target.chmod(0o644)

    install_claim = {
        "schema": tool.SCHEMA_INSTALL,
        "stage": "CONTROL_APPLYING",
        "source_head": "1" * 40,
        "control_manifest_sha256": "2" * 64,
        "f4_transaction_sha256": "c" * 64,
        "control_repair_authorization_id": (
            "N3W_T1_F4_REBOOT_CONTROL_REPAIR_20261016_01"
        ),
        "control_repair_authorization_claimed": True,
        "control_repair_authorization_consumed": True,
        "control_repair_authorization_replay_allowed": False,
        "installation_apply_started": True,
        "board_access": False,
    }
    recovery_claim = {
        "schema": tool.SCHEMA_RECOVERY,
        "stage": "RECOVERY_CLAIMED",
        "recovery_from_install_claim_sha256": "d" * 64,
        "recovery_from_source_head": "1" * 40,
        "recovery_from_control_manifest_sha256": "2" * 64,
        "source_head": "a" * 40,
        "control_manifest_sha256": manifest_sha256,
        "f4_transaction_sha256": "c" * 64,
        "pre_runtime_snapshot_sha256": "3" * 64,
        "pre_certificate_snapshot_sha256": "4" * 64,
        "pre_boot_id_sha256": "e" * 64,
        "control_recovery_authorization_id": (
            "N3W_T1_F4_CONTROL_APPLYING_RECOVERY_LIVE_20261016_01"
        ),
        "control_recovery_authorization_claimed": True,
        "control_recovery_authorization_consumed": True,
        "control_recovery_authorization_replay_allowed": False,
        "files": files,
        "recovery_apply_started": False,
        "recovery_verified": False,
        "installation_verified": False,
        "live_runtime_mutation": False,
        "board_access": False,
    }
    package = {
        "root": package_root,
        "files": package_files,
    }
    install_path.write_text(json.dumps(install_claim), encoding="utf-8")
    install_path.chmod(0o600)
    return (
        recovery_path,
        install_path,
        targets,
        package,
        install_claim,
        recovery_claim,
    )


def test_recover_control_requires_durable_applying_before_replacement(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    (
        recovery_path,
        install_path,
        targets,
        package,
        install_claim,
        recovery_claim,
    ) = _recovery_apply_fixture(tool, tmp_path)
    monkeypatch.setattr(tool, "CONTROL_RECOVERY_CLAIM_PATH", recovery_path)
    monkeypatch.setattr(tool, "INSTALL_CLAIM_PATH", install_path)
    monkeypatch.setattr(tool, "CONTROL_TARGETS", targets)
    monkeypatch.setattr(tool, "_exclusive", lambda: nullcontext())
    monkeypatch.setattr(
        tool,
        "_validate_recovery_claim_for_apply",
        lambda **_kwargs: (
            package,
            SimpleNamespace(),
            {},
            install_claim,
            recovery_claim,
        ),
    )

    def write_record(path: Path, document: dict[str, object]) -> None:
        path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        path.chmod(0o600)

    def mismatched_record(path: Path, _mode: int) -> dict[str, object]:
        document = json.loads(path.read_text(encoding="utf-8"))
        if path == recovery_path:
            document["recovery_apply_started"] = False
        return document

    replacements: list[str] = []
    monkeypatch.setattr(tool, "_atomic_write_record", write_record)
    monkeypatch.setattr(tool, "_record", mismatched_record)
    monkeypatch.setattr(
        tool,
        "_replace_exact_file",
        lambda _source, target, _mode: replacements.append(target.name),
    )

    with pytest.raises(
        tool.AuthorityError,
        match="control_recovery_applying_persistence_mismatch",
    ):
        tool.recover_control(
            package_root=package["root"],
            source_head="a" * 40,
            manifest_sha256=recovery_claim["control_manifest_sha256"],
            expected_transaction_sha256="c" * 64,
            expected_install_claim_sha256="d" * 64,
            expected_boot_id_sha256="e" * 64,
        )

    assert replacements == []


def test_recover_control_commits_control_ready_only_after_verified_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    (
        recovery_path,
        install_path,
        targets,
        package,
        install_claim,
        recovery_claim,
    ) = _recovery_apply_fixture(tool, tmp_path)
    manifest_target = tmp_path / "installed-manifest.json"
    events: list[str] = []

    monkeypatch.setattr(tool, "CONTROL_RECOVERY_CLAIM_PATH", recovery_path)
    monkeypatch.setattr(tool, "INSTALL_CLAIM_PATH", install_path)
    monkeypatch.setattr(tool, "CONTROL_MANIFEST", manifest_target)
    monkeypatch.setattr(tool, "CONTROL_TARGETS", targets)
    monkeypatch.setattr(tool, "_exclusive", lambda: nullcontext())
    monkeypatch.setattr(
        tool,
        "_validate_recovery_claim_for_apply",
        lambda **_kwargs: (
            package,
            SimpleNamespace(),
            {},
            install_claim,
            recovery_claim,
        ),
    )

    def write_record(path: Path, document: dict[str, object]) -> None:
        events.append(f"{path.name}:{document['stage']}")
        path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        path.chmod(0o600)

    def replace_file(source: Path, target: Path, mode: int) -> None:
        events.append(f"replace:{target.name}")
        target.write_bytes(source.read_bytes())
        target.chmod(mode)

    monkeypatch.setattr(tool, "_atomic_write_record", write_record)
    monkeypatch.setattr(
        tool,
        "_record",
        lambda path, _mode: json.loads(path.read_text(encoding="utf-8")),
    )
    monkeypatch.setattr(tool, "_replace_exact_file", replace_file)
    monkeypatch.setattr(tool, "_run", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        tool,
        "_verify_recovered_control",
        lambda **_kwargs: events.append("verify") or (SimpleNamespace(), {}),
    )
    monkeypatch.setattr(
        tool,
        "_validate_recovery_ready_link",
        lambda *_args, **_kwargs: events.append("ready-link"),
    )

    result = tool.recover_control(
        package_root=package["root"],
        source_head="a" * 40,
        manifest_sha256=recovery_claim["control_manifest_sha256"],
        expected_transaction_sha256="c" * 64,
        expected_install_claim_sha256="d" * 64,
        expected_boot_id_sha256="e" * 64,
    )

    applying = events.index(f"{recovery_path.name}:RECOVERY_APPLYING")
    verified = events.index(f"{recovery_path.name}:RECOVERY_VERIFIED")
    ready = events.index(f"{install_path.name}:CONTROL_READY")
    assert applying < events.index("verify") < verified < ready
    assert events[-1] == "ready-link"
    assert result["state"] == "CONTROL_READY"
    assert result["recovery_verified"] is True
    assert result["control_recovery_authorization_replay_allowed"] is False


def test_recover_control_partial_failure_stays_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    (
        recovery_path,
        install_path,
        targets,
        package,
        install_claim,
        recovery_claim,
    ) = _recovery_apply_fixture(tool, tmp_path)
    monkeypatch.setattr(tool, "CONTROL_RECOVERY_CLAIM_PATH", recovery_path)
    monkeypatch.setattr(tool, "INSTALL_CLAIM_PATH", install_path)
    monkeypatch.setattr(
        tool,
        "CONTROL_MANIFEST",
        tmp_path / "installed-manifest.json",
    )
    monkeypatch.setattr(tool, "CONTROL_TARGETS", targets)
    monkeypatch.setattr(tool, "_exclusive", lambda: nullcontext())
    monkeypatch.setattr(
        tool,
        "_validate_recovery_claim_for_apply",
        lambda **_kwargs: (
            package,
            SimpleNamespace(),
            {},
            install_claim,
            recovery_claim,
        ),
    )

    def write_record(path: Path, document: dict[str, object]) -> None:
        path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        path.chmod(0o600)

    monkeypatch.setattr(tool, "_atomic_write_record", write_record)
    monkeypatch.setattr(
        tool,
        "_record",
        lambda path, _mode: json.loads(path.read_text(encoding="utf-8")),
    )

    def fail_replace(_source: Path, _target: Path, _mode: int) -> None:
        raise tool.AuthorityError("simulated_partial_failure")

    monkeypatch.setattr(tool, "_replace_exact_file", fail_replace)

    with pytest.raises(tool.AuthorityError, match="simulated_partial_failure"):
        tool.recover_control(
            package_root=package["root"],
            source_head="a" * 40,
            manifest_sha256=recovery_claim["control_manifest_sha256"],
            expected_transaction_sha256="c" * 64,
            expected_install_claim_sha256="d" * 64,
            expected_boot_id_sha256="e" * 64,
        )

    durable_recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
    durable_install = json.loads(install_path.read_text(encoding="utf-8"))
    assert durable_recovery["stage"] == "RECOVERY_APPLYING"
    assert durable_recovery["recovery_apply_started"] is True
    assert durable_recovery["recovery_verified"] is False
    assert durable_recovery["live_runtime_mutation"] is True
    assert durable_install["stage"] == "CONTROL_APPLYING"


def test_claim_reboot_persists_consumed_authority_before_actuation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    claim_path = tmp_path / "reboot-claim.json"
    payload = {
        "schema": tool.SCHEMA_REBOOT,
        "stage": "REBOOT_PENDING",
        "reboot_authorization_claimed": True,
        "reboot_authorization_consumed": True,
        "reboot_authorization_replay_allowed": False,
        "reboot_acceptance_passed": False,
        "pre_boot_id_sha256": "a" * 64,
        "board_access": False,
    }

    monkeypatch.setattr(tool, "REBOOT_CLAIM_PATH", claim_path)
    monkeypatch.setattr(tool, "_exclusive", lambda: nullcontext())
    monkeypatch.setattr(tool, "reboot_claim_payload", lambda **_kwargs: payload)

    def write_record(path: Path, document: dict[str, object]) -> None:
        path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        path.chmod(0o600)

    monkeypatch.setattr(tool, "_atomic_write_record", write_record)
    monkeypatch.setattr(
        tool,
        "_record",
        lambda path, _mode: json.loads(path.read_text(encoding="utf-8")),
    )

    result = tool.claim_reboot(
        source_head="a" * 40,
        manifest_sha256="b" * 64,
        authorization_id="N3W_T1_F4_REBOOT_SUCCESSOR_LIVE_20261016_01",
        expected_transaction_sha256="c" * 64,
    )

    assert claim_path.is_file()
    assert json.loads(claim_path.read_text()) == payload
    assert result["state"] == "REBOOT_PENDING"
    assert result["reboot_authorization_consumed"] is True
    assert result["host_reboot_actuation_required"] is True



def _test_acceptance_report(tool, *, pre_boot: str, post_boot: str) -> dict[str, object]:
    return {
        "schema": tool.REBOOT_ACCEPTANCE_SCHEMA,
        "status": "PASS",
        "state": "REBOOT_ACCEPTED",
        "reboot_acceptance_passed": True,
        "pre_boot_id_sha256": pre_boot,
        "post_boot_id_sha256": post_boot,
        "f4_transaction_unchanged": True,
        "provision_resume_verified": True,
        "broker_services_persistence_verified": True,
        "certificate_timer_runtime_verified": True,
        "certificate_service_result_verified": True,
        "certificate_status_sha256": "f" * 64,
        "certificate_identity_unchanged": True,
        "manager_runtime_stability_verified": True,
        "homeassistant_mqtt_integration_not_duplicated": True,
        "manager_business_state_fresh": True,
        "board_access": False,
    }


def _test_executor_package(tool, tmp_path: Path) -> dict[str, object]:
    root = tmp_path / "executor-package"
    authority = root / "tools" / "n3w_t1_f4_reboot_authority.py"
    authority.parent.mkdir(parents=True)
    authority.write_text("executor", encoding="utf-8")
    binding = {
        "sha256": tool._sha256(authority),
        "size": authority.stat().st_size,
    }
    return {
        "root": root,
        "files": {
            "tools/n3w_t1_f4_reboot_authority.py": binding,
        },
    }


def test_finalize_reboot_acceptance_persists_terminal_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    claim_path = tmp_path / "reboot-claim.json"
    pre_boot = "a" * 64
    post_boot = "b" * 64
    installed_source = "c" * 40
    installed_manifest = "d" * 64
    executor_source = "1" * 40
    executor_manifest = "2" * 64
    pending = {
        "schema": tool.SCHEMA_REBOOT,
        "stage": "REBOOT_PENDING",
        "source_head": installed_source,
        "control_manifest_sha256": installed_manifest,
        "f4_transaction_sha256": "e" * 64,
        "pre_certificate_snapshot_sha256": "f" * 64,
        "reboot_authorization_id": "N3W_T1_F4_REBOOT_SUCCESSOR_LIVE_20261016_01",
        "reboot_authorization_claimed": True,
        "reboot_authorization_consumed": True,
        "reboot_authorization_replay_allowed": False,
        "pre_boot_id_sha256": pre_boot,
        "reboot_acceptance_passed": False,
        "board_access": False,
    }
    claim_path.write_text(
        json.dumps(pending, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    claim_path.chmod(0o600)
    pending_sha = tool._sha256(claim_path)
    package = _test_executor_package(tool, tmp_path)

    monkeypatch.setattr(tool, "REBOOT_CLAIM_PATH", claim_path)
    monkeypatch.setattr(tool, "_exclusive", lambda: nullcontext())
    monkeypatch.setattr(tool, "_package", lambda *_args, **_kwargs: package)
    monkeypatch.setattr(tool, "_validate_recovery_entrypoint", lambda _package: None)

    observed_installed = {}

    def verify_installed(**kwargs):
        observed_installed.update(kwargs)

    monkeypatch.setattr(
        tool,
        "_verify_installed_control_material_binding",
        verify_installed,
    )
    monkeypatch.setattr(tool, "_boot_id_sha256", lambda: post_boot)
    monkeypatch.setattr(
        tool,
        "_post_reboot_acceptance_report",
        lambda: _test_acceptance_report(
            tool,
            pre_boot=pre_boot,
            post_boot=post_boot,
        ),
    )
    monkeypatch.setattr(
        tool,
        "_record",
        lambda path, _mode: json.loads(path.read_text(encoding="utf-8")),
    )

    def write_record(path: Path, document: dict[str, object]) -> None:
        path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        path.chmod(0o600)

    monkeypatch.setattr(tool, "_atomic_write_record", write_record)

    result = tool.finalize_reboot_acceptance(
        package_root=package["root"],
        source_head=executor_source,
        manifest_sha256=executor_manifest,
        expected_installed_source_head=installed_source,
        expected_installed_manifest_sha256=installed_manifest,
        expected_transaction_sha256="e" * 64,
        expected_pending_claim_sha256=pending_sha,
    )

    accepted = json.loads(claim_path.read_text(encoding="utf-8"))
    assert accepted["stage"] == "REBOOT_ACCEPTED"
    assert accepted["source_head"] == installed_source
    assert accepted["control_manifest_sha256"] == installed_manifest
    assert accepted["acceptance_finalizer_source_head"] == executor_source
    assert accepted["acceptance_finalizer_manifest_sha256"] == executor_manifest
    assert accepted["reboot_acceptance_passed"] is True
    assert accepted["reboot_acceptance_finalized"] is True
    assert accepted["reboot_executed"] is True
    assert accepted["reboot_authorization_consumed"] is True
    assert accepted["reboot_authorization_replay_allowed"] is False
    assert accepted["pre_acceptance_claim_sha256"] == pending_sha
    assert accepted["post_boot_id_sha256"] == post_boot
    assert observed_installed["source_head"] == installed_source
    assert observed_installed["manifest_sha256"] == installed_manifest
    assert result["state"] == "REBOOT_ACCEPTED"
    assert result["accepted_claim_sha256"] == tool._sha256(claim_path)


def test_finalize_reboot_acceptance_rejects_pending_claim_hash_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    claim_path = tmp_path / "reboot-claim.json"
    claim_path.write_text("{}\n", encoding="utf-8")
    claim_path.chmod(0o600)
    package = _test_executor_package(tool, tmp_path)
    monkeypatch.setattr(tool, "REBOOT_CLAIM_PATH", claim_path)
    monkeypatch.setattr(tool, "_exclusive", lambda: nullcontext())
    monkeypatch.setattr(tool, "_package", lambda *_args, **_kwargs: package)
    monkeypatch.setattr(tool, "_validate_recovery_entrypoint", lambda _package: None)
    with pytest.raises(
        tool.AuthorityError,
        match="reboot_pending_claim_sha256_mismatch",
    ):
        tool.finalize_reboot_acceptance(
            package_root=package["root"],
            source_head="1" * 40,
            manifest_sha256="2" * 64,
            expected_installed_source_head="a" * 40,
            expected_installed_manifest_sha256="b" * 64,
            expected_transaction_sha256="c" * 64,
            expected_pending_claim_sha256="d" * 64,
        )


def test_verify_reboot_accepted_is_read_only_terminal_check(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    claim_path = tmp_path / "reboot-claim.json"
    pre_boot = "a" * 64
    post_boot = "b" * 64
    installed_source = "c" * 40
    installed_manifest = "d" * 64
    executor_source = "1" * 40
    executor_manifest = "2" * 64
    package = _test_executor_package(tool, tmp_path)
    executor_sha = package["files"]["tools/n3w_t1_f4_reboot_authority.py"]["sha256"]
    report = _test_acceptance_report(tool, pre_boot=pre_boot, post_boot=post_boot)
    accepted = {
        "schema": tool.SCHEMA_REBOOT,
        "stage": "REBOOT_ACCEPTED",
        "source_head": installed_source,
        "control_manifest_sha256": installed_manifest,
        "f4_transaction_sha256": "e" * 64,
        "reboot_authorization_id": "N3W_T1_F4_REBOOT_SUCCESSOR_LIVE_20261016_01",
        "reboot_authorization_claimed": True,
        "reboot_authorization_consumed": True,
        "reboot_authorization_replay_allowed": False,
        "pre_boot_id_sha256": pre_boot,
        "post_boot_id_sha256": post_boot,
        "reboot_acceptance_passed": True,
        "reboot_acceptance_finalized": True,
        "reboot_executed": True,
        "pre_acceptance_claim_sha256": "f" * 64,
        "acceptance_report_sha256": tool._canonical_sha(report),
        "acceptance_report": report,
        "acceptance_finalizer_source_head": executor_source,
        "acceptance_finalizer_manifest_sha256": executor_manifest,
        "acceptance_finalizer_executor_sha256": executor_sha,
        "board_access": False,
    }
    claim_path.write_text(
        json.dumps(accepted, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    claim_path.chmod(0o600)
    accepted_sha = tool._sha256(claim_path)

    monkeypatch.setattr(tool, "REBOOT_CLAIM_PATH", claim_path)
    monkeypatch.setattr(tool, "_package", lambda *_args, **_kwargs: package)
    monkeypatch.setattr(tool, "_validate_recovery_entrypoint", lambda _package: None)
    monkeypatch.setattr(
        tool,
        "_verify_installed_control_material_binding",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(tool, "_boot_id_sha256", lambda: post_boot)
    monkeypatch.setattr(
        tool,
        "_record",
        lambda path, _mode: json.loads(path.read_text(encoding="utf-8")),
    )

    before = claim_path.read_bytes()
    result = tool.verify_reboot_accepted(
        package_root=package["root"],
        source_head=executor_source,
        manifest_sha256=executor_manifest,
        expected_installed_source_head=installed_source,
        expected_installed_manifest_sha256=installed_manifest,
        expected_transaction_sha256="e" * 64,
        expected_accepted_claim_sha256=accepted_sha,
    )
    after = claim_path.read_bytes()

    assert before == after
    assert result["state"] == "REBOOT_ACCEPTED"
    assert result["reboot_acceptance_finalized"] is True
    assert result["accepted_claim_sha256"] == accepted_sha


def test_material_binding_is_post_reboot_safe_without_pre_reboot_runtime_checks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    state_root = tmp_path / "state"
    state_root.mkdir(mode=0o700)
    transaction_path = state_root / "F4_ACTIVATION_TRANSACTION.json"
    install_path = state_root / "F4_REBOOT_SUCCESSOR_INSTALL_AUTHORIZATION.json"
    manifest_path = tmp_path / "reboot-successor-manifest.json"
    target = tmp_path / "guard.py"
    target.write_text("exact-control", encoding="utf-8")
    target.chmod(0o755)

    transaction = {
        "stage": "PERSISTENCE_ENABLED",
        "runtime_acceptance_passed": True,
        "persistence_enabled": True,
        "broker_services_persistence_enabled": True,
        "certificate_first_audit_passed": True,
        "certificate_timer_enabled": True,
        "pre_reboot_ready": True,
        "board_access": False,
    }
    transaction_path.write_text(
        json.dumps(transaction, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    transaction_path.chmod(0o600)
    transaction_sha = tool._sha256(transaction_path)

    source_head = "a" * 40
    target_sha = tool._sha256(target)
    manifest = {
        "schema": tool.PACKAGE_SCHEMA,
        "source_head": source_head,
    }
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    manifest_path.chmod(0o644)
    manifest_sha = tool._sha256(manifest_path)

    install = {
        "schema": tool.SCHEMA_INSTALL,
        "stage": "CONTROL_READY",
        "source_head": source_head,
        "control_manifest_sha256": manifest_sha,
        "f4_transaction_sha256": transaction_sha,
        "control_repair_authorization_claimed": True,
        "control_repair_authorization_consumed": True,
        "control_repair_authorization_replay_allowed": False,
        "installation_verified": True,
        "board_access": False,
        "files": {
            "guard.py": {
                "sha256": target_sha,
                "size": target.stat().st_size,
                "target": str(target),
                "mode": 0o755,
            }
        },
    }
    install_path.write_text(
        json.dumps(install, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    install_path.chmod(0o600)

    monkeypatch.setattr(tool, "F4_TRANSACTION", transaction_path)
    monkeypatch.setattr(tool, "INSTALL_CLAIM_PATH", install_path)
    monkeypatch.setattr(tool, "CONTROL_MANIFEST", manifest_path)
    monkeypatch.setattr(tool, "CONTROL_TARGETS", {"guard.py": (target, 0o755)})
    monkeypatch.setattr(
        tool,
        "_record",
        lambda path, _mode: json.loads(path.read_text(encoding="utf-8")),
    )
    monkeypatch.setattr(
        tool,
        "_validate_recovery_ready_link",
        lambda *_args, **_kwargs: None,
    )

    def pre_reboot_must_not_run(_expected_sha: str):
        raise AssertionError("pre_reboot_runtime_check_reused")

    monkeypatch.setattr(tool, "_base_pre_reboot", pre_reboot_must_not_run)

    observed_transaction, observed_claim = (
        tool._verify_installed_control_material_binding(
            source_head=source_head,
            manifest_sha256=manifest_sha,
            expected_transaction_sha256=transaction_sha,
        )
    )

    assert observed_transaction == transaction
    assert observed_claim == install
