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


## 9. R2 operator authorization grant

```text
R2_AUTHORIZATION_GRANT_RECORDED=true
AUTHORIZATION_CLASS=NEW_CANDIDATE_BOARD_READONLY_ACCESS_R2
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
CANDIDATE_BOARD=same genuinely new candidate from R1
BOARD_TARGETED_ESPTOOL=false
NEXT_ACTION=HOST_ONLY_USB_OWNERSHIP_PRECLAIM
```

The operator explicitly authorized P1 R2 read-only access and confirmed continued use of the same genuinely new candidate board. Per the R2 contract, authorization is not claimed or consumed until the first board-targeted `esptool get-security-info` invocation begins after both zero-owner preclaim checks pass.


## 10. R2 first ownership preclaim result

Operator public-safe output from the first R2 preclaim:

```text
R2_PRECLAIM_RESULT=STOP_LOCATOR_UNSTABLE
USB_MODEM_COUNT_INITIAL=1
CHECK_1_OWNER_COUNT=0
SAME_LOCATOR=false
CHECK_2_OWNER_COUNT=NOT_REACHED
READY_FOR_BOARD_PROBE=false

AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
BOARD_TARGETED_ESPTOOL=false
FLASH_WRITE=false
FLASH_ERASE=false
NVS_WRITE=false
T1_MUTATION=false
STOP=true
```

The preclaim correctly failed closed before any serial open or board-targeted
`esptool` command. This does not establish whether the device temporarily
disappeared, re-enumerated under a different locator, or a second locator
appeared. Exact root cause remains `TBD`.

```text
PRODUCT_DEFECT=false
R2_AUTHORIZATION_STILL_AVAILABLE=true
AUTO_BOARD_RETRY=false
NEXT_ACTION=HOST_ONLY_USB_ENUMERATION_STABILITY_DIAGNOSIS
```

The next diagnostic must remain host-only: sample the `/dev/cu.usbmodem*`
candidate set over a bounded observation window without opening any serial
device. Only after a stable single-locator observation may the existing granted,
still-unclaimed R2 authorization proceed to a fresh ownership preclaim and then
the first board-targeted read-only probe.


## 11. R2 host-only USB enumeration stability diagnosis

The bounded 10-second host-only observation sampled the USB modem locator set
20 times without opening any serial device or invoking board-targeted esptool.

```text
R2_USB_ENUMERATION_STABILITY_RESULT=FAIL
OBSERVATION_SECONDS=10
SAMPLE_COUNT=20
DISTINCT_ENUMERATION_STATE_COUNT=2
STATE_A_USB_MODEM_COUNT=1
STATE_B_USB_MODEM_COUNT=0
ALL_SAMPLES_SINGLE_DEVICE=false
LOCATOR_STABLE=false

AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
BOARD_TARGETED_ESPTOOL=false
FLASH_WRITE=false
FLASH_ERASE=false
NVS_WRITE=false
T1_MUTATION=false
STOP=true
```

This is stronger evidence than the earlier one-shot `Resource busy` symptom:
the macOS serial locator itself is disappearing during an observation window.
The current evidence does not distinguish physical USB disconnect/power reset,
USB-device re-enumeration, native USB interface reset, or another host-side
USB-stack cause.

```text
DOMAIN=PHYSICAL_HARNESS
OBSERVED_CAUSE=USB_MODEM_ENUMERATION_DROPS_TO_ZERO
EXACT_ROOT_CAUSE=TBD
PRODUCT_DEFECT=false
R2_AUTHORIZATION_STILL_AVAILABLE=true
```

Do not invoke board-targeted esptool until the host can prove a stable USB
device/serial-interface presence. The next diagnostic remains host-only and
must compare USB-device presence with both `/dev/cu.usbmodem*` and
`/dev/tty.usbmodem*` presence over the same bounded window.


## 12. R2 USB parent vs serial-interface diagnosis

The follow-up host-only observation sampled both the USB parent device and
macOS serial device nodes for 10 seconds without opening either serial device.

```text
R2_USB_PARENT_STABLE_SERIAL_INTERFACE_UNSTABLE=true
OBSERVATION_SECONDS=10
SAMPLE_COUNT=20
DISTINCT_STATE_COUNT=2

ESPRESSIF_USB_ALWAYS_PRESENT=true
USB_JTAG_SERIAL_PID_ALWAYS_PRESENT=true

CU_ALWAYS_PRESENT=false
TTY_ALWAYS_PRESENT=false

OBSERVED_STATE_A=cu:1,tty:1,EspressifVID:1,USB-JTAG-SerialPID:1
OBSERVED_STATE_B=cu:0,tty:0,EspressifVID:1,USB-JTAG-SerialPID:1

AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
BOARD_TARGETED_ESPTOOL=false
STOP=true
```

This rules against a complete loss of the USB parent device during the sampled
window. The failure is now localized below the parent USB-device layer and at
or above the macOS serial-interface publication layer: the Espressif USB
device with the expected USB-JTAG/Serial PID remains present while both
`/dev/cu.usbmodem*` and `/dev/tty.usbmodem*` disappear.

```text
DOMAIN=PHYSICAL_HARNESS
FULL_USB_DEVICE_DISCONNECT_OBSERVED=false
SERIAL_BSD_NODE_PUBLICATION_UNSTABLE=true
EXACT_ROOT_CAUSE=TBD
PRODUCT_DEFECT=false
R2_AUTHORIZATION_STILL_AVAILABLE=true
```

Do not run board-targeted esptool yet. The next diagnostic should remain
host-only and inspect the macOS IOSerialBSDClient / USB-interface publication
state and recent USB/serial kernel log events across the same transition.


## 13. R2 macOS IOSerial publication diagnosis

The next host-only observation sampled `IOSerialBSDClient` together with both
BSD serial device-node classes for 10 seconds. No serial device was opened.

```text
R2_IOSERIAL_PUBLICATION_RESULT=UNSTABLE
OBSERVATION_SECONDS=10
SAMPLE_COUNT=20
DISTINCT_STATE_COUNT=2

STATE_A=cu:1,tty:1,ioserial:true
STATE_B=cu:0,tty:0,ioserial:false

CU_ALWAYS_PRESENT=false
TTY_ALWAYS_PRESENT=false
IOSERIAL_ALWAYS_PRESENT=false

AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
BOARD_TARGETED_ESPTOOL=false
STOP=true
```

Combined with the previous observation that the Espressif USB parent and
USB-JTAG/Serial PID remained continuously present, this localizes the observed
instability above the USB parent-device layer and at or below the macOS serial
client publication layer.

```text
USB_PARENT_DEVICE_STABLE=true
IOSERIALBSDCLIENT_PUBLICATION_UNSTABLE=true
BSD_SERIAL_NODE_PUBLICATION_UNSTABLE=true
FULL_USB_DEVICE_DISCONNECT_OBSERVED=false

DOMAIN=PHYSICAL_HARNESS
EXACT_ROOT_CAUSE=TBD
PRODUCT_DEFECT=false
R2_AUTHORIZATION_STILL_AVAILABLE=true
```

Do not invoke board-targeted esptool. The next host-only discriminator is to
sample the matching Espressif USB device's child `IOUSBHostInterface` objects
at the same time as `IOSerialBSDClient`. If the USB interfaces remain stable
while IOSerial disappears, the fault is below USB-interface enumeration and in
serial-driver/client publication. If the matching USB interface set changes,
the instability is at the device-interface/re-enumeration layer even though the
parent USB device remains present.


## 14. R2 USB-interface vs IOSerial diagnosis

The next host-only observation again proved that the Espressif USB parent
remained present while the macOS serial client and both BSD serial nodes
disappeared.

```text
OBSERVATION_SECONDS=10
SAMPLE_COUNT=20
DISTINCT_STATE_COUNT=2

USB_PARENT_ALWAYS_PRESENT=true
IOSERIAL_ALWAYS_PRESENT=false
CU_ALWAYS_PRESENT=false
TTY_ALWAYS_PRESENT=false

STATE_A=parent:1,ioserial:1,cu:1,tty:1
STATE_B=parent:1,ioserial:0,cu:0,tty:0

AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
BOARD_TARGETED_ESPTOOL=false
STOP=true
```

The attempted USB-interface discriminator did **not** produce usable interface
evidence: both sampled states returned an empty `interfaces` list. Therefore
`USB_INTERFACE_SET_STABLE=true` is a vacuous result from the diagnostic
parser and must not be treated as proof that the matching USB interface set
actually remained stable.

```text
R2_USB_INTERFACE_DIAGNOSIS=INCONCLUSIVE_EMPTY_INTERFACE_SET
USB_INTERFACE_SET_STABILITY=NOT_PROVEN
USB_PARENT_DEVICE_STABLE=true
IOSERIALBSDCLIENT_PUBLICATION_UNSTABLE=true
BSD_SERIAL_NODE_PUBLICATION_UNSTABLE=true
FULL_USB_DEVICE_DISCONNECT_OBSERVED=false

DOMAIN=PHYSICAL_HARNESS
EXACT_ROOT_CAUSE=TBD
PRODUCT_DEFECT=false
R2_AUTHORIZATION_STILL_AVAILABLE=true
```

The next diagnostic must remain host-only and use a direct
`IOUSBHostInterface` service query rather than inferring child interface
objects from the USB-parent plist tree.


## 15. External USB Serial/JTAG reference note

Espressif's USB Serial/JTAG programming guide documents two device-side
conditions that can make the host serial function disappear even while the
physical USB cable remains connected:

- application reconfiguration of the USB pins or disabling the USB Serial/JTAG
  controller;
- sleep entry, where the USB Serial/JTAG controller is not usable and the host
  may report the serial function disconnected or erroneous.

This external reference is consistent with the observed symptom class but does
not prove that either condition occurred on the current new candidate.

```text
ESPRESSIF_USB_SERIAL_JTAG_REFERENCE_REVIEW=NOTED
DEVICE_SIDE_SLEEP_OR_USJ_DISABLE=PLAUSIBLE_NOT_PROVEN
MACOS_SERIAL_PUBLICATION_DEFECT=PLAUSIBLE_NOT_PROVEN
EXACT_ROOT_CAUSE=TBD
```

The current P1 route therefore continues to require evidence rather than
assigning either host or device root cause.


## 16. R2 direct IOUSBHostInterface observation

The direct host-only query observed the Espressif USB parent continuously and at
least one matching IOUSBHostInterface continuously, but the number of matching
interfaces varied and IOSerial visibility differed from the BSD node snapshot
within one sequential sample.

```text
R2_DIRECT_IOUSBHOSTINTERFACE_RESULT=MIXED_NONATOMIC_TRANSITION
OBSERVATION_SECONDS=10
SAMPLE_COUNT=20
DISTINCT_STATE_COUNT=3

USB_PARENT_ALWAYS_PRESENT=true
USB_INTERFACE_ALWAYS_PRESENT=true
MATCHING_USB_INTERFACE_COUNTS=3,4

IOSERIAL_ALWAYS_PRESENT=false
CU_ALWAYS_PRESENT=true
TTY_ALWAYS_PRESENT=true

STATE_A=parent:1,interfaces:4,ioserial:1,cu:1,tty:1
STATE_B=parent:1,interfaces:3,ioserial:1,cu:1,tty:1
STATE_C=parent:1,interfaces:4,ioserial:0,cu:1,tty:1

AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
BOARD_TARGETED_ESPTOOL=false
STOP=true
```

Interpretation is intentionally bounded. The host queries are sequential rather
than atomic, so `ioserial:0` with `cu:1,tty:1` can represent a transition
caught between observations and must not be classified as a persistent orphan
device-node state. Likewise, a 3/4 matching-interface count establishes that
the matching interface-service inventory was not constant under this query, but
does not by itself identify which exact interface detached or why.

```text
USB_PARENT_DEVICE_STABLE=true
MATCHING_USB_INTERFACE_INVENTORY_CONSTANT=false
SERIAL_PUBLICATION_INTERMITTENT=true
EXACT_ROOT_CAUSE=TBD
PRODUCT_DEFECT=false
R2_AUTHORIZATION_STILL_AVAILABLE=true
```

Do not run board-targeted esptool yet. The next discriminator should be a
host-only event/log capture around one transition, correlating USB interface and
serial-client attach/detach messages. No serial open is needed.


## 17. R2 direct-interface inventory result and next disposition

The direct IOUSBHostInterface sample produced three public-safe states:

```text
STATE_A=parent:1,interfaces:4,ioserial:1,cu:1,tty:1
STATE_B=parent:1,interfaces:3,ioserial:1,cu:1,tty:1
STATE_C=parent:1,interfaces:4,ioserial:0,cu:1,tty:1

USB_PARENT_ALWAYS_PRESENT=true
USB_INTERFACE_ALWAYS_PRESENT=true
R2_INTERFACE_INVENTORY_RESULT=NONCONSTANT_3_4
IOSERIAL_ALWAYS_PRESENT=false
CU_ALWAYS_PRESENT=true
TTY_ALWAYS_PRESENT=true

AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
BOARD_TARGETED_ESPTOOL=false
STOP=true
```

The individual host queries within each sample are sequential, not atomic.
Therefore `ioserial:0` together with still-present BSD device nodes is treated
as a transition/race observation, not a persistent orphan-node condition.
However, the direct interface-service inventory itself was not constant (3/4)
while the USB parent remained present.

Current bounded interpretation:

```text
USB_PARENT_STABLE=true
USB_INTERFACE_SERVICE_INVENTORY_STABLE=false
SERIAL_PUBLICATION_INTERMITTENT=true
FULL_USB_DEVICE_DISCONNECT_OBSERVED=false
EXACT_ROOT_CAUSE=TBD
PRODUCT_DEFECT=false
```

Espressif documentation states that USB Serial/JTAG becomes unusable during
light/deep sleep and can appear disconnected to the host; application-side
pin/controller changes can also make it disappear. This makes current
factory/application runtime behavior a plausible device-side explanation, but
it is not yet proven.

Repository history also contains KF-088: controlled RESET can transiently sample
GPIO9 low and place ESP32-C6 in ROM Download Mode. Therefore a reset/BOOT action
must not be introduced casually as an untracked diagnostic. If the next step
deliberately enters ROM Download Mode to isolate the running application from
the USB-serial instability, it must be treated as an explicit physical-harness
step with its own recorded authorization boundary and post-action mode proof.

```text
R2_AUTHORIZATION_STILL_AVAILABLE=true
R2_BOARD_PROBE_NOT_STARTED=true
NEXT_DISPOSITION=PREPARE_CONTROLLED_ROM_DOWNLOAD_MODE_ISOLATION_STEP
AUTO_EXECUTE=false
```


## 18. R2 ROM Download Mode isolation authorization

The operator explicitly authorized one deliberate BOOT+RESET transition on the
same genuinely new candidate board for USB-stability isolation only.

```text
ROM_DOWNLOAD_MODE_ISOLATION_AUTHORIZATION_GRANTED=true
ROM_DOWNLOAD_MODE_ISOLATION_AUTHORIZATION_CLAIMED=false
ROM_DOWNLOAD_MODE_ISOLATION_AUTHORIZATION_CONSUMED=false

ALLOWED_PHYSICAL_ACTION=one BOOT+RESET sequence to enter ESP32-C6 ROM Download Mode
FLASH_WRITE=false
FLASH_ERASE=false
NVS_WRITE=false
APPLICATION_SERIAL_OPEN=false
BOARD_TARGETED_ESPTOOL=false
POST_ACTION_SCOPE=host-only USB/serial publication observation
AUTO_P1_PROBE=false
AUTO_P2=false
```

The existing P1 R2 read-only board-probe authorization remains separately
granted but unclaimed/unconsumed. It is not consumed by the host-only
post-ROM observation. The ROM-isolation authorization becomes claimed/consumed
when the operator performs the authorized BOOT+RESET action.


## 19. R2 ROM Download Mode USB stability result

After the explicitly authorized BOOT+RESET isolation action, the same candidate
was observed for 10 seconds using host-only USB/serial publication checks.

```text
ROM_DOWNLOAD_MODE_ISOLATION_AUTHORIZATION_CLAIMED=true
ROM_DOWNLOAD_MODE_ISOLATION_AUTHORIZATION_CONSUMED=true

ROM_DOWNLOAD_MODE_USB_STABILITY=PASS
OBSERVATION_SECONDS=10
SAMPLE_COUNT=20
DISTINCT_STATE_COUNT=1

USB_PARENT_ALWAYS_PRESENT=true
IOSERIAL_ALWAYS_PRESENT=true
CU_ALWAYS_PRESENT=true
TTY_ALWAYS_PRESENT=true

OBSERVED_STATE=parent:1,ioserial:1,cu:1,tty:1

P1_R2_AUTHORIZATION_CLAIMED=false
P1_R2_AUTHORIZATION_CONSUMED=false
BOARD_TARGETED_ESPTOOL=false
FLASH_WRITE=false
FLASH_ERASE=false
NVS_WRITE=false
STOP=true
```

This is strong discriminator evidence that the earlier serial-publication
instability is associated with the previous running-board state rather than a
persistent loss of the physical USB parent/device path. It does not prove the
exact mechanism inside the previous application/runtime.

```text
PREVIOUS_RUNTIME_ASSOCIATION=STRONGLY_SUPPORTED
EXACT_RUNTIME_MECHANISM=TBD
MACOS_PERSISTENT_USB_FAILURE_NOT_SUPPORTED_BY_ROM_OBSERVATION=true
PRODUCT_DEFECT=false
```

The already-granted P1 R2 read-only board-probe authorization remains available.
Before its first board-targeted command, the executor must repeat the two
zero-owner preclaim checks. The first successful attempt to invoke read-only
`get-security-info` is the R2 authorization claim/consume boundary.
