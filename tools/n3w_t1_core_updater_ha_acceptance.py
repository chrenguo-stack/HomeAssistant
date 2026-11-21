from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from n3w_t1_core_updater_v2_common import SHA256


HA_ACCEPTANCE_RULE = "HA_IMPACT_V1"
HA_ACCEPTANCE_ATTEMPTS = 3
# The HA-only upgrade also stops Manager and remounts both application data roots.
HA_ACCEPTANCE_CHECKS = ("monitoring_path", "protected_data")


@dataclass(frozen=True, slots=True)
class HaAcceptanceEvidence:
    verdict: str
    sha256: str | None = None


class HaAcceptanceObserver(Protocol):
    def capture_baseline(self, transaction: dict[str, Any]) -> dict[str, str]:
        """Prove both checks on the running predecessor and bind the approved sample and methods."""
        ...

    def observe(
        self, transaction: dict[str, Any], check: str, *, fallback: bool,
    ) -> HaAcceptanceEvidence:
        """Observe the current target against the frozen check baseline and approved method."""
        ...


def valid_evidence_set(evidence: Any) -> bool:
    return (
        isinstance(evidence, dict) and set(evidence) == set(HA_ACCEPTANCE_CHECKS)
        and all(isinstance(value, str) and SHA256.fullmatch(value) for value in evidence.values())
    )


def expected_target_images(document: dict[str, Any]) -> dict[str, Any]:
    return {
        **document["predecessor_start"]["images"],
        "homeassistant": {
            "reference": document["target_image_ref"],
            "runtime_id": document["target_loaded_image_id"],
        },
    }
