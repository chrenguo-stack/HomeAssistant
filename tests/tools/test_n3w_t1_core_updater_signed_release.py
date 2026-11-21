from __future__ import annotations

import base64
import copy
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import n3w_t1_core_updater_signed_release as signing
from n3w_t1_core_stack_release import make_release, release_material
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
    after["components"]["homeassistant"] = {
        "image": target["target_image_ref"], "platform": "linux/arm64",
        "identity": {"kind": "tar_sha256", "sha256": target["target_archive_sha256"]},
    }
    after = make_release(after)
    release = {
        "schema": signing.DISTRIBUTION_SCHEMA, "expires_at_unix": 2_147_483_647,
        "predecessor": before, "target": after, "archive_path": "1.0.1/target.tar",
        "minimum_updater_version": "0.1.0", "required_updater_capabilities": sorted(signing.CHECKER_CAPABILITIES),
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
        getresponse=lambda: SimpleNamespace(status=302),
        close=lambda: None,
    )
    monkeypatch.setattr(signing.http.client, "HTTPSConnection", lambda host, **kwargs: connection)
    with pytest.raises(UpdaterV2Error, match="https_response_invalid"):
        signing._fetch_https("releases.example.test", "/ota/index.json", 4096)
    assert calls == [("GET", "/ota/index.json")]
