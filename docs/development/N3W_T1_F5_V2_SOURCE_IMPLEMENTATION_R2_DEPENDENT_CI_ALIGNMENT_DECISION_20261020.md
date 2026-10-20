# N3W T1 F5 V2 R2 dependent CI alignment decision — 2026-10-20

## 0. Gate

~~~text
TASK=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R2_DEPENDENT_CI_ALIGNMENT_DECISION_20261020_01
AUTHORIZATION=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R2_DEPENDENT_CI_ALIGNMENT_DECISION_20261020_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true

SOURCE_PR=624
SOURCE_BRANCH=feat/n3w-t1-f5-v2-source-implementation-20261019
R2_EXACT_SOURCE_HEAD=2defed8b39bcbdf03d7e90c266be6862e12aa27a
PRE_DECISION_DOCS_HEAD=c6b35de4594276655216f5889fdd0eba43408a0b
BASE_MAIN=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
BEHIND_MAIN=0

R2_SOURCE_CI=PASS
R2_PAYLOAD_CI=PASS
F2_SOURCE_CI=FAIL_STALE_EXACT_BINDING

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

This gate is a source-alignment decision only. It does not mutate the F2 execution package.

## 1. Final dependent CI state

At the current docs head all 17 triggered workflows are complete.

~~~text
SUCCESS=16
FAILURE=1
PENDING=0
~~~

The only failure is:

~~~text
N3W_T1_F2_READONLY_PREFLIGHT_SOURCE_CI_RUN=39362039956
RESULT=FAIL
FAILED_TEST=test_source_authority_binds_current_head_and_main_ancestor
ERROR=source_blob_mismatch:tools/n3w_t1_fresh_product_staging_host.py
TEST_SUMMARY=70_PASS_1_FAIL
~~~

The two payload workflows that were still pending at the previous stop are now both PASS:

~~~text
N3W_T1_PRODUCTION_STACK_STAGING_PAYLOAD_CI_RUN=39362040025
RESULT=PASS

N3W_T1_FRESH_BOOTSTRAP_DEPLOYABLE_PAYLOAD_CI_RUN=39362040045
RESULT=PASS
~~~

Therefore there is no evidence of a second runtime/payload integration blocker in the current source candidate.

## 2. Exact stale-binding inventory

The F2 execution package currently contains two separate exact-source binding representations.

### 2.1 Executor enforcement

File:

~~~text
tools/execution_packages/n3w/f2/t1_fresh_readonly_preflight/executor.py
~~~

Current enforced values are:

~~~text
IDENTITY_RELATIVE=26a2f47c9c83fef5637f551ea75ba6b5d5ba3866
INVENTORY_RELATIVE=073bbc936cef3648411a95023a59d6b7e04d4a32
STAGING_RELATIVE=e924f02265564666efab89986479d1b5af40123d
BASELINE_RELATIVE=d6f72a7a595f7ba5b8d9d2e5dc06188dbfa973b2
~~~

Fresh exact source blobs are:

~~~text
IDENTITY_CURRENT=26a2f47c9c83fef5637f551ea75ba6b5d5ba3866
INVENTORY_CURRENT=073bbc936cef3648411a95023a59d6b7e04d4a32
STAGING_CURRENT=1196f185069db3000d4e96059be8908ba29e23f0
BASELINE_CURRENT=ae7d114bd54825114f462b4f7034ed6009f80f6f
~~~

Identity and inventory remain exact. Only staging and baseline require alignment.

### 2.2 Execution-package manifest

File:

~~~text
tools/execution_packages/n3w/f2/t1_fresh_readonly_preflight/manifest.json
~~~

The manifest currently declares:

~~~text
fresh_product_staging_host_blob_sha=7e1a82a8b67375a9c88558b6f3c4e0cc45b46f2e
fresh_host_baseline_blob_sha=d6f72a7a595f7ba5b8d9d2e5dc06188dbfa973b2
~~~

Both are stale against the current source candidate.

The staging hash in the manifest also differs from the executor's pre-R2 staging hash. This is a pre-existing package-internal drift that was not enforced by the current F2 CI. It should be reconciled in the same bounded alignment repair rather than preserved.

## 3. Search result

Repository search for the stale executable binding hashes found no second active execution authority requiring R2 alignment.

Operational stale binding is therefore bounded to the F2 read-only execution package.

Historical design/closure/handoff documents contain old source/blob identities as historical evidence. They are not executable authority and must not be rewritten merely to make old records look current.

## 4. Semantic compatibility decision

The F2 gate remains read-only and does not receive R2 mutation authority.

The current F2 test run reached:

~~~text
70_PASS
1_FAIL_EXACT_SOURCE_BINDING_ONLY
~~~

The R2 source candidate also has:

~~~text
N3W_T1_F5_V2_SOURCE_CI=PASS
N3W_T1_FRESH_INSTALL_HOST_ONLY_CI=PASS
N3W_T1_PRODUCTION_STACK_STAGING_PAYLOAD_CI=PASS
N3W_T1_FRESH_BOOTSTRAP_DEPLOYABLE_PAYLOAD_CI=PASS
~~~

No observed failure requires changing F2 read-only acceptance semantics, SSH behavior, evidence behavior, or live target behavior.

The alignment repair must therefore be metadata/authority binding only. It must not alter F2's read-only product semantics.

## 5. Minimum approved repair scope

The next repair gate is approved to modify only:

~~~text
tools/execution_packages/n3w/f2/t1_fresh_readonly_preflight/executor.py
tools/execution_packages/n3w/f2/t1_fresh_readonly_preflight/manifest.json
tests/execution_packages/n3w/f2/t1_fresh_readonly_preflight/test_executor.py
~~~

Required changes:

~~~text
1. update STAGING_RELATIVE expected blob to 1196f185069db3000d4e96059be8908ba29e23f0
2. update BASELINE_RELATIVE expected blob to ae7d114bd54825114f462b4f7034ed6009f80f6f
3. update manifest staging/baseline source_binding fields to the same exact blobs
4. add a focused regression proving manifest source_binding and executor EXPECTED_BLOBS agree with the current git blobs
~~~

The workflow file does not require modification because the current F2 source workflow already triggers on the execution-package directory and both adapted source files, and already executes the relevant test module.

## 6. Forbidden expansion

The alignment repair must not change:

~~~text
F2 acceptance rules
F2 SSH transport semantics
F2 live evidence semantics
F3/F4 business logic
R2 source candidate behavior
R3 source
T1 state
board state
production services
merge state
~~~

It must also not rewrite historical docs merely because they record older exact source identities.

## 7. Decision

~~~text
DEPENDENT_ALIGNMENT_INVENTORY_COMPLETE=true
DEPENDENT_ALIGNMENT_SCOPE_COUNT=3
EXECUTOR_BINDING_UPDATE_REQUIRED=true
MANIFEST_BINDING_UPDATE_REQUIRED=true
CONSISTENCY_REGRESSION_REQUIRED=true

R2_SOURCE_REPAIR_REQUIRED=false
F2_BEHAVIOR_REPAIR_REQUIRED=false
R3_ENTRY=false

R2_DEPENDENT_CI_ALIGNMENT_DECISION=CLOSED_PASS
NEXT_ONE_GATE=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R2_DEPENDENT_CI_ALIGNMENT_REPAIR_20261020_01
AUTO_EXECUTE_NEXT_GATE=false
NEW_AUTHORIZATION_REQUIRED=true

STOP=true
~~~

## 8. Hard safety boundary

~~~text
T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false
MERGE=false
~~~
