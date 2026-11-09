from __future__ import annotations

import pytest

import n3w_t1_core_updater_ha_capacity as capacity
from n3w_t1_core_updater_v2_common import UpdaterV2Error


def frozen_document() -> dict:
    return capacity.CapacityPolicy.frozen().to_document()


def test_frozen_capacity_policy_matches_kf147_design() -> None:
    policy = capacity.CapacityPolicy.from_document(frozen_document())

    assert policy.usb_measured_usable_floor_bytes == 15_032_385_536
    assert policy.round_up_quantum_bytes == 268_435_456
    assert policy.ha_data_backup_min_budget_bytes == 1_073_741_824
    assert policy.ha_data_growth_margin_ratio_ppm == 250_000
    assert policy.ha_data_growth_margin_floor_bytes == 536_870_912
    assert policy.transaction_working_floor_bytes == 536_870_912
    assert policy.transaction_working_target_ratio_ppm == 100_000
    assert policy.removable_reserve_floor_bytes == 1_073_741_824
    assert policy.removable_reserve_ratio_ppm == 100_000
    assert policy.recommended_nominal_usb_sizes_gb == (
        32,
        64,
        128,
        256,
        512,
        1024,
    )
    assert policy.nominal_usable_guard_ppm == 900_000


def test_policy_drift_fails_closed() -> None:
    document = frozen_document()
    document["removable_reserve_ratio_ppm"] = 50_000

    with pytest.raises(UpdaterV2Error, match="ha_prepare_capacity_policy_drift"):
        capacity.CapacityPolicy.from_document(document)


def test_current_transition_capacity_formula_is_exact() -> None:
    result = capacity.compute_capacity(
        target_artifact_bytes=835_309_535,
        predecessor_recovery_budget_bytes=1_342_177_280,
        ha_data_measured_bytes=0,
    )

    assert result.ha_data_growth_margin_bytes == 536_870_912
    assert result.ha_data_backup_budget_bytes == 1_073_741_824
    assert result.transaction_working_budget_bytes == 536_870_912
    base = 835_309_535 + 1_342_177_280 + 1_073_741_824 + 536_870_912
    assert result.removable_reserve_bytes == 1_073_741_824
    assert result.usb_required_bytes == base + 1_073_741_824
    assert result.recommended_nominal_usb_gb == 32


def test_ha_data_growth_uses_25_percent_or_512_mib_floor() -> None:
    small = capacity.compute_capacity(
        target_artifact_bytes=835_309_535,
        predecessor_recovery_budget_bytes=1_342_177_280,
        ha_data_measured_bytes=1,
    )
    large = capacity.compute_capacity(
        target_artifact_bytes=835_309_535,
        predecessor_recovery_budget_bytes=1_342_177_280,
        ha_data_measured_bytes=8 * 1024**3,
    )

    assert small.ha_data_growth_margin_bytes == 512 * 1024**2
    assert large.ha_data_growth_margin_bytes == 2 * 1024**3
    assert large.ha_data_backup_budget_bytes == 10 * 1024**3


def test_working_budget_rounds_to_256_mib() -> None:
    result = capacity.compute_capacity(
        target_artifact_bytes=6 * 1024**3,
        predecessor_recovery_budget_bytes=1,
        ha_data_measured_bytes=0,
    )
    expected_raw = (6 * 1024**3 * 100_000 + 999_999) // 1_000_000
    assert expected_raw > 512 * 1024**2
    assert result.transaction_working_budget_bytes % (256 * 1024**2) == 0
    assert result.transaction_working_budget_bytes >= expected_raw


def test_recommendation_tier_boundaries() -> None:
    policy = capacity.CapacityPolicy.frozen()

    assert capacity.recommended_nominal_usb_gb(28_800_000_000, policy) == 32
    assert capacity.recommended_nominal_usb_gb(28_800_000_001, policy) == 64
    assert capacity.recommended_nominal_usb_gb(57_600_000_000, policy) == 64
    assert capacity.recommended_nominal_usb_gb(57_600_000_001, policy) == 128


def test_14_gib_floor_is_independent_from_recommendation() -> None:
    policy = capacity.CapacityPolicy.frozen()

    assert capacity.candidate_raw_capacity_plausible(
        policy.usb_measured_usable_floor_bytes,
        1,
        policy,
    )
    assert not capacity.candidate_raw_capacity_plausible(
        policy.usb_measured_usable_floor_bytes - 1,
        1,
        policy,
    )
    assert capacity.recommended_nominal_usb_gb(1, policy) == 32


@pytest.mark.parametrize("value", [True, -1, 1.5, "1"])
def test_invalid_dynamic_measurements_fail_closed(value: object) -> None:
    with pytest.raises(UpdaterV2Error):
        capacity.compute_capacity(
            target_artifact_bytes=835_309_535,
            predecessor_recovery_budget_bytes=1_342_177_280,
            ha_data_measured_bytes=value,  # type: ignore[arg-type]
        )


def test_oversize_arithmetic_fails_closed() -> None:
    with pytest.raises(UpdaterV2Error, match="ha_capacity"):
        capacity.compute_capacity(
            target_artifact_bytes=capacity.MAX_SAFE_BYTES,
            predecessor_recovery_budget_bytes=capacity.MAX_SAFE_BYTES,
            ha_data_measured_bytes=0,
        )
