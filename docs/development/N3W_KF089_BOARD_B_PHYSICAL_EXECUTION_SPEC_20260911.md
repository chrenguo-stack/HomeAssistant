# N3-W KF-089 Board B Authorized Physical Execution Specification — 2026-09-11

Status: `AUTHORIZED_EXECUTION_SPEC_FROZEN`  
Authorization: `N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_20260911_01`  
Target: Board B only.  
This specification does not authorize Board A access or any PR merge.

## 1. Required authorities

Before any physical-device open, fresh-rebind all of the following:

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_20260911_01
AUTHORIZATION_GRANTED=true
REPLAY_PERMITTED=false

REVIEWED_IMPLEMENTATION_HEAD=b8eb0aec6d26d3905e8bc861625c1e20f1c40ba3
TOOL_GIT_BLOB=e7b0019cdb9673fbf4e23653dec561ea40ff757c
TEST_GIT_BLOB=5b4405b178384e2f3326c6ad0a3a963508d723e4
TOOL_VERSION=0.2.2-review
TOOL_MODE=BOARD_B_RECOVERY_ONLY

ESPTOOL_VERSION=5.2.0
ESPTOOL_WRAPPER_SHA256=a8461ddc0852eb1d00cf9d13bfc7698a3cad92871e51f2c4d1ff7ee2561150be

FIRMWARE_BIN_SIZE=1115648
FIRMWARE_BIN_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b

EXPECTED_BOARD_B_IDENTITY_SOURCE=EXISTING_PRIVATE_TRUSTED_EVIDENCE
EXPECTED_BOARD_B_IDENTITY_BOUND=true
```

Use the exact Python interpreter proven by the P0R1 closure. Do not install, upgrade, rebuild, or substitute anything. Any mismatch means STOP before device open.

## 2. Private evidence root

Create a fresh empty private execution root outside every Git worktree. Best-effort permissions: root 0700, files 0600. It may contain private identity, absolute paths, raw readback bytes, and local authorization evidence. Never commit it publicly.

## 3. Port discovery and identity rule

Physical access is now authorized, but a USB path is only a locator.

A bounded serial-device enumeration may be used to locate the candidate endpoint. Enumeration alone must not be treated as identity proof. Do not toggle DTR/RTS or reset the board during discovery.

Fresh ROM silicon identity must be proven by the Guard against the expected private Board B identity. Any mismatch means STOP. Do not try a second board or second candidate automatically under the same authorization.

## 4. Authorization claim / anti-replay

Immediately before the first device open, create a private durable claim record using exclusive creation semantics so an existing claim cannot be overwritten. It must bind:

```text
AUTHORIZATION_ID
TARGET_ROLE=BOARD_B
TOOL_GIT_BLOB
FIRMWARE_SHA256
EXPECTED_PRIVATE_IDENTITY_BINDING_PRESENT=true
CLAIMED=true
REPLAY_PERMITTED=false
```

After that claim is created, no second physical workflow invocation is allowed with this authorization ID. For fail-closed anti-replay handling, if the first open/connection attempt fails after claim, report the authorization as consumed and STOP; do not retry automatically.

## 5. Single allowed Guard invocation

After successful pre-open rebind and authorization claim, invoke exactly one Board B recovery workflow:

```text
<EXACT_PYTHON> <EXACT_GUARD_PATH> \
  --python <EXACT_PYTHON> \
  --esptool <EXACT_ESP_IDF_V5_5_4_WRAPPER> \
  recover-app0-to-slot0 \
  --port <CANDIDATE_PORT> \
  --evidence-dir <FRESH_PRIVATE_GUARD_EVIDENCE_DIR> \
  --expected-base-mac <PRIVATE_EXPECTED_BOARD_B_BASE_MAC> \
  --authorization-id N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_20260911_01
```

The exact paths and private MAC stay in private evidence only.

Do not wrap this invocation in a retry loop. Do not invoke it a second time automatically for any reason.

## 6. Enforced physical sequence inside the Guard

The reviewed Guard must perform:

```text
fresh ROM identity
-> app0 exact readback: offset 0x10000, length 1115648
-> app0 SHA256 exact match
-> full otadata pre-read: offset 0x9000, length 0x2000
-> recovery plan
-> same mutation connection:
     ROM identity recheck
     app0 device-side freshness check
     exact otadata-preimage freshness check
-> at most one direct ROM mutation of one 32-byte OTA-select entry
-> full 0x2000 otadata post-readback
-> exact postcondition verification
```

Hard prohibitions:

```text
APP0_WRITE_ALLOWED=false
SECOND_APP0_FLASH_ALLOWED=false
BOOTLOADER_WRITE_ALLOWED=false
PARTITION_TABLE_WRITE_ALLOWED=false
NVS_HOST_WRITE_ALLOWED=false
GENERIC_WRITE_FLASH_ALLOWED=false
OTADATA_MUTATION_COUNT_MAX=1
MUTATION_RETRY=false
AUTO_SECOND_ATTEMPT=false
AUTO_ROLLBACK=false
```

## 7. STOP semantics

Before mutation, any of the following means STOP with zero mutation:

- source/toolchain/firmware authority mismatch;
- expected private identity unavailable;
- ROM identity mismatch;
- app0 exact readback failure;
- app0 size/hash mismatch;
- otadata pre-read/parse/plan failure;
- same-connection identity/app0/otadata freshness mismatch.

If mutation boundary may have been entered and any exception occurs:

```text
NO_MUTATION_RETRY=true
NO_AUTO_ROLLBACK=true
NO_AUTO_BOOT=true
ONLY_ONE_BOUNDED_READONLY_FAILURE_STATE_CAPTURE=true
```

## 8. Normal boot boundary

If and only if the Guard returns full PASS including exact otadata post-verify with selected slot `app0`, one normal boot is authorized.

To avoid reintroducing unreviewed host reset semantics, the preferred normal-boot mechanism is one operator-performed manual power cycle/reset after Guard PASS. Do not use an additional flashing command to cause the boot.

If Guard does not return PASS, no normal boot is authorized by this execution path.

## 9. Bounded Schema-v5 runtime observation

After the one normal boot, bounded read-only runtime observation is permitted to prove that the Schema-v5 firmware starts. Do not mutate NVS, credentials, pairing state, broker/T1 state, or firmware during this observation.

If runtime observation requires a serial endpoint, open it read-only/best-effort without DTR/RTS reset where supported. If a safe no-reset observation path cannot be established, record `SCHEMA_V5_RUNTIME_OBSERVATION=NOT_PROVEN` rather than adding a new reset or flashing action.

## 10. Required closure

Return a public-safe closure exactly once after the workflow stops:

```text
=== N3W KF089 BOARD B EXISTING APP0 RECOVERY PHYSICAL EXECUTION CLOSURE ===

AUTHORIZATION_ID=N3W_KF089_BOARD_B_EXISTING_APP0_RECOVERY_TO_SLOT0_20260911_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=<true|false>
AUTHORIZATION_CONSUMED=<true|false>
REPLAY_PERMITTED=false

FRESH_SOURCE_REBIND=<PASS|FAIL>
FRESH_LOCAL_TOOLCHAIN_REBIND=<PASS|FAIL>
FRESH_FIRMWARE_BINDING=<PASS|FAIL>
FRESH_PRIVATE_TARGET_IDENTITY_BINDING=<PASS|FAIL>

PORT_DISCOVERY=<PASS|FAIL|NOT_EXECUTED>
ROM_IDENTITY_BINDING=<PASS|FAIL|NOT_EXECUTED>

APP0_READBACK_SIZE=<integer|NOT_EXECUTED>
APP0_READBACK_SHA256=<sha256|NOT_EXECUTED>
APP0_BINDING=<PASS|FAIL|NOT_EXECUTED>
APP0_WRITE_EXECUTED=false
SECOND_APP0_FLASH_EXECUTED=false

OTADATA_PRE_READ=<PASS|FAIL|NOT_EXECUTED>
OTADATA_PRE_SELECTED_SLOT=<app0|app1|UNKNOWN|NOT_EXECUTED>
SAME_CONNECTION_IDENTITY_RECHECK=<PASS|FAIL|NOT_EXECUTED>
SAME_CONNECTION_APP0_FRESHNESS=<PASS|FAIL|NOT_EXECUTED>
SAME_CONNECTION_OTADATA_FRESHNESS=<PASS|FAIL|NOT_EXECUTED>
OTADATA_MUTATION_EXECUTED=<true|false>
OTADATA_MUTATION_COUNT=<0|1>
OTADATA_POST_READ=<PASS|FAIL|NOT_EXECUTED>
OTADATA_POST_VERIFY=<PASS|FAIL|NOT_EXECUTED>
OTADATA_POST_SELECTED_SLOT=<app0|app1|UNKNOWN|NOT_EXECUTED>

MUTATION_RETRY_EXECUTED=false
AUTO_ROLLBACK_EXECUTED=false
NORMAL_BOOT_EXECUTED=<true|false>
NORMAL_BOOT_MECHANISM=<MANUAL|NOT_EXECUTED>
SCHEMA_V5_RUNTIME_OBSERVATION=<PASS|FAIL|NOT_PROVEN|NOT_EXECUTED>

RESULT=<PASS|STOP>
FIRST_FAILED_STAGE=<stage|NONE>
STOP_REASON=<public-safe reason|NONE>
NEXT_ONE_GATE=<gate>

=== END ===
```

Do not publish the full Board B identity, local absolute paths, or raw flash/otadata contents.