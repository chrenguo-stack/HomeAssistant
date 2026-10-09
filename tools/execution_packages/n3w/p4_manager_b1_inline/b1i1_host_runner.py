from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from b1i1_contract import Authority, Operations, require
from b1i1_journal import private_root
from b1i1_supervisor import (
    Budget, HostOwnedPlan, require_host_owned_transaction,
)
from b1i1_transaction import Result, execute

HOST_ATTEMPT_MARKER = ".b1i1-host-owned-attempt-private"


def execute_host_owned(
    root: Path,
    authority: Authority,
    ops: Operations,
    budget: Budget,
    plan: HostOwnedPlan,
    *,
    authorization_id: str,
    ssh_is_owner: bool,
    host_unit_verified: bool,
    now: Callable[[], float],
) -> Result:
    private_root(root)
    plan.validate()
    authority.validate()
    require_host_owned_transaction(
        ssh_is_owner=ssh_is_owner,
        host_unit_verified=host_unit_verified,
    )
    require(plan.user_authorization == authorization_id, "LIVE_AUTHORIZATION_ID_MISMATCH")
    require(plan.source_ref == authority.source_ref, "EXACT_SOURCE_BINDING_MISMATCH")
    require(not (root / HOST_ATTEMPT_MARKER).is_symlink(), "ATTEMPT_MARKER_SYMLINK")
    marker = root / HOST_ATTEMPT_MARKER
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write("B1I1_HOST_OWNED_ATTEMPT_CLAIMED\n")
        stream.flush()
        os.fsync(stream.fileno())
    dirfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dirfd)
    finally:
        os.close(dirfd)
    return execute(root, authority, ops, budget, now=now)
