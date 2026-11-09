from __future__ import annotations

import json

import pytest

import n3w_t1_core_updater_ha_recovery_encoding as encoding


def test_exact_predecessor_identity_is_frozen() -> None:
    assert encoding.PREDECESSOR_UPSTREAM_TAG == "2026.10.0"
    assert encoding.PREDECESSOR_ARM64_MANIFEST_DIGEST == (
        "sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4"
    )
    assert encoding.PREDECESSOR_IMAGE_REF == (
        "local/n3w-homeassistant:2026.10.0-0c73235a"
    )
    assert encoding.PREDECESSOR_IMAGE_ID == (
        "sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879"
    )


def test_exact_recovery_encoder_is_docker_save_plus_deterministic_gzip() -> None:
    assert encoding.docker_save_argv() == (
        "docker",
        "save",
        encoding.PREDECESSOR_IMAGE_REF,
    )
    assert encoding.gzip_argv() == ("gzip", "-1", "-n", "-c")


def test_wrong_predecessor_ref_is_rejected() -> None:
    with pytest.raises(
        encoding.RecoveryEncodingError,
        match="predecessor_image_ref_mismatch",
    ):
        encoding.docker_save_argv("local/n3w-homeassistant:wrong")


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "1"])
def test_budget_rejects_invalid_measurements(value: object) -> None:
    with pytest.raises(encoding.RecoveryEncodingError):
        encoding.predecessor_recovery_budget_bytes(value)  # type: ignore[arg-type]


def test_budget_formula_uses_additive_or_ratio_bound_and_256_mib_rounding() -> None:
    measured = 1_000_000_000
    ratio_bound = (measured * 110 + 99) // 100
    additive_bound = measured + 256 * 1024 * 1024
    expected_raw = max(ratio_bound, additive_bound)
    quantum = 256 * 1024 * 1024
    expected = ((expected_raw + quantum - 1) // quantum) * quantum
    assert encoding.predecessor_recovery_budget_bytes(measured) == expected


def test_qualification_evidence_binds_encoder_and_budget() -> None:
    evidence = encoding.QualificationEvidence(
        source_head="a" * 40,
        measured_export_bytes=1_234_567_890,
        archive_sha256="b" * 64,
        portable_identity_sha256="c" * 64,
    ).to_dict()

    assert evidence["schema"] == encoding.QUALIFICATION_SCHEMA
    assert evidence["predecessor"]["image_ref"] == encoding.PREDECESSOR_IMAGE_REF
    assert evidence["encoding"]["gzip_argv"] == ["gzip", "-1", "-n", "-c"]
    assert evidence["measurement"]["measured_export_bytes"] == 1_234_567_890
    assert evidence["budget"]["predecessor_recovery_budget_bytes"] == (
        encoding.predecessor_recovery_budget_bytes(1_234_567_890)
    )

    canonical = json.dumps(
        evidence,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    assert len(encoding.canonical_sha256(evidence)) == 64
    assert canonical
