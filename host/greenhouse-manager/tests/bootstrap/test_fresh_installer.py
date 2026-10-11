from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from greenhouse_manager.bootstrap.fresh_broker import (
    create_fresh_broker_materials,
)
from greenhouse_manager.bootstrap.fresh_installer import (
    FreshInstallerError,
    FreshInstallerRecoveryRequired,
    run_fresh_staging,
)
from greenhouse_manager.bootstrap.fresh_product_state import (
    create_fresh_state,
)
from greenhouse_manager.bootstrap.system_init import (
    INITIALIZATION_CONFIRMATION,
    initialize_system,
)


def preflight_report() -> dict[str, object]:
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


class SourceAdapters:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def preflight(self):
        self.calls.append("preflight")
        return preflight_report()

    def load_images(self):
        self.calls.append("load_images")
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
        report = initialize_system(
            candidate_root / "identity",
            enable=True,
            confirmation=INITIALIZATION_CONFIRMATION,
        )
        return report.to_dict()

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

    def initialize_dynsec(self, _candidate_root: Path, _system_id: str):
        self.calls.append("dynsec")
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

    def stage_runtime(self, _candidate_root: Path, _system_id: str):
        self.calls.append("runtime")
        return {
            "status": "PASS",
            "source_files_staged": True,
            "network_count": 2,
            "guard_ready": True,
            "services_stopped": True,
            "production_service_start": False,
        }

    def commit_candidate(self, _candidate_root: Path, _system_id: str):
        self.calls.append("commit")
        return {
            "status": "PASS",
            "committed": True,
            "transaction_owned_only": True,
            "production_service_start": False,
        }

    def stopped_postcheck(self, _system_id: str):
        self.calls.append("postcheck")
        return {
            "status": "PASS",
            "fresh_product_staged": True,
            "node_credential_count": 0,
            "product_listener_count": 0,
            "production_service_start": False,
        }

    def cleanup(self, candidate_root: Path):
        self.calls.append("cleanup")
        shutil.rmtree(candidate_root, ignore_errors=True)
        return {
            "status": "PASS",
            "transaction_owned_only": True,
            "production_service_start": False,
        }


def test_r3_orchestrates_real_fresh_source_constructors(tmp_path: Path) -> None:
    adapters = SourceAdapters()
    candidate = tmp_path / "candidate"

    report = run_fresh_staging(adapters, candidate)

    assert report["status"] == "PASS"
    assert report["fresh_product_staged"] is True
    assert report["production_service_start"] is False
    assert report["activation_authorized"] is False
    assert report["node_credential_count"] == 0
    assert adapters.calls == [
        "preflight",
        "load_images",
        "identity",
        "state",
        "broker",
        "dynsec",
        "runtime",
        "commit",
        "postcheck",
    ]

    expected_sha = hashlib.sha256(report["system_id"].encode()).hexdigest()
    assert (candidate / "identity/INITIALIZED.json").is_file()
    assert (candidate / "manager/manager-state.sqlite3").is_file()
    assert (candidate / "n3w/replay.sqlite3").is_file()
    assert (candidate / "broker/tls/ca.pem").is_file()
    assert expected_sha


def test_dirty_minimal_host_stops_before_any_mutation(tmp_path: Path) -> None:
    adapters = SourceAdapters()

    def dirty_preflight():
        report = preflight_report()
        report["product_volumes"] = 1
        return report

    adapters.preflight = dirty_preflight  # type: ignore[method-assign]

    with pytest.raises(FreshInstallerError, match="product_volumes_invalid"):
        run_fresh_staging(adapters, tmp_path / "candidate")

    assert adapters.calls == []


def test_failure_after_mutation_cleans_only_transaction_candidate(
    tmp_path: Path,
) -> None:
    adapters = SourceAdapters()

    def fail_runtime(_candidate_root: Path, _system_id: str):
        adapters.calls.append("runtime")
        raise RuntimeError("injected")

    adapters.stage_runtime = fail_runtime  # type: ignore[method-assign]
    candidate = tmp_path / "candidate"

    with pytest.raises(FreshInstallerError, match="fresh_install_failed"):
        run_fresh_staging(adapters, candidate)

    assert not candidate.exists()
    assert adapters.calls[-1] == "cleanup"


def test_cleanup_failure_requires_manual_recovery(tmp_path: Path) -> None:
    adapters = SourceAdapters()

    def fail_runtime(_candidate_root: Path, _system_id: str):
        raise RuntimeError("injected")

    def fail_cleanup(_candidate_root: Path):
        raise RuntimeError("cleanup-injected")

    adapters.stage_runtime = fail_runtime  # type: ignore[method-assign]
    adapters.cleanup = fail_cleanup  # type: ignore[method-assign]

    with pytest.raises(
        FreshInstallerRecoveryRequired,
        match="cleanup_not_proven",
    ):
        run_fresh_staging(adapters, tmp_path / "candidate")


def test_existing_candidate_root_is_rejected_before_preflight(
    tmp_path: Path,
) -> None:
    adapters = SourceAdapters()
    candidate = tmp_path / "candidate"
    candidate.mkdir()

    with pytest.raises(
        FreshInstallerError,
        match="candidate_root_already_exists",
    ):
        run_fresh_staging(adapters, candidate)

    assert adapters.calls == []
