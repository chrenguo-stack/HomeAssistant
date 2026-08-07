from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .ingest import TelemetryProcessor
from .n3w_ingress_router import N3wManagerIngressRouter
from .n3w_path_lease import N3wPathLeaseCoordinator, PathLeasePolicy
from .n3w_relay_authorization import SqliteRelayAuthorizationProvider
from .n3w_relay_ingress import N3wRelayIngressCore
from .registration import RegistrationRegistry
from .replay_registry import ReplayRegistry

if TYPE_CHECKING:
    from .config import Settings


class N3wRuntimeWiringError(RuntimeError):
    """Production-shaped N3-W runtime state cannot be safely composed."""


def _path_contains_symlink(path: Path) -> bool:
    current = path
    while True:
        if current.is_symlink():
            return True
        if current == current.parent:
            return False
        current = current.parent


def _require_existing_regular_file(path: Path, *, code: str) -> None:
    if not path.is_absolute() or _path_contains_symlink(path):
        raise N3wRuntimeWiringError(code)
    try:
        info = path.stat()
    except OSError as exc:
        raise N3wRuntimeWiringError(code) from exc
    if not stat.S_ISREG(info.st_mode):
        raise N3wRuntimeWiringError(code)


def _require_existing_private_file(path: Path, *, code: str) -> None:
    _require_existing_regular_file(path, code=code)
    info = path.stat()
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise N3wRuntimeWiringError(code)
    if hasattr(os, "getuid") and info.st_uid != os.getuid():
        raise N3wRuntimeWiringError(code)


def require_n3w_registration_store(raw_path: str) -> Path:
    """Fail before Manager startup can create a missing N3-W registration store."""

    path = Path(raw_path).expanduser()
    _require_existing_regular_file(path, code="n3w_registration_store_unavailable")
    return path


@dataclass(slots=True)
class N3wRuntimeWiring:
    """Own one default-off production-shaped N3-W Manager runtime composition.

    The object owns only N3-W replay and authorization resources. The existing
    Manager ``TelemetryProcessor`` and ``RegistrationRegistry`` remain owned by the
    service so Direct and Relay ingress converge on the existing canonical
    publication/discovery path without introducing a second publisher.
    """

    system_id: str
    router: N3wManagerIngressRouter
    replay_registry: ReplayRegistry
    authorization: SqliteRelayAuthorizationProvider
    path_lease: N3wPathLeaseCoordinator
    relay_core: N3wRelayIngressCore
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def relay_subscription(self) -> str:
        return f"gh/v1/{self.system_id}/ingress/gateway/+/+/frame"

    def is_relay_topic(self, topic: str) -> bool:
        if not isinstance(topic, str):
            return False
        parts = topic.split("/")
        return (
            len(parts) == 8
            and parts[:5] == ["gh", "v1", self.system_id, "ingress", "gateway"]
            and parts[7] == "frame"
        )

    def audit(self) -> dict[str, object]:
        """Return secret-free startup evidence without changing runtime state."""

        return {
            "schema": "gh.n3w-manager-runtime-wiring-audit/1",
            "status": "passed",
            "replay": self.replay_registry.audit(),
            "path": self.path_lease.audit(),
            "authorization": self.authorization.audit(),
            "default_off_contract": True,
            "secret_values_included": False,
            "mutated": False,
        }

    def close(self) -> None:
        if self._closed:
            return
        self.authorization.close()
        self.replay_registry.close()
        self._closed = True

    def __enter__(self) -> N3wRuntimeWiring:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def build_n3w_runtime_wiring(
    *,
    settings: Settings,
    processor: TelemetryProcessor,
    registration_registry: RegistrationRegistry | None,
) -> N3wRuntimeWiring:
    """Compose P1/P2 N3-W runtime parts without making any MQTT connection."""

    if not settings.n3w_runtime_enabled:
        raise N3wRuntimeWiringError("n3w_runtime_not_enabled")
    require_n3w_registration_store(settings.pairing_db_path)
    if registration_registry is None:
        raise N3wRuntimeWiringError("n3w_registration_registry_unavailable")

    replay_path = Path(settings.n3w_replay_db_path).expanduser()
    _require_existing_private_file(
        replay_path,
        code="n3w_replay_store_unavailable",
    )

    replay: ReplayRegistry | None = None
    authorization: SqliteRelayAuthorizationProvider | None = None
    try:
        replay = ReplayRegistry(replay_path)
        authorization = SqliteRelayAuthorizationProvider(
            settings.n3w_relay_authorization_db_path,
            settings.n3w_relay_key_dir,
        )
        path_lease = N3wPathLeaseCoordinator(
            replay_registry=replay,
            policy=PathLeasePolicy(
                stability_window_s=settings.n3w_path_stability_window_s,
                minimum_distinct_frames=settings.n3w_path_minimum_distinct_frames,
                lease_ttl_s=settings.n3w_path_lease_ttl_s,
                old_path_grace_s=settings.n3w_path_old_grace_s,
            ),
            ingress_allowed=registration_registry.is_node_id_ingress_allowed,
        )
        relay_core = N3wRelayIngressCore(
            system_id=settings.system_id,
            authorization=authorization,
            replay_registry=replay,
        )
        router = N3wManagerIngressRouter(
            processor=processor,
            replay_registry=replay,
            relay_core=relay_core,
            path_lease=path_lease,
        )
        wiring = N3wRuntimeWiring(
            system_id=settings.system_id,
            router=router,
            replay_registry=replay,
            authorization=authorization,
            path_lease=path_lease,
            relay_core=relay_core,
        )
        wiring.audit()
        return wiring
    except Exception as exc:
        if authorization is not None:
            authorization.close()
        if replay is not None:
            replay.close()
        if isinstance(exc, N3wRuntimeWiringError):
            raise
        raise N3wRuntimeWiringError("n3w_runtime_wiring_unavailable") from exc
