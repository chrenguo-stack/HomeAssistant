# N3-W Production Gateway Selection V1
## Three-Board Write-Target Preflight Summary — 2026-09-23

Status: `CLOSED_PASS`

## 1. Gate

```text
TASK=N3W_PRODUCTION_GWSEL_V1_THREE_BOARD_WRITE_TARGET_PREFLIGHT_SUMMARY_20260923_01

BOARD_ACCESS=false
DOCUMENTATION_AND_GATE_ALIGNMENT_ONLY=true
AUTO_EXECUTE=false

FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_BOARD_MUTATION=false
```

This summary freezes the current A/B/C static write-target compatibility evidence
and the exact artifact authority. It does not authorize a firmware write.

## 2. Exact product / artifact authority

```text
PRODUCT_SOURCE=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

PRODUCT_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

ARTIFACT_ID=
10693728323

ARTIFACT_NAME=
n3w-production-gwsel-v1-r2-8c445f2-exact-source

ARTIFACT_OUTER_SIZE=
4281423

ARTIFACT_OUTER_SHA256=
e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814

RELEASE_BUNDLE_SHA256=
f7c7ac703e6b23040235020c92e480f08c602076d32afa18c8a37e5da3882598

PARTITION_TABLE_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

The wrong historical artifact `10691518958` remains forbidden for Gateway
Selection V1 physical use.

## 3. Identity parser authority

The first A/B preflight identity results were affected by the historical parser
defect that truncated a generic ESP32-C6 EUI-64 identity.

Current repair authority:

```text
IDENTITY_PARSER_REPAIR_SOURCE_HEAD=
b1587ea9ffb0a14b4c784bcfa8f1cb5f919faf18

IDENTITY_PARSER_REPAIR_CLOSURE_HEAD=
288accbc216176de0acab100233301c780571fb8

IDENTITY_PARSER_REPAIR_CI=
35815218810

IDENTITY_PARSER_REPAIR=PASS
```

Current reusable preflight authority:

```text
RUNBOOK=
docs/development/N3W_PRODUCTION_BOARD_WRITE_TARGET_PREFLIGHT_RUNBOOK.md

RUNBOOK_BLOB=
ff792c77e4ffe811aad05a27a90f87b01cca396b
```

The project hardware-ID contract remains:

```text
base_mac = canonical 6-byte ESP32-C6 base MAC
hardware_id = "ghw-c6-" + base_mac_without_colons
hardware_id_sha256 = SHA256(UTF-8 hardware_id)
```

Raw ROM MAC/base-MAC values are not public evidence.

## 4. Board A final authority

Final Board A closure:

```text
CLOSURE_HEAD=
349639269b1733df6dc2ae0cf378d54e34893b8c

BOARD_A_HARDWARE_ID_SHA256=
f1f1e36fe4784a26b936d6a2bc5d239ab531f5683aca91356a5e39f3f566b1eb

BOARD_A_IDENTITY_RECHECK=PASS
BOARD_A_HISTORICAL_IDENTITY_MATCH=PASS
BOARD_A_DISTINCT_FROM_BOARD_B=PASS

BOARD_A_PARTITION_BINDING=PASS
BOARD_A_SECURITY_COMPATIBILITY=PASS
BOARD_A_ARTIFACT_AUTHORITY_BINDING=PASS
BOARD_A_STATIC_WRITE_TARGET_COMPATIBILITY=PASS
```

Board A's earlier non-identity preflight facts remain valid because the identity
parser defect did not affect the independent chip, flash-size, security, partition
or artifact-validation paths.

## 5. Board B final authority

Final Board B closure:

```text
CLOSURE_HEAD=
bba5fdc8ae65aa2c5cb9ecf3d4c6b776c2331f91

BOARD_B_HARDWARE_ID_SHA256=
cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0

BOARD_B_IDENTITY_RECHECK=PASS
BOARD_B_HISTORICAL_IDENTITY_MATCH=PASS

BOARD_B_PREVIOUS_IDENTITY_CONFLICT=
SUPERSEDED_FALSE_POSITIVE

BOARD_B_PARTITION_BINDING=PASS
BOARD_B_SECURITY_COMPATIBILITY=PASS
BOARD_B_ARTIFACT_AUTHORITY_BINDING=PASS
BOARD_B_STATIC_WRITE_TARGET_COMPATIBILITY=PASS
```

The earlier A/B equal-identity result is not current evidence and must not be reused.

## 6. Board C final authority

Board C used the corrected parser before its first Gateway Selection V1 full
preflight and was directly bound to the frozen Board C historical identity.

Final Board C closure:

```text
CLOSURE_HEAD=
bd13a8683bdb8ced9adc5709363acba5dfdd7b5b

BOARD_C_HARDWARE_ID_SHA256=
d6ef3f98a35f06a5a8b8e7716a015e17336242128b314a1b3244b114fc6f72e2

BOARD_C_FROZEN_IDENTITY_MATCH=PASS

CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false

BOARD_C_PARTITION_BINDING=PASS
BOARD_C_SECURITY_COMPATIBILITY=PASS
BOARD_C_ARTIFACT_AUTHORITY_BINDING=PASS
BOARD_C_STATIC_WRITE_TARGET_COMPATIBILITY=PASS

OTADATA_READBACK_SHA256=
b7e293bb607d3bddb99b7f38a7a45afd5823c0c61e3216e67858bbc759535282
```

Board C OTA-data differs from earlier A/B readback evidence. That is permitted
because OTA-data is mutable boot-selection state and is not silicon identity.

## 7. Three-board adjudication

```text
BOARD_A_IDENTITY_BINDING=PASS
BOARD_B_IDENTITY_BINDING=PASS
BOARD_C_IDENTITY_BINDING=PASS

BOARD_A_STATIC_WRITE_TARGET_COMPATIBILITY=PASS
BOARD_B_STATIC_WRITE_TARGET_COMPATIBILITY=PASS
BOARD_C_STATIC_WRITE_TARGET_COMPATIBILITY=PASS

THREE_BOARD_STATIC_WRITE_TARGET_COMPATIBILITY=PASS
```

All three boards are therefore compatible targets for a separately authorized
Gateway Selection V1 firmware-write workflow, subject to fresh per-board pre-write
revalidation at the time of mutation.

## 8. Sequential physical-access history

The project maintained the one-board-at-a-time safety boundary.

The original full static preflights were performed sequentially for A and B. After
the identity parser defect was discovered, targeted identity-only recovery rechecks
were performed on B and then A, one connected board at a time. Board C was then
preflighted separately.

The recovery recheck order therefore revisited previously inspected boards and was
not a new A->B->C full-preflight pass. It did not involve simultaneous USB access.

Current safety invariant remains:

```text
ONE_PHYSICAL_TARGET_AT_A_TIME=true
SIMULTANEOUS_A_B_C_USB_PREFLIGHT=false
BOARD_BOUNDARY_STOP_REQUIRED=true
```

## 9. Supersession map

Earlier intermediate documents may contain state markers that were correct when
written but are now superseded.

Current interpretation:

```text
PARSER_REPAIR_CLOSURE_BOARD_A_PENDING=SUPERSEDED_BY_BOARD_A_RECHECK_PASS
PARSER_REPAIR_CLOSURE_BOARD_B_PENDING=SUPERSEDED_BY_BOARD_B_RECHECK_PASS

BOARD_B_CLOSURE_BOARD_A_PENDING=SUPERSEDED_BY_BOARD_A_RECHECK_PASS

BOARD_A_CLOSURE_BOARD_C_NOT_ACCESSED=
SUPERSEDED_BY_BOARD_C_PREFLIGHT_PASS

BOARD_B_IDENTITY_CONFLICT=
SUPERSEDED_FALSE_POSITIVE
```

This summary is the current cross-board authority for write-target compatibility.

## 10. Current mutation boundary

No firmware write has been authorized or executed in the three-board Gateway
Selection V1 synchronization route.

```text
FLASH_WRITE=false
NVS_WRITE=false
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
FULL_FLASH_ERASE=false
WRITE_AUTHORIZATION_GRANTED=false
```

A successful static preflight is not a permanent time-valid write token.

Before each future board mutation, the exact write executor must freshly revalidate
the target identity and the compatibility facts required by that write gate.

## 11. Write-route evidence currently available

Historical N3-W deployment authorities show a deliberately minimal write pattern:

```text
0x9000  ota_data_initial.bin
0x10000 firmware.bin
```

and historical deployments explicitly preserved:

```text
BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false
```

However, those historical write records are not themselves a Gateway Selection V1
write authorization.

The current Gateway Selection V1 repository has not yet frozen a dedicated exact
write executor that rebinds this minimal route to artifact `10693728323`.

Therefore:

```text
HISTORICAL_MINIMAL_WRITE_PATTERN_AVAILABLE=true
GWSEL_V1_EXACT_WRITE_ROUTE_FROZEN=false
HISTORICAL_WRITE_PATTERN_IS_CURRENT_WRITE_AUTHORITY=false
```

The exact Gateway Selection V1 write route must be established in a separate
preparation gate before any board is mutated.

## 12. Requirements for the next preparation gate

The next preparation gate must, without board access:

1. independently inspect the exact artifact `10693728323`, including its manifest,
   partition image and flash-argument metadata;
2. prove which artifact members and offsets are required for the intended minimal
   production update;
3. explicitly decide whether the Gateway Selection V1 route is limited to
   `ota_data_initial.bin` and `firmware.bin`;
4. keep bootloader, partition table, product NVS, factory image and full erase
   forbidden unless a newly discovered incompatibility is separately reviewed;
5. create a write executor that uses the corrected ESP32-C6 identity parser;
6. bind A, B and C to their exact public hardware-identity digests;
7. require exactly one connected board and explicit per-board write authorization;
8. perform fresh identity, chip, flash-size, security, partition and artifact checks
   immediately before each write;
9. fail closed on any mismatch and never auto-migrate, auto-erase, auto-repair or
   switch write strategy;
10. make all paste-ready operator shell commands compliant with the current zsh
    RUNBOOK rule;
11. preserve a hard stop after each board.

## 13. Proposed deployment sequence

The preparation gate should design for independent, sequential mutation:

```text
A -> STOP -> B -> STOP -> C -> STOP
```

No write authorization is inherited from one board to another.

After all three writes eventually complete, the physical validation route remains a
separate stage; write success alone must not be promoted to Gateway Selection V1
three-board functional acceptance.

## 14. Closure

```text
N3W_PRODUCTION_GWSEL_V1_THREE_BOARD_WRITE_TARGET_PREFLIGHT_SUMMARY=CLOSED_PASS

THREE_BOARD_STATIC_WRITE_TARGET_COMPATIBILITY=PASS

GWSEL_V1_EXACT_WRITE_EXECUTOR_READY=false
GWSEL_V1_EXACT_WRITE_ROUTE_FROZEN=false

BOARD_ACCESS=false
FLASH_WRITE=false
NVS_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false

STOP=true
```

## 15. Next ONE gate

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_GWSEL_V1_THREE_BOARD_EXACT_ARTIFACT_WRITE_PREPARATION_20260923_01

BOARD_ACCESS=false
SOURCE_AND_EXECUTOR_PREPARATION_ONLY=true
ARTIFACT_INSPECTION_REQUIRED=true
WRITE_ROUTE_FREEZE_REQUIRED=true
AUTO_EXECUTE=false

FLASH_WRITE=false
NVS_WRITE=false
```

That gate may prepare and test the exact write executor, but it must not access or
mutate any physical board.
