from __future__ import annotations

import os
import stat
from pathlib import Path

from .c06b2_runtime_wiring import run_manager_service as run_c06b2_manager_service
from .config import Settings
from .mqtt_service import ManagerMqttService
from .n3w_node_application_keys import SqliteNodeApplicationKeyProvider
from .n3w_simplified_isolated_mqtt_service import N3wSimplifiedIsolatedMqttService
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


def build_manager_mqtt_service(settings: Settings) -> ManagerMqttService:
    """Select simplified N3-W when enabled; preserve the normal base otherwise."""

    if settings.n3w_runtime_enabled:
        return build_n3w_simplified_manager_service(settings)
    return ManagerMqttService(settings)


def run_manager_service(settings: Settings) -> None:
    """Run Manager/C06-B2 with the Phase 5-A N3-W service selector."""

    run_c06b2_manager_service(
        settings,
        service_factory=build_manager_mqtt_service,
    )
