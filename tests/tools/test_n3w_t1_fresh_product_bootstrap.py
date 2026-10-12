from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/n3w_t1_fresh_product_bootstrap.py"


def load_tool():
    name = "n3w_t1_fresh_product_bootstrap"
    specification = importlib.util.spec_from_file_location(name, TOOL)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def test_deployable_workflow_prevents_post_manifest_bytecode_contamination() -> None:
    workflow = (
        ROOT
        / ".github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml"
    ).read_text(encoding="utf-8")

    assert "PYTHONDONTWRITEBYTECODE=1 sudo -E python - \"$PAYLOAD\"" in workflow
    assert workflow.count("--phase self-check") >= 2
    assert "find \"$PAYLOAD\" -type f -path '*/__pycache__/*'" in workflow
    assert "rootfs_layers_sha256" in workflow
    assert "FRESH_CROSS_STORE_IMAGE_BINDING=PASS" in workflow


def test_future_authorization_is_fresh_bootstrap_specific() -> None:
    tool = load_tool()
    assert tool.AUTHORIZATION_ID == (
        "N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_"
        "LIVE_APPLY_20261012_04"
    )
    assert "PRODUCTION_STACK_STAGING" not in tool.AUTHORIZATION_ID


def test_runtime_image_binding_accepts_containerd_runtime_id_when_rootfs_exact() -> None:
    tool = load_tool()
    layers = [
        "sha256:" + "1" * 64,
        "sha256:" + "2" * 64,
    ]
    runtime_id = "sha256:" + "c" * 64
    record = {
        "image": "local/test:exact",
        "rootfs_layers_sha256": tool._normalized_hash(layers),
    }

    class FakeRunner:
        def run(self, _argv):
            return json.dumps(
                [
                    {
                        "Id": runtime_id,
                        "Architecture": "arm64",
                        "Os": "linux",
                        "RootFS": {"Layers": layers},
                    }
                ]
            )

    binding = tool._verify_runtime_image(
        FakeRunner(),
        "homeassistant",
        record,
    )

    assert binding["runtime_id"] == runtime_id
    assert binding["rootfs_layers_sha256"] == record["rootfs_layers_sha256"]


def test_runtime_image_binding_rejects_rootfs_drift() -> None:
    tool = load_tool()
    expected_layers = ["sha256:" + "1" * 64]
    observed_layers = ["sha256:" + "2" * 64]
    record = {
        "image": "local/test:exact",
        "rootfs_layers_sha256": tool._normalized_hash(expected_layers),
    }

    class FakeRunner:
        def run(self, _argv):
            return json.dumps(
                [
                    {
                        "Id": "sha256:" + "c" * 64,
                        "Architecture": "arm64",
                        "Os": "linux",
                        "RootFS": {"Layers": observed_layers},
                    }
                ]
            )

    with pytest.raises(
        tool.BootstrapError,
        match="image_rootfs_binding_invalid:homeassistant",
    ):
        tool._verify_runtime_image(
            FakeRunner(),
            "homeassistant",
            record,
        )


def test_final_targets_do_not_include_host_baseline() -> None:
    tool = load_tool()
    targets = set(tool.FINAL_DIRS) | set(tool.FINAL_FILES)

    assert "/var/lib/docker" not in targets
    assert "/etc/NetworkManager" not in targets
    assert "/etc/ssh" not in targets
    assert "/" not in targets


def test_apply_rejects_wrong_authorization_before_root_check(
    tmp_path: Path,
) -> None:
    tool = load_tool()

    with pytest.raises(tool.BootstrapError, match="authorization_id_mismatch"):
        tool.execute_apply(tmp_path, "WRONG")


def test_source_forbids_broad_prune_and_activation() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert "docker system prune" not in source.split("def self_check", 1)[0]
    assert "docker volume prune" not in source.split("def self_check", 1)[0]
    assert "docker network prune" not in source.split("def self_check", 1)[0]
    assert "docker compose up" not in source.split("def self_check", 1)[0]


def test_source_contains_real_dynsec_candidate_and_stopped_postcheck() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert "mosquitto_rr" in source
    assert "$CONTROL/dynamic-security/v1" in source
    assert "audit_fresh_dynsec_document" in source
    assert '("docker", "network", "create", network)' not in source
    assert '"docker", "compose"' in source
    assert "postcheck_listener_present" in source
    assert "postcheck_guard_active" in source


def test_source_uses_no_trunc_image_postcheck() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert '("docker", "image", "ls", "--no-trunc", "-q")' in source


def test_claimed_failure_is_structured_no_replay() -> None:
    source = TOOL.read_text(encoding="utf-8")
    assert '"status": "STOP_PARTIAL"' in source
    assert '"replay_allowed": False' in source
    assert '"automatic_retry": False' in source


def test_staging_defers_product_network_creation_to_activation() -> None:
    source = TOOL.read_text(encoding="utf-8")

    assert 'if networks != DEFAULT_NETWORKS:' in source
    assert '("docker", "network", "create", network)' not in source
