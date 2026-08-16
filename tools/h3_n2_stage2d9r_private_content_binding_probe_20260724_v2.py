#!/usr/bin/env python3
"""Corrected Stage 2D-9R private-content binding verifier.

This version preserves the reviewed V1 contract while correcting the broker
certificate binding to compare the public descriptor's DER certificate digest,
not the raw PEM file digest. It also binds the permanently consumed U1-03
failure marker before any future private-content read.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import importlib.util

_BASE_PATH = Path(__file__).with_name(
    "h3_n2_stage2d9r_private_content_binding_probe_20260724_v1.py"
)
_BASE_SPEC = importlib.util.spec_from_file_location("stage2d9r_private_content_binding_v1", _BASE_PATH)
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


def certificate_der_sha256(openssl: Path, certificate: Path) -> str:
    """Return the canonical DER certificate SHA-256 used by public descriptors."""
    return _base.sha256_bytes(
        _base.run_openssl(
            openssl,
            ["x509", "-in", str(certificate), "-outform", "DER"],
        )
    )


def preauthorization_state(home: Path, binding: dict[str, Any]) -> dict[str, Any]:
    state = _original_preauthorization_state(home)
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
    private_descriptor = _base.exact_json(
        root / "private-custody-descriptor.json",
        EXPECTED["pki_private_descriptor_sha256"],
    )
    public_descriptor = _base.exact_json(
        root / "public-descriptor.redacted.json",
        EXPECTED["pki_public_descriptor_sha256"],
    )
    public_config = _base.exact_json(
        root / "isolated-broker-public-config.redacted.json",
        EXPECTED["pki_public_config_sha256"],
    )
    materials = private_descriptor.get("materials")
    _base.require(isinstance(materials, dict), "PKI_MATERIALS_INVALID")
    observed: dict[str, dict[str, str]] = {}
    material_bytes: dict[str, bytes] = {}
    for name, metadata in materials.items():
        _base.require(
            isinstance(name, str) and isinstance(metadata, dict),
            "PKI_MATERIAL_METADATA_INVALID",
        )
        relative = metadata.get("relative_path")
        _base.require(
            isinstance(relative, str)
            and "/" not in relative
            and relative not in ("", ".", ".."),
            "PKI_MATERIAL_PATH_INVALID",
        )
        path = root / relative
        _base.require(
            path.is_file() and not path.is_symlink(),
            "PKI_MATERIAL_FILE_INVALID",
        )
        _base.require(
            _base.file_mode(path) == "0600" and metadata.get("mode") == "0600",
            "PKI_MATERIAL_MODE_MISMATCH",
        )
        raw = path.read_bytes()
        digest = _base.sha256_bytes(raw)
        _base.require(metadata.get("sha256") == digest, "PKI_MATERIAL_DIGEST_MISMATCH")
        observed[name] = {"relative_path": relative, "mode": "0600", "sha256": digest}
        material_bytes[name] = raw

    package_sha = _base.material_set_digest(observed)
    _base.require(package_sha == EXPECTED["pki_package_sha256"], "PKI_PACKAGE_DIGEST_MISMATCH")
    _base.require(
        private_descriptor["package_sha256"] == package_sha,
        "PKI_PRIVATE_PACKAGE_BINDING_MISMATCH",
    )
    _base.require(
        public_descriptor["public_material"]["private_package_sha256"] == package_sha,
        "PKI_PUBLIC_PACKAGE_BINDING_MISMATCH",
    )

    root_key = root / materials["root_ca_private_key"]["relative_path"]
    root_cert = root / materials["root_ca_certificate"]["relative_path"]
    broker_key = root / materials["broker_private_key"]["relative_path"]
    broker_cert = root / materials["broker_certificate"]["relative_path"]
    fullchain = root / materials["broker_full_chain"]["relative_path"]
    passwd = root / materials["mosquitto_password_file"]["relative_path"]
    config = root / materials["isolated_broker_configuration"]["relative_path"]
    acl = root / materials["isolated_broker_acl"]["relative_path"]

    _base.require(
        _base.sha256_file(root_cert) == EXPECTED["ca_pem_sha256"],
        "CA_PEM_DIGEST_MISMATCH",
    )
    _base.require(
        certificate_der_sha256(openssl, broker_cert)
        == EXPECTED["broker_certificate_sha256"],
        "BROKER_CERTIFICATE_DER_DIGEST_MISMATCH",
    )
    root_key_spki = _base.sha256_bytes(_base.key_public_der(openssl, root_key))
    root_cert_spki = _base.sha256_bytes(_base.cert_public_der(openssl, root_cert))
    broker_key_spki = _base.sha256_bytes(_base.key_public_der(openssl, broker_key))
    broker_cert_spki = _base.sha256_bytes(_base.cert_public_der(openssl, broker_cert))
    _base.require(root_key_spki == root_cert_spki, "ROOT_CA_PRIVATE_KEY_MISMATCH")
    _base.require(broker_key_spki == broker_cert_spki, "BROKER_PRIVATE_KEY_MISMATCH")
    _base.require(
        broker_cert_spki == EXPECTED["broker_spki_sha256"],
        "BROKER_SPKI_PUBLIC_BINDING_MISMATCH",
    )
    _base.run_openssl(openssl, ["verify", "-CAfile", str(root_cert), str(broker_cert)])
    _base.run_openssl(
        openssl,
        ["x509", "-in", str(broker_cert), "-checkhost", EXPECTED["broker_host"], "-noout"],
    )
    _base.require(
        fullchain.read_bytes() == broker_cert.read_bytes() + root_cert.read_bytes(),
        "FULLCHAIN_CONTENT_MISMATCH",
    )

    password_bytes = passwd.read_bytes()
    _base.require(len(password_bytes.splitlines()) == 1, "PASSWORD_DATABASE_LINE_COUNT_INVALID")
    line = password_bytes.decode("ascii").strip()
    _base.require(
        line.startswith(EXPECTED["mqtt_username"] + ":$7$"),
        "PASSWORD_DATABASE_FORMAT_INVALID",
    )
    _base.require(
        EXPECTED["mqtt_password_sha256"] == public_config["mqtt_password_sha256"],
        "PUBLIC_PASSWORD_DIGEST_BINDING_MISMATCH",
    )

    config_text = config.read_text(encoding="utf-8")
    required_lines = {
        "per_listener_settings true",
        "listener 8883 127.0.0.1",
        "protocol mqtt",
        "allow_anonymous false",
        f"password_file {passwd}",
        f"acl_file {acl}",
        f"cafile {root_cert}",
        f"certfile {broker_cert}",
        f"keyfile {broker_key}",
        "require_certificate false",
        "tls_version tlsv1.2",
        "persistence false",
    }
    _base.require(
        required_lines.issubset(set(config_text.splitlines())),
        "BROKER_CONFIG_BINDING_MISMATCH",
    )
    acl_text = acl.read_text(encoding="utf-8")
    _base.require(
        acl_text
        == "user stage2d9r-test\n"
        "topic readwrite gh-test/gh-test-run-tlsvalid01/node/#\n",
        "BROKER_ACL_BINDING_MISMATCH",
    )
    _base.require(
        public_config["broker_host"] == EXPECTED["broker_host"],
        "PUBLIC_BROKER_HOST_MISMATCH",
    )
    _base.require(
        public_config["broker_port"] == EXPECTED["broker_port"],
        "PUBLIC_BROKER_PORT_MISMATCH",
    )
    _base.require(
        public_descriptor["public_material"]["candidate_digest_sha256"]
        == EXPECTED["candidate_digest_sha256"],
        "CANDIDATE_DIGEST_MISMATCH",
    )
    auth = (home.resolve(strict=True) / _base.AUTH_RELATIVE).resolve(strict=False)
    consumed = _base.exact_marker(
        auth / "U1-H3N2-STAGE2D9R-PRIVATE-PKI-20260723-01.consumed.json",
        EXPECTED["pki_marker_sha256"],
        "U1-H3N2-STAGE2D9R-PRIVATE-PKI-20260723-01",
        "CONSUMED",
    )
    private_record = private_descriptor["authorization"]["record_sha256"]
    _base.require(
        isinstance(private_record, str) and _base.HEX64.fullmatch(private_record) is not None,
        "PKI_PRIVATE_RECORD_SHAPE_INVALID",
    )
    _base.require(
        consumed["record_sha256"] == private_record,
        "PKI_RECORD_CROSS_BINDING_MISMATCH",
    )
    material_bytes.clear()
    password_bytes = b""
    return {
        "private_package_sha256": package_sha,
        "ca_pem_sha256": EXPECTED["ca_pem_sha256"],
        "broker_certificate_sha256": EXPECTED["broker_certificate_sha256"],
        "broker_spki_sha256": EXPECTED["broker_spki_sha256"],
        "candidate_digest_sha256": EXPECTED["candidate_digest_sha256"],
        "root_ca_private_key_matches_certificate": True,
        "broker_private_key_matches_certificate": True,
        "certificate_chain_valid": True,
        "hostname_valid": True,
        "password_database_hash_format_valid": True,
        "authorization_record_cross_binding_valid": True,
        "raw_private_keys_included": False,
        "password_database_content_included": False,
        "raw_mqtt_password_included": False,
    }


_base.preauthorization_state = preauthorization_state
_base.pki_deep_binding = pki_deep_binding


def main() -> int:
    return _base.main()


if __name__ == "__main__":
    raise SystemExit(main())
