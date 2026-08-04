from __future__ import annotations

import asyncio
import math
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal, Protocol

from .const import (
    MAX_LEDGER_BYTES,
    MAX_LEDGER_ENTRIES,
    STORAGE_VERSION,
    VERIFIED_RETENTION_DAYS,
    validate_system_id,
)
from .protocol import (
    ProjectionRequest,
    ProtocolError,
    canonical_json,
    projection_hash,
    validate_projection,
    validate_utc_timestamp,
)

LedgerState = Literal["pending", "verified"]
DecisionStatus = Literal["accepted", "verified", "resume", "retry", "blocked"]
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_CODE_RE = re.compile(r"^[a-z0-9_]{1,96}$")


class LedgerError(RuntimeError):
    pass


class LedgerCorruptionError(LedgerError):
    pass


class LedgerCapacityError(LedgerError):
    pass


class LedgerStore(Protocol):
    async def async_load(self) -> dict[str, Any] | None: ...

    async def async_save(self, document: dict[str, Any]) -> None: ...


def _utc(value: Any, field: str) -> datetime:
    try:
        text = validate_utc_timestamp(value, field)
    except ProtocolError as exc:
        raise LedgerCorruptionError(str(exc)) from exc
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


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
    def from_document(cls, raw: Any) -> ResolvedSeries:
        keys = {
            "measurement_key",
            "entity_unique_id",
            "entity_id",
            "unit_of_measurement",
            "mean",
            "minimum",
            "maximum",
        }
        if not isinstance(raw, dict) or set(raw) != keys:
            raise LedgerCorruptionError("resolved series shape is invalid")
        for name in ("measurement_key", "entity_unique_id", "entity_id", "unit_of_measurement"):
            if not isinstance(raw[name], str) or not raw[name]:
                raise LedgerCorruptionError(f"resolved series {name} is invalid")
        values = []
        for name in ("mean", "minimum", "maximum"):
            value = raw[name]
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise LedgerCorruptionError(f"resolved series {name} is invalid")
            value = float(value)
            if not math.isfinite(value):
                raise LedgerCorruptionError(f"resolved series {name} must be finite")
            values.append(value)
        mean, minimum, maximum = values
        if not minimum <= mean <= maximum:
            raise LedgerCorruptionError("resolved series ordering is invalid")
        return cls(
            raw["measurement_key"],
            raw["entity_unique_id"],
            raw["entity_id"],
            raw["unit_of_measurement"],
            mean,
            minimum,
            maximum,
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


class TargetLedger:
    def __init__(
        self,
        store: LedgerStore,
        *,
        configured_system_id: str,
        verified_retention_days: int = VERIFIED_RETENTION_DAYS,
        max_entries: int = MAX_LEDGER_ENTRIES,
        max_serialized_bytes: int = MAX_LEDGER_BYTES,
    ) -> None:
        self.store = store
        self.system_id = validate_system_id(configured_system_id)
        if verified_retention_days < 0 or max_entries < 1 or max_serialized_bytes < 1:
            raise ValueError("ledger bounds are invalid")
        self.retention_days = verified_retention_days
        self.max_entries = max_entries
        self.max_bytes = max_serialized_bytes
        self._entries: dict[str, LedgerEntry] = {}
        self._loaded = False
        self._transaction_lock = asyncio.Lock()

    def _document(self, entries: dict[str, LedgerEntry]) -> dict[str, Any]:
        return {
            "storage_schema_version": STORAGE_VERSION,
            "system_id": self.system_id,
            "entries": {key: value.as_document() for key, value in sorted(entries.items())},
        }

    def _decode_entry(self, key: str, raw: Any) -> LedgerEntry:
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
        if not isinstance(raw, dict) or set(raw) != required:
            raise LedgerCorruptionError("ledger entry shape is invalid")
        if raw["system_id"] != self.system_id or raw["idempotency_key"] != key:
            raise LedgerCorruptionError("ledger identity is inconsistent")
        if raw["state"] not in {"pending", "verified"}:
            raise LedgerCorruptionError("ledger state is invalid")
        if type(raw["revision"]) is not int or raw["revision"] < 1:
            raise LedgerCorruptionError("ledger revision is invalid")
        declared_hash = raw["projection_hash"]
        if not isinstance(declared_hash, str) or not _HASH_RE.fullmatch(declared_hash):
            raise LedgerCorruptionError("ledger projection hash is invalid")
        try:
            projection = validate_projection(raw["projection"])
        except ProtocolError as exc:
            raise LedgerCorruptionError(f"ledger projection is invalid: {exc}") from exc
        if (
            projection["idempotency_key"] != key
            or projection["revision"] != raw["revision"]
            or projection_hash(projection) != declared_hash
        ):
            raise LedgerCorruptionError("ledger projection tuple is inconsistent")
        _utc(raw["accepted_at"], "accepted_at")
        for field in ("last_reconciled_at", "verified_at"):
            if raw[field] is not None:
                _utc(raw[field], field)
        attempts = raw["reconcile_attempts"]
        if type(attempts) is not int or attempts < 0:
            raise LedgerCorruptionError("ledger attempts are invalid")
        error_code = raw["last_error_code"]
        if error_code is not None and (
            not isinstance(error_code, str) or not _CODE_RE.fullmatch(error_code)
        ):
            raise LedgerCorruptionError("ledger error code is invalid")
        if not isinstance(raw["resolved_series"], list):
            raise LedgerCorruptionError("resolved series list is invalid")
        resolved = tuple(ResolvedSeries.from_document(item) for item in raw["resolved_series"])
        if raw["state"] == "pending":
            if raw["verified_at"] is not None or resolved:
                raise LedgerCorruptionError("pending ledger state is inconsistent")
        else:
            if not raw["verified_at"] or error_code is not None:
                raise LedgerCorruptionError("verified ledger state is inconsistent")
            expected = {item["measurement_key"]: item for item in projection["series"]}
            actual = {item.measurement_key: item for item in resolved}
            if len(actual) != len(resolved) or set(actual) != set(expected):
                raise LedgerCorruptionError("resolved measurements are inconsistent")
            for name, item in actual.items():
                source = expected[name]
                if (
                    item.entity_unique_id != source["entity_unique_id"]
                    or item.unit_of_measurement != source["unit_of_measurement"]
                    or item.mean != float(source["mean"])
                    or item.minimum != float(source["min"])
                    or item.maximum != float(source["max"])
                ):
                    raise LedgerCorruptionError("resolved values are inconsistent")
        return LedgerEntry(
            raw["system_id"],
            key,
            raw["revision"],
            declared_hash,
            deepcopy(projection),
            raw["state"],
            raw["accepted_at"],
            raw["last_reconciled_at"],
            raw["verified_at"],
            resolved,
            error_code,
            attempts,
        )

    def _require_loaded(self) -> None:
        if not self._loaded:
            raise LedgerError("target ledger is not loaded")

    async def async_load(self) -> None:
        raw = await self.store.async_load()
        if raw is None:
            self._loaded = True
            return
        if not isinstance(raw, dict) or set(raw) != {
            "storage_schema_version",
            "system_id",
            "entries",
        }:
            raise LedgerCorruptionError("target ledger root shape is invalid")
        if raw["storage_schema_version"] != STORAGE_VERSION or raw["system_id"] != self.system_id:
            raise LedgerCorruptionError("target ledger root binding is invalid")
        if not isinstance(raw["entries"], dict):
            raise LedgerCorruptionError("target ledger entries are invalid")
        entries = {key: self._decode_entry(key, value) for key, value in raw["entries"].items()}
        if not self._within_capacity(entries):
            raise LedgerCorruptionError("target ledger exceeds capacity")
        self._entries = entries
        self._loaded = True

    def read(self, key: str) -> LedgerEntry | None:
        self._require_loaded()
        return deepcopy(self._entries.get(key))

    def snapshot(self) -> dict[str, LedgerEntry]:
        self._require_loaded()
        return deepcopy(self._entries)

    def _validate_request(self, request: ProjectionRequest) -> None:
        if request.system_id != self.system_id:
            raise LedgerError("request system_id does not match target ledger")
        try:
            validate_projection(request.projection)
        except ProtocolError as exc:
            raise LedgerError(f"request projection is invalid: {exc}") from exc
        if projection_hash(request.projection) != request.projection_hash:
            raise LedgerError("request projection hash is invalid")

    @staticmethod
    def _same(entry: LedgerEntry, request: ProjectionRequest) -> bool:
        return (
            entry.system_id == request.system_id
            and entry.revision == request.revision
            and entry.projection_hash == request.projection_hash
            and canonical_json(entry.projection) == canonical_json(request.projection)
        )

    def _prune(
        self,
        entries: dict[str, LedgerEntry],
        reference: datetime,
    ) -> dict[str, LedgerEntry]:
        cutoff = reference - timedelta(days=self.retention_days)
        return {
            key: entry
            for key, entry in entries.items()
            if not (
                entry.state == "verified"
                and datetime.fromisoformat(
                    str(entry.projection["sample_hour"]).replace("Z", "+00:00")
                )
                < cutoff
            )
        }

    def _within_capacity(self, entries: dict[str, LedgerEntry]) -> bool:
        if len(entries) > self.max_entries:
            return False
        try:
            size = len(canonical_json(self._document(entries)).encode("utf-8"))
        except (TypeError, ValueError):
            return False
        return size <= self.max_bytes

    async def _commit(self, entries: dict[str, LedgerEntry]) -> None:
        await self.store.async_save(self._document(entries))
        self._entries = entries

    async def async_prepare(
        self,
        request: ProjectionRequest,
        *,
        accepted_at: str,
    ) -> LedgerDecision:
        self._require_loaded()
        self._validate_request(request)
        reference = _utc(accepted_at, "accepted_at")
        async with self._transaction_lock:
            existing = self._entries.get(request.idempotency_key)
            if existing:
                if request.revision < existing.revision:
                    return LedgerDecision("blocked", "target_newer_revision", deepcopy(existing))
                if request.revision == existing.revision:
                    if not self._same(existing, request):
                        return LedgerDecision(
                            "blocked",
                            "target_same_revision_hash_conflict",
                            deepcopy(existing),
                        )
                    status = "verified" if existing.state == "verified" else "resume"
                    code = (
                        "verified_idempotent_readback"
                        if existing.state == "verified"
                        else "resume_pending"
                    )
                    return LedgerDecision(status, code, deepcopy(existing))
                if existing.state == "pending":
                    return LedgerDecision("retry", "prior_revision_pending", deepcopy(existing))
            candidate = self._prune(deepcopy(self._entries), reference)
            entry = LedgerEntry(
                request.system_id,
                request.idempotency_key,
                request.revision,
                request.projection_hash,
                deepcopy(request.projection),
                "pending",
                accepted_at,
            )
            candidate[request.idempotency_key] = entry
            if not self._within_capacity(candidate):
                return LedgerDecision(
                    "blocked",
                    "target_ledger_capacity_exceeded",
                    deepcopy(existing),
                )
            await self._commit(candidate)
            code = "accepted_new_target" if existing is None else "accepted_higher_revision"
            return LedgerDecision("accepted", code, deepcopy(entry))

    async def async_record_failure(
        self,
        request: ProjectionRequest,
        *,
        reconciled_at: str,
        code: str,
    ) -> LedgerEntry:
        self._require_loaded()
        self._validate_request(request)
        _utc(reconciled_at, "reconciled_at")
        if not _CODE_RE.fullmatch(code):
            raise LedgerError("failure code is invalid")
        async with self._transaction_lock:
            existing = self._entries.get(request.idempotency_key)
            if existing is None or not self._same(existing, request):
                raise LedgerError("cannot update a different target tuple")
            if existing.state == "verified":
                return deepcopy(existing)
            updated = LedgerEntry(
                existing.system_id,
                existing.idempotency_key,
                existing.revision,
                existing.projection_hash,
                deepcopy(existing.projection),
                "pending",
                existing.accepted_at,
                reconciled_at,
                None,
                (),
                code,
                existing.reconcile_attempts + 1,
            )
            candidate = deepcopy(self._entries)
            candidate[request.idempotency_key] = updated
            if not self._within_capacity(candidate):
                raise LedgerCapacityError("failure update exceeds ledger capacity")
            await self._commit(candidate)
            return deepcopy(updated)

    async def async_mark_verified(
        self,
        request: ProjectionRequest,
        *,
        verified_at: str,
        resolved_series: tuple[ResolvedSeries, ...],
    ) -> LedgerEntry:
        self._require_loaded()
        self._validate_request(request)
        _utc(verified_at, "verified_at")
        async with self._transaction_lock:
            existing = self._entries.get(request.idempotency_key)
            if existing is None or not self._same(existing, request):
                raise LedgerError("cannot verify a different target tuple")
            if existing.state == "verified":
                return deepcopy(existing)
            updated = LedgerEntry(
                existing.system_id,
                existing.idempotency_key,
                existing.revision,
                existing.projection_hash,
                deepcopy(existing.projection),
                "verified",
                existing.accepted_at,
                verified_at,
                verified_at,
                tuple(deepcopy(resolved_series)),
                None,
                existing.reconcile_attempts + 1,
            )
            updated = self._decode_entry(updated.idempotency_key, updated.as_document())
            candidate = deepcopy(self._entries)
            candidate[request.idempotency_key] = updated
            if not self._within_capacity(candidate):
                raise LedgerCapacityError("verified update exceeds ledger capacity")
            await self._commit(candidate)
            return deepcopy(updated)
