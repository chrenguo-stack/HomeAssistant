from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from n3w_t1_core_updater_ha_data_evidence import HaProtectedDataEvidence
from n3w_t1_core_updater_v2_common import SHA256, canonical, sha256_bytes


HA_ACCEPTANCE_RULE = "HA_IMPACT_V1"
HA_ACCEPTANCE_ATTEMPTS = 3
# The HA-only upgrade also stops Manager and remounts both application data roots.
HA_ACCEPTANCE_CHECKS = ("monitoring_path", "protected_data")


@dataclass(frozen=True, slots=True)
class HaAcceptanceEvidence:
    verdict: str
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class HaAcceptanceBaseline:
    checks: dict[str, str]
    data_sample: dict[str, Any]


class HaAcceptanceObserver(Protocol):
    def capture_baseline(self, transaction: dict[str, Any]) -> HaAcceptanceBaseline | dict[str, str]:
        """Prove both checks on the running predecessor and bind the approved sample and methods."""
        ...

    def observe(
        self, transaction: dict[str, Any], check: str, *, fallback: bool,
    ) -> HaAcceptanceEvidence:
        """Observe the current target against the frozen check baseline and approved method."""
        ...


class HaMonitoringEvidence(Protocol):
    def capture_baseline(self, transaction: dict[str, Any]) -> str:
        ...

    def observe(self, transaction: dict[str, Any], *, fallback: bool) -> HaAcceptanceEvidence:
        ...


class LocalHaAcceptanceObserver:
    def __init__(self, monitoring: HaMonitoringEvidence, protected_data: HaProtectedDataEvidence) -> None:
        self.monitoring = monitoring
        self.protected_data = protected_data

    def capture_baseline(self, transaction: dict[str, Any]) -> HaAcceptanceBaseline:
        sample = self.protected_data.capture()
        return HaAcceptanceBaseline(
            checks={
                "monitoring_path": self.monitoring.capture_baseline(transaction),
                "protected_data": sha256_bytes(canonical(sample)),
            },
            data_sample=sample,
        )

    def observe(self, transaction: dict[str, Any], check: str, *, fallback: bool) -> HaAcceptanceEvidence:
        if check == "monitoring_path":
            return self.monitoring.observe(transaction, fallback=fallback)
        if check == "protected_data" and not fallback:
            sample = transaction["target_acceptance"]["data_sample"]
            verdict = self.protected_data.compare(sample)
            return HaAcceptanceEvidence(verdict, sha256_bytes(canonical(sample)) if verdict == "PASS" else None)
        return HaAcceptanceEvidence("EVIDENCE_UNAVAILABLE")


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
