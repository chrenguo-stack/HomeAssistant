from __future__ import annotations

import base64
import copy
import fcntl
import io
import json
import os
import subprocess
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import n3w_t1_core_updater_ha_recovery_deploy as deploy
import n3w_t1_core_updater_ha_recovery_startup as startup
import n3w_t1_core_updater_signed_release as signing
from n3w_t1_core_stack_release import make_release, release_material
from n3w_t1_core_updater_common import UpdaterError
from n3w_t1_core_updater_ha_ipc import (
    APPROVED_MANIFEST, IPC_SOCKET, RELEASE_PIN, SIGNED_INDEX_STATE, HaUsbIpcExecutor, LocalApprovedHaRelease,
)
from n3w_t1_core_updater_ha_usb_state import HaUsbStateStore
from n3w_t1_core_updater_v2_common import UpdaterV2Error, canonical, sha256_bytes


@pytest.fixture
def signed_inputs(tmp_path):
    key = tmp_path / "fixture-key.pem"
    subprocess.run(("/usr/bin/openssl", "genpkey", "-algorithm", "ED25519", "-out", str(key)), check=True)
    public = subprocess.check_output(("/usr/bin/openssl", "pkey", "-in", str(key), "-pubout", "-outform", "DER"))
    policy = tmp_path / "trust.json"
    policy.write_bytes(canonical({
        "schema": signing.TRUST_SCHEMA, "base_url": "https://releases.example.test/ota",
        "minimum_index_sequence": 5, "public_key_der_base64": base64.b64encode(public).decode(),
    }))
    before = release_material(json.loads((ROOT / "infra/n3w-t1/releases/1.0.0/release.json").read_bytes()))
    before["runtime_contract"]["image_binding_modes"]["homeassistant"] = "dynamic"
    before = make_release(before)
    after = release_material(copy.deepcopy(before))
    after["stack_version"] = "1.0.1"
    target = json.loads((ROOT / "infra/n3w-t1/upgrades/homeassistant-2026.10.4.json").read_bytes())
    after["product_source_head"] = target["compatibility_evidence"]["target_source_head"]
    after["components"]["homeassistant"] = {
        "image": target["target_image_ref"], "platform": "linux/arm64",
        "identity": {"kind": "tar_sha256", "sha256": target["target_archive_sha256"]},
    }
    after = make_release(after)
    release = {
        "schema": signing.DISTRIBUTION_SCHEMA, "expires_at_unix": 2_147_483_647,
        "predecessor": before, "target": after, "archive_path": "1.0.1/target.tar",
        "minimum_updater_version": "0.1.0", "required_updater_capabilities": sorted(signing.CHECKER_CAPABILITIES),
        "predecessor_runtime_image_ids": {
            name: "sha256:" + str(number) * 64 for number, name in enumerate(sorted(before["components"]), 1)
        },
        "ha_candidate": {
            "schema": "gh.n3w-t1-ota-approved-manifest/1", "release_identity": after["release_id"],
            "version": "2026.10.4", "approval_status": "APPROVED", "signature_status": "VERIFIED",
            "validity_status": "VALID", "verification_status": "PASS", "target_archive_size_bytes": 835309535,
            "target": target,
        },
    }
    index = {
        "schema": signing.INDEX_SCHEMA, "expires_at_unix": 2_147_483_647,
        "sequence": 5, "release_id": after["release_id"], "release_path": "1.0.1/release.json",
    }

    def signature(raw):
        payload = tmp_path / "data"
        payload.write_bytes(raw)
        return subprocess.check_output((
            "/usr/bin/openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(key), "-in", str(payload),
        ))

    return policy, index, release, signature


def simulated_predecessor(release):
    predecessor_ids = release["predecessor_runtime_image_ids"]
    images = {
        name: {"reference": component["image"], "runtime_id": predecessor_ids[name]}
        for name, component in release["predecessor"]["components"].items()
    }
    current = {
        "image_ref": images["homeassistant"]["reference"], "image_id": predecessor_ids["homeassistant"],
        "platform": "linux/arm64",
    }
    runtime = SimpleNamespace(
        _runtime=lambda service: current, _open_target_source=deploy.LocalHaPredecessorRuntime._open_target_source,
        capture_start_binding=lambda transaction: {"images": copy.deepcopy(images), "launch_sha256": "b" * 64},
    )
    return images, current, runtime


@pytest.mark.parametrize(("fault", "reason"), [
    (None, None),
    ("index_signature", "signature_invalid"),
    ("manifest_signature", "signature_invalid"),
    ("manifest_substitution", "index_manifest_binding_mismatch"),
    ("stale", "index_sequence_too_old"),
    ("expired", "signed_release_expired"),
    ("path", "signed_release_path_invalid"),
    ("updater", "updater_version_insufficient"),
    ("missing_capability", "updater_capabilities_unsupported"),
    ("archive_hash", "candidate_binding_mismatch"),
    ("runtime_ids", "predecessor_image_ids_invalid"),
    ("broker", "stack_scope_mismatch"),
])
def test_signed_release_checks_exact_bytes_and_ha_only_contract(signed_inputs, fault, reason):
    policy, index, release, signature = signed_inputs
    if fault == "stale":
        index["sequence"] -= 1
    elif fault == "expired":
        release["expires_at_unix"] = 1
    elif fault == "path":
        index["release_path"] = "https://other.example.test/release.json"
    elif fault == "updater":
        release["minimum_updater_version"] = "0.2.0"
    elif fault == "missing_capability":
        release["required_updater_capabilities"].remove("STACK_ROLLBACK_V1")
    elif fault == "archive_hash":
        release["ha_candidate"]["target"]["target_archive_sha256"] = "a" * 64
    elif fault == "runtime_ids":
        release["predecessor_runtime_image_ids"].pop("broker")
    elif fault == "broker":
        after = release_material(release["target"])
        after["components"]["broker"]["image"] = "local/n3w-mosquitto:other"
        release["target"] = make_release(after)
        index["release_id"] = release["target"]["release_id"]
    manifest_raw = canonical(release)
    index["release_sha256"] = "a" * 64 if fault == "manifest_substitution" else sha256_bytes(manifest_raw)
    index_raw = canonical(index)
    transport = {
        "/ota/index.json": index_raw,
        "/ota/index.json.sig": signature(b"other index" if fault == "index_signature" else index_raw),
        "/ota/1.0.1/release.json": manifest_raw,
        "/ota/1.0.1/release.json.sig": signature(b"other manifest" if fault == "manifest_signature" else manifest_raw),
    }
    calls = []

    def fetch(host, path, limit):
        assert host == "releases.example.test"
        calls.append(path)
        return transport[path][:limit + 1]

    if reason:
        with pytest.raises(UpdaterV2Error, match=reason):
            signing.check_signed_release(policy, fetch=fetch)
        if fault in {"index_signature", "stale", "path"}:
            assert calls == ["/ota/index.json", "/ota/index.json.sig"]
    else:
        result = signing.check_signed_release(policy, fetch=fetch)
        assert calls == list(transport)
        assert result["status"] == "SIGNED_RELEASE_VERIFIED"
        assert result["release_id"] == release["target"]["release_id"]
        assert result["archive_sha256"] == release["ha_candidate"]["target"]["target_archive_sha256"]


def test_https_fetch_rejects_redirect_without_dispatching_another_request(monkeypatch):
    calls = []
    connection = SimpleNamespace(
        request=lambda method, path, **kwargs: calls.append((method, path)),
        getresponse=lambda: SimpleNamespace(status=302, close=lambda: None),
        close=lambda: None,
    )
    monkeypatch.setattr(signing.http.client, "HTTPSConnection", lambda host, **kwargs: connection)
    with pytest.raises(UpdaterV2Error, match="https_response_invalid"):
        signing._fetch_https("releases.example.test", "/ota/index.json", 4096)
    assert calls == [("GET", "/ota/index.json")]


@pytest.mark.parametrize("fault", [
    None, "runtime_id", "runtime_changed", "archive_length", "archive_digest", "new_transaction",
])
def test_signed_candidate_streams_verified_archive_and_admits_exact_intent(signed_inputs, tmp_path, monkeypatch, fault):
    policy, index, release, signature = signed_inputs
    candidate = release["ha_candidate"]
    target = candidate["target"]
    layer = b"fixture layer"
    config = canonical({
        "architecture": "arm64", "os": "linux", "config": {"Entrypoint": ["homeassistant"]},
        "rootfs": {"type": "layers", "diff_ids": ["sha256:" + sha256_bytes(layer)]},
    })
    config_name = sha256_bytes(config) + ".json"
    contents = io.BytesIO()
    with tarfile.open(fileobj=contents, mode="w") as archive:
        for name, blob in (
            (config_name, config), ("layer.tar", layer), ("manifest.json", canonical([
                {"Config": config_name, "Layers": ["layer.tar"], "RepoTags": [target["target_image_ref"]]},
            ])),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(blob)
            archive.addfile(member, io.BytesIO(blob))
    payload = contents.getvalue()
    target["target_archive_sha256"] = sha256_bytes(payload)
    candidate["target_archive_size_bytes"] = len(payload)
    target_stack = release_material(release["target"])
    target_stack["components"]["homeassistant"]["identity"]["sha256"] = target["target_archive_sha256"]
    release["target"] = make_release(target_stack)
    candidate["release_identity"] = index["release_id"] = release["target"]["release_id"]
    manifest_raw = canonical(release)
    index["release_sha256"] = sha256_bytes(manifest_raw)

    root = tmp_path / "host"
    outbound = root / IPC_SOCKET.parent.relative_to("/")
    outbound.mkdir(parents=True)
    store = HaUsbStateStore(root / deploy.STATE_ROOT_V2.relative_to("/"))
    index_file = store.root / SIGNED_INDEX_STATE
    partial = store.root / deploy.CANDIDATE_DOWNLOAD_PART
    pin = store.root / RELEASE_PIN
    exported = outbound / APPROVED_MANIFEST
    images, current, runtime = simulated_predecessor(release)
    if fault == "runtime_id":
        images["manager"]["runtime_id"] = "sha256:" + "a" * 64
    resolver = LocalApprovedHaRelease(pin, exported, lambda: current)
    executor = HaUsbIpcExecutor(store=store, admission_resolver=resolver)

    archive_path = "/ota/1.0.1/target.tar"
    transport = {
        "/ota/1.0.1/release.json": manifest_raw, "/ota/1.0.1/release.json.sig": signature(manifest_raw),
        archive_path: payload[:-1] + b"x" if fault == "archive_digest" else payload,
    }
    archive_requests = []

    def publish_index(sequence):
        index["sequence"] = sequence
        raw = canonical(index)
        transport["/ota/index.json"] = raw
        transport["/ota/index.json.sig"] = signature(raw)
        return sha256_bytes(raw)

    def connect(host, **kwargs):
        assert host == "releases.example.test" and kwargs["context"].check_hostname

        def request(method, path, *, headers):
            assert method == "GET" and headers == {"Accept-Encoding": "identity"}
            connection.path = path
            if path == archive_path:
                assert not pin.exists() and not exported.exists()
                with store.lock():
                    if fault == "new_transaction":
                        monkeypatch.setattr(deploy.V2StateStore, "read", lambda self: {"status": "ACTIVE"})
                archive_requests.append(path)
                if fault == "runtime_changed":
                    images["broker"]["runtime_id"] = "sha256:" + "a" * 64

        def response():
            output = io.BytesIO(transport[connection.path])
            output.status = 200
            output.getheader = lambda name, default=None: (
                str(len(payload) + 1) if name == "Content-Length" and fault == "archive_length" else default
            )
            return output

        connection = SimpleNamespace(request=request, getresponse=response, close=lambda: None)
        return connection

    monkeypatch.setattr(signing.http.client, "HTTPSConnection", connect)
    accepted_digest = publish_index(7)

    def materialize():
        return deploy.materialize_signed_candidate(policy, root=root, runtime=runtime)

    if fault:
        reason = {
            "runtime_id": "signed_predecessor_identity_mismatch", "runtime_changed": "predecessor_changed",
            "archive_length": "archive_length_mismatch", "archive_digest": "archive_digest_mismatch",
            "new_transaction": "transaction_active",
        }[fault]
        with pytest.raises((UpdaterError, UpdaterV2Error), match=reason):
            materialize()
        assert len(archive_requests) == (0 if fault == "runtime_id" else 1)
        assert not pin.exists() and not exported.exists() and not index_file.exists()
        assert not partial.exists()
        if fault in {"runtime_id", "archive_length", "archive_digest"}:
            assert not list(store.root.glob("*.tar"))
        return

    with store.lock():
        partial.write_bytes(b"incomplete download from interrupted process")
    download_lock = store.root / deploy.CANDIDATE_DOWNLOAD_LOCK
    download_lock.touch(mode=0o600)
    with download_lock.open("r+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(UpdaterError, match="candidate_download_busy"):
            materialize()
        assert partial.exists() and not archive_requests
    result = materialize()
    assert not partial.exists()
    staged = Path(result["target_source"])
    assert result["index_sequence"] == 7 and result["index_sha256"] == accepted_digest
    assert staged.read_bytes() == payload and staged.stat().st_mode & 0o777 == 0o600
    assert index_file.stat().st_mode & 0o777 == 0o600
    assert exported.read_bytes() == canonical(candidate)
    assert materialize() == result and archive_requests == [archive_path]
    signed_binding = sha256_bytes(canonical(runtime.capture_start_binding({})))
    admission = resolver.resolve_homeassistant_release(index["release_id"])
    assert admission.target_manifest_identity["predecessor_binding_sha256"] == signed_binding
    publish_index(6)
    with pytest.raises(UpdaterError, match="signed_index_replay"):
        materialize()
    index["expires_at_unix"] -= 1
    publish_index(7)
    with pytest.raises(UpdaterError, match="signed_index_sequence_conflict"):
        materialize()

    # A power loss after committing the higher sequence blocks the previous signed pin until retry.
    publish_index(8)
    write_record = deploy._write_candidate_record

    def interrupt(path, content, mode):
        if path == pin:
            raise OSError("simulated signed pin interruption")
        write_record(path, content, mode)

    with monkeypatch.context() as patch:
        patch.setattr(deploy, "_write_candidate_record", interrupt)
        with pytest.raises(OSError, match="simulated signed pin interruption"):
            materialize()
    with pytest.raises(UpdaterV2Error, match="signed_release_pin_invalid"):
        executor.submit("PREPARE", index["release_id"])
    assert store.read() is None
    assert materialize()["index_sequence"] == 8 and archive_requests == [archive_path]
    assert executor.submit("PREPARE", index["release_id"])["phase"] == "PREPARE_REQUESTED"
    transaction = store.read()
    assert transaction["target_archive_sha256"] == sha256_bytes(payload)
    assert transaction["target_manifest_identity"]["predecessor_binding_sha256"] == signed_binding

    images["broker"]["runtime_id"] = "sha256:" + "c" * 64
    monkeypatch.setattr(startup, "IPC_SOCKET", outbound / IPC_SOCKET.name)
    with pytest.raises(UpdaterV2Error, match="signed_predecessor_binding_drift"):
        startup.LocalHaPredecessorRuntime.issue_candidate_authority(runtime, store, "prepare", {
            "expires_at_unix": 2_147_483_647, "transaction_id_sha256": transaction["transaction_id_sha256"],
        })
    assert store.read() == transaction
    assert not (store.root / startup.PREPARE_AUTHORITY_FILE).exists()


def test_signed_distribution_stages_frozen_ha_archive(signed_inputs, tmp_path, monkeypatch):
    artifact_dir = os.environ.get("N3W_T1_HA_EXACT_ARTIFACT_DIR")
    if artifact_dir is None:
        pytest.skip("frozen HA archive is supplied by the exact target-binding job")
    artifact = Path(artifact_dir)
    archive = artifact / "homeassistant-arm64.tar.gz"
    binding = json.loads((artifact / "upstream-binding.json").read_bytes())
    policy, index, release, signature = signed_inputs
    candidate = release["ha_candidate"]
    target = candidate["target"]

    assert binding["local_image"] == target["target_image_ref"]
    assert binding["control_plane_head"] == release["target"]["product_source_head"]
    assert binding["archive_sha256"] == target["target_archive_sha256"]
    size = candidate["target_archive_size_bytes"]
    assert archive.stat().st_size == binding["archive_size_bytes"] == size

    release["archive_path"] = "1.0.1/homeassistant-arm64.tar.gz"
    release_raw = canonical(release)
    index["release_sha256"] = sha256_bytes(release_raw)
    index_raw = canonical(index)
    metadata = {
        "/ota/index.json": index_raw,
        "/ota/index.json.sig": signature(index_raw),
        "/ota/1.0.1/release.json": release_raw,
        "/ota/1.0.1/release.json.sig": signature(release_raw),
    }
    archive_url = "/ota/" + release["archive_path"]
    requests = []

    def connect(host, *, timeout, context):
        assert host == "releases.example.test" and context.check_hostname

        def request(method, path, *, headers):
            assert method == "GET" and headers == {"Accept-Encoding": "identity"}
            requests.append(path)

        def response():
            path = requests[-1]
            stream = archive.open("rb") if path == archive_url else io.BytesIO(metadata[path])
            return SimpleNamespace(
                status=200, read=stream.read, close=stream.close,
                getheader=lambda name, default=None: (
                    str(size) if name == "Content-Length" and path == archive_url else default
                ),
            )

        return SimpleNamespace(request=request, getresponse=response, close=lambda: None)

    monkeypatch.setattr(signing.http.client, "HTTPSConnection", connect)
    root = tmp_path / "host"
    export = root / IPC_SOCKET.parent.relative_to("/")
    export.mkdir(parents=True)
    _, current, runtime = simulated_predecessor(release)
    result = deploy.materialize_signed_candidate(policy, root=root, runtime=runtime)
    assert requests == [*metadata, archive_url]
    assert result["status"] == "CANDIDATE_MATERIALIZED"
    assert result["index_sha256"] == sha256_bytes(index_raw)
    assert result["release_identity"] == index["release_id"]

    store = HaUsbStateStore(root / deploy.STATE_ROOT_V2.relative_to("/"))
    staged = store.root / f"ha-target-{target['target_archive_sha256']}.tar"
    assert Path(result["target_source"]) == staged and staged.stat().st_size == size
    assert (export / APPROVED_MANIFEST).read_bytes() == canonical(candidate)
    resolver = LocalApprovedHaRelease(store.root / RELEASE_PIN, export / APPROVED_MANIFEST, lambda: current)
    executor = HaUsbIpcExecutor(store=store, admission_resolver=resolver)
    assert executor.submit("PREPARE", index["release_id"])["phase"] == "PREPARE_REQUESTED"
    transaction = store.read()
    assert transaction["target_image_ref"] == target["target_image_ref"]
    assert transaction["target_archive_sha256"] == target["target_archive_sha256"]
    assert transaction["target_archive_size"] == size
    assert transaction["authorization_consumed"] is False
