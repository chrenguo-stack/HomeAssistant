from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools import n3w_t1_core_stack_current_authority_check as check


ROOT = Path(__file__).resolve().parents[2]


def documents():
    return (
        json.loads((ROOT / check.AUTHORITY).read_text(encoding="utf-8")),
        json.loads((ROOT / check.TARGET).read_text(encoding="utf-8")),
        (ROOT / check.FRESH_COMPOSE).read_text(encoding="utf-8"),
        (ROOT / check.BOOTSTRAP).read_text(encoding="utf-8"),
        (ROOT / check.CURRENT_STATE).read_text(encoding="utf-8"),
        (ROOT / check.CURRENT_INDEX).read_text(encoding="utf-8"),
    )


def test_current_authority_repository_contract_passes():
    report = check.validate_repo(ROOT)
    assert report["status"] == "PASS"
    assert report["manager_only_upgrade"] is True
    assert report["homeassistant_unchanged"] is True
    assert report["broker_unchanged"] is True
    assert report["legacy_static_compose_is_current_authority"] is False
    assert report["live_deployment_state"] == "NOT_YET_APPLIED"


def test_manager_target_drift_fails_closed():
    authority, target, compose, bootstrap, state, index = documents()
    target = copy.deepcopy(target)
    target["image"] = "local/greenhouse-manager:fresh-000000000000"
    with pytest.raises(check.AuthorityError, match="target_image_mismatch"):
        check.validate_documents(
            authority,
            target,
            compose,
            bootstrap,
            state,
            index,
        )


def test_current_state_cannot_claim_live_deployment():
    authority, target, compose, bootstrap, state, index = documents()
    authority = copy.deepcopy(authority)
    authority["live_deployment"]["state"] = "APPLIED"
    with pytest.raises(check.AuthorityError, match="live_state_invalid"):
        check.validate_documents(
            authority,
            target,
            compose,
            bootstrap,
            state,
            index,
        )


def test_legacy_static_compose_cannot_be_promoted_silently():
    authority, target, compose, bootstrap, state, index = documents()
    authority = copy.deepcopy(authority)
    authority["current_repository_stack"]["legacy_static_compose"][
        "current_successor_authority"
    ] = True
    with pytest.raises(check.AuthorityError, match="legacy_compose_boundary_invalid"):
        check.validate_documents(
            authority,
            target,
            compose,
            bootstrap,
            state,
            index,
        )


def test_successor_scope_cannot_mutate_homeassistant_or_broker():
    authority, target, compose, bootstrap, state, index = documents()
    authority = copy.deepcopy(authority)
    authority["mutation_scope"]["broker_image"] = True
    with pytest.raises(check.AuthorityError, match="mutation_scope_not_manager_only"):
        check.validate_documents(
            authority,
            target,
            compose,
            bootstrap,
            state,
            index,
        )
