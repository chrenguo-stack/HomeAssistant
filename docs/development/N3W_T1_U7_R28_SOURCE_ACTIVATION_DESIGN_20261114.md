# N3-W T1 U7 R28 source activation design / preauthorization staging
# 2026-11-14

STATUS=SOURCE_PACKAGE_PREPARED_UNGRANTED_PENDING_FRESH_CI
PR=807
BASE_R27_HEAD=2e9105e6b9e166779a2d898c30b788ca6f42f66f
R27_RETEST03=CLOSED_PASS
R27_PUBLIC_ARCHIVE_COMMENT=6877244227

USER_STAGE_AUTHORIZATION_RECEIVED=true
LIVE_EXECUTION_AUTHORIZED=false
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_PERMITTED=false

## 1. Purpose

R27 proved the real T1 post-reboot U6 baseline and returned:

- `u7_source_activation_required=true`;
- `u7_source_activation_eligible=true`;
- `u7_live_execution_eligible=false`.

R28 activates only the already reviewed U7 source needed by the later HA-quiesce /
HA_DATA_BACKUP gate. R28 does not execute U7 lifecycle work.

The user explicitly agreed to enter the U7 source-activation stage after R27 closure.
That decision permits preparation, review, CI and, after exact package closure, the
grant-only binding for this same bounded source-activation action. The initial package
remains ungranted until exact-source CI/review closes.

## 2. Exact activation scope

R28 deploys exactly four files:

```text
/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_backup.py
/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_usb.py
/opt/HomeAssistant/tools/n3w_t1_core_updater_ha_install.py
/opt/HomeAssistant/tools/n3w_t1_core_updater_host.py
```

The first three have exact U6 predecessor SHA-256 bindings from R27.
`n3w_t1_core_updater_host.py` must be absent before activation.

The package also revalidates the nine unchanged U6 dependency files observed by R27,
so an unrelated source drift cannot be hidden by correct hashes for the four target
files.

## 3. Embedded preflight

Before any staging or authorization claim, R28 requires:

- exact durable U6 transaction SHA and phase;
- product U9 authorization fields still false/null;
- R26 consumed/no-replay ledger exact;
- R26 predecessor durable authority exact;
- four changed-source predecessors exact, including pre-U7 host.py absence;
- nine unchanged U6 dependency hashes exact;
- production owner units active/running/success;
- Manager, Home Assistant and Broker exact images running;
- IPC phase still `PREDECESSOR_RECOVERY_PREPARING`;
- no R28 state/staging residue.

A preflight failure is read-only and cannot claim authorization.

## 4. Mutation contract

After a granted exact package passes embedded preflight:

1. stage the four exact repository sources under a private root-owned 0700 directory;
2. copy the three existing predecessor files to a private pre-claim rollback directory;
3. persist the one-shot claim as consumed/no-replay;
4. revalidate U6/runtime state after claim;
5. atomically replace the four source files;
6. import all four modules with bytecode writes disabled;
7. revalidate exact target hashes, unchanged dependency hashes, U6 transaction and unit PIDs;
8. persist a durable `success.json`;
9. remove staging.

The running OTA daemon is not restarted or reloaded. Existing production processes
therefore continue using their already-loaded code until a later separately authorized
gate.

## 5. Failure / rollback

After claim, authorization is consumed even if execution fails.

If any source mutation has occurred, R28 performs at most one rollback:

- restore the three predecessor files from the pre-claim backup;
- delete `n3w_t1_core_updater_host.py`, because it was absent before U7 activation;
- revalidate the predecessor U6 state.

There is no automatic retry. Unknown post-invoke transport/result state is treated as
consumed/no-replay.

## 6. Explicit non-goals / stop boundary

```text
SERVICE_STOP=false
SERVICE_RESTART=false
USB_MUTATION=false
TRANSACTION_MUTATION=false
U7_TRANSITION=false
HA_QUIESCE=false
HA_DATA_BACKUP_CREATE=false
U8_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

R28 success stops before the live U7 HA-quiesce/data-backup gate.

NEXT_AFTER_R28_PASS=SEPARATE_U7_HA_QUIESCE_DATA_BACKUP_LIVE_GATE
