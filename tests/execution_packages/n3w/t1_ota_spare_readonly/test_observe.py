import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest


OBSERVER = (
    Path(__file__).resolve().parents[4]
    / "tools/execution_packages/n3w/t1_ota_spare_readonly/observe.py"
)
CODE = runpy.run_path(str(OBSERVER))


class BaselineError(RuntimeError):
    pass


@pytest.mark.parametrize(
    ("clean_reference", "reason", "may_collect"),
    [
        (True, "relevant_failed_units:n3wfc4-provision-resume.service", True),
        (True, "unit_health_invalid:n3wfc4-provision-resume.service", True),
        (False, "relevant_failed_units:n3wfc4-provision-resume.service", False),
        (True, "relevant_failed_units:broker.service,n3wfc4-provision-resume.service", False),
        (True, "runtime_service_set_invalid", False),
    ],
)
def test_runtime_collection_retains_original_baseline_failure(clean_reference, reason, may_collect):
    def strict_snapshot():
        raise BaselineError(reason)

    def read_services():
        assert may_collect
        return ["broker", "homeassistant", "manager"]

    host = SimpleNamespace(
        _observe_running_base_v2=strict_snapshot,
        _running_project_services_v2=read_services,
        render_compose=lambda: {},
        _runtime=lambda name: {"name": name},
        _listener_snapshot=lambda: {"tcp_8883": 1},
    )
    admission = {}
    obtain = CODE["observe_running_snapshot"]
    if may_collect:
        snapshot = obtain(host, clean_reference, admission, BaselineError)
        assert set(snapshot["runtime"]) == {"broker", "homeassistant", "manager"}
        assert snapshot["listeners"] == {"tcp_8883": 1}
    else:
        with pytest.raises(BaselineError):
            obtain(host, clean_reference, admission, BaselineError)
    assert admission == {"status": "BLOCKED", "reason": reason.split(":")[0]}


def test_reference_checks_identity_binding_and_absence_of_legacy_records(monkeypatch, tmp_path):
    source = CODE["CLEAN_REFERENCE_SOURCE"]
    marker = {"schema": "gh.h0h1.system-initialization/1"}
    marker["manifest_sha256"] = CODE["digest"](
        json.dumps(marker, sort_keys=True, separators=(",", ":")).encode()
    )
    documents = {
        "fresh-release.json": {
            "schema": "gh.n3w-t1-fresh-release/1",
            "release_id": source,
            "source_head": source,
            "explicit_provisioning_required": True,
        },
        "INITIALIZED.json": marker,
    }
    for phase, stage, control, flag in (
        ("r2a", "RUNTIME_STARTED", "abeb6c31147bcf249361dcec7e9536eaed6106a6", "runtime_started"),
        ("r2b", "REBOOT_ACCEPTED", "e15c64ac8f0f5f482a6c8538072031734002a559", "reboot_acceptance_passed"),
    ):
        documents[f"n3w-t1-clean-reference-{phase}"] = {
            "schema": f"gh.n3w-t1-clean-reference-{phase}-transaction/1",
            "stage": stage,
            "product_source_head": source,
            "control_plane_head": control,
            "authorization_claimed": True,
            "authorization_consumed": True,
            "authorization_replay_allowed": False,
            flag: True,
        }

    def record(path, _mode):
        return dict(documents[path.parent.name if path.name == "transaction.json" else path.name])

    check = CODE["has_clean_reference_records"]
    monkeypatch.setitem(check.__globals__, "read_reference_record", record)
    release = tmp_path / "fresh-release.json"
    assert check(tmp_path, release)

    reboot = documents["n3w-t1-clean-reference-r2b"]
    reboot["product_source_head"] = "drift"
    assert not check(tmp_path, release)
    reboot["product_source_head"] = source

    legacy = tmp_path / "n3w-t1-provisioning"
    legacy.mkdir()
    (legacy / "transaction.json").symlink_to(tmp_path / "missing")
    assert not check(tmp_path, release)
