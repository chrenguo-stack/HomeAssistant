"""Verify the signed engineering distribution contract for a HA-only Stack release."""

from __future__ import annotations

import base64
import http.client
import json
import os
import re
import ssl
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from n3w_t1_core_stack_release import StackReleaseError, build_upgrade_plan, parse_semver
from n3w_t1_core_updater_ha_ipc import candidate_admission, read_local_release_input, reject_duplicate_fields
from n3w_t1_core_updater_v2_common import SHA256, UpdaterV2Error, canonical, sha256_bytes

TRUST_SCHEMA = "gh.n3w-t1-ota-release-trust/1"
INDEX_SCHEMA = "gh.n3w-t1-ota-release-index/1"
DISTRIBUTION_SCHEMA = "gh.n3w-t1-ota-ha-release-distribution/1"
CHECKER_VERSION = "0.1.0"
CHECKER_CAPABILITIES = frozenset({"STACK_RELEASE_V1", "HA_IMAGE_UPGRADE_V1", "STACK_ROLLBACK_V1"})
INDEX_LIMIT = 16 * 1024
RELEASE_LIMIT = 128 * 1024
ED25519_SPKI_PREFIX = bytes.fromhex("302a300506032b6570032100")
_PATH_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")
_HOST = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?")


def _object(raw: bytes, schema: str, fields: set[str]) -> dict[str, Any]:
    try:
        document = json.loads(raw, object_pairs_hook=reject_duplicate_fields)
    except ValueError as error:
        raise UpdaterV2Error("signed_release_json_invalid") from error
    if not isinstance(document, dict) or document.keys() != fields | {"schema"} or document["schema"] != schema:
        raise UpdaterV2Error("signed_release_document_invalid")
    return document


def _relative_path(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 512 or not all(
        _PATH_SEGMENT.fullmatch(segment) for segment in value.split("/")
    ):
        raise UpdaterV2Error("signed_release_path_invalid")
    return value


def _sha256(value: Any) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise UpdaterV2Error("signed_release_digest_invalid")
    return value


def _expires(value: Any) -> int:
    if type(value) is not int or value <= time.time():
        raise UpdaterV2Error("signed_release_expired")
    return value


def _fetch_https(host: str, path: str, limit: int) -> bytes:
    connection = http.client.HTTPSConnection(host, timeout=10, context=ssl.create_default_context())
    try:
        connection.request("GET", path, headers={"Accept-Encoding": "identity"})
        response = connection.getresponse()
        if response.status != 200 or response.getheader("Content-Encoding", "identity").lower() != "identity":
            raise UpdaterV2Error("signed_release_https_response_invalid")
        return response.read(limit + 1)
    except (OSError, http.client.HTTPException) as error:
        raise UpdaterV2Error("signed_release_https_unavailable") from error
    finally:
        connection.close()


def _verify_signature(key: bytes, raw: bytes, signature: bytes) -> None:
    if len(signature) != 64:
        raise UpdaterV2Error("signed_release_signature_invalid")
    with tempfile.TemporaryDirectory(prefix="n3w-release-verify-") as folder:
        directory = Path(folder)
        public, payload, signed = (directory / name for name in ("key.der", "payload", "signature"))
        for path, value in ((public, key), (payload, raw), (signed, signature)):
            path.write_bytes(value)
        result = subprocess.run(
            ("/usr/bin/openssl", "pkeyutl", "-verify", "-pubin", "-keyform", "DER",
             "-inkey", str(public), "-rawin", "-in", str(payload), "-sigfile", str(signed)),
            env={"PATH": os.defpath}, capture_output=True, timeout=10,
        )
    if result.returncode != 0:
        raise UpdaterV2Error("signed_release_signature_invalid")


def check_signed_release(
    trust_policy: Path, *, fetch: Callable[[str, str, int], bytes] = _fetch_https,
) -> dict[str, object]:
    policy = _object(read_local_release_input(trust_policy, limit=4096, private=False), TRUST_SCHEMA, {
        "base_url", "minimum_index_sequence", "public_key_der_base64",
    })
    base = policy["base_url"]
    if not isinstance(base, str) or re.fullmatch(r"https://[A-Za-z0-9.-]+(/[A-Za-z0-9_.\-/]+)?", base) is None:
        raise UpdaterV2Error("signed_release_origin_invalid")
    location = urlsplit(base)
    if _HOST.fullmatch(location.netloc) is None:
        raise UpdaterV2Error("signed_release_origin_invalid")
    prefix = location.path.rstrip("/")
    if prefix:
        _relative_path(prefix[1:])
    minimum = policy["minimum_index_sequence"]
    if type(minimum) is not int or minimum <= 0:
        raise UpdaterV2Error("signed_release_sequence_policy_invalid")
    try:
        key = base64.b64decode(policy["public_key_der_base64"], validate=True)
    except (TypeError, ValueError) as error:
        raise UpdaterV2Error("signed_release_trust_key_invalid") from error
    if len(key) != len(ED25519_SPKI_PREFIX) + 32 or not key.startswith(ED25519_SPKI_PREFIX):
        raise UpdaterV2Error("signed_release_trust_key_invalid")

    def read_signed(name: str, limit: int) -> bytes:
        path = f"{prefix}/{_relative_path(name)}"
        raw = fetch(location.netloc, path, limit)
        if not raw or len(raw) > limit:
            raise UpdaterV2Error("signed_release_metadata_size_invalid")
        _verify_signature(key, raw, fetch(location.netloc, path + ".sig", 64))
        return raw

    index = _object(read_signed("index.json", INDEX_LIMIT), INDEX_SCHEMA, {
        "sequence", "expires_at_unix", "release_id", "release_path", "release_sha256",
    })
    expiry = _expires(index["expires_at_unix"])
    sequence = index["sequence"]
    if type(sequence) is not int or sequence < minimum:
        raise UpdaterV2Error("signed_release_index_sequence_too_old")
    release_id = _sha256(index["release_id"])
    expected_digest = _sha256(index["release_sha256"])
    manifest = read_signed(index["release_path"], RELEASE_LIMIT)
    if sha256_bytes(manifest) != expected_digest:
        raise UpdaterV2Error("signed_release_index_manifest_binding_mismatch")
    release = _object(manifest, DISTRIBUTION_SCHEMA, {
        "expires_at_unix", "predecessor", "target", "minimum_updater_version",
        "required_updater_capabilities", "ha_candidate", "archive_path",
    })
    _expires(min(expiry, _expires(release["expires_at_unix"])))
    try:
        plan = build_upgrade_plan(release["predecessor"], release["target"])
        if parse_semver(release["minimum_updater_version"]) > parse_semver(CHECKER_VERSION):
            raise UpdaterV2Error("signed_release_updater_version_insufficient")
    except StackReleaseError as error:
        raise UpdaterV2Error("signed_release_stack_contract_invalid") from error
    capabilities = release["required_updater_capabilities"]
    if (
        not isinstance(capabilities, list) or not all(isinstance(item, str) for item in capabilities)
        or set(capabilities) != CHECKER_CAPABILITIES or len(capabilities) != len(CHECKER_CAPABILITIES)
    ):
        raise UpdaterV2Error("signed_release_updater_capabilities_unsupported")
    if (
        plan["to_release_id"] != release_id
        or plan["component_actions"] != {"manager": "KEEP", "homeassistant": "UPGRADE", "broker": "KEEP"}
        or plan["runtime_contract_action"] != "KEEP"
        or release["target"]["runtime_contract"]["image_binding_modes"]["homeassistant"] != "dynamic"
    ):
        raise UpdaterV2Error("signed_release_stack_scope_mismatch")
    predecessor = release["predecessor"]["components"]["homeassistant"]
    target = release["target"]["components"]["homeassistant"]
    candidate = canonical(release["ha_candidate"])
    # The checker validates the signed declaration. Live materialization must prove the actual predecessor.
    admission = candidate_admission(candidate, {
        "image_ref": predecessor["image"], "image_id": "sha256:" + predecessor["identity"]["sha256"],
        "platform": predecessor["platform"],
    })
    if (
        admission.release_identity != release_id or admission.target_image_ref != target["image"]
        or target["identity"] != {"kind": "tar_sha256", "sha256": admission.target_archive_sha256}
    ):
        raise UpdaterV2Error("signed_release_candidate_binding_mismatch")
    _relative_path(release["archive_path"])
    return {
        "status": "SIGNED_RELEASE_VERIFIED", "index_sequence": sequence, "release_id": release_id,
        "predecessor_release_id": plan["from_release_id"], "signed_manifest_sha256": expected_digest,
        "approved_ha_manifest_sha256": sha256_bytes(candidate), "archive_sha256": admission.target_archive_sha256,
        "archive_size_bytes": admission.target_archive_size,
    }
