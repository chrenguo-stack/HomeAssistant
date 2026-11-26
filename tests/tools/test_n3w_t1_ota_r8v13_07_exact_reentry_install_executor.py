from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "tools"
    / "execution_packages"
    / "n3w"
    / "t1_ota_r8v13_07"
    / "N3W_T1_R8V13_07_EXACT_REENTRY_INSTALL_TO_TERMINAL_20261125_02.py"
)
SPEC = importlib.util.spec_from_file_location("r8v13_07_exact_install_executor", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)



class FakeOps:
    def __init__(self, states):
        import json
        self.states = [json.loads(json.dumps(state)) for state in states]
        self.index = 0
        self.calls = []
        self.launch = "f" * 64

    def preflight_static(self):
        self.calls.append("preflight_static")

    def read_transaction(self):
        import json
        return json.loads(json.dumps(self.states[self.index]))

    def validate_runtime_binding(self, document):
        self.calls.append("validate_runtime_binding")
        return self.launch

    def require_release_authority(self):
        self.calls.append("require_release_authority")

    def validate_u4_entry_artifacts(self, document, launch_sha256):
        self.calls.append("validate_u4_entry_artifacts")

    def submit_install(self):
        self.calls.append("submit_install")
        self.index += 1

    def ensure_install_authority(self, document, launch_sha256):
        self.calls.append("ensure_install_authority")

    def start_worker(self, attempt):
        self.calls.append(f"start_worker_{attempt}")
        if self.index < len(self.states) - 1:
            self.index += 1
        return 0

    def verify_committed(self, document):
        self.calls.append("verify_committed")

    def verify_rolled_back(self, document):
        self.calls.append("verify_rolled_back")

def tx(*, status="ACTIVE", phase=None, recovery=False, start=False, failure=None):
    phase = mod.U4 if phase is None else phase
    document = {
        "transaction_id_sha256": mod.EXPECTED_TX,
        "status": status,
        "phase": phase,
        "failure_code": failure,
        "recovery_required": recovery,
        "authorization_claimed": phase in {mod.U9, mod.U10, mod.U11, mod.U12, mod.U13A, mod.U13B},
        "authorization_consumed": phase in {mod.U9, mod.U10, mod.U11, mod.U12, mod.U13A, mod.U13B},
        "authorization_id_sha256": None,
        "usb_binding_mode": "existing_filesystem",
        "usb_filesystem_uuid": mod.EXPECTED_USB,
        "current_image_ref": mod.EXPECTED_PREDECESSOR_REF,
        "target_image_ref": mod.EXPECTED_TARGET_REF,
        "target_artifact_verified": True,
        "prepared_image_materials": {
            "target": {
                "kind": "target",
                "image_ref": mod.EXPECTED_TARGET_REF,
                "archive_sha256": mod.EXPECTED_TARGET_SHA,
                "archive_size_bytes": mod.EXPECTED_TARGET_SIZE,
                "verified": True,
                "fsynced": True,
            },
            "predecessor": {
                "kind": "predecessor",
                "image_ref": mod.EXPECTED_PREDECESSOR_REF,
                "archive_sha256": mod.EXPECTED_PREDECESSOR_SHA,
                "archive_size_bytes": mod.EXPECTED_PREDECESSOR_SIZE,
                "verified": True,
                "fsynced": True,
            },
        },
    }
    if document["authorization_claimed"]:
        import hashlib
        document["authorization_id_sha256"] = hashlib.sha256(mod.AUTH_ID.encode()).hexdigest()
    if start:
        document["predecessor_start"] = {"launch_sha256": "f" * 64}
    return document


def committed():
    document = tx(status="COMMITTED", phase=mod.U13A)
    document["recovery_required"] = False
    document["target_activation"] = "WRITES_POSSIBLE"
    document["target_loaded_image_id"] = "sha256:" + "9" * 64
    document["target_acceptance"] = {
        "receipt": {
            "images": {
                "homeassistant": {
                    "reference": mod.EXPECTED_TARGET_REF,
                    "runtime_id": document["target_loaded_image_id"],
                }
            },
            "observations": {
                "monitoring_path": "a" * 64,
                "protected_data": "b" * 64,
            },
        }
    }
    return document


def rolled_back_postcutover():
    document = tx(status="ROLLED_BACK", phase=mod.U13B)
    document["recovery_required"] = False
    return document


def rolled_back_precutover(phase=mod.U8):
    document = tx(status="ROLLED_BACK", phase=phase, start=True)
    document["recovery_required"] = False
    document["pre_cutover_predecessor_restored"] = True
    document["authorization_claimed"] = False
    document["authorization_consumed"] = False
    document["authorization_id_sha256"] = None
    return document


def test_clean_u4_path_runs_install_authority_worker_and_commits():
    ops = FakeOps([tx(), tx(phase=mod.U5), committed()])
    assert mod.execute(ops) == 0
    assert ops.calls == [
        "preflight_static",
        "validate_runtime_binding",
        "require_release_authority",
        "validate_u4_entry_artifacts",
        "submit_install",
        "ensure_install_authority",
        "start_worker_1",
        "verify_committed",
    ]


def test_u5_reentry_does_not_resubmit_install():
    ops = FakeOps([tx(phase=mod.U5), committed()])
    assert mod.execute(ops) == 0
    assert "submit_install" not in ops.calls
    assert ops.calls.count("ensure_install_authority") == 1
    assert ops.calls.count("start_worker_1") == 1


def test_u6_without_predecessor_start_is_safe_forward_reentry():
    ops = FakeOps([tx(phase=mod.U6), committed()])
    assert mod.execute(ops) == 0
    assert "submit_install" not in ops.calls
    assert "validate_runtime_binding" in ops.calls
    assert "ensure_install_authority" in ops.calls


def test_pre_cutover_recovery_hands_directly_to_product_worker():
    ops = FakeOps([tx(phase=mod.U7, recovery=True, start=True), rolled_back_precutover(mod.U7)])
    assert mod.execute(ops) == 2
    assert "validate_runtime_binding" not in ops.calls
    assert "require_release_authority" not in ops.calls
    assert "ensure_install_authority" not in ops.calls
    assert ops.calls == ["preflight_static", "start_worker_1", "verify_rolled_back"]


def test_post_authorization_recovery_hands_directly_to_product_worker():
    ops = FakeOps([tx(phase=mod.U10, recovery=True, start=True), rolled_back_postcutover()])
    assert mod.execute(ops) == 2
    assert ops.calls == ["preflight_static", "start_worker_1", "verify_rolled_back"]


def test_u12_can_forward_commit_through_product_worker():
    active = tx(phase=mod.U12, start=True)
    active["target_activation"] = "WRITES_POSSIBLE"
    ops = FakeOps([active, committed()])
    assert mod.execute(ops) == 0
    assert ops.calls == ["preflight_static", "start_worker_1", "verify_committed"]


def test_recoverable_active_state_gets_one_bounded_second_worker_dispatch():
    first = tx(phase=mod.U9, start=True)
    second = tx(phase=mod.U10, recovery=True, start=True)
    ops = FakeOps([first, second, rolled_back_postcutover()])
    assert mod.execute(ops) == 2
    assert ops.calls.count("start_worker_1") == 1
    assert ops.calls.count("start_worker_2") == 1
    assert ops.calls[-1] == "verify_rolled_back"


def test_terminal_committed_is_classified_without_replay():
    ops = FakeOps([committed()])
    assert mod.execute(ops) == 0
    assert ops.calls == ["preflight_static", "verify_committed"]


def test_terminal_pre_cutover_rollback_is_valid_terminal_state():
    ops = FakeOps([rolled_back_precutover()])
    assert mod.execute(ops) == 2
    assert ops.calls == ["preflight_static", "verify_rolled_back"]


def test_u4_pre_cutover_failure_is_not_replayed():
    document = tx(failure="ha_usb_install_revalidation_failed")
    ops = FakeOps([document])
    assert mod.execute(ops) == 3
    assert ops.calls == ["preflight_static"]


def test_second_worker_nonterminal_result_leaves_product_timer_owner():
    first = tx(phase=mod.U9, start=True)
    second = tx(phase=mod.U10, recovery=True, start=True)
    third = tx(phase=mod.U10, recovery=True, start=True)
    ops = FakeOps([first, second, third])
    assert mod.execute(ops) == 4
    assert ops.calls == ["preflight_static", "start_worker_1", "start_worker_2"]


def test_exact_transaction_drift_blocks_before_any_product_action():
    document = tx()
    document["transaction_id_sha256"] = "0" * 64
    ops = FakeOps([document])
    try:
        mod.execute(ops)
    except mod.GateError as error:
        assert str(error) == "TRANSACTION_ID_DRIFT"
    else:
        raise AssertionError("expected GateError")
    assert ops.calls == ["preflight_static"]


def test_executor_has_no_shell_local_mutation_authority_or_fixed_workdir():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "MUTATION_STARTED" not in source
    assert "INSTALL_INTENT_SUBMITTED" not in source
    assert "EXPECTED_OLD_INSTALL_BINDING" not in source
    assert "test ! -e" not in source
    assert "mktemp -d /tmp/n3w-r8v13-07-fresh-tx-a-install" not in source


def test_executor_never_directly_invokes_live_resume_pending():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert '["systemctl", "start", RECOVERY_UNIT]' in source
    assert '"--resume-pending"' not in source
    assert "n3w-t1-ha-recovery-retry.service" in source


def test_worker_reentry_matrix():
    assert mod.worker_reentry_admitted(tx(phase=mod.U5))
    assert mod.worker_reentry_admitted(tx(phase=mod.U6))
    assert mod.worker_reentry_admitted(tx(phase=mod.U7, recovery=True, start=True))
    assert mod.worker_reentry_admitted(tx(phase=mod.U9, start=True))
    assert not mod.worker_reentry_admitted(tx())
    assert not mod.worker_reentry_admitted(committed())


def test_install_authority_reuse_contract_accepts_only_exact_current_grant():
    binding = "1" * 64
    launch = "2" * 64
    exact = {
        "schema": "gh.n3w-t1-ha-install-authority/3",
        "binding_sha256": binding,
        "authorization_id": mod.AUTH_ID,
        "launch_sha256": launch,
        "expires_at_unix": 200,
    }
    assert mod.install_authority_reusable(
        exact, binding_sha256=binding, launch_sha256=launch, now=100
    )
    assert not mod.install_authority_reusable(
        {**exact, "binding_sha256": "3" * 64},
        binding_sha256=binding,
        launch_sha256=launch,
        now=100,
    )
    assert not mod.install_authority_reusable(
        {**exact, "authorization_id": mod.AUTH_ID + "_conflict"},
        binding_sha256=binding,
        launch_sha256=launch,
        now=100,
    )
    assert not mod.install_authority_reusable(
        {**exact, "launch_sha256": "4" * 64},
        binding_sha256=binding,
        launch_sha256=launch,
        now=100,
    )
    assert not mod.install_authority_reusable(
        {**exact, "expires_at_unix": 100},
        binding_sha256=binding,
        launch_sha256=launch,
        now=100,
    )


def test_old_different_binding_is_not_hard_coded_as_a_gate():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "EXPECTED_OLD_INSTALL_BINDING" not in source
    assert "install_authority_reusable" in source


def test_committed_durable_evidence_validator_rejects_malformed_receipt():
    good = committed()
    mod.validate_committed_document(good)

    missing = committed()
    del missing["target_acceptance"]["receipt"]
    try:
        mod.validate_committed_document(missing)
    except mod.GateError as error:
        assert str(error) == "COMMIT_ACCEPTANCE_MISSING"
    else:
        raise AssertionError("expected missing receipt rejection")

    bad_observations = committed()
    bad_observations["target_acceptance"]["receipt"]["observations"] = {"monitoring_path": "a" * 64}
    try:
        mod.validate_committed_document(bad_observations)
    except mod.GateError as error:
        assert str(error) == "COMMIT_ACCEPTANCE_OBSERVATIONS_INVALID"
    else:
        raise AssertionError("expected observation-set rejection")

    wrong_runtime = committed()
    wrong_runtime["target_acceptance"]["receipt"]["images"]["homeassistant"]["runtime_id"] = "sha256:" + "8" * 64
    try:
        mod.validate_committed_document(wrong_runtime)
    except mod.GateError as error:
        assert str(error) == "COMMIT_ACCEPTANCE_RUNTIME_ID_DRIFT"
    else:
        raise AssertionError("expected runtime-id rejection")


def test_recovery_dispatch_uses_product_recovery_install_guard():
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "require_recovery_install()" in source
    assert '["systemctl", "start", RECOVERY_UNIT]' in source


def test_global_preflight_does_not_require_release_manifest_for_recovery():
    source = MODULE_PATH.read_text(encoding="utf-8")
    preflight = source.split("def preflight_static", 1)[1].split("def read_transaction", 1)[0]
    assert "EXPECTED_PYZ" in preflight
    assert "EXPECTED_MANIFEST" not in preflight
    assert "APPROVED" not in preflight


def test_exact_executor_binds_current_u4_physical_evidence() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    for literal in (
        "f6eb053e9eb21b034e98f7651e179194b0b3eed61ce561df978c4743c796467a",
        "9d69992a72c3b8dd60f33ebcf00ac7c8fcf88e255c7fadb8878d15aa86f10ffa",
        "59a920dda80e9ff009aeaea64f6b87163c9c6b48b4791a0f9da6d39b2be5e620",
        "96ebc1da9fff3a1df68b25eb5d880d407245364a5a5d52509abd3023beeacee3",
        "814a7f974c5c7eb3ddd8703c5200d6b5bb89a15145851da15868db94dcda16fc",
        "e99e5d494fd8c39172dcf2d25ae50ae3dfcbdc8f15377eebc6c488b1f0209351",
        "304683dee3ff75785215710c5a4a8ffbb12ae0b0912101474b969a46e035c83b",
        "67877cffd28b1c94de17f6b8eecabd1b579649f7e282fdfc65e4bcfcfd5fdc26",
    ):
        assert literal in source


def test_exact_executor_does_not_mutate_release_pin_directly() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    block = source.split("def require_release_authority", 1)[1].split("def validate_u4_entry_artifacts", 1)[0]
    assert 'pin["expires_at_unix"] =' not in source
    assert "atomic_private_json(PIN" not in source
    assert "os.replace" not in block
    assert "LocalApprovedHaRelease" in block
    assert "RELEASE_AUTHORITY=PASS" in block


def test_exact_executor_requires_explicit_install_authorization() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert 'INSTALL_APPROVAL_ENV = "N3W_T1_R8V13_07_FRESH_TX_A_INSTALL_APPROVED"' in source
    assert 'os.environ.get(INSTALL_APPROVAL_ENV) != "YES"' in source
    assert "EXPLICIT_INSTALL_AUTHORIZATION_REQUIRED" in source


def test_u5_reentry_skips_exact_u4_entry_artifact_check() -> None:
    ops = FakeOps([tx(phase=mod.U5), committed()])
    assert mod.execute(ops) == 0
    assert "validate_u4_entry_artifacts" not in ops.calls
    assert "submit_install" not in ops.calls
    assert "require_release_authority" in ops.calls


def test_u4_exact_entry_check_happens_before_install_submission() -> None:
    ops = FakeOps([tx(), tx(phase=mod.U5), committed()])
    assert mod.execute(ops) == 0
    assert ops.calls.index("validate_u4_entry_artifacts") < ops.calls.index("submit_install")
