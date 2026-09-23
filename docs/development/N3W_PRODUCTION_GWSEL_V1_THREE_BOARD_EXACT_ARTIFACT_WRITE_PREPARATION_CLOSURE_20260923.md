# N3-W Production Gateway Selection V1
## Three-Board Exact Artifact Write Preparation Closure — 2026-09-23

Status: `CLOSED_PASS`

## 1. Gate

```text
TASK=N3W_PRODUCTION_GWSEL_V1_THREE_BOARD_EXACT_ARTIFACT_WRITE_PREPARATION_20260923_01

BOARD_ACCESS=false
SOURCE_AND_EXECUTOR_PREPARATION_ONLY=true
AUTO_EXECUTE=false

FLASH_WRITE=false
NVS_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false
```

## 2. Exact preparation authority

```text
BRANCH=
exec/n3w-production-gwsel-v1-three-board-exact-write-preparation-20260923

HEAD=
33e6658244146d890887876ba18f32dd61a879b5

TREE=
42c207566981de2d8841275771be736b76236aad

CI_RUN_ID=
35819186201

CI_RESULT=SUCCESS
```

Final exact-head CI passed:

```text
COMPILE_EXACT_WRITE_EXECUTOR=PASS
EXACT_WRITE_EXECUTOR_TESTS=PASS
REUSABLE_RUNBOOK_TESTS=PASS
EXACT_PRODUCTION_ARTIFACT_DOWNLOAD=PASS
EXACT_ARTIFACT_MINIMAL_WRITE_ROUTE_VALIDATION=PASS
SOURCE_WRITE_SCOPE_CONTRACT=PASS
PUBLIC_REPOSITORY_SAFETY=PASS
```

## 3. Exact artifact authority

```text
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

PRODUCT_SOURCE=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

PRODUCT_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181
```

The exact-head CI independently downloaded this artifact and validated the frozen
write route against its real bytes.

## 4. Frozen exact minimal write route

Gateway Selection V1 is now bound to:

```text
WRITE 0x9000  ota_data_initial.bin
WRITE 0x10000 firmware.bin

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FACTORY_IMAGE_WRITE=false
FULL_FLASH_ERASE=false
```

The artifact's bundled `flash_args` remains layout evidence only.

```text
BLIND_EXECUTION_OF_RELEASE_FLASH_ARGS=FORBIDDEN
```

The route is valid only when fresh pre-write inspection proves the expected target
identity, ESP32-C6, 8 MiB flash, security state and exact partition table.

## 5. Frozen partition layout

```text
otadata   offset=0x9000   size=0x2000
phy_init  offset=0xb000   size=0x1000
app0      offset=0x10000  size=0x3c0000
app1      offset=0x3d0000 size=0x3c0000
nvs       offset=0x790000 size=0x70000

PARTITION_TABLE_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

## 6. Exact write executor

Prepared executor:

```text
tools/execution_packages/n3w/production/gwsel_v1_three_board_write/executor.py
```

It binds the repaired ESP32-C6 identity parser and all three frozen public hardware
identities.

Execution model:

```text
FRESH_READONLY_PREFLIGHT
-> EXPLICIT_BOARD_SPECIFIC_WRITE_AUTHORIZATION
-> FRESH_TARGET_REVALIDATION
-> SINGLE_USE_PREFLIGHT_CLAIM
-> MINIMAL_TWO_REGION_WRITE
-> POSTWRITE_THREE_REGION_READBACK
-> STOP
```

Preflight maximum age:

```text
PREFLIGHT_MAX_AGE_SECONDS=900
```

No board inherits another board's authorization.

## 7. Mandatory post-write readback

A future board write is PASS only if all three values match:

```text
OTADATA_READBACK_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

APPLICATION_READBACK_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

PARTITION_TABLE_READBACK_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

## 8. Failure policy

Once a board-specific authorization is claimed:

```text
AUTO_RETRY=false
AUTO_REFLASH=false
AUTO_ERASE=false
AUTO_REPAIR=false
AUTO_PARTITION_MIGRATION=false
AUTO_NVS_ERASE=false
AUTO_FACTORY_IMAGE_FALLBACK=false
STOP_AND_REVIEW=true
```

A disconnect, write failure, unexpected reset or readback mismatch must stop the
route.

## 9. Sequential deployment boundary

The prepared route is:

```text
A -> STOP -> B -> STOP -> C -> STOP
```

For every board:

```text
single connected target
fresh read-only preflight
explicit reset / ROM access authorization
STOP
explicit board-specific write authorization
write
readback verification
STOP
```

## 10. RUNBOOK authority

The reusable production RUNBOOK now includes the exact write-gate contract:

```text
docs/development/N3W_PRODUCTION_BOARD_WRITE_TARGET_PREFLIGHT_RUNBOOK.md
```

At this closure the RUNBOOK contains:

```text
CORRECTED_EUI64_IDENTITY_PARSER=true
OTADATA_NOT_USED_AS_IDENTITY=true
PASTE_READY_ZSH_RULE=true
EXACT_WRITE_GATE_RULE=true
SINGLE_USE_PREFLIGHT=true
MANDATORY_POSTWRITE_READBACK=true
SEQUENTIAL_BOARD_STOP=true
```

## 11. Closure

```text
N3W_PRODUCTION_GWSEL_V1_THREE_BOARD_EXACT_ARTIFACT_WRITE_PREPARATION=CLOSED_PASS

THREE_BOARD_STATIC_WRITE_TARGET_COMPATIBILITY=PASS

GWSEL_V1_EXACT_WRITE_ROUTE_FROZEN=true
GWSEL_V1_EXACT_WRITE_EXECUTOR_READY=true
GWSEL_V1_EXACT_WRITE_EXECUTOR_CI=PASS

BOARD_ACCESS=false
FLASH_READ=false
FLASH_WRITE=false
NVS_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false

STOP=true
```

## 12. Next ONE gate

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_GWSEL_V1_BOARD_A_EXACT_WRITE_PREFLIGHT_20260923_01

BOARD_LABEL=A
BOARD_ACCESS_REQUIRED=true
READ_ONLY=true
FLASH_WRITE=false
NVS_WRITE=false
TEMPORARY_RESET_ROM_ENTRY_REQUIRES_EXPLICIT_AUTHORIZATION=true
AUTO_EXECUTE=false
```

The next gate is still read-only. It does not itself authorize firmware mutation.
