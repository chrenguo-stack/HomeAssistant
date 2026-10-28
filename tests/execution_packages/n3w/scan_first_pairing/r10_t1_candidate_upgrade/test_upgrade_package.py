from __future__ import annotations

import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[5]
BUILDER_PATH = (
    ROOT
    / "tools/execution_packages/n3w/scan_first_pairing/"
      "r10_t1_candidate_upgrade/package_builder.py"
)
EXECUTOR_PATH = (
    ROOT
    / "tools/execution_packages/n3w/scan_first_pairing/"
      "r10_t1_candidate_upgrade/live_upgrade.py"
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load(BUILDER_PATH, "r10_upgrade_builder")
executor = load(EXECUTOR_PATH, "r10_upgrade_executor")


def write(root: Path, relative: str, payload: bytes = b"x\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def materialize_source_roots(tmp_path: Path) -> tuple[Path, Path]:
    old = tmp_path / "old"
    target = tmp_path / "target"
    old.mkdir()
    target.mkdir()
    for group in (builder.LIVE_FILES,):
        for spec in group.values():
            old_rel = spec.get("predecessor_source")
            target_rel = spec["target_source"]
            if old_rel is not None:
                write(old, str(old_rel), ("old:" + str(old_rel)).encode())
            if not (target / str(target_rel)).exists():
                write(
                    target,
                    str(target_rel),
                    ("target:" + str(target_rel)).encode(),
                )
    return old, target


def test_package_scope_is_manager_only_and_preserves_f4_launcher() -> None:
    assert set(builder.LIVE_FILES) == {
        "compose",
        "services_unit",
        "dispatcher",
        "registration_unit",
        "registration_guard",
        "trusted_lan_authority",
    }
    assert {
        name
        for name, value in builder.LIVE_FILES.items()
        if value["f4_bound"]
    } == {"compose", "services_unit", "dispatcher"}
    all_targets = {
        value["target"]
        for value in builder.LIVE_FILES.values()
    }
    assert "/usr/local/sbin/n3w-t1-f4-activation" not in all_targets
    assert (
        "/opt/HomeAssistant/tools/n3w_t1_f4_activation_host.py"
        not in all_targets
    )


def test_builder_creates_exact_small_scope_package(tmp_path: Path) -> None:
    old, target = materialize_source_roots(tmp_path)
    manager_tar = write(tmp_path, "manager.tar", b"manager-image")
    live_executor = write(tmp_path, "executor.py", b"#!/usr/bin/python3\n")
    distributions = write(
        tmp_path,
        "distributions.json",
        b'[{"name":"greenhouse-manager","version":"0.4.99"}]\n',
    )
    output = tmp_path / "package"

    args = type(
        "Args",
        (),
        {
            "output": str(output),
            "predecessor_source_root": str(old),
            "target_source_root": str(target),
            "predecessor_source": builder.PREDECESSOR_SOURCE,
            "target_source": builder.TARGET_SOURCE,
            "package_head": "a" * 40,
            "manager_tar": str(manager_tar),
            "manager_image": builder.TARGET_MANAGER_IMAGE,
            "manager_image_id": "sha256:" + "1" * 64,
            "manager_image_size_bytes": 123456,
            "base_image_ref": builder.BASE_IMAGE_REF,
            "base_arm64_digest": "sha256:" + "2" * 64,
            "base_image_id": "sha256:" + "3" * 64,
            "executor": str(live_executor),
            "python_distributions": str(distributions),
        },
    )()
    manifest = builder.build(args)
    assert manifest["policy"]["homeassistant_image_included"] is False
    assert manifest["policy"]["broker_image_included"] is False
    assert manifest["manager"]["historical_byte_continuity_claimed"] is False
    assert manifest["manager"]["future_rebuild_byte_identity_claimed"] is False
    assert manifest["manager"]["python_distributions"]["count"] == 1
    assert manifest["capacity"]["upgrade_emergency_reserve_bytes"] == 2 * 1024**3
    verified = builder.verify(output)
    assert verified["target_source"] == builder.TARGET_SOURCE


def test_builder_rejects_extra_member(tmp_path: Path) -> None:
    old, target = materialize_source_roots(tmp_path)
    manager_tar = write(tmp_path, "manager.tar", b"manager-image")
    live_executor = write(tmp_path, "executor.py", b"x")
    distributions = write(
        tmp_path,
        "distributions.json",
        b'[{"name":"greenhouse-manager","version":"0.4.99"}]\n',
    )
    output = tmp_path / "package"
    args = type(
        "Args",
        (),
        {
            "output": str(output),
            "predecessor_source_root": str(old),
            "target_source_root": str(target),
            "predecessor_source": builder.PREDECESSOR_SOURCE,
            "target_source": builder.TARGET_SOURCE,
            "package_head": "a" * 40,
            "manager_tar": str(manager_tar),
            "manager_image": builder.TARGET_MANAGER_IMAGE,
            "manager_image_id": "sha256:" + "1" * 64,
            "manager_image_size_bytes": 123,
            "base_image_ref": builder.BASE_IMAGE_REF,
            "base_arm64_digest": "sha256:" + "2" * 64,
            "base_image_id": "sha256:" + "3" * 64,
            "executor": str(live_executor),
            "python_distributions": str(distributions),
        },
    )()
    builder.build(args)
    write(output, "unexpected.txt", b"bad")
    with pytest.raises(builder.PackageError, match="package_file_set_invalid"):
        builder.verify(output)


def f4_predecessor() -> dict:
    installed = {
        target: {
            "sha256": "old-" + str(index),
            "size": 100 + index,
            "mode": 0o644,
            "uid": 0,
            "gid": 0,
        }
        for index, target in enumerate(sorted(executor.F4_CHANGED_TARGETS))
    }
    installed["/other/f4-bound"] = {
        "sha256": "same",
        "size": 9,
        "mode": 0o600,
        "uid": 0,
        "gid": 0,
    }
    return {
        "schema": "gh.n3w-t1-f4-activation-transaction/1",
        "authorization_id": "N3W_T1_F4_ORIGINAL",
        "release_id": "old-release",
        "host_instance_id": "host",
        "system_id": "private-system-id",
        "system_id_sha256": "s" * 64,
        "package_source_head": "p" * 40,
        "package_manifest_sha256": "m" * 64,
        "runtime_acceptance_report_sha256": "r" * 64,
        "certificate_status_sha256": "c" * 64,
        "installed_files": installed,
        "stage": "PERSISTENCE_ENABLED",
        "authorization_claimed": True,
        "authorization_consumed": True,
        "replay_allowed": False,
        "other_history": ["kept"],
    }


def f4_manifest() -> dict:
    live = {}
    for index, target in enumerate(sorted(executor.F4_CHANGED_TARGETS)):
        live[f"f{index}"] = {
            "target": target,
            "f4_bound": True,
        }
    live["new"] = {
        "target": "/new/not-f4-bound",
        "f4_bound": False,
    }
    return {"live_files": live}


def test_f4_successor_changes_only_installed_files_and_upgrade_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    predecessor = f4_predecessor()

    def fake_binding(path: Path) -> dict:
        assert str(path) in executor.F4_CHANGED_TARGETS
        return {
            "sha256": "new-" + path.name,
            "size": 999,
            "mode": 0o644,
            "uid": 0,
            "gid": 0,
        }

    monkeypatch.setattr(executor, "file_binding", fake_binding)
    successor = executor.successor_f4_document(
        predecessor,
        manifest=f4_manifest(),
        authorization_id="N3W_R10_T1_CANDIDATE_UPGRADE_TEST",
        manifest_sha256="f" * 64,
    )

    for key, value in predecessor.items():
        if key == "installed_files":
            continue
        assert successor[key] == value
    assert successor["other_history"] == ["kept"]
    assert successor["package_source_head"] == "p" * 40
    assert successor["runtime_acceptance_report_sha256"] == "r" * 64
    assert successor["r10_candidate_upgrade_committed"] is False
    assert (
        successor["r10_candidate_upgrade_predecessor_installed_files_sha256"]
        == executor.canonical_sha256(predecessor["installed_files"])
    )


def test_f4_successor_requires_exact_three_changed_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        executor,
        "file_binding",
        lambda _path: {
            "sha256": "x",
            "size": 1,
            "mode": 0o644,
            "uid": 0,
            "gid": 0,
        },
    )
    manifest = f4_manifest()
    manifest["live_files"].pop("f0")
    with pytest.raises(executor.UpgradeError, match="f4_changed_target_set_invalid"):
        executor.successor_f4_document(
            f4_predecessor(),
            manifest=manifest,
            authorization_id="N3W_R10_T1_CANDIDATE_UPGRADE_TEST",
            manifest_sha256="f" * 64,
        )


def test_preclaim_failure_cannot_consume_authorization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    claimed: list[bool] = []
    monkeypatch.setattr(executor, "require_root", lambda: None)
    monkeypatch.setattr(executor, "validate_package", lambda *_a: {"package_head": "a" * 40})
    monkeypatch.setattr(
        executor,
        "verify_prestate",
        lambda *_a: (_ for _ in ()).throw(executor.UpgradeError("preflight_fail")),
    )
    monkeypatch.setattr(
        executor,
        "claim_upgrade",
        lambda **_k: claimed.append(True),
    )
    with pytest.raises(executor.UpgradeError, match="preflight_fail"):
        executor.execute_apply(
            package_root=tmp_path,
            expected_manifest_sha256="f" * 64,
            authorization_id="N3W_R10_T1_CANDIDATE_UPGRADE_TEST",
            confirmation=executor.CONFIRMATION,
        )
    assert claimed == []


def test_claim_occurs_before_first_mutating_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    manifest = {
        "package_head": "a" * 40,
        "manager": {"image_size_bytes": 1},
        "capacity": {
            "upgrade_emergency_reserve_bytes": 1,
            "runtime_bundle_size_bytes": 1,
        },
    }
    prestate = {
        "system_id": "private",
        "broker": {
            "id": "b",
            "image_id": "bi",
            "image": "broker",
            "started_at": "t",
            "restart_count": 0,
        },
        "homeassistant": {"image": "ha", "image_id": "hai"},
    }
    monkeypatch.setattr(executor, "require_root", lambda: None)
    monkeypatch.setattr(executor, "validate_package", lambda *_a: manifest)
    monkeypatch.setattr(executor, "verify_prestate", lambda *_a: prestate)
    monkeypatch.setattr(executor, "claim_upgrade", lambda **_k: events.append("claim"))
    monkeypatch.setattr(executor, "create_workspace", lambda _a: (events.append("workspace") or tmp_path))
    monkeypatch.setattr(executor, "static_backup", lambda *_a: (events.append("backup") or {"x": {}}))
    monkeypatch.setattr(executor, "advance_upgrade", lambda *_a, **_k: {})
    monkeypatch.setattr(executor, "load_target_manager", lambda *_a: events.append("docker_load"))
    tls_stage = tmp_path / "registration-tls"
    tls_stage.mkdir()
    monkeypatch.setattr(
        executor,
        "generate_registration_tls",
        lambda *_a: tls_stage,
    )
    monkeypatch.setattr(
        executor,
        "container",
        lambda _service: {
            "Id": "b",
            "Image": "bi",
            "RestartCount": 0,
            "State": {"StartedAt": "t", "Running": True},
            "Config": {"Image": "broker"},
        },
    )
    monkeypatch.setattr(executor, "run", lambda *_a, **_k: "")
    monkeypatch.setattr(executor, "manager_state_backup", lambda _w: write(tmp_path, "state.tar", b"x"))
    monkeypatch.setattr(executor.shutil, "disk_usage", lambda _p: type("D", (), {"free": 999999})())
    monkeypatch.setattr(executor, "install_runtime_files", lambda *_a: events.append("install"))
    monkeypatch.setattr(executor, "rewrite_manager_image", lambda *_a, **_k: None)
    monkeypatch.setattr(executor, "install_registration_tls", lambda *_a: None)
    monkeypatch.setattr(
        executor,
        "service_state",
        lambda _u: {"active": "active", "enabled": "enabled", "load": "loaded"},
    )
    monkeypatch.setattr(executor, "trusted_lan_ready", lambda: True)
    monkeypatch.setattr(executor, "write_f4_successor", lambda **_k: None)
    monkeypatch.setattr(executor, "f4_services_eligibility", lambda: None)
    monkeypatch.setattr(
        executor,
        "read_private_json",
        lambda _p: {"installed_files": {}},
    )
    monkeypatch.setattr(
        executor,
        "wait_strict_postcheck",
        lambda _p, _m: {
            "manager": {"image_id": "target"},
        },
    )
    monkeypatch.setattr(executor, "commit_f4_successor", lambda: None)
    monkeypatch.setattr(executor, "rollback", lambda **_k: None)

    result = executor.execute_apply(
        package_root=tmp_path,
        expected_manifest_sha256="f" * 64,
        authorization_id="N3W_R10_T1_CANDIDATE_UPGRADE_TEST",
        confirmation=executor.CONFIRMATION,
    )
    assert result["status"] == "PASS"
    assert events[0] == "claim"
    assert events.index("claim") < events.index("workspace")
    assert events.index("claim") < events.index("docker_load")
    assert events.index("claim") < events.index("install")


def test_executor_has_no_broker_stop_recreate_or_compose_override() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    assert '"stop", BROKER_UNIT' not in source
    assert "--force-recreate" not in source
    assert "compose.override" not in source
    assert "docker compose down" not in source
    assert "docker system prune" not in source


def test_authorization_is_one_shot() -> None:
    assert executor.valid_authorization_id(
        "N3W_R10_T1_CANDIDATE_UPGRADE_20261028_01"
    )
    assert not executor.valid_authorization_id("N3W_T1_F4_OLD")


def test_strict_postcheck_requires_manifest_image_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prestate = {
        "broker": {
            "id": "broker-id",
            "image_id": "broker-image-id",
            "image": "broker-ref",
            "started_at": "same",
            "restart_count": 0,
        },
        "homeassistant": {
            "image": "ha-ref",
            "image_id": "ha-image-id",
        },
    }

    docs = {
        "broker": {
            "Id": "broker-id",
            "Image": "broker-image-id",
            "RestartCount": 0,
            "State": {"StartedAt": "same", "Running": True},
            "Config": {"Image": "broker-ref"},
        },
        "manager": {
            "Id": "manager-id",
            "Image": "wrong-target-image-id",
            "RestartCount": 0,
            "State": {"StartedAt": "new", "Running": True},
            "Config": {"Image": executor.TARGET_MANAGER_IMAGE},
        },
        "homeassistant": {
            "Id": "ha-id",
            "Image": "ha-image-id",
            "RestartCount": 0,
            "State": {"StartedAt": "new", "Running": True},
            "Config": {"Image": "ha-ref"},
        },
    }
    monkeypatch.setattr(
        executor,
        "service_state",
        lambda _u: {"active": "active", "enabled": "enabled", "load": "loaded"},
    )
    monkeypatch.setattr(executor, "container", lambda service: docs[service])
    with pytest.raises(executor.UpgradeError, match="target_manager_not_running"):
        executor.strict_postcheck(
            prestate,
            {"manager": {"image_id": "expected-target-image-id"}},
        )


def test_broker_dynsec_is_readonly_continuity_authority() -> None:
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    assert str(executor.BROKER_DYNSEC) == (
        "/var/lib/n3wfc4-broker/dynamic-security.json"
    )
    assert "broker_dynsec_sha256" in source
    assert "broker_dynsec_changed" in source
    assert "rollback_broker_dynsec_changed" in source
    assert "atomic_write_bytes(\n        BROKER_DYNSEC" not in source
    assert "shutil.copyfile(\n        BROKER_DYNSEC" not in source
    assert "BROKER_DYNSEC.unlink" not in source


def test_historical_opt_homeassistant_tree_is_not_a_live_upgrade_target() -> None:
    targets = {
        str(record["target"])
        for record in builder.LIVE_FILES.values()
    }
    assert all(
        not target.startswith("/opt/HomeAssistant/")
        for target in targets
    )
    source = EXECUTOR_PATH.read_text(encoding="utf-8")
    assert "source_overlay" not in source
    assert 'Path("/opt/HomeAssistant")' not in source


def test_live_executor_self_binding_matches_packaged_executor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    old, target = materialize_source_roots(tmp_path)
    manager_tar = write(tmp_path, "manager.tar", b"manager-image")
    distributions = write(
        tmp_path,
        "distributions.json",
        b'[{"name":"greenhouse-manager","version":"0.4.99"}]\n',
    )
    output = tmp_path / "package"
    args = type(
        "Args",
        (),
        {
            "output": str(output),
            "predecessor_source_root": str(old),
            "target_source_root": str(target),
            "predecessor_source": builder.PREDECESSOR_SOURCE,
            "target_source": builder.TARGET_SOURCE,
            "package_head": "a" * 40,
            "manager_tar": str(manager_tar),
            "manager_image": builder.TARGET_MANAGER_IMAGE,
            "manager_image_id": "sha256:" + "1" * 64,
            "manager_image_size_bytes": 123,
            "base_image_ref": builder.BASE_IMAGE_REF,
            "base_arm64_digest": "sha256:" + "2" * 64,
            "base_image_id": "sha256:" + "3" * 64,
            "executor": str(EXECUTOR_PATH),
            "python_distributions": str(distributions),
        },
    )()
    builder.build(args)
    manifest_sha = builder.sha256_file(output / "manifest.json")
    doc = executor.validate_package(output, manifest_sha)
    assert doc["executor"]["sha256"] == executor.sha256_file(EXECUTOR_PATH)

    wrong = write(tmp_path, "wrong-executor.py", b"wrong\n")
    monkeypatch.setattr(executor, "__file__", str(wrong))
    with pytest.raises(
        executor.UpgradeError,
        match="running_executor_binding_invalid",
    ):
        executor.validate_package(output, manifest_sha)


def test_postupgrade_readiness_waits_for_transient_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}
    timeline = iter([0.0, 0.5, 1.0, 1.5])

    def fake_monotonic() -> float:
        return next(timeline)

    def fake_postcheck(_prestate, _manifest):
        calls["count"] += 1
        if calls["count"] == 1:
            raise executor.UpgradeError(
                "registration_listener_postcheck_failed"
            )
        return {"status": "ready"}

    monkeypatch.setattr(executor.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(executor.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(executor, "strict_postcheck", fake_postcheck)
    result = executor.wait_strict_postcheck(
        {},
        {},
        timeout_seconds=10,
        poll_seconds=1,
    )
    assert result == {"status": "ready"}
    assert calls["count"] == 2


def test_postupgrade_readiness_does_not_wait_on_broker_contradiction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        executor,
        "strict_postcheck",
        lambda _p, _m: (_ for _ in ()).throw(
            executor.UpgradeError("broker_continuity_failed")
        ),
    )
    with pytest.raises(
        executor.UpgradeError,
        match="broker_continuity_failed",
    ):
        executor.wait_strict_postcheck(
            {},
            {},
            timeout_seconds=10,
            poll_seconds=1,
        )


def test_successor_live_file_postcheck_binds_all_live_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    live = {}
    for index, (name, record) in enumerate(builder.LIVE_FILES.items()):
        path = tmp_path / f"live-{index}"
        path.write_bytes((name + "\n").encode())
        os.chmod(path, int(record["mode"]))
        live[name] = {
            "target": str(path),
            "sha256": executor.sha256_file(path),
            "size": path.stat().st_size,
            "mode": int(record["mode"]),
        }

    real_binding = executor.file_binding

    def fake_binding(path: Path) -> dict:
        result = real_binding(path)
        result["uid"] = 0
        result["gid"] = 0
        return result

    monkeypatch.setattr(executor, "file_binding", fake_binding)
    executor.verify_successor_live_files({"live_files": live})

    first = next(iter(live.values()))
    Path(first["target"]).write_bytes(b"drift\n")
    with pytest.raises(
        executor.UpgradeError,
        match="successor_live_file_drift",
    ):
        executor.verify_successor_live_files({"live_files": live})
