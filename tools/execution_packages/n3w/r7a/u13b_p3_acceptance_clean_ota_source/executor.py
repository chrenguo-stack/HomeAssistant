from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[5]
MANIFEST_PATH = Path(__file__).with_name("manifest.json")
TARGET_PATH = (
    ROOT
    / "infra"
    / "n3w-t1"
    / "upgrades"
    / "homeassistant-2026.10.3-u13b-physical.json"
)

GATE_ID = "N3W_T1_U13B_P3_ACCEPTANCE_CLEAN_OTA_SOURCE_PACKAGE_20261117_01"
MANIFEST_SCHEMA = "gh.n3w-t1-u13b-p3-acceptance-clean-ota-source-manifest/1"
RESULT_SCHEMA = "gh.n3w-t1-u13b-p3-acceptance-clean-ota-source-result/1"


class Stop(RuntimeError):
    pass


def git_text(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise Stop("git_command_failed:" + args[0])
    return completed.stdout.strip()


def read_manifest(expected_commit: str) -> dict[str, Any]:
    if re.fullmatch(r"[0-9a-f]{40}", expected_commit or "") is None:
        raise Stop("expected_commit_invalid")
    if git_text("rev-parse", "HEAD") != expected_commit:
        raise Stop("local_head_mismatch")
    if git_text("status", "--porcelain", "--untracked-files=no"):
        raise Stop("tracked_worktree_dirty")
    document = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if (
        document.get("schema") != MANIFEST_SCHEMA
        or document.get("gate_id") != GATE_ID
        or document.get("real_t1_access_authorized") is not False
        or document.get("live_execution_authorized") is not False
        or document.get("new_clean_ota_mutation_authorized") is not False
        or document.get("controlled_rollback_mutation_authorized") is not False
    ):
        raise Stop("manifest_gate_invalid")
    for relative, blob in document["package_source_authority"].items():
        if git_text("rev-parse", "HEAD:" + relative) != blob:
            raise Stop("package_source_authority_drift:" + relative)
    return document


def _runtime_modules():
    import sys

    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from n3w_t1_core_updater_ha_ipc import HostOtaAdmission
    from n3w_t1_core_updater_v2_common import (
        ComponentTarget,
        canonical,
        sha256_bytes,
    )
    return HostOtaAdmission, ComponentTarget, canonical, sha256_bytes


def build_acceptance_admission(
    manifest: dict[str, Any],
    *,
    current_image_ref: str,
    current_runtime_image_id: str,
):
    HostOtaAdmission, ComponentTarget, canonical, sha256_bytes = _runtime_modules()
    expected = manifest["acceptance_target"]
    if current_image_ref != expected["expected_predecessor_image_ref"]:
        raise Stop("p3_current_image_ref_drift")
    if (
        not isinstance(current_runtime_image_id, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", current_runtime_image_id) is None
    ):
        raise Stop("p3_current_runtime_image_id_invalid")

    target = ComponentTarget.load(TARGET_PATH)
    if (
        target.target_image_ref != expected["target_image_ref"]
        or target.expected_predecessor_image_ref
        != expected["expected_predecessor_image_ref"]
        or target.target_archive_sha256 != expected["target_archive_sha256"]
        or target.artifact_identity != expected["artifact_identity"]
    ):
        raise Stop("p3_target_authority_drift")

    target_document = json.loads(TARGET_PATH.read_text(encoding="utf-8"))
    release_identity = manifest["acceptance_release_identity"]
    admission = HostOtaAdmission(
        release_identity=release_identity,
        current_image_ref=current_image_ref,
        current_image_identity={
            "runtime_image_id": current_runtime_image_id,
            "platform": "linux/arm64",
        },
        target_manifest_identity={
            "release_identity": release_identity,
            "target_manifest_sha256": sha256_bytes(canonical(target_document)),
            "target_image_ref": target.target_image_ref,
            "target_archive_sha256": target.target_archive_sha256,
        },
        target_image_ref=target.target_image_ref,
        target_archive_sha256=target.target_archive_sha256,
        target_archive_size=expected["target_archive_size_bytes"],
    )
    return admission.validate()


def source_check(manifest: dict[str, Any]) -> dict[str, Any]:
    expected = manifest["acceptance_target"]
    admission = build_acceptance_admission(
        manifest,
        current_image_ref=expected["expected_predecessor_image_ref"],
        current_runtime_image_id="sha256:" + "1" * 64,
    )
    return {
        "schema": RESULT_SCHEMA,
        "gate_id": GATE_ID,
        "status": "U13B_P3_ACCEPTANCE_CLEAN_OTA_SOURCE_READY",
        "acceptance_release_identity": admission.release_identity,
        "current_image_ref": admission.current_image_ref,
        "target_image_ref": admission.target_image_ref,
        "target_archive_sha256": admission.target_archive_sha256,
        "target_archive_size_bytes": admission.target_archive_size,
        "uses_product_host_ota_admission": True,
        "uses_product_prepare_new": True,
        "manager_version_rule_modified": False,
        "real_t1_access": False,
        "t1_mutation": False,
        "usb_mutation": False,
        "service_mutation": False,
        "image_mutation": False,
        "ha_data_mutation": False,
        "new_clean_ota_mutation_authorized": False,
        "u13b_live_execution_authorized": False,
        "controlled_rollback_mutation_authorized": False,
        "board_access": False,
        "merge": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-package-commit", required=True)
    parser.add_argument("--mode", choices=("source-check",), default="source-check")
    args = parser.parse_args()
    try:
        manifest = read_manifest(args.expected_package_commit)
        result = source_check(manifest)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        print(
            json.dumps(
                {
                    "schema": RESULT_SCHEMA,
                    "gate_id": GATE_ID,
                    "status": "STOP",
                    "reason": type(error).__name__ + ":" + str(error)[:300],
                    "real_t1_access": False,
                    "t1_mutation": False,
                    "new_clean_ota_mutation_authorized": False,
                    "u13b_live_execution_authorized": False,
                    "controlled_rollback_mutation_authorized": False,
                    "board_access": False,
                    "merge": False,
                },
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
