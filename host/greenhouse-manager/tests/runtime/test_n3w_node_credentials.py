from __future__ import annotations

import inspect

from greenhouse_manager.runtime import n3w_node_credentials as credentials
from greenhouse_manager.runtime import n3w_simplified_provisioning as provisioning


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
        "ProductCredentialMaterial",
        "ProductCredentialIssuer",
        "ManagedProductCredentialIssuer",
        "ProductCredentialBundle",
    ):
        assert hasattr(credentials, name)
