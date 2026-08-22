from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from .n3w_node_application_keys import (
    NodeApplicationKeyStoreUnavailable,
    SqliteNodeApplicationKeyAdmin,
)
from .registration import (
    NodeIdLeaseState,
    RegistrationConflict,
    RegistrationRegistry,
    RegistrationState,
    _utc,
)


def stage_pairing_epoch_key(
    application_keys: Any,
    *,
    node_id: str,
    key_material: bytes,
    target_key_epoch: int,
) -> dict[str, object]:
    """Stage exactly the pairing epoch key without materializing skipped epochs.

    The production SqliteNodeApplicationKeyAdmin historically allocates MAX+1.
    Recovery from an expired durable pairing epoch may legitimately advance the
    pairing epoch farther than the key table's current maximum. This adapter keeps
    the generic admin behavior unchanged while giving the pairing path one narrow,
    fail-closed exact-target operation.
    """

    if (
        not isinstance(target_key_epoch, int)
        or isinstance(target_key_epoch, bool)
        or target_key_epoch < 1
    ):
        raise NodeApplicationKeyStoreUnavailable("target_key_epoch_invalid")

    if isinstance(application_keys, SqliteNodeApplicationKeyAdmin):
        return _stage_sqlite_exact_epoch(
            application_keys,
            node_id=node_id,
            key_material=key_material,
            target_key_epoch=target_key_epoch,
        )

    result = application_keys.stage_key(
        node_id=node_id,
        key_material=key_material,
    )
    observed = result.get("key_epoch")
    if observed != target_key_epoch:
        if (
            isinstance(observed, int)
            and not isinstance(observed, bool)
            and observed >= 1
        ):
            try:
                application_keys.revoke_key(
                    node_id=node_id,
                    key_epoch=observed,
                )
            except Exception as error:
                raise NodeApplicationKeyStoreUnavailable(
                    "target_key_epoch_mismatch_rollback_failed"
                ) from error
        raise NodeApplicationKeyStoreUnavailable(
            "target_key_epoch_mismatch"
        )
    return result


def _stage_sqlite_exact_epoch(
    admin: SqliteNodeApplicationKeyAdmin,
    *,
    node_id: str,
    key_material: bytes,
    target_key_epoch: int,
) -> dict[str, object]:
    node_id = admin._require_active_node(node_id)
    target_key_epoch = admin._require_epoch(target_key_epoch)

    if (
        not isinstance(key_material, bytes)
        or len(key_material) != 32
    ):
        raise NodeApplicationKeyStoreUnavailable(
            "key_material_invalid"
        )

    digest = hashlib.sha256(key_material).hexdigest()

    with admin._lock:
        maximum = admin._connection.execute(
            """
            SELECT MAX(key_epoch)
            FROM n3w_relay_key_epochs
            WHERE node_id=?
            """,
            (node_id,),
        ).fetchone()[0]
        maximum_epoch = int(maximum or 0)

        if target_key_epoch <= maximum_epoch:
            raise NodeApplicationKeyStoreUnavailable(
                "target_key_epoch_not_monotonic"
            )

        staged = admin._connection.execute(
            """
            SELECT 1
            FROM n3w_relay_key_epochs
            WHERE node_id=? AND state='STAGED'
            LIMIT 1
            """,
            (node_id,),
        ).fetchone()
        if staged is not None:
            raise NodeApplicationKeyStoreUnavailable(
                "key_rotation_already_staged"
            )

        key_file = (
            f"{node_id}-epoch-{target_key_epoch}.key"
        )

        with admin._transaction() as connection:
            connection.execute(
                """
                INSERT INTO n3w_relay_nodes(node_id,active)
                VALUES (?,1)
                ON CONFLICT(node_id) DO UPDATE SET active=1
                """,
                (node_id,),
            )
            connection.execute(
                """
                INSERT INTO n3w_relay_key_epochs(
                    node_id,
                    key_epoch,
                    key_file,
                    enabled,
                    state,
                    key_sha256
                )
                VALUES (?,?,?,0,'STAGED',?)
                """,
                (
                    node_id,
                    target_key_epoch,
                    key_file,
                    digest,
                ),
            )
            admin._record_operation(
                connection,
                node_id=node_id,
                key_epoch=target_key_epoch,
                status="FILE_PENDING",
            )

        admin._fsync_database()

        try:
            admin._write_key(
                key_file,
                key_material,
            )
        except Exception as error:
            with admin._transaction() as connection:
                connection.execute(
                    """
                    UPDATE n3w_relay_key_epochs
                    SET state='REVOKED',enabled=0
                    WHERE node_id=? AND key_epoch=?
                    """,
                    (node_id, target_key_epoch),
                )
                admin._record_operation(
                    connection,
                    node_id=node_id,
                    key_epoch=target_key_epoch,
                    status="RECOVERED",
                )
            admin._fsync_database()
            raise NodeApplicationKeyStoreUnavailable(
                "node_key_file_write_failed"
            ) from error

        with admin._transaction() as connection:
            admin._record_operation(
                connection,
                node_id=node_id,
                key_epoch=target_key_epoch,
                status="DONE",
            )

        admin._fsync_database()

    return admin._result(
        "stage_key_exact",
        node_id=node_id,
        key_epoch=target_key_epoch,
    )


def rollback_automatic_approval_preserving_node(
    registry: RegistrationRegistry,
    hardware_id: str,
    pairing_id: str,
    *,
    preserve_node_id: str,
    reason: str,
    now: datetime,
) -> None:
    """Return a repair pairing to PENDING without retiring its inherited NODE_ID."""

    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ValueError("rollback reason must not be empty")
    occurred_at = _utc(now)

    with registry._lock, registry._connection:
        record = registry._require_current(
            hardware_id,
            pairing_id,
        )

        if record.node_id != preserve_node_id:
            raise RegistrationConflict(
                "preserved node_id binding could not be proven"
            )

        if record.state is RegistrationState.PENDING:
            return

        if record.state is not RegistrationState.APPROVED:
            raise RegistrationConflict(
                "only an uncommitted repair approval can be rolled back"
            )

        lease = registry._connection.execute(
            """
            SELECT hardware_id,state
            FROM node_id_leases
            WHERE node_id=?
            """,
            (preserve_node_id,),
        ).fetchone()
        if (
            lease is None
            or lease["hardware_id"] != hardware_id
            or NodeIdLeaseState(lease["state"])
            is not NodeIdLeaseState.ACTIVE
        ):
            raise RegistrationConflict(
                "preserved node_id active lease could not be proven"
            )

        history = registry._connection.execute(
            """
            SELECT node_id
            FROM registration_node_history
            WHERE hardware_id=? AND released_at IS NULL
            ORDER BY history_id DESC
            LIMIT 1
            """,
            (hardware_id,),
        ).fetchone()
        if (
            history is None
            or history["node_id"] != preserve_node_id
        ):
            raise RegistrationConflict(
                "preserved node_id assignment history could not be proven"
            )

        registry._record_event(
            hardware_id,
            pairing_id,
            "automatic_approval_rolled_back_preserved_node",
            normalized_reason,
            occurred_at,
            node_id=preserve_node_id,
            logical_location_id=record.logical_location_id,
        )
        registry._set_session_state(
            pairing_id,
            RegistrationState.PENDING,
            normalized_reason,
        )

        current = registry._current_row(hardware_id)
        if (
            current is None
            or current["node_id"] != preserve_node_id
            or current["state"] != RegistrationState.PENDING
        ):
            raise RegistrationConflict(
                "preserved node_id rollback verification failed"
            )

        lease_after = registry._connection.execute(
            """
            SELECT hardware_id,state
            FROM node_id_leases
            WHERE node_id=?
            """,
            (preserve_node_id,),
        ).fetchone()
        if (
            lease_after is None
            or lease_after["hardware_id"] != hardware_id
            or NodeIdLeaseState(lease_after["state"])
            is not NodeIdLeaseState.ACTIVE
        ):
            raise RegistrationConflict(
                "preserved node_id lease changed during rollback"
            )

        history_after = registry._connection.execute(
            """
            SELECT node_id,released_at
            FROM registration_node_history
            WHERE hardware_id=?
            ORDER BY history_id DESC
            LIMIT 1
            """,
            (hardware_id,),
        ).fetchone()
        if (
            history_after is None
            or history_after["node_id"] != preserve_node_id
            or history_after["released_at"] is not None
        ):
            raise RegistrationConflict(
                "preserved node_id history changed during rollback"
            )
