from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
PREFLIGHT_EXECUTOR = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "u13b_p3_fresh_readonly_preflight" / "executor.py"
)
PREFLIGHT_MANIFEST = PREFLIGHT_EXECUTOR.with_name("manifest.json")
LIVE_EXECUTOR = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "u13b_p3_live_to_u11" / "executor.py"
)
LIVE_MANIFEST = LIVE_EXECUTOR.with_name("manifest.json")
RESET_EXECUTOR = (
    ROOT / "tools" / "execution_packages" / "n3w" / "r7a"
    / "u13b_p3_single_usb_reuse_reset" / "executor.py"
)
RESET_MANIFEST = RESET_EXECUTOR.with_name("manifest.json")
RECOVERY_EXECUTOR = LIVE_EXECUTOR.parent.parent / "u13b_p3_u1_u4_recovery" / "executor.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_u1_recovery_stops_before_writing_existing_signature(monkeypatch):
    module = load(RECOVERY_EXECUTOR, "p3_recovery_blank_guard")
    calls = []
    monkeypatch.setattr(module, "select_usb", lambda *args: SimpleNamespace(locator="/dev/test"))
    monkeypatch.setattr(module, "device_unused", lambda path: calls.append(("unused", path)))
    monkeypatch.setattr(module, "disk_signatures", lambda _: [{"type": "gpt"}])
    monkeypatch.setattr(module, "run", lambda *args, **kwargs: pytest.fail("unexpected command"))
    with pytest.raises(module.Stop, match="on_disk_partition_table_or_signature_present"):
        module.verify_blank_media(None, {})
    assert calls == [("unused", "/dev/test")]


def test_u1_recovery_creates_gpt_without_force_or_signature_erase(monkeypatch):
    module = load(RECOVERY_EXECUTOR, "p3_recovery_partition")
    calls = []
    monkeypatch.setattr(module, "run", lambda stage, args, **kw: calls.append((stage, args, kw)))
    monkeypatch.setattr(module, "select_usb", lambda *_: SimpleNamespace(locator="/dev/test"))
    monkeypatch.setattr(module, "verify_partition_layout", lambda *args: calls.append(("layout", args)))
    monkeypatch.setattr(module, "device_unused", lambda _: None)
    monkeypatch.setattr(module, "disk_signatures", lambda _: [])
    assert module.create_gpt(SimpleNamespace(_partition=lambda _: "/dev/test1"), {}, "/dev/test") == "/dev/test1"
    assert calls[0][1] == [
        "sfdisk", "--lock=yes", "--wipe", "never", "--wipe-partitions", "never", "/dev/test",
    ]
    assert calls[0][2]["input_bytes"] == b"label: gpt\n,;\n"
    assert [entry[0] for entry in calls] == ["create_gpt", "settle_partition_events", "layout"]


def test_u1_recovery_refuses_existing_recovery_ledger(tmp_path, monkeypatch):
    module = load(RECOVERY_EXECUTOR, "p3_recovery_one_shot")
    original = tmp_path / "original"
    original.mkdir()
    recovery = tmp_path / "recovery"
    recovery.mkdir()
    monkeypatch.setattr(module, "STATE", tmp_path)
    monkeypatch.setattr(module, "RECOVERY_ROOT", recovery)
    monkeypatch.setattr(module, "private_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "read_record", lambda _: pytest.fail("replay read past guard"))
    with pytest.raises(module.Stop, match="recovery_attempt_already_started"):
        module.recover({"original_root": original.name}, {})


def test_u1_recovery_requires_prior_confirmation_and_u1_digest(tmp_path, monkeypatch):
    module = load(RECOVERY_EXECUTOR, "p3_recovery_bind")
    transaction = {"transaction_id_sha256": "tx", "phase": "U1_PREPARE_REQUESTED", "status": "ACTIVE"}
    state = {
        "transaction_id_sha256": "tx", "confirmation_consumed": True,
        "confirmation_required": False, "candidate": {"model": "test"},
    }
    store = SimpleNamespace(read=lambda: transaction, path=tmp_path / "tx")
    prepare = SimpleNamespace(read=lambda: state)
    monkeypatch.setattr(module, "digest", lambda _: module.U1_SHA256)
    assert module.require_u1(store, prepare, {"usb": state["candidate"]}) == transaction
    state["confirmation_consumed"] = False
    with pytest.raises(module.Stop, match="u1_prepare_confirmation_drift"):
        module.require_u1(store, prepare, {"usb": state["candidate"]})
    monkeypatch.setattr(module, "digest", lambda _: "other")
    with pytest.raises(module.Stop, match="active_u1_transaction_drift"):
        module.require_u1(store, prepare, {"usb": state["candidate"]})


def test_u1_recovery_reports_failed_tool_and_refuses_duplicate_record(tmp_path, monkeypatch):
    module = load(RECOVERY_EXECUTOR, "p3_recovery_failure")
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=11))
    with pytest.raises(module.Stop, match="create_gpt:exit_11"):
        module.run("create_gpt", ["sfdisk"])
    ledger = tmp_path / "claim.json"
    module.write_once(ledger, {"claimed": True})
    with pytest.raises(FileExistsError):
        module.write_once(ledger, {"claimed": False})
    assert json.loads(ledger.read_text()) == {"claimed": True}


def test_p3_recovery_keeps_original_grants_and_ends_at_u4(tmp_path, monkeypatch):
    import base64

    from n3w_t1_core_updater_ha_capacity import compute_capacity
    from n3w_t1_core_updater_ha_prepare import (
        PREPARE_STATE_SCHEMA, HostUsbCandidate, PrepareStateStore,
    )
    from n3w_t1_core_updater_ha_recovery import ImageRecoveryRecord
    from n3w_t1_core_updater_ha_usb import request_prepare
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore, new_transaction
    import n3w_t1_portable_image_identity as portable

    module = load(RECOVERY_EXECUTOR, "p3_recovery_integrated")
    original = tmp_path / "original"
    original.mkdir(mode=0o700)
    (original / "staging").mkdir(mode=0o700)
    (original / "staging" / "homeassistant-arm64.tar.gz").touch()
    monkeypatch.setattr(module, "STATE", tmp_path)
    recovery = tmp_path / "recovery"
    monkeypatch.setattr(module, "RECOVERY_ROOT", recovery)
    monkeypatch.setattr(module, "private_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "load_frozen_tools", lambda *args: None)
    monkeypatch.setattr(module, "check_peers", lambda _: None)
    monkeypatch.setattr(module, "os", SimpleNamespace(
        **(vars(module.os) | {"geteuid": lambda: 0, "umask": lambda _: None})
    ))
    monkeypatch.setattr(module, "ota_daemon", lambda: ({"InvocationID": "unchanged"}, 1))

    sha = "1" * 64
    uuid = "12345678-1234-5678-1234-567812345678"
    image = "local/n3w-homeassistant:2026.10.4-bbbbbbbb"
    transaction = request_prepare(new_transaction(
        current_image_ref="local/n3w-homeassistant:2026.10.0-aaaaaaaa",
        current_image_identity={"portable_identity_sha256": "2" * 64, "platform": "linux/arm64"},
        target_manifest_identity={"release_identity": "ha-2026.10.4", "manifest_sha256": "3" * 64},
        target_image_ref=image, target_archive_sha256=sha, target_archive_size=835_299_595,
    ))
    tx_id = transaction["transaction_id_sha256"]
    store = HaUsbStateStore(tmp_path)
    store.write(transaction)
    monkeypatch.setattr(module, "U1_SHA256", module.digest(store.path))
    candidate = HostUsbCandidate("/dev/test", "a" * 64, "test", 32_017_047_552)
    capacity = compute_capacity(
        target_artifact_bytes=835_299_595, predecessor_recovery_budget_bytes=1_342_177_280,
        ha_data_measured_bytes=134_217_728,
    ).snapshot(calculated_at_unix=2)
    prepare_store = PrepareStateStore(tmp_path)
    prepare_store.write({
        "schema": PREPARE_STATE_SCHEMA, "transaction_id_sha256": tx_id,
        "release_identity": "ha-2026.10.4", "baseline_public_fingerprints": [],
        "candidate": candidate.public(), "confirmation_consumed": True,
        "confirmation_required": False, "error_code": None,
        "updated_at_unix": 2, "capacity_snapshot": capacity,
    })
    initial_prepare = prepare_store.path.read_bytes()
    initial_claim = {
        "execution_id": "previous-run", "authorization_id": "previous-grant",
        "consumed": True, "claimed": True, "replay_permitted": False,
    }
    original_claim = original / "authorization_claim.json"
    module.write_once(original_claim, initial_claim)
    module.write_once(original / "failure.json", {
        "status": "STOP_POSTCLAIM", "transaction_phase": transaction["phase"],
        "transaction_id_sha256": tx_id, "authorization_consumed": True,
    })
    module.write_once(original / "progress.json", {
        "phase": "fresh_usb_format_and_target_prepare", "updated_at_unix": 2,
    })

    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    commands, phases = [], []
    verified_target = ImageRecoveryRecord(
        kind="target", image_ref=image, archive_sha256=sha, archive_size_bytes=835_299_595,
        portable_identity_sha256="4" * 64, platform="linux/arm64", verified=True, fsynced=True,
    )
    backend = SimpleNamespace(
        runtime_root=runtime,
        policy_provider=SimpleNamespace(load=lambda _: SimpleNamespace(target_archive_sha256=sha)),
        capacity_snapshot=lambda *a, **kw: capacity,
        _self_test=lambda _: None,
        _filesystem_space=lambda _: (30_000_000_000, 29_000_000_000),
        _require_bound_media=lambda _: None,
        sync_transaction_metadata=lambda document, media: phases.append((document["phase"], media)),
        resolve_transaction_media=lambda *a, **kw: phases[-1][1],
        prepare_target=lambda **kw: verified_target,
    )

    def run(stage, argv, **kwargs):
        commands.append(stage)
        return f"UUID={uuid}\nTYPE=ext4\nLABEL=N3W-UPDATE\n".encode() if stage == "verify_ext4" else b""

    monkeypatch.setattr(module, "run", run)
    monkeypatch.setattr(module, "recovery_backend", lambda *a: backend)
    monkeypatch.setattr(module, "verify_blank_media", lambda *a: candidate)
    monkeypatch.setattr(module, "create_gpt", lambda *a: "/dev/test1")
    monkeypatch.setattr(portable, "parse_image_archive", lambda *a, **kw: SimpleNamespace(
        config_semantics_sha256="5" * 64, rootfs_diff_ids_sha256="6" * 64,
    ))

    plan = {
        "original_root": original.name, "original_execution_id": "previous-run",
        "original_authorization_id": "previous-grant", "tools_sha256": {},
        "usb": candidate.public(), "historical_uuid": "other",
        "target": {
            "target_archive_sha256": sha, "target_archive_size_bytes": 835_299_595,
            "target_image_ref": image, "target_config_semantics_sha256": "5" * 64,
            "target_rootfs_diff_ids_sha256": "6" * 64,
        },
    }
    encoded = base64.b64encode(json.dumps(plan).encode()).decode()
    assert module.remote_main("execute", encoded) == 0
    assert module.status_result()["stop_before_u5"] is True
    assert store.read()["phase"] == "U4_READY_TO_INSTALL"
    assert store.read()["transaction_id_sha256"] == tx_id
    assert store.read()["target_artifact_verified"] is True
    assert [phase for phase, _ in phases] == [
        "U2_USB_QUALIFIED_FORMATTED_BOUND", "U2_USB_QUALIFIED_FORMATTED_BOUND",
        "U3_TARGET_DOWNLOADING_VERIFYING", "U4_READY_TO_INSTALL",
    ]
    assert commands == ["create_ext4", "settle_filesystem_events", "verify_ext4", "mount_ext4"]
    assert prepare_store.path.read_bytes() == initial_prepare
    assert json.loads(original_claim.read_text()) == initial_claim
    assert module.remote_main("execute", encoded) == 2
    assert module.status_result()["status"] == "U4_RECOVERY_PASS"


def test_fresh_readonly_manifest_is_non_live_and_preserves_old_usb():
    value = manifest(PREFLIGHT_MANIFEST)
    assert value["read_only_preflight"] is True
    assert value["real_t1_readonly_execution_authorized"] is True
    assert value["new_clean_ota_mutation_authorized"] is False
    assert value["u13b_live_execution_authorized"] is False
    assert value["controlled_rollback_mutation_authorized"] is False
    contract = value["execution_contract"]
    assert contract["exactly_one_fresh_usb_candidate_required"] is True
    assert contract["historical_usb_reuse_forbidden"] is False
    assert contract["historical_usb_reuse_without_destructive_reset_forbidden"] is True
    assert contract["single_usb_reuse_after_destructive_reset_authorized"] is True
    assert contract["current_terminal_transaction_write"] is False
    assert contract["usb_format"] is False
    assert value["execution_contract"]["execute_mode_forbidden_until_separate_authorization"] is False
    assert value["stop_boundary"] == (
        "STOP_AFTER_POST_RESET_READONLY_PREFLIGHT_BEFORE_P3_LIVE_AUTHORIZATION"
    )


def test_fresh_readonly_remote_compiles_and_has_no_mutation_calls():
    module = load(PREFLIGHT_EXECUTOR, "p3_fresh_readonly")
    compile(module.REMOTE_SCRIPT, "<p3-fresh-readonly>", "exec")
    remote = module.REMOTE_SCRIPT
    forbidden = (
        ".prepare_new(",
        ".write(",
        "format_and_mount(",
        "sync_transaction_metadata(",
        "systemctl",
        '"docker", "rm"',
        '"docker", "image", "rm"',
        "record_recovery_admission(",
        "claim_live_authorization(",
        "record_predecessor_capacity_released(",
        "record_target_started(",
        "record_target_accepted(",
        "record_commit(",
    )
    for token in forbidden:
        assert token not in remote
    assert "backend.inventory()" in remote
    assert "candidate.public_fingerprint != old_fingerprint" in remote
    assert "filesystem_uuids_for_candidate" in remote
    assert 'old_filesystem_uuid = expected["filesystem_uuid"].lower()' in remote
    assert "old_filesystem_uuid not in observed_filesystem_uuids" in remote
    assert "expected_reuse_fingerprint" in remote
    assert "single_usb_reuse_after_reset" in remote


def test_fresh_readonly_execute_mode_requires_true_manifest_authority():
    source = PREFLIGHT_EXECUTOR.read_text(encoding="utf-8")
    assert 'choices=("source-check", "execute-readonly")' in source
    assert "require_authorized=True if execute else None" in source
    assert "require_authorized is not None" in source
    assert (
        'document.get("real_t1_readonly_execution_authorized")'
        in source
    )
    source_check = source.index("if not execute:")
    evidence = source.index("evidence = prepare_evidence_root", source_check)
    assert source_check < evidence


@pytest.mark.parametrize(
    "drift",
    [
        {},
        {"historical_transaction_phase": "U11_TARGET_INSTALLED_STARTED"},
        {"historical_transaction_status": "ACTIVE"},
        {"historical_transaction_sha256": "0" * 64},
        {"historical_transaction_id_sha256": "0" * 64},
        {"single_usb_reuse_after_reset": False},
    ],
)
def test_post_reset_readonly_binds_current_host_terminal(
    drift, monkeypatch, tmp_path
):
    module = load(PREFLIGHT_EXECUTOR, "p3_post_reset_readonly")
    value = manifest(PREFLIGHT_MANIFEST)
    terminal = value["expected_terminal_u13a"]
    probe = {
        "prepare_new_admissible": True,
        "fresh_usb_candidate_count": 1,
        "fresh_usb_candidate": {"display_model": "test-usb"},
        "single_usb_reuse_after_reset": True,
        "historical_transaction_phase": terminal["transaction_phase"],
        "historical_transaction_status": terminal["transaction_status"],
        "historical_transaction_sha256": terminal["transaction_sha256"],
        "historical_transaction_id_sha256": terminal["transaction_id_sha256"],
        "historical_usb_filesystem_uuid": terminal["filesystem_uuid"],
        "historical_usb_public_fingerprint": "1" * 64,
        "current_homeassistant_image": terminal["target_image"],
        "current_homeassistant_runtime_image_id": terminal["target_runtime_image_id"],
    }
    probe.update(drift)

    def reject_historical_usb_read(*args):
        pytest.fail("post-reset preflight must not read the old USB mirror")

    monkeypatch.setattr(module, "load_module", reject_historical_usb_read)
    monkeypatch.setattr(module, "remote_probe", lambda **kwargs: probe)
    arguments = {
        "manifest": value,
        "execution_id": "test-post-reset-readonly",
        "evidence_root": tmp_path,
        "t1_ssh_target": "test",
        "known_hosts": tmp_path / "known_hosts",
        "expected_host_key_sha256": "2" * 64,
        "access_state": {},
    }
    evidence = tmp_path / "p3_fresh_readonly_result.json"
    if drift:
        with pytest.raises(module.Stop, match="p3_fresh_readonly_composite_drift"):
            module.run_readonly(**arguments)
        assert not evidence.exists()
        return

    result = module.run_readonly(**arguments)
    assert result["status"] == "P3_FRESH_REAL_T1_READONLY_PREFLIGHT_PASS"
    assert result["fresh_terminal_binding"] is True
    assert result["single_usb_reuse_after_reset"] is True
    assert result["historical_transaction_sha256"] == terminal["transaction_sha256"]
    assert manifest(evidence) == result


def test_live_manifest_authorization_is_narrow_and_consistent():
    value = manifest(LIVE_MANIFEST)
    granted = value["live_execution_authorized"]
    assert type(granted) is bool
    assert value["new_clean_ota_mutation_authorized"] is granted
    assert value["authorization_state"] == {
        "granted": granted,
        "claimed": False,
        "consumed": False,
        "replay_permitted": False,
    }
    assert value["u13b_live_execution_authorized"] is False
    assert value["controlled_rollback_mutation_authorized"] is False
    if granted:
        assert value["authorized_execution_id"] == "u13b-p3-live-to-u11-20261118-01"
    contract = value["execution_contract"]
    assert contract["fresh_real_t1_readonly_preflight_required"] is True
    assert contract["historical_usb_reuse_forbidden"] is False
    assert contract["historical_usb_reuse_without_destructive_reset_forbidden"] is True
    assert contract["single_usb_reuse_after_destructive_reset_required"] is True
    assert contract["exactly_one_fresh_usb_candidate_required"] is True
    assert contract["acceptance_staged_artifact_adapter_only"] is True
    assert contract["manager_version_rule_modified"] is False
    assert contract["stop_at_u11_before_u12"] is True
    assert contract["record_target_accepted_forbidden"] is True
    assert contract["record_commit_forbidden"] is True
    target = value["acceptance_target"]
    assert target["target_image_ref"] == "local/n3w-homeassistant:2026.10.4-u13b-acceptance-v1"
    assert target["target_ci_runtime_image_id"] == "sha256:59b51fc720f83eac91881937337e439e2a2a1a8bb58c9e760cbdf95ce8653fbc"
    assert target["cross_store_runtime_id_rebound_required"] is True
    assert target["live_target_runtime_id_must_differ_from_predecessor"] is True


def test_live_remote_compiles_and_stops_at_u11():
    module = load(LIVE_EXECUTOR, "p3_live")
    compile(module.REMOTE_SCRIPT, "<p3-live>", "exec")
    remote = module.REMOTE_SCRIPT
    order = [
        'ipc.submit("PREPARE"',
        "prepare.confirm_and_prepare()",
        "u6.prepare_or_resume()",
        "u7.prepare_or_resume()",
        "admitted = record_recovery_admission(",
        "claimed = claim_live_authorization(",
        "u10 = record_predecessor_capacity_released(",
        "installed = u11.install()",
    ]
    positions = [remote.index(token) for token in order]
    assert positions == sorted(positions)
    assert "record_target_accepted(" not in remote
    assert "record_commit(" not in remote
    assert "U12_TARGET_ACCEPTANCE" not in remote
    assert '"u12_plus": False' in remote
    assert '"U11_TARGET_INSTALLED_STARTED"' in remote
    assert "u11_target_runtime_id_not_distinct_from_predecessor" in remote
    assert "target_runtime_image_id_rebound=True" in remote


def test_live_revalidates_same_fresh_usb_before_outer_claim():
    module = load(LIVE_EXECUTOR, "p3_live_usb_recheck")
    remote = module.REMOTE_SCRIPT
    fresh_check = remote.index("revalidate_reset_usb(plan, SubprocessPrepareBackend(), classify_candidate)", remote.index("def init_claim("))
    state_root = remote.index("root.mkdir(mode=0o700)", fresh_check)
    claim_write = remote.index('durable_json_once(root / "authorization_claim.json", claim)')
    assert fresh_check < state_root < claim_write
    assert 'candidate.public_fingerprint == expected_fingerprint' in remote
    assert 'candidate.get("public_fingerprint") != expected_fingerprint' in remote


@pytest.mark.parametrize(
    ("observed", "uuids", "reason"),
    [
        (("same-usb",), "", None),
        (("other-usb",), "", "preclaim_fresh_usb_candidate_drift"),
        (("same-usb", "other-usb"), "", "preclaim_fresh_usb_candidate_drift"),
        (("same-usb",), "old-uuid", "historical_usb_filesystem_uuid_present"),
    ],
)
def test_live_usb_revalidation_after_reset(observed, uuids, reason):
    module = load(LIVE_EXECUTOR, "p3_live_usb_revalidation")
    namespace = {}
    exec(module.REMOTE_SCRIPT.rsplit("\nmain()", 1)[0], namespace)
    namespace["run"] = lambda argv, timeout: SimpleNamespace(stdout=uuids)
    backend = SimpleNamespace(
        inventory=lambda: [
            SimpleNamespace(
                public_fingerprint=fingerprint,
                locator="/dev/test",
                as_media_candidate=lambda: None,
            )
            for fingerprint in observed
        ]
    )
    plan = {
        "preflight": {
            "single_usb_reuse_after_reset": True,
            "fresh_usb_public_fingerprint": "same-usb",
        },
        "expected_terminal_u13a": {"filesystem_uuid": "old-uuid"},
    }
    revalidate = namespace["revalidate_reset_usb"]
    if reason:
        with pytest.raises(namespace["Stop"], match=reason):
            revalidate(plan, backend, lambda candidate: ())
    else:
        revalidate(plan, backend, lambda candidate: ())


def test_live_rejects_a_different_execution_id_before_artifact_or_ssh():
    module = load(LIVE_EXECUTOR, "p3_live_fixed_execution_id")
    args = SimpleNamespace(
        authorization_id=module.AUTHORIZATION_ID,
        confirm=module.CONFIRMATION,
        execution_id="different-id",
    )
    with pytest.raises(module.Stop, match="authorized_execution_id_mismatch"):
        module.execute_live(args, {"authorized_execution_id": "bound-id"}, {})


@pytest.mark.parametrize("init_acknowledged", [True, False])
def test_live_preserves_claim_truth_when_transport_fails(
    init_acknowledged, monkeypatch, tmp_path
):
    module = load(LIVE_EXECUTOR, "p3_live_claim_transport")
    args = SimpleNamespace(
        authorization_id=module.AUTHORIZATION_ID,
        confirm=module.CONFIRMATION,
        execution_id="bound-id",
        target_archive=tmp_path / "target",
        evidence_root=tmp_path,
        known_hosts=tmp_path / "known_hosts",
        t1_ssh_target="test",
        expected_host_key_sha256="0" * 64,
    )
    preflight = {
        "status": "P3_FRESH_REAL_T1_READONLY_PREFLIGHT_PASS",
        "prepare_new_admissible": True,
        "fresh_usb_candidate_count": 1,
        "single_usb_reuse_after_reset": True,
    }

    def disconnected(*args, **kwargs):
        raise RuntimeError("connection_lost")

    transport = SimpleNamespace(
        start_epoch=lambda: None, scp_to=disconnected, close_epoch=lambda: None
    )
    preflight_module = SimpleNamespace(
        prepare_evidence_root=lambda path: path, run_readonly=lambda **kwargs: preflight
    )

    def load_dependency(path, name):
        if path == module.PREFLIGHT_EXECUTOR:
            return preflight_module
        return SimpleNamespace(SSHTransport=lambda **kwargs: transport)

    calls = []

    def remote_mode(transport, mode, *args, **kwargs):
        calls.append(mode)
        if mode == "init" and init_acknowledged:
            return SimpleNamespace(returncode=0), {
                "status": "P3_LIVE_AUTHORIZATION_CLAIMED",
                "authorization_claimed": True,
                "authorization_consumed": True,
            }
        disconnected()

    monkeypatch.setattr(module, "load_module", load_dependency)
    monkeypatch.setattr(module, "verify_local_target_archive", lambda *args: None)
    monkeypatch.setattr(module, "build_source_bundle", lambda *args: (tmp_path, {}))
    monkeypatch.setattr(module, "build_plan", lambda *args, **kwargs: {"state_root": "/test"})
    monkeypatch.setattr(module, "remote_mode", remote_mode)

    state = {}
    value = {"authorized_execution_id": "bound-id", "embedded_preflight_manifest": {}}
    with pytest.raises(module.Stop, match="remote_status_unavailable_after_init_attempt"):
        module.execute_live(args, value, state)
    assert calls == ["init", "status"]
    expected = True if init_acknowledged else None
    assert state["authorization_claimed"] is expected
    assert state["authorization_consumed"] is expected


def test_live_uses_staged_exact_artifact_without_network_fetch():
    module = load(LIVE_EXECUTOR, "p3_live_staged_artifact")
    remote = module.REMOTE_SCRIPT
    assert "class StagedArtifactBackend(SubprocessPrepareBackend)" in remote
    assert "with staged.open" in remote
    assert "portable.parse_image_archive(" in remote
    assert "urllib.request" not in remote
    assert "response.read(" not in remote


def test_live_runs_fresh_readonly_before_one_shot_claim_and_scp():
    source = LIVE_EXECUTOR.read_text(encoding="utf-8")
    preflight = source.index("preflight_module.run_readonly(")
    epoch = source.index("transport.start_epoch()", preflight)
    init = source.index('"init",', epoch)
    first_scp = source.index("transport.scp_to(", init)
    execute = source.index('"execute",', first_scp)
    assert preflight < epoch < init < first_scp < execute


def test_live_source_bundle_and_authorization_fail_closed():
    source = LIVE_EXECUTOR.read_text(encoding="utf-8")
    assert "source_bundle_sha256" in source
    assert "product_source_sha256" in source
    assert "source_bundle_member_hash_drift" in source
    assert "granted is not require_authorized" in source
    assert (
        'value.get("new_clean_ota_mutation_authorized")'
        in source
    )
    assert '"granted": granted' in source
    assert 'result["t1_access"] = True' not in source


def test_live_reports_authorization_truth_from_manifest():
    source = LIVE_EXECUTOR.read_text(encoding="utf-8")
    assert (
        'result["live_execution_authorized"] = manifest['
        in source
    )
    assert (
        'result["new_clean_ota_mutation_authorized"] = manifest['
        in source
    )


def test_single_usb_reuse_reset_manifest_is_narrow_and_authorized():
    value = manifest(RESET_MANIFEST)
    assert value["destructive_usb_reset_authorized"] is True
    assert value["transaction_mutation_authorized"] is False
    assert value["service_mutation_authorized"] is False
    assert value["image_mutation_authorized"] is False
    assert value["ha_data_mutation_authorized"] is False
    assert value["p3_live_execution_authorized"] is False
    assert value["expected_historical_media"]["filesystem_uuid"] == (
        value["expected_terminal_u13a"]["filesystem_uuid"]
    )
    contract = value["execution_contract"]
    assert contract["unmount_exact_historical_mount"] is True
    assert contract["remove_historical_filesystem_signature"] is True
    assert contract["repartition"] is False
    assert contract["mkfs"] is False
    assert contract["transaction_write"] is False


def test_single_usb_reuse_reset_remote_is_usb_only_and_fail_closed():
    module = load(RESET_EXECUTOR, "p3_single_usb_reuse_reset")
    compile(module.REMOTE_SCRIPT, "<p3-single-usb-reuse-reset>", "exec")
    remote = module.REMOTE_SCRIPT
    assert 'run(["umount", media["mount_target"]])' in remote
    assert 'run(["wipefs", "--all", "--force", partition_path])' in remote
    assert 'run(["udevadm", "settle"])' in remote
    assert "mkfs" not in remote
    assert "sfdisk" not in remote
    forbidden = (
        ".write(",
        "systemctl",
        '"docker", "rm"',
        '"docker", "image", "rm"',
        "record_recovery_admission(",
        "claim_live_authorization(",
        "record_predecessor_capacity_released(",
        "record_target_started(",
        "record_target_accepted(",
        "record_commit(",
    )
    for token in forbidden:
        assert token not in remote
    assert "single_usb_historical_uuid_drift" in remote
    assert "single_usb_historical_mount_drift" in remote
    assert "single_usb_historical_uuid_still_present" in remote


def test_single_usb_reset_runs_exact_historical_binding_before_destruction():
    source = RESET_EXECUTOR.read_text(encoding="utf-8")
    binding = source.index("p1.run_status_only(")
    reset = source.index("value = remote_reset(", binding)
    assert binding < reset
    module = load(RESET_EXECUTOR, "p3_single_usb_reset_partial_mutation")
    remote = module.REMOTE_SCRIPT
    assert 'MUTATION_STATE["usb_mutation"] = True' in remote
    assert 'MUTATION_STATE["destructive_usb_reset"] = True' in remote


def test_live_requires_verified_single_usb_reset_preflight():
    source = LIVE_EXECUTOR.read_text(encoding="utf-8")
    assert 'preflight.get("single_usb_reuse_after_reset") is not True' in source
    module = load(LIVE_EXECUTOR, "p3_live_single_usb_reset")
    remote = module.REMOTE_SCRIPT
    assert "single_usb_reuse_reset_not_verified" in remote


@pytest.fixture
def p3_u5(monkeypatch):
    recovery = load(RECOVERY_EXECUTOR, "p3_recovery_for_u5")
    monkeypatch.setitem(sys.modules, "executor", recovery)
    return load(RECOVERY_EXECUTOR.with_name("preflight.py"), "p3_u5_preflight")


@pytest.mark.parametrize(
    ("mountinfo", "error"),
    [
        ("", "usb_mount_missing_or_ambiguous"),
        ("42 28 8:1 / /run/medium ro,nosuid,nodev,noexec - ext4 /dev/sdz1 rw", "usb_mount_identity"),
        ("42 28 8:1 / /run/medium rw,nosuid,nodev,noexec - ext4 /dev/sdz1 ro", "usb_mount_identity"),
        ("42 28 8:1 / /run/medium rw,nosuid,nodev,noexec - ext4 /dev/sdz1 rw,noload", "usb_mount_identity"),
        ("42 28 8:2 / /run/medium rw,nosuid,nodev,noexec - ext4 /dev/sdz2 rw", "usb_mount_identity"),
        ("42 28 8:1 / /run/medium rw,nosuid,nodev,noexec - ext4 /dev/sdz1 rw\n"
         "43 28 8:1 / /run/other rw - ext4 /dev/sdz1 rw", "usb_mount_missing_or_ambiguous"),
    ],
)
def test_p3_u5_mount_check_refuses_wrong_mount(monkeypatch, p3_u5, mountinfo, error):
    monkeypatch.setattr(Path, "read_text", lambda _path: mountinfo)
    with pytest.raises(p3_u5.recovery.Stop, match=error):
        p3_u5.mount_entry(17, "8:1", Path("/run/medium"))


def test_p3_u5_mount_check_uses_device_number_not_saved_devnode(monkeypatch, p3_u5):
    mountinfo = "42 28 8:1 / /run/medium rw,nosuid,nodev,noexec - ext4 /dev/sdz1 rw"
    monkeypatch.setattr(Path, "read_text", lambda _path: mountinfo)
    assert p3_u5.mount_entry(17, "8:1", Path("/run/medium"))["id"] == "42"


def test_p3_u5_ipc_queries_status_only(monkeypatch, p3_u5):
    def run_status(stage, arguments, **_):
        assert stage == "manager_ota_ipc_status"
        assert arguments[:5] == ["docker", "exec", "-u", "999:999", "manager"]
        probe = arguments[-1]
        compile(probe, "ipc_probe", "exec")
        assert '"operation":"status"' in probe
        assert "submit" not in probe
        return json.dumps({
            "schema": "gh.n3w-t1-ha-ota-ipc-response/3", "accepted": True, "code": "status",
            "phase": "READY_TO_INSTALL", "error_code": None, "installed_version": "2026.10.4",
        }).encode()

    monkeypatch.setattr(p3_u5, "run", run_status)
    assert p3_u5.ipc_status("manager", "2026.10.4") == "READY_TO_INSTALL"
    with pytest.raises(p3_u5.recovery.Stop, match="ota_ipc_not_ready"):
        p3_u5.ipc_status("manager", "2026.10.0")


def test_p3_u5_returns_stop_if_u4_drifts_during_archive_check(monkeypatch, p3_u5):
    module = p3_u5
    tx = {"current_image_ref": "prior", "target_archive_size": 10, "target_archive_sha256": "digest"}
    plan = {"predecessor_runtime_id": "runtime", "predecessor_version": "2026.10.4"}
    claim = {"peers": {"manager": {"container_id": "manager"},
                       "homeassistant": {"image_ref": "prior", "runtime_image_id": "runtime"}}}
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(module, "bind_ledger", lambda _: claim)
    monkeypatch.setattr(module, "bind_transaction", lambda _, raw: tx)
    monkeypatch.setattr(module.recovery, "check_peers", lambda _: None)
    monkeypatch.setattr(module.recovery, "private_path", lambda *_, **__: None)
    monkeypatch.setattr(module, "service_binding", lambda: (1, {}))
    monkeypatch.setattr(module, "installed_binding", lambda *_: {})
    monkeypatch.setattr(module, "bind_media", lambda *_: (Path("/tmp/media"), {}))
    monkeypatch.setattr(module, "bind_mirror", lambda *_: None)
    monkeypatch.setattr(module, "ipc_status", lambda *_: "READY_TO_INSTALL")

    records = iter([b"u4_before", b"u4_changed"])
    monkeypatch.setattr(module, "read_private",
                        lambda _, size=None: next(records) if size is None else "digest")
    with pytest.raises(module.recovery.Stop, match="transaction_or_mount_changed"):
        module.preflight(plan, {})

    monkeypatch.setattr(module, "read_private",
                        lambda _, size=None: b"u4_before" if size is None else "digest")
    result = {}
    module.preflight(plan, result)
    assert result["status"] == "P3_U5_READONLY_PREFLIGHT_PASS"
    assert result["transaction_phase"] == module.U4


@pytest.fixture
def p3_intent(monkeypatch, p3_u5):
    monkeypatch.setitem(sys.modules, "preflight", p3_u5)
    return load(RECOVERY_EXECUTOR.with_name("install_intent.py"), "p3_install_intent")


def test_p3_u5_intent_requires_separate_exact_unexpired_grant(p3_intent, monkeypatch):
    module = p3_intent
    monkeypatch.setattr(module.time, "time", lambda: 1000)
    plan = {"candidate_commit": "a" * 40, "target": {"target_archive_sha256": "b" * 64}}
    grant = {
        "schema": module.SCHEMA, "authorized": True, "authorization_id": module.AUTHORIZATION_ID,
        "candidate_commit": plan["candidate_commit"], "preflight_receipt_sha256": module.PREFLIGHT_SHA,
        "u4_transaction_sha256": module.preflight.U4_SHA, "target_archive_sha256": "b" * 64,
        "maximum_phase": module.U5, "expires_at_unix": 1001,
    }
    monkeypatch.setattr(module.preflight, "preflight", lambda *_: pytest.fail("unexpected host probe"))
    for bad, reason in (
        (None, "install_grant_required"),
        ({**grant, "maximum_phase": "U6"}, "install_grant_binding_invalid"),
        ({**grant, "candidate_commit": "c" * 40}, "install_grant_binding_invalid"),
        ({**grant, "expires_at_unix": 1000}, "install_grant_expired"),
    ):
        with pytest.raises(module.recovery.Stop, match=reason):
            module.execute({**plan, "grant": bad}, {})
    module.validate_grant(grant, plan)


@pytest.mark.parametrize("host_write_fails", [False, True])
def test_p3_u5_intent_uses_product_usb_then_host_and_exposes_split(
    p3_intent, monkeypatch, tmp_path, host_write_fails
):
    from test_n3w_t1_core_updater_ha_usb_r1 import ready_to_install, target_record
    from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
    from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend
    from n3w_t1_core_updater_ha_usb import request_install
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore

    module = p3_intent
    state = tmp_path / "host"
    mount = tmp_path / "usb"
    mount.mkdir(mode=0o700)
    store = HaUsbStateStore(state)
    backend = SubprocessPrepareBackend()
    monkeypatch.setattr(backend, "_require_bound_media", lambda _: "/dev/test")
    monkeypatch.setattr(module.recovery, "private_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.preflight, "read_private", lambda path: path.read_bytes())
    tx = ready_to_install()
    record = target_record()
    tx["target_artifact_identity"] = record.public()
    media = PreparedUsbMedia("/dev/test", tx["usb_device_identity_public_fingerprint"],
                             tx["usb_filesystem_uuid"], tx["usb_measured_usable_bytes"], str(mount))
    store.write(tx)
    backend.sync_transaction_metadata(tx, media)
    before = store.path.read_bytes()
    u5 = request_install(tx, target=record)
    original_write = store.write

    def assert_usb_first(document):
        assert store.path.read_bytes() == before
        module.preflight.bind_mirror(mount, document)
        assert document["phase"] == module.U5
        if host_write_fails:
            raise OSError("injected host persistence failure")
        original_write(document)

    monkeypatch.setattr(store, "write", assert_usb_first)
    result = {}
    args = (store, backend, media, before, u5, mount, result)
    if host_write_fails:
        with pytest.raises(OSError, match="injected host"):
            module.persist_intent(*args)
        assert result["stage"] == "persist_host_u5"
        assert store.path.read_bytes() == before
    else:
        module.persist_intent(*args)
        assert store.read() == u5
        assert store.path.read_bytes() == module.state_bytes(u5)
        assert store.read()["authorization_consumed"] is False
    module.preflight.bind_mirror(mount, u5)

    ledger = state / module.LEDGER_NAME
    ledger.mkdir(mode=0o700)
    monkeypatch.setattr(module.recovery, "STATE", state)
    monkeypatch.setattr(module.preflight, "U4_SHA", module.digest_bytes(before))
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(module.preflight, "bind_ledger", lambda _: None)
    monkeypatch.setattr(module.preflight, "service_binding", lambda: (1, {}))
    monkeypatch.setattr(module.preflight, "bind_media", lambda *_: (mount, {}))
    module.recovery.write_once(ledger / "claim.json", {
        "schema": module.SCHEMA, "authorization_id": module.AUTHORIZATION_ID,
        "preflight_receipt_sha256": module.PREFLIGHT_SHA, "claimed": True,
        "consumed": True, "replay_permitted": False,
        "u4_transaction_sha256": module.digest_bytes(before),
        "u5_transaction_sha256": module.digest_bytes(module.state_bytes(u5)),
    })
    host_bytes = store.path.read_bytes()
    status = {}
    module.inspect({}, status)
    expected = "STOP_USB_U5_HOST_U4" if host_write_fails else "P3_U5_BOTH_U5_VERIFIED"
    assert status["status"] == expected
    assert status["authorization_claimed"] is True
    assert store.path.read_bytes() == host_bytes


def test_p3_u5_intent_stops_on_existing_ledger_before_probing(p3_intent, monkeypatch, tmp_path):
    module = p3_intent
    monkeypatch.setattr(module, "validate_grant", lambda *_: None)
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(module.os, "umask", lambda _: None)
    monkeypatch.setattr(module, "ledger_root", lambda: tmp_path)
    monkeypatch.setattr(module.preflight, "preflight", lambda *_: pytest.fail("unexpected host probe"))
    with pytest.raises(module.recovery.Stop, match="install_ledger_exists_never_replay"):
        module.execute({}, {})


def test_p3_u5_intent_rejects_changed_preflight_before_claim(p3_intent, monkeypatch, tmp_path):
    module = p3_intent
    monkeypatch.setattr(module, "validate_grant", lambda *_: None)
    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(module.os, "umask", lambda _: None)
    ledger = tmp_path / "ledger"
    monkeypatch.setattr(module, "ledger_root", lambda: ledger)
    monkeypatch.setattr(module.preflight, "preflight", lambda plan, receipt: receipt.update(status="changed"))
    with pytest.raises(module.recovery.Stop, match="archived_preflight_snapshot_drift"):
        module.execute({}, {})
    assert not ledger.exists()


@pytest.fixture
def p3_u6(p3_intent, monkeypatch):
    monkeypatch.setitem(sys.modules, "install_intent", p3_intent)
    return load(RECOVERY_EXECUTOR.with_name("u6_preflight.py"), "p3_u6_preflight")


@pytest.mark.parametrize("edit", ["claim", "receipt", None])
def test_p3_u6_requires_exact_consumed_u5_ledger(p3_u6, monkeypatch, tmp_path, edit):
    module = p3_u6
    intent = module.install_intent
    monkeypatch.setattr(intent, "ledger_root", lambda: tmp_path)
    monkeypatch.setattr(module.recovery, "private_path", lambda *args, **kwargs: None)
    payload = b"U5 result\n"
    claim = {
        "schema": intent.SCHEMA, "authorization_id": intent.AUTHORIZATION_ID,
        "candidate_commit": module.U5_CANDIDATE, "preflight_receipt_sha256": intent.PREFLIGHT_SHA,
        "u4_transaction_sha256": module.preflight.U4_SHA, "u5_transaction_sha256": module.U5_SHA,
        "claimed": True, "consumed": True, "replay_permitted": False,
    }
    monkeypatch.setattr(module, "U5_RECEIPT_SHA", intent.digest_bytes(payload))
    monkeypatch.setattr(module.preflight, "read_object", lambda _: claim)
    monkeypatch.setattr(module.preflight, "read_private", lambda _: payload)
    if edit == "claim":
        claim["replay_permitted"] = True
    if edit == "receipt":
        payload = b"changed receipt"
    if edit:
        with pytest.raises(module.recovery.Stop, match=f"u5_install_intent_{edit}_drift"):
            module.bind_u5_receipt()
    else:
        module.bind_u5_receipt()


@pytest.mark.parametrize("drift", ["archive", "host", None])
def test_p3_u6_readonly_checks_snapshot_before_reporting_pass(p3_u6, monkeypatch, tmp_path, drift):
    module = p3_u6
    tx = {"phase": module.install_intent.U5, "target_archive_size": 10, "target_archive_sha256": "artifact"}
    claim = {"peers": {"manager": {"container_id": "manager"}}}
    mount = tmp_path / "usb"
    media = {"session_fingerprint_matches": True}
    events = []
    state_reads = iter([b"u5", b"different state" if drift == "host" else b"u5"])

    def read_private(_path, *, size=None):
        if size is None:
            return next(state_reads)
        return "broken" if drift == "archive" else "artifact"

    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(module, "bind_u5_receipt", lambda: None)
    monkeypatch.setattr(module, "bind_u5_transaction", lambda *args: tx)
    monkeypatch.setattr(module, "owner_units", lambda: {})
    monkeypatch.setattr(module, "image_binding", lambda _: None)
    monkeypatch.setattr(module, "require_empty_recovery_dirs", lambda _: None)
    monkeypatch.setattr(module.recovery, "private_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.recovery, "check_peers", lambda _: None)
    monkeypatch.setattr(module.preflight, "read_private", read_private)
    monkeypatch.setattr(module.preflight, "bind_ledger", lambda _: claim)
    monkeypatch.setattr(module.preflight, "service_binding", lambda: (1, {}))
    monkeypatch.setattr(module.preflight, "bind_media", lambda *args: (mount, media))
    monkeypatch.setattr(module.preflight, "bind_mirror", lambda *args: events.append("mirror"))
    monkeypatch.setattr(module.preflight, "installed_binding", lambda *args: {"installed_matches_prior_reference": True})
    monkeypatch.setattr(module.install_intent, "archive_stat", lambda _: ())
    monkeypatch.setattr(module, "validate_capacity", lambda *args: SimpleNamespace(
        observed_usb_free_bytes=99, required_remaining_bytes=90,
    ))

    def ipc(container, version, *, expected_phase):
        assert (container, version, expected_phase) == ("manager", "2026.10.4", module.IPC_PHASE)
        events.append("ipc")
        return expected_phase

    monkeypatch.setattr(module.preflight, "ipc_status", ipc)
    result = {}
    plan = {"predecessor_version": "2026.10.4"}
    if drift:
        reason = "u6_target_archive_drift" if drift == "archive" else "u6_preflight_state_drift"
        with pytest.raises(module.recovery.Stop, match=reason):
            module.inspect(plan, result)
        assert "status" not in result
    else:
        module.inspect(plan, result)
        assert result["status"] == module.PASS
        assert result["transaction_phase"] == module.install_intent.U5
        assert result["capacity_pass"] is True
        assert events == ["mirror", "ipc", "mirror"]


@pytest.fixture
def p3_u6_recovery(p3_u6, monkeypatch):
    monkeypatch.setitem(sys.modules, "u6_preflight", p3_u6)
    return load(RECOVERY_EXECUTOR.with_name("u6_recovery.py"), "p3_u6_recovery")


def test_p3_u6_execute_requires_u6_only_grant_before_preflight(p3_u6_recovery, monkeypatch):
    module = p3_u6_recovery
    plan = {"candidate_commit": "a" * 40, "target": {"target_archive_sha256": "b" * 64}}
    monkeypatch.setattr(module.time, "time", lambda: 1000)
    monkeypatch.setattr(module.u6_preflight, "inspect", lambda *_: pytest.fail("authorization precedes probing"))
    grant = {**module.binding(plan), "authorized": True, "expires_at_unix": 1001}
    for invalid, reason in (
        (None, "u6_grant_required"),
        ({**grant, "maximum_phase": "U7"}, "u6_grant_binding_drift"),
        ({**grant, "preflight_receipt_sha256": "0" * 64}, "u6_grant_binding_drift"),
        ({**grant, "expires_at_unix": 1000}, "u6_grant_expired"),
    ):
        with pytest.raises(module.recovery.Stop, match=reason):
            module.execute({**plan, "grant": invalid}, {})
    module.validate_grant({**plan, "grant": grant})


@pytest.mark.parametrize("fail_export", [False, True])
def test_p3_u6_execution_stops_at_u6_and_status_reconciles(
    p3_u6_recovery, monkeypatch, tmp_path, fail_export
):
    from dataclasses import replace
    from test_n3w_t1_core_updater_ha_u6_predecessor import FakeBackend, predecessor_record, u5_transaction
    from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore

    module = p3_u6_recovery
    state = tmp_path / "host"
    mount = tmp_path / "usb"
    mount.mkdir(mode=0o700)
    store = HaUsbStateStore(state)
    u5 = u5_transaction()
    store.write(u5)
    expected_u5 = module.install_intent.digest_bytes(store.path.read_bytes())
    monkeypatch.setattr(module.u6_preflight, "U5_SHA", expected_u5)
    monkeypatch.setattr(module.recovery, "STATE", state)
    monkeypatch.setattr(module.recovery, "private_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "os", SimpleNamespace(
        geteuid=lambda: 0, umask=lambda _: None, path=module.os.path,
    ))

    mirror_backend = SubprocessPrepareBackend()
    monkeypatch.setattr(mirror_backend, "_require_bound_media", lambda _: "/dev/test")
    archive_bytes = b"predecessor archive"
    record = replace(predecessor_record(), archive_sha256=module.install_intent.digest_bytes(archive_bytes),
                     archive_size_bytes=len(archive_bytes))

    class LocalBackend(FakeBackend):
        def __init__(self):
            super().__init__(fail_export=fail_export)
            self.media = replace(self.media, mount_path=str(mount))

        def sync_transaction_metadata(self, transaction, media):
            super().sync_transaction_metadata(transaction, media)
            mirror_backend.sync_transaction_metadata(transaction, media)

        def prepare_predecessor_recovery(self, *, transaction, media):
            assert store.read()["phase"] == module.U6
            module.preflight.bind_mirror(mount, transaction)
            assert manifest(module.ledger_root() / "claim.json")["consumed"] is True
            super().prepare_predecessor_recovery(transaction=transaction, media=media)
            archive = mount / "n3w-update" / "predecessor" / "homeassistant-predecessor.tar.gz"
            archive.parent.mkdir()
            archive.write_bytes(archive_bytes)
            return record

        def verify_prepared_predecessor(self, *, transaction, media):
            return record

    backend = LocalBackend()
    mirror_backend.sync_transaction_metadata(u5, backend.media)
    plan = {"candidate_commit": "a" * 40, "target": {"target_archive_sha256": u5["target_archive_sha256"]},
            "predecessor_version": "2026.10.4"}
    plan["grant"] = {**module.binding(plan), "authorized": True, "expires_at_unix": int(module.time.time()) + 120}

    def inspect_preflight(_, result):
        result["status"] = module.u6_preflight.PASS
        return {"transaction": u5, "mount": mount, "original_claim": {"peers": {"manager": {"container_id": "m"}}}}

    def read_private(path, *, size=None):
        payload = path.read_bytes()
        if size is None:
            return payload
        assert size == len(payload)
        return module.install_intent.digest_bytes(payload)

    monkeypatch.setattr(module, "bound_backend", lambda *_: backend)
    monkeypatch.setattr(module, "check_binding", lambda *args: None)
    monkeypatch.setattr(module.u6_preflight, "inspect", inspect_preflight)
    monkeypatch.setattr(module.u6_preflight, "validate_capacity", lambda *args: None)
    monkeypatch.setattr(module.preflight, "read_private", read_private)
    monkeypatch.setattr(module.preflight, "bind_ledger", lambda _: None)
    monkeypatch.setattr(module.preflight, "service_binding", lambda: (1, {}))
    monkeypatch.setattr(module.preflight, "bind_media", lambda *args: (mount, {}))
    monkeypatch.setattr(module.preflight, "ipc_status", lambda *args, expected_phase: expected_phase)
    result = {}
    if fail_export:
        with pytest.raises(RuntimeError, match="synthetic_export_failed"):
            module.execute(plan, result)
        assert result["status"] == "STOP_POSTCLAIM"
        assert (module.ledger_root() / "failure.json").is_file()
    else:
        module.execute(plan, result)
        assert result["status"] == module.PASS
        assert result["predecessor"] == record.public()
        assert (module.ledger_root() / "success.json").is_file()
    assert store.read()["phase"] == module.U6
    assert store.read()["authorization_claimed"] is False
    assert backend.synced_phases == [module.U6]

    status = {}
    module.inspect(plan, status)
    assert status["status"] == ("P3_U6_NO_DURABLE_PASS" if fail_export else "P3_U6_DURABLE_PASS_VERIFIED")
    with pytest.raises(module.recovery.Stop, match="u6_ledger_exists_never_replay"):
        module.execute(plan, {})
    assert backend.synced_phases == [module.U6]


@pytest.fixture
def p3_u7(p3_u6_recovery, monkeypatch):
    monkeypatch.setitem(sys.modules, "u6_recovery", p3_u6_recovery)
    return load(RECOVERY_EXECUTOR.with_name("check_ha_backup.py"), "p3_u7")


def test_p3_u7_binds_completed_u6_and_refuses_changed_ledger(p3_u7, monkeypatch, tmp_path):
    module = p3_u7
    u6 = module.u6_recovery
    plan = {"target": {"target_archive_sha256": "a" * 64}}
    claim = {
        **u6.binding({**plan, "candidate_commit": module.U6_CANDIDATE}),
        "claimed": True, "consumed": True, "replay_permitted": False,
    }
    receipt = {
        "status": u6.PASS, "transaction_sha256": module.U6_SHA, "transaction_phase": u6.U6,
        "u7_plus": False, "predecessor": {"archive_sha256": "b" * 64},
    }
    monkeypatch.setattr(u6, "ledger_root", lambda: tmp_path)
    monkeypatch.setattr(module.recovery, "private_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.preflight, "read_object", lambda _: claim)
    success = tmp_path / "success.json"
    success.write_text(json.dumps(receipt))
    monkeypatch.setattr(module.preflight, "read_private", Path.read_bytes)
    monkeypatch.setattr(module, "U6_RECEIPT_SHA", module.install_intent.digest_bytes(success.read_bytes()))

    assert module.bind_u6_receipt(plan) == receipt["predecessor"]
    claim["candidate_commit"] = "c" * 40
    with pytest.raises(module.recovery.Stop, match="u6_recovery_claim_drift"):
        module.bind_u6_receipt(plan)
    claim["candidate_commit"] = module.U6_CANDIDATE
    success.write_text(json.dumps({**receipt, "u7_plus": True}))
    with pytest.raises(module.recovery.Stop, match="u6_recovery_receipt_drift"):
        module.bind_u6_receipt(plan)


@pytest.mark.parametrize("drift", [None, "predecessor", "capacity", "late_archive", "late_host"])
def test_p3_u7_readonly_entry_preserves_u6_and_rejects_drift(p3_u7, monkeypatch, tmp_path, drift):
    import base64

    module = p3_u7
    tx = {"phase": module.u6_recovery.U6, "target_archive_size": 10, "target_archive_sha256": "target"}
    claim = {"peers": {"manager": {"container_id": "mgr"}, "homeassistant": {"container_id": "ha"}}}
    predecessor = {"archive_sha256": "old"}
    mount = tmp_path / "usb"
    media = {"session_fingerprint_matches": True}
    states = iter([b"u6", b"changed" if drift == "late_host" else b"u6"])
    archives = iter([(), (), ("changed",) if drift == "late_archive" else ()])
    events = []

    def verify_archive(*args):
        assert args == (mount, tx, predecessor)
        module.require(drift != "predecessor", "u6_predecessor_archive_digest_drift")

    def verify_capacity(*_):
        module.require(drift != "capacity", "capacity_failed")
        return SimpleNamespace(observed_usb_free_bytes=99, required_remaining_bytes=90)

    def ipc(container, version, *, expected_phase):
        assert (container, version, expected_phase) == ("mgr", "2026.10.4", module.u6_recovery.IPC_U6)
        events.append("ipc")
        return expected_phase

    monkeypatch.setattr(module.os, "geteuid", lambda: 0)
    monkeypatch.setattr(module.recovery, "private_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.recovery, "check_peers", lambda _: None)
    monkeypatch.setattr(module, "bind_u6_receipt", lambda _: predecessor)
    monkeypatch.setattr(module, "bind_u6_transaction", lambda *args: tx)
    monkeypatch.setattr(module.u6_preflight, "owner_units", lambda: {})
    monkeypatch.setattr(module.u6_preflight, "image_binding", lambda _: None)
    monkeypatch.setattr(module.preflight, "read_private", lambda _, size=None: "target" if size else next(states))
    monkeypatch.setattr(module.preflight, "bind_ledger", lambda _: claim)
    monkeypatch.setattr(module.preflight, "service_binding", lambda: (1, {}))
    monkeypatch.setattr(module.preflight, "installed_binding", lambda *args: {"installed_matches_prior_reference": True})
    monkeypatch.setattr(module.preflight, "bind_media", lambda *args: (mount, media))
    monkeypatch.setattr(module.preflight, "bind_mirror", lambda *args: events.append("mirror"))
    monkeypatch.setattr(module.install_intent, "archive_stat", lambda _: next(archives))
    monkeypatch.setattr(module.install_intent, "check_continuity", lambda *args: None)
    monkeypatch.setattr(module.u6_recovery, "verify_archive", verify_archive)
    monkeypatch.setattr(module, "backup_inputs", lambda role: events.append(role))
    monkeypatch.setattr(module, "verify_capacity", verify_capacity)
    monkeypatch.setattr(module.preflight, "ipc_status", ipc)

    args = base64.b64encode(json.dumps({"predecessor_version": "2026.10.4"}).encode())
    assert module.remote_main(args) == (2 if drift else 0)
    if not drift:
        assert events == ["mirror", "ha", "ipc", "mirror"]


def test_p3_u7_bootstrap_loads_remote_readonly_entry(p3_u7):
    import subprocess

    module = p3_u7
    bootstrap = module.u6_recovery.make_bootstrap(
        Path(module.__file__), extra_modules=(("u6_recovery", module.u6_recovery),),
    )
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", bootstrap, "--remote", "invalid"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 2, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["schema"] == module.SCHEMA
    assert receipt["read_only"] is True
    assert receipt["u7_transition"] is False
    assert receipt["status"] == "STOP"


@pytest.fixture
def p3_u7_backup(p3_u7, monkeypatch):
    monkeypatch.setitem(sys.modules, "check_ha_backup", p3_u7)
    return load(RECOVERY_EXECUTOR.with_name("ha_backup.py"), "p3_u7_backup")


def test_p3_u7_execute_requires_unexpired_exact_u7_grant(p3_u7_backup, monkeypatch):
    module = p3_u7_backup
    plan = {"candidate_commit": "a" * 40, "target": {"target_archive_sha256": "b" * 64}}
    monkeypatch.setattr(module.time, "time", lambda: 1000)
    monkeypatch.setattr(module.check_ha_backup, "inspect", lambda *_: pytest.fail("grant checked before probes"))
    grant = {**module.binding(plan), "authorized": True, "expires_at_unix": 1001}
    for invalid, reason in (
        (None, "u7_grant_required"),
        ({**grant, "maximum_phase": "U8"}, "u7_grant_binding_drift"),
        ({**grant, "preflight_receipt_sha256": "0" * 64}, "u7_grant_binding_drift"),
        ({**grant, "expires_at_unix": 1000}, "u7_grant_expired"),
    ):
        with pytest.raises(module.recovery.Stop, match=reason):
            module.execute({**plan, "grant": invalid}, {})
    module.validate_grant({**plan, "grant": grant})


@pytest.mark.parametrize("failure", [None, "prestop_drift", "backup_failure"])
def test_p3_u7_candidate_checks_claim_stops_at_u7_and_reconciles(
    p3_u7_backup, monkeypatch, tmp_path, failure,
):
    import base64
    from dataclasses import replace
    from test_n3w_t1_core_updater_ha_backup_u7 import (
        FakeBackend, FakeBackup, FakeRuntime, FINGERPRINT, PREDECESSOR_RECORD, USB_UUID, build_u6,
    )
    import n3w_t1_core_updater_ha_backup as product_backup
    import n3w_t1_core_updater_host as host
    from n3w_t1_core_updater_ha_prepare import PreparedUsbMedia
    from n3w_t1_core_updater_ha_prepare_host import SubprocessPrepareBackend
    from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore

    module = p3_u7_backup
    state = tmp_path / "host"
    mount = tmp_path / "usb"
    mount.mkdir()
    store = HaUsbStateStore(state)
    u6 = build_u6()
    store.write(u6)
    monkeypatch.setattr(module.recovery, "STATE", state)
    monkeypatch.setattr(module.recovery, "private_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.check_ha_backup, "U6_SHA", module.install_intent.digest_bytes(store.path.read_bytes()))
    monkeypatch.setattr(module, "os", SimpleNamespace(geteuid=lambda: 0, umask=lambda _: None, path=module.os.path))
    mirror = SubprocessPrepareBackend()
    monkeypatch.setattr(mirror, "_require_bound_media", lambda _: "/dev/test")

    class LocalBackend(FakeBackend):
        def sync_transaction_metadata(self, transaction, media):
            super().sync_transaction_metadata(transaction, media)
            mirror.sync_transaction_metadata(transaction, media)

    backend = LocalBackend(PreparedUsbMedia("/dev/test", FINGERPRINT, USB_UUID, 20 * 1024**3, str(mount)))
    mirror.sync_transaction_metadata(u6, backend.media)
    encrypted = b"encrypted archive"
    provider = FakeBackup(fail=failure == "backup_failure")
    provider.record = replace(provider.record, archive_sha256=module.install_intent.digest_bytes(encrypted),
                              archive_size_bytes=len(encrypted))

    def create(**kwargs):
        record = FakeBackup.create_consistent_backup(provider, **kwargs)
        assert store.read()["phase"] == module.U7
        assert runtime.quiesce_count == 1
        assert manifest(module.ledger_root() / "claim.json")["consumed"] is True
        destination = kwargs["destination_root"]
        destination.mkdir()
        (destination / product_backup.BACKUP_ARCHIVE_NAME).write_bytes(encrypted)
        (destination / product_backup.BACKUP_METADATA_NAME).write_bytes(b"verified backup metadata")
        return record

    provider.create_consistent_backup = create
    runtime = FakeRuntime()
    monkeypatch.setattr(host, "LocalHost", lambda: runtime)
    monkeypatch.setattr(product_backup, "ProtectedHaDataBackupProvider", lambda: provider)
    plan = {"candidate_commit": "a" * 40, "target": {"target_archive_sha256": u6["target_archive_sha256"]}}
    plan["grant"] = {**module.binding(plan), "authorized": True, "expires_at_unix": int(module.time.time()) + 120}
    media = {"session_fingerprint_matches": True}
    broker = {"InvocationID": "before"}
    before_claim = {"peers": {}}
    predecessor = PREDECESSOR_RECORD.public()
    snapshot = {
        "transaction": u6, "mount": mount, "original_claim": before_claim, "usb_binding": media,
        "daemon": {}, "owner_units": {host.BROKER_UNIT: broker}, "runtime_admission": {},
        "old_path": mount / "old", "old_stat": (), "target_path": mount / "target", "target_stat": (),
        "predecessor": predecessor,
    }

    def inspect_preflight(_, result):
        result["status"] = module.check_ha_backup.PASS
        return snapshot

    def read_private(path, *, size=None):
        data = path.read_bytes()
        if size is None:
            return data
        assert size == len(data)
        return module.install_intent.digest_bytes(data)

    def check_binding(*args):
        if failure == "prestop_drift" and (module.ledger_root() / "claim.json").exists():
            raise module.recovery.Stop("u7_prestop_binding_drift")

    def verify_quiesced(claim, unit):
        assert claim == before_claim and unit == broker
        assert (runtime.quiesce_count, runtime.resume_count) == (1, 0)

    monkeypatch.setattr(module, "bound_backend", lambda *_: backend)
    monkeypatch.setattr(module, "verify_quiesced", verify_quiesced)
    monkeypatch.setattr(module.u6_recovery, "check_binding", check_binding)
    monkeypatch.setattr(module.u6_preflight, "image_binding", lambda _: None)
    monkeypatch.setattr(module.check_ha_backup, "inspect", inspect_preflight)
    monkeypatch.setattr(module.check_ha_backup, "verify_capacity", lambda *_: None)
    monkeypatch.setattr(module.check_ha_backup, "bind_u6_receipt", lambda _: predecessor)
    monkeypatch.setattr(module.install_intent, "archive_stat", lambda _: ())
    monkeypatch.setattr(module.preflight, "read_private", read_private)
    monkeypatch.setattr(module.preflight, "bind_ledger", lambda _: before_claim)
    monkeypatch.setattr(module.preflight, "service_binding", lambda: (1, {}))
    monkeypatch.setattr(module.preflight, "bind_media", lambda *args: (mount, media))
    monkeypatch.setattr(module.preflight, "installed_binding", lambda *args: {})
    encoded = base64.b64encode(json.dumps(plan).encode())
    assert module.remote_main("execute", encoded) == (2 if failure else 0)
    durable = module.ledger_root() / ("failure.json" if failure else "success.json")
    receipt = manifest(durable)
    assert receipt["replay_permitted"] is False and receipt["u8_plus"] is False
    assert receipt["authorization_consumed"] is True
    assert store.read()["phase"] == (module.u6_recovery.U6 if failure == "prestop_drift" else module.U7)
    assert (runtime.quiesce_count, runtime.resume_count) == {
        None: (1, 0), "prestop_drift": (0, 0), "backup_failure": (1, 1),
    }[failure]
    if failure:
        assert receipt["status"] == "STOP_POSTCLAIM"
    else:
        assert receipt["status"] == module.PASS
        assert receipt["backup"] == store.read()["ha_data_backup_identity"]
    status = {}
    module.inspect(plan, status)
    assert status["status"] == ("P3_U7_NO_DURABLE_PASS" if failure else module.STATUS_PASS)
    with pytest.raises(module.recovery.Stop, match="u7_ledger_exists_never_replay"):
        module.execute(plan, {})


def test_p3_u7_backup_bootstrap_requires_grant_before_probing(p3_u7_backup):
    import subprocess

    module = p3_u7_backup
    bootstrap = module.u6_recovery.make_bootstrap(
        Path(module.__file__), extra_modules=(("u6_recovery", module.u6_recovery), ("check_ha_backup", module.check_ha_backup)),
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", bootstrap, "--remote", "execute", "e30="],
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 2, completed.stderr
    receipt = json.loads(completed.stdout)
    assert receipt["reason"] == "u7_grant_required"
    assert receipt["service_stop_attempted"] is False
