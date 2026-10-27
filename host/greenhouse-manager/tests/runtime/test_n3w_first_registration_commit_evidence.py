from __future__ import annotations

import pytest

from greenhouse_manager.runtime.n3w_simplified_provisioning import (
    StagedProvisionedSimplifiedBundle,
)


class Issuer:
    def __init__(self) -> None:
        self.preserve_calls = 0
        self.legacy_calls = 0
        self.rollback_calls = 0

    def commit_preserving_evidence(
        self,
        material,
        *,
        now=None,
    ):
        self.preserve_calls += 1
        raise RuntimeError(
            "synthetic downstream commit failure"
        )

    def commit(self, material, *, now=None):
        self.legacy_calls += 1

    def rollback(self, material):
        self.rollback_calls += 1


class Identity:
    def __init__(self) -> None:
        self.deprovision_calls = 0

    def deprovision(self, plan):
        self.deprovision_calls += 1


def test_preserving_commit_never_rolls_back_cross_store_evidence() -> None:
    issuer = Issuer()
    identity = Identity()
    staged = StagedProvisionedSimplifiedBundle(
        bundle=object(),
        plan=object(),
        credentials=object(),
        material=object(),
        identity_provisioner=identity,
        product_issuer=issuer,
        preserve_commit_evidence=True,
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic downstream commit failure",
    ):
        staged.commit()

    assert issuer.preserve_calls == 1
    assert issuer.legacy_calls == 0
    assert issuer.rollback_calls == 0
    assert identity.deprovision_calls == 0
    assert staged.committed is False
    assert staged.rolled_back is False


def test_legacy_commit_retains_existing_broker_rollback_behavior() -> None:
    class FailingIssuer(Issuer):
        def commit(self, material, *, now=None):
            self.legacy_calls += 1
            raise RuntimeError("legacy failure")

    issuer = FailingIssuer()
    identity = Identity()
    staged = StagedProvisionedSimplifiedBundle(
        bundle=object(),
        plan=object(),
        credentials=object(),
        material=object(),
        identity_provisioner=identity,
        product_issuer=issuer,
        preserve_commit_evidence=False,
    )

    with pytest.raises(
        RuntimeError,
        match="legacy failure",
    ):
        staged.commit()

    assert issuer.preserve_calls == 0
    assert issuer.legacy_calls == 1
    assert identity.deprovision_calls == 1
