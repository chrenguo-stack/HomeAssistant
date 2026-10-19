from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


load("n3w_t1_production_v2_contract", "n3w_t1_production_v2_contract.py")
forensics = load("n3w_t1_failure_forensics_test", "n3w_t1_failure_forensics.py")


def failure():
    return {
        "run_id": "1" * 64,
        "release_id": "2" * 64,
        "source_head": "3" * 40,
        "failed_stage": "F3_DEPLOY",
        "last_success_stage": "HOST_BASELINE",
        "error_code": "f3_apply_failed",
        "mutation_started": True,
    }


def test_failure_is_frozen_before_snapshot_and_never_overwritten(tmp_path):
    root = tmp_path / "evidence"
    first = forensics.freeze_failure(root, failure())
    assert first["failure_frozen"] is True
    before = (root / forensics.FAILURE_SUMMARY).read_bytes()
    with pytest.raises(forensics.FailureForensicsError, match="evidence_already_exists"):
        forensics.freeze_failure(root, {"error_code": "different"})
    assert (root / forensics.FAILURE_SUMMARY).read_bytes() == before


def test_snapshot_cannot_run_before_failure_freeze(tmp_path):
    root = tmp_path / "evidence"
    root.mkdir()
    with pytest.raises(forensics.FailureForensicsError, match="failure_must_be_frozen_first"):
        forensics.collect_snapshot(root, {"boot": lambda: {"boot_id": "x"}})


def test_unreachable_probe_is_explicit_unavailable_and_manifest_completes(tmp_path):
    root = tmp_path / "evidence"
    forensics.freeze_failure(root, failure())

    def unavailable():
        raise TimeoutError("target unreachable")

    snapshot = forensics.collect_snapshot(
        root,
        {
            "boot_identity": unavailable,
            "marker": lambda: {"state": "STARTED", "sha256": "4" * 64},
        },
    )
    assert snapshot["probes"]["boot_identity"] == {
        "status": "UNAVAILABLE",
        "reason": "TimeoutError",
    }
    assert snapshot["probes"]["marker"]["status"] == "OBSERVED"
    manifest = forensics.build_manifest(root)
    assert manifest["FORENSIC_SNAPSHOT_COMPLETE"] is True
    assert manifest["NO_TARGET_MUTATION"] is True
    assert manifest["UNAVAILABLE_IS_EXPLICIT"] is True
    assert manifest["unavailable_count"] == 1
    assert len(manifest["bundle_sha256"]) == 64
    assert forensics.verify_manifest(root) == manifest


def test_reflash_disposition_requires_manifest_and_session_close(tmp_path):
    root = tmp_path / "evidence"
    forensics.freeze_failure(root, failure())
    forensics.collect_snapshot(root, {"marker": lambda: {"state": "STARTED"}})
    manifest = forensics.build_manifest(root)
    with pytest.raises(forensics.FailureForensicsError, match="reflash_before_session_close_forbidden"):
        forensics.reflash_disposition(manifest, {"session_closed": False})
    disposition = forensics.reflash_disposition(manifest, {"session_closed": True})
    assert disposition["TARGET_DISPOSITION"] == "REFLASH_REQUIRED"
    assert disposition["REFLASH_ALLOWED"] is True


def test_manifest_detects_evidence_tamper(tmp_path):
    root = tmp_path / "evidence"
    forensics.freeze_failure(root, failure())
    forensics.collect_snapshot(root, {"marker": lambda: {"state": "STARTED"}})
    forensics.build_manifest(root)
    path = root / forensics.FORENSIC_SNAPSHOT
    document = json.loads(path.read_text(encoding="utf-8"))
    document["status"] = "ALTERED"
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)
    with pytest.raises(forensics.FailureForensicsError, match="manifest_file_binding_invalid"):
        forensics.verify_manifest(root)


def test_forensics_source_has_no_target_mutation_commands():
    source = (TOOLS / "n3w_t1_failure_forensics.py").read_text(encoding="utf-8").casefold()
    for forbidden in (
        "systemctl restart",
        "systemctl start",
        "systemctl stop",
        "docker rm",
        "docker rmi",
        "apt-get install",
        "ssh ",
        "scp ",
    ):
        assert forbidden not in source
