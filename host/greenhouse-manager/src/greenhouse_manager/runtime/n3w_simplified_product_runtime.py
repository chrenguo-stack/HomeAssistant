from __future__ import annotations

import base64
import contextlib
import json
import logging
import os
import re
import stat
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Settings
from .credential_lifecycle import CredentialLifecycleStore
from .n3w_node_application_keys import (
    SqliteNodeApplicationKeyAdmin,
)
from .n3w_node_credentials import (
    ManagedApplicationKeyLifecycle,
    ManagedMqttCredentialLifecycle,
    ManagedProductCredentialIssuer,
)
from .n3w_node_identity_provisioner import (
    PahoNodeIdentityProvisioner,
)
from .n3w_pairing_local_ipc import ManagerOwnedPairingSocket
from .n3w_peer_trust_store import SystemPeerTrustStore
from .n3w_simplified_credentials import (
    SimplifiedCredentialBundleIssuer,
)
from .n3w_simplified_pairing import SimplifiedPairingCoordinator
from .n3w_simplified_pairing_runtime import (
    SimplifiedPairingNetworkSettings,
    assemble_simplified_pairing_runtime,
)
from .n3w_simplified_provisioning import (
    SimplifiedProvisioningStager,
)
from .registration import RegistrationRegistry

_LOGGER = logging.getLogger(__name__)

_HANDOFF_NAME = re.compile(
    r"^handoff-[0-9a-f]{32}\.json$"
)
_HANDOFF_SCHEMA = "gh.pair.setup-secret-import/1"
_MAX_HANDOFF_BYTES = 4096


class SimplifiedProductRuntimeError(RuntimeError):
    pass


def _path_contains_symlink(path: Path) -> bool:
    current = path

    while True:
        if current.is_symlink():
            return True

        if current == current.parent:
            return False

        current = current.parent


def _require_private_path(
    path: Path,
    *,
    directory: bool,
    code: str,
) -> None:
    if (
        not path.is_absolute()
        or _path_contains_symlink(path)
    ):
        raise SimplifiedProductRuntimeError(code)

    try:
        info = path.stat()
    except OSError as error:
        raise SimplifiedProductRuntimeError(code) from error

    valid_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)

    if (
        not valid_type
        or stat.S_IMODE(info.st_mode) & 0o077
        or (
            hasattr(os, "getuid")
            and info.st_uid != os.getuid()
        )
    ):
        raise SimplifiedProductRuntimeError(code)


def _require_private_parent(
    path: Path,
    *,
    code: str,
) -> None:
    _require_private_path(
        path,
        directory=True,
        code=code,
    )


def _ensure_private_database(path: Path) -> None:
    if not path.is_absolute():
        raise SimplifiedProductRuntimeError(
            "private_database_path_invalid"
        )

    if path.exists():
        _require_private_path(
            path,
            directory=False,
            code="private_database_permissions_invalid",
        )
        return

    _require_private_parent(
        path.parent,
        code="private_database_parent_invalid",
    )

    try:
        fd = os.open(
            path,
            os.O_RDWR | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except OSError as error:
        raise SimplifiedProductRuntimeError(
            "private_database_create_failed"
        ) from error

    os.close(fd)
    os.chmod(path, 0o600)


def _ensure_private_runtime_directory(path: Path) -> None:
    """Create or validate one process-owned ephemeral runtime directory."""

    if not path.is_absolute():
        raise SimplifiedProductRuntimeError(
            "pairing_runtime_directory_path_invalid"
        )

    if path.exists() or path.is_symlink():
        _require_private_path(
            path,
            directory=True,
            code="pairing_runtime_directory_permissions_invalid",
        )
        return

    parent = path.parent

    if _path_contains_symlink(parent):
        raise SimplifiedProductRuntimeError(
            "pairing_runtime_directory_parent_invalid"
        )

    try:
        parent_info = parent.stat()
    except OSError as error:
        raise SimplifiedProductRuntimeError(
            "pairing_runtime_directory_parent_invalid"
        ) from error

    parent_mode = stat.S_IMODE(parent_info.st_mode)

    owned_private_parent = (
        stat.S_ISDIR(parent_info.st_mode)
        and not (parent_mode & 0o077)
        and (
            not hasattr(os, "getuid")
            or parent_info.st_uid == os.getuid()
        )
    )

    sticky_shared_parent = (
        stat.S_ISDIR(parent_info.st_mode)
        and bool(parent_info.st_mode & stat.S_ISVTX)
        and bool(parent_mode & 0o002)
    )

    if not (
        owned_private_parent
        or sticky_shared_parent
    ):
        raise SimplifiedProductRuntimeError(
            "pairing_runtime_directory_parent_invalid"
        )

    created = False
    try:
        path.mkdir(mode=0o700)
        created = True
    except FileExistsError:
        # A concurrent creator is accepted only if the final path still
        # proves to be our own private non-symlink directory below.
        pass
    except OSError as error:
        raise SimplifiedProductRuntimeError(
            "pairing_runtime_directory_create_failed"
        ) from error

    if created:
        try:
            os.chmod(path, 0o700)
        except OSError as error:
            raise SimplifiedProductRuntimeError(
                "pairing_runtime_directory_create_failed"
            ) from error

    _require_private_path(
        path,
        directory=True,
        code="pairing_runtime_directory_permissions_invalid",
    )


def _decode_setup_secret(value: object) -> bytes:
    if (
        not isinstance(value, str)
        or not value
        or not value.isascii()
    ):
        raise SimplifiedProductRuntimeError(
            "setup_secret_encoding_invalid"
        )

    try:
        material = base64.urlsafe_b64decode(
            value
            + "="
            * ((4 - len(value) % 4) % 4)
        )
    except (ValueError, TypeError) as error:
        raise SimplifiedProductRuntimeError(
            "setup_secret_encoding_invalid"
        ) from error

    if len(material) != 32:
        raise SimplifiedProductRuntimeError(
            "setup_secret_length_invalid"
        )

    return material


@dataclass(frozen=True, slots=True)
class SimplifiedProductCompositionConfig:
    manager_id: str
    advertised_host: str

    provisioning_username: str
    provisioning_password: str
    provisioning_client_id: str

    node_broker_host: str
    node_broker_port: int
    node_broker_tls_server_name: str
    node_ca_pem: str

    peer_trust_db_path: str
    credential_lifecycle_db_path: str
    pairing_socket_path: str

    bind_host: str = "0.0.0.0"
    http_port: int = 47112
    udp_port: int = 47111

    def validate(self) -> None:
        required = (
            self.manager_id,
            self.advertised_host,
            self.provisioning_username,
            self.provisioning_password,
            self.provisioning_client_id,
            self.node_broker_host,
        )

        if any(
            not isinstance(value, str)
            or not value.strip()
            for value in required
        ):
            raise ValueError(
                "simplified product composition is incomplete"
            )

        if not 1 <= self.node_broker_port <= 65535:
            raise ValueError(
                "node broker port is invalid"
            )

        if not 1 <= self.http_port <= 65535:
            raise ValueError(
                "simplified pairing HTTP port is invalid"
            )

        if not 1 <= self.udp_port <= 65535:
            raise ValueError(
                "simplified pairing UDP port is invalid"
            )

        for raw in (
            self.peer_trust_db_path,
            self.credential_lifecycle_db_path,
            self.pairing_socket_path,
        ):
            path = Path(raw).expanduser()
            if not path.is_absolute():
                raise ValueError(
                    "simplified product private paths must be absolute"
                )


class PrivateSetupSecretInbox:
    """LAB_ONLY filesystem compatibility adapter.

    Setup Secret is never exposed as a LAN HTTP administration API.
    Final handoff files are mode 0600 under one mode-0700 directory.
    """

    def __init__(
        self,
        coordinator: SimplifiedPairingCoordinator,
        directory: str | Path,
        *,
        poll_interval_s: float = 0.25,
    ) -> None:
        if poll_interval_s <= 0:
            raise ValueError(
                "setup secret inbox poll interval must be positive"
            )

        self.coordinator = coordinator
        self.directory = Path(directory).expanduser()
        self.poll_interval_s = poll_interval_s

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        self._prepare_directory()

    def _prepare_directory(self) -> None:
        if not self.directory.is_absolute():
            raise SimplifiedProductRuntimeError(
                "setup_secret_inbox_path_invalid"
            )

        if self.directory.exists():
            _require_private_path(
                self.directory,
                directory=True,
                code="setup_secret_inbox_permissions_invalid",
            )
            return

        _require_private_parent(
            self.directory.parent,
            code="setup_secret_inbox_parent_invalid",
        )

        self.directory.mkdir(
            mode=0o700,
        )
        os.chmod(
            self.directory,
            0o700,
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

        self._stop.clear()

        self._thread = threading.Thread(
            target=self._run,
            name="n3w-setup-secret-inbox",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
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
            raise SimplifiedProductRuntimeError(
                "setup_secret_inbox_stop_timeout"
            )

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                result = self.process_once()

                if result["rejected"]:
                    _LOGGER.warning(
                        "Rejected private Setup Secret handoff count=%d",
                        result["rejected"],
                    )
            except Exception as error:
                _LOGGER.error(
                    "Private Setup Secret inbox iteration failed type=%s",
                    type(error).__name__,
                )

            self._stop.wait(
                self.poll_interval_s
            )

    def process_once(self) -> dict[str, int]:
        accepted = 0
        rejected = 0

        names = sorted(
            name
            for name in os.listdir(
                self.directory
            )
            if _HANDOFF_NAME.fullmatch(name)
        )

        dir_flags = (
            os.O_RDONLY
            | getattr(
                os,
                "O_DIRECTORY",
                0,
            )
            | getattr(
                os,
                "O_NOFOLLOW",
                0,
            )
        )

        try:
            dir_fd = os.open(
                self.directory,
                dir_flags,
            )
        except OSError as error:
            raise SimplifiedProductRuntimeError(
                "setup_secret_inbox_unavailable"
            ) from error

        try:
            directory_info = os.fstat(
                dir_fd
            )

            if (
                not stat.S_ISDIR(
                    directory_info.st_mode
                )
                or stat.S_IMODE(
                    directory_info.st_mode
                )
                & 0o077
                or (
                    hasattr(os, "getuid")
                    and directory_info.st_uid
                    != os.getuid()
                )
            ):
                raise SimplifiedProductRuntimeError(
                    "setup_secret_inbox_permissions_invalid"
                )

            for name in names:
                try:
                    self._consume_file(
                        dir_fd,
                        name,
                    )
                    accepted += 1
                except Exception:
                    rejected += 1
                finally:
                    with contextlib.suppress(FileNotFoundError):
                        os.unlink(
                            name,
                            dir_fd=dir_fd,
                        )

            if names:
                os.fsync(dir_fd)

        finally:
            os.close(dir_fd)

        return {
            "accepted": accepted,
            "rejected": rejected,
        }

    def _consume_file(
        self,
        dir_fd: int,
        name: str,
    ) -> None:
        flags = (
            os.O_RDONLY
            | getattr(
                os,
                "O_NOFOLLOW",
                0,
            )
        )

        try:
            fd = os.open(
                name,
                flags,
                dir_fd=dir_fd,
            )
        except OSError as error:
            raise SimplifiedProductRuntimeError(
                "setup_secret_handoff_unavailable"
            ) from error

        try:
            info = os.fstat(fd)

            if (
                not stat.S_ISREG(
                    info.st_mode
                )
                or stat.S_IMODE(
                    info.st_mode
                )
                != 0o600
                or (
                    hasattr(os, "getuid")
                    and info.st_uid
                    != os.getuid()
                )
            ):
                raise SimplifiedProductRuntimeError(
                    "setup_secret_handoff_permissions_invalid"
                )

            if (
                info.st_size < 1
                or info.st_size
                > _MAX_HANDOFF_BYTES
            ):
                raise SimplifiedProductRuntimeError(
                    "setup_secret_handoff_size_invalid"
                )

            payload = b""

            while (
                len(payload)
                <= _MAX_HANDOFF_BYTES
            ):
                block = os.read(
                    fd,
                    min(
                        1024,
                        _MAX_HANDOFF_BYTES
                        + 1
                        - len(payload),
                    ),
                )

                if not block:
                    break

                payload += block

            if (
                len(payload)
                > _MAX_HANDOFF_BYTES
            ):
                raise SimplifiedProductRuntimeError(
                    "setup_secret_handoff_size_invalid"
                )

        finally:
            os.close(fd)

        try:
            document = json.loads(
                payload.decode("utf-8")
            )
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise SimplifiedProductRuntimeError(
                "setup_secret_handoff_json_invalid"
            ) from error

        if (
            not isinstance(document, dict)
            or set(document)
            != {
                "schema",
                "hardware_id",
                "pairing_id",
                "setup_secret",
            }
        ):
            raise SimplifiedProductRuntimeError(
                "setup_secret_handoff_fields_invalid"
            )

        if (
            document["schema"]
            != _HANDOFF_SCHEMA
        ):
            raise SimplifiedProductRuntimeError(
                "setup_secret_handoff_schema_invalid"
            )

        hardware_id = document[
            "hardware_id"
        ]
        pairing_id = document[
            "pairing_id"
        ]

        if (
            not isinstance(
                hardware_id,
                str,
            )
            or not isinstance(
                pairing_id,
                str,
            )
        ):
            raise SimplifiedProductRuntimeError(
                "setup_secret_handoff_identity_invalid"
            )

        material = bytearray(
            _decode_setup_secret(
                document["setup_secret"]
            )
        )

        try:
            self.coordinator.import_setup_secret(
                hardware_id,
                pairing_id,
                setup_secret=bytes(
                    material
                ),
            )
        finally:
            for index in range(
                len(material)
            ):
                material[index] = 0

            material.clear()


@dataclass(slots=True)
class SimplifiedProductPairingComposition:
    registry: RegistrationRegistry
    key_admin: SqliteNodeApplicationKeyAdmin
    credential_store: CredentialLifecycleStore
    peer_trust: SystemPeerTrustStore
    application_key_lifecycle: ManagedApplicationKeyLifecycle
    mqtt_credential_lifecycle: ManagedMqttCredentialLifecycle
    coordinator: SimplifiedPairingCoordinator
    pairing_runtime: Any
    pairing_socket: ManagerOwnedPairingSocket

    _closed: bool = False

    def close(self) -> None:
        if self._closed:
            return

        self._closed = True

        failures: list[Exception] = []

        try:
            self.pairing_socket.stop()
        except Exception as error:
            failures.append(error)

        try:
            self.pairing_runtime.close()
        except Exception as error:
            failures.append(error)

        for resource in (
            self.registry,
            self.key_admin,
            self.credential_store,
            self.peer_trust,
        ):
            try:
                resource.close()
            except Exception as error:
                failures.append(error)

        if failures:
            raise SimplifiedProductRuntimeError(
                "simplified product composition close failed"
            ) from failures[0]


def _read_node_broker_ca_pem(
    raw_path: str,
) -> str:
    path = Path(
        raw_path
    ).expanduser()

    if (
        not path.is_absolute()
        or path.is_symlink()
        or not path.is_file()
    ):
        raise SimplifiedProductRuntimeError(
            "node_broker_ca_file_invalid"
        )

    if path.stat().st_size > 64 * 1024:
        raise SimplifiedProductRuntimeError(
            "node_broker_ca_file_too_large"
        )

    try:
        value = path.read_text(
            encoding="utf-8"
        )
    except UnicodeError as error:
        raise SimplifiedProductRuntimeError(
            "node_broker_ca_file_invalid"
        ) from error

    if (
        "-----BEGIN CERTIFICATE-----"
        not in value
        or "-----END CERTIFICATE-----"
        not in value
        or "\x00" in value
    ):
        raise SimplifiedProductRuntimeError(
            "node_broker_ca_file_invalid"
        )

    return value


def build_simplified_product_config_from_settings(
    settings: Settings,
) -> SimplifiedProductCompositionConfig:
    settings.validate()

    if not settings.n3w_product_pairing_enabled:
        raise SimplifiedProductRuntimeError(
            "n3w_product_pairing_not_enabled"
        )

    if (
        settings.n3w_provisioning_username
        is None
        or settings.n3w_provisioning_password
        is None
        or settings.n3w_provisioning_client_id
        is None
        or settings.n3w_node_broker_ca_file
        is None
    ):
        raise SimplifiedProductRuntimeError(
            "n3w_product_pairing_configuration_incomplete"
        )

    return SimplifiedProductCompositionConfig(
        manager_id=(
            settings.n3w_pairing_manager_id
        ),
        advertised_host=(
            settings.n3w_pairing_advertised_host
        ),
        provisioning_username=(
            settings.n3w_provisioning_username
        ),
        provisioning_password=(
            settings.n3w_provisioning_password
        ),
        provisioning_client_id=(
            settings.n3w_provisioning_client_id
        ),
        node_broker_host=(
            settings.n3w_node_broker_host
        ),
        node_broker_port=(
            settings.n3w_node_broker_port
        ),
        node_broker_tls_server_name=(
            settings.n3w_node_broker_tls_server_name
        ),
        node_ca_pem=(
            _read_node_broker_ca_pem(
                settings.n3w_node_broker_ca_file
            )
        ),
        peer_trust_db_path=(
            settings.n3w_peer_trust_db_path
        ),
        credential_lifecycle_db_path=(
            settings.n3w_credential_lifecycle_db_path
        ),
        pairing_socket_path=settings.n3w_pairing_socket_path,
        bind_host=(
            settings.n3w_pairing_bind_host
        ),
        http_port=(
            settings.n3w_pairing_http_port
        ),
        udp_port=(
            settings.n3w_pairing_udp_port
        ),
    )


def build_simplified_product_pairing_composition(
    settings: Settings,
    config: SimplifiedProductCompositionConfig,
    *,
    identity_provisioner_factory: Callable[..., Any]
    = PahoNodeIdentityProvisioner,
    pairing_runtime_factory: Callable[..., Any]
    = assemble_simplified_pairing_runtime,
) -> SimplifiedProductPairingComposition:
    settings.validate()
    config.validate()

    if not settings.n3w_runtime_enabled:
        raise SimplifiedProductRuntimeError(
            "n3w_simplified_runtime_not_enabled"
        )

    registration_path = Path(
        settings.pairing_db_path
    ).expanduser()

    lifecycle_path = Path(
        config.credential_lifecycle_db_path
    ).expanduser()

    peer_trust_path = Path(
        config.peer_trust_db_path
    ).expanduser()

    _ensure_private_database(
        registration_path
    )
    _ensure_private_database(
        lifecycle_path
    )
    _ensure_private_database(
        peer_trust_path
    )

    registry: RegistrationRegistry | None = None
    key_admin: SqliteNodeApplicationKeyAdmin | None = None
    credential_store: CredentialLifecycleStore | None = None
    peer_trust: SystemPeerTrustStore | None = None
    pairing_runtime: Any = None

    try:
        registry = RegistrationRegistry(
            registration_path,
            pending_ttl_s=(
                settings.pairing_pending_ttl_s
            ),
        )

        os.chmod(
            registration_path,
            0o600,
        )

        key_admin = (
            SqliteNodeApplicationKeyAdmin(
                settings.n3w_relay_authorization_db_path,
                settings.n3w_relay_key_dir,
                node_state=(
                    registry.node_id_lease_state
                ),
            )
        )

        credential_store = (
            CredentialLifecycleStore(
                lifecycle_path
            )
        )

        os.chmod(
            lifecycle_path,
            0o600,
        )

        peer_trust = SystemPeerTrustStore(
            peer_trust_path
        )

        os.chmod(
            peer_trust_path,
            0o600,
        )

        identity_provisioner = (
            identity_provisioner_factory(
                host=settings.mqtt_host,
                port=settings.mqtt_port,
                username=(
                    config.provisioning_username
                ),
                password=(
                    config.provisioning_password
                ),
                client_id=(
                    config.provisioning_client_id
                ),
                tls_enabled=(
                    settings.mqtt_tls
                ),
                ca_file=(
                    settings.mqtt_ca_file
                ),
            )
        )

        application_key_lifecycle = (
            ManagedApplicationKeyLifecycle(
                key_admin
            )
        )

        mqtt_credential_lifecycle = (
            ManagedMqttCredentialLifecycle(
                credential_store
            )
        )

        product_issuer = (
            ManagedProductCredentialIssuer(
                application_key_lifecycle,
                mqtt_credential_lifecycle,
            )
        )

        simplified_issuer = (
            SimplifiedCredentialBundleIssuer(
                peer_trust
            )
        )

        stager = SimplifiedProvisioningStager(
            identity_provisioner=(
                identity_provisioner
            ),
            product_issuer=(
                product_issuer
            ),
            simplified_issuer=(
                simplified_issuer
            ),
            system_id=settings.system_id,
            broker_host=(
                config.node_broker_host
            ),
            broker_port=(
                config.node_broker_port
            ),
            broker_tls_server_name=(
                config.node_broker_tls_server_name
            ),
            ca_pem=config.node_ca_pem,
        )

        coordinator = (
            SimplifiedPairingCoordinator(
                registry,
                stager,
                manager_id=(
                    config.manager_id
                ),
                session_ttl_s=(
                    settings.pairing_pending_ttl_s
                ),
            )
        )

        network_settings = (
            SimplifiedPairingNetworkSettings(
                manager_id=(
                    config.manager_id
                ),
                system_id=(
                    settings.system_id
                ),
                advertised_host=(
                    config.advertised_host
                ),
                bind_host=(
                    config.bind_host
                ),
                http_port=(
                    config.http_port
                ),
                udp_port=(
                    config.udp_port
                ),
            )
        )

        pairing_runtime = (
            pairing_runtime_factory(
                network_settings,
                coordinator,
            )
        )

        pairing_socket_path = Path(
            config.pairing_socket_path
        ).expanduser()

        _ensure_private_runtime_directory(
            pairing_socket_path.parent
        )

        pairing_socket = ManagerOwnedPairingSocket(
            coordinator,
            pairing_socket_path,
        )

        return (
            SimplifiedProductPairingComposition(
                registry=registry,
                key_admin=key_admin,
                credential_store=(
                    credential_store
                ),
                peer_trust=peer_trust,
                application_key_lifecycle=(
                    application_key_lifecycle
                ),
                mqtt_credential_lifecycle=(
                    mqtt_credential_lifecycle
                ),
                coordinator=coordinator,
                pairing_runtime=(
                    pairing_runtime
                ),
                pairing_socket=pairing_socket,
            )
        )

    except Exception:
        if pairing_runtime is not None:
            with contextlib.suppress(Exception):
                pairing_runtime.close()

        for resource in (
            registry,
            key_admin,
            credential_store,
            peer_trust,
        ):
            if resource is not None:
                with contextlib.suppress(Exception):
                    resource.close()

        raise
