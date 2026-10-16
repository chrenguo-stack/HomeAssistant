# N3-W T1 F4 Reboot Successor — Postclaim Recovery Source Design

Date: 2026-10-16

```text
TASK=N3W_T1_F4_REBOOT_SUCCESSOR_POSTCLAIM_RECOVERY_SOURCE_DESIGN_20261016_01

LIVE_RUNTIME_MUTATION=false
REBOOT=false
BOARD_ACCESS=false
MERGE=false

OLD_SOURCE_HEAD=5368acc1eb50f1fc62bbd7c16ff9e64139131a29
OLD_MANIFEST_SHA256=2f2ae69dbf78d5f578fa60bbee7fb269a5d0c3b17a00e2f697bc65d3ed91c40c
OLD_INSTALL_CLAIM_SHA256=6c8cad9331094bbb0abe89ff67bc75b724d66c7eb97cdf6f4117c3bce5ed4d80
OLD_INSTALL_CLAIM_STAGE=CONTROL_APPLYING
OLD_INSTALL_AUTHORIZATION_CONSUMED=true
OLD_INSTALL_AUTHORIZATION_REPLAY_ALLOWED=false

RECOVERY_AUTHORIZATION_GRANTED=false
```

## Problem

The original successor-control install authorization was correctly consumed before mutation. The installation then
reached `CONTROL_APPLYING`, installed all old exact control targets and manifest, loaded the systemd drop-in and
failed because the old runtime guard required a `board_access` field that the frozen F4
`_runtime_activity()` schema does not contain.

The original authorization cannot be replayed. A raw overwrite of the guard is also insufficient because the
installed manifest and durable install claim remain bound to the old source head and old guard hash.

## Recovery authority

The recovery source introduces:

```text
tools/n3w_t1_f4_reboot_successor_postclaim_recovery.py
```

It is an execution authority carried by the exact recovery artifact and is not a permanent fifth successor control
target.

The final installed successor control package remains exactly four files plus its manifest.

## Recovery preflight

Before any recovery authorization can be claimed, the tool must prove:

- the old install claim SHA is exact;
- claim stage is exactly `CONTROL_APPLYING`;
- the original install authorization remains claimed/consumed/non-replayable;
- `installation_apply_started=true` and `installation_verified!=true`;
- old source head, old manifest hash and F4 transaction hash are exact;
- old runtime/certificate snapshots are exact;
- current boot ID is exact;
- all old installed successor files and manifest exactly match the old manifest;
- the successor drop-in remains loaded;
- Broker/Manager/Home Assistant runtime and TLS contracts remain healthy;
- certificate timer is enabled/inactive and lifecycle service is inactive;
- no reboot claim exists;
- the target repaired package is exact;
- the only installed-control content delta between old and target package is the runtime guard.

Any mismatch is a fail-closed STOP.

## Fresh recovery authorization

Recovery uses a new authorization distinct from the consumed install authorization.

The recovery authorization is durably stored at:

```text
/var/lib/n3w-t1-provisioning/F4_REBOOT_SUCCESSOR_RECOVERY_AUTHORIZATION.json
```

The claim binds:

- old install-claim SHA;
- old source head and manifest hash;
- target source head and target manifest hash;
- F4 transaction SHA;
- current runtime snapshot;
- current certificate-identity snapshot;
- current boot-ID SHA;
- old and target runtime-guard SHA;
- claimed=true;
- consumed=true;
- replay_allowed=false.

The recovery claim is persisted before any control-file mutation.

## Bounded mutation

The target repaired package must differ from the installed old package only in
`tools/n3w_t1_f4_certificate_runtime_guard.py`.

The recovery mutation therefore replaces only:

1. installed runtime guard;
2. installed successor manifest.

Authority, reboot verifier and systemd drop-in must already match the repaired package and are not rewritten.

The drop-in content is unchanged, so recovery does not require a product service restart or timer start.

## Durable transition to CONTROL_READY

After the repaired guard passes, recovery updates the original durable install claim instead of erasing it.

The original install authorization fields remain preserved.

The claim adds explicit recovery provenance and changes only the control-package binding needed for the repaired
source:

- preserve original consumed install authorization;
- record original source head, manifest hash and claim SHA;
- record fresh postclaim recovery authorization;
- update source head to repaired source;
- update manifest hash and exact file bindings;
- set `postclaim_recovery_applied=true`;
- set `stage=CONTROL_READY`;
- set `installation_verified=true`.

The installed repository-owned reboot authority must then pass `verify-install` against the repaired source and
manifest.

Finally the recovery record advances to `RECOVERY_VERIFIED`.

## Reboot boundary

Recovery does not:

- claim reboot authorization;
- reboot, shutdown or power off the host;
- start the certificate timer/service;
- restart Broker/Manager/Home Assistant;
- access boards;
- merge PRs.

A successful recovery only restores a fully verified `CONTROL_READY` state.

Reboot remains a later separate one-shot authorization boundary.

```text
RECOVERY_PASS_STATE=RECOVERY_VERIFIED
INSTALL_PASS_STATE=CONTROL_READY
REBOOT_AUTHORIZATION_GRANTED=false
AUTO_EXECUTE_REBOOT=false
```
