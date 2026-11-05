from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/n3w-t1-core-updater-homeassistant-target-binding-ci.yml"
FAST = ROOT / ".github/workflows/n3w-ci-fast-source-exact-closure-contract-ci.yml"
POLICY = ROOT / "docs/development/N3W_CI_POLICY_MANIFEST_V1.json"

NAME = "n3w-t1-core-updater-homeassistant-target-binding-ci.yml"


def test_target_binding_workflow_is_policy_registered_and_self_triggered() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["workflows"][NAME] == {
        "class": "EXACT",
        "draft_policy": "run",
        "exceptions": {},
    }

    fast = FAST.read_text(encoding="utf-8")
    needle = f'      - ".github/workflows/{NAME}"'
    assert fast.count(needle) == 2


def test_target_binding_workflow_reuses_frozen_p2a_artifact() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'UPSTREAM_RUN_ID: "41976542377"' in text
    assert 'UPSTREAM_ARTIFACT_ID: "13391983948"' in text
    assert "df95749cec1e48796d2cf3241d19739601fe7be78c48638284d10eec786e4fd2" in text
    assert "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973" in text
    assert "sha256:5881590fca108a6e6b5eb9fff1718baeddda9d6dd5b52d1594e3386fe33b4d66" in text
    assert "actions/download-artifact@v4" in text
    assert "docker pull" not in text
    assert "docker save" not in text


def test_target_binding_workflow_keeps_no_live_execution_path() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "ssh " not in text
    assert "scp " not in text
    assert "T1_ACCESS=false" in text
    assert "T1_MUTATION=false" in text
    assert "workflow_dispatch:" in text
    assert "timeout-minutes:" in text
    assert "concurrency:" in text
    assert "cancel-in-progress:" in text
