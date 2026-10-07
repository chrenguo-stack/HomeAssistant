# N3-W Clean Product First-Pair / Runtime Identity
# P1 R1 Port-Busy Closure and P1 R2 Read-Only Preexecution — 2026-10-07

```text
STATUS=CURRENT_P1_SUCCESSOR_PREEXECUTION
REPOSITORY=chrenguo-stack/HomeAssistant
PR=522
PR_STATE=OPEN_DRAFT
MERGE=false
LIVE_MUTATION=false
BOARD_ACCESS=false
T1_MUTATION=false
```

## 1. R1 observed closure

The first clean-candidate P1 execution stopped at the first board-targeted
`esptool get-security-info` command.

Public-safe operator evidence:

```text
P1_R1_EXECUTION_ID=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_20261007_01
P1_R1_ERROR=security_COMMAND_FAILED_RC_2
ESPTOOL_VERSION=5.3.1
SERIAL_OPEN_RESULT=RESOURCE_BUSY
ERROR_CLASS=Could not open port / Errno 16 / Resource busy

FLASH_WRITE=false
FLASH_ERASE=false
NVS_WRITE=false
T1_MUTATION=false
READY_FOR_P2=false
STOP=true
```

A subsequent host-only diagnostic observed exactly one `/dev/cu.usbmodem*`
candidate and no current `lsof` owner.

```text
POSTFAIL_USB_MODEM_COUNT=1
POSTFAIL_PORT_OWNER=NONE_OBSERVED
```

This does **not** prove which process or driver held the serial endpoint at the
time of the failed open.

```text
DOMAIN=PHYSICAL_HARNESS
OBSERVED_CAUSE=SERIAL_PORT_OPEN_FAILED_RESOURCE_BUSY
EXACT_ROOT_CAUSE=TBD
PRODUCT_DEFECT=false
BOARD_CLEAN_STATE_CHANGED=false
CLEAN_BOARD_ELIGIBILITY=NOT_PROVEN
```

No successful chip/security/flash/NVS read occurred in R1.

## 2. R1 authorization disposition

The original P1 authorization was explicitly granted by the operator. The first
board-targeted `esptool` command was attempted, so the authorization is treated
as claimed and consumed even though the OS rejected the port open.

```text
R1_AUTHORIZATION_CLASS=NEW_CANDIDATE_BOARD_READONLY_ACCESS
R1_AUTHORIZATION_GRANTED=true
R1_AUTHORIZATION_CLAIMED=true
R1_AUTHORIZATION_CONSUMED=true
R1_REPLAY_PERMITTED=false
R1_AUTO_RETRY=false
```

The same board remains eligible to be considered by a successor because R1 did
not erase or write flash/NVS and did not establish any product runtime identity.

## 3. Repository history relevant to the successor

Existing repository evidence already treats local serial ownership as a
precondition rather than a product oracle.

### 3.1 PR #437 USB-only inspection

`docs/development/N3W_PR437_WIFI_RECOVERY_BUDGET_SOURCE_REPAIR_ALIGNMENT_20260921.md`
records:

```text
USBMODEM_CANDIDATE_COUNT=1
EXPECTED_PORT_OPEN_OWNER_COUNT=0
APPLICATION_SERIAL_OPEN=false
BOARD_RESET=false
FLASH_WRITE=false
NVS_WRITE=false
```

### 3.2 Existing physical-harness guards

`KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` already preserves adjacent rules:

- KF-043: bind the intended serial target before opening it; do not rely on a
  hard-coded `/dev/cu.usbmodem...` path.
- KF-046: application serial is not a passive oracle and must not be opened for
  this gate.
- Historical Stage2D9 execution treated USB/preflight failures before the
  execution boundary as fail-closed and non-mutating.

The exact R1 `Errno 16 / Resource busy` symptom was not found as a prior
repository incident. It therefore remains a new physical-harness observation,
with exact root cause `TBD`.

## 4. R2 design change

R2 preserves the original P1 product acceptance contract. It changes only the
local physical-harness preclaim sequence.

```text
R2_PRODUCT_ACCEPTANCE_SEMANTICS=UNCHANGED
R2_ARTIFACT_AUTHORITY=UNCHANGED
R2_CLEANLINESS_ORACLE=UNCHANGED
R2_PRODUCT_IDENTITY_DEFERRED=true
R2_NEW_GUARD=USB_SERIAL_OWNERSHIP_PRECLAIM
```

The R2 sequence is frozen as follows.

### 4.1 Before new board authorization

Allowed:

```text
repository rebind
artifact/hash rebind
esptool version query
host-only preparation
```

Forbidden:

```text
USB device access
serial open
board-targeted esptool
flash/NVS read
```

### 4.2 After explicit R2 read-only authorization, before authorization claim

Perform only non-opening target-locator checks:

```text
1. enumerate /dev/cu.usbmodem*
2. require exactly one candidate locator
3. run lsof -nP against that locator
4. require open-owner count == 0
5. perform one bounded second ownership check
6. require open-owner count == 0 again
```

These checks must not open application serial and must not invoke a board-targeted
`esptool` command.

If any preclaim check fails:

```text
R2_AUTHORIZATION_CLAIMED=false
R2_AUTHORIZATION_CONSUMED=false
BOARD_TARGETED_ESPTOOL=false
AUTO_RETRY=false
READY_FOR_P2=false
STOP=true
```

A failed preclaim does not consume the one-shot R2 execution authorization.

### 4.3 Claim boundary

Only after both ownership checks pass may the executor cross the claim boundary.

Immediately before invoking the first board-targeted command:

```text
R2_AUTHORIZATION_CLAIMED=true
R2_AUTHORIZATION_CONSUMED=true
```

The first board-targeted command remains the read-only ESP32-C6
`get-security-info` operation.

If that command again returns `Resource busy`:

```text
R2_RESULT=INVALID_REPEATED_PORT_OPEN_FAILURE
EXACT_ROOT_CAUSE=TBD
PRODUCT_DEFECT=false
AUTO_RETRY=false
READY_FOR_P2=false
STOP=true
```

Do not loop or automatically issue another board command.

### 4.4 Continue original P1 only after the first command succeeds

After successful `get-security-info`, continue the original frozen P1 contract:

```text
ESP32-C6 identity/security proof
-> 8MB flash-id
-> silicon-binding SHA256 uniqueness check
-> partition-table read-flash
-> every discovered NVS partition read-flash
-> offline N3-W residue inspection
-> public-safe closure
-> STOP
```

All original fail-closed rules remain in force.

## 5. R2 hard scope

```text
FLASH_WRITE=false
FLASH_ERASE=false
NVS_WRITE=false
APPLICATION_SERIAL_OPEN=false
PRODUCT_NORMAL_BOOT_ACCEPTANCE=false
WIFI_PROVISIONING=false
PAIRING_IMPORT=false
T1_MUTATION=false
MANAGER_DB_WRITE=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
PR522_MERGE=false
AUTO_P2=false
```

Private evidence remains local under a fresh R2 namespace. Raw ROM MAC, USB
locator, partition bytes and NVS bytes must not enter public GitHub evidence.

## 6. Successor authorization

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_R2_20261007_01
AUTHORIZATION_CLASS=NEW_CANDIDATE_BOARD_READONLY_ACCESS_R2
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

CANDIDATE_BOARD=same genuinely new candidate from R1
BOARD_ACCESS=false
READY_FOR_P2=false
STOP_BEFORE_NEW_R2_AUTHORIZATION=true
```

R2 must not start from the consumed R1 authorization.

## 7. Known-failure numbering boundary

Current repository `main` has known-failure numbering through KF-100, while
the stacked PR #522 branch carries an older copy of the central known-failure
file. Do not allocate a new KF number by editing that stale branch copy.

If this port-ownership incident is promoted to the central known-failure index,
reconcile against fresh `main` first and allocate the next non-conflicting ID.
Until then this document is the exact incident/preexecution authority.

## 8. Stop point

```text
R1=CLOSED_INVALID_PORT_BUSY
R2_PREEXECUTION_DESIGN=PASS
R2_PHYSICAL_EXECUTION=NOT_AUTHORIZED
BOARD_ACCESS=false
LIVE_MUTATION=false
NEXT_ACTION=REQUEST_EXPLICIT_R2_READONLY_BOARD_AUTHORIZATION
STOP=true
```
