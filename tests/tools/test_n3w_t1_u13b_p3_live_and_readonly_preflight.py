from __future__ import annotations

import importlib.util
import json
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
