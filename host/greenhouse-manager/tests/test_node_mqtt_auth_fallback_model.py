from __future__ import annotations

import json

import pytest

from greenhouse_manager import node_mqtt_auth_fallback_model as module


@pytest.fixture
def policy() -> module.Policy:
    return module.Policy(
        auth_failure_threshold=3,
        observation_success_threshold=2,
        retry_cooldown_s=120,
    )


@pytest.fixture
def candidate() -> module.Candidate:
    return module.Candidate(
        generation=1,
        username="ghn_gh-n1-a9f2f8",
        client_id="gh-n1-a9f2f8",
        secret_fingerprint="0123456789abcdef",
    )


def _connecting(
    policy: module.Policy,
    candidate: module.Candidate,
) -> module.State:
    staged = module.stage_candidate(module.initial_state(), candidate, policy)
    return module.transition(
        staged,
        module.Event.ACTIVATE,
        policy,
        activation_authorized=True,
    )


def test_happy_path_reaches_committed_state(
    policy: module.Policy,
    candidate: module.Candidate,
) -> None:
    state = _connecting(policy, candidate)
    state = module.transition(state, module.Event.AUTH_OK, policy=policy)
    state = module.transition(state, module.Event.OBSERVATION_OK, policy=policy)
    state = module.transition(state, module.Event.OBSERVATION_OK, policy=policy)

    assert module.ready_for_commit(state, policy) is True

    state = module.transition(
        state,
        module.Event.COMMIT,
        policy,
        commit_authorized=True,
    )

    assert state.phase is module.Phase.COMMITTED
    assert state.profile is module.Profile.CANDIDATE
    assert state.committed_generation == 1
    assert state.anonymous_fallback_present is True


def test_authentication_rejection_is_bounded_and_preserves_candidate(
    policy: module.Policy,
    candidate: module.Candidate,
) -> None:
    state = _connecting(policy, candidate)
    for _ in range(policy.auth_failure_threshold):
        state = module.transition(state, module.Event.AUTH_REJECTED, policy=policy)

    assert state.phase is module.Phase.FALLBACK_ANONYMOUS
    assert state.profile is module.Profile.ANONYMOUS
    assert state.candidate == candidate
    assert state.auth_failures == policy.auth_failure_threshold
    assert state.retry_after_s == policy.retry_cooldown_s


def test_transport_failure_does_not_consume_auth_failure_budget(
    policy: module.Policy,
    candidate: module.Candidate,
) -> None:
    state = _connecting(policy, candidate)
    state = module.transition(state, module.Event.TRANSPORT_FAILURE, policy=policy)

    assert state.phase is module.Phase.FALLBACK_ANONYMOUS
    assert state.auth_failures == 0
    assert state.last_failure == "transport_unavailable"
    assert state.local_operation_healthy is True


def test_observation_failure_rolls_back_without_erasing_candidate(
    policy: module.Policy,
    candidate: module.Candidate,
) -> None:
    state = _connecting(policy, candidate)
    state = module.transition(state, module.Event.AUTH_OK, policy=policy)
    state = module.transition(state, module.Event.OBSERVATION_FAILED, policy=policy)

    assert state.phase is module.Phase.FALLBACK_ANONYMOUS
    assert state.candidate == candidate
    assert state.last_failure == "continuity_or_acl_failure"


def test_restart_before_commit_uses_anonymous_fallback(
    policy: module.Policy,
    candidate: module.Candidate,
) -> None:
    staged = module.stage_candidate(module.initial_state(), candidate, policy)
    restarted = module.transition(staged, module.Event.RESTART, policy=policy)

    assert restarted.phase is module.Phase.FALLBACK_ANONYMOUS
    assert restarted.profile is module.Profile.ANONYMOUS
    assert restarted.candidate == candidate


def test_restart_after_commit_uses_candidate_with_fallback_retained(
    policy: module.Policy,
    candidate: module.Candidate,
) -> None:
    state = _connecting(policy, candidate)
    state = module.transition(state, module.Event.AUTH_OK, policy=policy)
    for _ in range(policy.observation_success_threshold):
        state = module.transition(state, module.Event.OBSERVATION_OK, policy=policy)
    state = module.transition(
        state,
        module.Event.COMMIT,
        policy,
        commit_authorized=True,
    )
    restarted = module.transition(state, module.Event.RESTART, policy=policy)

    assert restarted.phase is module.Phase.CANDIDATE_CONNECTING
    assert restarted.profile is module.Profile.CANDIDATE
    assert restarted.anonymous_fallback_present is True


def test_activation_and_commit_are_explicitly_authorized(
    policy: module.Policy,
    candidate: module.Candidate,
) -> None:
    staged = module.stage_candidate(module.initial_state(), candidate, policy)
    with pytest.raises(module.ModelError, match="activation requires"):
        module.transition(staged, module.Event.ACTIVATE, policy=policy)

    observed = _connecting(policy, candidate)
    observed = module.transition(observed, module.Event.AUTH_OK, policy=policy)
    for _ in range(policy.observation_success_threshold):
        observed = module.transition(
            observed,
            module.Event.OBSERVATION_OK,
            policy,
        )
    with pytest.raises(module.ModelError, match="commit requires"):
        module.transition(observed, module.Event.COMMIT, policy=policy)


def test_public_diagnostics_are_secret_free(
    policy: module.Policy,
    candidate: module.Candidate,
) -> None:
    state = _connecting(policy, candidate)
    report = module.public_diagnostics(state, policy)
    encoded = json.dumps(report, sort_keys=True)

    assert report["candidate_secret_present"] is True
    assert report["candidate_secret_fingerprint"] == "0123456789abcdef"
    assert report["password_included"] is False
    assert report["secret_values_included"] is False
    assert '"password"' not in encoded
    assert "password=" not in encoded


def test_isolated_fault_matrix_passes_without_live_side_effects() -> None:
    report = module.run_fault_matrix()

    assert report["status"] == "node_mqtt_auth_fallback_fault_matrix_passed"
    assert report["scenario_count"] == 7
    assert report["passed_scenario_count"] == 7
    assert report["candidate_firmware_reference_model_validated"] is True
    assert report["ready_for_candidate_firmware_build"] is True
    assert report["ready_for_real_board_capability_test"] is False
    assert report["ready_for_node_credential_generation"] is False
    assert report["ready_for_live_apply"] is False
    assert report["anonymous_closure_enabled"] is False
    assert report["production_execution_invoked"] is False
    assert report["homeassistant_storage_read"] is False
    assert report["node_credentials_delivered"] is False
