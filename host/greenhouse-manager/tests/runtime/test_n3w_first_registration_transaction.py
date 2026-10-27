from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest

from greenhouse_manager.runtime.n3w_first_registration_intent import (
    FirstRegistrationIntentStore,
)
from greenhouse_manager.runtime.n3w_first_registration_transaction import (
    FIRST_REGISTRATION_TTL_SECONDS,
    FirstRegistrationTransactionRejected,
    FirstRegistrationTransactionService,
)
from greenhouse_manager.runtime.registration import RegistrationRegistry

NOW = datetime(2026, 10, 27, 1, 0, tzinfo=UTC)
HARDWARE_ID = "ghw-c6-00000000000a"
PAIRING_ID = "c83aeb0d-8f48-4a39-a34b-ea584a588475"
SECRET = bytes(range(32))


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def request() -> dict[str, str]:
    return {
        "manager_id": "manager_lab_01",
        "system_id": "greenhouse",
        "hardware_id": HARDWARE_ID,
        "pairing_id": PAIRING_ID,
        "setup_secret": _b64(SECRET),
    }


class Window:
    def __init__(self, registry: RegistrationRegistry) -> None:
        self.registry = registry
        self.calls = 0
        self.fail = False
        self.deadlines = []

    def open_first_registration(self, intent):
        self.calls += 1
        durable = self.registry.first_registration_ledger().get(
            intent.pairing_id
        )
        assert durable.expires_at == intent.expires_at
        self.deadlines.append(intent.expires_at)
        if self.fail:
            raise RuntimeError("synthetic open failure")
        return {"pairing_host": "192.168.10.1"}


def service(registry, intents, window):
    return FirstRegistrationTransactionService(
        registry=registry,
        intents=intents,
        window=window,
        manager_id="manager_lab_01",
        system_id="greenhouse",
        clock=lambda: NOW,
    )


def test_durable_active_exists_before_window_and_deadline_is_1800(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        intents = FirstRegistrationIntentStore()
        window = Window(registry)
        result = service(registry, intents, window).start(
            request(),
            source_ip="192.168.10.44",
        )
        attempt = registry.first_registration_ledger().get(PAIRING_ID)

        assert attempt.opened_at == NOW
        assert (
            attempt.expires_at
            == NOW + timedelta(seconds=FIRST_REGISTRATION_TTL_SECONDS)
        )
        assert result.expires_at == attempt.expires_at
        assert window.calls == 1
        assert intents.current() is not None
        assert intents.current().expires_at == attempt.expires_at


def test_exact_duplicate_reuses_deadline_and_conflicting_secret_is_busy(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        intents = FirstRegistrationIntentStore()
        window = Window(registry)
        tx = service(registry, intents, window)

        first = tx.start(request(), source_ip="192.168.10.44")
        second = tx.start(request(), source_ip="192.168.10.44")

        assert first.expires_at == second.expires_at
        assert window.deadlines == [first.expires_at, first.expires_at]

        conflicting = request()
        conflicting["setup_secret"] = _b64(bytes(reversed(range(32))))
        with pytest.raises(
            FirstRegistrationTransactionRejected,
            match="registration_busy",
        ):
            tx.start(
                conflicting,
                source_ip="192.168.10.44",
            )


def test_window_failure_preserves_active_attempt_for_exact_retry(tmp_path) -> None:
    with RegistrationRegistry(tmp_path / "registration.sqlite3") as registry:
        intents = FirstRegistrationIntentStore()
        window = Window(registry)
        tx = service(registry, intents, window)
        window.fail = True

        with pytest.raises(
            FirstRegistrationTransactionRejected,
            match="bootstrap_unavailable",
        ):
            tx.start(
                request(),
                source_ip="192.168.10.44",
            )

        first = registry.first_registration_ledger().get(PAIRING_ID)
        assert first.state.value == "ACTIVE"
        assert intents.current() is not None

        window.fail = False
        retry = tx.start(
            request(),
            source_ip="192.168.10.44",
        )
        assert retry.expires_at == first.expires_at
        assert window.calls == 2
