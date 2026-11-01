from __future__ import annotations

import inspect
from datetime import UTC, datetime

import pytest

from greenhouse_manager.runtime import n3w_node_credentials as credentials
from greenhouse_manager.runtime import n3w_simplified_provisioning as provisioning
from greenhouse_manager.runtime.credential_lifecycle import (
    CredentialLifecycleStore,
    CredentialState,
)
from greenhouse_manager.runtime.pairing_service import (
    PairingProvisioningError,
)


def test_current_node_credentials_excludes_retired_pairing_authority() -> None:
    source = inspect.getsource(credentials)
    assert "ProductPairingCore" not in source
    assert "ProductSecurePairingCoordinator" not in source
    assert "SecurePairingCoordinator" not in source
    assert "X25519" not in source


def test_simplified_provisioning_uses_current_credentials_module() -> None:
    source = inspect.getsource(provisioning)
    assert "n3w_product_pairing" not in source
    assert "n3w_node_credentials" in source


def test_required_current_credential_primitives_exist() -> None:
    for name in (
        "ProductApplicationKeyAdmin",
        "ProductApplicationKeyMaterial",
        "ManagedApplicationKeyLifecycle",
        "ManagedMqttCredentialLifecycle",
        "ProductCredentialMaterial",
        "ProductCredentialIssuer",
        "ManagedProductCredentialIssuer",
        "ProductCredentialBundle",
    ):
        assert hasattr(credentials, name)

class FakeApplicationKeyAdmin:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int | bytes]] = []

    def stage_key(
        self,
        *,
        node_id: str,
        key_material: bytes,
    ) -> dict[str, object]:
        self.calls.append(
            ("stage", node_id, key_material)
        )
        return {
            "key_epoch": 7,
        }

    def activate_key(
        self,
        *,
        node_id: str,
        key_epoch: int,
    ) -> dict[str, object]:
        self.calls.append(
            ("activate", node_id, key_epoch)
        )
        return {}

    def revoke_key(
        self,
        *,
        node_id: str,
        key_epoch: int,
    ) -> dict[str, object]:
        self.calls.append(
            ("revoke", node_id, key_epoch)
        )
        return {}

    def rollback_rotation(
        self,
        *,
        node_id: str,
        key_epoch: int,
    ) -> dict[str, object]:
        self.calls.append(
            ("rollback", node_id, key_epoch)
        )
        return {}


def test_application_key_lifecycle_has_no_mqtt_store_dependency() -> None:
    admin = FakeApplicationKeyAdmin()

    lifecycle = credentials.ManagedApplicationKeyLifecycle(
        admin,
        random_bytes=lambda size: b"K" * size,
    )

    material = lifecycle.stage_rotation(
        node_id="node_test_01"
    )

    assert material.key_epoch == 7
    assert material.application_key == b"K" * 32

    lifecycle.rollback_staged_rotation(
        material
    )

    assert [
        call[0]
        for call in admin.calls
    ] == [
        "stage",
        "revoke",
    ]


def test_mqtt_credential_rotation_has_no_application_key_dependency(
    tmp_path,
) -> None:
    now = datetime(
        2026,
        8,
        25,
        4,
        0,
        tzinfo=UTC,
    )

    with CredentialLifecycleStore(
        tmp_path / "credentials.sqlite3"
    ) as store:
        lifecycle = (
            credentials.ManagedMqttCredentialLifecycle(
                store
            )
        )

        activated = lifecycle.activate_initial(
            hardware_id="ghw-c6-00000000000a",
            pairing_id=(
                "11111111-1111-4111-8111-111111111111"
            ),
            node_id="node_test_01",
            credential_generation=1,
            now=now,
        )

        assert (
            activated.state
            is CredentialState.ACTIVE
        )
        assert activated.active_generation == 1

        rotating = lifecycle.begin_rotation(
            "ghw-c6-00000000000a",
            credential_generation=2,
            now=now,
        )

        assert (
            rotating.state
            is CredentialState.ROTATING
        )
        assert rotating.pending_generation == 2

        committed = lifecycle.commit_rotation(
            "ghw-c6-00000000000a",
            now=now,
        )

        assert (
            committed.state
            is CredentialState.ACTIVE
        )
        assert committed.active_generation == 2


def test_product_issuer_is_first_registration_only(
    tmp_path,
) -> None:
    admin = FakeApplicationKeyAdmin()
    application_keys = (
        credentials.ManagedApplicationKeyLifecycle(
            admin,
            random_bytes=lambda size: b"K" * size,
        )
    )

    with CredentialLifecycleStore(
        tmp_path / "credentials.sqlite3"
    ) as store:
        mqtt = (
            credentials.ManagedMqttCredentialLifecycle(
                store
            )
        )

        mqtt.activate_initial(
            hardware_id="ghw-c6-00000000000a",
            pairing_id=(
                "11111111-1111-4111-8111-111111111111"
            ),
            node_id="node_test_01",
            credential_generation=1,
        )

        issuer = credentials.ManagedProductCredentialIssuer(
            application_keys,
            mqtt,
        )

        with pytest.raises(
            PairingProvisioningError,
            match="lifecycle already exists",
        ):
            issuer.stage(
                hardware_id="ghw-c6-00000000000a",
                pairing_id=(
                    "22222222-2222-4222-8222-222222222222"
                ),
                node_id="node_test_01",
                credential_generation=1,
            )

    assert admin.calls == []
