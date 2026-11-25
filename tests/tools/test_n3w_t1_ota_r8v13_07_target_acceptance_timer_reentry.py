from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import n3w_t1_core_updater_ha_recovery_startup as startup
from n3w_t1_core_updater_ha_usb_state import TARGET_WRITES_POSSIBLE, U11


def document(*, retry_after: int | None) -> dict[str, object]:
    state: dict[str, object] = {
        "attempts": 1,
    }
    if retry_after is not None:
        state["retry_after_unix"] = retry_after
    return {
        "status": "ACTIVE",
        "phase": U11,
        "recovery_required": False,
        "target_activation": TARGET_WRITES_POSSIBLE,
        "target_acceptance": state,
    }


class Store:
    def __init__(self, root: Path, value: dict[str, object]) -> None:
        self.root = root
        self.value = value

    def read(self) -> dict[str, object]:
        return self.value


class Runtime:
    def __init__(self) -> None:
        self.media_calls: list[tuple[Store, dict[str, object], bool]] = []

    def mounted_recovery_provider(
        self, store: Store, value: dict[str, object], *, require_original: bool = False
    ) -> object:
        self.media_calls.append((store, value, require_original))
        return object()


def test_u11_retry_wait_does_not_reenter_worker_before_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path, document(retry_after=2_000_000_020))
    runtime = Runtime()
    monkeypatch.setattr(startup.time, "time", lambda: 2_000_000_000)

    assert startup._dispatch_pending_candidate(store, runtime) == "TARGET_ACCEPTANCE_WAITING"
    assert runtime.media_calls == []


@pytest.mark.parametrize(
    ("terminal_status", "expected"),
    [
        ("ACTIVE", "TARGET_ACCEPTANCE_PENDING"),
        ("COMMITTED", "COMMITTED"),
        ("ROLLED_BACK", "ROLLED_BACK"),
    ],
)
def test_u11_retry_timer_reenters_acceptance_without_install_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    terminal_status: str,
    expected: str,
) -> None:
    store = Store(tmp_path, document(retry_after=2_000_000_000))
    runtime = Runtime()
    calls: list[object] = []
    monkeypatch.setattr(startup.time, "time", lambda: 2_000_000_001)

    class Recovery:
        def __init__(self, observed_store, observed_runtime, health) -> None:
            assert observed_store is store
            assert observed_runtime is runtime
            assert health is runtime

        def resume_target_acceptance(self, media: object) -> dict[str, str]:
            calls.append(media)
            return {"status": terminal_status}

    monkeypatch.setattr(startup, "HaPredecessorRecovery", Recovery)
    monkeypatch.setattr(
        runtime,
        "install_requested",
        lambda _store: pytest.fail("INSTALL must not be replayed from U11"),
        raising=False,
    )

    assert startup._dispatch_pending_candidate(store, runtime) == expected
    assert len(runtime.media_calls) == 1
    assert runtime.media_calls[0][2] is True
    assert calls == [calls[0]]
