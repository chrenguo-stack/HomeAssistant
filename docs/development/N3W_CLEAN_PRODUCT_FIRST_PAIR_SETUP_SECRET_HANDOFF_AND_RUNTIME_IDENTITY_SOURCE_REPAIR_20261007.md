# N3-W Clean Product First-Pair Setup-Secret Handoff and Runtime Identity Source Repair — 2026-10-07

```text
TASK=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_SOURCE_REPAIR_20261007_01
STATUS=IMPLEMENTED_CI_PENDING
DESIGN_BASE=6cf5f31daefa84a98b3c6711dcb19455a78a1014
SOURCE_REPAIR_CODE_HEAD=8085e6d50ca4d0e9fb7342e5fbffe437857f5d06
BOARD_ACCESS=false
T1_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
MERGE=false
```

## 1. Scope

This source-only gate repairs the two blockers found during clean-product P4:

1. the production device had no normal-product surface that exposed the board-generated `GHN3W2` first-pair payload to the user/operator;
2. the clean-board preflight incorrectly labeled a ROM/base-MAC-derived locator as the Manager product hardware identity.

No current board or T1 runtime was accessed or mutated in this gate.

## 2. Production LCD repair

The existing five-page LCD layout is preserved. Page 4 (the fifth page) is now state-sensitive.

```text
Wi-Fi disconnected + unprovisioned
-> existing Wi-Fi provisioning QR

Wi-Fi connected + unprovisioned + Manager hello accepted
-> GHN3W2 first-pair QR

Wi-Fi connected + unprovisioned + handoff not ready
-> searching for Manager

provisioned + Wi-Fi connected
-> existing connected page

provisioned + Wi-Fi disconnected
-> network offline status, no pairing QR
```

The production N3-W transport package updates neutral display globals. The shared F1.0-RC2 display package does not directly depend on the N3-W component, preserving compilation of the non-N3-W base target.

The pairing client exposes a bounded `handoff_ready` state. It becomes true only after the Manager accepts the exact hello transaction for the current hardware/pairing identity and returns a proceed disposition. Pairing intent renewal and successful final acknowledgement clear the state.

The raw `GHN3W2` payload is not written to normal product logs by this repair.

## 3. Manager intake repair

The supported CLI now adds:

```text
greenhouse-manager-pairing import-payload --payload-stdin
```

The command:

- accepts one bounded complete `GHN3W2` payload from stdin;
- strictly parses its hardware ID, pairing ID and Setup Secret;
- does not print the payload or Setup Secret;
- calls the existing `import_setup_secret_over_socket()` path;
- therefore retains the Manager-owned `pairing.sock` contract.

The existing Manager coordinator remains the final authority: Setup Secret import is rejected unless the exact hardware ID and pairing ID currently match a pending registration.

## 4. Acceptance identity repair

The clean-board executor schema advances to version 2.

The esptool ROM/base-MAC-derived value is now explicitly named a silicon binding:

```text
SILICON_BINDING_SHA256=physical-board locator only
PRODUCT_HARDWARE_ID_SHA256=DEFERRED
```

The executor no longer claims that this value is the Manager runtime hardware identity.

Manager-history checking now requires an explicitly supplied runtime product identity:

```text
--product-hardware-id-sha256
IDENTITY_AUTHORITY=RUNTIME_QR_EQUALS_MANAGER_PENDING
```

Final clean-product acceptance must bind the hardware ID optically obtained from the production LCD `GHN3W2` payload to the newly observed Manager pending registration before importing the Setup Secret.

The low-level reason for the previously observed ROM/runtime identity discrepancy is intentionally not inferred in this gate.

## 5. Regression coverage

New or extended coverage includes:

- production first-pair LCD/source contract;
- complete `GHN3W2` CLI parsing and non-echo behavior;
- silicon-binding versus runtime-product-identity semantics;
- full F1.0-RC2 N3-W target configuration and compile.

Source repair plus CI-only follow-up remains source-only and adds focused tests without touching board/T1 runtime state.

## 6. CI binding

After the CI-only repair follow-up, the following final-head runs were queued:

```text
SOURCE_REPAIR_CODE_HEAD=8085e6d50ca4d0e9fb7342e5fbffe437857f5d06
PRODUCTION_CONVERGENCE_RUN=37570672418
CLEAN_BOARD_PREFLIGHT_RUN=37570672324
GREENHOUSE_MANAGER_RUN=37570672481
F1_RC2_FIRMWARE_RUN=37570672403
CI_STATUS=PENDING
```

Do not mark this source-repair gate PASS until the required runs complete successfully and the exact code head is reviewed.

## 7. Boundary

```text
FIRST_PAIR_HANDOFF_AND_IDENTITY_SOURCE_REPAIR=IMPLEMENTED_CI_PENDING
REPLACEMENT_EXACT_ARTIFACT=NOT_BUILT
PHYSICAL_ACCEPTANCE_RESUME=false
CURRENT_BLOCKED_BOARD_ERASE=false
MERGE=false

NEXT_ONE_GATE=WAIT_FOR_SOURCE_REPAIR_CI_AND_REVIEW
```
