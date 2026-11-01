from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from greenhouse_manager.bootstrap.fresh_broker import (
    audit_fresh_dynsec_document,
    create_fresh_broker_materials,
    provision_fresh_service_identities,
    verify_fresh_broker_materials,
)
from greenhouse_manager.bootstrap.fresh_installer import (
    FreshInstallerError,
    run_fresh_staging,
)
from greenhouse_manager.bootstrap.fresh_product_state import (
    audit_fresh_state,
    create_fresh_state,
)
from greenhouse_manager.bootstrap.system_init import (
    INITIALIZATION_CONFIRMATION,
    initialize_system,
    verify_initialization,
)


class RecordingTransport:
    def __init__(self) -> None:
        self.commands: list[dict[str, Any]] = []

    def execute(self, commands):
        self.commands.extend(dict(command) for command in commands)
        return tuple({"command": command["command"]} for command in commands)


class HostOnlyFreshInstall:
    def __init__(self, host_root: Path) -> None:
        self.host_root = host_root
        self.host_root.mkdir(mode=0o700)
        self.images = host_root / "docker-images"
        self.final = host_root / "product"
        self.calls: list[str] = []

    def preflight(self):
        self.calls.append("preflight")
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
            "product_images": 0 if not self.images.exists() else 3,
            "product_volumes": 0,
            "product_networks": 0,
            "product_listeners": 0,
            "product_paths_absent": not self.final.exists(),
            "product_units_absent": True,
            "product_dispatcher_absent": True,
            "product_firewall_absent": True,
            "production_service_start": False,
        }

    def load_images(self):
        self.calls.append("load_images")
        self.images.mkdir(mode=0o700)
        for name in ("homeassistant", "manager", "broker"):
            (self.images / name).write_text("offline\n", encoding="utf-8")
        return {
            "status": "PASS",
            "image_count": 3,
            "offline": True,
            "registry_pull": False,
            "platform": "linux/arm64",
            "production_service_start": False,
        }

    def create_identity(self, candidate_root: Path):
        self.calls.append("identity")
        return initialize_system(
            candidate_root / "identity",
            enable=True,
            confirmation=INITIALIZATION_CONFIRMATION,
        ).to_dict()

    def create_state(self, candidate_root: Path, system_id_sha256: str):
        self.calls.append("state")
        manager = candidate_root / "manager"
        n3w = candidate_root / "n3w"
        manager.mkdir(mode=0o700)
        n3w.mkdir(mode=0o700)
        return create_fresh_state(
            manager,
            n3w,
            expected_system_id_sha256=system_id_sha256,
        )

    def create_broker(self, candidate_root: Path, system_id: str):
        self.calls.append("broker")
        return create_fresh_broker_materials(
            candidate_root / "broker",
            system_id=system_id,
        ).to_dict()

    def initialize_dynsec(self, candidate_root: Path, system_id: str):
        self.calls.append("dynsec")
        transport = RecordingTransport()
        provision_fresh_service_identities(
            transport,
            candidate_root / "broker/service-credentials",
            system_id=system_id,
        )

        defaults: dict[str, bool] = {}
        clients = [{"username": "admin"}]
        roles: list[dict[str, str]] = []
        for command in transport.commands:
            if command["command"] == "setDefaultACLAccess":
                defaults = {
                    str(item["acltype"]): bool(item["allow"])
                    for item in command["acls"]
                }
            elif command["command"] == "createRole":
                roles.append({"rolename": str(command["rolename"])})
            elif command["command"] == "createClient":
                clients.append({"username": str(command["username"])})

        document = {
            "defaultACLAccess": defaults,
            "clients": clients,
            "roles": roles,
        }
        broker_data = candidate_root / "broker-data"
        broker_data.mkdir(mode=0o700)
        path = broker_data / "dynamic-security.json"
        path.write_text(json.dumps(document, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(path, 0o600)
        report = audit_fresh_dynsec_document(path, system_id=system_id)
        return {
            **report,
            "production_service_start": False,
        }

    def stage_runtime(self, candidate_root: Path, _system_id: str):
        self.calls.append("runtime")
        runtime = candidate_root / "runtime"
        runtime.mkdir(mode=0o700)
        (runtime / "networks.json").write_text(
            json.dumps(["n3wfc4-private", "n3wfc4-services"]) + "\n",
            encoding="utf-8",
        )
        (runtime / "guard.ready").write_text("true\n", encoding="utf-8")
        (runtime / "services.json").write_text(
            json.dumps(
                {
                    "broker": {"running": False, "enabled": False},
                    "manager": {"running": False, "enabled": False},
                    "homeassistant": {"running": False, "enabled": False},
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return {
            "status": "PASS",
            "source_files_staged": True,
            "network_count": 2,
            "guard_ready": True,
            "services_stopped": True,
            "production_service_start": False,
        }

    def commit_candidate(self, candidate_root: Path, _system_id: str):
        self.calls.append("commit")
        if self.final.exists():
            raise RuntimeError("final_already_exists")
        candidate_root.rename(self.final)
        return {
            "status": "PASS",
            "committed": True,
            "transaction_owned_only": True,
            "production_service_start": False,
        }

    def stopped_postcheck(self, system_id: str):
        self.calls.append("postcheck")
        identity = verify_initialization(self.final / "identity")
        if identity.system_id != system_id:
            raise RuntimeError("identity_drift")
        system_id_sha256 = hashlib.sha256(system_id.encode()).hexdigest()
        state = audit_fresh_state(
            self.final / "manager",
            self.final / "n3w",
            expected_system_id_sha256=system_id_sha256,
        )
        broker = verify_fresh_broker_materials(self.final / "broker")
        dynsec = audit_fresh_dynsec_document(
            self.final / "broker-data/dynamic-security.json",
            system_id=system_id,
        )
        services = json.loads(
            (self.final / "runtime/services.json").read_text(encoding="utf-8")
        )
        if any(item["running"] or item["enabled"] for item in services.values()):
            raise RuntimeError("service_started")
        return {
            "status": "PASS",
            "fresh_product_staged": True,
            "node_credential_count": max(
                int(state["node_credential_count"]),
                int(broker.node_credential_count),
                int(dynsec["node_client_count"]),
            ),
            "product_listener_count": 0,
            "production_service_start": False,
        }

    def cleanup(self, candidate_root: Path):
        self.calls.append("cleanup")
        shutil.rmtree(candidate_root, ignore_errors=True)
        shutil.rmtree(self.final, ignore_errors=True)
        shutil.rmtree(self.images, ignore_errors=True)
        return {
            "status": "PASS",
            "transaction_owned_only": True,
            "production_service_start": False,
        }


def test_full_fresh_install_from_empty_host(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    host = tmp_path / "host"
    adapters = HostOnlyFreshInstall(host)
    candidate = host / "candidate"

    report = run_fresh_staging(adapters, candidate)

    assert report["status"] == "PASS"
    assert report["fresh_product_staged"] is True
    assert report["node_credential_count"] == 0
    assert report["production_service_start"] is False
    assert report["activation_authorized"] is False
    assert not candidate.exists()
    assert adapters.final.is_dir()

    services = json.loads(
        (adapters.final / "runtime/services.json").read_text(encoding="utf-8")
    )
    assert all(
        item == {"running": False, "enabled": False}
        for item in services.values()
    )

    secret_values = [
        (
            adapters.final
            / f"broker/service-credentials/{service}/password"
        ).read_text(encoding="utf-8").strip()
        for service in ("manager", "provisioning", "homeassistant")
    ]
    secret_values.append(
        (adapters.final / "broker/private/dynsec-admin-password")
        .read_text(encoding="utf-8")
        .strip()
    )
    output = capsys.readouterr().out
    serialized_report = json.dumps(report, sort_keys=True)
    assert all(secret not in output for secret in secret_values)
    assert all(secret not in serialized_report for secret in secret_values)


def test_dirty_baseline_stops_before_mutation(tmp_path: Path) -> None:
    host = tmp_path / "host"
    adapters = HostOnlyFreshInstall(host)
    adapters.final.mkdir()

    with pytest.raises(
        FreshInstallerError,
        match="product_paths_absent_invalid",
    ):
        run_fresh_staging(adapters, host / "candidate")

    assert adapters.calls == ["preflight"]
    assert not adapters.images.exists()


def test_partial_candidate_blocks_replay(tmp_path: Path) -> None:
    host = tmp_path / "host"
    adapters = HostOnlyFreshInstall(host)
    candidate = host / "candidate"
    candidate.mkdir()
    (candidate / "partial").write_text("owned-but-unresolved\n", encoding="utf-8")

    with pytest.raises(
        FreshInstallerError,
        match="candidate_root_already_exists",
    ):
        run_fresh_staging(adapters, candidate)

    assert adapters.calls == []
    assert (candidate / "partial").is_file()


def test_fault_cleanup_preserves_unrelated_host_state(tmp_path: Path) -> None:
    host = tmp_path / "host"
    adapters = HostOnlyFreshInstall(host)
    sentinel = host / "baseline-preserve.txt"
    sentinel.write_text("keep\n", encoding="utf-8")

    def fail_runtime(_candidate_root: Path, _system_id: str):
        adapters.calls.append("runtime")
        raise RuntimeError("fault-injected")

    adapters.stage_runtime = fail_runtime  # type: ignore[method-assign]

    with pytest.raises(FreshInstallerError, match="fresh_install_failed"):
        run_fresh_staging(adapters, host / "candidate")

    assert sentinel.read_text(encoding="utf-8") == "keep\n"
    assert not (host / "candidate").exists()
    assert not adapters.final.exists()
    assert not adapters.images.exists()
    assert adapters.calls[-1] == "cleanup"


def test_before_mutation_runs_after_preflight_before_image_load(
    tmp_path: Path,
) -> None:
    host = tmp_path / "host"
    adapters = HostOnlyFreshInstall(host)
    events: list[str] = []

    original_preflight = adapters.preflight
    original_load = adapters.load_images

    def preflight():
        events.append("preflight")
        return original_preflight()

    def load_images():
        events.append("load_images")
        return original_load()

    adapters.preflight = preflight  # type: ignore[method-assign]
    adapters.load_images = load_images  # type: ignore[method-assign]

    def claim() -> None:
        events.append("claim")

    run_fresh_staging(
        adapters,
        host / "candidate",
        before_mutation=claim,
    )

    assert events[:3] == ["preflight", "claim", "load_images"]


def test_partial_image_load_failure_enters_cleanup(tmp_path: Path) -> None:
    host = tmp_path / "host"
    adapters = HostOnlyFreshInstall(host)

    def partial_load():
        adapters.calls.append("load_images")
        adapters.images.mkdir(mode=0o700)
        (adapters.images / "manager").write_text("partial\n", encoding="utf-8")
        raise RuntimeError("partial-load")

    adapters.load_images = partial_load  # type: ignore[method-assign]

    with pytest.raises(FreshInstallerError, match="fresh_install_failed"):
        run_fresh_staging(adapters, host / "candidate")

    assert adapters.calls[-1] == "cleanup"
    assert not adapters.images.exists()
