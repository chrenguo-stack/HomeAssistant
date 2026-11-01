from __future__ import annotations

from datetime import UTC, datetime, timedelta

from .history_projection_aggregate import aggregate_projection
from .history_projection_contract import (
    AdapterDispatchResult,
    ProjectionAdapter,
    ProjectionBlockedError,
    ProjectionContractError,
    ProjectionRetryableError,
    ProjectionRunResult,
)
from .history_projection_store import ProjectionStore, ProjectionTask


class ProjectionRunner:
    """Claim, aggregate, dispatch, verify, and settle one C06-B1 job."""

    def __init__(
        self,
        *,
        store: ProjectionStore,
        adapter: ProjectionAdapter,
        worker_id: str,
        lease_seconds: int = 60,
        adapter_timeout_seconds: int = 30,
        retry_base_seconds: int = 10,
        retry_max_seconds: int = 3600,
    ) -> None:
        if not 1 <= retry_base_seconds <= retry_max_seconds <= 86_400:
            raise ValueError("retry delays must satisfy 1 <= base <= max <= 86400")
        if not 1 <= adapter_timeout_seconds < lease_seconds:
            raise ValueError("adapter timeout must be positive and shorter than the lease")
        self.store = store
        self.adapter = adapter
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.adapter_timeout_seconds = adapter_timeout_seconds
        self.retry_base_seconds = retry_base_seconds
        self.retry_max_seconds = retry_max_seconds

    @staticmethod
    def _utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("runner timestamps must be timezone-aware")
        return value.astimezone(UTC)

    def _retry_at(self, task: ProjectionTask, now: datetime) -> datetime:
        exponent = min(max(task.attempts - 1, 0), 30)
        delay = min(self.retry_base_seconds * (2**exponent), self.retry_max_seconds)
        return now + timedelta(seconds=delay)

    def _retry(
        self,
        task: ProjectionTask,
        *,
        code: str,
        detail: str,
        now: datetime,
        projection_hash: str | None = None,
    ) -> ProjectionRunResult:
        settled = self.store.mark_retry(
            task,
            error_code=code,
            error=detail,
            next_attempt_at=self._retry_at(task, now),
            now=now,
        )
        return ProjectionRunResult(
            status="retry" if settled else "stale",
            task=task,
            projection_hash=projection_hash,
            code=code,
            detail=detail,
        )

    def _blocked(
        self,
        task: ProjectionTask,
        *,
        code: str,
        detail: str,
        now: datetime,
        projection_hash: str | None = None,
    ) -> ProjectionRunResult:
        settled = self.store.mark_blocked(
            task, error_code=code, error=detail, now=now
        )
        return ProjectionRunResult(
            status="blocked" if settled else "stale",
            task=task,
            projection_hash=projection_hash,
            code=code,
            detail=detail,
        )

    def run_once(
        self,
        *,
        now: datetime | None = None,
        settled_at: datetime | None = None,
    ) -> ProjectionRunResult:
        claim_at = self._utc(now or datetime.now(UTC))
        task = self.store.claim_next(
            worker_id=self.worker_id,
            now=claim_at,
            lease_seconds=self.lease_seconds,
        )
        if task is None:
            return ProjectionRunResult(status="idle")

        def phase_time() -> datetime:
            return self._utc(
                settled_at
                if settled_at is not None
                else (datetime.now(UTC) if now is None else claim_at)
            )

        try:
            batch = aggregate_projection(task, self.store.load_records(task))
        except ProjectionContractError as exc:
            failure_at = phase_time()
            if failure_at >= task.lease_until:
                return ProjectionRunResult(
                    status="stale",
                    task=task,
                    code="lease_expired_during_projection_build",
                    detail="projection build finished after the finite lease expired",
                )
            return self._blocked(
                task,
                code="projection_contract_error",
                detail=str(exc),
                now=failure_at,
            )
        except Exception as exc:  # noqa: BLE001 - host boundary must retain the job
            failure_at = phase_time()
            if failure_at >= task.lease_until:
                return ProjectionRunResult(
                    status="stale",
                    task=task,
                    code="lease_expired_during_projection_build",
                    detail="projection build failed after the finite lease expired",
                )
            return self._retry(
                task,
                code="projection_build_failed",
                detail=f"{type(exc).__name__}: {exc}",
                now=failure_at,
            )

        dispatch_at = self._utc(
            datetime.now(UTC) if now is None else claim_at
        )
        if not self.store.claim_is_current(task, now=dispatch_at):
            return ProjectionRunResult(
                status="stale",
                task=task,
                projection_hash=batch.projection_hash,
                code="claim_stale_before_dispatch",
            )

        try:
            result = self.adapter.dispatch(batch)
        except ProjectionBlockedError as exc:
            result = AdapterDispatchResult(
                status="blocked", code="adapter_blocked", detail=str(exc)
            )
        except ProjectionRetryableError as exc:
            result = AdapterDispatchResult(
                status="retry", code="adapter_retryable", detail=str(exc)
            )
        except Exception as exc:  # noqa: BLE001 - adapter failures remain retryable
            result = AdapterDispatchResult(
                status="retry",
                code="adapter_dispatch_failed",
                detail=f"{type(exc).__name__}: {exc}",
            )

        finished = phase_time()
        if finished < dispatch_at:
            raise ValueError("settled_at must not precede adapter dispatch")
        elapsed = (finished - dispatch_at).total_seconds()
        if finished >= task.lease_until:
            return ProjectionRunResult(
                status="stale",
                task=task,
                projection_hash=batch.projection_hash,
                code="lease_expired_during_dispatch",
                detail="adapter returned after the finite lease expired",
            )
        if elapsed > self.adapter_timeout_seconds:
            return self._retry(
                task,
                code="adapter_timeout_exceeded",
                detail="adapter exceeded the frozen dispatch timeout",
                now=finished,
                projection_hash=batch.projection_hash,
            )

        if result.status == "retry":
            return self._retry(
                task,
                code=result.code or "adapter_retry",
                detail=result.detail or "adapter requested retry",
                now=finished,
                projection_hash=batch.projection_hash,
            )
        if result.status == "blocked":
            return self._blocked(
                task,
                code=result.code or "adapter_blocked",
                detail=result.detail or "adapter blocked the projection",
                now=finished,
                projection_hash=batch.projection_hash,
            )
        if result.status != "verified":
            return self._retry(
                task,
                code="adapter_status_invalid",
                detail=f"unsupported adapter status: {result.status!r}",
                now=finished,
                projection_hash=batch.projection_hash,
            )
        if result.monotonic_revision_enforced is not True:
            return self._blocked(
                task,
                code="adapter_monotonic_revision_unverified",
                detail="adapter did not enforce the monotonic revision contract",
                now=finished,
                projection_hash=batch.projection_hash,
            )
        if result.verified_idempotency_key != batch.idempotency_key:
            return self._blocked(
                task,
                code="adapter_idempotency_key_mismatch",
                detail="adapter did not verify the exact idempotency key",
                now=finished,
                projection_hash=batch.projection_hash,
            )
        if result.verified_revision != batch.revision:
            return self._blocked(
                task,
                code="adapter_revision_mismatch",
                detail="adapter did not verify the exact projection revision",
                now=finished,
                projection_hash=batch.projection_hash,
            )
        if result.verified_projection_hash != batch.projection_hash:
            return self._blocked(
                task,
                code="adapter_hash_mismatch",
                detail="adapter did not verify the exact projection hash",
                now=finished,
                projection_hash=batch.projection_hash,
            )

        completed = self.store.mark_completed(
            task,
            projection_hash=batch.projection_hash,
            payload_json=batch.payload_json,
            adapter_kind=self.adapter.kind,
            adapter_version=self.adapter.version,
            now=finished,
        )
        return ProjectionRunResult(
            status="completed" if completed else "stale",
            task=task,
            projection_hash=batch.projection_hash,
        )
