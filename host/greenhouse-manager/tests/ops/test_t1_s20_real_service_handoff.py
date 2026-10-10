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


def test_temp_broker_preserves_image_entrypoint_user_flow() -> None:
    source = Path(module.__file__).read_text(encoding="utf-8")

    assert '"--user",\n        "1883:1883"' not in source
    assert '"--user",\n            "0:0"' in source


class BrokerLifecycleRunner:
    def __init__(
        self,
        *,
        rm_code: int = 0,
        inspect_code: int = 1,
        inspect_output: str = "",
    ) -> None:
        self.rm_code = rm_code
        self.inspect_code = inspect_code
        self.inspect_output = inspect_output
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
            return self.inspect_code, self.inspect_output
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


def test_streamed_dependency_binding_accepts_exact_hashes() -> None:
    streamed = {
        str(path.relative_to(module.SOURCE_ROOT)): digest
        for path, digest in module.EXPECTED_DEPENDENCY_SHA256.items()
    }

    module._verify_source_dependencies(streamed)


def test_streamed_dependency_binding_rejects_missing_dependency() -> None:
    streamed = {
        str(path.relative_to(module.SOURCE_ROOT)): digest
        for path, digest in module.EXPECTED_DEPENDENCY_SHA256.items()
    }
    streamed.pop(next(iter(streamed)))

    with pytest.raises(
        module.S20ServiceHandoffError,
        match="source_dependency_set_mismatch",
    ):
        module._verify_source_dependencies(streamed)


def test_streamed_dependency_binding_rejects_hash_drift() -> None:
    streamed = {
        str(path.relative_to(module.SOURCE_ROOT)): digest
        for path, digest in module.EXPECTED_DEPENDENCY_SHA256.items()
    }
    first = next(iter(streamed))
    streamed[first] = "0" * 64

    with pytest.raises(
        module.S20ServiceHandoffError,
        match="source_dependency_sha256_mismatch",
    ):
        module._verify_source_dependencies(streamed)


def test_start_broker_rejects_early_container_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = BrokerLifecycleRunner(
        inspect_code=0,
        inspect_output="exited|1\n",
    )
    image_id = "sha256:" + "2" * 64

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

    with pytest.raises(
        module.S20ServiceHandoffError,
        match="transaction_broker_exited_before_ready:1",
    ):
        module._start_broker(
            runner,  # type: ignore[arg-type]
        )


def test_start_broker_command_has_no_forced_runtime_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = BrokerLifecycleRunner()
    image_id = "sha256:" + "3" * 64

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
    assert "--user" not in run_command


def test_r4_authorization_and_snapshot_paths_are_attempt_scoped() -> None:
    assert module.AUTHORIZATION_ID == (
        "N3W_T1_S20_REAL_THREE_SERVICE_SECRET_HANDOFF_"
        "APPLY_R4_20261010_01"
    )
    assert Path(
        "/etc/n3wfc4/private/dynsec-s20-pre-three-service.json"
    ) == module.R1_EVIDENCE_SNAPSHOT
    assert Path(
        "/etc/n3wfc4/private/dynsec-s20-r2-pre-three-service.json"
    ) == module.R2_EVIDENCE_SNAPSHOT
    assert Path(
        "/etc/n3wfc4/private/dynsec-s20-r3-pre-three-service.json"
    ) == module.R3_EVIDENCE_SNAPSHOT
    assert Path(
        "/etc/n3wfc4/private/dynsec-s20-r4-pre-three-service.json"
    ) == module.ROLLBACK_SNAPSHOT
    assert len(
        {
            module.R1_EVIDENCE_SNAPSHOT,
            module.R2_EVIDENCE_SNAPSHOT,
            module.R3_EVIDENCE_SNAPSHOT,
            module.ROLLBACK_SNAPSHOT,
        }
    ) == 4


def test_cleanup_transaction_material_verifies_removal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "greenhouse-secrets"
    root = parent / "mqtt"
    transaction = tmp_path / "transaction"
    root.mkdir(parents=True)
    transaction.mkdir()
    (transaction / "parent-was-absent").write_text(
        "true\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "SECRET_PARENT", parent)
    monkeypatch.setattr(module, "SECRET_ROOT", root)
    monkeypatch.setattr(module, "TRANSACTION_DIR", transaction)

    module._cleanup_transaction_material(remove_bundle=True)

    assert not root.exists()
    assert not parent.exists()
    assert not transaction.exists()


def test_cleanup_transaction_material_rejects_silent_transaction_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "greenhouse-secrets"
    root = parent / "mqtt"
    transaction = tmp_path / "transaction"
    root.mkdir(parents=True)
    transaction.mkdir()

    monkeypatch.setattr(module, "SECRET_PARENT", parent)
    monkeypatch.setattr(module, "SECRET_ROOT", root)
    monkeypatch.setattr(module, "TRANSACTION_DIR", transaction)

    real_rmtree = module.shutil.rmtree

    def selective_rmtree(path: object, *args: object, **kwargs: object) -> None:
        if Path(path) == transaction:
            return
        real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(module.shutil, "rmtree", selective_rmtree)

    with pytest.raises(
        module.S20ServiceHandoffError,
        match="transaction_directory_cleanup_failed",
    ):
        module._cleanup_transaction_material(remove_bundle=True)


def test_local_runtime_rollback_requires_readonly_postcheck(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    monkeypatch.setattr(
        module,
        "_stop_broker",
        lambda _runner: events.append("stop"),
    )
    monkeypatch.setattr(
        module,
        "_restore_snapshot_or_verify_baseline",
        lambda: events.append("restore"),
    )
    monkeypatch.setattr(
        module,
        "_cleanup_transaction_material",
        lambda *, remove_bundle, parent_was_absent=None: events.append(
            f"cleanup:{str(remove_bundle).lower()}:"
            f"{str(parent_was_absent).lower()}"
        ),
    )
    monkeypatch.setattr(
        module,
        "_rollback_postcheck",
        lambda _runner: events.append("postcheck"),
    )

    runtime = module.LocalTransactionRuntime(
        object(),  # type: ignore[arg-type]
        executor_path=None,
        executor_source_sha256="a" * 64,
        streamed_dependency_sha256={},
        expected_executor_sha256="a" * 64,
    )

    runtime.rollback()

    assert events == [
        "stop",
        "restore",
        "cleanup:true:none",
        "postcheck",
    ]


def test_start_broker_mounts_tls_files_individually(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = BrokerLifecycleRunner()
    image_id = "sha256:" + "4" * 64

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
    rendered = " ".join(run_command)

    assert (
        f"{module.TLS_CA}:/mosquitto/config/n3w-ca.pem:ro"
        in rendered
    )
    assert (
        f"{module.TLS_CERT}:/mosquitto/config/n3w-server.pem:ro"
        in rendered
    )
    assert (
        f"{module.TLS_KEY}:/mosquitto/config/n3w-server.key:ro"
        in rendered
    )
    assert f"{module.TLS_DIR}:/mosquitto/tls:ro" not in rendered
    assert f"{module.TLS_CA}:/mosquitto/tls/ca.pem:ro" not in rendered


def test_verify_tls_material_accepts_production_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeStat:
        def __init__(self, uid: int, gid: int, mode: int) -> None:
            self.st_uid = uid
            self.st_gid = gid
            self.st_mode = mode

    class FakeTLSPath:
        def __init__(self, uid: int, gid: int, mode: int) -> None:
            self._stat = FakeStat(uid, gid, mode)

        def is_symlink(self) -> bool:
            return False

        def is_file(self) -> bool:
            return True

        def stat(self) -> FakeStat:
            return self._stat

    monkeypatch.setattr(module, "TLS_CA", FakeTLSPath(0, 0, 0o644))
    monkeypatch.setattr(module, "TLS_CERT", FakeTLSPath(0, 0, 0o644))
    monkeypatch.setattr(
        module,
        "TLS_KEY",
        FakeTLSPath(1883, 1883, 0o600),
    )

    module._verify_tls_material()



def test_create_snapshot_removes_partial_file_on_validation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dynsec = tmp_path / "dynamic-security.json"
    snapshot = tmp_path / "snapshot.json"
    dynsec.write_text('{"clients": []}\n', encoding="utf-8")

    monkeypatch.setattr(module, "DYNSEC_PATH", dynsec)
    monkeypatch.setattr(module, "ROLLBACK_SNAPSHOT", snapshot)
    monkeypatch.setattr(module, "EXPECTED_DYNSEC_SHA256", "0" * 64)
    monkeypatch.setattr(module.os, "chown", lambda *_args: None)

    with pytest.raises(
        module.S20ServiceHandoffError,
        match="rollback_snapshot_sha_mismatch",
    ):
        module._create_snapshot()

    assert not snapshot.exists()


def test_restore_snapshot_validates_before_replacing_live_dynsec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    def reject_snapshot() -> str:
        events.append("verify")
        raise module.S20ServiceHandoffError("r4_rollback_snapshot_sha_drift")

    monkeypatch.setattr(
        module,
        "_verify_r4_snapshot_if_present",
        reject_snapshot,
    )
    monkeypatch.setattr(
        module.os,
        "replace",
        lambda *_args: events.append("replace"),
    )

    with pytest.raises(
        module.S20ServiceHandoffError,
        match="r4_rollback_snapshot_sha_drift",
    ):
        module._restore_snapshot()

    assert events == ["verify"]


def test_runtime_rollback_keeps_preclaim_parent_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []

    monkeypatch.setattr(
        module,
        "build_preclaim_report",
        lambda *_args, **_kwargs: {
            "status": "PASS",
            "secret_parent_state": "absent",
        },
    )
    monkeypatch.setattr(module, "_stop_broker", lambda _runner: None)
    monkeypatch.setattr(
        module,
        "_restore_snapshot_or_verify_baseline",
        lambda: None,
    )
    monkeypatch.setattr(
        module,
        "_cleanup_transaction_material",
        lambda *, remove_bundle, parent_was_absent=None: events.append(
            f"{str(remove_bundle).lower()}:{str(parent_was_absent).lower()}"
        ),
    )
    monkeypatch.setattr(module, "_rollback_postcheck", lambda _runner: None)

    runtime = module.LocalTransactionRuntime(
        object(),  # type: ignore[arg-type]
        executor_path=None,
        executor_source_sha256="a" * 64,
        streamed_dependency_sha256={},
        expected_executor_sha256="a" * 64,
    )

    runtime.preclaim()
    runtime.rollback()

    assert events == ["true:true"]



def test_broker_config_tls_contract_accepts_exact_executor_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "mosquitto.conf"
    config.write_text(
        "\n".join(
            (
                f"cafile {module.BROKER_TLS_CA_TARGET}",
                f"certfile {module.BROKER_TLS_CERT_TARGET}",
                f"keyfile {module.BROKER_TLS_KEY_TARGET}",
                "",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "BROKER_CONFIG", config)

    module._verify_broker_config_tls_contract()


def test_broker_config_tls_contract_rejects_mount_path_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "mosquitto.conf"
    config.write_text(
        "\n".join(
            (
                "cafile /mosquitto/tls/ca.pem",
                "certfile /mosquitto/tls/server.pem",
                "keyfile /mosquitto/tls/server.key",
                "",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "BROKER_CONFIG", config)

    with pytest.raises(
        module.S20ServiceHandoffError,
        match="broker_tls_path_contract_drift",
    ):
        module._verify_broker_config_tls_contract()
