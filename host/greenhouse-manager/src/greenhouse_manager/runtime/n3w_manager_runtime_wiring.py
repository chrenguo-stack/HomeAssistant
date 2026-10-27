from __future__ import annotations

import contextlib
import os
import stat
from pathlib import Path

from .c06b2_runtime_wiring import run_manager_service as run_c06b2_manager_service
from .config import Settings
from .credential_lifecycle import CredentialLifecycleStore
from .mqtt_service import ManagerMqttService
from .n3w_first_registration_intent import (
    FirstRegistrationIntentStore,
)
from .n3w_first_registration_reconciliation import (
    FirstRegistrationReconciler,
)
from .n3w_first_registration_transaction import (
    FirstRegistrationTransactionService,
)
from .n3w_dynamic_pairing_window import (
    DynamicPairingWindowController,
    DynamicPairingWindowControlServer,
    N3wSimplifiedProductPairingWorker,
    dynamic_pairing_control_socket_path,
)
from .n3w_node_application_keys import (
    SqliteNodeApplicationKeyAdmin,
    SqliteNodeApplicationKeyProvider,
)
from .n3w_node_identity_provisioner import (
    PahoNodeIdentityProvisioner,
)
from .n3w_peer_trust_store import SystemPeerTrustStore
from .n3w_registration_runtime import (
    RegistrationNetworkRuntime,
    RegistrationNetworkSettings,
    assemble_registration_network_runtime,
)
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


class N3wDynamicPairingManagerMqttService(
    N3wSimplifiedManagerMqttService
):
    """Own normal N3-W MQTT plus registration and dynamic pairing authority."""

    def __init__(
        self,
        settings: Settings,
        *,
        registration: RegistrationRegistry,
        replay: ReplayRegistry,
        keys: SqliteNodeApplicationKeyProvider,
    ) -> None:
        self._settings = settings
        self._dynamic_pairing = (
            DynamicPairingWindowController(
                settings,
                registration=registration,
            )
        )
        self._pairing_control = (
            DynamicPairingWindowControlServer(
                self._dynamic_pairing,
                dynamic_pairing_control_socket_path(
                    settings
                ),
            )
        )
        self._first_registration_intents = (
            FirstRegistrationIntentStore()
        )
        self._registration_network: (
            RegistrationNetworkRuntime | None
        ) = None
        self._registration_credential_store: (
            CredentialLifecycleStore | None
        ) = None
        self._registration_key_admin: (
            SqliteNodeApplicationKeyAdmin | None
        ) = None
        self._registration_failure: Exception | None = None
        self._registration_ready = False

        super().__init__(
            settings,
            registration=registration,
            replay=replay,
            keys=keys,
        )

    @property
    def registration_ready(self) -> bool:
        return self._registration_ready

    @property
    def registration_failure_type(self) -> str | None:
        failure = self._registration_failure
        return None if failure is None else type(failure).__name__

    def _close_registration_resources(self) -> None:
        network = self._registration_network
        self._registration_network = None
        if network is not None:
            with contextlib.suppress(Exception):
                network.close()

        self._first_registration_intents.close_active()

        key_admin = self._registration_key_admin
        self._registration_key_admin = None
        if key_admin is not None:
            with contextlib.suppress(Exception):
                key_admin.close()

        credential_store = self._registration_credential_store
        self._registration_credential_store = None
        if credential_store is not None:
            with contextlib.suppress(Exception):
                credential_store.close()

        self._registration_ready = False

    def _start_registration_if_ready(self) -> bool:
        settings = self._settings
        credential_store: CredentialLifecycleStore | None = None
        key_admin: SqliteNodeApplicationKeyAdmin | None = None
        network: RegistrationNetworkRuntime | None = None

        try:
            certificate = _require_existing_regular_file(
                Path(
                    settings
                    .n3w_registration_certificate_file
                ).expanduser(),
                code="n3w_registration_certificate_unavailable",
            )
            private_key = _require_existing_private_file(
                Path(
                    settings
                    .n3w_registration_private_key_file
                ).expanduser(),
                code="n3w_registration_private_key_unavailable",
            )

            peer_trust_path = Path(
                settings.n3w_peer_trust_db_path
            ).expanduser()
            peer_trust_path.parent.mkdir(
                parents=True,
                exist_ok=True,
                mode=0o700,
            )
            with SystemPeerTrustStore(
                peer_trust_path
            ) as peer_trust:
                peer_trust.initialize_baseline(
                    settings.system_id
                )

            for value in (
                settings.n3w_provisioning_username,
                settings.n3w_provisioning_password,
                settings.n3w_provisioning_client_id,
            ):
                if value is None or not value:
                    raise N3wSimplifiedManagerRuntimeError(
                        "n3w_registration_provisioning_identity_unavailable"
                    )

            credential_store = CredentialLifecycleStore(
                settings.n3w_credential_lifecycle_db_path
            )
            key_admin = SqliteNodeApplicationKeyAdmin(
                settings.n3w_relay_authorization_db_path,
                settings.n3w_relay_key_dir,
                node_state=self.registration_registry.node_id_lease_state,
                recover_on_open=False,
            )
            identity = PahoNodeIdentityProvisioner(
                host=settings.mqtt_host,
                port=settings.mqtt_port,
                username=settings.n3w_provisioning_username,
                password=settings.n3w_provisioning_password,
                client_id=settings.n3w_provisioning_client_id,
                tls_enabled=settings.mqtt_tls,
                ca_file=settings.mqtt_ca_file,
            )
            reconciler = FirstRegistrationReconciler(
                registry=self.registration_registry,
                credential_store=credential_store,
                application_keys=key_admin,
                dynsec=identity,
                system_id=settings.system_id,
            )

            reconciler.reconcile_startup()

            transaction = FirstRegistrationTransactionService(
                registry=self.registration_registry,
                intents=self._first_registration_intents,
                window=self._dynamic_pairing,
                manager_id=settings.n3w_pairing_manager_id,
                system_id=settings.system_id,
                reconciler=reconciler,
            )
            self._dynamic_pairing.set_first_registration_close_callback(
                transaction.window_closed
            )

            network = assemble_registration_network_runtime(
                RegistrationNetworkSettings(
                    manager_id=settings.n3w_pairing_manager_id,
                    system_id=settings.system_id,
                    certificate_file=str(certificate),
                    private_key_file=str(private_key),
                ),
                transaction_service=transaction,
            )
            network.start()

            self._registration_credential_store = (
                credential_store
            )
            self._registration_key_admin = key_admin
            self._registration_network = network
            self._registration_failure = None
            self._registration_ready = True
            return True
        except Exception as error:
            if network is not None:
                with contextlib.suppress(Exception):
                    network.close()
            if key_admin is not None:
                with contextlib.suppress(Exception):
                    key_admin.close()
            if credential_store is not None:
                with contextlib.suppress(Exception):
                    credential_store.close()
            self._dynamic_pairing.set_first_registration_close_callback(
                None
            )
            self._first_registration_intents.close_active()
            self._registration_failure = error
            self._registration_ready = False
            return False

    def run(self) -> None:
        self._pairing_control.start()
        self._start_registration_if_ready()
        try:
            super().run()
        finally:
            try:
                self._close_registration_resources()
            finally:
                try:
                    self._pairing_control.stop()
                finally:
                    self._dynamic_pairing.stop()


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
        return N3wDynamicPairingManagerMqttService(
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
