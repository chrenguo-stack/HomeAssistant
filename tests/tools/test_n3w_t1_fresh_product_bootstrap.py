from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_fresh_product_bootstrap.py"


def load_tool():
    name = "n3w_t1_fresh_product_bootstrap"
    specification = importlib.util.spec_from_file_location(name, TOOL)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def test_deployable_workflow_prevents_post_manifest_bytecode_contamination() -> None:
    workflow = (
        ROOT
        / ".github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml"
    ).read_text(encoding="utf-8")

    assert "PYTHONDONTWRITEBYTECODE=1 sudo -E python - \"$PAYLOAD\"" in workflow
    assert workflow.count("--phase self-check") >= 2
    assert "find \"$PAYLOAD\" -type f -path '*/__pycache__/*'" in workflow
    assert "rootfs_layers_sha256" in workflow
    assert "FRESH_CROSS_STORE_IMAGE_BINDING=PASS" in workflow


def test_future_authorization_is_fresh_bootstrap_specific() -> None:
    tool = load_tool()
    assert tool.AUTHORIZATION_ID == (
        "N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_"
        "LIVE_APPLY_20261012_08"
    )
    assert "PRODUCTION_STACK_STAGING" not in tool.AUTHORIZATION_ID


def test_runtime_image_binding_accepts_containerd_runtime_id_when_rootfs_exact() -> None:
    tool = load_tool()
    layers = [
        "sha256:" + "1" * 64,
        "sha256:" + "2" * 64,
    ]
    runtime_id = "sha256:" + "c" * 64
    config = {
        "Entrypoint": ["/init"],
        "Cmd": None,
        "User": "",
    }
    record = {
        "image": "local/test:exact",
        "rootfs_layers_sha256": tool._normalized_hash(layers),
        "config_contract_sha256": tool._normalized_hash(
            tool._image_config_contract(config)
        ),
    }

    class FakeRunner:
        def run(self, _argv):
            return json.dumps(
                [
                    {
                        "Id": runtime_id,
                        "Architecture": "arm64",
                        "Os": "linux",
                        "RootFS": {"Layers": layers},
                        "Config": config,
                    }
                ]
            )

    binding = tool._verify_runtime_image(
        FakeRunner(),
        "homeassistant",
        record,
    )

    assert binding["runtime_id"] == runtime_id
    assert binding["rootfs_layers_sha256"] == record["rootfs_layers_sha256"]


def test_runtime_image_binding_rejects_rootfs_drift() -> None:
    tool = load_tool()
    expected_layers = ["sha256:" + "1" * 64]
    observed_layers = ["sha256:" + "2" * 64]
    config = {"Entrypoint": ["/init"], "User": ""}
    record = {
        "image": "local/test:exact",
        "rootfs_layers_sha256": tool._normalized_hash(expected_layers),
        "config_contract_sha256": tool._normalized_hash(
            tool._image_config_contract(config)
        ),
    }

    class FakeRunner:
        def run(self, _argv):
            return json.dumps(
                [
                    {
                        "Id": "sha256:" + "c" * 64,
                        "Architecture": "arm64",
                        "Os": "linux",
                        "RootFS": {"Layers": observed_layers},
                        "Config": config,
                    }
                ]
            )

    with pytest.raises(
        tool.BootstrapError,
        match="image_rootfs_binding_invalid:homeassistant",
    ):
        tool._verify_runtime_image(
            FakeRunner(),
            "homeassistant",
            record,
        )


def test_dynsec_uses_tmpfs_for_declared_log_volume() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert '"--tmpfs",\n                "/mosquitto/log",' in source
    assert '("docker", "rm", "-f", "-v", name)' in source


def test_stage_runtime_keeps_credential_bundle_immutable() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert 'env_file = "/etc/n3wfc4/docker-compose.env"' in source
    assert 'compose_env = etc / "docker-compose.env"' in source
    assert 'with runtime_env.open("a"' not in source


def test_fresh_installer_exposes_safe_stage_diagnostics(tmp_path: Path) -> None:
    contract_path = (
        ROOT
        / "host/greenhouse-manager/src/greenhouse_manager/bootstrap/fresh_installer.py"
    )
    specification = importlib.util.spec_from_file_location(
        "n3w_fresh_installer_contract_test",
        contract_path,
    )
    assert specification is not None
    assert specification.loader is not None
    contract = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = contract
    specification.loader.exec_module(contract)

    class Adapter:
        def preflight(self):
            return {
                "status": "PASS",
                "arch": "aarch64",
                "docker_ready": True,
                "compose_ready": True,
                "network_ready": True,
                "default_route": True,
                "time_sync": True,
                "root_capacity": True,
                "product_containers": 0,
                "product_images": 0,
                "product_volumes": 0,
                "product_networks": 0,
                "product_listeners": 0,
                "product_paths_absent": True,
                "product_units_absent": True,
                "product_dispatcher_absent": True,
                "product_firewall_absent": True,
                "production_service_start": False,
            }

        def load_images(self):
            raise RuntimeError("secret-like detail must not escape")

        def cleanup(self, _candidate):
            return {
                "status": "PASS",
                "transaction_owned_only": True,
                "production_service_start": False,
            }

    candidate = tmp_path / "candidate"
    with pytest.raises(contract.FreshInstallerStageError) as captured:
        contract.run_fresh_staging(
            Adapter(),
            candidate,
            before_mutation=lambda: None,
        )

    error = captured.value
    assert error.failed_stage == "load_images"
    assert error.failure_code == "adapter_failure"
    assert error.cleanup_result == "PASS"
    assert "secret-like" not in str(error)


def test_image_config_contract_normalizes_docker_null_empty_equivalence() -> None:
    tool = load_tool()
    archive_config = {
        "Entrypoint": None,
        "Cmd": None,
        "User": None,
        "Env": None,
        "WorkingDir": None,
        "Labels": None,
        "Healthcheck": None,
        "StopSignal": None,
        "Volumes": None,
        "ExposedPorts": None,
    }
    runtime_config = {
        "Entrypoint": [],
        "Cmd": [],
        "User": "",
        "Env": [],
        "WorkingDir": "",
        "Labels": {},
        "Healthcheck": {},
        "StopSignal": "",
        "Volumes": {},
        "ExposedPorts": {},
    }

    assert tool._image_config_contract(
        archive_config
    ) == tool._image_config_contract(runtime_config)


def test_image_config_contract_preserves_behavioral_drift() -> None:
    tool = load_tool()
    first = {
        "Entrypoint": ["/init"],
        "Cmd": ["python", "-m", "homeassistant"],
        "User": "0",
        "Env": ["A=1"],
        "WorkingDir": "/config",
        "Labels": {"role": "ha"},
        "Healthcheck": {"Test": ["CMD", "true"]},
        "StopSignal": "SIGTERM",
        "Volumes": {"/config": {}},
        "ExposedPorts": {"8123/tcp": {}},
    }
    second = {
        **first,
        "Entrypoint": ["/bin/sh"],
    }

    assert tool._image_config_contract(
        first
    ) != tool._image_config_contract(second)


def test_runtime_image_binding_rejects_same_rootfs_with_config_drift() -> None:
    tool = load_tool()
    layers = ["sha256:" + "1" * 64]
    expected_config = {
        "Entrypoint": ["/init"],
        "Cmd": ["python", "-m", "homeassistant"],
        "User": "0",
        "Volumes": {"/config": {}},
    }
    observed_config = {
        **expected_config,
        "Entrypoint": ["/bin/sh"],
        "User": "999",
    }
    record = {
        "image": "local/test:exact",
        "rootfs_layers_sha256": tool._normalized_hash(layers),
        "config_contract_sha256": tool._normalized_hash(
            tool._image_config_contract(expected_config)
        ),
    }

    class FakeRunner:
        def run(self, _argv):
            return json.dumps(
                [
                    {
                        "Id": "sha256:" + "c" * 64,
                        "Architecture": "arm64",
                        "Os": "linux",
                        "RootFS": {"Layers": layers},
                        "Config": observed_config,
                    }
                ]
            )

    with pytest.raises(
        tool.BootstrapError,
        match="image_config_binding_invalid:homeassistant",
    ):
        tool._verify_runtime_image(
            FakeRunner(),
            "homeassistant",
            record,
        )


def test_authorization_ledger_blocks_same_authorization_across_payload_dirs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    ledger = tmp_path / "ledger"
    monkeypatch.setattr(tool, "AUTHORIZATION_LEDGER_ROOT", ledger)
    manifest = {"source_head": "a" * 40}
    first = tmp_path / "payload-a"
    second = tmp_path / "payload-b"
    first.mkdir()
    second.mkdir()
    payload_manifest = json.dumps({"source_head": "a" * 40}) + "\n"
    (first / "payload-manifest.json").write_text(
        payload_manifest,
        encoding="utf-8",
    )
    (second / "payload-manifest.json").write_text(
        payload_manifest,
        encoding="utf-8",
    )

    tool._claim_authorization(first, manifest)

    assert tool._authorization_record_present() is True
    record = json.loads(
        tool._authorization_record_path().read_text(encoding="utf-8")
    )
    assert record["authorization_id"] == tool.AUTHORIZATION_ID
    assert record["source_head"] == "a" * 40
    assert record["payload_manifest_sha256"] == tool._sha256_file(
        first / "payload-manifest.json"
    )

    with pytest.raises(
        tool.BootstrapError,
        match="authorization_already_consumed",
    ):
        tool._claim_authorization(second, manifest)


def test_stopped_postcheck_splits_state_owner_and_root_audits() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert 'f"{MANAGER_UID}:{MANAGER_GID}"' in source
    assert (
        "src=/var/lib/greenhouse-manager/manager,dst=/manager,readonly"
        in source
    )
    assert (
        "src=/var/lib/greenhouse-manager/n3w,dst=/n3w,readonly"
        in source
    )
    assert (
        "src=/var/lib/greenhouse-manager/identity,dst=/identity,readonly"
        in source
    )


def test_postcheck_failure_runs_cleanup_and_reports_stage() -> None:
    contract_path = (
        ROOT
        / "host/greenhouse-manager/src/greenhouse_manager/bootstrap/fresh_installer.py"
    )
    specification = importlib.util.spec_from_file_location(
        "n3w_fresh_installer_postcheck_cleanup_test",
        contract_path,
    )
    assert specification is not None
    assert specification.loader is not None
    contract = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = contract
    specification.loader.exec_module(contract)

    system_id = "fresh-system"
    system_hash = __import__("hashlib").sha256(system_id.encode()).hexdigest()

    class Adapter:
        cleanup_called = False

        def preflight(self):
            return {
                "status": "PASS",
                "arch": "aarch64",
                "docker_ready": True,
                "compose_ready": True,
                "network_ready": True,
                "default_route": True,
                "time_sync": True,
                "root_capacity": True,
                "product_containers": 0,
                "product_images": 0,
                "product_volumes": 0,
                "product_networks": 0,
                "product_listeners": 0,
                "product_paths_absent": True,
                "product_units_absent": True,
                "product_dispatcher_absent": True,
                "product_firewall_absent": True,
                "production_service_start": False,
            }

        def load_images(self):
            return {
                "status": "PASS",
                "image_count": 3,
                "offline": True,
                "registry_pull": False,
                "platform": "linux/arm64",
                "production_service_start": False,
            }

        def create_identity(self, _candidate):
            return {
                "created": True,
                "production_services_modified": False,
                "network_operation": False,
                "system_id": system_id,
            }

        def create_state(self, _candidate, _system_hash):
            return {
                "status": "PASS",
                "fresh_product_state": True,
                "legacy_state_imported": False,
                "node_credential_count": 0,
                "production_service_start": False,
                "system_id_sha256": system_hash,
            }

        def create_broker(self, _candidate, _system_id):
            return {
                "service_count": 3,
                "node_credential_count": 0,
                "broker_transport_ca_separate_from_system_ca": True,
                "secret_values_included": False,
                "production_service_start": False,
                "network_operation": False,
                "system_id": system_id,
            }

        def initialize_dynsec(self, _candidate, _system_id):
            return {
                "status": "PASS",
                "service_client_count": 3,
                "service_role_count": 3,
                "node_client_count": 0,
                "node_role_count": 0,
                "default_acl_exact": True,
                "admin_runtime_use_forbidden": True,
                "secret_values_included": False,
                "production_service_start": False,
            }

        def stage_runtime(self, _candidate, _system_id):
            return {
                "status": "PASS",
                "source_files_staged": True,
                "network_count": 2,
                "guard_ready": True,
                "services_stopped": True,
                "production_service_start": False,
            }

        def commit_candidate(self, _candidate, _system_id):
            return {
                "status": "PASS",
                "committed": True,
                "transaction_owned_only": True,
                "production_service_start": False,
            }

        def stopped_postcheck(self, _system_id):
            raise RuntimeError("manager_root_owner_invalid")

        def cleanup(self, _candidate):
            self.cleanup_called = True
            return {
                "status": "PASS",
                "transaction_owned_only": True,
                "production_service_start": False,
            }

    adapter = Adapter()
    candidate = Path("/tmp/n3w-fresh-postcheck-cleanup-test-unused")
    with pytest.raises(contract.FreshInstallerStageError) as captured:
        contract.run_fresh_staging(
            adapter,
            candidate,
            before_mutation=lambda: None,
        )

    error = captured.value
    assert error.failed_stage == "postcheck"
    assert error.cleanup_result == "PASS"
    assert adapter.cleanup_called is True
    assert str(error) == "fresh_install_failed"


def test_final_targets_do_not_include_host_baseline() -> None:
    tool = load_tool()
    targets = set(tool.FINAL_DIRS) | set(tool.FINAL_FILES)

    assert "/var/lib/docker" not in targets
    assert "/etc/NetworkManager" not in targets
    assert "/etc/ssh" not in targets
    assert "/" not in targets


def test_apply_rejects_wrong_authorization_before_root_check(
    tmp_path: Path,
) -> None:
    tool = load_tool()

    with pytest.raises(tool.BootstrapError, match="authorization_id_mismatch"):
        tool.execute_apply(tmp_path, "WRONG")


def test_source_forbids_broad_prune_and_activation() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert "docker system prune" not in source.split("def self_check", 1)[0]
    assert "docker volume prune" not in source.split("def self_check", 1)[0]
    assert "docker network prune" not in source.split("def self_check", 1)[0]
    assert "docker compose up" not in source.split("def self_check", 1)[0]


def test_source_contains_real_dynsec_candidate_and_stopped_postcheck() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert "mosquitto_rr" in source
    assert "$CONTROL/dynamic-security/v1" in source
    assert "audit_fresh_dynsec_document" in source
    assert '("docker", "network", "create", network)' not in source
    assert '"docker", "compose"' in source
    assert "postcheck_listener_present" in source
    assert "postcheck_guard_active" in source


def test_source_uses_no_trunc_image_postcheck() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert '("docker", "image", "ls", "--no-trunc", "-q")' in source


def test_claimed_failure_is_structured_no_replay() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert '"status": "STOP_PARTIAL"' in source
    assert '"replay_allowed": False' in source
    assert '"automatic_retry": False' in source


def test_staging_defers_product_network_creation_to_activation() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert 'if networks != DEFAULT_NETWORKS:' in source
    assert '("docker", "network", "create", network)' not in source


def test_master_and_instance_target_ownership_is_disjoint_and_complete() -> None:
    tool = load_tool()

    public_dirs = set(tool.PUBLIC_FINAL_DIRS)
    instance_dirs = set(tool.INSTANCE_FINAL_DIRS)
    public_files = set(tool.PUBLIC_FINAL_FILES)
    instance_files = set(tool.INSTANCE_FINAL_FILES)

    assert public_dirs.isdisjoint(instance_dirs)
    assert public_files.isdisjoint(instance_files)
    assert public_dirs | instance_dirs == set(tool.FINAL_DIRS)
    assert public_files | instance_files == set(tool.FINAL_FILES)
    assert public_dirs == {"/opt/HomeAssistant"}
    assert "/opt/greenhouse-secrets" in instance_dirs
    assert "/var/lib/greenhouse-manager" in instance_dirs


def test_legacy_runtime_wrapper_uses_split_stage_ownership() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert "def stage_public_runtime(" in source
    assert "def stage_instance_runtime(" in source
    assert "instance_report = self.stage_instance_runtime(" in source
    assert "public_report = self.stage_public_runtime(" in source
    assert "reuse_stage=True" in source


def test_split_cleanup_ownership_does_not_cross_boundaries() -> None:
    source = TOOL.read_text(encoding="utf-8")
    instance_cleanup = source.split(
        "    def cleanup_instance_candidate(", 1
    )[1].split("    def cleanup_master_candidate(", 1)[0]
    master_cleanup = source.split(
        "    def cleanup_master_candidate(", 1
    )[1].split("    def cleanup(", 1)[0]

    assert "INSTANCE_FINAL_DIRS" in instance_cleanup
    assert "PUBLIC_FINAL_DIRS" not in instance_cleanup
    assert "created_images" not in instance_cleanup

    assert "PUBLIC_FINAL_DIRS" in master_cleanup
    assert "INSTANCE_FINAL_DIRS" not in master_cleanup
    assert "created_images" in master_cleanup


def test_postcheck_is_split_between_master_and_instance() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert "def master_postcheck(" in source
    assert "require_instance_absent: bool = True" in source
    assert "staged_units_enabled: bool = False" in source
    assert "postcheck_master_instance_material_present" in source
    assert "def instance_stopped_postcheck(self, system_id: str)" in source
    assert "require_instance_absent=False" in source
    assert "staged_units_enabled=True" in source
    assert "instance = self.instance_stopped_postcheck(system_id)" in source


def test_legacy_commit_preflights_all_targets_before_first_move(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    tool = load_tool()
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    instance_source = candidate / "instance-source"
    public_source = candidate / "public-source"
    instance_source.mkdir()
    public_source.mkdir()

    instance_target = tmp_path / "instance-target"
    public_target = tmp_path / "public-target"
    public_target.mkdir()

    monkeypatch.setattr(
        tool,
        "FINAL_DIRS",
        {
            str(instance_target): "instance-source",
            str(public_target): "public-source",
        },
    )
    monkeypatch.setattr(tool, "FINAL_FILES", {})

    class Runner:
        def run(self, _argv):
            return ""

    adapters = tool.LiveFreshInstallerAdapters(
        tmp_path,
        {"images": {"manager": {"image": "manager"}}},
        Runner(),
    )

    with pytest.raises(
        tool.BootstrapError,
        match="commit_target_exists",
    ):
        adapters.commit_candidate(candidate, "system-id")

    assert instance_source.is_dir()
    assert not instance_target.exists()
    assert public_target.is_dir()

def test_live_adapter_master_preflight_maps_minimal_host(monkeypatch) -> None:
    tool = load_tool()
    monkeypatch.setattr(
        tool,
        "_preflight",
        lambda _runner: {
            "status": "PASS",
            "production_service_start": False,
        },
    )
    adapter = tool.LiveFreshInstallerAdapters(Path("/tmp/payload"), {}, object())

    report = adapter.preflight_master()

    assert report == {
        "status": "PASS",
        "instance_material_absent": True,
        "production_service_start": False,
    }



def test_public_runtime_installs_explicit_provisioning_entrypoint() -> None:
    tool = load_tool()
    public_files = set(tool.PUBLIC_FINAL_FILES)

    assert "/usr/local/sbin/n3w-t1-provision" in public_files
    assert "/etc/systemd/system/n3wfc4-provision-resume.service" in public_files
    assert "/usr/local/sbin/n3w-t1-systemd-staged-install" in public_files
    assert "/usr/local/sbin/n3w-t1-production-activation-enable" in public_files


def test_transport_v2_requests_one_image_only_after_authorization() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert '"event": "image_requested"' in source
    assert '"event": "image_loaded"' in source
    assert "multiple_staged_image_tars_forbidden" in source
    assert "image_capacity_insufficient" in source
    assert "staged_tar_deleted" in source
    assert 'run_fresh_public_staging(' in source
