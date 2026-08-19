from __future__ import annotations

import os
import stat
import threading
from pathlib import Path

from .c06b2_runtime_wiring import run_manager_service as run_c06b2_manager_service
from .config import Settings
from .mqtt_service import ManagerMqttService
from .n3w_node_application_keys import SqliteNodeApplicationKeyProvider
from .n3w_simplified_isolated_mqtt_service import N3wSimplifiedIsolatedMqttService
from .n3w_simplified_product_runtime import (
    SimplifiedProductPairingComposition,
    build_simplified_product_config_from_settings,
    build_simplified_product_pairing_composition,
)
from .registration import RegistrationRegistry
from .replay_registry import ReplayRegistry


class N3wSimplifiedManagerRuntimeError(RuntimeError):
    """Production-shaped simplified N3-W Manager state is not safely composable."""


def _path_contains_symlink(path: Path) -> bool:
    current = path
    while True:
        if current.is_symlink():
            return True
        if current == current.parent:
            return False
        current = current.parent


def _require_existing_regular_file(path: Path, *, code: str) -> Path:
    if not path.is_absolute() or _path_contains_symlink(path):
        raise N3wSimplifiedManagerRuntimeError(code)
    try:
        info = path.stat()
    except OSError as error:
        raise N3wSimplifiedManagerRuntimeError(code) from error
    if not stat.S_ISREG(info.st_mode):
        raise N3wSimplifiedManagerRuntimeError(code)
    return path


def _require_existing_private_file(path: Path, *, code: str) -> Path:
    _require_existing_regular_file(path, code=code)
    info = path.stat()
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise N3wSimplifiedManagerRuntimeError(code)
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise N3wSimplifiedManagerRuntimeError(code)
    return path


class N3wSimplifiedManagerMqttService(N3wSimplifiedIsolatedMqttService):
    """Own simplified N3-W MQTT ingress plus its replay/key readers."""

    def __init__(
        self,
        settings: Settings,
        *,
        registration: RegistrationRegistry,
        replay: ReplayRegistry,
        keys: SqliteNodeApplicationKeyProvider,
    ) -> None:
        self._owned_replay = replay
        self._owned_keys = keys
        super().__init__(
            settings,
            registration=registration,
            replay=replay,
            keys=keys,
        )

    def run(self) -> None:
        try:
            super().run()
        finally:
            self._owned_keys.close()
            self._owned_replay.close()


class N3wSimplifiedProductPairingWorker:
    """Own product pairing expiry and private Setup-Secret inbox lifecycle."""

    def __init__(
        self,
        composition: SimplifiedProductPairingComposition,
    ) -> None:
        self.composition = composition
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._failure: Exception | None = None

    @property
    def is_alive(self) -> bool:
        return bool(
            self._thread
            and self._thread.is_alive()
        )

    def start(self) -> None:
        if self.is_alive:
            return

        self._stop.clear()
        self._failure = None

        try:
            self.composition.pairing_runtime.start()
            self.composition.setup_secret_inbox.start()
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

        while not self._stop.wait(interval):
            try:
                self.composition.pairing_runtime.expire()

                if (
                    not self.composition
                    .setup_secret_inbox
                    .is_alive
                ):
                    raise RuntimeError(
                        "setup secret inbox stopped"
                    )
            except Exception as error:
                self._failure = error
                self._stop.set()
                return

    def stop(
        self,
        timeout_s: float = 5.0,
    ) -> None:
        self._stop.set()

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
            raise N3wSimplifiedManagerRuntimeError(
                "n3w_product_pairing_worker_stop_timeout"
            )

        try:
            self.composition.close()
        finally:
            if self._failure is not None:
                raise N3wSimplifiedManagerRuntimeError(
                    "n3w_product_pairing_worker_failed"
                ) from self._failure


class N3wSimplifiedProductManagerMqttService(
    N3wSimplifiedManagerMqttService
):
    """Own normal N3-W MQTT plus simplified first-registration runtime."""

    def __init__(
        self,
        settings: Settings,
        *,
        registration: RegistrationRegistry,
        replay: ReplayRegistry,
        keys: SqliteNodeApplicationKeyProvider,
        pairing: SimplifiedProductPairingComposition,
    ) -> None:
        self._product_pairing = pairing
        self._product_pairing_worker = (
            N3wSimplifiedProductPairingWorker(
                pairing
            )
        )

        super().__init__(
            settings,
            registration=registration,
            replay=replay,
            keys=keys,
        )

    def run(self) -> None:
        self._product_pairing_worker.start()

        try:
            super().run()
        finally:
            self._product_pairing_worker.stop()


def build_n3w_simplified_manager_service(
    settings: Settings,
) -> N3wSimplifiedManagerMqttService:
    """Compose the Phase-4-proven Direct/Relay path for normal Manager startup.

    The transitional application-key database/key directory are reused read-only,
    but gateway grants and Manager PATH ownership are not consulted.
    """

    if not settings.n3w_runtime_enabled:
        raise N3wSimplifiedManagerRuntimeError("n3w_simplified_runtime_not_enabled")

    registration_path = _require_existing_regular_file(
        Path(settings.pairing_db_path).expanduser(),
        code="n3w_registration_store_unavailable",
    )
    replay_path = _require_existing_private_file(
        Path(settings.n3w_replay_db_path).expanduser(),
        code="n3w_replay_store_unavailable",
    )

    registration: RegistrationRegistry | None = None
    replay: ReplayRegistry | None = None
    keys: SqliteNodeApplicationKeyProvider | None = None
    try:
        registration = RegistrationRegistry(
            registration_path,
            pending_ttl_s=settings.pairing_pending_ttl_s,
        )
        replay = ReplayRegistry(replay_path)
        keys = SqliteNodeApplicationKeyProvider(
            settings.n3w_relay_authorization_db_path,
            settings.n3w_relay_key_dir,
        )
        keys.audit()
        return N3wSimplifiedManagerMqttService(
            settings,
            registration=registration,
            replay=replay,
            keys=keys,
        )
    except Exception as error:
        if keys is not None:
            keys.close()
        if replay is not None:
            replay.close()
        if registration is not None:
            registration.close()
        if isinstance(error, N3wSimplifiedManagerRuntimeError):
            raise
        raise N3wSimplifiedManagerRuntimeError(
            "n3w_simplified_runtime_wiring_unavailable"
        ) from error


def build_n3w_simplified_product_manager_service(
    settings: Settings,
) -> N3wSimplifiedProductManagerMqttService:
    """Compose final product first-registration and Direct/Relay runtime."""

    if (
        not settings.n3w_runtime_enabled
        or not settings.n3w_product_pairing_enabled
    ):
        raise N3wSimplifiedManagerRuntimeError(
            "n3w_product_pairing_runtime_not_enabled"
        )

    pairing: SimplifiedProductPairingComposition | None = None
    registration: RegistrationRegistry | None = None
    replay: ReplayRegistry | None = None
    keys: SqliteNodeApplicationKeyProvider | None = None

    try:
        product_config = (
            build_simplified_product_config_from_settings(
                settings
            )
        )

        pairing = (
            build_simplified_product_pairing_composition(
                settings,
                product_config,
            )
        )

        registration_path = (
            _require_existing_private_file(
                Path(
                    settings.pairing_db_path
                ).expanduser(),
                code=(
                    "n3w_registration_store_unavailable"
                ),
            )
        )

        replay_path = (
            _require_existing_private_file(
                Path(
                    settings.n3w_replay_db_path
                ).expanduser(),
                code="n3w_replay_store_unavailable",
            )
        )

        registration = RegistrationRegistry(
            registration_path,
            pending_ttl_s=(
                settings.pairing_pending_ttl_s
            ),
        )

        replay = ReplayRegistry(
            replay_path
        )

        keys = SqliteNodeApplicationKeyProvider(
            settings.n3w_relay_authorization_db_path,
            settings.n3w_relay_key_dir,
        )

        keys.audit()

        return N3wSimplifiedProductManagerMqttService(
            settings,
            registration=registration,
            replay=replay,
            keys=keys,
            pairing=pairing,
        )

    except Exception as error:
        if keys is not None:
            keys.close()

        if replay is not None:
            replay.close()

        if registration is not None:
            registration.close()

        if pairing is not None:
            pairing.close()

        if isinstance(
            error,
            N3wSimplifiedManagerRuntimeError,
        ):
            raise

        raise N3wSimplifiedManagerRuntimeError(
            "n3w_product_pairing_runtime_wiring_unavailable"
        ) from error


def build_manager_mqtt_service(settings: Settings) -> ManagerMqttService:
    """Select simplified N3-W when enabled; preserve the normal base otherwise."""

    if settings.n3w_runtime_enabled:
        if settings.n3w_product_pairing_enabled:
            return (
                build_n3w_simplified_product_manager_service(
                    settings
                )
            )
        return build_n3w_simplified_manager_service(
            settings
        )

    return ManagerMqttService(settings)


def run_manager_service(settings: Settings) -> None:
    """Run Manager/C06-B2 with the Phase 5-A N3-W service selector."""

    run_c06b2_manager_service(
        settings,
        service_factory=build_manager_mqtt_service,
    )
