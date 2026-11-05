from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEDICATED = ROOT / ".github/workflows/n3w-t1-core-updater-ha-template-readonly-preflight-ci.yml"
FAST = ROOT / ".github/workflows/n3w-ci-fast-source-exact-closure-contract-ci.yml"
POLICY = ROOT / "docs/development/N3W_CI_POLICY_MANIFEST_V1.json"

NAME = "n3w-t1-core-updater-ha-template-readonly-preflight-ci.yml"


def test_readonly_preflight_workflow_is_policy_registered_and_self_triggered():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["workflows"][NAME] == {
        "class": "FAST",
        "draft_policy": "run",
        "exceptions": {},
    }

    fast = FAST.read_text(encoding="utf-8")
    needle = f'      - ".github/workflows/{NAME}"'
    assert fast.count(needle) == 2


def test_readonly_preflight_workflow_keeps_exact_source_and_readonly_scope():
    text = DEDICATED.read_text(encoding="utf-8")
    assert "SOURCE_HEAD:" in text
    assert 'test "$(git rev-parse HEAD)" = "$SOURCE_HEAD"' in text
    assert "timeout-minutes:" in text
    assert "concurrency:" in text
    assert "cancel-in-progress:" in text
    assert "n3w_t1_core_updater_ha_template_convergence.py" in text
    assert "ha_template_convergence_readonly_preflight/executor.py" in text
    assert "workflow_dispatch:" in text
