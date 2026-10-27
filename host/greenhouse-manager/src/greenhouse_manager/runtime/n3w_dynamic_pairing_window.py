from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import os
import re
import socket
import stat
import threading
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import Settings
from .credential_lifecycle import CredentialLifecycleStore
from .n3w_first_registration_intent import FirstRegistrationIntent
from .n3w_simplified_discovery import resolve_route_selected_ipv4
from .n3w_simplified_product_runtime import (
    SimplifiedProductPairingComposition,
    build_simplified_product_config_from_settings,
    build_simplified_product_pairing_composition,
)
from .pairing_discovery import is_local_source
from .registration import RegistrationRegistry

CONTROL_SCHEMA = "gh.n3w.pairing-window-control/1"
CONTROL_RESPONSE_SCHEMA = "gh.n3w.pairing-window-control-result/1"
MAX_CONTROL_BYTES = 4096
CONTROL_TIMEOUT_S = 3.0
MIN_WINDOW_SECONDS = 180
MAX_WINDOW_SECONDS = 600
DEFAULT_WINDOW_SECONDS = 300


class DynamicPairingWindowError(RuntimeError):
    pass


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_rfc1918_ipv4(address: ipaddress.IPv4Address) -> bool:
    value = int(address)
    return (
        value & 0xFF000000 == 0x0A000000
        or value & 0xFFF00000 == 0xAC100000
        or value & 0xFFFF0000 == 0xC0A80000
    )


def _ipv4(value: str, *, code: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as error:
        raise DynamicPairingWindowError(code) from error
    if (
        not isinstance(address, ipaddress.IPv4Address)
        or address.is_unspecified
    ):
        raise DynamicPairingWindowError(code)
    return str(address)


def _private_ipv4(value: str, *, code: str) -> str:
    try:
        address = ipaddress.ip_address(value)
    except ValueError as error:
        raise DynamicPairingWindowError(code) from error
    if (
        not isinstance(address, ipaddress.IPv4Address)
        or not _is_rfc1918_ipv4(address)
    ):
        raise DynamicPairingWindowError(code)
    return str(address)


def _has_symlink(path: Path) -> bool:
    current = path
    while current != current.parent:
        if current.is_symlink():
            return True
        current = current.parent
    return current.is_symlink()


def _validate_socket_path(path: Path, *, mode: int) -> None:
    if (
        not path.is_absolute()
        or _has_symlink(path.parent)
        or mode & 0o077
    ):
        raise DynamicPairingWindowError(
            "pairing_control_socket_path_invalid"
        )
    try:
        info = path.parent.stat()
    except OSError as error:
        raise DynamicPairingWindowError(
            "pairing_control_socket_parent_invalid"
        ) from error
    if (
        not stat.S_ISDIR(info.st_mode)
        or stat.S_IMODE(info.st_mode) & 0o077
        or (
            hasattr(os, "getuid")
            and info.st_uid != os.getuid()
        )
    ):
        raise DynamicPairingWindowError(
            "pairing_control_socket_parent_invalid"
        )
    if path.exists() or path.is_symlink():
        raise DynamicPairingWindowError(
            "pairing_control_socket_path_exists"
        )


def dynamic_pairing_control_socket_path(
    settings: Settings,
) -> Path:
    return (
        Path(settings.n3w_pairing_socket_path)
        .expanduser()
        .with_name("pairing-control.sock")
    )


class N3wSimplifiedProductPairingWorker:
    def __init__(
        self,
        composition: SimplifiedProductPairingComposition,
        *,
        failure_callback: Callable[
            [Exception, bool],
            None,
        ]
        | None = None,
    ) -> None:
        self.composition = composition
        self._failure_callback = failure_callback
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._failure: Exception | None = None
        self._close_failure: Exception | None = None

    @property
    def is_alive(self) -> bool:
        return bool(
            self._thread
            and self._thread.is_alive()
        )

    @property
    def failure(self) -> Exception | None:
        return self._failure

    def start(self) -> None:
        if self.is_alive:
            return
        self._stop.clear()
        self._failure = None
        self._close_failure = None
        try:
            self.composition.pairing_runtime.start()
            if getattr(
                self.composition,
                "pairing_socket_required",
                True,
            ):
                self.composition.pairing_socket.start()
        except Exception:
            self.composition.close()
            raise
        self._thread = threading.Thread(
            target=self._run,
            name="n3w-product-pairing-maintenance",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        interval = (
            self.composition
            .pairing_runtime
            .settings
            .expiry_poll_s
        )
        try:
            while not self._stop.wait(interval):
                self.composition.pairing_runtime.expire()
                if (
                    getattr(
                        self.composition,
                        "pairing_socket_required",
                        True,
                    )
                    and not self.composition.pairing_socket.is_alive
                ):
                    raise RuntimeError(
                        "setup secret inbox stopped"
                    )
        except Exception as error:
            self._failure = error
            exposure_closed = True
            try:
                self.composition.close()
            except Exception as close_error:
                self._close_failure = close_error
                exposure_closed = False
            self._stop.set()
            callback = self._failure_callback
            if callback is not None:
                callback(error, exposure_closed)

    def stop(
        self,
        timeout_s: float = 5.0,
    ) -> None:
        self._stop.set()
        thread = self._thread
        if (
            thread is not None
            and thread is not threading.current_thread()
            and thread.is_alive()
        ):
            thread.join(timeout_s)
        if (
            thread is not None
            and thread is not threading.current_thread()
            and thread.is_alive()
        ):
            raise DynamicPairingWindowError(
                "n3w_product_pairing_worker_stop_timeout"
            )
        try:
            self.composition.close()
        except Exception as error:
            self._close_failure = error
            raise DynamicPairingWindowError(
                "n3w_product_pairing_worker_close_failed"
            ) from error
        if self._close_failure is not None:
            raise DynamicPairingWindowError(
                "n3w_product_pairing_worker_close_failed"
            ) from self._close_failure
        if self._failure is not None:
            raise DynamicPairingWindowError(
                "n3w_product_pairing_worker_failed"
            ) from self._failure


class DynamicPairingWindowController:
    def __init__(
        self,
        settings: Settings,
        *,
        registration: RegistrationRegistry | None = None,
        route_resolver: Callable[
            [str],
            str,
        ] = resolve_route_selected_ipv4,
        composition_factory: Callable[
            [Settings, Any],
            SimplifiedProductPairingComposition,
        ] = build_simplified_product_pairing_composition,
        config_factory: Callable[
            [Settings],
            Any,
        ] = build_simplified_product_config_from_settings,
        worker_factory: Callable[..., N3wSimplifiedProductPairingWorker]
        = N3wSimplifiedProductPairingWorker,
        min_window_seconds: int = MIN_WINDOW_SECONDS,
        max_window_seconds: int = MAX_WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if (
            min_window_seconds < 1
            or max_window_seconds < min_window_seconds
        ):
            raise ValueError(
                "dynamic pairing window bounds are invalid"
            )
        if not settings.n3w_runtime_enabled:
            raise DynamicPairingWindowError(
                "n3w_simplified_runtime_not_enabled"
            )
        if settings.n3w_product_pairing_enabled:
            raise DynamicPairingWindowError(
                "durable_product_pairing_must_be_disabled"
            )
        self.settings = settings
        self._registration = registration
        self._route_resolver = route_resolver
        self._composition_factory = composition_factory
        self._config_factory = config_factory
        self._worker_factory = worker_factory
        self._min_window_seconds = min_window_seconds
        self._max_window_seconds = max_window_seconds
        self._clock = clock
        self._wall_clock = wall_clock
        self._lock = threading.RLock()
        self._operation_lock = threading.Lock()
        self._state = "CLOSED"
        self._generation = 0
        self._composition: SimplifiedProductPairingComposition | None = None
        self._worker: N3wSimplifiedProductPairingWorker | None = None
        self._deadline_stop: threading.Event | None = None
        self._deadline_thread: threading.Thread | None = None
        self._deadline: float | None = None
        self._window_seconds: int | None = None
        self._broker_host_sha256: str | None = None
        self._last_close_reason = "manager_start"
        self._last_failure_type: str | None = None
        self._first_registration_pairing_id: str | None = None
        self._first_registration_pairing_host: str | None = None
        self._first_registration_close_callback: (
            Callable[[str, str], None] | None
        ) = None
        self._registration_discovery_external = False

    def _broker_for_peer(self, peer_ip: str) -> str:
        peer = _private_ipv4(
            peer_ip,
            code="pairing_window_peer_invalid",
        )
        if not is_local_source(peer):
            raise DynamicPairingWindowError(
                "pairing_window_peer_not_local"
            )
        try:
            selected = self._route_resolver(peer)
        except Exception as error:
            raise DynamicPairingWindowError(
                "pairing_window_route_unavailable"
            ) from error
        return _private_ipv4(
            selected,
            code="pairing_window_broker_locator_invalid",
        )

    def _status_locked(self) -> dict[str, object]:
        expires_in: int | None = None
        if (
            self._deadline is not None
            and self._state in {
                "OPEN",
                "CLOSING",
            }
        ):
            expires_in = max(
                0,
                int(
                    self._deadline
                    - self._clock()
                ),
            )
        return {
            "pairing_window_state": self._state,
            "window_seconds": self._window_seconds,
            "expires_in_seconds": expires_in,
            "broker_host_sha256": (
                self._broker_host_sha256
            ),
            "close_reason": self._last_close_reason,
            "failure_type": self._last_failure_type,
            "raw_locator_in_output": False,
        }

    def status(self) -> dict[str, object]:
        with self._lock:
            return self._status_locked()

    def recover_expired_first_registration(
        self,
        *,
        hardware_id_sha256: str,
        pairing_id_sha256: str,
    ) -> dict[str, object]:
        for value in (
            hardware_id_sha256,
            pairing_id_sha256,
        ):
            if (
                not isinstance(value, str)
                or re.fullmatch(
                    r"[0-9a-f]{64}",
                    value,
                )
                is None
            ):
                raise DynamicPairingWindowError(
                    "pairing_recovery_hash_invalid"
                )

        with self._operation_lock:
            with self._lock:
                if self._state != "CLOSED":
                    raise DynamicPairingWindowError(
                        "pairing_recovery_requires_closed_window"
                    )

            registration = self._registration
            if registration is None:
                raise DynamicPairingWindowError(
                    "pairing_recovery_registry_unavailable"
                )

            matches = [
                record
                for record
                in registration.list_current()
                if (
                    _sha256_text(
                        record.hardware_id
                    )
                    == hardware_id_sha256
                    and _sha256_text(
                        record.pairing_id
                    )
                    == pairing_id_sha256
                )
            ]
            if len(matches) != 1:
                raise DynamicPairingWindowError(
                    "pairing_recovery_identity_not_unique"
                )

            record = matches[0]
            try:
                credential_history = (
                    CredentialLifecycleStore(
                        self.settings
                        .n3w_credential_lifecycle_db_path,
                        read_only=True,
                    )
                )
                try:
                    abandoned = (
                        registration
                        .recover_expired_first_registration(
                            record.hardware_id,
                            record.pairing_id,
                            credential_history=(
                                credential_history
                            ),
                        )
                    )
                finally:
                    credential_history.close()
            except Exception as error:
                raise DynamicPairingWindowError(
                    "pairing_recovery_rejected"
                ) from error

            if (
                _sha256_text(
                    abandoned.hardware_id
                )
                != hardware_id_sha256
                or _sha256_text(
                    abandoned.pairing_id
                )
                != pairing_id_sha256
                or any(
                    _sha256_text(
                        current.hardware_id
                    )
                    == hardware_id_sha256
                    for current
                    in registration.list_current()
                )
            ):
                raise DynamicPairingWindowError(
                    "pairing_recovery_postcondition_invalid"
                )

            return {
                "hardware_id_sha256": (
                    hardware_id_sha256
                ),
                "pairing_id_sha256": (
                    pairing_id_sha256
                ),
                "current_registration_released": True,
                "replay_tombstone_preserved": True,
                "credential_history_absent": True,
                "manager_recreated": False,
                "raw_identity_in_output": False,
            }

    def set_registration_discovery_external(
        self,
        enabled: bool,
    ) -> None:
        with self._lock:
            self._registration_discovery_external = bool(enabled)

    def set_first_registration_close_callback(
        self,
        callback: Callable[[str, str], None] | None,
    ) -> None:
        with self._lock:
            self._first_registration_close_callback = callback

    def complete_first_registration(
        self,
        pairing_id: str,
    ) -> None:
        def close_committed() -> None:
            try:
                with self._operation_lock:
                    with self._lock:
                        if (
                            self._state != "OPEN"
                            or self._first_registration_pairing_id
                            != pairing_id
                        ):
                            return
                    self._close_locked(
                        reason="committed",
                    )
            except DynamicPairingWindowError:
                return

        threading.Thread(
            target=close_committed,
            name="n3w-first-registration-complete",
            daemon=True,
        ).start()

    def _worker_failed(
        self,
        generation: int,
        error: Exception,
        exposure_closed: bool,
    ) -> None:
        callback = None
        pairing_id = None
        with self._lock:
            if generation != self._generation:
                return
            deadline_stop = self._deadline_stop
            if deadline_stop is not None:
                deadline_stop.set()
            self._last_close_reason = "worker_failure"
            self._last_failure_type = type(error).__name__
            if exposure_closed:
                pairing_id = self._first_registration_pairing_id
                if pairing_id is not None:
                    callback = self._first_registration_close_callback
                self._state = "CLOSED"
                self._composition = None
                self._worker = None
                self._deadline = None
                self._window_seconds = None
                self._broker_host_sha256 = None
                self._first_registration_pairing_id = None
                self._first_registration_pairing_host = None
            else:
                self._state = "CLOSING"
        if callback is not None and pairing_id is not None:
            callback(pairing_id, "worker_failure")

    def _deadline_run(
        self,
        generation: int,
        stop: threading.Event,
        window_seconds: int,
    ) -> None:
        if stop.wait(window_seconds):
            return
        try:
            with self._operation_lock:
                with self._lock:
                    if (
                        generation != self._generation
                        or self._state != "OPEN"
                    ):
                        return
                self._close_locked(
                    reason="deadline",
                )
        except DynamicPairingWindowError:
            return

    def open_window(
        self,
        *,
        peer_ip: str,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> dict[str, object]:
        if (
            not isinstance(window_seconds, int)
            or isinstance(window_seconds, bool)
            or not self._min_window_seconds
            <= window_seconds
            <= self._max_window_seconds
        ):
            raise DynamicPairingWindowError(
                "pairing_window_seconds_invalid"
            )
        if (
            self.settings.n3w_pairing_advertised_host
            != "auto"
        ):
            raise DynamicPairingWindowError(
                "dynamic_pairing_requires_auto_advertised_host"
            )
        broker_host = self._broker_for_peer(
            peer_ip
        )
        broker_hash = _sha256_text(
            broker_host
        )
        with self._operation_lock:
            with self._lock:
                if self._state != "CLOSED":
                    raise DynamicPairingWindowError(
                        "pairing_window_already_active"
                    )
                self._generation += 1
                generation = self._generation
                self._state = "OPENING"
                self._last_failure_type = None
                self._last_close_reason = "opening"

            composition: SimplifiedProductPairingComposition | None = None
            worker: N3wSimplifiedProductPairingWorker | None = None
            try:
                dynamic_settings = replace(
                    self.settings,
                    n3w_product_pairing_enabled=True,
                    n3w_node_broker_host=broker_host,
                )
                config = self._config_factory(
                    dynamic_settings
                )
                if self._registration_discovery_external:
                    composition = self._composition_factory(
                        dynamic_settings,
                        config,
                        http_only=True,
                    )
                else:
                    composition = self._composition_factory(
                        dynamic_settings,
                        config,
                    )
                worker = self._worker_factory(
                    composition,
                    failure_callback=(
                        lambda error, closed: (
                            self._worker_failed(
                                generation,
                                error,
                                closed,
                            )
                        )
                    ),
                )
                with self._lock:
                    if (
                        generation != self._generation
                        or self._state != "OPENING"
                    ):
                        raise DynamicPairingWindowError(
                            "pairing_window_open_cancelled"
                        )
                    self._composition = composition
                    self._worker = worker
                worker.start()
                with self._lock:
                    if (
                        generation != self._generation
                        or self._state != "OPENING"
                        or worker.failure is not None
                        or not worker.is_alive
                    ):
                        raise DynamicPairingWindowError(
                            "pairing_window_worker_unavailable"
                        )
                    stop = threading.Event()
                    self._deadline_stop = stop
                    self._deadline = (
                        self._clock()
                        + window_seconds
                    )
                    self._window_seconds = (
                        window_seconds
                    )
                    self._broker_host_sha256 = (
                        broker_hash
                    )
                    self._last_close_reason = "open"
                    self._first_registration_pairing_id = (
                        intent.pairing_id
                    )
                    self._first_registration_pairing_host = (
                        pairing_host
                    )
                    self._state = "OPEN"
                    deadline_thread = threading.Thread(
                        target=self._deadline_run,
                        args=(
                            generation,
                            stop,
                            window_seconds,
                        ),
                        name="n3w-dynamic-pairing-deadline",
                        daemon=True,
                    )
                    self._deadline_thread = (
                        deadline_thread
                    )
                    result = self._status_locked()
                deadline_thread.start()
                return result
            except Exception as error:
                cleanup_ok = True
                if worker is not None:
                    try:
                        worker.stop()
                    except Exception:
                        if composition is not None:
                            try:
                                composition.close()
                            except Exception:
                                cleanup_ok = False
                elif composition is not None:
                    try:
                        composition.close()
                    except Exception:
                        cleanup_ok = False
                with self._lock:
                    if generation == self._generation:
                        self._last_failure_type = (
                            type(error).__name__
                        )
                        self._last_close_reason = (
                            "open_failure"
                        )
                        if cleanup_ok:
                            self._state = "CLOSED"
                            self._composition = None
                            self._worker = None
                            self._deadline_stop = None
                            self._deadline_thread = None
                            self._deadline = None
                            self._window_seconds = None
                            self._broker_host_sha256 = None
                        else:
                            self._state = "CLOSING"
                if isinstance(
                    error,
                    DynamicPairingWindowError,
                ):
                    raise
                raise DynamicPairingWindowError(
                    "pairing_window_open_failed"
                ) from error

    def open_first_registration(
        self,
        intent: FirstRegistrationIntent,
    ) -> dict[str, object]:
        if (
            self.settings.n3w_pairing_advertised_host
            != "auto"
        ):
            raise DynamicPairingWindowError(
                "dynamic_pairing_requires_auto_advertised_host"
            )
        observed_at = self._wall_clock().astimezone(UTC)
        remaining = math.ceil(
            (intent.expires_at - observed_at).total_seconds()
        )
        if (
            not intent.active
            or intent.consumed
            or remaining <= 0
        ):
            raise DynamicPairingWindowError(
                "first_registration_intent_expired"
            )
        peer = _ipv4(
            intent.source_ip,
            code="first_registration_source_invalid",
        )
        try:
            selected = self._route_resolver(peer)
        except Exception as error:
            raise DynamicPairingWindowError(
                "pairing_window_route_unavailable"
            ) from error
        pairing_host = _ipv4(
            selected,
            code="pairing_window_broker_locator_invalid",
        )
        broker_hash = _sha256_text(pairing_host)
        identity_hash = _sha256_text(
            "|".join(
                (
                    intent.hardware_id,
                    intent.pairing_id,
                    intent.source_ip,
                )
            )
        )

        with self._operation_lock:
            with self._lock:
                if self._state == "OPEN":
                    if (
                        self._first_registration_pairing_id
                        == intent.pairing_id
                        and self._first_registration_pairing_host
                        is not None
                    ):
                        return {
                            **self._status_locked(),
                            "pairing_host": (
                                self._first_registration_pairing_host
                            ),
                            "window_mode": "first_registration",
                            "first_registration_identity_sha256": (
                                identity_hash
                            ),
                        }
                    raise DynamicPairingWindowError(
                        "pairing_window_already_active"
                    )
                if self._state != "CLOSED":
                    raise DynamicPairingWindowError(
                        "pairing_window_already_active"
                    )
                self._generation += 1
                generation = self._generation
                self._state = "OPENING"
                self._last_failure_type = None
                self._last_close_reason = "opening"

            composition = None
            worker = None
            try:
                dynamic_settings = replace(
                    self.settings,
                    n3w_product_pairing_enabled=True,
                    n3w_node_broker_host=pairing_host,
                )
                config = self._config_factory(
                    dynamic_settings
                )
                composition = self._composition_factory(
                    dynamic_settings,
                    config,
                    first_registration_intent=intent,
                    first_registration_complete_callback=(
                        self.complete_first_registration
                    ),
                )
                worker = self._worker_factory(
                    composition,
                    failure_callback=(
                        lambda error, closed: (
                            self._worker_failed(
                                generation,
                                error,
                                closed,
                            )
                        )
                    ),
                )
                with self._lock:
                    if (
                        generation != self._generation
                        or self._state != "OPENING"
                    ):
                        raise DynamicPairingWindowError(
                            "pairing_window_open_cancelled"
                        )
                    self._composition = composition
                    self._worker = worker
                worker.start()
                with self._lock:
                    if (
                        generation != self._generation
                        or self._state != "OPENING"
                        or worker.failure is not None
                        or not worker.is_alive
                    ):
                        raise DynamicPairingWindowError(
                            "pairing_window_worker_unavailable"
                        )
                    stop = threading.Event()
                    self._deadline_stop = stop
                    self._deadline = self._clock() + remaining
                    self._window_seconds = remaining
                    self._broker_host_sha256 = broker_hash
                    self._last_close_reason = "open"
                    self._state = "OPEN"
                    deadline_thread = threading.Thread(
                        target=self._deadline_run,
                        args=(
                            generation,
                            stop,
                            remaining,
                        ),
                        name="n3w-first-registration-deadline",
                        daemon=True,
                    )
                    self._deadline_thread = deadline_thread
                    result = self._status_locked()
                deadline_thread.start()
                return {
                    **result,
                    "pairing_host": pairing_host,
                    "window_mode": "first_registration",
                    "first_registration_identity_sha256": identity_hash,
                }
            except Exception as error:
                cleanup_ok = True
                if worker is not None:
                    try:
                        worker.stop()
                    except Exception:
                        if composition is not None:
                            try:
                                composition.close()
                            except Exception:
                                cleanup_ok = False
                elif composition is not None:
                    try:
                        composition.close()
                    except Exception:
                        cleanup_ok = False
                with self._lock:
                    if generation == self._generation:
                        self._last_failure_type = type(error).__name__
                        self._last_close_reason = "open_failure"
                        if cleanup_ok:
                            self._state = "CLOSED"
                            self._composition = None
                            self._worker = None
                            self._deadline_stop = None
                            self._deadline_thread = None
                            self._deadline = None
                            self._window_seconds = None
                            self._broker_host_sha256 = None
                        else:
                            self._state = "CLOSING"
                if isinstance(error, DynamicPairingWindowError):
                    raise
                raise DynamicPairingWindowError(
                    "first_registration_window_open_failed"
                ) from error

    def _close_locked(
        self,
        *,
        reason: str,
    ) -> dict[str, object]:
        with self._lock:
            if self._state == "CLOSED":
                return self._status_locked()
            if self._state != "OPEN":
                raise DynamicPairingWindowError(
                    "pairing_window_close_unproven"
                )
            self._state = "CLOSING"
            worker = self._worker
            deadline_stop = self._deadline_stop
            deadline_thread = self._deadline_thread
            generation = self._generation
            pairing_id = self._first_registration_pairing_id
            callback = (
                self._first_registration_close_callback
                if pairing_id is not None
                else None
            )
        if deadline_stop is not None:
            deadline_stop.set()
        if worker is None:
            raise DynamicPairingWindowError(
                "pairing_window_worker_missing"
            )
        try:
            worker.stop()
        except Exception as error:
            with self._lock:
                if generation == self._generation:
                    self._last_failure_type = (
                        type(error).__name__
                    )
                    self._last_close_reason = (
                        "close_failure"
                    )
                    if self._state != "CLOSED":
                        self._state = "CLOSING"
            raise DynamicPairingWindowError(
                "pairing_window_close_unproven"
            ) from error
        if (
            deadline_thread is not None
            and deadline_thread
            is not threading.current_thread()
            and deadline_thread.is_alive()
        ):
            deadline_thread.join(1.0)
        with self._lock:
            if generation == self._generation:
                self._state = "CLOSED"
                self._composition = None
                self._worker = None
                self._deadline_stop = None
                self._deadline_thread = None
                self._deadline = None
                self._window_seconds = None
                self._broker_host_sha256 = None
                self._first_registration_pairing_id = None
                self._first_registration_pairing_host = None
                self._last_close_reason = reason
                self._last_failure_type = None
            result = self._status_locked()
        if callback is not None and pairing_id is not None:
            callback(pairing_id, reason)
        return result

    def close_window(self) -> dict[str, object]:
        with self._operation_lock:
            with self._lock:
                if self._first_registration_pairing_id is not None:
                    raise DynamicPairingWindowError(
                        "first_registration_window_product_owned"
                    )
            return self._close_locked(
                reason="manual",
            )

    def stop(self) -> None:
        with self._operation_lock:
            with self._lock:
                state = self._state
            if state == "OPEN":
                self._close_locked(
                    reason="manager_shutdown",
                )
            elif state not in {
                "CLOSED",
            }:
                raise DynamicPairingWindowError(
                    "pairing_window_shutdown_unproven"
                )


def _read_frame(
    connection: socket.socket,
) -> bytearray:
    payload = bytearray()
    frame_end: int | None = None
    while len(payload) <= MAX_CONTROL_BYTES:
        block = connection.recv(
            min(
                1024,
                MAX_CONTROL_BYTES
                + 1
                - len(payload),
            )
        )
        if not block:
            break
        payload.extend(block)
        if len(payload) > MAX_CONTROL_BYTES:
            raise DynamicPairingWindowError(
                "pairing_control_request_too_large"
            )
        if frame_end is None:
            newline = payload.find(b"\n")
            if newline >= 0:
                frame_end = newline
        if frame_end is not None:
            trailing = payload[
                frame_end + 1:
            ]
            if bytes(trailing).strip():
                raise DynamicPairingWindowError(
                    "pairing_control_request_invalid"
                )
    if not payload:
        raise DynamicPairingWindowError(
            "pairing_control_request_invalid"
        )
    if frame_end is not None:
        del payload[frame_end:]
    if not payload:
        raise DynamicPairingWindowError(
            "pairing_control_request_invalid"
        )
    return payload


def _response(
    controller: DynamicPairingWindowController,
    *,
    accepted: bool,
    code: str,
    extra: dict[str, object] | None = None,
) -> bytes:
    document = {
        "schema": CONTROL_RESPONSE_SCHEMA,
        "accepted": accepted,
        "code": code,
        **controller.status(),
    }
    if extra is not None:
        document.update(extra)
    return (
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


class DynamicPairingWindowControlServer:
    def __init__(
        self,
        controller: DynamicPairingWindowController,
        path: str | Path,
        *,
        mode: int = 0o600,
    ) -> None:
        self.controller = controller
        self.path = Path(
            path
        ).expanduser()
        self.mode = mode
        self._socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        _validate_socket_path(
            self.path,
            mode=self.mode,
        )

    @property
    def is_alive(self) -> bool:
        return bool(
            self._thread
            and self._thread.is_alive()
        )

    def start(self) -> None:
        if self.is_alive:
            return
        _validate_socket_path(
            self.path,
            mode=self.mode,
        )
        listener = socket.socket(
            socket.AF_UNIX,
            socket.SOCK_STREAM,
        )
        try:
            listener.bind(
                str(self.path)
            )
            os.chmod(
                self.path,
                self.mode,
            )
            listener.listen(4)
            listener.settimeout(0.25)
        except Exception:
            listener.close()
            self.path.unlink(
                missing_ok=True
            )
            raise
        self._socket = listener
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._serve,
            name="n3w-pairing-window-control",
            daemon=True,
        )
        self._thread.start()

    def stop(
        self,
        timeout_s: float = 5.0,
    ) -> None:
        self._stop.set()
        listener = self._socket
        if listener is not None:
            listener.close()
        thread = self._thread
        if (
            thread is not None
            and thread.is_alive()
        ):
            thread.join(timeout_s)
        if (
            thread is not None
            and thread.is_alive()
        ):
            raise DynamicPairingWindowError(
                "pairing_control_socket_stop_timeout"
            )
        self._socket = None
        self.path.unlink(
            missing_ok=True
        )

    def _serve(self) -> None:
        while not self._stop.is_set():
            listener = self._socket
            if listener is None:
                return
            try:
                connection, _ = (
                    listener.accept()
                )
            except TimeoutError:
                continue
            except OSError:
                if self._stop.is_set():
                    return
                raise
            with connection:
                connection.settimeout(
                    CONTROL_TIMEOUT_S
                )
                connection.sendall(
                    self._handle(
                        connection
                    )
                )

    def _handle(
        self,
        connection: socket.socket,
    ) -> bytes:
        payload = bytearray()
        try:
            payload = _read_frame(
                connection
            )
            try:
                document = json.loads(
                    bytes(payload).decode(
                        "utf-8"
                    )
                )
            except (
                UnicodeDecodeError,
                json.JSONDecodeError,
            ) as error:
                raise DynamicPairingWindowError(
                    "pairing_control_request_invalid"
                ) from error
            if (
                not isinstance(document, dict)
                or document.get("schema")
                != CONTROL_SCHEMA
            ):
                raise DynamicPairingWindowError(
                    "pairing_control_request_invalid"
                )
            operation = document.get(
                "operation"
            )
            if operation == "status":
                if set(document) != {
                    "schema",
                    "operation",
                }:
                    raise DynamicPairingWindowError(
                        "pairing_control_request_invalid"
                    )
                return _response(
                    self.controller,
                    accepted=True,
                    code="status",
                )
            if operation == "open":
                if set(document) != {
                    "schema",
                    "operation",
                    "peer_ip",
                    "window_seconds",
                }:
                    raise DynamicPairingWindowError(
                        "pairing_control_request_invalid"
                    )
                peer_ip = document.get(
                    "peer_ip"
                )
                window_seconds = document.get(
                    "window_seconds"
                )
                if (
                    not isinstance(
                        peer_ip,
                        str,
                    )
                    or not isinstance(
                        window_seconds,
                        int,
                    )
                    or isinstance(
                        window_seconds,
                        bool,
                    )
                ):
                    raise DynamicPairingWindowError(
                        "pairing_control_request_invalid"
                    )
                self.controller.open_window(
                    peer_ip=peer_ip,
                    window_seconds=(
                        window_seconds
                    ),
                )
                return _response(
                    self.controller,
                    accepted=True,
                    code="opened",
                )
            if operation == "close":
                if set(document) != {
                    "schema",
                    "operation",
                }:
                    raise DynamicPairingWindowError(
                        "pairing_control_request_invalid"
                    )
                self.controller.close_window()
                return _response(
                    self.controller,
                    accepted=True,
                    code="closed",
                )
            if operation == "recover-expired-first":
                if set(document) != {
                    "schema",
                    "operation",
                    "hardware_id_sha256",
                    "pairing_id_sha256",
                }:
                    raise DynamicPairingWindowError(
                        "pairing_control_request_invalid"
                    )
                result = (
                    self.controller
                    .recover_expired_first_registration(
                        hardware_id_sha256=str(
                            document[
                                "hardware_id_sha256"
                            ]
                        ),
                        pairing_id_sha256=str(
                            document[
                                "pairing_id_sha256"
                            ]
                        ),
                    )
                )
                return _response(
                    self.controller,
                    accepted=True,
                    code=(
                        "expired_first_recovery_complete"
                    ),
                    extra=result,
                )
            raise DynamicPairingWindowError(
                "pairing_control_operation_invalid"
            )
        except Exception as error:
            code = (
                str(error)
                if isinstance(
                    error,
                    DynamicPairingWindowError,
                )
                else "pairing_control_rejected"
            )
            return _response(
                self.controller,
                accepted=False,
                code=code,
            )
        finally:
            if payload:
                payload[:] = (
                    b"\0"
                    * len(payload)
                )
                payload.clear()


def _request_over_control_socket(
    path: str | Path,
    document: dict[str, object],
    *,
    timeout_s: float = CONTROL_TIMEOUT_S,
) -> dict[str, object]:
    request = (
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )
    if len(request) > MAX_CONTROL_BYTES:
        raise DynamicPairingWindowError(
            "pairing_control_request_too_large"
        )
    with socket.socket(
        socket.AF_UNIX,
        socket.SOCK_STREAM,
    ) as client:
        client.settimeout(
            timeout_s
        )
        try:
            client.connect(
                str(
                    Path(path).expanduser()
                )
            )
            client.sendall(
                request
            )
            client.shutdown(
                socket.SHUT_WR
            )
            payload = _read_frame(
                client
            )
        except (
            OSError,
            TimeoutError,
        ) as error:
            raise DynamicPairingWindowError(
                "pairing_control_unavailable"
            ) from error
    try:
        result = json.loads(
            bytes(payload).decode(
                "utf-8"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise DynamicPairingWindowError(
            "pairing_control_response_invalid"
        ) from error
    if (
        not isinstance(result, dict)
        or result.get("schema")
        != CONTROL_RESPONSE_SCHEMA
        or not isinstance(
            result.get("accepted"),
            bool,
        )
        or not isinstance(
            result.get("code"),
            str,
        )
        or result.get(
            "pairing_window_state"
        )
        not in {
            "CLOSED",
            "OPENING",
            "OPEN",
            "CLOSING",
        }
        or result.get(
            "raw_locator_in_output"
        )
        is not False
    ):
        raise DynamicPairingWindowError(
            "pairing_control_response_invalid"
        )
    return result


def open_dynamic_pairing_window_over_socket(
    path: str | Path,
    *,
    peer_ip: str,
    window_seconds: int,
) -> dict[str, object]:
    return _request_over_control_socket(
        path,
        {
            "schema": CONTROL_SCHEMA,
            "operation": "open",
            "peer_ip": peer_ip,
            "window_seconds": window_seconds,
        },
    )


def dynamic_pairing_window_status_over_socket(
    path: str | Path,
) -> dict[str, object]:
    return _request_over_control_socket(
        path,
        {
            "schema": CONTROL_SCHEMA,
            "operation": "status",
        },
    )


def close_dynamic_pairing_window_over_socket(
    path: str | Path,
) -> dict[str, object]:
    return _request_over_control_socket(
        path,
        {
            "schema": CONTROL_SCHEMA,
            "operation": "close",
        },
    )


def recover_expired_first_registration_over_socket(
    path: str | Path,
    *,
    hardware_id_sha256: str,
    pairing_id_sha256: str,
) -> dict[str, object]:
    result = _request_over_control_socket(
        path,
        {
            "schema": CONTROL_SCHEMA,
            "operation": "recover-expired-first",
            "hardware_id_sha256": (
                hardware_id_sha256
            ),
            "pairing_id_sha256": (
                pairing_id_sha256
            ),
        },
    )
    if result.get("accepted") is True and (
        result.get("code")
        != "expired_first_recovery_complete"
        or result.get(
            "hardware_id_sha256"
        )
        != hardware_id_sha256
        or result.get(
            "pairing_id_sha256"
        )
        != pairing_id_sha256
        or result.get(
            "current_registration_released"
        )
        is not True
        or result.get(
            "replay_tombstone_preserved"
        )
        is not True
        or result.get(
            "credential_history_absent"
        )
        is not True
        or result.get(
            "manager_recreated"
        )
        is not False
        or result.get(
            "raw_identity_in_output"
        )
        is not False
    ):
        raise DynamicPairingWindowError(
            "pairing_recovery_response_invalid"
        )
    return result
