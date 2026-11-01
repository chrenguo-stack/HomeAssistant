#!/usr/bin/env python3
"""Pure host model for H3/N2 Stage 2D-9 G3 PREPARE_CANDIDATE.

This module contains no device, serial, network, Broker, eFuse or production
integration. It models the one allowed durable transition for Stage 2D-9:
EMPTY -> PREPARED while the active profile remains unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
import hashlib
import json


class PrepareError(RuntimeError):
    """Raised when the model must fail closed."""


class DurablePhase(str, Enum):
    EMPTY = "empty"
    PROFILE_WRITTEN = "profile_written"
    PREPARED_COMMITTED = "prepared_committed"


@dataclass(frozen=True)
class ProfileState:
    active_generation: int = 0
    candidate_generation: int = 0
    candidate_state: str = "EMPTY"
    active_digest: str = ""
    candidate_digest: str = ""
    writes: int = 0
    active_session: bool = False
    candidate_session: bool = False
    prepare_authorization_consumed: bool = False
    activate_authorization_present: bool = False
    cleanup_authorization_present: bool = False


@dataclass(frozen=True)
class PrepareAuthorization:
    action: str
    active_generation: int
    candidate_generation: int
    candidate_digest: str
    one_shot: bool
    replay_permitted: bool
    authorization_id: str


@dataclass
class DurableStore:
    phase: DurablePhase = DurablePhase.EMPTY
    candidate_generation: int = 0
    candidate_digest: str = ""
    authorization_id: str = ""
    write_count: int = 0

    def write_profile(self, authorization: PrepareAuthorization) -> None:
        self.phase = DurablePhase.PROFILE_WRITTEN
        self.candidate_generation = authorization.candidate_generation
        self.candidate_digest = authorization.candidate_digest
        self.authorization_id = authorization.authorization_id
        self.write_count += 1

    def commit_prepared(self) -> None:
        if self.phase is not DurablePhase.PROFILE_WRITTEN:
            raise PrepareError("candidate profile must be written before commit")
        self.phase = DurablePhase.PREPARED_COMMITTED
        self.write_count += 1

    def recover(self, base: ProfileState) -> ProfileState:
        if self.phase is DurablePhase.PREPARED_COMMITTED:
            return replace(
                base,
                candidate_generation=self.candidate_generation,
                candidate_state="PREPARED",
                candidate_digest=self.candidate_digest,
                writes=self.write_count,
                prepare_authorization_consumed=True,
            )
        return replace(
            base,
            candidate_generation=0,
            candidate_state="EMPTY",
            candidate_digest="",
            writes=self.write_count,
            prepare_authorization_consumed=False,
        )


def digest_profile(profile: dict[str, object]) -> str:
    canonical = json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def validate_authorization(
    state: ProfileState,
    authorization: PrepareAuthorization,
    *,
    key_loaded: bool,
) -> None:
    if not key_loaded:
        raise PrepareError("volatile test key not loaded")
    if authorization.action != "PREPARE_CANDIDATE":
        raise PrepareError("action is not PREPARE_CANDIDATE")
    if not authorization.one_shot or authorization.replay_permitted:
        raise PrepareError("authorization is not exact one-shot")
    if not authorization.authorization_id:
        raise PrepareError("authorization id missing")
    if state.active_generation != authorization.active_generation:
        raise PrepareError("active generation binding mismatch")
    if state.candidate_generation != 0 or state.candidate_state != "EMPTY":
        raise PrepareError("candidate slot is not empty")
    if authorization.candidate_generation != state.active_generation + 1:
        raise PrepareError("candidate generation must be active generation plus one")
    if len(authorization.candidate_digest) != 64:
        raise PrepareError("candidate digest must be sha256")
    int(authorization.candidate_digest, 16)
    if state.active_session or state.candidate_session:
        raise PrepareError("MQTT session must remain absent")
    if state.activate_authorization_present or state.cleanup_authorization_present:
        raise PrepareError("activate or cleanup authorization present")
    if state.prepare_authorization_consumed:
        raise PrepareError("prepare authorization already consumed")


def prepare_candidate(
    state: ProfileState,
    authorization: PrepareAuthorization,
    store: DurableStore,
    *,
    key_loaded: bool,
    fail_after: str | None = None,
) -> ProfileState:
    """Execute the modeled one-shot transition.

    ``fail_after`` is a host-test-only failure injection point. The model never
    retries PREPARE. Recovery returns EMPTY unless the PREPARED commit is
    durable, and always leaves the active profile unchanged.
    """
    validate_authorization(state, authorization, key_loaded=key_loaded)

    if fail_after == "authorization":
        raise PrepareError("injected failure after authorization validation")

    store.write_profile(authorization)
    if fail_after == "profile_write":
        raise PrepareError("injected failure after candidate profile write")

    store.commit_prepared()
    if fail_after == "prepared_commit":
        raise PrepareError("injected failure after prepared commit")

    recovered = store.recover(state)
    if recovered.active_generation != state.active_generation:
        raise PrepareError("active generation changed")
    if recovered.active_digest != state.active_digest:
        raise PrepareError("active digest changed")
    if recovered.candidate_state != "PREPARED":
        raise PrepareError("candidate state is not PREPARED")
    if recovered.candidate_generation != authorization.candidate_generation:
        raise PrepareError("candidate generation verification failed")
    if recovered.candidate_digest != authorization.candidate_digest:
        raise PrepareError("candidate digest verification failed")
    if recovered.active_session or recovered.candidate_session:
        raise PrepareError("MQTT session unexpectedly present")
    return recovered
