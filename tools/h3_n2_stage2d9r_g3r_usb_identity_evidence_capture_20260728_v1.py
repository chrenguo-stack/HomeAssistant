#!/usr/bin/env python3
"""Pure helpers that capture path-sensitive USB evidence before any comparison."""
from __future__ import annotations

from typing import Any, Mapping

import h3_n2_stage2d9r_g3r_usb_identity_evidence_repair_contract_20260728_v1 as contract


def identity_mapping(identity: Any) -> dict[str, Any]:
    return {
        "device": str(identity.device),
        "vid": int(identity.vid),
        "pid": int(identity.pid),
        "serial_number": str(identity.serial_number),
        "manufacturer": str(identity.manufacturer),
        "product": str(identity.product),
        "location": str(identity.location),
        "hwid": str(identity.hwid),
    }


def capture_transport(identity: Any) -> dict[str, Any]:
    return contract.build_transport_evidence(identity_mapping(identity))


def build_complete_evidence(
    *,
    identity: Any,
    chip_stdout: str,
    flash_stdout: str,
    test_partition_sha256: str,
    test_partition_size: int,
) -> dict[str, Any]:
    transport = capture_transport(identity)
    chip_mac_sha256, chip_mac_count = contract.extract_chip_mac_sha256(chip_stdout)
    return contract.build_path_neutral_baseline_evidence(
        transport_evidence=transport,
        chip_id_output_sha256=contract.sha256_text(chip_stdout),
        flash_id_output_sha256=contract.sha256_text(flash_stdout),
        test_partition_sha256=test_partition_sha256,
        test_partition_size=test_partition_size,
        chip_mac_sha256=chip_mac_sha256,
        chip_mac_candidate_count=chip_mac_count,
    )


def transport_path_changed(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    for key in ("device_path_sha256", "location_sha256", "hwid_sha256"):
        if left.get(key) != right.get(key):
            return True
    return False


def path_neutral_identity_matches(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return left.get("path_neutral_usb_identity_sha256") == right.get("path_neutral_usb_identity_sha256")
