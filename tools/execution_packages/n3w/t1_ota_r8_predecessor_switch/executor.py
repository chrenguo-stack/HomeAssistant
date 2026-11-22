from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from contract import (
    PHASE_BACKUP_VERIFIED,
    PHASE_BINDING_SWITCHED,
    PHASE_CAPACITY_PASSED,
    PHASE_CURRENT_RELEASED,
    PHASE_CURRENT_RELEASE_INTENT,
    PHASE_DATA_EXCHANGED,
    PHASE_PREDECESSOR_HEALTHY,
    PHASE_PREDECESSOR_LOADED,
    PHASE_PREFLIGHT,
    PHASE_QUIESCED,
    PHASE_RECOVERY_REQUIRED,
    PHASE_ROLLED_BACK,
    SwitchGrant,
    post_release_capacity,
    require_transition,
    transaction_id,
)


class SwitchStop(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BackupEvidence:
    archive_sha256: str
    archive_size_bytes: int
    manifest_sha256: str
    staged_data_sha256: str


@dataclass(frozen=True, slots=True)
class SwitchResult:
    status: str
    transaction_id: str
    phase: str
    post_release_capacity: dict[str, int | bool | str] | None
    backup: BackupEvidence | None
    failure: str | None = None


class SwitchBackend(Protocol):
    def verify_preflight(self, grant: SwitchGrant) -> None:
        ...

    def write_state(self, document: dict[str, Any]) -> None:
        ...

    def quiesce_application(self, grant: SwitchGrant) -> None:
        ...

    def create_fresh_backup_and_stage(self, grant: SwitchGrant, txid: str) -> BackupEvidence:
        ...

    def exchange_data_root(self, grant: SwitchGrant, txid: str, backup: BackupEvidence) -> None:
        ...

    def release_current_image(self, grant: SwitchGrant, txid: str) -> None:
        ...

    def measure_post_release_available_bytes(self, grant: SwitchGrant) -> int:
        ...

    def load_predecessor_from_stream(self, grant: SwitchGrant, txid: str) -> None:
        ...

    def switch_to_predecessor_binding(self, grant: SwitchGrant, txid: str) -> None:
        ...

    def start_and_verify_predecessor(self, grant: SwitchGrant, txid: str) -> None:
        ...

    def rollback_to_current(
        self,
        grant: SwitchGrant,
        txid: str,
        *,
        phase: str,
        backup: BackupEvidence | None,
    ) -> None:
        ...


def _state(
    *,
    grant: SwitchGrant,
    txid: str,
    phase: str,
    backup: BackupEvidence | None = None,
    capacity: dict[str, int | bool | str] | None = None,
    failure: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": "gh.n3w-t1-r8-predecessor-switch-state/1",
        "transaction_id": txid,
        "authorization_id": grant.authorization_id,
        "source_head": grant.source_head,
        "phase": phase,
        "current_image": grant.current_image,
        "current_image_id": grant.current_image_id,
        "predecessor_image": grant.predecessor_image,
        "predecessor_image_id": grant.predecessor_image_id,
        "rollback_transaction_sha256": grant.rollback_transaction_sha256,
        "backup": None if backup is None else {
            "archive_sha256": backup.archive_sha256,
            "archive_size_bytes": backup.archive_size_bytes,
            "manifest_sha256": backup.manifest_sha256,
            "staged_data_sha256": backup.staged_data_sha256,
        },
        "post_release_capacity": capacity,
        "failure": failure,
    }


def _advance(
    backend: SwitchBackend,
    grant: SwitchGrant,
    txid: str,
    current: str,
    next_phase: str,
    *,
    backup: BackupEvidence | None,
    capacity: dict[str, int | bool | str] | None,
) -> str:
    require_transition(current, next_phase)
    backend.write_state(
        _state(
            grant=grant,
            txid=txid,
            phase=next_phase,
            backup=backup,
            capacity=capacity,
        )
    )
    return next_phase


def execute_switch(backend: SwitchBackend, grant: SwitchGrant) -> SwitchResult:
    grant.validate()
    txid = transaction_id(grant)
    phase = PHASE_PREFLIGHT
    backup: BackupEvidence | None = None
    capacity: dict[str, int | bool | str] | None = None

    backend.verify_preflight(grant)
    backend.write_state(_state(grant=grant, txid=txid, phase=phase))

    try:
        backend.quiesce_application(grant)
        phase = _advance(
            backend, grant, txid, phase, PHASE_QUIESCED,
            backup=backup, capacity=capacity,
        )

        backup = backend.create_fresh_backup_and_stage(grant, txid)
        phase = _advance(
            backend, grant, txid, phase, PHASE_BACKUP_VERIFIED,
            backup=backup, capacity=capacity,
        )

        backend.exchange_data_root(grant, txid, backup)
        phase = _advance(
            backend, grant, txid, phase, PHASE_DATA_EXCHANGED,
            backup=backup, capacity=capacity,
        )

        # The durable intent must exist before the exact current container/image is removed.
        phase = _advance(
            backend, grant, txid, phase, PHASE_CURRENT_RELEASE_INTENT,
            backup=backup, capacity=capacity,
        )
        backend.release_current_image(grant, txid)
        phase = _advance(
            backend, grant, txid, phase, PHASE_CURRENT_RELEASED,
            backup=backup, capacity=capacity,
        )

        available = backend.measure_post_release_available_bytes(grant)
        capacity = post_release_capacity(
            available_bytes=available,
            import_bytes=grant.predecessor_import_worst_case_bytes,
        )
        if capacity["capacity_pass"] is not True:
            raise SwitchStop("post_release_capacity_insufficient")
        phase = _advance(
            backend, grant, txid, phase, PHASE_CAPACITY_PASSED,
            backup=backup, capacity=capacity,
        )

        backend.load_predecessor_from_stream(grant, txid)
        phase = _advance(
            backend, grant, txid, phase, PHASE_PREDECESSOR_LOADED,
            backup=backup, capacity=capacity,
        )

        backend.switch_to_predecessor_binding(grant, txid)
        phase = _advance(
            backend, grant, txid, phase, PHASE_BINDING_SWITCHED,
            backup=backup, capacity=capacity,
        )

        backend.start_and_verify_predecessor(grant, txid)
        phase = _advance(
            backend, grant, txid, phase, PHASE_PREDECESSOR_HEALTHY,
            backup=backup, capacity=capacity,
        )

        return SwitchResult(
            status="PREDECESSOR_SWITCH_PASS",
            transaction_id=txid,
            phase=phase,
            post_release_capacity=capacity,
            backup=backup,
        )
    except Exception as error:
        failure = str(error).partition(":")[0] or type(error).__name__
        try:
            backend.rollback_to_current(
                grant,
                txid,
                phase=phase,
                backup=backup,
            )
            terminal = PHASE_ROLLED_BACK
            status = "PREDECESSOR_SWITCH_ROLLED_BACK"
        except Exception as rollback_error:
            terminal = PHASE_RECOVERY_REQUIRED
            status = "PREDECESSOR_SWITCH_RECOVERY_REQUIRED"
            failure = failure + ";rollback=" + (
                str(rollback_error).partition(":")[0]
                or type(rollback_error).__name__
            )
        backend.write_state(
            _state(
                grant=grant,
                txid=txid,
                phase=terminal,
                backup=backup,
                capacity=capacity,
                failure=failure,
            )
        )
        return SwitchResult(
            status=status,
            transaction_id=txid,
            phase=terminal,
            post_release_capacity=capacity,
            backup=backup,
            failure=failure,
        )
