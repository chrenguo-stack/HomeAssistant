from __future__ import annotations

import pytest

from greenhouse_manager.t1_broker_identity_activation_checks import (
    BrokerIdentityActivationCheckError,
)
from greenhouse_manager.t1_broker_identity_preactivation_gate import (
    _live_readiness,
)


def _audit(live_readiness: dict[str, object]) -> dict[str, object]:
    return {
        "schema": "gh.m2.t1-auth-client-migration-audit/1",
        "read_only": True,
        "apply_enabled": False,
        "current_services_modified": False,
        "audit_complete": True,
        "ready_for_live_apply": False,
        "live_readiness": live_readiness,
    }


def test_accepts_compact_client_migration_readiness_contract() -> None:
    live = {
        "ready": True,
        "source_binding": True,
        "retained_topic_readable": True,
    }

    assert _live_readiness(_audit(live)) == live


def test_rejects_incomplete_compact_readiness_contract() -> None:
    live = {
        "ready": True,
        "source_binding": True,
        "retained_topic_readable": False,
    }

    with pytest.raises(
        BrokerIdentityActivationCheckError,
        match="live readiness details are missing",
    ):
        _live_readiness(_audit(live))
