# N3-W T1 Home Assistant USB mandatory OTA V1.2 route / engineering-bloat review
# 2026-11-14

STATUS=REVIEW_CLOSED
ARCHITECTURE_ROUTE_DRIFT=NO
PRODUCT_STATE_MACHINE_DRIFT=NO
SAFETY_MODEL_DRIFT=NO
ENGINEERING_BLOAT=YES_MODERATE_HIGH
R29_EXECUTION_BLOCKED_BY_REVIEW=false
POST_R29_CONVERGENCE_REQUIRED=true

## 1. Review authority

Primary architecture authority:

- `docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_REMOVABLE_MEDIA_CONTENT_AUTHORITY_ARCHITECTURE_V1.2_20261112.md`
- frozen V1.2 semantics:
  - internal transaction is primary authority;
  - exact target / predecessor / HA-backup content is recovery authority;
  - USB physical device, /dev node, filesystem UUID and public fingerprint are not cross-session continuity authority;
  - U6 prepares exact predecessor recovery;
  - U7 quiesces HA/Manager and creates/verifies protected HA backup;
  - U8 persists complete recovery admission;
  - U9 is the one-shot destructive authorization boundary.

Implementation/design authorities reviewed:

- `docs/development/N3W_T1_HOMEASSISTANT_REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_DESIGN_20261112.md`
- `docs/development/N3W_T1_HOMEASSISTANT_REMOVABLE_MEDIA_CONTENT_AUTHORITY_V1_2_SOURCE_REPAIR_CLOSURE_20261112.md`
- `docs/development/N3W_T1_U7_HA_QUIESCE_DATA_BACKUP_SOURCE_DESIGN_AND_REVIEW_20261114.md`
- `docs/development/N3W_T1_U7_R28_IMPORT_FAILURE_TO_R29_SOURCE_REPAIR_20261114.md`

Current exact R29 source authority:
`acad3133d224ac9ae17c2ce45311c22db1e5ebe7`

## 2. Route-alignment finding

The current durable live state is still:

`U6_PREDECESSOR_RECOVERY_PREPARING`

R26 physically proved the V1.2 U6 requirement:

- exact predecessor archive identity;
- exact predecessor size / SHA-256 / portable identity;
- durable U6 transaction;
- no U7+ transition.

R29 is not a new product lifecycle state. It is a source-activation gate that prepares the already-reviewed U7 implementation while deliberately leaving the durable transaction at U6.

R29 success is explicitly bounded to:

- activate the six exact U7 source modules;
- preserve runtime continuity;
- no service stop/restart;
- no transaction mutation;
- no USB mutation;
- no U7 transition;
- no HA quiesce;
- no HA backup creation;
- no U8+.

After R29, the next lifecycle action remains exactly the V1.2 U6 -> U7 HA-quiesce/data-backup path.

Therefore:

```text
ARCHITECTURE_ROUTE_DRIFT=NO
PRODUCT_STATE_MACHINE_DRIFT=NO
CONTENT_AUTHORITY_MODEL_PRESERVED=true
U9_DESTRUCTIVE_BOUNDARY_PRESERVED=true
```

## 3. Engineering-bloat finding

The implementation / verification layer has expanded materially beyond the compact A-J implementation sequence described by the V1.2 source design.

Current PR #807 at review time:

```text
COMMITS=389
CHANGED_FILES=139
ADDITIONS=46985
DELETIONS=760
```

The expansion is concentrated in:

- many generation-specific Rxx execution packages;
- separate manifest + executor + focused-test sets for successive live/source gates;
- repeated grant-only / exact-binding / read-only-preflight wrappers;
- cumulative current-state and handoff history;
- duplicated embedded remote-execution scaffolding across generations.

This complexity is no longer theoretical. It has already produced self-inflicted execution defects:

- R28: incomplete transitive import-closure contract;
- R29 Attempt01: R28 helper indirection did not export the helper interfaces R29 assumed;
- R29 Attempt02: embedded remote script used `base64` without importing it and decoded outside its JSON error boundary.

Attempt01/02 did not reveal V1.2 product-state defects. They were executor/scaffolding defects.

Therefore:

```text
ENGINEERING_BLOAT=YES_MODERATE_HIGH
BLOAT_HAS_CREATED_NEW_FAILURE_SURFACE=true
PRODUCT_ARCHITECTURE_REDESIGN_REQUIRED=false
CURRENT_R29_SOURCE_REDESIGN_REQUIRED=false
```

## 4. Necessary complexity vs avoidable complexity

Necessary safety complexity that should remain:

- exact source/content binding;
- one-shot claim / consumed-no-replay semantics;
- preclaim read-only validation;
- bounded rollback after source mutation;
- exact predecessor / target / backup authority;
- post-claim uncertainty reconciliation;
- explicit U9 destructive boundary;
- private target/SSH authority kept out of public GitHub.

Complexity that should be converged after the current R29/U7 gate is stable:

- generation-specific copies of transport/evidence/JSON-envelope helpers;
- nested executor-as-helper imports;
- repeated remote-script boilerplate;
- duplicated one-shot claim and rollback plumbing;
- accumulated stage history in active-state documents;
- long-lived oversized PR scope.

## 5. Route correction / convergence rule

Do **not** perform a framework refactor immediately before the already-reviewed R29 live activation. That would invalidate the exact source/preflight evidence and create unnecessary risk.

Instead:

1. execute the already-bounded R29 source-activation gate after its exact grant-only successor and fresh CI;
2. continue only to the already-designed U7 lifecycle gate;
3. do not invent a new product phase or redesign V1.2;
4. after R29/U7 source/runtime closure, schedule a dedicated repository/executor convergence slice;
5. converge reusable transport/evidence/remote-JSON/one-shot-claim primitives behind one tested authority rather than chaining historical executors;
6. reduce active current-state documents to current delta + links, leaving detailed history in immutable closure/handoff records;
7. decide PR #807 convergence/merge strategy separately; no merge is authorized by this review.

## 6. R29 disposition

R29 Attempt03 real-T1 read-only preflight is CLOSED_PASS:

- source_activation_eligible=true;
- live_execution_authorized=false at the reviewed source head;
- authorization_claimed=false;
- authorization_consumed=false;
- remote_staging=false;
- host/service/transaction/USB/U7/U8+ mutation=false;
- exact U6 transaction/R26/content/runtime preconditions PASS.

The architecture review finds no V1.2 route blocker to the next R29 one-shot source activation.

User authorization for the next chat is separately recorded in the handoff/current-state alignment. The current source manifest remains ungranted until a grant-only successor is materialized and receives fresh CI/exact review.

## 7. Final verdict

```text
V1_2_ROUTE_ALIGNED=true
CURRENT_LIVE_PHASE_ALIGNED=true
R29_IS_IMPLEMENTATION_GATE_NOT_PRODUCT_PHASE=true
PRODUCT_ROUTE_CHANGE_REQUIRED=false
ENGINEERING_CONVERGENCE_REQUIRED=true
CONVERGENCE_BEFORE_R29_REQUIRED=false
R29_MAY_PROCEED_AFTER_EXACT_GRANT_AND_FRESH_CI=true
```
