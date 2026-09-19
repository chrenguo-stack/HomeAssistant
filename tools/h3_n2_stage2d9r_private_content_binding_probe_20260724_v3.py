#!/usr/bin/env python3
"""Corrected one-shot Stage 2D-9R private-content binding verifier.

This version preserves the reviewed V1 execution contract while correcting the
broker certificate comparison to use the public descriptor's canonical DER
certificate digest. It also requires the permanently consumed U1-03 failure
marker before any future private-content read.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_BASE_PATH = Path(__file__).with_name(
    "h3_n2_stage2d9r_private_content_binding_probe_20260724_v1.py"
)
_BASE_SPEC = importlib.util.spec_from_file_location(
    "stage2d9r_private_content_binding_v1_for_v3", _BASE_PATH
)
if _BASE_SPEC is None or _BASE_SPEC.loader is None:
    raise RuntimeError("unable to load V1 verifier")
_base = importlib.util.module_from_spec(_BASE_SPEC)
_BASE_SPEC.loader.exec_module(_base)

for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)

EXPECTED = dict(_base.EXPECTED)
EXPECTED["u1_03_record_sha256"] = (
    "38edfa6ba1d42aea5d0d6d57f0a3157209be3afc6873f957d92d0156fceae0a2"
)
_base.EXPECTED = EXPECTED

_original_preauthorization_state = _base.preauthorization_state
_original_pki_deep_binding = _base.pki_deep_binding
_original_probe = _base.probe
_original_execute = _base.execute
_active_binding: dict[str, Any] | None = None


def certificate_der_sha256(openssl: Path, certificate: Path) -> str:
    """Return the canonical DER certificate digest used by public descriptors."""
    return _base.sha256_bytes(
        _base.run_openssl(
            openssl,
            ["x509", "-in", str(certificate), "-outform", "DER"],
        )
    )


def preauthorization_state(home: Path) -> dict[str, Any]:
    state = _original_preauthorization_state(home)
    binding = _active_binding
    _base.require(isinstance(binding, dict), "ACTIVE_BINDING_MISSING")
    failed_marker_sha = binding.get("u1_03_failed_marker_sha256")
    _base.require(
        isinstance(failed_marker_sha, str)
        and _base.HEX64.fullmatch(failed_marker_sha) is not None,
        "U1_03_FAILED_MARKER_BINDING_MISSING",
    )
    auth = (home.resolve(strict=True) / _base.AUTH_RELATIVE).resolve(strict=False)
    failed = _base.exact_marker(
        auth
        / "U1-H3N2-STAGE2D9R-PRIVATE-CONTENT-BINDING-20260724-03.consumed.json",
        failed_marker_sha,
        "U1-H3N2-STAGE2D9R-PRIVATE-CONTENT-BINDING-20260724-03",
        "CONSUMED_FAILED",
    )
    _base.require(
        failed.get("record_sha256") == EXPECTED["u1_03_record_sha256"],
        "U1_03_RECORD_CROSS_BINDING_MISMATCH",
    )
    _base.require(
        failed.get("failure_code") == "BROKER_CERTIFICATE_DIGEST_MISMATCH",
        "U1_03_FAILURE_CODE_MISMATCH",
    )
    _base.require(failed.get("result_sha256") is None, "U1_03_RESULT_SHAPE_INVALID")
    return {
        **state,
        "u1_03_failed_marker_bound": True,
        "u1_03_failure_code_bound": True,
    }


def pki_deep_binding(home: Path, openssl: Path) -> dict[str, Any]:
    root = _base.private_root(home, _base.PKI_ROOT_RELATIVE, EXPECTED["pki_root_digest"])
    descriptor = _base.exact_json(
        root / "private-custody-descriptor.json",
        EXPECTED["pki_private_descriptor_sha256"],
    )
    materials = descriptor.get("materials")
    _base.require(isinstance(materials, dict), "PKI_MATERIALS_INVALID")
    broker_metadata = materials.get("broker_certificate")
    _base.require(isinstance(broker_metadata, dict), "BROKER_CERTIFICATE_METADATA_INVALID")
    relative = broker_metadata.get("relative_path")
    _base.require(
        isinstance(relative, str)
        and "/" not in relative
        and relative not in ("", ".", ".."),
        "BROKER_CERTIFICATE_PATH_INVALID",
    )
    broker_cert = (root / relative).resolve(strict=True)
    original_sha256_file = _base.sha256_file

    def corrected_sha256_file(path: Path) -> str:
        resolved = Path(path).resolve(strict=True)
        if resolved == broker_cert:
            return certificate_der_sha256(openssl, resolved)
        return original_sha256_file(resolved)

    _base.sha256_file = corrected_sha256_file
    try:
        return _original_pki_deep_binding(home, openssl)
    finally:
        _base.sha256_file = original_sha256_file


def probe(binding: dict[str, Any], home: Path, openssl: Path) -> dict[str, Any]:
    global _active_binding
    _active_binding = binding
    try:
        return _original_probe(binding, home, openssl)
    finally:
        _active_binding = None


def execute(
    binding: dict[str, Any],
    authorization_path: Path,
    home: Path,
    openssl: Path,
) -> dict[str, Any]:
    global _active_binding
    _active_binding = binding
    try:
        return _original_execute(binding, authorization_path, home, openssl)
    finally:
        _active_binding = None


_base.EXPECTED = EXPECTED
_base.preauthorization_state = preauthorization_state
_base.pki_deep_binding = pki_deep_binding
_base.probe = probe
_base.execute = execute
_base.__file__ = __file__


if __name__ == "__main__":
    raise SystemExit(_base.main())
