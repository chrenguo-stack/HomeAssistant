from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
import re

SCHEMA = "gh.n3w.p4.b1i1.inline/1"
JOURNAL_NAME = "b1i1-private-transaction.json"
MANAGER_NAME = "greenhouse-manager"
BROKER_NAME = "n3wfc4-broker-1"
PARKED_NAME = "greenhouse-manager-p4-b1i1-parked"
FAILED_NAME = "greenhouse-manager-p4-b1i1-failed"
SHADOW_NAME = "greenhouse-manager-p4-b1i1-shadow"

FRESH_RW = (
    "/var/lib/greenhouse-manager-registration",
    "/var/lib/greenhouse-manager/n3w",
    "/var/lib/greenhouse-manager/n3w/relay-keys",
)
EXISTING_RO = (
    "/run/secrets/provisioning_password",
    "/run/secrets/broker-ca.pem",
    "/run/secrets/gh_manager_mqtt_password",
)
REQUIRED_HEALTH = ("healthz", "tcp47112", "udp47111", "pairing_ipc", "tls8883")
TERMINAL = frozenset(("FINALIZED", "FAIL_ROLLED_BACK", "FAIL_ROLLBACK_INCOMPLETE", "UNKNOWN_FROZEN", "PREPARE_STOP"))
MUTATING = frozenset(("OLD_STOP_INTENT", "OLD_PARK_INTENT", "CANDIDATE_CREATE_INTENT", "CANDIDATE_START_INTENT", "POSTFLIGHT_INTENT", "COMMIT_INTENT"))


class GateStop(RuntimeError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise GateStop(code)


@dataclass(frozen=True)
class Authority:
    old_manager_id: str
    old_image: str
    broker_id: str
    broker_started_at: str
    broker_restart_count: int
    candidate_image_id: str
    source_ref: str
    fresh_mounts: tuple[str, ...]
    ro_mounts: tuple[str, ...]

    def validate(self) -> None:
        for value in (
            self.old_manager_id, self.old_image, self.broker_id,
            self.broker_started_at, self.candidate_image_id, self.source_ref,
        ):
            require(isinstance(value, str) and bool(value), "EMPTY_AUTHORITY")
        require(type(self.broker_restart_count) is int and self.broker_restart_count >= 0, "BROKER_COUNT_INVALID")
        require(self.fresh_mounts == FRESH_RW, "FRESH_RW_MOUNT_DRIFT")
        require(self.ro_mounts == EXISTING_RO, "RO_SECRET_MOUNT_DRIFT")
        require(re.fullmatch(r"[0-9a-f]{40}", self.source_ref) is not None, "SOURCE_REF_NOT_EXACT_SHA")


class Operations(Protocol):
    def preflight(self, authority: Authority) -> None: ...
    def prepare_fresh_and_shadow(self, authority: Authority) -> None: ...
    def verify_pre_stop(self, authority: Authority) -> None: ...
    def stop_old(self, authority: Authority) -> None: ...
    def park_old(self, authority: Authority) -> None: ...
    def create_candidate(self, authority: Authority, token: str) -> str: ...
    def inspect_candidate(self, authority: Authority, token: str) -> str | None: ...
    def verify_candidate_ownership(self, authority: Authority, token: str, candidate_id: str) -> bool: ...
    def start_candidate(self, authority: Authority, candidate_id: str) -> None: ...
    def verify_candidate_health(self, candidate_id: str, checks: tuple[str, ...]) -> None: ...
    def verify_fresh_zero_state(self, authority: Authority) -> None: ...
    def verify_candidate_mounts_and_security(self, authority: Authority, candidate_id: str) -> None: ...
    def verify_broker_ha_r5(self, authority: Authority) -> None: ...
    def verify_old_stopped_and_parked(self, authority: Authority) -> None: ...
    def quarantine_owned_candidate(self, authority: Authority, candidate_id: str) -> None: ...
    def restore_old_exact_id(self, authority: Authority) -> None: ...
    def verify_old_healthy_and_unchanged(self, authority: Authority) -> None: ...
    def verify_finalized(self, authority: Authority, candidate_id: str) -> None: ...
