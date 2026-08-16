import inspect

from greenhouse_manager.runtime.n3w_ingress_router import N3wManagerIngressRouter
from greenhouse_manager.runtime.n3w_multi_ingress_router import N3wMultiIngressRouter
from greenhouse_manager.runtime.n3w_path_lease import N3wPathLeaseCoordinator
from greenhouse_manager.runtime.n3w_product_pairing import ProductCredentialBundle
from greenhouse_manager.runtime.n3w_simplified_credentials import SimplifiedProductCredentialBundle


def test_legacy_host_paths_remain_importable_for_regression_comparison() -> None:
    assert N3wManagerIngressRouter is not None
    assert N3wPathLeaseCoordinator is not None


def test_new_multi_ingress_router_has_no_path_lease_dependency() -> None:
    source = inspect.getsource(inspect.getmodule(N3wMultiIngressRouter))
    assert "n3w_path_lease" not in source
    assert "N3wPathLeaseCoordinator" not in source


def test_v2_credential_bundle_is_additive_to_legacy_fields() -> None:
    old_fields = set(ProductCredentialBundle.__dataclass_fields__)
    new_fields = set(SimplifiedProductCredentialBundle.__dataclass_fields__)

    assert old_fields - {"schema"} <= new_fields
    assert {"peer_trust_generation", "system_peer_key"} <= new_fields
