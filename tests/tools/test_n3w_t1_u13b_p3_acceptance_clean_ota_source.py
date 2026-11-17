from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
EXECUTOR = (
    ROOT
    / "tools"
    / "execution_packages"
    / "n3w"
    / "r7a"
    / "u13b_p3_acceptance_clean_ota_source"
    / "executor.py"
)
MANIFEST = EXECUTOR.with_name("manifest.json")


def load_executor():
    spec = importlib.util.spec_from_file_location("u13b_p3_source", EXECUTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_is_acceptance_only_and_non_live():
    value = manifest()
    assert value["real_t1_access_authorized"] is False
    assert value["live_execution_authorized"] is False
    assert value["new_clean_ota_mutation_authorized"] is False
    assert value["controlled_rollback_mutation_authorized"] is False
    assert value["execution_contract"]["manager_version_discovery_bypass_only"] is True
    assert value["execution_contract"]["manager_version_rule_modified"] is False
    assert value["execution_contract"]["product_prepare_new_required"] is True
    assert value["execution_contract"]["stop_before_u12"] is True
    assert value["stop_boundary"] == "STOP_BEFORE_P3_REAL_T1_NEW_CLEAN_OTA_MUTATION"


def test_acceptance_admission_binds_distinct_exact_target():
    module = load_executor()
    value = manifest()
    admission = module.build_acceptance_admission(
        value,
        current_image_ref="local/n3w-homeassistant:2026.10.4-5881590f",
        current_runtime_image_id="sha256:" + "2" * 64,
    )
    assert admission.release_identity == "homeassistant-2026.10.4-u13b-p3-same-version-acceptance-v1"
    assert admission.current_image_ref == "local/n3w-homeassistant:2026.10.4-5881590f"
    assert admission.target_image_ref == "local/n3w-homeassistant:2026.10.4-u13b-acceptance-v1"
    assert admission.current_image_ref != admission.target_image_ref
    assert admission.target_archive_sha256 == (
        "be30c4778bf537258d9e3825524c79532f20e8eb7a82136f560110d8f44b418d"
    )
    assert admission.target_archive_size == 835299595


def test_acceptance_admission_fails_closed_on_predecessor_or_runtime_drift():
    module = load_executor()
    value = manifest()
    with pytest.raises(module.Stop, match="p3_current_image_ref_drift"):
        module.build_acceptance_admission(
            value,
            current_image_ref="local/n3w-homeassistant:2026.10.0-deadbeef",
            current_runtime_image_id="sha256:" + "2" * 64,
        )
    with pytest.raises(module.Stop, match="p3_current_runtime_image_id_invalid"):
        module.build_acceptance_admission(
            value,
            current_image_ref="local/n3w-homeassistant:2026.10.4-5881590f",
            current_runtime_image_id="not-a-runtime-id",
        )


def test_product_prepare_path_archives_then_creates_fresh_transaction():
    import sys

    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from n3w_t1_core_updater_ha_ipc import HaUsbIpcExecutor

    source = inspect.getsource(HaUsbIpcExecutor.submit)
    archive = source.index("self.store.prepare_new()")
    fresh = source.index("document = new_transaction(")
    requested = source.index("prepared = request_prepare(document)")
    persist = source.index("self.store.write(prepared)")
    assert archive < fresh < requested < persist
    assert "compare_versions" not in source


def test_source_package_has_no_live_transport_or_host_mutation_surface():
    source = EXECUTOR.read_text(encoding="utf-8")
    forbidden = (
        "load_transport(",
        "t1_ssh_target",
        "known_hosts",
        "systemctl",
        "docker load",
        "docker image rm",
        "mkfs",
        "parted",
        "sgdisk",
        "record_target_started(",
        "claim_live_authorization(",
    )
    for token in forbidden:
        assert token not in source
