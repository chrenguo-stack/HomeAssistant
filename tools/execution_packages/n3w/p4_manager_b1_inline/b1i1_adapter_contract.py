from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, TypeVar

from b1i1_contract import GateStop, require

T = TypeVar("T")


@dataclass(frozen=True)
class OperationWindow:
    cutoff: float
    now: Callable[[], float]
    phase: str

    def remaining(self, per_command_max: float) -> float:
        require(
            isinstance(self.phase, str) and self.phase != "",
            "OPERATION_PHASE_MISSING",
        )
        require(
            type(per_command_max) in (float, int)
            and math.isfinite(per_command_max) and per_command_max > 0,
            "COMMAND_TIMEOUT_UNBOUNDED",
        )
        left = self.cutoff - self.now()
        require(math.isfinite(left) and left > 0, "ACTION_DEADLINE_ALREADY_EXPIRED")
        return min(left, per_command_max)

    def invoke(
        self,
        runner: Callable[[float], T],
        *,
        per_command_max: float,
    ) -> T:
        timeout = self.remaining(per_command_max)
        try:
            result = runner(timeout)
        except TimeoutError as error:
            raise GateStop("ACTION_TIMEOUT_RUNTIME_UNKNOWN") from error
        require(
            self.cutoff >= self.now(),
            "ACTION_COMPLETED_AFTER_DEADLINE_RUNTIME_UNKNOWN",
        )
        return result


def enforce_forward_and_recovery_windows(
    *,
    forward_cutoff: float,
    recovery_cutoff: float,
    evidence_cutoff: float,
    host_hard_cutoff: float,
) -> None:
    for value in (
        forward_cutoff, recovery_cutoff, evidence_cutoff, host_hard_cutoff
    ):
        require(
            type(value) in (int, float) and math.isfinite(value),
            "ABSOLUTE_DEADLINE_INVALID",
        )
    require(
        forward_cutoff < recovery_cutoff < evidence_cutoff < host_hard_cutoff,
        "HOST_DEADLINE_ORDER_UNSAFE",
    )
