from __future__ import annotations

import json
import re
from pathlib import Path

import n3w_t1_core_updater_ha_recovery_encoding as encoding


ROOT = Path(__file__).resolve().parents[2]
RECORD = (
    ROOT
    / "infra/n3w-t1/upgrades/homeassistant-2026.10.0-predecessor-recovery-qualification.json"
)
POLICY = (
    ROOT
    / "infra/n3w-t1/upgrades/homeassistant-2026.10.4-host-release-policy.json"
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def record() -> dict:
    return json.loads(RECORD.read_text(encoding="utf-8"))


def test_record_binds_exact_qualification_source_and_github_artifact() -> None:
    document = record()
    qualification = document["qualification"]

    assert document["schema"] == (
        "gh.n3w-t1-ha-predecessor-recovery-qualification-record/1"
    )
    assert qualification["source_head"] == (
        "bd71f5eeaac215f7108d64aebe268a49b3758573"
    )
    assert qualification["workflow_run_id"] == 42558486089
    assert qualification["workflow_job_id"] == 128969470757
    assert qualification["workflow_result"] == "success"
    assert qualification["artifact_id"] == 13648383855
    assert qualification["artifact_name"] == (
        "n3w-ha-predecessor-recovery-qualification-"
        "bd71f5eeaac215f7108d64aebe268a49b3758573"
    )
    assert qualification["artifact_zip_digest"] == (
        "sha256:680e5fc7cc19d0763b61b9b55842e9427cdf6bff3d8fc7ee9217f80a456e72ab"
    )
    assert SHA256.fullmatch(qualification["evidence_json_sha256"])
    assert SHA256.fullmatch(qualification["evidence_json_canonical_sha256"])


def test_record_binds_exact_predecessor_and_product_encoder() -> None:
    document = record()

    assert document["predecessor"] == {
        "upstream_repository": "ghcr.io/home-assistant/home-assistant",
        "upstream_tag": "2026.10.0",
        "arm64_manifest_digest": (
            "sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4"
        ),
        "image_ref": "local/n3w-homeassistant:2026.10.0-0c73235a",
        "image_id": (
            "sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879"
        ),
    }
    assert document["encoding"]["schema"] == encoding.ENCODING_SCHEMA
    assert document["encoding"]["docker_save_argv"] == list(encoding.docker_save_argv())
    assert document["encoding"]["gzip_argv"] == list(encoding.gzip_argv())


def test_record_measurement_and_budget_are_fail_closed_and_recomputable() -> None:
    document = record()
    measurement = document["measurement"]
    budget = document["budget"]
    samples = measurement["samples"]

    assert measurement["method"] == "max_of_two_exact_product_exports"
    assert len(samples) == 2
    assert all(SHA256.fullmatch(sample["archive_sha256"]) for sample in samples)
    assert all(
        SHA256.fullmatch(sample["portable_identity_sha256"]) for sample in samples
    )

    sample_sizes = tuple(sample["archive_size_bytes"] for sample in samples)
    measured = encoding.qualification_measured_export_bytes(sample_sizes)

    assert measured == max(sample_sizes)
    assert measured == 835454845
    assert measurement["selected_sample_index"] == 2
    assert measurement["measured_export_bytes"] == measured
    assert budget["ratio_percent"] == encoding.RECOVERY_MARGIN_RATIO_PERCENT
    assert budget["round_up_quantum_bytes"] == encoding.ROUND_UP_QUANTUM_BYTES
    assert budget["ratio_bound_bytes"] == (measured * 110 + 99) // 100
    assert budget["additive_bound_bytes"] == (
        measured + encoding.ROUND_UP_QUANTUM_BYTES
    )
    assert budget["predecessor_recovery_budget_bytes"] == (
        encoding.predecessor_recovery_budget_bytes(measured)
    )
    assert budget["predecessor_recovery_budget_bytes"] == 1342177280


def test_record_requires_double_identity_and_load_verification() -> None:
    verification = record()["verification"]

    assert verification == {
        "portable_identity_equivalent": True,
        "docker_load_smoke_pass_for_each_sample": True,
        "exact_product_export_sample_count": 2,
        "independent_budget_recalculation_pass": True,
    }


def test_production_policy_is_cross_bound_to_qualification_record() -> None:
    qualification = record()
    policy = json.loads(POLICY.read_text(encoding="utf-8"))

    assert policy["schema"] == "gh.n3w-t1-ha-ota-host-release-policy/2"
    assert policy["release_identity"] == "homeassistant-2026.10.4"
    assert policy["target_archive_size_bytes"] == 835_309_535
    assert policy["target_archive_sha256"] == (
        "eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973"
    )
    assert policy["expected_predecessor_image_ref"] == (
        qualification["predecessor"]["image_ref"]
    )
    assert policy["predecessor_recovery_budget_bytes"] == (
        qualification["budget"]["predecessor_recovery_budget_bytes"]
    )
    assert policy["capacity_policy"] == encoding_capacity_policy_document()


def encoding_capacity_policy_document() -> dict:
    from n3w_t1_core_updater_ha_capacity import CapacityPolicy

    return CapacityPolicy.frozen().to_document()
