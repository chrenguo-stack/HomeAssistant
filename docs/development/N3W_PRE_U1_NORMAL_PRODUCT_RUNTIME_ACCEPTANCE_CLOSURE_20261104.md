# N3-W Pre-U1 normal product runtime acceptance closure

Date: 2026-11-04

## 1. Overall result

```text
PLAN=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE
RESULT=CLOSED_PASS

PRE_U1_G0_RESULT=CLOSED_PASS
PRE_U1_G1_RESULT=CLOSED_PASS
PRE_U1_G2_RESULT=CLOSED_PASS
PRE_U1_G3_RESULT=CLOSED_PASS
PRE_U1_G4_RESULT=CLOSED_PASS
PRE_U1_G5_RESULT=CLOSED_PASS

PRE_U1_BUSINESS_RUNTIME_REFERENCE_FROZEN=true
PRE_U1_UPGRADE_SAFETY_REVALIDATION=PASS
U0_REOPEN=false
U1_MANAGER_A_TO_B_MAY_BE_RECONSIDERED=true
U1_AUTO_RESUME=false
```

## 2. G5 exact upgrade-safety revalidation

G5 reused the exact reviewed updater package used for U0 rather than rebuilding a new observer.

```text
UPDATER_ARTIFACT_ID=13261072174
UPDATER_ARTIFACT_DIGEST=sha256:cb070fdc1a10b2a17675449b3fc0e4bc868fac88a1e1f878ca2203a5d4b39aac
UPDATER_PYZ_SHA256=54f2e6299fa8905d33033ea86b5d449f16ad4dcd6ae8c7a3e9d647d6001e22fa
UPDATER_CONTROL_HEAD=4dd39befedce891bd2db3cc84c592d41f778bc51
```

Two fresh live T1_B baseline reads were taken without intervening mutation:

```text
BASELINE_READ_1_RC=0
BASELINE_READ_2_RC=0
BASELINE_READ_1_BYTES=2275
BASELINE_READ_2_BYTES=2275
BASELINE_READ_1_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc
BASELINE_READ_2_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc
BASELINE_CMP_EXIT=0
FRESH_BASELINE_READS_BYTE_IDENTICAL=true
FRESH_BASELINE_EQUALS_U0_BASELINE_A=true
```

This is the strongest planned G5 result: normal Home Assistant onboarding, real Node A sensor use, Node B first registration, two-node operation, DynSec population growth and HA registry growth did not change any U0 hard upgrade authority.

The exact baseline still freezes the same stack images, platforms, image-binding modes, runtime-contract hashes, fixed configuration hashes, persistent path authority, supported SQLite schema hashes, MQTT identities, CA hashes, Home Assistant storage versions and Dynamic Security structural authority.

## 3. Frozen normal-business reference

Machine-readable public-safe reference:

```text
infra/n3w-t1/clean-reference/pre-u1-business-runtime-reference-20261104.json
```

Frozen business facts:

```text
REGISTERED_NODE_COUNT=2
ACTIVE_NODE_ID_LEASE_COUNT=2
ACTIVE_CREDENTIAL_ASSIGNMENT_COUNT=2
ACTIVE_APPLICATION_NODE_COUNT=2
ACTIVE_OR_GRACE_APPLICATION_EPOCH_COUNT=2
UNRESOLVED_FIRST_REGISTRATION_COUNT=0

NODE_A_NODE_ID_SHA256=7c5197ca0643ea0669c2ee43d5d89a994b09b0394fdd7e9872fea5aa4d97e090
NODE_B_NODE_ID_SHA256=589486b4e4e7fb05fc0a7e8994d977b67c60ce72770b80af6ee74eef0bd1d724

DYNSEC_CLIENT_COUNT=6
DYNSEC_GROUP_COUNT=1
DYNSEC_ROLE_COUNT=12

HA_CONFIG_ENTRY_COUNT=11
HA_DEVICE_REGISTRY_COUNT=7
HA_ENTITY_REGISTRY_COUNT=41
HA_NODE_A_DEVICE_MATCH_COUNT=1
HA_NODE_A_ENTITY_COUNT=17
HA_NODE_B_DEVICE_MATCH_COUNT=1
HA_NODE_B_ENTITY_COUNT=6

HA_STORAGE_VERSION_CONFIG_ENTRIES=1
HA_STORAGE_VERSION_DEVICES=3
HA_STORAGE_VERSION_ENTITIES=1
```

No raw hardware ID, pairing ID, setup secret, MQTT password, application key material, HA credential/token or private network locator is frozen in repository evidence.

## 4. Runtime state at G5 collection

```text
MANAGER=running/restart_count=0
HOMEASSISTANT=running/restart_count=0
BROKER=running/restart_count=0

TCP_47110=LISTEN
UDP_47111=LISTEN
TCP_47112=CLOSED
```

Current canonical runtime remained Direct for both registered nodes.

Node B remained on the same boot-session evidence lineage and had advanced to seq 55.

Node A was observed on a new boot session after G4 and was at seq 4 when G5 evidence was collected. The operator subsequently confirmed that this board reboot was intentionally initiated. The registered Node A identity remained unchanged, its current source was Direct, and no Manager/Home Assistant/Broker restart accompanied it. Because G4 had already completed its required 601-second stable two-node run and G5 tests hard upgrade authority plus current business-reference state rather than board uptime continuity, this observation does not invalidate G5. It remains explicitly recorded instead of being silently discarded.

## 5. Earlier gate summary

- G0: fresh read-only T1/authority preflight CLOSED_PASS.
- G1: official Home Assistant local onboarding/UI acceptance CLOSED_PASS.
- G2: existing Node A identity preserved; real SCD30/SHT30/BH1750/RS485 telemetry and HA presentation CLOSED_PASS.
- G3: fresh Node B completed normal product first registration; durable COMMIT, generation-1 credential/application key, exact DynSec plan and automatic HA discovery CLOSED_PASS.
- G4: 601-second two-node ordinary Direct run; both nodes advanced on every one-minute observation interval; services stayed restart_count=0; HA retained exactly one device per node CLOSED_PASS.
- G5: two byte-identical baseline reads exactly equal U0 Baseline A; public-safe business reference frozen CLOSED_PASS.

## 6. Deferred product parameter review

The exact deployed board target currently uses:

```text
N3W_TELEMETRY_INTERVAL=60s
SCD30_UPDATE_INTERVAL=30s
SHT30_UPDATE_INTERVAL=30s
BH1750_UPDATE_INTERVAL=30s
SOIL_READ_INTERVAL=20min
```

The 20-minute RS485 soil cadence remains a separate product-parameter review item before final production release. It is not a failure of this Pre-U1 acceptance.

## 7. Working-context alignment

`N3W_PROJECT_WORKING_CONTEXT.md` declares `STABLE_CONVENTIONS_ONLY=true` and `STAGE_SPECIFIC_VALUES_PROHIBITED=true`. G5 adds no new stable process convention; therefore alignment was reviewed but no new G5-specific values are appended to that file. Current stage authority remains in CURRENT_STATE / CURRENT_STATE_INDEX and the frozen machine reference.

## 8. Next boundary

```text
NEXT_ONE_GATE=N3W_PR774_FINAL_MERGE_READINESS_REVIEW_20261104_01
PR774_MERGE=false
MERGE_AUTHORIZATION_REQUIRED=true
U1_AUTO_RESUME=false
STOP=true
```

The next action is final exact-head PR #774 merge-readiness review and fresh CI confirmation. This closure does not itself authorize merge or U1 live execution.
