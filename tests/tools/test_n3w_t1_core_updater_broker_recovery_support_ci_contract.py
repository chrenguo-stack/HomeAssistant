from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAME = "n3w-t1-core-updater-broker-recovery-support-ci.yml"
WORKFLOW = ROOT / ".github/workflows" / NAME
FAST = ROOT / ".github/workflows/n3w-ci-fast-source-exact-closure-contract-ci.yml"
POLICY = ROOT / "docs/development/N3W_CI_POLICY_MANIFEST_V1.json"


def test_broker_recovery_support_workflow_is_policy_registered_and_fast_triggered():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["workflows"][NAME] == {
        "class": "EXACT",
        "draft_policy": "run",
        "exceptions": {},
    }
    fast = FAST.read_text(encoding="utf-8")
    needle = f'      - ".github/workflows/{NAME}"'
    assert fast.count(needle) == 2
    test_needle = (
        '      - "tests/tools/'
        'test_n3w_t1_core_updater_broker_recovery_support_ci_contract.py"'
    )
    assert fast.count(test_needle) == 2


def test_broker_recovery_support_workflow_builds_and_rechecks_exact_artifact():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "n3w_t1_core_updater_broker_support.py build" in text
    assert "n3w_t1_core_updater_broker_support.py verify" in text
    assert "actions/upload-artifact@v4" in text
    assert "actions/download-artifact@v4" in text
    assert "recover-broker-pending" in text
    assert "n3w_t1_core_updater_broker_recovery.py" in text
    assert "test_n3w_t1_core_updater_broker_support.py" in text
    assert "test_n3w_t1_core_updater_a2.py" in text


def test_broker_recovery_support_workflow_has_bounded_pr_execution_and_no_live_path():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "concurrency:" in text
    assert "cancel-in-progress:" in text
    assert "timeout-minutes:" in text
    assert "ssh " not in text
    assert "scp " not in text
    assert "T1_ACCESS=false" in text
    assert "T1_MUTATION=false" in text
    assert "BOARD_ACCESS=false" in text
    assert "PRODUCTION_SERVICE_START=false" in text
