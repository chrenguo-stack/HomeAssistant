from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from .const import STORAGE_VERSION
from .protocol import ProjectionRequest, canonical_json

LedgerState = Literal["pending", "verified"]
DecisionStatus = Literal["accepted", "verified", "resume", "retry", "blocked"]


class LedgerError(RuntimeError):
    """Base error for the target-side monotonic ledger."""


class LedgerCorruptionError(LedgerError):
    """Raised when persisted state cannot be trusted and processing must stop."""


class LedgerStore(Protocol):
    async def async_load(self) -> dict[str, Any] | None:
        """Load the complete JSON-serializable ledger document."""

    async def async_save(self, document: dict[str, Any]) -> None:
        """Atomically replace the complete ledger document."""


@dataclass(frozen=True, slots=True)
class ResolvedSeries:
    measurement_key: str
    entity_unique_id: str
    entity_id: str
    unit_of_measurement: str
    mean: float
    minimum: float
    maximum: float

    def as_document(self) -> dict[str, Any]:
        return {
            "measurement_key": self.measurement_key,
            "entity_unique_id": self.entity_unique_id,
            "entity_id": self.entity_id,
            "unit_of_measurement": self.unit_of_measurement,
            "mean": self.mean,
            "minimum": self.minimum,
            "maximum": self.maximum,
        }

    @classmethod
    def from_document(cls, document: Any) -> ResolvedSeries:
        keys = {
            "measurement_key",
            "entity_unique_id",
            "entity_id",
            "unit_of_measurement",
            "mean",
            "minimum",
            "maximum",
        }
        if not isinstance(document, dict) or set(document) != keys:
            raise LedgerCorruptionError("resolved series has an invalid shape")
        for field_name in (
            "measurement_key",
            "entity_unique_id",
            "entity_id",
            "unit_of_measurement",
        ):
            if not isinstance(document[field_name], str) or not document[field_name]:
                raise LedgerCorruptionError(f"resolved series {field_name} is invalid")
        values: dict[str, float] = {}
        for field_name in ("mean", "minimum", "maximum"):
            value = document[field_name]
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise LedgerCorruptionError(f"resolved series {field_name} is invalid")
            values[field_name] = float(value)
        if not values["minimum"] <= values["mean"] <= values["maximum"]:
            raise LedgerCorruptionError("resolved series min/mean/max ordering is invalid")
        return cls(
            measurement_key=document["measurement_key"],
            entity_unique_id=document["entity_unique_id"],
            entity_id=document["entity_id"],
            unit_of_measurement=document["unit_of_measurement"],
            mean=values["mean"],
            minimum=values["minimum"],
            maximum=values["maximum"],
        )


@dataclass(frozen=True, slots=True)
class LedgerEntry:
    system_id: str
    idempotency_key: str
    revision: int
    projection_hash: str
    projection: dict[str, Any]
    state: LedgerState
    accepted_at: str
    last_reconciled_at: str | None = None
    verified_at: str | None = None
    resolved_series: tuple[ResolvedSeries, ...] = ()
    last_error_code: str | None = None
    reconcile_attempts: int = 0

    def as_document(self) -> dict[str, Any]:
        return {
            "system_id": self.system_id,
            "idempotency_key": self.idempotency_key,
            "revision": self.revision,
            "projection_hash": self.projection_hash,
            "projection": deepcopy(self.projection),
            "state": self.state,
            "accepted_at": self.accepted_at,
            "last_reconciled_at": self.last_reconciled_at,
            "verified_at": self.verified_at,
            "resolved_series": [item.as_document() for item in self.resolved_series],
            "last_error_code": self.last_error_code,
            "reconcile_attempts": self.reconcile_attempts,
        }

    @classmethod
    def from_document(cls, key: str, document: Any) -> LedgerEntry:
        required = {
            "system_id",
            "idempotency_key",
            "revision",
            "projection_hash",
            "projection",
            "state",
            "accepted_at",
            "last_reconciled_at",
            "verified_at",
            "resolved_series",
            "last_error_code",
            "reconcile_attempts",
        }
        if not isinstance(document, dict) or set(document) != required:
            raise LedgerCorruptionError(f"ledger entry {key!r} has an invalid shape")
        if document["idempotency_key"] != key:
            raise LedgerCorruptionError("ledger key does not match entry idempotency_key")
        if document["state"] not in {"pending", "verified"}:
            raise LedgerCorruptionError("ledger entry state is invalid")
        if type(document["revision"]) is not int or document["revision"] < 1:
            raise LedgerCorruptionError("ledger entry revision is invalid")
        if not isinstance(document["projection_hash"], str) or len(document["projection_hash"]) != 64:
            raise LedgerCorruptionError("ledger entry projection_hash is invalid")
        if not isinstance(document["projection"], dict):
            raise LedgerCorruptionError("ledger entry projection is invalid")
        if canonical_json(document["projection"]) == "":
            raise LedgerCorruptionError("ledger entry projection cannot be empty")
        for field_name in ("system_id", "accepted_at"):
            if not isinstance(document[field_name], str) or not document[field_name]:
                raise LedgerCorruptionError(f"ledger entry {field_name} is invalid")
        for field_name in ("last_reconciled_at", "verified_at", "last_error_code"):
            value = document[field_name]
            if value is not None and not isinstance(value, str):
                raise LedgerCorruptionError(f"ledger entry {field_name} is invalid")
        if type(document["reconcile_attempts"]) is not int or document["reconcile_attempts"] < 0:
            raise LedgerCorruptionError("ledger entry reconcile_attempts is invalid")
        resolved = document["resolved_series"]
        if not isinstance(resolved, list):
            raise LedgerCorruptionError("ledger entry resolved_series is invalid")
        resolved_series = tuple(ResolvedSeries.from_document(item) for item in resolved)
        if document["state"] == "verified" and not document["verified_at"]:
            raise LedgerCorruptionError("verified ledger entry has no verified_at timestamp")
        if document["state"] == "pending" and document["verified_at"] is not None:
            raise LedgerCorruptionError("pending ledger entry cannot have verified_at")
        return cls(
            system_id=document["system_id"],
            idempotency_key=document["idempotency_key"],
            revision=document["revision"],
            projection_hash=document["projection_hash"],
            projection=deepcopy(document["projection"]),
            state=document["state"],
            accepted_at=document["accepted_at"],
            last_reconciled_at=document["last_reconciled_at"],
            verified_at=document["verified_at"],
            resolved_series=resolved_series,
            last_error_code=document["last_error_code"],
            reconcile_attempts=document["reconcile_attempts"],
        )


@dataclass(frozen=True, slots=True)
class LedgerDecision:
    status: DecisionStatus
    code: str
    entry: LedgerEntry | None


@dataclass(slots=True)
class MemoryLedgerStore:
    document: dict[str, Any] | None = None
    saves: int = 0

    async def async_load(self) -> dict[str, Any] | None:
        return deepcopy(self.document)

    async def async_save(self, document: dict[str, Any]) -> None:
        self.document = deepcopy(document)
        self.saves += 1


@dataclass(slots=True)
class TargetLedger:
    store: LedgerStore
    _entries: dict[str, LedgerEntry] = field(default_factory=dict, init=False, repr=False)
    _loaded: bool = field(default=False, init=False, repr=False)
    _locks: dict[str, asyncio.Lock] = field(default_factory=dict, init=False, repr=False)
    _locks_guard: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    async def async_load(self) -> None:
        document = await self.store.async_load()
        if document is None:
            self._entries = {}
            self._loaded = True
            return
        if not isinstance(document, dict) or set(document) != {
            "storage_schema_version",
            "entries",
        }:
            raise LedgerCorruptionError("target ledger root has an invalid shape")
        if document["storage_schema_version"] != STORAGE_VERSION:
            raise LedgerCorruptionError("unsupported target ledger storage schema version")
        raw_entries = document["entries"]
        if not isinstance(raw_entries, dict):
            raise LedgerCorruptionError("target ledger entries must be an object")
        loaded: dict[str, LedgerEntry] = {}
        for key, raw_entry in raw_entries.items():
            if not isinstance(key, str) or not key:
                raise LedgerCorruptionError("target ledger contains an invalid key")
            loaded[key] = LedgerEntry.from_document(key, raw_entry)
        self._entries = loaded
        self._loaded = True

    def _require_loaded(self) -> None:
        if not self._loaded:
            raise LedgerError("target ledger must be loaded before use")

    async def _lock_for(self, key: str) -> asyncio.Lock:
        async with self._locks_guard:
            return self._locks.setdefault(key, asyncio.Lock())

    async def _save(self) -> None:
        document = {
            "storage_schema_version": STORAGE_VERSION,
            "entries": {
                key: entry.as_document() for key, entry in sorted(self._entries.items())
            },
        }
        await self.store.async_save(document)

    def read(self, idempotency_key: str) -> LedgerEntry | None:
        self._require_loaded()
        return self._entries.get(idempotency_key)

    def snapshot(self) -> dict[str, LedgerEntry]:
        self._require_loaded()
        return dict(self._entries)

    @staticmethod
    def _same_tuple(entry: LedgerEntry, request: ProjectionRequest) -> bool:
        return (
            entry.revision == request.revision
            and entry.projection_hash == request.projection_hash
            and canonical_json(entry.projection) == canonical_json(request.projection)
        )

    async def async_prepare(self, request: ProjectionRequest, *, accepted_at: str) -> LedgerDecision:
        self._require_loaded()
        lock = await self._lock_for(request.idempotency_key)
        async with lock:
            existing = self._entries.get(request.idempotency_key)
            if existing is not None:
                if request.revision < existing.revision:
                    return LedgerDecision("blocked", "target_newer_revision", existing)
                if request.revision == existing.revision:
                    if not self._same_tuple(existing, request):
                        return LedgerDecision(
                            "blocked", "target_same_revision_hash_conflict", existing
                        )
                    if existing.state == "verified":
                        return LedgerDecision("verified", "verified_idempotent_readback", existing)
                    return LedgerDecision("resume", "resume_pending", existing)
                if existing.state == "pending":
                    return LedgerDecision("retry", "prior_revision_pending", existing)
            entry = LedgerEntry(
                system_id=request.system_id,
                idempotency_key=request.idempotency_key,
                revision=request.revision,
                projection_hash=request.projection_hash,
                projection=deepcopy(request.projection),
                state="pending",
                accepted_at=accepted_at,
            )
            self._entries[request.idempotency_key] = entry
            await self._save()
            code = "accepted_new_target" if existing is None else "accepted_higher_revision"
            return LedgerDecision("accepted", code, entry)

    async def async_record_failure(
        self,
        request: ProjectionRequest,
        *,
        reconciled_at: str,
        code: str,
    ) -> LedgerEntry:
        self._require_loaded()
        lock = await self._lock_for(request.idempotency_key)
        async with lock:
            existing = self._entries.get(request.idempotency_key)
            if existing is None or not self._same_tuple(existing, request):
                raise LedgerError("cannot record failure for a different target tuple")
            if existing.state != "pending":
                return existing
            updated = LedgerEntry(
                system_id=existing.system_id,
                idempotency_key=existing.idempotency_key,
                revision=existing.revision,
                projection_hash=existing.projection_hash,
                projection=existing.projection,
                state="pending",
                accepted_at=existing.accepted_at,
                last_reconciled_at=reconciled_at,
                resolved_series=existing.resolved_series,
                last_error_code=code,
                reconcile_attempts=existing.reconcile_attempts + 1,
            )
            self._entries[request.idempotency_key] = updated
            await self._save()
            return updated

    async def async_mark_verified(
        self,
        request: ProjectionRequest,
        *,
        verified_at: str,
        resolved_series: tuple[ResolvedSeries, ...],
    ) -> LedgerEntry:
        self._require_loaded()
        lock = await self._lock_for(request.idempotency_key)
        async with lock:
            existing = self._entries.get(request.idempotency_key)
            if existing is None or not self._same_tuple(existing, request):
                raise LedgerError("cannot verify a different target tuple")
            if existing.state == "verified":
                return existing
            updated = LedgerEntry(
                system_id=existing.system_id,
                idempotency_key=existing.idempotency_key,
                revision=existing.revision,
                projection_hash=existing.projection_hash,
                projection=existing.projection,
                state="verified",
                accepted_at=existing.accepted_at,
                last_reconciled_at=verified_at,
                verified_at=verified_at,
                resolved_series=resolved_series,
                last_error_code=None,
                reconcile_attempts=existing.reconcile_attempts + 1,
            )
            self._entries[request.idempotency_key] = updated
            await self._save()
            return updated
