from __future__ import annotations

from typing import Any, Protocol

from .t1_manager_identity_migration_production_runtime_probe import (
    ManagerProductionRuntimeProbe,
    ManagerProductionRuntimeProbeError,
    ManagerRuntimeProbeFailureCode,
    _read_json_payload,
)


class RuntimeProbe(Protocol):
    def capture_baseline(self) -> dict[str, object]: ...

    def verify_authenticated_identity(self, username: str, client_id: str) -> None: ...

    def verify_ingress_subscription(self) -> None: ...

    def verify_canonical_publication(self) -> None: ...

    def verify_availability_publication(self) -> None: ...

    def verify_discovery_publication(self) -> None: ...

    def verify_reconnect(self) -> None: ...

    def verify_existing_entities(self) -> None: ...

    def verify_legacy_anonymous_path(self) -> None: ...

    def postactivation_audit(self) -> dict[str, object]: ...


class RetainedRecoveryRuntimeProbe:
    """Accept fresh ingress or exact retained-canonical recovery evidence.

    The production manager subscribes to retained canonical telemetry at startup.
    Restoring that retained document republishes the exact Home Assistant Discovery
    document. This wrapper accepts the corresponding post-start log as evidence
    that the authenticated candidate consumed and validated canonical state, while
    keeping the existing fresh-ingress path as the preferred alternative.
    """

    def __init__(
        self,
        inner: RuntimeProbe,
        base: ManagerProductionRuntimeProbe,
    ) -> None:
        self.inner = inner
        self.base = base
        self._canonical_evidence_source: str | None = None

    def capture_baseline(self) -> dict[str, object]:
        return self.inner.capture_baseline()

    def verify_authenticated_identity(self, username: str, client_id: str) -> None:
        self.inner.verify_authenticated_identity(username, client_id)

    def verify_ingress_subscription(self) -> None:
        self.inner.verify_ingress_subscription()

    def verify_canonical_publication(self) -> None:
        fresh_marker = f"Accepted telemetry node={self.base.node_id} "
        recovery_marker = (
            f"Published Home Assistant discovery node={self.base.node_id} "
            f"topic={self.base.discovery_topic}"
        )
        deadline = self.base.monotonic() + self.base.telemetry_timeout_s
        evidence_source: str | None = None
        while True:
            document = self.base._inspect()
            _pid, started_at, log_path = self.base._validate_identity_binding(document)
            messages = self.base._log_messages(log_path, started_at)
            if any(fresh_marker in message for message in messages):
                evidence_source = "fresh_ingress"
                break
            if any(recovery_marker in message for message in messages):
                evidence_source = "retained_recovery"
                break
            if self.base.monotonic() >= deadline:
                raise ManagerProductionRuntimeProbeError(
                    "greenhouse-manager canonical recovery or fresh telemetry evidence timed out",
                    failure_code=(
                        ManagerRuntimeProbeFailureCode.PASSIVE_TELEMETRY_TIMED_OUT
                    ),
                )
            remaining = deadline - self.base.monotonic()
            self.base.sleeper(min(self.base.poll_interval_s, remaining))

        canonical = _read_json_payload(
            self.base.reader_factory().read(self.base.canonical_topic),
            "canonical telemetry",
        )
        if canonical.get("node_id") != self.base.node_id:
            raise ManagerProductionRuntimeProbeError(
                "canonical telemetry node_id does not match"
            )
        self._canonical_evidence_source = evidence_source
        self.base._checks["canonical_publication_verified"] = True

    def _availability_document(self) -> dict[str, Any]:
        document = _read_json_payload(
            self.base.reader_factory().read(self.base.availability_topic),
            "availability",
        )
        if document.get("node_id") != self.base.node_id:
            raise ManagerProductionRuntimeProbeError(
                "manager availability node_id does not match"
            )
        return document

    def verify_availability_publication(self) -> None:
        if self._canonical_evidence_source not in {
            "fresh_ingress",
            "retained_recovery",
        }:
            raise ManagerProductionRuntimeProbeError(
                "canonical evidence source is unavailable"
            )

        document = self._availability_document()
        state = document.get("state")
        if self._canonical_evidence_source == "fresh_ingress":
            if state != "online":
                raise ManagerProductionRuntimeProbeError(
                    "fresh ingress did not produce online availability"
                )
        elif state == "unavailable":
            self.base._wait_for_log(
                f"Published unavailable state topic={self.base.availability_topic}"
            )
            document = self._availability_document()
            if document.get("state") != "unavailable":
                raise ManagerProductionRuntimeProbeError(
                    "retained recovery unavailable state did not remain bound"
                )
        elif state != "online":
            raise ManagerProductionRuntimeProbeError(
                "retained recovery availability state is invalid"
            )

        self.base._checks["availability_publication_verified"] = True

    def verify_discovery_publication(self) -> None:
        self.inner.verify_discovery_publication()

    def verify_reconnect(self) -> None:
        self.inner.verify_reconnect()

    def verify_existing_entities(self) -> None:
        self.inner.verify_existing_entities()

    def verify_legacy_anonymous_path(self) -> None:
        self.inner.verify_legacy_anonymous_path()

    def postactivation_audit(self) -> dict[str, object]:
        return self.inner.postactivation_audit()


def _find_base_probe(probe: Any) -> ManagerProductionRuntimeProbe | None:
    candidate = probe
    seen: set[int] = set()
    for _depth in range(4):
        if isinstance(candidate, ManagerProductionRuntimeProbe):
            return candidate
        marker = id(candidate)
        if marker in seen:
            return None
        seen.add(marker)
        candidate = getattr(candidate, "inner", None)
        if candidate is None:
            return None
    return None


def wrap_manager_runtime_probe(probe: RuntimeProbe) -> RuntimeProbe:
    if isinstance(probe, RetainedRecoveryRuntimeProbe):
        return probe
    base = _find_base_probe(probe)
    if base is None:
        return probe
    return RetainedRecoveryRuntimeProbe(probe, base)
