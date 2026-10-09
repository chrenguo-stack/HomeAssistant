from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from b1i1_contract import GateStop, require


@dataclass(frozen=True)
class Budget:
    total: float
    forward_after_old_stop: float
    rollback_reserve: float
    evidence_reserve: float
    outer_grace: float

    def validate(self) -> None:
        for value in (
            self.total, self.forward_after_old_stop, self.rollback_reserve,
            self.evidence_reserve, self.outer_grace,
        ):
            require(type(value) in (int, float) and 0 < value < 10000, "BUDGET_INVALID")
        require(
            self.total > self.forward_after_old_stop + self.rollback_reserve
            + self.evidence_reserve + self.outer_grace,
            "BUDGET_OVERCOMMITTED",
        )


class Deadline:
    def __init__(self, budget: Budget, now: Callable[[], float]):
        budget.validate()
        self.budget = budget
        self.now = now
        self.end = now() + budget.total
        self.in_rollback = False

    def before_old_stop(self) -> None:
        self.require_forward(self.budget.forward_after_old_stop)

    def require_forward(self, minimum: float = 0) -> None:
        require(not self.in_rollback, "FORWARD_AFTER_ROLLBACK_FORBIDDEN")
        require(
            self.end - self.now() >= self.budget.rollback_reserve
            + self.budget.evidence_reserve + minimum,
            "INSUFFICIENT_ROLLBACK_BUDGET",
        )

    def forward_cutoff(self) -> float:
        self.require_forward()
        return self.end - self.budget.rollback_reserve - self.budget.evidence_reserve

    def enter_rollback(self) -> None:
        self.in_rollback = True

    def rollback_cutoff(self) -> float:
        require(self.in_rollback, "ROLLBACK_NOT_STARTED")
        cutoff = self.end - self.budget.evidence_reserve
        require(cutoff > self.now(), "ROLLBACK_TIME_BUDGET_EXHAUSTED")
        return cutoff

    def rollback_time_remaining(self) -> float:
        require(self.in_rollback, "ROLLBACK_NOT_STARTED")
        return max(0.0, self.end - self.now() - self.budget.evidence_reserve)


@dataclass(frozen=True)
class HostOwnedPlan:
    service_name: str
    user_authorization: str
    source_ref: str
    stage_name: str
    journal_name: str
    restart: str = "no"

    def validate(self) -> None:
        require(self.service_name.startswith("n3w-p4-b1i1-"), "HOST_OWNER_SERVICE_NOT_ISOLATED")
        require(self.stage_name.startswith("p4-manager-b1i1-"), "HOST_STAGE_NOT_ISOLATED")
        require(self.journal_name == "b1i1-private-transaction.json", "HOST_JOURNAL_NOT_ISOLATED")
        require(bool(self.user_authorization) and bool(self.source_ref), "HOST_SOURCE_AUTH_MISSING")
        require(self.restart == "no", "AUTOMATIC_REPLAY_FORBIDDEN")


def require_host_owned_transaction(*, ssh_is_owner: bool, host_unit_verified: bool) -> None:
    require(ssh_is_owner is False and host_unit_verified is True, "HOST_OWNER_NOT_PROVEN")
