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
    material = {
        "schema": contract.RELEASE_SCHEMA,
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
    return {"release_id": contract.canonical_sha256(material), **material}


class Adapter:
    def __init__(self, fail_at: str | set[str] | None = None):
        self.calls = []
        if isinstance(fail_at, str):
            self.fail_at = {fail_at}
        else:
            self.fail_at = set(fail_at or ())
        self.marker_digest = "8" * 64
        self.frozen_failure = None

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
        if "start_marker" in self.fail_at:
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

    def controlled_reboot(
        self,
        _install_authorization_id,
        _reboot_authorization_id,
    ):
        return self._pass("controlled_reboot")

    def close_pre_reboot_epoch(self):
        return self._pass(
            "close_pre_reboot_epoch",
            {"session_closed": True},
        )

    def freeze_failure(self, failure):
        self.frozen_failure = copy.deepcopy(failure)
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

    def wait_for_ssh(self):
        return self._pass("wait_for_ssh")

    def start_post_reboot_epoch(self):
        return self._pass(
            "start_post_reboot_epoch",
            {"host_key_sha256": "6" * 64},
        )

    def wait_for_post_reboot_readiness(self):
        return self._pass(
            "wait_for_post_reboot_readiness",
            {
                "state": "READY",
                "board_access": False,
                "target_mutation": False,
            },
        )

    def post_reboot_acceptance(self, _release, _binding):
        return self._pass(
            "post_reboot_acceptance",
            {"acceptance_sha256": "9" * 64},
        )

    def accept_marker(self, _binding, acceptance_sha256):
        self.calls.append("accept_marker")
        if "accept_marker" in self.fail_at:
            return {"state": "FAIL"}
        return {
            "state": "ACCEPTED",
            "acceptance_sha256": acceptance_sha256,
            "T1_PRODUCTION_READY": True,
        }

    def close_post_reboot_epoch(self):
        return self._pass(
            "close_post_reboot_epoch",
            {"session_closed": True},
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
        "F4_PERSISTENCE",
        "F4_CERT_AUDIT",
        "F4_CERT_TIMER",
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


def test_r2_callback_approval_occurs_after_qualification_before_marker():
    adapter = Adapter()
    observed = []

    def approve(plan):
        observed.append((plan["run_id"], list(adapter.calls)))
        return True

    result = r2.R2Orchestrator(adapter).execute(
        release_document(),
        run_id="1" * 64,
        target_binding_sha256="5" * 64,
        approved=False,
        approval_callback=approve,
    )
    assert result["status"] == "PASS"
    assert observed == [
        (
            "1" * 64,
            ["verify_release", "start_ssh_epoch", "qualify"],
        )
    ]
    assert adapter.calls.index("qualify") < adapter.calls.index("start_marker")


def test_r2_rejects_dual_approval_authority():
    adapter = Adapter()
    with pytest.raises(
        r2.ProductionV2R2Error,
        match="production_approval_authority_ambiguous",
    ):
        r2.R2Orchestrator(adapter).execute(
            release_document(),
            run_id="1" * 64,
            target_binding_sha256="5" * 64,
            approved=True,
            approval_callback=lambda _plan: True,
        )


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



def test_r3_completes_post_reboot_acceptance_before_marker_accept_and_close():
    adapter = Adapter()
    result = r2.R3Orchestrator(adapter).execute(
        release_document(),
        run_id="1" * 64,
        target_binding_sha256="5" * 64,
        approved=True,
    )
    assert result["status"] == "PASS"
    assert result["marker_state"] == "ACCEPTED"
    assert result["device_acceptance"] == "PASS"
    assert result["T1_PRODUCTION_READY"] is True
    assert result["reflash_required"] is False
    assert adapter.calls[-6:] == [
        "wait_for_ssh",
        "start_post_reboot_epoch",
        "wait_for_post_reboot_readiness",
        "post_reboot_acceptance",
        "accept_marker",
        "close_post_reboot_epoch",
    ]


def test_r3_post_reboot_failure_finalizes_forensics_before_reflash():
    adapter = Adapter(fail_at="post_reboot_acceptance")
    result = r2.R3Orchestrator(adapter).execute(
        release_document(),
        run_id="1" * 64,
        target_binding_sha256="5" * 64,
        approved=True,
    )
    assert result["status"] == "FAIL"
    assert result["marker_state"] == "STARTED"
    assert result["error_class"] == "POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED"
    assert result["reflash_required"] is True
    assert adapter.calls[-4:] == [
        "freeze_failure",
        "collect_failure_forensics",
        "failure_session_close",
        "record_reflash_disposition",
    ]


def test_r3_marker_accept_is_last_target_acceptance_mutation():
    adapter = Adapter()
    result = r2.R3Orchestrator(adapter).execute(
        release_document(),
        run_id="1" * 64,
        target_binding_sha256="5" * 64,
        approved=True,
    )
    assert result["status"] == "PASS"
    assert adapter.calls.index("post_reboot_acceptance") < adapter.calls.index(
        "accept_marker"
    )
    assert adapter.calls.index("accept_marker") < adapter.calls.index(
        "close_post_reboot_epoch"
    )


def test_r3_cleanup_failure_after_durable_accept_preserves_device_acceptance():
    adapter = Adapter(fail_at="close_post_reboot_epoch")
    result = r2.R3Orchestrator(adapter).execute(
        release_document(),
        run_id="1" * 64,
        target_binding_sha256="5" * 64,
        approved=True,
    )
    assert result["status"] == "FAIL"
    assert result["marker_state"] == "ACCEPTED"
    assert result["error_class"] == "PROCESS_CLEANUP_FAIL"
    assert result["device_acceptance"] == "PASS"
    assert result["T1_PRODUCTION_READY"] is True
    assert result["reflash_required"] is False
    assert "record_reflash_disposition" not in adapter.calls


def test_r3_rejects_post_reboot_host_key_drift_before_acceptance():
    adapter = Adapter()
    original = adapter.start_post_reboot_epoch

    def changed():
        result = original()
        result["host_key_sha256"] = "0" * 64
        return result

    adapter.start_post_reboot_epoch = changed
    result = r2.R3Orchestrator(adapter).execute(
        release_document(),
        run_id="1" * 64,
        target_binding_sha256="5" * 64,
        approved=True,
    )
    assert result["status"] == "FAIL"
    assert result["marker_state"] == "STARTED"
    assert result["reflash_required"] is True
    assert "post_reboot_acceptance" not in adapter.calls



def test_r3_does_not_misclassify_started_failure_finalization_error_as_pre_mutation():
    adapter = Adapter(fail_at={"f3_deploy", "collect_failure_forensics"})
    with pytest.raises(
        r2.ProductionV2R2Error,
        match="failure_forensics_not_pass",
    ):
        r2.R3Orchestrator(adapter).execute(
            release_document(),
            run_id="1" * 64,
            target_binding_sha256="5" * 64,
            approved=True,
        )


def test_r3_pre_mutation_failure_can_emit_absent_marker_result_after_session_close():
    adapter = Adapter(fail_at="qualify")
    result = r2.R3Orchestrator(adapter).execute(
        release_document(),
        run_id="1" * 64,
        target_binding_sha256="5" * 64,
        approved=True,
    )
    assert result["status"] == "FAIL"
    assert result["marker_state"] == "ABSENT"
    assert result["error_class"] == "PRE_MUTATION_FAIL"
    assert result["operator_session_closed"] is True
    assert result["reflash_required"] is False



def test_r2_marker_start_unknown_is_treated_as_mutation_and_requires_reflash():
    adapter = Adapter(fail_at="start_marker")
    result = r2.R2Orchestrator(adapter).execute(
        release_document(),
        run_id="1" * 64,
        target_binding_sha256="5" * 64,
        approved=True,
    )
    assert result["status"] == "FAIL"
    assert result["state"] == "REFLASH_REQUIRED"
    assert result["failed_stage"] == "MARKER_START"
    assert result["reflash_required"] is True
    assert adapter.calls[-4:] == [
        "freeze_failure",
        "collect_failure_forensics",
        "failure_session_close",
        "record_reflash_disposition",
    ]


def test_r3_marker_start_failure_finalization_error_is_not_pre_mutation():
    adapter = Adapter(fail_at={"start_marker", "collect_failure_forensics"})
    with pytest.raises(
        r2.ProductionV2R2Error,
        match="failure_forensics_not_pass",
    ):
        r2.R3Orchestrator(adapter).execute(
            release_document(),
            run_id="1" * 64,
            target_binding_sha256="5" * 64,
            approved=True,
        )


def test_r3_pre_mutation_session_close_failure_does_not_claim_closed():
    adapter = Adapter(fail_at={"qualify", "close_pre_reboot_epoch"})
    result = r2.R3Orchestrator(adapter).execute(
        release_document(),
        run_id="1" * 64,
        target_binding_sha256="5" * 64,
        approved=True,
    )
    assert result["status"] == "FAIL"
    assert result["marker_state"] == "ABSENT"
    assert result["error_class"] == "PRE_MUTATION_FAIL"
    assert result["operator_session_closed"] is False
    assert result["reflash_required"] is False
    assert result["terminal_stage"] == "PRE_MUTATION_SESSION_CLOSE"



def test_r3_insufficient_evidence_stops_without_claiming_product_failure():
    adapter = Adapter()

    def insufficient(_release, _binding):
        adapter.calls.append("post_reboot_acceptance")
        raise r2.EvidenceInsufficientError(
            "runtime_snapshot_evidence_insufficient"
        )

    adapter.post_reboot_acceptance = insufficient
    result = r2.R3Orchestrator(adapter).execute(
        release_document(),
        run_id="1" * 64,
        target_binding_sha256="5" * 64,
        approved=True,
    )
    assert result["status"] == "FAIL"
    assert result["marker_state"] == "STARTED"
    assert result["error_class"] == (
        "POST_REBOOT_EVIDENCE_INSUFFICIENT_REFLASH_REQUIRED"
    )
    assert result["device_acceptance"] == "NOT_REACHED"
    assert result["T1_PRODUCTION_READY"] is False
    assert result["reflash_required"] is True
    assert "accept_marker" not in adapter.calls
    assert adapter.calls[-4:] == [
        "freeze_failure",
        "collect_failure_forensics",
        "failure_session_close",
        "record_reflash_disposition",
    ]


def test_r3_readiness_failure_is_terminal_before_acceptance():
    adapter = Adapter(fail_at="wait_for_post_reboot_readiness")
    result = r2.R3Orchestrator(adapter).execute(
        release_document(),
        run_id="1" * 64,
        target_binding_sha256="5" * 64,
        approved=True,
    )
    assert result["status"] == "FAIL"
    assert result["terminal_stage"] == "POST_REBOOT_READINESS"
    assert result["marker_state"] == "STARTED"
    assert result["reflash_required"] is True
    assert "post_reboot_acceptance" not in adapter.calls
    assert "accept_marker" not in adapter.calls
    assert adapter.calls[-4:] == [
        "freeze_failure",
        "collect_failure_forensics",
        "failure_session_close",
        "record_reflash_disposition",
    ]


def test_r3_preserves_sanitized_target_error_code_in_frozen_failure():
    adapter = Adapter()

    def fail_readiness():
        error = r2.ProductionV2R2Error("target_local_reboot_verify_command_failed")
        error.error_code = "post_reboot_unit_contract_invalid"
        error.target_failure_class = "VERIFY_FAILED"
        raise error

    adapter.wait_for_post_reboot_readiness = fail_readiness
    result = r2.R3Orchestrator(adapter).execute(
        release_document(),
        run_id="1" * 64,
        target_binding_sha256="5" * 64,
        approved=True,
    )
    assert result["status"] == "FAIL"
    assert adapter.frozen_failure["error_code"] == "post_reboot_unit_contract_invalid"
    assert adapter.frozen_failure["target_failure_class"] == "VERIFY_FAILED"
    assert "error" not in adapter.frozen_failure



def test_r3_rejects_unknown_syntactically_safe_error_code_from_frozen_failure():
    adapter = Adapter()

    def fail_readiness():
        error = r2.ProductionV2R2Error("target_local_reboot_verify_command_failed")
        error.error_code = "secrettoken"
        error.target_failure_class = "VERIFY_FAILED"
        raise error

    adapter.wait_for_post_reboot_readiness = fail_readiness
    result = r2.R3Orchestrator(adapter).execute(
        release_document(),
        run_id="1" * 64,
        target_binding_sha256="5" * 64,
        approved=True,
    )
    assert result["status"] == "FAIL"
    assert "error_code" not in adapter.frozen_failure
    assert adapter.frozen_failure["target_failure_class"] == "VERIFY_FAILED"
