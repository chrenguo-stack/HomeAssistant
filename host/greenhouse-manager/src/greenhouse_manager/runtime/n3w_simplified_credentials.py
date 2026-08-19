from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field

from .n3w_credential_contract import ProductCredentialSource
from .n3w_long_lived_peer_trust import SystemPeerCredential
from .n3w_peer_trust_store import SystemPeerTrustStore
from .n3w_simple_pairing_crypto import (
    PairingTranscript,
    derive_bootstrap_key,
    encrypt_credential_bundle,
)

_SCHEMA = "gh.pair.credentials/2"


def _encode_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


@dataclass(frozen=True, slots=True, repr=False)
class SimplifiedProductCredentialBundle:
    """ADR-0007 bundle delivered through the one-time Setup Secret channel."""

    system_id: str
    node_id: str
    broker_host: str
    broker_port: int
    broker_tls_server_name: str
    ca_pem: str
    mqtt_username: str
    mqtt_client_id: str
    credential_generation: int
    n3w_key_epoch: int
    peer_trust_generation: int
    mqtt_password: str = field(repr=False)
    n3w_application_key: str = field(repr=False)
    system_peer_key: bytes = field(repr=False)
    schema: str = _SCHEMA

    @classmethod
    def from_existing(
        cls,
        base: ProductCredentialSource,
        peer: SystemPeerCredential,
    ) -> SimplifiedProductCredentialBundle:
        if base.system_id != peer.system_id:
            raise ValueError("credential bundle system_id does not match peer trust")
        return cls(
            system_id=base.system_id,
            node_id=base.node_id,
            broker_host=base.broker_host,
            broker_port=base.broker_port,
            broker_tls_server_name=base.broker_tls_server_name,
            ca_pem=base.ca_pem,
            mqtt_username=base.mqtt_username,
            mqtt_client_id=base.mqtt_client_id,
            credential_generation=base.credential_generation,
            n3w_key_epoch=base.n3w_key_epoch,
            peer_trust_generation=peer.generation,
            mqtt_password=base.mqtt_password,
            n3w_application_key=base.n3w_application_key,
            system_peer_key=peer.key,
        )

    def to_document(self) -> dict[str, object]:
        return {
            "broker_host": self.broker_host,
            "broker_port": self.broker_port,
            "broker_tls_server_name": self.broker_tls_server_name,
            "ca_pem": self.ca_pem,
            "credential_generation": self.credential_generation,
            "mqtt_client_id": self.mqtt_client_id,
            "mqtt_password": self.mqtt_password,
            "mqtt_username": self.mqtt_username,
            "n3w_application_key": self.n3w_application_key,
            "n3w_key_epoch": self.n3w_key_epoch,
            "node_id": self.node_id,
            "peer_trust_generation": self.peer_trust_generation,
            "schema": self.schema,
            "system_id": self.system_id,
            "system_peer_key": _encode_base64url(self.system_peer_key),
        }

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            self.to_document(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")

    def __repr__(self) -> str:
        return (
            "SimplifiedProductCredentialBundle("
            f"schema={self.schema!r}, system_id={self.system_id!r}, "
            f"node_id={self.node_id!r}, broker_host={self.broker_host!r}, "
            f"broker_port={self.broker_port!r}, "
            f"broker_tls_server_name={self.broker_tls_server_name!r}, "
            "ca_pem=<certificate>, "
            f"mqtt_username={self.mqtt_username!r}, "
            f"mqtt_client_id={self.mqtt_client_id!r}, "
            f"credential_generation={self.credential_generation!r}, "
            f"n3w_key_epoch={self.n3w_key_epoch!r}, "
            f"peer_trust_generation={self.peer_trust_generation!r}, "
            "mqtt_password=<redacted>, n3w_application_key=<redacted>, "
            "system_peer_key=<redacted>)"
        )


class SimplifiedCredentialBundleIssuer:
    """Attach the current canonical SYSTEM_PEER_KEY to an existing node bundle."""

    def __init__(self, peer_trust: SystemPeerTrustStore) -> None:
        self.peer_trust = peer_trust

    def issue(
        self,
        base: ProductCredentialSource,
        *,
        now=None,
    ) -> SimplifiedProductCredentialBundle:
        peer = self.peer_trust.get_or_create(base.system_id, now=now)
        return SimplifiedProductCredentialBundle.from_existing(base, peer)


def encrypt_for_setup_secret(
    bundle: SimplifiedProductCredentialBundle,
    *,
    setup_secret: bytes,
    transcript: PairingTranscript,
    nonce: bytes,
) -> bytes:
    """Encrypt the complete post-registration bundle on the simplified bootstrap path."""

    bootstrap_key = derive_bootstrap_key(setup_secret, transcript)
    return encrypt_credential_bundle(
        bootstrap_key,
        transcript,
        nonce=nonce,
        plaintext=bundle.to_json_bytes(),
    )
