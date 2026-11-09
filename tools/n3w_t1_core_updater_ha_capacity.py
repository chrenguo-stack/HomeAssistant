from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from n3w_t1_core_updater_v2_common import UpdaterV2Error


CAPACITY_POLICY_SCHEMA = "gh.n3w-t1-ha-usb-capacity-policy/1"
USB_MEASURED_USABLE_FLOOR_BYTES = 14 * 1024**3
ROUND_UP_QUANTUM_BYTES = 256 * 1024**2
HA_DATA_BACKUP_MIN_BUDGET_BYTES = 1024**3
HA_DATA_GROWTH_MARGIN_RATIO_PPM = 250_000
HA_DATA_GROWTH_MARGIN_FLOOR_BYTES = 512 * 1024**2
TRANSACTION_WORKING_FLOOR_BYTES = 512 * 1024**2
TRANSACTION_WORKING_TARGET_RATIO_PPM = 100_000
REMOVABLE_RESERVE_FLOOR_BYTES = 1024**3
REMOVABLE_RESERVE_RATIO_PPM = 100_000
RECOMMENDED_NOMINAL_USB_SIZES_GB = (32, 64, 128, 256, 512, 1024)
NOMINAL_USABLE_GUARD_PPM = 900_000
PPM_DENOMINATOR = 1_000_000
MAX_SAFE_BYTES = (1 << 63) - 1


def _positive_int(value: Any, reason: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
        or value > MAX_SAFE_BYTES
    ):
        raise UpdaterV2Error(reason)
    return value


def _nonnegative_int(value: Any, reason: str) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > MAX_SAFE_BYTES
    ):
        raise UpdaterV2Error(reason)
    return value


def _checked_add(*values: int) -> int:
    result = 0
    for value in values:
        _nonnegative_int(value, "ha_capacity_value_invalid")
        result += value
        if result > MAX_SAFE_BYTES:
            raise UpdaterV2Error("ha_capacity_overflow")
    return result


def ceil_ratio_ppm(value: int, ratio_ppm: int) -> int:
    value = _nonnegative_int(value, "ha_capacity_value_invalid")
    ratio_ppm = _nonnegative_int(ratio_ppm, "ha_capacity_ratio_invalid")
    if ratio_ppm > PPM_DENOMINATOR:
        raise UpdaterV2Error("ha_capacity_ratio_invalid")
    if value and ratio_ppm and value > MAX_SAFE_BYTES // ratio_ppm:
        raise UpdaterV2Error("ha_capacity_overflow")
    return (value * ratio_ppm + PPM_DENOMINATOR - 1) // PPM_DENOMINATOR


def round_up(value: int, quantum: int = ROUND_UP_QUANTUM_BYTES) -> int:
    value = _positive_int(value, "ha_capacity_value_invalid")
    quantum = _positive_int(quantum, "ha_capacity_quantum_invalid")
    if value > MAX_SAFE_BYTES - (quantum - 1):
        raise UpdaterV2Error("ha_capacity_overflow")
    result = ((value + quantum - 1) // quantum) * quantum
    if result > MAX_SAFE_BYTES:
        raise UpdaterV2Error("ha_capacity_overflow")
    return result


@dataclass(frozen=True, slots=True)
class CapacityPolicy:
    usb_measured_usable_floor_bytes: int
    round_up_quantum_bytes: int
    ha_data_backup_min_budget_bytes: int
    ha_data_growth_margin_ratio_ppm: int
    ha_data_growth_margin_floor_bytes: int
    transaction_working_floor_bytes: int
    transaction_working_target_ratio_ppm: int
    removable_reserve_floor_bytes: int
    removable_reserve_ratio_ppm: int
    recommended_nominal_usb_sizes_gb: tuple[int, ...]
    nominal_usable_guard_ppm: int

    @classmethod
    def frozen(cls) -> "CapacityPolicy":
        return cls(
            usb_measured_usable_floor_bytes=USB_MEASURED_USABLE_FLOOR_BYTES,
            round_up_quantum_bytes=ROUND_UP_QUANTUM_BYTES,
            ha_data_backup_min_budget_bytes=HA_DATA_BACKUP_MIN_BUDGET_BYTES,
            ha_data_growth_margin_ratio_ppm=HA_DATA_GROWTH_MARGIN_RATIO_PPM,
            ha_data_growth_margin_floor_bytes=HA_DATA_GROWTH_MARGIN_FLOOR_BYTES,
            transaction_working_floor_bytes=TRANSACTION_WORKING_FLOOR_BYTES,
            transaction_working_target_ratio_ppm=TRANSACTION_WORKING_TARGET_RATIO_PPM,
            removable_reserve_floor_bytes=REMOVABLE_RESERVE_FLOOR_BYTES,
            removable_reserve_ratio_ppm=REMOVABLE_RESERVE_RATIO_PPM,
            recommended_nominal_usb_sizes_gb=RECOMMENDED_NOMINAL_USB_SIZES_GB,
            nominal_usable_guard_ppm=NOMINAL_USABLE_GUARD_PPM,
        )

    @classmethod
    def from_document(cls, value: Any) -> "CapacityPolicy":
        if not isinstance(value, dict):
            raise UpdaterV2Error("ha_prepare_capacity_policy_invalid")
        expected = {
            "usb_measured_usable_floor_bytes",
            "round_up_quantum_bytes",
            "ha_data_backup_min_budget_bytes",
            "ha_data_growth_margin_ratio_ppm",
            "ha_data_growth_margin_floor_bytes",
            "transaction_working_floor_bytes",
            "transaction_working_target_ratio_ppm",
            "removable_reserve_floor_bytes",
            "removable_reserve_ratio_ppm",
            "recommended_nominal_usb_sizes_gb",
            "nominal_usable_guard_ppm",
        }
        if set(value) != expected:
            raise UpdaterV2Error("ha_prepare_capacity_policy_invalid")
        tiers = value["recommended_nominal_usb_sizes_gb"]
        if not isinstance(tiers, list) or any(
            isinstance(item, bool) or not isinstance(item, int) for item in tiers
        ):
            raise UpdaterV2Error("ha_prepare_capacity_policy_invalid")
        policy = cls(
            usb_measured_usable_floor_bytes=value["usb_measured_usable_floor_bytes"],
            round_up_quantum_bytes=value["round_up_quantum_bytes"],
            ha_data_backup_min_budget_bytes=value["ha_data_backup_min_budget_bytes"],
            ha_data_growth_margin_ratio_ppm=value["ha_data_growth_margin_ratio_ppm"],
            ha_data_growth_margin_floor_bytes=value["ha_data_growth_margin_floor_bytes"],
            transaction_working_floor_bytes=value["transaction_working_floor_bytes"],
            transaction_working_target_ratio_ppm=value[
                "transaction_working_target_ratio_ppm"
            ],
            removable_reserve_floor_bytes=value["removable_reserve_floor_bytes"],
            removable_reserve_ratio_ppm=value["removable_reserve_ratio_ppm"],
            recommended_nominal_usb_sizes_gb=tuple(tiers),
            nominal_usable_guard_ppm=value["nominal_usable_guard_ppm"],
        )
        if policy != cls.frozen():
            raise UpdaterV2Error("ha_prepare_capacity_policy_drift")
        return policy

    def to_document(self) -> dict[str, Any]:
        return {
            "usb_measured_usable_floor_bytes": self.usb_measured_usable_floor_bytes,
            "round_up_quantum_bytes": self.round_up_quantum_bytes,
            "ha_data_backup_min_budget_bytes": self.ha_data_backup_min_budget_bytes,
            "ha_data_growth_margin_ratio_ppm": self.ha_data_growth_margin_ratio_ppm,
            "ha_data_growth_margin_floor_bytes": self.ha_data_growth_margin_floor_bytes,
            "transaction_working_floor_bytes": self.transaction_working_floor_bytes,
            "transaction_working_target_ratio_ppm": (
                self.transaction_working_target_ratio_ppm
            ),
            "removable_reserve_floor_bytes": self.removable_reserve_floor_bytes,
            "removable_reserve_ratio_ppm": self.removable_reserve_ratio_ppm,
            "recommended_nominal_usb_sizes_gb": list(
                self.recommended_nominal_usb_sizes_gb
            ),
            "nominal_usable_guard_ppm": self.nominal_usable_guard_ppm,
        }


@dataclass(frozen=True, slots=True)
class CapacityBreakdown:
    target_artifact_bytes: int
    predecessor_recovery_budget_bytes: int
    ha_data_measured_bytes: int
    ha_data_growth_margin_bytes: int
    ha_data_backup_budget_bytes: int
    transaction_working_budget_bytes: int
    removable_reserve_bytes: int
    usb_required_bytes: int
    recommended_nominal_usb_gb: int

    def snapshot(self, *, calculated_at_unix: int) -> dict[str, int | str]:
        _positive_int(calculated_at_unix, "ha_capacity_timestamp_invalid")
        return {
            "capacity_policy_schema": CAPACITY_POLICY_SCHEMA,
            "target_artifact_bytes": self.target_artifact_bytes,
            "predecessor_recovery_budget_bytes": (
                self.predecessor_recovery_budget_bytes
            ),
            "ha_data_measured_bytes": self.ha_data_measured_bytes,
            "ha_data_growth_margin_bytes": self.ha_data_growth_margin_bytes,
            "ha_data_backup_budget_bytes": self.ha_data_backup_budget_bytes,
            "transaction_working_budget_bytes": self.transaction_working_budget_bytes,
            "removable_reserve_bytes": self.removable_reserve_bytes,
            "usb_required_bytes": self.usb_required_bytes,
            "recommended_nominal_usb_gb": self.recommended_nominal_usb_gb,
            "calculated_at_unix": calculated_at_unix,
        }


def recommended_nominal_usb_gb(
    required_bytes: int,
    policy: CapacityPolicy | None = None,
) -> int:
    policy = policy or CapacityPolicy.frozen()
    required = max(
        _positive_int(required_bytes, "ha_capacity_required_invalid"),
        policy.usb_measured_usable_floor_bytes,
    )
    for tier in policy.recommended_nominal_usb_sizes_gb:
        guarded = (
            tier * 1_000_000_000 * policy.nominal_usable_guard_ppm
        ) // PPM_DENOMINATOR
        if guarded >= required:
            return tier
    raise UpdaterV2Error("ha_capacity_recommendation_unsupported")


def compute_capacity(
    *,
    target_artifact_bytes: int,
    predecessor_recovery_budget_bytes: int,
    ha_data_measured_bytes: int,
    policy: CapacityPolicy | None = None,
) -> CapacityBreakdown:
    policy = policy or CapacityPolicy.frozen()
    target = _positive_int(target_artifact_bytes, "ha_capacity_target_invalid")
    predecessor = _positive_int(
        predecessor_recovery_budget_bytes,
        "ha_capacity_predecessor_invalid",
    )
    measured = _nonnegative_int(
        ha_data_measured_bytes,
        "ha_capacity_ha_data_invalid",
    )

    growth = max(
        policy.ha_data_growth_margin_floor_bytes,
        ceil_ratio_ppm(measured, policy.ha_data_growth_margin_ratio_ppm),
    )
    backup = round_up(
        max(
            policy.ha_data_backup_min_budget_bytes,
            _checked_add(measured, growth),
        ),
        policy.round_up_quantum_bytes,
    )
    working = round_up(
        max(
            policy.transaction_working_floor_bytes,
            ceil_ratio_ppm(
                target,
                policy.transaction_working_target_ratio_ppm,
            ),
        ),
        policy.round_up_quantum_bytes,
    )
    base = _checked_add(target, predecessor, backup, working)
    reserve = round_up(
        max(
            policy.removable_reserve_floor_bytes,
            ceil_ratio_ppm(base, policy.removable_reserve_ratio_ppm),
        ),
        policy.round_up_quantum_bytes,
    )
    required = _checked_add(base, reserve)
    recommendation = recommended_nominal_usb_gb(required, policy)

    return CapacityBreakdown(
        target_artifact_bytes=target,
        predecessor_recovery_budget_bytes=predecessor,
        ha_data_measured_bytes=measured,
        ha_data_growth_margin_bytes=growth,
        ha_data_backup_budget_bytes=backup,
        transaction_working_budget_bytes=working,
        removable_reserve_bytes=reserve,
        usb_required_bytes=required,
        recommended_nominal_usb_gb=recommendation,
    )


def candidate_raw_capacity_plausible(
    raw_capacity_bytes: int,
    required_bytes: int,
    policy: CapacityPolicy | None = None,
) -> bool:
    policy = policy or CapacityPolicy.frozen()
    raw = _positive_int(raw_capacity_bytes, "usb_raw_capacity_invalid")
    required = _positive_int(required_bytes, "ha_capacity_required_invalid")
    return raw >= max(required, policy.usb_measured_usable_floor_bytes)
