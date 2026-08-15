from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .credential_lifecycle import CredentialLifecycleStore
from .n3w_product_isolated_mqtt_service import N3wProductIsolatedMqttService
from .n3w_product_manager_adapter import (
    ManagerRelayEligibilityProvider,
    PeerAuthorizationMqttAdapter,
    ReplayRegistryPathAuthority,
)
from .n3w_product_peer_authorization import (
    PeerAuthorizationService,
    ProductNodeApplicationKeyProvider,
    RegistrationMembershipResolver,
    SqlitePeerAuthorizationReplayStore,
)
from .registration import RegistrationRegistry
from .replay_registry import ReplayRegistry


class N3wProductIsolatedLauncherError(RuntimeError):
    """The isolated-lab S5 Manager assembly cannot be composed safely."""


@dataclass(slots=True)
class IsolatedPeerAuthorityResources:
    """Own the extra S4 peer-authority readers used only by the isolated launcher."""

    registration_registry: RegistrationRegistry
    credential_store: CredentialLifecycleStore
    application_keys: ProductNodeApplicationKeyProvider
    replay_registry: ReplayRegistry
    peer_replay_store: SqlitePeerAuthorizationReplayStore
    adapter: PeerAuthorizationMqttAdapter
    _closed: bool = False

    def close(self) -> None:
        if self._closed:
            return
        self.peer_replay_store.close()
        self.replay_registry.close()
        self.application_keys.close()
        self.credential_store.close()
        self.registration_registry.close()
        self._closed = True


@dataclass(slots=True)
class IsolatedManagerAssembly:
    service: N3wProductIsolatedMqttService
    authority: IsolatedPeerAuthorityResources

    def run(self) -> None:
        try:
            self.service.run()
        finally:
            self.authority.close()


def build_isolated_peer_authority(settings: Settings) -> IsolatedPeerAuthorityResources:
    """Compose the existing S4 authority against one isolated Manager state copy.

    This function creates no MQTT client and opens no network socket. It uses the
    same registration, credential-lifecycle, application-key, path-lease and
    replay authorities already used by S4/N3-W; it does not create a second
    authorization policy and never derives a pair LMK.
    """

    settings.validate()
    if not settings.n3w_runtime_enabled:
        raise N3wProductIsolatedLauncherError("n3w_runtime_required")

    registration: RegistrationRegistry | None = None
    credentials: CredentialLifecycleStore | None = None
    application_keys: ProductNodeApplicationKeyProvider | None = None
    replay: ReplayRegistry | None = None
    peer_replay: SqlitePeerAuthorizationReplayStore | None = None
    try:
        registration = RegistrationRegistry(
            settings.pairing_db_path,
            pending_ttl_s=settings.pairing_pending_ttl_s,
        )
        credentials = CredentialLifecycleStore(settings.pairing_db_path)
        application_keys = ProductNodeApplicationKeyProvider(
            settings.n3w_relay_authorization_db_path,
            settings.n3w_relay_key_dir,
        )
        replay = ReplayRegistry(settings.n3w_replay_db_path)
        membership = RegistrationMembershipResolver(
            registration,
            credentials,
            application_keys,
            system_id=settings.system_id,
        )
        eligibility = ManagerRelayEligibilityProvider(
            registration,
            ReplayRegistryPathAuthority(replay),
            system_id=settings.system_id,
        )
        peer_replay = SqlitePeerAuthorizationReplayStore(settings.n3w_replay_db_path)
        authority = PeerAuthorizationService(
            membership,
            eligibility,
            peer_replay,
        )
        adapter = PeerAuthorizationMqttAdapter(authority)
        return IsolatedPeerAuthorityResources(
            registration_registry=registration,
            credential_store=credentials,
            application_keys=application_keys,
            replay_registry=replay,
            peer_replay_store=peer_replay,
            adapter=adapter,
        )
    except Exception as error:
        if peer_replay is not None:
            peer_replay.close()
        if replay is not None:
            replay.close()
        if application_keys is not None:
            application_keys.close()
        if credentials is not None:
            credentials.close()
        if registration is not None:
            registration.close()
        if isinstance(error, N3wProductIsolatedLauncherError):
            raise
        raise N3wProductIsolatedLauncherError(
            "isolated_peer_authority_unavailable"
        ) from error


def assemble_isolated_manager_service(settings: Settings) -> IsolatedManagerAssembly:
    """Build the opt-in isolated live service without changing normal app.py."""

    authority = build_isolated_peer_authority(settings)
    try:
        service = N3wProductIsolatedMqttService(settings, authority.adapter)
    except Exception:
        authority.close()
        raise
    return IsolatedManagerAssembly(service=service, authority=authority)


def run_isolated_manager(settings: Settings) -> None:
    assemble_isolated_manager_service(settings).run()
