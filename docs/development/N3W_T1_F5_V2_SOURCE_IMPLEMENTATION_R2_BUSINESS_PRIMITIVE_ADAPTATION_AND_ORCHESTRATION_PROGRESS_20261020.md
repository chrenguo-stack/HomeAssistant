# N3W T1 F5 V2 R2 business primitive adaptation + orchestration progress — 2026-10-20

## 0. Gate state

~~~text
TASK=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R2_BUSINESS_PRIMITIVE_ADAPTATION_AND_ORCHESTRATION_20261020_01
AUTHORIZATION=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R2_BUSINESS_PRIMITIVE_ADAPTATION_AND_ORCHESTRATION_20261020_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true

R2_ENTRY_DECISION_HEAD=afa681b04d100e6ec49f2ec50ee0295626dff5fa
R2_EXACT_SOURCE_HEAD=2defed8b39bcbdf03d7e90c266be6862e12aa27a
BASE_MAIN=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
BEHIND_MAIN=0

R2_SOURCE_IMPLEMENTATION=IMPLEMENTED_CANDIDATE
R2_DEDICATED_SOURCE_CI=PASS
R1_REGRESSION_JOB=PASS
R2_FOCUSED_TESTS=PASS:86
R2_BOUNDARY_CHECK=PASS

R2_SOURCE_BLOCKER_COUNT=0
REPOSITORY_INTEGRATION_BLOCKER_COUNT=1
DOWNSTREAM_F2_EXACT_BLOB_BINDING=STALE_OUTSIDE_CURRENT_FILE_BOUNDARY

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false

GATE_RESULT=STOP_SCOPE_EXPANSION_REQUIRED
STOP=true
~~~

The R2 source candidate is implemented and its dedicated R1/R2 source CI is green. Repository-wide closure is not claimed because the historical F2 read-only preflight execution package still pins the pre-R2 blobs of source files that R2 is explicitly required to adapt.

## 1. R2 source implemented

### HOST_BASELINE

`tools/n3w_t1_fresh_host_baseline.py` now requires exact approved package versions for:

~~~text
docker.io
docker-compose-v2
~~~

Install behavior is now:

~~~text
apt-get update
-> read APT candidate
-> candidate must equal approved release version
-> otherwise STOP before apt-get install
-> install exact package=approved_version
-> post-install package versions must still match
~~~

An already-ready host with different installed package versions also fails closed instead of being silently accepted.

The original executable file mode was preserved after CI caught an accidental mode regression.

### F3 V2 authority boundary

F3 now requires all of the following before the V2 apply path may claim its one-shot action or perform the first F3 mutation:

~~~text
immutable payload identity
+
external V2 run context
+
current STARTED production marker binding
~~~

The dynamic run context:

- is an exact-schema file;
- binds run/release/source/target/marker/action;
- must be outside the immutable payload root;
- is transferred separately from the payload;
- is mode-restricted on target;
- is verified against the current STARTED marker and marker SHA;
- is included in the durable one-shot action-claim binding.

The historical fixed F3 authorization string remains only as an existing action label/ledger namespace. It is no longer sufficient by itself to authorize V2 apply.

Successful staging cleanup now removes both the payload staging directory and the separately transferred V2 run-context file.

### V2 R2 orchestrator

Added:

~~~text
tools/n3w_t1_production_v2.py
tests/tools/test_n3w_t1_production_v2.py
~~~

The R2 orchestration boundary now covers:

~~~text
release validation
-> SSH epoch #1
-> host-key binding
-> fresh qualification
-> plan
-> one top-level production approval
-> marker STARTED
-> exact HOST_BASELINE
-> F3 V2 deploy
-> Provision
-> F4 grouped normal actions with deterministic internal one-shot IDs
-> controlled reboot
-> pre-reboot SSH epoch close
-> REBOOT_PENDING
~~~

R3 post-reboot acceptance remains explicitly incomplete.

Normal R2 mutation failure after STARTED is fail-closed:

~~~text
failure
-> freeze original failure
-> complete read-only forensics
-> establish failure-session close terminal state
-> record reflash disposition
~~~

No reflash disposition is allowed if forensic completion or session-close proof fails.

No automatic mutation retry or normal-path repair command was added.

## 2. Files changed in the R2 source candidate

~~~text
.github/workflows/n3w-t1-f5-v2-source-ci.yml

tools/n3w_t1_fresh_host_baseline.py
tests/tools/test_n3w_t1_fresh_host_baseline.py

tools/n3w_t1_fresh_product_bootstrap.py
tests/tools/test_n3w_t1_fresh_product_bootstrap.py

tools/n3w_t1_fresh_product_staging_host.py
tests/tools/test_n3w_t1_fresh_product_staging_host.py

tools/n3w_t1_production_v2.py
tests/tools/test_n3w_t1_production_v2.py
~~~

No Provision or F4 conditional-only source file was modified.

No R3 post-reboot acceptance or release-builder source was added.

## 3. Exact source bindings

~~~text
HOST_BASELINE_BLOB=ae7d114bd54825114f462b4f7034ed6009f80f6f
F3_BOOTSTRAP_BLOB=6a29899b834c7593f33b673390ec47c5e8c3edff
F3_STAGING_HOST_BLOB=1196f185069db3000d4e96059be8908ba29e23f0
R2_ORCHESTRATOR_BLOB=01ab670c0956353ccd2e428a98e84a7b2fae9003
~~~

## 4. Dedicated source CI

~~~text
N3W_T1_F5_V2_SOURCE_CI_RUN=39361779995
R1_FOUNDATIONS=SUCCESS
R2_SOURCE=SUCCESS
R2_FOCUSED_TESTS=86_PASS
R2_BOUNDARY=PASS

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
~~~

The separate `N3W T1 fresh install host-only CI` is also SUCCESS at this exact source head.

## 5. Downstream CI blocker

The F2 read-only preflight source CI is FAIL at:

~~~text
RUN=39361779966
FAILURE=source_blob_mismatch:tools/n3w_t1_fresh_product_staging_host.py
~~~

This is not evidence that the new R2 staging behavior failed its tests. The F2 execution package contains an exact `EXPECTED_BLOBS` map that still binds:

~~~text
STAGING_RELATIVE=e924f02265564666efab89986479d1b5af40123d
BASELINE_RELATIVE=d6f72a7a595f7ba5b8d9d2e5dc06188dbfa973b2
~~~

R2 intentionally changed both source files. Their current blobs are:

~~~text
STAGING_RELATIVE=1196f185069db3000d4e96059be8908ba29e23f0
BASELINE_RELATIVE=ae7d114bd54825114f462b4f7034ed6009f80f6f
~~~

Therefore the F2 failure is classified as a downstream exact-source binding alignment requirement.

The current R2 work-package file boundary does not authorize mutation of:

~~~text
tools/execution_packages/n3w/f2/t1_fresh_readonly_preflight/executor.py
tests/execution_packages/n3w/f2/t1_fresh_readonly_preflight/test_executor.py
~~~

Changing that authority in this gate would expand the frozen source scope, so it was not done automatically.

## 6. Other CI

At this stop point all completed non-F2 workflows are green. Two large source-dependent payload workflows were still running at the exact source head:

~~~text
N3W_T1_PRODUCTION_STACK_STAGING_PAYLOAD_CI_RUN=39361780128
N3W_T1_FRESH_BOOTSTRAP_DEPLOYABLE_PAYLOAD_CI_RUN=39361779989
~~~

Their final result must be read before defining the exact downstream-alignment mutation set. No repeated polling is required.

## 7. Focused source review

The same-gate source review found and repaired two narrow R2 issues before this stop:

1. STARTED mutation failures originally only raised from the orchestrator; the R2 source now explicitly enforces forensic completion and session close before reflash disposition.
2. The external V2 run-context file was preserved after successful F3 staging cleanup; success cleanup now removes it with the payload staging directory.

After those repairs:

~~~text
HOST_BASELINE_EXACT_RELEASE_BINDING=PASS
F3_EXTERNAL_RUN_CONTEXT_AND_STARTED_MARKER_BINDING=PASS
F3_LEGACY_STATIC_AUTHORITY_NOT_SUFFICIENT=PASS
F3_EXTERNAL_CONTEXT_SUCCESS_CLEANUP=PASS
V2_ORCHESTRATOR_R2_SCOPE=PASS
STARTED_FAILURE_FINALIZATION_ORDERING=PASS
FOCUSED_R2_TESTS=PASS
R1_REGRESSIONS=PASS
R3_SCOPE_NOT_ENTERED=true
R2_SOURCE_BLOCKER_COUNT=0
~~~

## 8. Stop and next decision

~~~text
R2_SOURCE_CANDIDATE_READY=true
R2_REPOSITORY_CLOSURE_READY=false
SCOPE_EXPANSION_REQUIRED=true

NEXT_ONE_GATE=
N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R2_DEPENDENT_CI_ALIGNMENT_DECISION_20261020_01

AUTO_EXECUTE_NEXT_GATE=false
~~~

The next gate is read-only first: read the two pending payload workflow results, enumerate every stale exact-source binding caused by the approved R2 source changes, and decide the smallest explicit alignment scope. It must not enter R3, access T1/boards, or merge.
