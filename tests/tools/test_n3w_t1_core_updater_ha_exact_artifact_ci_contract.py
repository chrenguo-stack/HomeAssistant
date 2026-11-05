from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/n3w-t1-core-updater-homeassistant-exact-artifact-ci.yml"
FAST = ROOT / ".github/workflows/n3w-ci-fast-source-exact-closure-contract-ci.yml"
POLICY = ROOT / "docs/development/N3W_CI_POLICY_MANIFEST_V1.json"

NAME = "n3w-t1-core-updater-homeassistant-exact-artifact-ci.yml"


def test_exact_artifact_workflow_is_policy_registered_and_fast_source_triggered():
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    assert policy["workflows"][NAME] == {
        "class": "EXACT",
        "draft_policy": "run",
        "exceptions": {},
    }

    fast = FAST.read_text(encoding="utf-8")
    needle = f'      - ".github/workflows/{NAME}"'
    assert fast.count(needle) == 2


def test_exact_artifact_workflow_binds_platform_digest_not_tag_only():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "ghcr.io/home-assistant/home-assistant" in text
    assert 'UPSTREAM_TAG: "2026.10.4"' in text
    assert "docker buildx imagetools inspect" in text
    assert '"linux"' in text
    assert '"arm64"' in text
    assert 'docker pull --platform linux/arm64 "$UPSTREAM_REPOSITORY@$UPSTREAM_MANIFEST_DIGEST"' in text
    assert "UPSTREAM_INDEX_DIGEST" in text
    assert "UPSTREAM_MANIFEST_DIGEST" in text
    assert "local/n3w-homeassistant:2026.10.4-" in text


def test_exact_artifact_workflow_proves_portable_identity_and_reload():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "homeassistant-arm64.tar.gz" in text
    assert "parse_image_archive" in text
    assert "verify_runtime_document" in text
    assert 'docker load -i "$RUNNER_TEMP/package/homeassistant-arm64.tar.gz"' in text
    assert "portable-image-identity.json" in text
    assert "upstream-binding.json" in text
    assert "Upload exact HA 2026.10.4 ARM64 artifact" in text
    assert "Re-download and verify exact artifact" in text


def test_exact_artifact_workflow_has_no_t1_or_board_execution_path():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "ssh " not in text
    assert "scp " not in text
    assert "T1_ACCESS=false" in text
    assert "T1_MUTATION=false" in text
    assert "service_restart" in text
    assert "board_access" in text
    assert "timeout-minutes:" in text
    assert "concurrency:" in text
    assert "cancel-in-progress:" in text


def test_exact_artifact_stops_reproduction_after_target_freezes():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "target_present:" in text
    assert "P2B_TARGET_FROZEN" in text
    assert "P2A_BUILD_ALLOWED" in text
    assert "if: needs.source.outputs.target_present != 'true'" in text
    assert "infra/n3w-t1/upgrades/homeassistant-2026.10.4.json" in text
