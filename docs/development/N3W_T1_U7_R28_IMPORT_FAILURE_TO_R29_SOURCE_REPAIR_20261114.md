# N3-W T1 U7 R28 import failure → R29 dependency-safe source repair
# 2026-11-14

STATUS=SOURCE_REPAIR_IMPLEMENTED_UNGRANTED_PENDING_FRESH_CI
R28_RESULT=TERMINAL_STOP_ROLLBACK_PASS
R28_REPLAY=false
R29_LIVE_EXECUTION_AUTHORIZED=false

## 1. Physical result inherited from R28

R28 exact grant head:
`e73e6ad1b7cffbf9449f81bf12177f4176d05b11`

Real-T1 execution:
`U7-R28-SOURCE-ACTIVATION-20261114T130919Z`

R28 claimed and consumed its one-shot authorization, activated the four intended
source files, then stopped at `activated_source_import_failed`.

The bounded rollback completed successfully. Post-rollback evidence proved:

- the original backup / USB / install sources were restored;
- `n3w_t1_core_updater_host.py` returned to `ABSENT_PRE_U7`;
- the frozen U6 transaction SHA remained unchanged;
- R26 remained consumed/no-replay with exact predecessor authority;
- Manager, Home Assistant and Broker remained running with restart_count=0;
- host, services-owner and broker-owner remained active/running with NRestarts=0;
- IPC remained `PREDECESSOR_RECOVERY_PREPARING`;
- no service stop/restart, transaction mutation, USB mutation, U7 transition or U8+ occurred.

R28 is terminal and may not be replayed.

## 2. Source-review finding

R28's post-activation import check collapsed every Python import failure into the
single reason `activated_source_import_failed`. It did not identify the failing
module or safe stderr.

A fresh import-graph review found that the four activated U7 modules have a
13-module transitive N3W import closure. R28 explicitly bound the four targets and
nine U6 files, but two transitive modules were not part of the activation/prestate
contract:

- `n3w_t1_core_updater_common.py`
- `n3w_t1_core_updater_v2_state.py`

The common module is byte-identical between the product authority and current
source. `n3w_t1_core_updater_v2_state.py` is not: current source adds the active
Home Assistant USB transaction guard.

The exact R28 import exception is therefore not reconstructed from the physical
result alone, but R28's dependency contract is incomplete regardless and must not
be reused.

## 3. R29 repair contract

R29 is a new gate and a new one-shot authorization domain. It starts ungranted.

Activation set is expanded to six exact modules:

1. `n3w_t1_core_updater_ha_backup.py`
2. `n3w_t1_core_updater_ha_usb.py`
3. `n3w_t1_core_updater_ha_install.py`
4. `n3w_t1_core_updater_host.py`
5. `n3w_t1_core_updater_common.py`
6. `n3w_t1_core_updater_v2_state.py`

The nine R28 unchanged U6 dependencies remain exact SHA-256 bound.

For common/v2_state, R29 accepts only bounded predecessor states:

- common: absent or exact known product/current Git blob;
- v2_state: absent, exact product Git blob, or exact current target Git blob;
- any other content fails before authorization claim.

The observed predecessor state is copied to a private pre-claim backup and becomes
the rollback authority for that execution.

## 4. Pre-claim staged import

R29 stages the six target files under their canonical Python module filenames.

Before authorization claim it runs an import closure check with:

```text
sys.path[0]=private staging directory
sys.path[1]=/opt/HomeAssistant/tools
```

This proves the new six-file set can import against the exact installed dependency
set before any production source replacement or one-shot claim.

If staged import fails:
- authorization remains unclaimed/unconsumed;
- production source remains untouched;
- the result exposes a bounded/sanitized import reason instead of the generic R28
  oracle.

The same import validation runs again after activation.

## 5. Runtime / rollback tightening

R29 requires before and after activation:

- exact U6 transaction and R26 authority;
- owner units active/running/success with NRestarts=0;
- exact configured/runtime images;
- all three containers running with restart_count=0;
- IPC phase remains `PREDECESSOR_RECOVERY_PREPARING`;
- unit PIDs, container IDs and restart counts remain continuous.

Rollback remains one bounded attempt. It restores the exact observed pre-claim
source state, including deleting a source that was absent before R29.

## 6. Boundary

```text
SERVICE_STOP=false
SERVICE_RESTART=false
TRANSACTION_MUTATION=false
USB_MUTATION=false
U7_TRANSITION=false
HA_QUIESCE=false
HA_DATA_BACKUP_CREATE=false
U8_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

R29 success stops before the separate live U7 HA-quiesce/data-backup gate.

NEXT=focused source review + fresh CI. No live R29 authorization is granted by this
document.


## 7. R29 read-only preflight Attempt 01 local-wrapper stop

After the first R29 source head reached 16/16 fresh CI, the real-T1 read-only
preflight wrapper was invoked as:

`U7-R29-READONLY-PREFLIGHT-20261114T132435Z`

It stopped locally before SSH transport creation:

```text
STATUS=STOP
REASON=AttributeError:module 'n3w_r29_base' has no attribute 'prepare_evidence_root'
T1_ACCESS=false
REMOTE_STAGING=false
REMOTE_EXECUTE_INVOKED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
HOST_SOURCE_MUTATION=false
SERVICE_STOP=false
SERVICE_RESTART=false
TRANSACTION_MUTATION=false
USB_MUTATION=false
U7_TRANSITION=false
U8_PLUS=false
```

Root cause:
- R29 loaded the R28 executor as a helper module;
- R28 itself calls helper functions inherited by loading R25 internally, but does not
  re-export `prepare_evidence_root`, `write_remote_evidence`,
  `write_private_json`, or `load_transport`;
- R29 therefore failed before evidence-root preparation completed and before any SSH
  connection was established.

Repair:
- bind R29 local helpers directly to the frozen R25 executor where those interfaces
  are defined;
- exact-bind the R25 helper executor in the R29 manifest;
- add a regression that imports R29, loads its helper authority, and asserts all six
  required local interfaces are present.

Attempt 01 is not a consumed authorization, not a T1 mutation attempt, and is safe to
supersede after fresh CI.


## 8. R29 read-only preflight Attempt 02 remote JSON stop

Attempt 02:
`U7-R29-READONLY-PREFLIGHT02-20261114T134022Z`

Observed local result:

```text
STATUS=STOP
REASON=Stop:r29_preflight_failed:remote_result_invalid
T1_ACCESS=true
REMOTE_STAGING=false
REMOTE_EXECUTE_INVOKED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
HOST_SOURCE_MUTATION=false
SERVICE_STOP=false
SERVICE_RESTART=false
TRANSACTION_MUTATION=false
USB_MUTATION=false
U7_TRANSITION=false
U8_PLUS=false
SSH_MASTER_CLEANUP=true
```

Source-proven root cause:
- the R29 embedded remote script decoded the base64 plan in `main()`;
- `base64` was not imported inside `REMOTE_SCRIPT`;
- plan decoding occurred before the remote `try` block;
- Python therefore raised `NameError` before any JSON result could be emitted;
- the local wrapper correctly reduced non-JSON stdout to `remote_result_invalid`.

Impact:
- SSH transport was established, so `T1_ACCESS=true`;
- the remote script failed before `verify_prestate()`, before any staging directory,
  before authorization claim, and before all source/service/USB/transaction mutations;
- Attempt 02 is read-only and unconsumed and is safe to supersede after source repair.

Repair:
- import `base64` in the embedded remote script;
- move mode/plan decoding inside the remote `try` block so malformed payloads also
  return a bounded JSON STOP instead of a raw traceback;
- add a regression that runs the embedded remote script with an invalid payload and
  requires return code 2, JSON STOP on stdout, no stderr traceback, and no
  authorization claim/consumption.
