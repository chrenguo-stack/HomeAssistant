from pathlib import Path

RUNTIME = Path(__file__).resolve().parents[2] / "src/greenhouse_manager/runtime"

QUARANTINED = {
    "n3w_product_pairing.py": (
        "n3w_product_pairing_legacy.py",
        "ProductSecurePairingCoordinator",
    ),
    "n3w_product_peer_authorization.py": (
        "n3w_product_peer_authorization_legacy.py",
        "PeerAuthorizationService",
    ),
    "n3w_product_manager_adapter.py": (
        "n3w_product_manager_adapter_legacy.py",
        "PeerAuthorizationMqttAdapter",
    ),
    "n3w_product_mqtt_service.py": (
        "n3w_product_mqtt_service_legacy.py",
        "ProductManagerMqttService",
    ),
    "n3w_path_lease.py": (
        "n3w_path_lease_legacy.py",
        "N3wPathLeaseCoordinator",
    ),
    "n3w_ingress_router.py": (
        "n3w_ingress_router_legacy.py",
        "N3wManagerIngressRouter",
    ),
    "n3w_runtime_wiring.py": (
        "n3w_runtime_wiring_legacy.py",
        "N3wPathLeaseCoordinator",
    ),
}


def test_legacy_product_authority_is_quarantined_behind_compatibility_shims() -> None:
    for public_name, (legacy_name, marker) in QUARANTINED.items():
        shim = (RUNTIME / public_name).read_text()
        legacy = (RUNTIME / legacy_name).read_text()
        legacy_stem = legacy_name.removesuffix(".py")
        assert f"from . import {legacy_stem} as _legacy" in shim
        assert "sys.modules[__name__] = _legacy" in shim
        assert marker not in shim
        assert marker in legacy
