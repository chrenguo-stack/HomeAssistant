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
    assert 'dynsec createClient "$APP_USER" -p "$APP_PASSWORD"' in text
    assert 'dynsec addClientRole "$APP_USER" "$APP_ROLE" 100' in text
    assert 'dynsec getRole "$APP_ROLE"' in text
    assert 'dynsec getClient "$APP_USER"' in text
    assert 'BROKER_B6_DYNSEC_APPLICATION_FIXTURE=PASS' in text
    for marker in (
        "BROKER_B6_APP_PROBE_PUBLISH=PASS",
        "BROKER_B6_PREDECESSOR_RETAINED_PUBLISH=PASS",
        "BROKER_B6_PREDECESSOR_STOP=PASS",
        "BROKER_B6_DYNSEC_FILE_PRESENT=PASS",
        "BROKER_B6_PERSISTENCE_DB_PRESENT=PASS",
        "BROKER_B6_PRE_TARGET_HASH_CAPTURE=PASS",
        "BROKER_B6_TARGET_START=PASS",
        "BROKER_B6_TARGET_VERSION=PASS",
        "BROKER_B6_TARGET_READS_PREDECESSOR=PASS",
        "BROKER_B6_TARGET_RETAINED_PUBLISH=PASS",
        "BROKER_B6_TARGET_STOP=PASS",
        "BROKER_B6_TARGET_STATE_CHANGED=PASS",
        "BROKER_B6_RESTORED_HASH_MATCH=PASS",
        "BROKER_B6_ROLLBACK_PREDECESSOR_START=PASS",
        "BROKER_B6_ROLLBACK_PREDECESSOR_READ=PASS",
    ):
        assert marker in text
    assert "docker exec -i n3w-b6-broker mosquitto_ctrl" not in text
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


def test_broker_target_phase2_freezes_successful_exact_artifact():
    target = json.loads(
        (ROOT / "infra/n3w-t1/upgrades/broker-2.1.4.json").read_text(
            encoding="utf-8"
        )
    )
    assert target["schema"] == "gh.n3w-t1-core-updater-target/2"
    assert target["component"] == "broker"
    assert target["mutation_profile"] == "IMAGE_ONLY_V1"
    assert target["target_image_ref"] == "local/n3w-mosquitto:2.1.4-5d96ab48"
    assert target["target_platform"] == "linux/arm64"
    assert target["target_archive_sha256"] == "35630ff4b3ba710d26f1b44ac022b806c3ad53c2f1a015195e48c79690d26f3e"
    assert target["artifact_identity"]["artifact_id"] == 14713718457
    assert target["artifact_identity"]["artifact_digest_sha256"] == "36d2d820b1d793f64014d910d08eace4d7ef90375adb2e43b1ba8e46a5195cf3"
    assert target["expected_predecessor_image_ref"] == "local/n3w-mosquitto:2.1.2-3184566d"
    assert target["rollback_compatible"] is True
    assert target["compatibility_evidence"]["review_evidence_sha256"] == "aeb8c37ad4fa0193944f0dcd8a91bc7e66a67218e66ddc1d49325f5ce9948941"


def test_broker_frozen_exact_binding_never_rebuilds_or_repulls_target():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "if: needs.source.outputs.target_present != 'true'" in text
    assert "if: needs.source.outputs.target_present == 'true'" in text
    frozen = text.split("  exact-binding:\n", 1)[1].split("  isolated-a-to-b:\n", 1)[0]
    assert 'UPSTREAM_RUN_ID: "44921739065"' in frozen
    assert 'UPSTREAM_ARTIFACT_ID: "14713718457"' in frozen
    assert "n3w-t1-core-updater-broker-2.1.4-arm64-46d14f7187de68c1500d3051e957109b97a21774" in frozen
    assert "actions/download-artifact@v4" in frozen
    assert "run-id: ${{ env.UPSTREAM_RUN_ID }}" in frozen
    assert "BROKER_2_1_4_FROZEN_TARGET_METADATA=PASS" in frozen
    assert "BROKER_2_1_4_FROZEN_EXACT_BINDING=PASS" in frozen
    assert "docker pull" not in frozen
    assert "docker save" not in frozen
    assert "imagetools inspect" not in frozen
