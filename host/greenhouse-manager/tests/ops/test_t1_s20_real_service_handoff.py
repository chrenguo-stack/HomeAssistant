from __future__ import annotations

import json
from pathlib import Path

import pytest

from greenhouse_manager.ops import t1_s20_real_service_handoff as module


def _admin_only_state() -> dict[str, object]:
    return {
        "defaultACLAccess": dict(module.EXPECTED_DEFAULTS),
        "clients": [
            {
                "username": "admin",
                "clientid": None,
                "roles": [{"rolename": "admin", "priority": 100}],
                "encoded_password": "not-output",
            }
        ],
        "roles": [
            {
                "rolename": "admin",
                "acls": [],
            }
        ],
    }


def _applied_state() -> dict[str, object]:
    plans = module._plans()
    clients: list[dict[str, object]] = [
        {
            "username": "admin",
            "clientid": None,
            "roles": [{"rolename": "admin", "priority": 100}],
            "encoded_password": "not-output",
        }
    ]
    roles: list[dict[str, object]] = [
        {
            "rolename": "admin",
            "acls": [],
        }
    ]
    for plan in plans.values():
        clients.append(
            {
                "username": plan.username,
                "clientid": plan.client_id,
                "roles": [{"rolename": plan.role_name, "priority": 100}],
                "encoded_password": "not-output",
            }
        )
        roles.append(
            {
                "rolename": plan.role_name,
                "acls": [
                    {
                        "acltype": acl.acl_type,
                        "topic": acl.topic,
                        "allow": acl.allow,
                        "priority": acl.priority,
                    }
                    for acl in reversed(plan.acls)
                ],
            }
        )
    return {
        "defaultACLAccess": dict(module.EXPECTED_DEFAULTS),
        "clients": clients,
        "roles": roles,
    }


def test_preclaim_dynsec_requires_admin_only_and_no_service_or_node() -> None:
    report = module.validate_preclaim_dynsec(_admin_only_state())

    assert report == {
        "client_count": 1,
        "target_service_clients_absent": True,
        "target_service_roles_absent": True,
        "node_clients_absent": True,
        "default_acl_baseline": True,
    }


def test_preclaim_dynsec_rejects_existing_target_identity() -> None:
    state = _admin_only_state()
    clients = state["clients"]
    assert isinstance(clients, list)
    manager = module._plans()["manager"]
    clients.append(
        {
            "username": manager.username,
            "clientid": manager.client_id,
            "roles": [{"rolename": manager.role_name, "priority": 100}],
        }
    )

    with pytest.raises(
        module.S20ServiceHandoffError,
        match="target_service_identity_already_present",
    ):
        module.validate_preclaim_dynsec(state)


def test_applied_dynsec_is_exact_three_services_and_zero_nodes() -> None:
    report = module.validate_applied_dynsec(_applied_state())

    assert report["service_client_count"] == 3
    assert report["service_role_count"] == 3
    assert report["node_client_created"] is False
    assert report["acl_counts"] == {
        "provisioning": 10,
        "manager": 17,
        "homeassistant": 9,
    }


def test_applied_dynsec_rejects_node_client() -> None:
    state = _applied_state()
    clients = state["clients"]
    assert isinstance(clients, list)
    clients.append(
        {
            "username": "ghn_forbidden",
            "clientid": "forbidden",
            "roles": [],
        }
    )

    with pytest.raises(
        module.S20ServiceHandoffError,
        match="postapply_client_set_invalid",
    ):
        module.validate_applied_dynsec(state)


def test_prepare_material_generates_three_secrets_and_numeric_manager_ownership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "greenhouse-secrets"
    root = parent / "mqtt"
    transaction = tmp_path / "transaction"
    admin_password = tmp_path / "admin-password"
    admin_password.write_text("admin-private-value\n", encoding="utf-8")
    admin_password.chmod(0o600)

    monkeypatch.setattr(module, "SECRET_PARENT", parent)
    monkeypatch.setattr(module, "SECRET_ROOT", root)
    monkeypatch.setattr(module, "TRANSACTION_DIR", transaction)
    monkeypatch.setattr(module, "ADMIN_PASSWORD", admin_password)

    chowns: list[tuple[Path, int, int]] = []

    def fake_chown(path: str | bytes | Path, uid: int, gid: int) -> None:
        chowns.append((Path(path), uid, gid))

    monkeypatch.setattr(module.os, "chown", fake_chown)

    plans = module._prepare_transaction_material()

    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert set(plans) == {"provisioning", "manager", "homeassistant"}
    assert manifest["service_count"] == 3
    assert manifest["node_credential_count"] == 0
    assert (
        root / "manager/password",
        999,
        999,
    ) in chowns
    assert (
        root / "provisioning/password",
        999,
        999,
    ) in chowns
    assert not any(
        path == root / "homeassistant/password" and (uid, gid) != (0, 0)
        for path, uid, gid in chowns
    )
    assert (transaction / "admin.conf").stat().st_mode & 0o777 == 0o600
    assert "admin-private-value" not in repr(plans)


class FakeRuntime:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.events: list[str] = []

    def preclaim(self) -> dict[str, object]:
        self.events.append("preclaim")
        return {"status": "PASS"}

    def create_snapshot(self) -> None:
        self.events.append("snapshot")

    def create_material(self) -> dict[str, object]:
        self.events.append("material")
        return {}

    def start_broker(self) -> None:
        self.events.append("start")

    def apply_and_verify(self, _plans: dict[str, object]) -> None:
        self.events.append("apply")
        if self.fail:
            raise RuntimeError("private-secret-value")

    def stop_broker(self) -> None:
        self.events.append("stop")

    def finish(self) -> dict[str, object]:
        self.events.append("finish")
        return {"ok": True}

    def rollback(self) -> None:
        self.events.append("rollback")


def test_apply_claim_boundary_precedes_first_mutation() -> None:
    runtime = FakeRuntime()
    events = runtime.events

    result = module.execute_apply(
        runtime,  # type: ignore[arg-type]
        authorization_id=module.AUTHORIZATION_ID,
        emit=lambda value: events.append(value),
    )

    assert events == [
        "preclaim",
        "AUTHORIZATION_CLAIMED=true",
        "snapshot",
        "material",
        "start",
        "apply",
        "stop",
        "finish",
    ]
    assert result["status"] == "PASS"
    assert result["authorization_consumed"] is True


def test_invalid_authorization_stops_before_preclaim_or_mutation() -> None:
    runtime = FakeRuntime()

    with pytest.raises(
        module.S20ServiceHandoffError,
        match="authorization_id_invalid",
    ):
        module.execute_apply(
            runtime,  # type: ignore[arg-type]
            authorization_id="wrong",
        )

    assert runtime.events == []


def test_postclaim_failure_rolls_back_once_without_secret_in_error() -> None:
    runtime = FakeRuntime(fail=True)

    with pytest.raises(module.S20ServiceHandoffError) as captured:
        module.execute_apply(
            runtime,  # type: ignore[arg-type]
            authorization_id=module.AUTHORIZATION_ID,
            emit=lambda _value: None,
        )

    assert runtime.events == [
        "preclaim",
        "snapshot",
        "material",
        "start",
        "apply",
        "rollback",
    ]
    assert "private-secret-value" not in str(captured.value)
    assert "transaction_failed_rolled_back:RuntimeError" in str(captured.value)


def test_client_config_secret_is_file_material_not_command_contract() -> None:
    rendered = module._client_config(
        username="service",
        password="private-secret-value",
        client_id="service-client",
    )

    assert "-P private-secret-value" in rendered
    assert "-u service" in rendered
    assert "-i service-client" in rendered

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert '"-P",' not in source
    assert '"-p",' in source
    assert '"--network",\n        "none"' in source
    assert '"--pull",\n        "never"' in source


def test_rollback_removes_secret_parent_only_when_transaction_created_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "greenhouse-secrets"
    root = parent / "mqtt"
    transaction = tmp_path / "transaction"
    admin_password = tmp_path / "admin-password"
    admin_password.write_text("admin-private-value\n", encoding="utf-8")
    admin_password.chmod(0o600)

    monkeypatch.setattr(module, "SECRET_PARENT", parent)
    monkeypatch.setattr(module, "SECRET_ROOT", root)
    monkeypatch.setattr(module, "TRANSACTION_DIR", transaction)
    monkeypatch.setattr(module, "ADMIN_PASSWORD", admin_password)
    monkeypatch.setattr(module.os, "chown", lambda *_args: None)

    module._prepare_transaction_material()
    assert (transaction / "parent-was-absent").is_file()

    module._cleanup_transaction_material(remove_bundle=True)

    assert not root.exists()
    assert not parent.exists()
    assert not transaction.exists()


def test_rollback_preserves_safe_preexisting_secret_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "greenhouse-secrets"
    parent.mkdir(mode=0o700)
    parent.chmod(0o700)
    root = parent / "mqtt"
    transaction = tmp_path / "transaction"
    admin_password = tmp_path / "admin-password"
    admin_password.write_text("admin-private-value\n", encoding="utf-8")
    admin_password.chmod(0o600)

    monkeypatch.setattr(module, "SECRET_PARENT", parent)
    monkeypatch.setattr(module, "SECRET_ROOT", root)
    monkeypatch.setattr(module, "TRANSACTION_DIR", transaction)
    monkeypatch.setattr(module, "ADMIN_PASSWORD", admin_password)

    real_stat = module.Path.stat

    class RootOwnedStat:
        def __init__(self, value: object) -> None:
            self._value = value
            self.st_uid = 0
            self.st_gid = 0
            self.st_mode = value.st_mode

        def __getattr__(self, name: str) -> object:
            return getattr(self._value, name)

    def fake_stat(path: Path, *args: object, **kwargs: object) -> object:
        value = real_stat(path, *args, **kwargs)
        if path == parent:
            return RootOwnedStat(value)
        return value

    monkeypatch.setattr(module.Path, "stat", fake_stat)
    monkeypatch.setattr(module.os, "chown", lambda *_args: None)

    module._prepare_transaction_material()
    assert (transaction / "parent-preexisting").is_file()

    module._cleanup_transaction_material(remove_bundle=True)

    assert parent.is_dir()
    assert not root.exists()
    assert not transaction.exists()


def test_prepare_rejects_unsafe_preexisting_secret_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "greenhouse-secrets"
    parent.mkdir(mode=0o755)
    parent.chmod(0o755)
    root = parent / "mqtt"
    transaction = tmp_path / "transaction"

    monkeypatch.setattr(module, "SECRET_PARENT", parent)
    monkeypatch.setattr(module, "SECRET_ROOT", root)
    monkeypatch.setattr(module, "TRANSACTION_DIR", transaction)
    monkeypatch.setattr(module.os, "chown", lambda *_args: None)

    with pytest.raises(
        module.S20ServiceHandoffError,
        match="production_secret_parent_unsafe",
    ):
        module._prepare_transaction_material()

    assert not root.exists()


class BrokerImageRunner:
    def __init__(self, *, digest: str) -> None:
        self.digest = digest
        self.commands: list[tuple[str, ...]] = []

    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, str]:
        assert input_text is None
        assert timeout == 30.0
        self.commands.append(command)
        assert command[:4] == (
            "docker",
            "image",
            "inspect",
            "--format",
        )
        assert command[-1] == module.BROKER_SOURCE_TAG
        repo_digest = (
            "m.daocloud.io/docker.io/library/eclipse-mosquitto@"
            f"{self.digest}"
        )
        return (
            0,
            "sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408"
            "|linux|arm64|"
            + json.dumps([repo_digest])
            + "\n",
        )


def test_accepts_local_broker_bound_by_frozen_oci_index_digest() -> None:
    runner = BrokerImageRunner(
        digest=module.EXPECTED_BROKER_INDEX_DIGEST,
    )

    report = module._verify_broker_source_tag(
        runner,  # type: ignore[arg-type]
    )

    assert report == {
        "image_id": (
            "sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408"
        ),
        "platform": "linux/arm64",
        "index_digest": module.EXPECTED_BROKER_INDEX_DIGEST,
        "arm64_manifest_digest": module.EXPECTED_BROKER_ARM64_MANIFEST_DIGEST,
    }


def test_rejects_local_broker_with_other_index_digest() -> None:
    runner = BrokerImageRunner(digest="sha256:" + "0" * 64)

    with pytest.raises(
        module.S20ServiceHandoffError,
        match="exact_broker_image_index_digest_drift",
    ):
        module._verify_broker_source_tag(
            runner,  # type: ignore[arg-type]
        )


class SecretClientRunner:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []

    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, str]:
        self.commands.append(command)
        if "mosquitto_rr" in command:
            return (
                0,
                json.dumps(
                    {
                        "responses": [
                            {
                                "command": "listClients",
                            }
                        ]
                    }
                ),
            )
        return 0, ""


def test_dynsec_secret_client_runs_as_root_not_broker_uid() -> None:
    runner = SecretClientRunner()

    module._rr(
        runner,  # type: ignore[arg-type]
        ({"command": "listClients"},),
        "/run/n3w-s20/admin.conf",
    )

    command = runner.commands[-1]
    assert command[:6] == (
        "docker",
        "exec",
        "-i",
        "--user",
        "0:0",
        module.CONTAINER_NAME,
    )


def test_service_secret_client_runs_as_root_not_broker_uid() -> None:
    runner = SecretClientRunner()

    assert module._mqtt_action(
        runner,  # type: ignore[arg-type]
        "manager",
        "/run/n3w-s20/manager.conf",
    )

    command = runner.commands[-1]
    assert command[:5] == (
        "docker",
        "exec",
        "--user",
        "0:0",
        module.CONTAINER_NAME,
    )


def test_temp_broker_itself_remains_uid_1883() -> None:
    source = Path(module.__file__).read_text(encoding="utf-8")

    assert '"--user",\n        "1883:1883"' in source
    assert '"--user",\n            "0:0"' in source


class BrokerLifecycleRunner:
    def __init__(
        self,
        *,
        rm_code: int = 0,
        inspect_code: int = 1,
    ) -> None:
        self.rm_code = rm_code
        self.inspect_code = inspect_code
        self.commands: list[tuple[str, ...]] = []

    def run(
        self,
        command: tuple[str, ...],
        *,
        input_text: str | None = None,
        timeout: float = 30.0,
    ) -> tuple[int, str]:
        assert input_text is None
        self.commands.append(command)
        if command[:3] == ("docker", "rm", "-f"):
            assert timeout == 30
            return self.rm_code, ""
        if command[:2] == ("docker", "inspect"):
            assert timeout == 10
            return self.inspect_code, ""
        if command[:2] == ("docker", "run"):
            assert timeout == 60
            return 0, "container-id"
        raise AssertionError(command)


def test_stop_broker_accepts_absent_only_after_inspect_proves_absence() -> None:
    runner = BrokerLifecycleRunner(rm_code=1, inspect_code=1)

    module._stop_broker(
        runner,  # type: ignore[arg-type]
    )

    assert runner.commands[-1][:2] == ("docker", "inspect")


def test_stop_broker_rejects_container_still_present() -> None:
    runner = BrokerLifecycleRunner(rm_code=0, inspect_code=0)

    with pytest.raises(
        module.S20ServiceHandoffError,
        match="transaction_broker_still_present",
    ):
        module._stop_broker(
            runner,  # type: ignore[arg-type]
        )


def test_start_broker_uses_verified_local_image_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = BrokerLifecycleRunner()
    image_id = "sha256:" + "1" * 64

    monkeypatch.setattr(
        module,
        "_verify_broker_source_tag",
        lambda _runner: {
            "image_id": image_id,
            "platform": "linux/arm64",
            "index_digest": module.EXPECTED_BROKER_INDEX_DIGEST,
            "arm64_manifest_digest": (
                module.EXPECTED_BROKER_ARM64_MANIFEST_DIGEST
            ),
        },
    )
    monkeypatch.setattr(
        module,
        "_rr",
        lambda *_args, **_kwargs: ({"command": "listClients"},),
    )

    module._start_broker(
        runner,  # type: ignore[arg-type]
    )

    run_command = next(
        command
        for command in runner.commands
        if command[:2] == ("docker", "run")
    )
    assert run_command[-1] == image_id
    assert module.BROKER_SOURCE_TAG not in run_command


def test_stream_executor_binding_accepts_exact_sha256() -> None:
    expected = "a" * 64

    module._verify_executor_binding(
        executor_path=None,
        executor_source_sha256=expected,
        expected_executor_sha256=expected,
    )


def test_stream_executor_binding_rejects_mismatch() -> None:
    with pytest.raises(
        module.S20ServiceHandoffError,
        match="executor_sha256_mismatch",
    ):
        module._verify_executor_binding(
            executor_path=None,
            executor_source_sha256="a" * 64,
            expected_executor_sha256="b" * 64,
        )


def test_source_dependency_binding_is_exact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency = tmp_path / "dependency.py"
    dependency.write_text("value = 1\n", encoding="utf-8")

    import hashlib

    expected = hashlib.sha256(dependency.read_bytes()).hexdigest()
    monkeypatch.setattr(
        module,
        "EXPECTED_DEPENDENCY_SHA256",
        {dependency: expected},
    )

    module._verify_source_dependencies()


def test_source_dependency_binding_rejects_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependency = tmp_path / "dependency.py"
    dependency.write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        module,
        "EXPECTED_DEPENDENCY_SHA256",
        {dependency: "0" * 64},
    )

    with pytest.raises(
        module.S20ServiceHandoffError,
        match="source_dependency_sha256_mismatch",
    ):
        module._verify_source_dependencies()
