from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "n3w-u13b-p3-ha-2026-10-4-same-version-acceptance-artifact-ci.yml"
)
REVIEW = (
    ROOT
    / "infra"
    / "n3w-t1"
    / "upgrades"
    / "homeassistant-2026.10.4-u13b-same-version-acceptance-review.json"
)


def test_same_version_review_supersedes_downgrade_target():
    value = json.loads(REVIEW.read_text(encoding="utf-8"))
    assert value["application_version"] == "2026.10.4"
    assert value["predecessor"]["image_ref"] == (
        "local/n3w-homeassistant:2026.10.4-5881590f"
    )
    assert value["predecessor"]["runtime_image_id"] == (
        "sha256:31bc185bfa185ed3dddce2f5bab867eb"
        "7d4ae96302bfd8b7f839fb0a9d5b7365"
    )
    assert value["candidate"]["application_version"] == "2026.10.4"
    assert value["candidate"]["target_image_ref"] == (
        "local/n3w-homeassistant:2026.10.4-u13b-acceptance-v1"
    )
    assert value["candidate"]["derivation"] == (
        "LABEL_ONLY_FROM_FROZEN_PREDECESSOR_ARTIFACT"
    )
    assert value["supersedes"]["candidate_version"] == "2026.10.3"
    invariants = value["required_invariants"]
    assert invariants["rootfs_diff_ids_identical"] is True
    assert invariants["runtime_config_except_labels_identical"] is True
    assert invariants["target_runtime_image_id_distinct"] is True
    assert invariants["base_artifact_reused_without_registry_pull"] is True
    assert invariants["homeassistant_data_schema_change"] is False
    assert value["new_clean_ota_authorized"] is False
    assert value["u13b_live_rollback_authorized"] is False
    assert value["t1_access"] is False
    assert value["t1_mutation"] is False


def test_artifact_workflow_reuses_frozen_predecessor_without_registry_pull():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'BASE_RUN_ID: "41976542377"' in text
    assert 'BASE_ARTIFACT_ID: "13391983948"' in text
    assert (
        "df95749cec1e48796d2cf3241d197396"
        "01fe7be78c48638284d10eec786e4fd2"
    ) in text
    assert (
        "eba1da958fc9c759c30d1cb34445c364"
        "e895bcd8d5e6c0d8392ab6849ece9973"
    ) in text
    assert "actions/download-artifact@v4" in text
    assert "docker pull" not in text
    assert "ghcr.io/" not in text


def test_artifact_workflow_only_changes_labels_and_proves_distinct_identity():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert (
        "org.hahub.n3w.u13b.acceptance"
        in text
    )
    assert (
        "p3-same-version-distinct-image-v1"
        in text
    )
    assert 'base["RootFS"]["Layers"] == target["RootFS"]["Layers"]' in text
    assert 'base_config.pop("Labels", None)' in text
    assert 'target_config.pop("Labels", None)' in text
    assert "assert base_config == target_config" in text
    assert 'assert target["Id"] != base["Id"]' in text
    assert '"rootfs_diff_ids_identical": True' in text
    assert '"runtime_config_except_labels_identical": True' in text
    assert '"target_runtime_image_id_distinct": True' in text
    assert '"registry_pull_used": False' in text
    assert "U13B_P3_BASE_CI_RUNTIME_PORTABLE_IDENTITY=PASS" in text
    assert 'assert base["Id"] == os.environ["BASE_RUNTIME_IMAGE_ID"]' not in text
    assert '"cross_store_runtime_id_rebound_required": True' in text
    assert '"live_target_runtime_id_must_differ_from_predecessor": True' in text
    assert '"live_predecessor_runtime_image_id": os.environ["BASE_RUNTIME_IMAGE_ID"]' in text
    assert 'read_json_member("index.json")' in text
    assert 'oci_manifest["config"]["digest"]' in text
    assert 'descriptor["digest"]' in text
    assert 'assert updated == 1' in text
    assert 'add_bytes(target, "index.json", index_raw)' in text


def test_artifact_workflow_has_no_live_authority():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert '"t1_access": False' in text
    assert '"t1_mutation": False' in text
    assert '"new_clean_ota_authorized": False' in text
    assert '"u13b_live_rollback_authorized": False' in text
    assert "ssh " not in text
    assert "scp " not in text
