from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract = load("n3w_t1_production_v2_contract", "n3w_t1_production_v2_contract.py")
r2 = load("n3w_t1_production_v2_r2_test", "n3w_t1_production_v2.py")


def release_document():
    return {
        "schema": contract.RELEASE_SCHEMA,
        "release_id": "a" * 64,
        "source_head": "b" * 40,
        "source_tree": "c" * 40,
        "os_contract": {
            "ID": "ubuntu",
            "VERSION_ID": "26.04",
            "VERSION_CODENAME": "resolute",
            "PRETTY_NAME": "Armbian OS 26.05.0 resolute",
            "BOARD": "S912-Phicomm-T1",
            "BOARD_NAME": "Aml.S912",
            "VERSION": "26.05.0",
            "BRANCH": "current",
            "ARCH": "arm64",
            "IMAGE_TYPE": "rebuild",
            "kernel_arch": "aarch64",
        },
        "packages": {
            "docker.io": "29.1.3-0ubuntu4.1",
            "docker-compose-v2": "2.40.3+ds1-0ubuntu1",
        },
        "apt_source_policy": {
            "host": "ports.ubuntu.com",
            "suite": "resolute",
            "component": "universe",
            "architecture": "arm64",
        },
        "artifacts": {
            name: {"sha256": str(index % 10) * 64, "size_bytes": index}
            for index, name in enumerate(sorted(contract.REQUIRED_RELEASE_ARTIFACTS), start=1)
        },
        "capacity": {"minimum_post_peak_free_bytes": 5 * 1024**3},
        "public_evidence_fields": ["status", "release_id", "source_head"],
    }


class Adapter:
    def __init__(self, fail_at: str | set[str] | None = None):
        self.calls = []
        if isinstance(fail_at, str):
            self.fail_at = {fail_at}
        else:
            self.fail_at = set(fail_at or ())
        self.marker_digest = "8" * 64

    def _pass(self, name, extra=None):
        self.calls.append(name)
        if name in self.fail_at:
            return {"status": "FAIL"}
        return {"status": "PASS", **(extra or {})}

    def verify_release(self, _release):
        return self._pass("verify_release")

    def start_ssh_epoch(self):
        return self._pass("start_ssh_epoch", {"host_key_sha256": "6" * 64})

    def qualify(self, _release):
        return self._pass("qualify")

    def start_marker(self, _binding):
        self.calls.append("start_marker")
        if self.fail_at == "start_marker":
            return {"state": "FAIL"}
        return {"state": "STARTED"}

    def marker_sha256(self):
        self.calls.append("marker_sha256")
        return self.marker_digest

    def host_baseline(self, _packages):
        return self._pass("host_baseline")

    def f3_deploy(self, _context):
        return self._pass("f3_deploy")

    def provision(self):
        return self._pass("provision")

    def f4_action(self, action, _authorization_id):
        return self._pass(action)

    def controlled_reboot(self, _authorization_id):
        return self._pass("controlled_reboot")

    def close_pre_reboot_epoch(self):
        return self._pass(
            "close_pre_reboot_epoch",
            {"session_closed": True},
        )

    def freeze_failure(self, _failure):
        return self._pass("freeze_failure")

    def collect_failure_forensics(self):
        return self._pass(
            "collect_failure_forensics",
            {"evidence_complete": True},
        )

    def failure_session_close(self):
        return self._pass(
            "failure_session_close",
            {"session_closed": True},
        )

    def record_reflash_disposition(self):
        return self._pass(
            "record_reflash_disposition",
            {"reflash_required": True},
        )


def test_r2_orchestrator_preserves_frozen_pre_reboot_order_and_stops_at_reboot():
    adapter = Adapter()
    result = r2.R2Orchestrator(adapter).execute(
        release_document(),
        run_id="1" * 64,
        target_binding_sha256="5" * 64,
        approved=True,
    )

    assert result["status"] == "PASS"
    assert result["state"] == "REBOOT_PENDING"
    assert result["post_reboot_acceptance_complete"] is False
    assert result["automatic_retry"] is False
    assert result["run_context"]["action"] == "F3_DEPLOY"
    assert adapter.calls == [
        "verify_release",
        "start_ssh_epoch",
        "qualify",
        "start_marker",
        "marker_sha256",
        "host_baseline",
        "f3_deploy",
        "provision",
        "F4_PREPARE",
        "F4_ACTIVATE",
        "F4_ACCEPT",
        "PERSIST_CERT",
        "controlled_reboot",
        "close_pre_reboot_epoch",
    ]


def test_r2_failure_is_fail_fast_and_finalizes_before_reflash():
    adapter = Adapter(fail_at="f3_deploy")
    result = r2.R2Orchestrator(adapter).execute(
        release_document(),
        run_id="1" * 64,
        target_binding_sha256="5" * 64,
        approved=True,
    )
    assert result["status"] == "FAIL"
    assert result["state"] == "REFLASH_REQUIRED"
    assert result["failed_stage"] == "F3_DEPLOY"
    assert result["evidence_complete"] is True
    assert result["operator_session_closed"] is True
    assert result["reflash_required"] is True
    assert result["automatic_retry"] is False
    assert adapter.calls.count("f3_deploy") == 1
    assert "provision" not in adapter.calls
    assert "F4_PREPARE" not in adapter.calls
    assert adapter.calls[-4:] == [
        "freeze_failure",
        "collect_failure_forensics",
        "failure_session_close",
        "record_reflash_disposition",
    ]


def test_r2_requires_one_top_level_approval_before_marker_or_mutation():
    adapter = Adapter()
    with pytest.raises(r2.ProductionV2R2Error, match="production_approval_required"):
        r2.R2Orchestrator(adapter).execute(
            release_document(),
            run_id="1" * 64,
            target_binding_sha256="5" * 64,
            approved=False,
        )
    assert adapter.calls == [
        "verify_release",
        "start_ssh_epoch",
        "qualify",
        "close_pre_reboot_epoch",
    ]


def test_internal_f4_action_ids_are_deterministic_distinct_and_compatible():
    values = {
        action: r2.derive_internal_action_id("1" * 64, action)
        for action in r2.F4_INTERNAL_ACTIONS
    }
    assert len(set(values.values())) == len(values)
    assert all(r2.F4_AUTH_PATTERN.fullmatch(value) for value in values.values())
    assert values == {
        action: r2.derive_internal_action_id("1" * 64, action)
        for action in r2.F4_INTERNAL_ACTIONS
    }


def test_host_baseline_command_uses_only_release_bound_package_versions():
    argv = r2.host_baseline_install_argv(release_document())
    assert "--docker-io-package-version" in argv
    assert "29.1.3-0ubuntu4.1" in argv
    assert "--docker-compose-v2-package-version" in argv
    assert "2.40.3+ds1-0ubuntu1" in argv
    assert "latest" not in argv


def test_f3_normal_path_requires_external_run_context_and_no_static_authority():
    argv = r2.f3_apply_argv("/private/run-context.json")
    assert "--run-context" in argv
    assert "--authorization-id" not in argv


def test_r2_self_check_excludes_repair_and_recovery_normal_path():
    report = r2.self_check()
    assert report["status"] == "PASS"
    assert report["forbidden_normal_path_tokens"] == []


def test_r2_started_failure_refuses_reflash_before_forensics_complete():
    adapter = Adapter(fail_at={"f3_deploy", "collect_failure_forensics"})
    with pytest.raises(r2.ProductionV2R2Error, match="failure_forensics_not_pass"):
        r2.R2Orchestrator(adapter).execute(
            release_document(),
            run_id="1" * 64,
            target_binding_sha256="5" * 64,
            approved=True,
        )
    assert "failure_session_close" not in adapter.calls
    assert "record_reflash_disposition" not in adapter.calls


def test_r2_started_failure_refuses_reflash_before_session_close():
    adapter = Adapter(fail_at={"f3_deploy", "failure_session_close"})
    with pytest.raises(r2.ProductionV2R2Error, match="failure_session_close_not_pass"):
        r2.R2Orchestrator(adapter).execute(
            release_document(),
            run_id="1" * 64,
            target_binding_sha256="5" * 64,
            approved=True,
        )
    assert "record_reflash_disposition" not in adapter.calls
