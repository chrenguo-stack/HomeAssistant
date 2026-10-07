## 0. 2026-10-08 P1 R2 clean-board closure

```text
P1_R2_CLEAN_BOARD_ELIGIBILITY=CLOSED_PASS
P1_R2_CLOSURE_AUTHORITY=docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_R2_CLOSURE_20261008.md

CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false
SILICON_BINDING_UNIQUE=true
HISTORICAL_BOARD_A_MATCH=false
HISTORICAL_BOARD_B_MATCH=false
BLOCKED_P4_BOARD_MATCH=false

PARTITION_TABLE_STATE=BLANK
NVS_PARTITION_COUNT=0
OLD_N3W_STATE_ABSENT=true

PRODUCT_HARDWARE_ID_SHA256=DEFERRED
FLASH_WRITE=false
FLASH_ERASE=false
NVS_WRITE=false
T1_MUTATION=false

READY_FOR_P2=true
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_T1_HEALTHY_BROKER_A_AND_MANAGER_PREBOOT_IDENTITY_SNAPSHOT_PREPARATION_20261007_01
AUTO_EXECUTE_NEXT_GATE=false
NEW_AUTHORIZATION_REQUIRED=true
```

P1 R2 is closed. The next stage is repository/T1 preparation for the healthy
Broker-A and Manager preboot identity snapshot; it is not authorized by the
consumed P1 R2 board-read authorization.

# N3-W Clean Product First-Pair Handoff and Runtime Identity — Progress Alignment — 2026-10-07

## 0. 2026-10-07 P1 R1 invalid closure / R2 successor

```text
P1_R1_RESULT=INVALID_PORT_BUSY
P1_R1_DOMAIN=PHYSICAL_HARNESS
P1_R1_OBSERVED_CAUSE=SERIAL_PORT_OPEN_FAILED_RESOURCE_BUSY
P1_R1_EXACT_ROOT_CAUSE=TBD
P1_R1_PRODUCT_DEFECT=false
P1_R1_BOARD_STATE_CHANGED=false
P1_R1_AUTHORIZATION_CONSUMED=true
P1_R1_REPLAY_PERMITTED=false

POSTFAIL_USB_MODEM_COUNT=1
POSTFAIL_PORT_OWNER=NONE_OBSERVED

R2_PREEXECUTION_DESIGN=PASS
R2_NEW_GUARD=USB_SERIAL_OWNERSHIP_PRECLAIM
R2_AUTHORIZATION_GRANTED=false
R2_BOARD_ACCESS=false
READY_FOR_P2=false

R2_PREEXECUTION_AUTHORITY=docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_R1_CLOSURE_AND_R2_PREEXECUTION_20261007.md
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_R2_20261007_01
```

R2 preserves the original clean-board eligibility contract. The only design change is to require two zero-owner checks before crossing the one-shot authorization claim boundary. A preclaim ownership failure stops without consuming the R2 execution authorization; the first board-targeted `esptool` command remains the claim boundary.

```text
STATUS=CURRENT_PROGRESS_ALIGNMENT
REPOSITORY=chrenguo-stack/HomeAssistant
PR=522
PR_STATE=OPEN_DRAFT
MERGE=false
```

## 1. Current product-source authority

```text
SOURCE_REPAIR=CLOSED_PASS
SOURCE_HEAD=629f096a32e087087ea32d30707dcc3cd6295e5d
SOURCE_TREE=0b97a97a63d7e251ed92cc96507386b454709161
SOURCE_REPAIR_CI=PASS
EXACT_SOURCE_READBACK=PASS
```

The clean-product first-pair repair now includes:

- production LCD page 5 GHN3W2 pairing QR after Manager hello acceptance;
- dedicated pairing QR separate from Wi-Fi provisioning QR;
- QR rebuild only when the exact payload changes;
- Manager `import-payload --payload-stdin` path through Manager-owned `pairing.sock`;
- strict hardware ID / pairing ID / 32-byte Setup Secret validation;
- preboot Manager identity snapshot plus runtime unique-new-pending identity binding;
- removal of raw pairing ID from ordinary product logs;
- preservation of the KF-050 durable boot-session repair.

The current product-source authority does not include later documentation-only commits.

## 2. Final source-repair CI

```text
PRODUCTION_CONVERGENCE_RUN=37590822231
CLEAN_BOARD_PREFLIGHT_RUN=37590822050
GREENHOUSE_MANAGER_RUN=37590822088
F1_RC2_FIRMWARE_RUN=37590822280
PUBLIC_SAFETY_RUN=37590822136
ALL_REQUIRED_CI=PASS
```

## 3. Replacement exact artifact

```text
EXACT_ARTIFACT_BUILD_AND_BINDING=CLOSED_PASS
BUILD_RUN_ID=37594598870
ARTIFACT_ID=11469977052
ARTIFACT_NAME=n3w-clean-product-first-pair-handoff-f1rc2-629f096-exact-source
ARTIFACT_OUTER_SHA256=8587c7bf130f2f17e81b4e4f7652780f372f6a61697cc240e72a6af7392a7dc8
RELEASE_ZIP_SHA256=55155717f7d8cbe1eb7cd856d42ffd2ac937b364fbbd80d52f1d37b47a46856c
FIRMWARE_BIN_SHA256=4e4442808fdff7fc3ca16eb379bd06741a9eea3364e31f1365be5e6bee325c65
FIRMWARE_FACTORY_BIN_SHA256=658645083ed2d83d6951abeb5f894dbde7d7124030c8bc1815683ed2bf24e914
BOOTLOADER_BIN_SHA256=985d0e0c5029d55d6cfab66470fe367200fd3e4e367e6a69ef1b557704c89fd5
PARTITIONS_BIN_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
OTA_DATA_INITIAL_BIN_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

Binding authority:

`docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_REPLACEMENT_EXACT_ARTIFACT_BUILD_AND_BINDING_20261007.md`

The older artifact bound to source `157448b...` is historical P3/P4 evidence only and is forbidden for resumed final clean-product acceptance.

## 4. Physical-acceptance plan

```text
CLEAN_BOARD_PHYSICAL_ACCEPTANCE_PREEXECUTION=PASS
PREEXECUTION_DOC=docs/development/N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_PHYSICAL_ACCEPTANCE_PREEXECUTION_20261007.md
BLOCKED_P4_BOARD_REUSE_AS_CLEAN=false
```

The planned physical route is:

```text
P1 new-board read-only eligibility
P2 T1/Broker-A readiness + Manager preboot identity snapshot
P3 full erase + four-region replacement-artifact write + readback
P4 normal Wi-Fi + optical LCD GHN3W2 + identity binding + pairing.sock import + KF-050 interruption
P5 healthy Direct baseline
P6 real T1 A->B relocation
P7 cold-start revalidation at B
```

The identity contract is now:

```text
SILICON_BINDING_SHA256=preboot physical-board locator only
PRODUCT_HARDWARE_ID_SHA256=runtime LCD/Manager identity only
PAIRING_ID_SHA256=current first-pair transaction only
```

The raw GHN3W2 payload and Setup Secret are private execution material and must not enter GitHub, ChatGPT, shell argv or public evidence.

## 5. Current stop point

No new board has been accessed under the replacement-artifact route.

```text
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH_ERASE=false
FLASH_WRITE=false
T1_MUTATION=false
MANAGER_REPLAY_MUTATION=false
MANAGER_HIGH_WATER_CLEAR=false
MERGE=false
```

The previously blocked P4 board remains historical evidence and must not be erased/reused as a new clean candidate.

## 6. Next ONE gate

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_SETUP_SECRET_HANDOFF_AND_RUNTIME_IDENTITY_CLEAN_BOARD_ELIGIBILITY_READONLY_PREFLIGHT_20261007_01
```

This next gate is read-only with respect to the board and live T1 runtime. It may inspect one genuinely new candidate board only after fresh board-access authorization. It must not erase or write flash, open application serial as a passive oracle, mutate T1, or clear Manager replay/high-water state.

## 7. Repository state

```text
REPOSITORY_MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
PR522_STATE=OPEN_DRAFT
PR522_MERGED=false
PR522_MERGEABLE=true
PR522_MERGE=false
```

PR #522 remains intentionally unmerged pending physical acceptance and the separate full-channel fallback physical RF axis.


## 6.1 Read-only preflight executor drift

Fresh source readback found that the existing repository helper:

`tools/execution_packages/n3w/auto_safe_fallback/clean_board_eligibility_readonly_preflight/executor.py`

still hard-codes the superseded `157448b...` source and artifact `11320812037`.

```text
PREFLIGHT_EXECUTOR_ARTIFACT_BINDING=STALE
PRODUCT_DEFECT=false
PHYSICAL_PRODUCT_BLOCKER=false
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_GATE_DSL_EXECUTION_PERMITTED=true
```

The next session must not use that stale helper as artifact authority and must not stop merely because the helper is stale. Under the formal DSL execution model, mechanically execute the bounded read-only preflight from the frozen replacement-artifact inputs in the handoff using already-installed tools. Do not patch or replace the helper inside the physical read-only gate unless a separate tooling change is explicitly authorized.

