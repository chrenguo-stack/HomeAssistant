from __future__ import annotations

import base64
import threading
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest

from greenhouse_manager.runtime.n3w_simplified_pairing import (
    SimplifiedPairingConflict,
    SimplifiedPairingCoordinator,
    SimplifiedPairingRejected,
)
from greenhouse_manager.runtime.registration import RegistrationRegistry, RegistrationState

NOW = datetime(2026, 8, 17, 8, 30, tzinfo=UTC)
HARDWARE = "ghw-c6-00000000000a"
PAIR = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
REPLACEMENT = "ca3e468d-fcdd-413d-b834-a8ac0cbe889e"
SECRET = bytes(range(32))


def hello(pairing_id: str = PAIR) -> dict[str, object]:
    return {
        "schema": "gh.pair.hello/1",
        "pairing_id": pairing_id,
        "pairing_epoch": 1,
        "hardware_id": HARDWARE,
        "model": "greenhouse-wifi-c6",
        "fw_version": "phase4-simple",
        "node_nonce": base64.urlsafe_b64encode(bytes([49]) * 32).rstrip(b"=").decode(),
        "capabilities": ["simple-setup-secret"],
        "sent_at_ms": 1,
    }


@pytest.fixture
def ready(tmp_path):
    with RegistrationRegistry(tmp_path / "registration.sqlite3", pending_ttl_s=120) as registry:
        registry.observe_hello(hello(), now=NOW)
        coordinator = SimplifiedPairingCoordinator(registry, object(), manager_id="manager_lab_01")
        yield registry, coordinator


def test_import_still_accepts_exact_pending_before_expiry(ready):
    registry, coordinator = ready
    coordinator.import_setup_secret(HARDWARE, PAIR, setup_secret=SECRET, now=NOW + timedelta(seconds=119))
    assert bytes(coordinator._setup[(HARDWARE, PAIR)]) == SECRET
    assert registry.get(HARDWARE).state is RegistrationState.PENDING


@pytest.mark.parametrize("seconds", [120, 121, 600])
def test_import_rejects_at_or_after_expiry_without_secret_mutation(ready, seconds):
    _, coordinator = ready
    with pytest.raises(SimplifiedPairingConflict, match="registration_expired"):
        coordinator.import_setup_secret(HARDWARE, PAIR, setup_secret=SECRET, now=NOW + timedelta(seconds=seconds))
    assert coordinator._setup == {}


def test_expired_import_cannot_use_existing_idempotent_secret(ready):
    _, coordinator = ready
    coordinator.import_setup_secret(HARDWARE, PAIR, setup_secret=SECRET, now=NOW + timedelta(seconds=1))
    with pytest.raises(SimplifiedPairingConflict, match="registration_expired"):
        coordinator.import_setup_secret(HARDWARE, PAIR, setup_secret=SECRET, now=NOW + timedelta(seconds=121))


def test_changed_pairing_id_rejects_without_storage(ready):
    registry, coordinator = ready
    registry.observe_hello(hello(REPLACEMENT), now=NOW + timedelta(seconds=1))
    with pytest.raises(SimplifiedPairingConflict, match="registration_not_pending"):
        coordinator.import_setup_secret(HARDWARE, PAIR, setup_secret=SECRET, now=NOW + timedelta(seconds=2))
    assert coordinator._setup == {}


def test_rejected_session_is_not_accepted_even_before_old_expiry(ready):
    registry, coordinator = ready
    registry.expire_pending(now=NOW + timedelta(seconds=121))
    with pytest.raises(SimplifiedPairingConflict, match="registration_not_pending"):
        coordinator.import_setup_secret(HARDWARE, PAIR, setup_secret=SECRET, now=NOW + timedelta(seconds=2))
    assert coordinator._setup == {}


def test_invalid_secret_rejected_without_access_to_pairing_mutation(ready):
    _, coordinator = ready
    with pytest.raises(SimplifiedPairingRejected, match="setup_secret_invalid"):
        coordinator.import_setup_secret(HARDWARE, PAIR, setup_secret=b"bad", now=NOW)
    assert coordinator._setup == {}


def test_conflicting_import_is_not_replaced(ready):
    _, coordinator = ready
    coordinator.import_setup_secret(HARDWARE, PAIR, setup_secret=SECRET, now=NOW + timedelta(seconds=1))
    with pytest.raises(SimplifiedPairingConflict, match="setup_secret_conflicting_import"):
        coordinator.import_setup_secret(HARDWARE, PAIR, setup_secret=bytes([4]) * 32, now=NOW + timedelta(seconds=2))
    assert bytes(coordinator._setup[(HARDWARE, PAIR)]) == SECRET


def test_registry_expiry_cannot_run_between_import_check_and_storage(ready, monkeypatch):
    registry, coordinator = ready
    entered = threading.Event()
    resume = threading.Event()
    updater_started = threading.Event()
    updater_done = threading.Event()
    outcomes = []
    original = registry.pending_import_guard

    @contextmanager
    def paused_guard(*args, **kwargs):
        with original(*args, **kwargs) as record:
            entered.set()
            if not resume.wait(3):
                raise RuntimeError("SYNTHETIC_TEST_TIMEOUT")
            yield record

    monkeypatch.setattr(registry, "pending_import_guard", paused_guard)

    def intake():
        try:
            coordinator.import_setup_secret(
                HARDWARE, PAIR, setup_secret=SECRET, now=NOW + timedelta(seconds=119)
            )
            outcomes.append("accepted")
        except Exception as error:
            outcomes.append(type(error).__name__)

    def expire():
        updater_started.set()
        registry.expire_pending(now=NOW + timedelta(seconds=121))
        updater_done.set()

    first = threading.Thread(target=intake)
    second = threading.Thread(target=expire)
    first.start()
    try:
        assert entered.wait(3)
        second.start()
        assert updater_started.wait(3)
        assert not updater_done.wait(0.08)
    finally:
        resume.set()
        first.join(3)
        if second.ident is not None:
            second.join(3)
    assert not first.is_alive()
    assert not second.is_alive()
    assert outcomes == ["accepted"]
    assert updater_done.is_set()
    assert bytes(coordinator._setup[(HARDWARE, PAIR)]) == SECRET
    assert registry.get(HARDWARE).state is RegistrationState.EXPIRED
