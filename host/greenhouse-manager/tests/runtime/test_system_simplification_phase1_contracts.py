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
ACCEPT = "accept"
DUPLICATE = "duplicate"
STALE_SEQUENCE = "stale_sequence"
STALE_BOOT = "stale_boot"


class CanonicalCursor:
    def __init__(self, *, boot_session: int | None = None, seq: int | None = None) -> None:
        self.boot_session = boot_session
        self.seq = seq

    def observe(self, *, boot_session: int, seq: int) -> str:
        if boot_session < 1 or seq < 0:
            raise ValueError("invalid telemetry cursor")
        if self.boot_session is None:
            self.boot_session = boot_session
            self.seq = seq
            return ACCEPT
        assert self.seq is not None
        if boot_session > self.boot_session:
            self.boot_session = boot_session
            self.seq = seq
            return ACCEPT
        if boot_session < self.boot_session:
            return STALE_BOOT
        if seq > self.seq:
            self.seq = seq
            return ACCEPT
        if seq == self.seq:
            return DUPLICATE
        return STALE_SEQUENCE


def test_multi_ingress_latest_valid_wins_without_path_ownership() -> None:
    cursor = CanonicalCursor()

    assert cursor.observe(boot_session=1, seq=100) == ACCEPT
    assert cursor.observe(boot_session=1, seq=100) == DUPLICATE
    assert cursor.observe(boot_session=1, seq=101) == ACCEPT
    assert cursor.observe(boot_session=1, seq=100) == STALE_SEQUENCE
    assert cursor.observe(boot_session=1, seq=102) == ACCEPT


def test_new_boot_accepts_seq_reset_and_old_boot_is_rejected() -> None:
    cursor = CanonicalCursor(boot_session=7, seq=900)

    assert cursor.observe(boot_session=8, seq=0) == ACCEPT
    assert cursor.observe(boot_session=7, seq=901) == STALE_BOOT
    assert cursor.observe(boot_session=8, seq=1) == ACCEPT


def test_lost_periodic_sample_recovers_on_next_higher_sequence() -> None:
    cursor = CanonicalCursor(boot_session=3, seq=40)

    # seq 41 is lost on air; the next sample advances canonical state directly.
    assert cursor.observe(boot_session=3, seq=42) == ACCEPT


# Decision C: opaque, stable, never-reused NODE_ID allocation contract.
class NodeIdAllocatorModel:
    def __init__(self, candidates: list[str]) -> None:
        self.candidates = candidates
        self.active_by_hardware: dict[str, str] = {}
        self.reserved: set[str] = set()

    def allocate(self, hardware_id: str) -> str:
        existing = self.active_by_hardware.get(hardware_id)
        if existing is not None:
            return existing
        while self.candidates:
            candidate = self.candidates.pop(0)
            if not candidate:
                raise ValueError("candidate node id must be non-empty")
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


def test_node_id_is_internal_stable_and_never_reused() -> None:
    first_id = "internal-generated-id-a"
    second_id = "internal-generated-id-b"
    allocator = NodeIdAllocatorModel(candidates=[first_id, first_id, second_id])

    first = allocator.allocate("hardware-a")
    assert first == first_id
    assert allocator.allocate("hardware-a") == first
    assert "hardware-a" not in first

    assert allocator.retire("hardware-a") == first
    second = allocator.allocate("hardware-a")
    assert second == second_id
    assert second != first
    assert first in allocator.reserved


def test_node_id_collision_is_retried_inside_allocator() -> None:
    allocator = NodeIdAllocatorModel(candidates=["already-used", "fresh-id"])
    allocator.reserved.add("already-used")

    assert allocator.allocate("hardware-b") == "fresh-id"


# Decision D: precheck failures do not consume a protected session; claims do.
PLANNED = "planned"
PRECHECKED = "prechecked"
CLAIMED = "claimed"
CONSUMED = "consumed"


class ProtectedSessionModel:
    def __init__(self) -> None:
        self.state = PLANNED
        self.claim_count = 0

    def precheck(self, *, passed: bool) -> None:
        if self.state != PLANNED:
            raise RuntimeError("precheck state invalid")
        if passed:
            self.state = PRECHECKED

    def claim(self) -> None:
        if self.state != PRECHECKED:
            raise RuntimeError("claim requires passed precheck")
        self.claim_count += 1
        self.state = CLAIMED

    def terminal(self) -> None:
        if self.state != CLAIMED:
            raise RuntimeError("terminal protected result requires claim")
        self.state = CONSUMED


def test_preclaim_failure_remains_reusable_and_unconsumed() -> None:
    session = ProtectedSessionModel()

    session.precheck(passed=False)
    assert session.state == PLANNED
    assert session.claim_count == 0

    session.precheck(passed=True)
    session.claim()
    session.terminal()
    assert session.state == CONSUMED
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
