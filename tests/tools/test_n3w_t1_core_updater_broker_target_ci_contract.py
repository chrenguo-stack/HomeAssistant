from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAME = "n3w-t1-core-updater-broker-target-ci.yml"
WORKFLOW = ROOT / ".github/workflows" / NAME
FAST = ROOT / ".github/workflows/n3w-ci-fast-source-exact-closure-contract-ci.yml"
POLICY = ROOT / "docs/development/N3W_CI_POLICY_MANIFEST_V1.json"


def test_broker_target_workflow_is_policy_registered_and_fast_triggered():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["workflows"][NAME] == {
        "class": "EXACT",
        "draft_policy": "run",
        "exceptions": {},
    }
    fast = FAST.read_text(encoding="utf-8")
    assert fast.count(f'      - ".github/workflows/{NAME}"') == 2
    assert fast.count(
        '      - "tests/tools/test_n3w_t1_core_updater_broker_target_ci_contract.py"'
    ) == 2


def test_broker_target_workflow_binds_exact_arm64_artifact_not_tag_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "docker.io/library/eclipse-mosquitto" in text
    assert 'UPSTREAM_TAG: "2.1.4-alpine"' in text
    assert "docker buildx imagetools inspect" in text
    assert "UPSTREAM_MANIFEST_DIGEST" in text
    assert 'docker pull --platform linux/arm64 "$UPSTREAM_REPOSITORY@$UPSTREAM_MANIFEST_DIGEST"' in text
    assert "local/n3w-mosquitto:2.1.4-" in text
    assert "broker-arm64.tar.gz" in text
    assert "portable-image-identity.json" in text
    assert "upstream-binding.json" in text
    assert "actions/upload-artifact@v4" in text
    assert "actions/download-artifact@v4" in text
    assert "Re-download and verify exact artifact" in text


def test_broker_target_workflow_runs_real_isolated_a_to_b_and_recovery_point():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "docker.io/library/eclipse-mosquitto:2.1.2-alpine" in text
    assert "docker.io/library/eclipse-mosquitto:2.1.4-alpine" in text
    assert "mosquitto_ctrl dynsec init" in text
    assert "LocalBrokerRecoveryPoint" in text
    assert "provider.create" in text
    assert "provider.restore" in text
    assert "n3w/b6/predecessor" in text
    assert "n3w/b6/target" in text
    assert "mosquitto version 2.1.2" in text
    assert "mosquitto version 2.1.4" in text
    assert "BROKER_B6_PREDECESSOR_RECOVERY=PASS" in text


def test_broker_target_fixture_keeps_dynsec_admin_out_of_application_topics():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'ADMIN="$(openssl rand -hex 24)"' in text
    assert 'APP_USER="b6-app-client"' in text
    assert 'APP_PASSWORD="$(openssl rand -hex 24)"' in text
    assert 'APP_ROLE="b6-app-role"' in text
    assert 'dynsec createRole "$APP_ROLE"' in text
    assert "dynsec addRoleACL" in text
    assert "publishClientSend 'n3w/b6/#' allow 100" in text
    assert "subscribePattern 'n3w/b6/#' allow 100" in text
    assert "publishClientReceive 'n3w/b6/#' allow 100" in text
    assert 'dynsec createClient "$APP_USER"' in text
    assert 'dynsec addClientRole "$APP_USER" "$APP_ROLE" 100' in text
    assert '-u "$APP_USER" -P "$APP_PASSWORD"' in text
    assert "CONTROL_PAYLOAD=" not in text
    assert '"password": password' not in text
    assert '-u admin -P "$ADMIN" \\\n            -r -t n3w/b6/' not in text


def test_broker_target_workflow_has_no_t1_or_production_execution_path():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "concurrency:" in text
    assert "cancel-in-progress:" in text
    assert "timeout-minutes:" in text
    assert "ssh " not in text
    assert "scp " not in text
    assert 'T1_ACCESS: "false"' in text
    assert 'T1_MUTATION: "false"' in text
    assert 'BOARD_ACCESS: "false"' in text
    assert 'PRODUCTION_SERVICE_START: "false"' in text
