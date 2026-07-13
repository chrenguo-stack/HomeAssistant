from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path
from typing import Any

import pytest

import greenhouse_manager.t1_manager_identity_migration_production_host_adapters as module
from greenhouse_manager.t1_manager_identity_migration_production_host_adapters import (
    LiveProductionManagerDriver,
    ManagerHostBinding,
    ManagerProductionHostAdaptersError,
    ManagerProductionHostTransactionAdapters,
)

USERNAME = "gh-manager-user"
CLIENT_ID = "gh-manager-client"
PASSWORD = "manager-password"


def _write(path: Path, value: str, mode: int = 0o600) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(value, encoding="utf-8")
    path.chmod(mode)
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rollback_item(path: Path, archive_path: str, kind: str) -> dict[str, object]:
    stat = path.stat()
    return {
        "archive_path": archive_path,
        "source_path": str(path.resolve()),
        "kind": kind,
        "mode": stat.st_mode & 0o777,
        "uid": stat.st_uid,
        "gid": stat.st_gid,
        "size": stat.st_size,
        "sha256": _sha(path),
    }


def _write_archive(
    path: Path,
    rollback: dict[str, Any],
    payloads: dict[str, bytes],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    by_name = {str(item["archive_path"]): item for item in rollback["files"]}
    with tarfile.open(path, mode="w:gz") as archive:
        manifest = json.dumps(rollback, sort_keys=True).encode()
        manifest_info = tarfile.TarInfo("rollback-manifest.json")
        manifest_info.size = len(manifest)
        manifest_info.mode = 0o600
        archive.addfile(manifest_info, io.BytesIO(manifest))
        for name, payload in payloads.items():
            item = by_name[name]
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = int(item["mode"])
            info.uid = int(item["uid"])
            info.gid = int(item["gid"])
            archive.addfile(info, io.BytesIO(payload))
    path.chmod(0o600)


def _fixture(
    tmp_path: Path,
) -> tuple[ManagerHostBinding, dict[str, Any], dict[str, Path]]:
    tmp_path.chmod(0o700)
    working = tmp_path / "compose"
    working.mkdir(mode=0o700)
    config = _write(
        working / "compose.yaml",
        "services:\n  greenhouse-manager:\n    image: test\n",
    )
    environment = _write(working / ".env", "SYSTEM_ID=test\n")
    secret_root = tmp_path / "secrets"
    secret_root.mkdir(mode=0o700)
    material = tmp_path / "material"
    material_environment = _write(
        material / "manager.env",
        f"GH_MQTT_USERNAME={USERNAME}\n"
        "GH_MQTT_PASSWORD_FILE=/run/secrets/gh_manager_mqtt_password\n"
        f"GH_MQTT_CLIENT_ID={CLIENT_ID}\n",
    )
    material_password = _write(material / "password", PASSWORD + "\n")
    material_overlay = _write(
        material / "overlay.yaml",
        "services:\n  greenhouse-manager:\n    environment:\n"
        f"      GH_MQTT_USERNAME: {USERNAME}\n",
    )
    binding = ManagerHostBinding(
        project="greenhouse",
        working_dir=working,
        config_files=(config,),
        environment_file=environment,
        secret_root=secret_root,
        password_target=secret_root / "manager/password",
        auth_environment_target=working / "manager-auth.env",
        overlay_target=working / "docker-compose.manager-auth.yml",
        material_environment=material_environment,
        material_password=material_password,
        material_overlay=material_overlay,
        username=USERNAME,
        client_id=CLIENT_ID,
    )
    config_item = _rollback_item(
        config,
        "compose/config/000.yaml",
        "compose_config",
    )
    env_item = _rollback_item(
        environment,
        "compose/environment/.env",
        "compose_environment",
    )
    rollback: dict[str, Any] = {
        "manager_only": True,
        "restart_scope": ["greenhouse-manager"],
        "forbidden_service_changes": ["mosquitto", "homeassistant", "node"],
        "files": [config_item, env_item],
    }
    execution = tmp_path / "execution"
    execution.mkdir(mode=0o700)
    _write_archive(
        execution / "fresh-manager-rollback.tar.gz",
        rollback,
        {
            "compose/config/000.yaml": config.read_bytes(),
            "compose/environment/.env": environment.read_bytes(),
        },
    )
    driver_contract = _write(tmp_path / "driver.json", "{}\n")
    preparation = tmp_path / "preparation"
    preparation.mkdir(mode=0o700)
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    return binding, rollback, {
        "config": config,
        "environment": environment,
        "execution": execution,
        "driver_contract": driver_contract,
        "preparation": preparation,
        "workspace": workspace,
    }


class FakeDriver:
    def __init__(self, *, audit_ok: bool = True) -> None:
        self.audit_ok = audit_ok
        self.calls: list[str] = []

    def recreate_manager(
        self,
        *,
        environment_file: Path,
        password_file: Path,
        overlay_file: Path,
    ) -> None:
        assert environment_file.is_file()
        assert password_file.read_text(encoding="utf-8").strip() == PASSWORD
        assert overlay_file.is_file()
        self.calls.append("recreate")

    def verify_authenticated_identity(self, username: str, client_id: str) -> None:
        assert username == USERNAME
        assert client_id == CLIENT_ID
        self.calls.append("identity")

    def verify_ingress_subscription(self) -> None:
        self.calls.append("ingress")

    def verify_canonical_publication(self) -> None:
        self.calls.append("canonical")

    def verify_availability_publication(self) -> None:
        self.calls.append("availability")

    def verify_discovery_publication(self) -> None:
        self.calls.append("discovery")

    def verify_reconnect(self) -> None:
        self.calls.append("reconnect")

    def verify_existing_entities(self) -> None:
        self.calls.append("entities")

    def postactivation_audit(self) -> dict[str, object]:
        self.calls.append("audit")
        return {
            "checks": {"all": self.audit_ok},
            "manager_identity_migrated": self.audit_ok,
            "manager_authenticated": True,
            "ingress_subscription_verified": True,
            "canonical_publication_verified": True,
            "availability_publication_verified": True,
            "discovery_publication_verified": True,
            "reconnect_verified": True,
            "existing_entities_verified": True,
            "rollback_required": not self.audit_ok,
            "node_credentials_delivered": False,
            "preserve_anonymous": True,
            "anonymous_closure_enabled": False,
        }

    def recreate_after_rollback(self) -> None:
        self.calls.append("rollback_recreate")

    def verify_legacy_anonymous_path(self) -> None:
        self.calls.append("legacy")


class FakeProbe(FakeDriver):
    def __init__(self) -> None:
        super().__init__()


class FakeRunner:
    def __init__(self, *, fail_compose: bool = False) -> None:
        self.fail_compose = fail_compose
        self.commands: list[tuple[str, ...]] = []

    def run(self, command: tuple[str, ...]) -> tuple[int, str]:
        self.commands.append(command)
        if command == ("docker", "inspect", "greenhouse-manager"):
            return 0, json.dumps(
                [{"State": {"Status": "running"}, "RestartCount": 0}]
            )
        if self.fail_compose:
            return 1, "compose failed"
        return 0, ""


def _adapters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    driver: FakeDriver | None = None,
) -> tuple[
    ManagerProductionHostTransactionAdapters,
    ManagerHostBinding,
    dict[str, Path],
    FakeDriver,
]:
    binding, rollback, paths = _fixture(tmp_path)
    monkeypatch.setattr(
        module,
        "_load_binding",
        lambda *_args, **_kwargs: (binding, rollback, {}),
    )
    active_driver = driver or FakeDriver()
    adapters = ManagerProductionHostTransactionAdapters(
        paths["driver_contract"],
        paths["execution"],
        paths["preparation"],
        paths["workspace"],
        driver=active_driver,
    )
    return adapters, binding, paths, active_driver


def test_prepare_captures_snapshot_without_live_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapters, binding, _paths, driver = _adapters(tmp_path, monkeypatch)

    report = adapters.prepare()

    assert report["production_transaction_adapters_installed"] is True
    assert report["production_manager_driver_installed"] is True
    assert report["execution_entrypoint_installed"] is False
    assert report["current_services_modified"] is False
    assert not binding.password_target.exists()
    assert not binding.auth_environment_target.exists()
    assert not binding.overlay_target.exists()
    assert driver.calls == []


def test_manager_only_mutation_and_complete_rollback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapters, binding, paths, driver = _adapters(tmp_path, monkeypatch)
    original_config = paths["config"].read_bytes()
    original_environment = paths["environment"].read_bytes()

    mutation = adapters.mutation_executor()

    assert mutation["greenhouse_manager_recreated"] is True
    assert mutation["mosquitto_modified"] is False
    assert mutation["homeassistant_modified"] is False
    assert mutation["nodes_modified"] is False
    assert binding.password_target.is_file()
    assert binding.auth_environment_target.is_file()
    assert binding.overlay_target.is_file()
    assert driver.calls == [
        "recreate",
        "identity",
        "ingress",
        "canonical",
        "availability",
        "discovery",
        "reconnect",
        "entities",
    ]

    paths["config"].write_text("drifted\n", encoding="utf-8")
    paths["environment"].write_text("drifted\n", encoding="utf-8")
    rollback = adapters.rollback_executor()

    assert rollback["rollback_completed"] is True
    assert paths["config"].read_bytes() == original_config
    assert paths["environment"].read_bytes() == original_environment
    assert not binding.password_target.exists()
    assert not binding.auth_environment_target.exists()
    assert not binding.overlay_target.exists()
    assert driver.calls[-3:] == ["rollback_recreate", "legacy", "entities"]


def test_postactivation_audit_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapters, _binding, _paths, _driver = _adapters(
        tmp_path,
        monkeypatch,
        driver=FakeDriver(audit_ok=False),
    )

    with pytest.raises(
        ManagerProductionHostAdaptersError,
        match="postactivation audit failed",
    ):
        adapters.postactivation_auditor()


def test_symlink_mutation_target_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapters, binding, _paths, _driver = _adapters(tmp_path, monkeypatch)
    target = binding.working_dir / "unexpected"
    target.write_text("unsafe", encoding="utf-8")
    binding.overlay_target.symlink_to(target)

    with pytest.raises(
        ManagerProductionHostAdaptersError,
        match="cannot be a symlink",
    ):
        adapters.mutation_executor()


def test_unexpected_rollback_source_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding, rollback, paths = _fixture(tmp_path)
    outside = _write(tmp_path / "outside", "outside\n")
    rollback["files"][0]["source_path"] = str(outside)
    _write_archive(
        paths["execution"] / "fresh-manager-rollback.tar.gz",
        rollback,
        {
            "compose/config/000.yaml": outside.read_bytes(),
            "compose/environment/.env": paths["environment"].read_bytes(),
        },
    )
    monkeypatch.setattr(
        module,
        "_load_binding",
        lambda *_args, **_kwargs: (binding, rollback, {}),
    )
    adapters = ManagerProductionHostTransactionAdapters(
        paths["driver_contract"],
        paths["execution"],
        paths["preparation"],
        paths["workspace"],
        driver=FakeDriver(),
    )

    with pytest.raises(
        ManagerProductionHostAdaptersError,
        match="source path is unexpected",
    ):
        adapters.prepare()


def test_live_driver_uses_exact_manager_only_compose_command(tmp_path: Path) -> None:
    binding, _rollback, _paths = _fixture(tmp_path)
    _write(binding.password_target, PASSWORD + "\n")
    _write(binding.auth_environment_target, "GH_MQTT_USERNAME=test\n")
    _write(binding.overlay_target, "services: {}\n")
    runner = FakeRunner()
    driver = LiveProductionManagerDriver(binding, probe=FakeProbe(), runner=runner)

    driver.recreate_manager(
        environment_file=binding.auth_environment_target,
        password_file=binding.password_target,
        overlay_file=binding.overlay_target,
    )

    compose = runner.commands[0]
    assert compose[:2] == ("docker", "compose")
    assert compose[-5:] == (
        "up",
        "-d",
        "--no-deps",
        "--force-recreate",
        "greenhouse-manager",
    )
    assert "mosquitto" not in compose
    assert "homeassistant" not in compose
    assert str(binding.overlay_target) in compose
    assert runner.commands[1] == ("docker", "inspect", "greenhouse-manager")

    driver.recreate_after_rollback()
    rollback_compose = runner.commands[2]
    assert str(binding.overlay_target) not in rollback_compose
    assert rollback_compose[-1] == "greenhouse-manager"
    assert runner.commands[3] == ("docker", "inspect", "greenhouse-manager")


def test_live_driver_rejects_unbound_paths_before_command(tmp_path: Path) -> None:
    binding, _rollback, _paths = _fixture(tmp_path)
    runner = FakeRunner()
    driver = LiveProductionManagerDriver(binding, probe=FakeProbe(), runner=runner)

    with pytest.raises(
        ManagerProductionHostAdaptersError,
        match="do not match",
    ):
        driver.recreate_manager(
            environment_file=tmp_path / "wrong-env",
            password_file=binding.password_target,
            overlay_file=binding.overlay_target,
        )

    assert runner.commands == []


def test_live_driver_reports_compose_failure(tmp_path: Path) -> None:
    binding, _rollback, _paths = _fixture(tmp_path)
    _write(binding.password_target, PASSWORD + "\n")
    _write(binding.auth_environment_target, "GH_MQTT_USERNAME=test\n")
    _write(binding.overlay_target, "services: {}\n")
    runner = FakeRunner(fail_compose=True)
    driver = LiveProductionManagerDriver(binding, probe=FakeProbe(), runner=runner)

    with pytest.raises(
        ManagerProductionHostAdaptersError,
        match="recreate failed",
    ):
        driver.recreate_manager(
            environment_file=binding.auth_environment_target,
            password_file=binding.password_target,
            overlay_file=binding.overlay_target,
        )

    assert len(runner.commands) == 1
    assert runner.commands[0][-1] == "greenhouse-manager"
