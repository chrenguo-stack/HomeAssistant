from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from typing import Any, Protocol

from n3w_t1_core_updater_ha_data_evidence import HaProtectedDataEvidence
from n3w_t1_core_updater_v2_common import SHA256, UpdaterV2Error, canonical, sha256_bytes


HA_ACCEPTANCE_RULE = "HA_IMPACT_V1"
NATURAL_MONITORING_METHOD = "NATURAL_TELEMETRY_V1"
SELF_TEST_MONITORING_METHOD = "MAINTENANCE_SELF_TEST_V1"
MONITORING_METHODS = (NATURAL_MONITORING_METHOD, SELF_TEST_MONITORING_METHOD)
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
    monitoring_method: str | None = None


class HaAcceptanceObserver(Protocol):
    def capture_baseline(self, transaction: dict[str, Any]) -> HaAcceptanceBaseline | dict[str, str]:
        """Prove both checks on the running predecessor and bind the approved sample and methods."""
        ...

    def observe(
        self, transaction: dict[str, Any], check: str, *, fallback: bool,
    ) -> HaAcceptanceEvidence:
        """Observe the current target against the frozen check baseline and approved method."""
        ...

    def run_monitoring_self_test(self) -> HaAcceptanceEvidence:
        """Actively exercise the preverified maintenance path."""
        ...


class HaMonitoringEvidence(Protocol):
    def capture_baseline(self, transaction: dict[str, Any]) -> str:
        ...

    def observe(self, transaction: dict[str, Any], *, fallback: bool) -> HaAcceptanceEvidence:
        ...


class LocalHaAcceptanceObserver:
    def __init__(
        self, monitoring: HaMonitoringEvidence, protected_data: HaProtectedDataEvidence,
        *, monitoring_method: str | None = None,
        self_test: Callable[[], HaAcceptanceEvidence] | None = None,
    ) -> None:
        self.monitoring = monitoring
        self.protected_data = protected_data
        self.monitoring_method = monitoring_method
        self.self_test = self_test

    def capture_baseline(self, transaction: dict[str, Any]) -> HaAcceptanceBaseline:
        sample = self.protected_data.capture()
        method = self.monitoring_method
        try:
            monitoring_sha256 = self.monitoring.capture_baseline(transaction)
        except UpdaterV2Error:
            if self.self_test is None:
                raise
            evidence = self.run_monitoring_self_test()
            if evidence.verdict != "PASS" or evidence.sha256 is None:
                raise
            monitoring_sha256 = evidence.sha256
            method = SELF_TEST_MONITORING_METHOD
        return HaAcceptanceBaseline(
            checks={
                "monitoring_path": monitoring_sha256,
                "protected_data": sha256_bytes(canonical(sample)),
            },
            data_sample=sample,
            monitoring_method=method,
        )

    def observe(self, transaction: dict[str, Any], check: str, *, fallback: bool) -> HaAcceptanceEvidence:
        if check == "monitoring_path":
            return self.monitoring.observe(transaction, fallback=fallback)
        if check == "protected_data" and not fallback:
            sample = transaction["target_acceptance"]["data_sample"]
            verdict = self.protected_data.compare(sample)
            return HaAcceptanceEvidence(verdict, sha256_bytes(canonical(sample)) if verdict == "PASS" else None)
        return HaAcceptanceEvidence("EVIDENCE_UNAVAILABLE")

    def run_monitoring_self_test(self) -> HaAcceptanceEvidence:
        if self.self_test is not None:
            return self.self_test()
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
