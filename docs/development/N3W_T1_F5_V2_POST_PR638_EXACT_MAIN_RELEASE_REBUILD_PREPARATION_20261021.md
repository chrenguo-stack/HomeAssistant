# N3W T1 F5 V2 post-PR638 exact-main release rebuild preparation — 2026-10-21

## 0. Gate

~~~text
TASK=N3W_T1_F5_V2_POST_PR638_EXACT_MAIN_RELEASE_REBUILD_PREPARATION_20261021_01
RESULT=PREPARATION_READY

PREPARATION_BASE_MAIN=998d528f3aafcbef64ad24fe7cff6c4c9c7001f5
PREPARATION_BASE_TREE=80bc51435e48af19c022fd26282426301cf427fd

PR637_MERGED=true
PR638_ALIGNMENT_MERGED=true

REBUILD_CHAIN_SOURCE_REVIEW=PASS
SOURCE_REPAIR_REQUIRED=false
NEW_BLOCKER_COUNT=0

REPOSITORY_MUTATION=DOCS_ONLY
WORKFLOW_DISPATCH=false
GITHUB_ARTIFACT_PRODUCTION=false
T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
REFLASH=false
PRODUCTION_EXECUTION=false
MERGE=false
~~~

## 1. Purpose

PR #637 merged the post-reboot product-readiness barrier and A7 error-code sanitizer.
PR #638 then merged the docs-only post-merge alignment. Any exact production release
created before the current source line is historical evidence only.

This preparation independently re-checks the current producer workflows and release
builders. It does not dispatch any workflow and does not create an artifact.

The preparation base is `998d528f3aafcbef64ad24fe7cff6c4c9c7001f5`. Because this preparation itself is a docs-only
branch, merging the preparation PR will advance `main` again. Therefore the artifact
execution gate must **fresh rebind the post-preparation merged main** and use that SHA/tree
as the one exact production source for A-D below.

~~~text
PREPARATION_BASE_IS_ARTIFACT_AUTHORITY=false
EXECUTION_EXACT_MAIN=FRESH_POST_PREPARATION_MERGE_MAIN
EXECUTION_EXACT_TREE=FRESH_POST_PREPARATION_MERGE_TREE
DISPATCH_FROM_PREPARATION_BRANCH=false
MIX_SOURCE_HEADS=false
~~~

## 2. Independent producer/source review

The current source still provides the complete production chain and remains fail-closed.

### A. F3 deployable payload

Workflow:

~~~text
.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml
name=N3W T1 fresh bootstrap deployable payload CI
event=workflow_dispatch
~~~

The workflow checks out its exact `SOURCE_HEAD`, builds the ARM64 Manager and pinned
external ARM64 images, uploads:

~~~text
n3w-t1-fresh-bootstrap-deployable-<EXECUTION_MAIN>
~~~

and re-downloads the uploaded artifact to verify the exact outer file set and sidecars.
Retention is 30 days.

### B. F4 control and reboot-control

Workflow:

~~~text
.github/workflows/n3w-t1-f4-exact-control-package.yml
name=N3W T1 F4 exact control package
event=workflow_dispatch
~~~

The same workflow run produces both:

~~~text
n3w-t1-f4-control-package-<EXECUTION_MAIN>
n3w-t1-f4-reboot-successor-control-<EXECUTION_MAIN>
~~~

The package reports/manifests bind to the run source head. The reboot-successor report
also asserts:

~~~text
live_runtime_mutation=false
reboot_executed=false
board_access=false
~~~

Retention is 14 days, so downstream C/D should follow without unnecessary delay.

### C. Exact V2 release inputs

Workflow:

~~~text
.github/workflows/n3w-t1-f5-v2-release-inputs-ci.yml
name=N3W T1 F5 V2 exact release inputs CI
event=workflow_dispatch

inputs:
  f3_run_id=<successful A run>
  f4_run_id=<successful B run>
~~~

Before consuming A/B, the workflow requires both upstream runs to be from the exact same
current `main` SHA, branch `main`, completed/successful, and from the exact producer
workflow paths. It requires exactly one unexpired F3 artifact, one F4 control artifact,
and one reboot-control artifact with names bound to the current `GITHUB_SHA`.

The builder runs with `--production-authority`, which requires:

~~~text
HEAD=source_head
HEAD^{tree}=source_tree
origin/main=source_head
~~~

The release-input artifact contains exactly six required production classes:

~~~text
f3_payload
f3_image
f4_control
reboot_control
v2_mac_tools
transport_contract
~~~

The current `v2_mac_tools` materialization includes the repaired production stack,
including:

~~~text
tools/n3w_t1_f4_reboot_verify.py
tools/n3w_t1_post_reboot_acceptance.py
tools/n3w_t1_production_v2.py
tools/n3w_t1_production_v2_contract.py
tools/n3w_t1_production_v2_executor.py
tools/n3w_t1_f5_v2_release_builder.py
~~~

The workflow uploads and re-downloads the release-input artifact and verifies its
post-upload source binding.

Required output:

~~~text
n3w-t1-f5-v2-release-inputs-<EXECUTION_MAIN>
~~~

### D. Final exact production release

Workflow:

~~~text
.github/workflows/n3w-t1-f5-v2-exact-production-release-ci.yml
name=N3W T1 F5 V2 exact production release CI
event=workflow_dispatch

inputs:
  inputs_run_id=<successful C run>
  inputs_artifact_name=n3w-t1-f5-v2-release-inputs-<EXECUTION_MAIN>
~~~

It checks out `main`, verifies `HEAD == GITHUB_SHA == origin/main`, requires the
release-input run to be the exact release-input workflow on the same main SHA, requires
one unexpired exact artifact, and builds with `--production-authority`.

Required output:

~~~text
n3w-t1-f5-v2-exact-production-release-<EXECUTION_MAIN>
~~~

The artifact contains:

~~~text
n3w-t1-f5-v2-release.tar.gz
n3w-t1-f5-v2-release.tar.gz.sha256
~~~

Retention is 30 days.

## 3. E — local exact-release validation

Final release production is not sufficient by itself. Before any T1 reflash or
production authorization, the downloaded GitHub artifact must pass the current
`verify-bundle` path in `tools/n3w_t1_f5_v2_release_builder.py`.

The validator independently requires:

~~~text
repository HEAD/source tree/current origin-main exact binding
workflow path exact
run_id/run_attempt exact
run head_sha=current execution main
run head_branch=main
event=workflow_dispatch
run status/conclusion=completed/success
artifact_id/name exact
artifact not expired
GitHub artifact digest == downloaded ZIP SHA256
final artifact outer file set exact
release tar SHA sidecar PASS
safe extraction PASS
release directory verification PASS
release.source_head=execution main
release.source_tree=execution tree
required six-artifact set exact
nested F4 control manifest/source binding PASS
nested reboot-control manifest/source binding PASS
v2_mac_tools exact member set and exact bytes vs repository PASS
transport contract source binding PASS
secret_values_included=false
t1_access=false
board_access=false
~~~

The local gate must freeze at least:

~~~text
FINAL_WORKFLOW_RUN_ID
FINAL_WORKFLOW_RUN_ATTEMPT
FINAL_ARTIFACT_ID
FINAL_ARTIFACT_NAME
FINAL_ARTIFACT_ZIP_SHA256
RELEASE_ID
RELEASE_SHA256
SOURCE_HEAD
SOURCE_TREE
LOCAL_BINDING_JSON
~~~

This is the gate that converts the downloaded GitHub artifact into locally verified
production authority. It remains separate from artifact production.

## 4. Execution ordering and main-drift rule

A and B may be dispatched in parallel only after the execution gate fresh-rebinds the
post-preparation merged main. C waits for A+B. D waits for C. E waits for D.

~~~text
A_F3
   \
    -> C_RELEASE_INPUTS -> D_FINAL_RELEASE -> E_LOCAL_VALIDATION
   /
B_F4_REBOOT
~~~

At every stage:

~~~text
if current main != EXECUTION_MAIN:
    STOP
    classify incomplete-chain artifacts as historical/non-authoritative
    fresh rebind
    rebuild the affected exact chain
~~~

Do not reuse an artifact across different source-head values even when the product bytes
appear unchanged.

## 5. Physical/live boundary after E

Nothing in this preparation authorizes T1 access. The failed target remains
reflash-required and the previous failed run remains terminal/no-replay.

Only after E passes may a later separately authorized route proceed:

~~~text
LOCAL_EXACT_RELEASE_VALIDATION=PASS
-> FAILED_T1_REFLASH
-> STANDARD_FRESH_ARMBIAN_READONLY_QUALIFICATION
-> NEW_PRODUCTION_RUN_ID
-> NEW_EXPLICIT_PRODUCTION_AUTHORIZATION
-> REAL_T1_PRODUCTION
-> POST_REBOOT_READINESS
-> STRICT_POST_REBOOT_ACCEPTANCE
-> FIVE_EXTERNAL_PROBES
-> EXISTING_90_SECOND_STABILITY_OBSERVATION
~~~

Current known-failure boundary:

~~~text
KF_122=OPEN
KF_124=SOURCE_REPAIR_MERGED_LIVE_REVALIDATION_PENDING
KF_125=SOURCE_REPAIR_MERGED_LIVE_REVALIDATION_PENDING
~~~

## 6. Current stop point

~~~text
PREPARATION_RESULT=CLOSED_PASS
SOURCE_REPAIR_REQUIRED=false
WORKFLOW_DISPATCH=false

NEXT_ONE_GATE=N3W_T1_F5_V2_POST_PR638_EXACT_MAIN_RELEASE_REBUILD_PREPARATION_MERGE_DECISION_20261021_01
AUTO_EXECUTE_NEXT_GATE=false

AFTER_PREPARATION_MERGE_NEXT_TECHNICAL_GATE=
N3W_T1_F5_V2_EXACT_MAIN_F3_F4_ARTIFACT_REBUILD_EXECUTION_20261021_01
~~~

The next merge is docs-only. After it, the artifact execution gate must fresh-rebind
the new merged main and may then dispatch A/B if that exact main has not drifted.
