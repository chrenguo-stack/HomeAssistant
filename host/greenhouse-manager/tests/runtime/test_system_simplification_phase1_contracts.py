from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


# Decision A: one-frame periodic telemetry budget.
ESPNOW_V2_PAYLOAD_LIMIT = 1470
CURRENT_DATA_HEADER_BYTES = 54
CURRENT_MAX_CIPHERTEXT_BYTES = 1024
CURRENT_TEST_TELEMETRY_BYTES = 255


def test_periodic_telemetry_fits_frozen_single_frame_budget() -> None:
    assert CURRENT_TEST_TELEMETRY_BYTES + CURRENT_DATA_HEADER_BYTES == 309
    assert CURRENT_MAX_CIPHERTEXT_BYTES + CURRENT_DATA_HEADER_BYTES == 1078
    assert (
        CURRENT_MAX_CIPHERTEXT_BYTES + CURRENT_DATA_HEADER_BYTES
        <= ESPNOW_V2_PAYLOAD_LIMIT
    )


# Decision B: transport-independent canonical freshness.
class FreshnessResult(StrEnum):
    ACCEPT = "accept"
    DUPLICATE = "duplicate"
    STALE_SEQUENCE = "stale_sequence"
    STALE_BOOT = "stale_boot"


@dataclass
class CanonicalCursor:
    boot_session: int | None = None
    seq: int | None = None

    def observe(self, *, boot_session: int, seq: int) -> FreshnessResult:
        if boot_session < 1 or seq < 0:
            raise ValueError("invalid telemetry cursor")
        if self.boot_session is None:
            self.boot_session = boot_session
            self.seq = seq
            return FreshnessResult.ACCEPT
        assert self.seq is not None
        if boot_session > self.boot_session:
            self.boot_session = boot_session
            self.seq = seq
            return FreshnessResult.ACCEPT
        if boot_session < self.boot_session:
            return FreshnessResult.STALE_BOOT
        if seq > self.seq:
            self.seq = seq
            return FreshnessResult.ACCEPT
        if seq == self.seq:
            return FreshnessResult.DUPLICATE
        return FreshnessResult.STALE_SEQUENCE


def test_multi_ingress_latest_valid_wins_without_path_ownership() -> None:
    cursor = CanonicalCursor()

    assert cursor.observe(boot_session=1, seq=100) is FreshnessResult.ACCEPT
    assert cursor.observe(boot_session=1, seq=100) is FreshnessResult.DUPLICATE
    assert cursor.observe(boot_session=1, seq=101) is FreshnessResult.ACCEPT
    assert (
        cursor.observe(boot_session=1, seq=100)
        is FreshnessResult.STALE_SEQUENCE
    )
    assert cursor.observe(boot_session=1, seq=102) is FreshnessResult.ACCEPT


def test_new_boot_accepts_seq_reset_and_old_boot_is_rejected() -> None:
    cursor = CanonicalCursor(boot_session=7, seq=900)

    assert cursor.observe(boot_session=8, seq=0) is FreshnessResult.ACCEPT
    assert cursor.observe(boot_session=7, seq=901) is FreshnessResult.STALE_BOOT
    assert cursor.observe(boot_session=8, seq=1) is FreshnessResult.ACCEPT


def test_lost_periodic_sample_recovers_on_next_higher_sequence() -> None:
    cursor = CanonicalCursor(boot_session=3, seq=40)

    # seq 41 is lost on air; the next sample advances canonical state directly.
    assert cursor.observe(boot_session=3, seq=42) is FreshnessResult.ACCEPT


# Decision C: opaque, stable, never-reused NODE_ID allocation contract.
@dataclass
class NodeIdAllocatorModel:
    candidates: list[str]
    active_by_hardware: dict[str, str] = field(default_factory=dict)
    reserved: set[str] = field(default_factory=set)

    def allocate(self, hardware_id: str) -> str:
        existing = self.active_by_hardware.get(hardware_id)
        if existing is not None:
            return existing
        while self.candidates:
            suffix = self.candidates.pop(0)
            candidate = f"node-{suffix}"
            valid_hex = all(character in "0123456789abcdef" for character in suffix)
            if len(suffix) != 32 or not valid_hex:
                raise ValueError(
                    "candidate must represent 128 random bits as lowercase hex"
                )
            if candidate in self.reserved:
                continue
            self.reserved.add(candidate)
            self.active_by_hardware[hardware_id] = candidate
            return candidate
        raise RuntimeError("node id candidate source exhausted")

    def retire(self, hardware_id: str) -> str:
        try:
            return self.active_by_hardware.pop(hardware_id)
        except KeyError as error:
            raise RuntimeError("hardware has no active node id") from error


def test_node_id_is_opaque_stable_and_never_reused() -> None:
    first_suffix = "0" * 31 + "1"
    second_suffix = "0" * 31 + "2"
    allocator = NodeIdAllocatorModel(
        candidates=[first_suffix, first_suffix, second_suffix]
    )

    first = allocator.allocate("hardware-a")
    assert first == f"node-{first_suffix}"
    assert allocator.allocate("hardware-a") == first
    assert "hardware-a" not in first

    assert allocator.retire("hardware-a") == first
    second = allocator.allocate("hardware-a")
    assert second == f"node-{second_suffix}"
    assert second != first
    assert first in allocator.reserved


def test_node_id_collision_is_retried_inside_allocator() -> None:
    reserved_suffix = "a" * 32
    fresh_suffix = "b" * 32
    allocator = NodeIdAllocatorModel(candidates=[reserved_suffix, fresh_suffix])
    allocator.reserved.add(f"node-{reserved_suffix}")

    assert allocator.allocate("hardware-b") == f"node-{fresh_suffix}"


# Decision D: precheck failures do not consume a protected session; claims do.
class SessionState(StrEnum):
    PLANNED = "planned"
    PRECHECKED = "prechecked"
    CLAIMED = "claimed"
    CONSUMED = "consumed"


@dataclass
class ProtectedSessionModel:
    state: SessionState = SessionState.PLANNED
    claim_count: int = 0

    def precheck(self, *, passed: bool) -> None:
        if self.state is not SessionState.PLANNED:
            raise RuntimeError("precheck state invalid")
        if passed:
            self.state = SessionState.PRECHECKED

    def claim(self) -> None:
        if self.state is not SessionState.PRECHECKED:
            raise RuntimeError("claim requires passed precheck")
        self.claim_count += 1
        self.state = SessionState.CLAIMED

    def terminal(self) -> None:
        if self.state is not SessionState.CLAIMED:
            raise RuntimeError("terminal protected result requires claim")
        self.state = SessionState.CONSUMED


def test_preclaim_failure_remains_reusable_and_unconsumed() -> None:
    session = ProtectedSessionModel()

    session.precheck(passed=False)
    assert session.state is SessionState.PLANNED
    assert session.claim_count == 0

    session.precheck(passed=True)
    session.claim()
    session.terminal()
    assert session.state is SessionState.CONSUMED
    assert session.claim_count == 1


def test_claim_cannot_be_silently_replayed() -> None:
    session = ProtectedSessionModel()
    session.precheck(passed=True)
    session.claim()

    try:
        session.claim()
    except RuntimeError as error:
        assert "precheck" in str(error)
    else:
        raise AssertionError("a protected claim must be single-use")
