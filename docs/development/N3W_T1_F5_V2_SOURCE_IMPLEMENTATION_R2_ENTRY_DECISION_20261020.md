# N3W T1 F5 V2 R2 entry decision — 2026-10-20

## 0. Gate

~~~text
TASK=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R2_ENTRY_DECISION_20261020_01
AUTHORIZATION=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R2_ENTRY_DECISION_20261020_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true

REPOSITORY=chrenguo-stack/HomeAssistant
SOURCE_PR=624
SOURCE_BRANCH=feat/n3w-t1-f5-v2-source-implementation-20261019

R1_REVIEWED_SOURCE_HEAD=169239395088e5d01dc3ccb7b8386a8ae1c2994e
CURRENT_DOCS_HEAD_BEFORE_DECISION=fa4b03ab95c3f532f0d54cf5aa466d348ba53afb
BASE_MAIN=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
BEHIND_MAIN=0

PR_DRAFT=true
PR_MERGEABLE=true
PR_WORKFLOWS=12_OF_12_SUCCESS

R1_CLOSED_PASS=true
READY_FOR_R2_ENTRY_DECISION=true

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

This gate decides whether the closed R1 foundations are stable enough to enter R2. It does not implement R2 source.

## 1. Entry prerequisites

All R2 entry prerequisites are satisfied:

~~~text
R1_CLOSED_PASS=true
R1_FINAL_FOCUSED_REVIEW_BLOCKER_COUNT=0
R1_EXACT_SOURCE_CI=PASS
CURRENT_DOCS_HEAD_CI=12_OF_12_SUCCESS
MAIN_DRIFT=false
REVIEWED_SOURCE_TO_CURRENT_HEAD=DOCS_ONLY
SOURCE_PR_OPEN_DRAFT=true
SOURCE_PR_MERGEABLE=true
R2_SOURCE_ALREADY_STARTED=false
~~~

The branch advance after the reviewed R1 source remains docs-only.

## 2. Fresh exact-source observations relevant to R2

### HOST_BASELINE

Current source still resolves the live APT candidate and installs that candidate version:

~~~text
apt-get update
-> apt-cache policy <package>
-> Candidate
-> apt-get install package=<candidate>
~~~

This is the already-known R2 adaptation target. It is not an entry blocker because the V2 design and work package already freeze the required replacement behavior:

~~~text
APT_CANDIDATE_MUST_EQUAL_RELEASE_VERSION=true
INSTALL_EXACT_PACKAGE_VERSION=true
VERSION_DRIFT_STOPS_BEFORE_INSTALL=true
~~~

### F3

Current F3 still carries the historical fixed `AUTHORIZATION_ID` in the bootstrap payload/authorization model.

R2 must preserve the immutable payload identity while changing normal V2 apply authority to:

~~~text
external V2 run context
+
current STARTED marker binding
+
existing small one-shot F3 action claim
~~~

The dynamic run context must remain outside the immutable payload root. A static historical authorization string must not by itself authorize V2 apply.

### Provision / F4

Current Provision and F4 one-shot/transaction/reboot safety surfaces remain available and are not pre-authorized for modification.

Initial R2 policy remains:

~~~text
PROVISION_SOURCE_CHANGE=false
F4_SOURCE_CHANGE=false
F4_EXISTING_TRANSACTION_GUARDS=KEEP
F4_REPAIR_COMMANDS_IN_NORMAL_V2_PATH=false
~~~

Only a focused integration test proving a real interface gap may promote one of the work-package conditional files into the R2 diff, and that reason must be documented before the change.

### V2 orchestrator

`tools/n3w_t1_production_v2.py` is still absent, as expected before R2.

R2 may add the V2 orchestrator and its focused tests. R3-only acceptance/release integration remains out of scope.

## 3. R2 boundary

R2 is approved only for the frozen work-package purpose:

~~~text
R2=BUSINESS_PRIMITIVE_ADAPTATION_AND_ORCHESTRATION
~~~

### Required R2 source work

~~~text
ADD
tools/n3w_t1_production_v2.py
tests/tools/test_n3w_t1_production_v2.py

ADAPT
tools/n3w_t1_fresh_host_baseline.py
tests/tools/test_n3w_t1_fresh_host_baseline.py

tools/n3w_t1_fresh_product_bootstrap.py
tests/tools/test_n3w_t1_fresh_product_bootstrap.py

tools/n3w_t1_fresh_product_staging_host.py
tests/tools/test_n3w_t1_fresh_product_staging_host.py

.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml
~~~

The dedicated V2 source CI may be extended only as needed to cover the R2 implementation.

### Conditional-only source

~~~text
tools/n3w_t1_device_provisioning_host.py
tests/tools/test_n3w_t1_device_provisioning_host.py

tools/n3w_t1_f4_activation_host.py
tests/tools/test_n3w_t1_f4_activation_host.py

tools/n3w_t1_f4_reboot_authority.py
tests/tools/test_n3w_t1_f4_reboot_authority.py

tools/n3w_t1_f4_reboot_verify.py
tests/tools/test_n3w_t1_f4_reboot_verify.py
~~~

These remain forbidden unless a focused R2 test proves the existing interface cannot satisfy the frozen V2 contract.

## 4. R2 invariants

R2 implementation must preserve:

~~~text
HOST_BASELINE_RELEASE_BOUND_EXACT_PACKAGES=true
APT_VERSION_DRIFT_FAILS_BEFORE_INSTALL=true

F3_DYNAMIC_RUN_CONTEXT_OUTSIDE_IMMUTABLE_PAYLOAD=true
F3_CURRENT_STARTED_MARKER_REQUIRED_BEFORE_FIRST_MUTATION=true
F3_STATIC_HISTORICAL_AUTHORITY_ALONE_FORBIDDEN=true
F3_ONE_SHOT_ACTION_GUARD_PRESERVED=true
F3_RECOVERY_STATE_MACHINE=false

ONE_HUMAN_PRODUCTION_APPROVAL=true
F4_INTERNAL_NO_REPLAY_GUARDS_PRESERVED=true
F4_INTERNAL_ACTION_IDS_DERIVED_FROM_RUN_AND_ACTION=true
V2_NORMAL_PATH_CALLS_REPAIR_COMMANDS=false

MUTATION_PHASE_AUTO_RETRY=false
R1_RESULT_FORENSIC_ORDERING_UNCHANGED=true
R1_QUALIFICATION_CLASSIFICATION_UNCHANGED=true
~~~

## 5. Explicitly deferred to R3

The following do not become R2 implementation authority:

~~~text
tools/n3w_t1_post_reboot_acceptance.py
tests/tools/test_n3w_t1_post_reboot_acceptance.py

tools/n3w_t1_f5_v2_release_builder.py
tests/tools/test_n3w_t1_f5_v2_release_builder.py

.github/workflows/n3w-t1-f5-v2-exact-production-release-ci.yml

isolated Linux end-to-end closure
final exact production release build
real T1 execution
~~~

R2 may define a clean orchestrator interface seam for later R3 acceptance integration, but it must not claim R3 acceptance complete.

## 6. Entry decision

~~~text
R2_ENTRY_PREREQUISITES=PASS
R2_ENTRY_BLOCKER_COUNT=0
R2_ENTRY_GRANTED=true
R2_STARTED=false
~~~

Known HOST_BASELINE and F3 changes are the intended R2 work, not blockers to entering R2.

No T1, board, production service, merge, or real deployment action is authorized by this decision.

## 7. Next one gate

~~~text
NEXT_ONE_GATE=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R2_BUSINESS_PRIMITIVE_ADAPTATION_AND_ORCHESTRATION_20261020_01
AUTO_EXECUTE_NEXT_GATE=false
NEW_AUTHORIZATION_REQUIRED=true
~~~

### PASS target for the next gate

The next source gate may produce an R2 implementation candidate only if:

~~~text
HOST_BASELINE_EXACT_RELEASE_BINDING=PASS
F3_EXTERNAL_RUN_CONTEXT_AND_STARTED_MARKER_BINDING=PASS
F3_LEGACY_STATIC_AUTHORITY_NOT_SUFFICIENT=PASS
V2_ORCHESTRATOR_R2_SCOPE=PASS
FOCUSED_R2_TESTS=PASS
R1_REGRESSIONS=PASS
R3_SCOPE_NOT_ENTERED=true
~~~

It must then stop for exact-head CI / focused source review according to the work package.

## 8. Hard stop

~~~text
R2_ENTRY_DECISION=CLOSED_PASS
R2_ENTRY_GRANTED=true
R2_STARTED=false

T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false
MERGE=false

STOP=true
~~~

## 9. KNOWN_FAILURES classification

~~~text
KNOWN_FAILURES_UPDATE_REQUIRED=false
NEW_KF_REQUIRED=false
~~~

No new runtime or field failure was established by this read-only/source-entry decision.
