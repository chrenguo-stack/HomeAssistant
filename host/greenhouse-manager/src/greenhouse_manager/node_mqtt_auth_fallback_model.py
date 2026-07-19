from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

SCHEMA = "gh.m2.node-mqtt-auth-fallback-model/1"
MATRIX_SCHEMA = "gh.m2.node-mqtt-auth-fallback-fault-matrix/1"


class ModelError(ValueError):
    """Raised for invalid or unsafe reference-model transitions."""


class Phase(StrEnum):
    LEGACY_ANONYMOUS = "legacy_anonymous"
    CANDIDATE_STAGED = "candidate_staged"
    CANDIDATE_CONNECTING = "candidate_connecting"
    AUTHENTICATED_OBSERVATION = "authenticated_observation"
    FALLBACK_ANONYMOUS = "fallback_anonymous"
    COMMITTED = "committed"


class Profile(StrEnum):
    ANONYMOUS = "anonymous"
    CANDIDATE = "candidate"


class Event(StrEnum):
    ACTIVATE = "activate_candidate"
    AUTH_OK = "auth_accepted"
    AUTH_REJECTED = "auth_rejected"
    TRANSPORT_FAILURE = "transport_failure"
    OBSERVATION_OK = "observation_passed"
    OBSERVATION_FAILED = "observation_failed"
    ROLLBACK = "rollback_requested"
    COMMIT = "commit_authorized"
    LEASE_EXPIRED = "candidate_lease_expired"
    RESTART = "restart"


@dataclass(frozen=True, slots=True)
class Policy:
    auth_failure_threshold: int = 3
    observation_success_threshold: int = 3
    retry_cooldown_s: int = 300
    candidate_lease_timeout_s: int = 600

    def validate(self) -> None:
        _require(self.auth_failure_threshold > 0, "auth failure threshold must be positive")
        _require(self.observation_success_threshold > 0, "observation threshold must be positive")
        _require(self.retry_cooldown_s > 0, "retry cooldown must be positive")
        _require(self.candidate_lease_timeout_s > 0, "candidate lease timeout must be positive")


@dataclass(frozen=True, slots=True)
class Candidate:
    generation: int
    username: str
    client_id: str
    secret_fingerprint: str

    def validate(self) -> None:
        _require(self.generation > 0, "candidate generation must be positive")
        _require(bool(self.username), "candidate username is required")
        _require(bool(self.client_id), "candidate client ID is required")
        _require(len(self.secret_fingerprint) == 16, "secret fingerprint must be 16 characters")


@dataclass(frozen=True, slots=True)
class State:
    phase: Phase
    profile: Profile
    candidate: Candidate | None
    anonymous_fallback_present: bool = True
    auth_failures: int = 0
    observation_successes: int = 0
    retry_after_s: int = 0
    committed_generation: int | None = None
    local_operation_healthy: bool = True
    last_failure: str | None = None

    def validate(self, policy: Policy) -> None:
        policy.validate()
        _require(self.anonymous_fallback_present, "anonymous fallback must remain present")
        _require(self.auth_failures >= 0, "auth failures cannot be negative")
        _require(self.observation_successes >= 0, "observation successes cannot be negative")
        _require(self.retry_after_s >= 0, "retry delay cannot be negative")
        _require(self.local_operation_healthy, "local operation must remain healthy")
        if self.profile is Profile.CANDIDATE:
            _require(self.candidate is not None, "candidate profile requires a candidate")
        if self.candidate is not None:
            self.candidate.validate()
        if self.phase is Phase.COMMITTED:
            _require(self.candidate is not None, "committed state requires a candidate")
            _require(
                self.committed_generation == self.candidate.generation,
                "committed generation must match the candidate",
            )


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ModelError(message)


def initial_state() -> State:
    return State(phase=Phase.LEGACY_ANONYMOUS, profile=Profile.ANONYMOUS, candidate=None)


def stage_candidate(state: State, candidate: Candidate, policy: Policy) -> State:
    state.validate(policy)
    candidate.validate()
    _require(state.committed_generation is None, "cannot stage over a committed generation")
    _require(
        state.phase in {Phase.LEGACY_ANONYMOUS, Phase.FALLBACK_ANONYMOUS},
        "candidate can only be staged from anonymous",
    )
    staged = replace(
        state,
        phase=Phase.CANDIDATE_STAGED,
        profile=Profile.ANONYMOUS,
        candidate=candidate,
        auth_failures=0,
        observation_successes=0,
        retry_after_s=0,
        last_failure=None,
    )
    staged.validate(policy)
    return staged


def _fallback(state: State, policy: Policy, reason: str) -> State:
    _require(state.candidate is not None, "fallback requires a preserved candidate")
    fallback = replace(
        state,
        phase=Phase.FALLBACK_ANONYMOUS,
        profile=Profile.ANONYMOUS,
        observation_successes=0,
        retry_after_s=policy.retry_cooldown_s,
        last_failure=reason,
    )
    fallback.validate(policy)
    return fallback


def transition(
    state: State,
    event: Event,
    policy: Policy,
    *,
    activation_authorized: bool = False,
    commit_authorized: bool = False,
) -> State:
    state.validate(policy)
    if event is Event.ACTIVATE:
        _require(activation_authorized, "candidate activation requires explicit authorization")
        _require(state.candidate is not None, "candidate activation requires a candidate")
        _require(
            state.phase in {Phase.CANDIDATE_STAGED, Phase.FALLBACK_ANONYMOUS},
            "candidate activation is not allowed from this phase",
        )
        result = replace(
            state,
            phase=Phase.CANDIDATE_CONNECTING,
            profile=Profile.CANDIDATE,
            auth_failures=0,
            observation_successes=0,
            retry_after_s=0,
            last_failure=None,
        )
    elif event is Event.AUTH_OK:
        _require(state.phase is Phase.CANDIDATE_CONNECTING, "auth success requires connecting")
        result = replace(
            state,
            phase=Phase.AUTHENTICATED_OBSERVATION,
            auth_failures=0,
            observation_successes=0,
            last_failure=None,
        )
    elif event is Event.AUTH_REJECTED:
        _require(state.phase is Phase.CANDIDATE_CONNECTING, "auth rejection requires connecting")
        failures = state.auth_failures + 1
        current = replace(state, auth_failures=failures, last_failure="authentication_rejected")
        result = (
            _fallback(current, policy, "authentication_rejected")
            if failures >= policy.auth_failure_threshold
            else current
        )
    elif event is Event.TRANSPORT_FAILURE:
        _require(
            state.phase
            in {Phase.CANDIDATE_CONNECTING, Phase.AUTHENTICATED_OBSERVATION, Phase.COMMITTED},
            "transport failure requires candidate activity",
        )
        result = _fallback(state, policy, "transport_unavailable")
    elif event is Event.OBSERVATION_OK:
        _require(
            state.phase is Phase.AUTHENTICATED_OBSERVATION,
            "observation success requires authenticated observation",
        )
        result = replace(
            state,
            observation_successes=state.observation_successes + 1,
            last_failure=None,
        )
    elif event is Event.OBSERVATION_FAILED:
        _require(
            state.phase is Phase.AUTHENTICATED_OBSERVATION,
            "observation failure requires authenticated observation",
        )
        result = _fallback(state, policy, "continuity_or_acl_failure")
    elif event is Event.ROLLBACK:
        result = _fallback(state, policy, "operator_rollback")
    elif event is Event.COMMIT:
        _require(commit_authorized, "commit requires explicit authorization")
        _require(
            state.phase is Phase.AUTHENTICATED_OBSERVATION,
            "commit requires authenticated observation",
        )
        _require(
            state.observation_successes >= policy.observation_success_threshold,
            "observation threshold has not been met",
        )
        _require(state.candidate is not None, "commit requires a candidate")
        result = replace(
            state,
            phase=Phase.COMMITTED,
            profile=Profile.CANDIDATE,
            committed_generation=state.candidate.generation,
            last_failure=None,
        )
    elif event is Event.LEASE_EXPIRED:
        _require(
            state.phase in {Phase.CANDIDATE_CONNECTING, Phase.AUTHENTICATED_OBSERVATION},
            "candidate lease expiry requires an uncommitted candidate",
        )
        result = _fallback(state, policy, "candidate_lease_expired")
    elif event is Event.RESTART:
        if state.phase is Phase.COMMITTED:
            result = replace(
                state,
                phase=Phase.CANDIDATE_CONNECTING,
                profile=Profile.CANDIDATE,
                auth_failures=0,
                observation_successes=0,
                retry_after_s=0,
                last_failure=None,
            )
        elif state.candidate is not None:
            result = replace(
                state,
                phase=Phase.FALLBACK_ANONYMOUS,
                profile=Profile.ANONYMOUS,
                observation_successes=0,
                retry_after_s=policy.retry_cooldown_s,
                last_failure=None,
            )
        else:
            result = initial_state()
    else:
        raise ModelError(f"unsupported event: {event}")
    result.validate(policy)
    return result


def ready_for_commit(state: State, policy: Policy) -> bool:
    state.validate(policy)
    return (
        state.phase is Phase.AUTHENTICATED_OBSERVATION
        and state.observation_successes >= policy.observation_success_threshold
    )


def public_diagnostics(state: State, policy: Policy) -> dict[str, object]:
    state.validate(policy)
    candidate = state.candidate
    report = {
        "schema": SCHEMA,
        "phase": state.phase.value,
        "active_profile": state.profile.value,
        "anonymous_fallback_present": True,
        "candidate_present": candidate is not None,
        "candidate_generation": candidate.generation if candidate else None,
        "candidate_secret_present": candidate is not None,
        "candidate_secret_fingerprint": candidate.secret_fingerprint if candidate else None,
        "auth_failure_count": state.auth_failures,
        "observation_success_count": state.observation_successes,
        "retry_after_s": state.retry_after_s,
        "committed_generation": state.committed_generation,
        "local_operation_healthy": state.local_operation_healthy,
        "last_failure_class": state.last_failure,
        "ready_for_commit": ready_for_commit(state, policy),
        "password_included": False,
        "secret_values_included": False,
        "anonymous_closure_enabled": False,
    }
    encoded = json.dumps(report, sort_keys=True)
    for forbidden in ("password=", '"password":', '"secret_value":'):
        _require(forbidden not in encoded, "diagnostics contain a forbidden secret field")
    return report


def _candidate() -> Candidate:
    return Candidate(1, "ghn_gh-n1-a9f2f8", "gh-n1-a9f2f8", "0123456789abcdef")


def _connecting(policy: Policy) -> State:
    staged = stage_candidate(initial_state(), _candidate(), policy)
    return transition(staged, Event.ACTIVATE, policy, activation_authorized=True)


def run_fault_matrix() -> dict[str, object]:
    policy = Policy()
    scenarios: list[dict[str, object]] = []

    observed = transition(_connecting(policy), Event.AUTH_OK, policy)
    for _ in range(policy.observation_success_threshold):
        observed = transition(observed, Event.OBSERVATION_OK, policy)
    committed = transition(observed, Event.COMMIT, policy, commit_authorized=True)
    scenarios.append({"scenario": "authenticated_happy_path", "passed": committed.phase is Phase.COMMITTED})

    rejected = _connecting(policy)
    for _ in range(policy.auth_failure_threshold):
        rejected = transition(rejected, Event.AUTH_REJECTED, policy)
    scenarios.append(
        {
            "scenario": "authentication_rejection_fallback",
            "passed": rejected.phase is Phase.FALLBACK_ANONYMOUS and rejected.candidate is not None,
        }
    )

    transport = transition(_connecting(policy), Event.TRANSPORT_FAILURE, policy)
    scenarios.append(
        {
            "scenario": "broker_unavailable_fallback",
            "passed": transport.phase is Phase.FALLBACK_ANONYMOUS and transport.auth_failures == 0,
        }
    )

    continuity = transition(observed, Event.OBSERVATION_FAILED, policy)
    scenarios.append(
        {"scenario": "continuity_failure_fallback", "passed": continuity.phase is Phase.FALLBACK_ANONYMOUS}
    )

    lease_expired = transition(_connecting(policy), Event.LEASE_EXPIRED, policy)
    scenarios.append(
        {
            "scenario": "uncommitted_candidate_lease_fallback",
            "passed": (
                lease_expired.phase is Phase.FALLBACK_ANONYMOUS
                and lease_expired.profile is Profile.ANONYMOUS
                and lease_expired.last_failure == "candidate_lease_expired"
            ),
        }
    )

    staged = stage_candidate(initial_state(), _candidate(), policy)
    staged_restart = transition(staged, Event.RESTART, policy)
    scenarios.append(
        {
            "scenario": "staged_restart_preserves_candidate",
            "passed": (
                staged_restart.phase is Phase.FALLBACK_ANONYMOUS
                and staged_restart.candidate == staged.candidate
            ),
        }
    )

    committed_restart = transition(committed, Event.RESTART, policy)
    scenarios.append(
        {
            "scenario": "committed_restart_uses_candidate_primary",
            "passed": committed_restart.phase is Phase.CANDIDATE_CONNECTING,
        }
    )

    diagnostics = public_diagnostics(rejected, policy)
    scenarios.append(
        {
            "scenario": "public_diagnostics_redacted",
            "passed": not diagnostics["password_included"] and not diagnostics["secret_values_included"],
        }
    )

    passed = all(item["passed"] is True for item in scenarios)
    return {
        "schema": MATRIX_SCHEMA,
        "status": "node_mqtt_auth_fallback_fault_matrix_passed" if passed else "failed",
        "policy": asdict(policy),
        "scenario_count": len(scenarios),
        "passed_scenario_count": sum(item["passed"] is True for item in scenarios),
        "scenarios": scenarios,
        "candidate_firmware_reference_model_validated": passed,
        "ready_for_candidate_firmware_build": passed,
        "ready_for_isolated_firmware_test": False,
        "ready_for_real_board_capability_test": False,
        "ready_for_node_credential_generation": False,
        "ready_for_live_apply": False,
        "ready_for_anonymous_closure": False,
        "anonymous_closure_enabled": False,
        "production_execution_invoked": False,
        "production_manager_upgraded": False,
        "homeassistant_storage_read": False,
        "node_credentials_delivered": False,
        "secret_values_included": False,
    }


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the node MQTT auth fallback reference model")
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args(argv)
    try:
        report = run_fault_matrix()
        _require(report["status"] == "node_mqtt_auth_fallback_fault_matrix_passed", "fault matrix failed")
        output = _canonical_json(report)
        if args.output_json:
            args.output_json.write_text(output + "\n", encoding="utf-8")
        print(output)
        return 0
    except (ModelError, OSError, UnicodeError) as error:
        print(f"Node MQTT auth fallback model failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
