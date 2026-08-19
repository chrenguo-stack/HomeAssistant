from __future__ import annotations

from typing import Protocol


class ProductCredentialSource(Protocol):
    """Neutral post-registration node credential fields used by simplified N3-W."""

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
    mqtt_password: str
    n3w_application_key: str
