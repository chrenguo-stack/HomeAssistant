# N3W T1 F5 V2 exact-main release rebuild preparation — 2026-10-21

## 0. Gate

~~~text
TASK=N3W_T1_F5_V2_EXACT_MAIN_RELEASE_REBUILD_PREPARATION_20261021_01
RESULT=PREPARATION_READY

EXACT_MAIN=90775b804807b4ff69ca7cea71a220a2e3a5a416
EXACT_MAIN_TREE=9919c90a854265cf9fedc795affc8a0a53a9e522

PR628_MERGED=true
PR629_ALIGNMENT_MERGED=true
PR628_SOURCE_BLOCKER=CLOSED
KF_122=OPEN

REPOSITORY_MUTATION=DOCS_ONLY
WORKFLOW_DISPATCH=false
GITHUB_ARTIFACT_PRODUCTION=false
T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false

REBUILD_CHAIN_SOURCE_REVIEW=PASS
SOURCE_REPAIR_REQUIRED=false
~~~

## 1. Purpose

The merged PR #628 changed the production executor, post-reboot acceptance and evidence classification. A release built before that merge cannot authorize production execution of the repaired source.

This gate does not build artifacts. It freezes the exact-main rebuild chain and the checks that must hold before each producer is dispatched.

## 2. Exact source authority

~~~text
SOURCE_HEAD=90775b804807b4ff69ca7cea71a220a2e3a5a416
SOURCE_TREE=9919c90a854265cf9fedc795affc8a0a53a9e522
SOURCE_BRANCH=main
~~~

Every artifact in the new chain must bind to this same source head and tree.

If `main` changes before the chain is complete, the chain is no longer production-authoritative. Do not mix artifacts from two main SHAs. Rebind to the new main and rebuild the affected chain from the beginning.

## 3. Producer chain

The exact rebuild order is:

~~~text
A. exact-main F3 deployable payload
B. exact-main F4 control + reboot-control packages
C. exact-main V2 release-inputs artifact
D. exact-main V2 production release
E. local exact-release validation
F. Standard Fresh Armbian read-only qualification
G. separate real-T1 production authorization decision
~~~

A and B may run in parallel because neither consumes the other. C must wait for successful A and B. D must wait for successful C.

No T1 operation belongs to A-D.

## 4. A — exact-main F3 producer

Workflow:

~~~text
.github/workflows/n3w-t1-fresh-bootstrap-deployable-payload-ci.yml
workflow name=N3W T1 fresh bootstrap deployable payload CI
event=workflow_dispatch
~~~

Expected binding:

~~~text
run.head_branch=main
run.head_sha=90775b804807b4ff69ca7cea71a220a2e3a5a416
run.status=completed
run.conclusion=success
~~~

Required artifact:

~~~text
n3w-t1-fresh-bootstrap-deployable-90775b804807b4ff69ca7cea71a220a2e3a5a416
~~~

The artifact must contain exactly the F3 outer set expected by `n3w_t1_f5_v2_release_inputs_builder.py`, including runtime payload, three ARM64 image tar files, capacity contract, executor, host wrapper and host baseline with sidecars.

The workflow itself verifies post-upload binding and declares T1/live mutation false.

Retention: 30 days.

## 5. B — exact-main F4/reboot producer

Workflow:

~~~text
.github/workflows/n3w-t1-f4-exact-control-package.yml
workflow name=N3W T1 F4 exact control package
event=workflow_dispatch
~~~

Expected binding:

~~~text
run.head_branch=main
run.head_sha=90775b804807b4ff69ca7cea71a220a2e3a5a416
run.status=completed
run.conclusion=success
~~~

Required artifacts from the same run:

~~~text
n3w-t1-f4-control-package-90775b804807b4ff69ca7cea71a220a2e3a5a416
n3w-t1-f4-reboot-successor-control-90775b804807b4ff69ca7cea71a220a2e3a5a416
~~~

Both package builders bind their manifests and reports to the exact source head. Neither package executes reboot or live mutation.

Retention: 14 days. This is the shortest retention in the chain, so C and D should follow without unnecessary delay after A/B close.

## 6. C — exact-main V2 release inputs

Workflow:

~~~text
.github/workflows/n3w-t1-f5-v2-release-inputs-ci.yml
workflow name=N3W T1 F5 V2 exact release inputs CI
event=workflow_dispatch

input:
  f3_run_id=<successful A run>
  f4_run_id=<successful B run>
~~~

The workflow enforces:

- current checkout is exact merged `main`;
- both upstream runs use the exact same current main SHA;
- F3 path is exactly the fresh-bootstrap producer;
- F4 path is exactly the F4 package producer;
- both upstream runs are completed/success;
- only push/workflow_dispatch upstream events are accepted;
- exact F3/F4/reboot artifact names exist once and are unexpired;
- builder runs with `--production-authority`;
- source head and source tree are embedded in release inputs;
- post-upload re-download verification passes.

Required output:

~~~text
n3w-t1-f5-v2-release-inputs-90775b804807b4ff69ca7cea71a220a2e3a5a416
~~~

The release-input material must contain exactly six required production artifacts:

~~~text
f3_payload
f3_image
f4_control
reboot_control
v2_mac_tools
transport_contract
~~~

The `v2_mac_tools` archive includes the merged production executor and verifier stack, including:

~~~text
n3w_t1_production_v2_executor.py
n3w_t1_production_v2.py
n3w_t1_production_v2_contract.py
n3w_t1_post_reboot_acceptance.py
n3w_t1_f4_reboot_verify.py
n3w_t1_f5_v2_release_builder.py
~~~

Retention: 30 days.

## 7. D — exact-main production release

Workflow:

~~~text
.github/workflows/n3w-t1-f5-v2-exact-production-release-ci.yml
workflow name=N3W T1 F5 V2 exact production release CI
event=workflow_dispatch

input:
  inputs_run_id=<successful C run>
  inputs_artifact_name=n3w-t1-f5-v2-release-inputs-90775b804807b4ff69ca7cea71a220a2e3a5a416
~~~

The workflow enforces:

- checkout is exact merged main;
- release-input producer path is exact;
- release-input run is workflow_dispatch, completed/success and bound to the same main SHA;
- the required release-input artifact exists exactly once and is unexpired;
- builder runs with `--production-authority`;
- release source head/tree match the checkout and release inputs;
- every required artifact has exact size/SHA binding;
- release directory passes `n3w_t1_f5_v2_release_builder.py verify`.

Required output:

~~~text
n3w-t1-f5-v2-exact-production-release-90775b804807b4ff69ca7cea71a220a2e3a5a416
~~~

The uploaded artifact contains:

~~~text
n3w-t1-f5-v2-release.tar.gz
n3w-t1-f5-v2-release.tar.gz.sha256
~~~

Retention: 30 days.

## 8. Main-drift rule

A/B/C/D must never silently bridge a main change.

The release-input and final-release workflows already fail closed if `origin/main` differs from the workflow's `GITHUB_SHA`. The operator-side rule is stronger:

~~~text
if current main != 90775b804807b4ff69ca7cea71a220a2e3a5a416
before the authoritative chain completes:
    STOP
    classify previous artifacts as historical/non-authoritative
    fresh rebind
    rebuild from the new exact main
~~~

Do not reuse A/B artifacts across different source heads even if file contents appear identical.

## 9. E — local exact-release validation boundary

Local validation is a separate gate after D succeeds. It must at minimum prove:

~~~text
artifact source/run/name binding=PASS
outer artifact set exact=PASS
release tar SHA sidecar=PASS
safe extraction=PASS
release directory verify=PASS
release.source_head=exact main
release.source_tree=exact main tree
required release artifact set exact=PASS
v2_mac_tools contains repaired executor/verifier bytes=PASS
secret_values_included=false
board_access=false
~~~

The local validation gate must record the final Actions run ID, artifact ID/digest, release tar SHA256, release manifest SHA256/release ID and the local cache path/binding. It must not access T1.

## 10. F — Standard Fresh Armbian read-only qualification boundary

Only after local release validation may the project prepare the target-side read-only qualification.

That qualification remains separate from production mutation and must prove the target is eligible for this exact release. It does not itself authorize STARTED, deployment, reboot or service mutation.

## 11. Current decision

~~~text
EXACT_MAIN_REBUILD_PATH=READY
SOURCE_REPAIR_REQUIRED=false

F3_DISPATCH_READY=true
F4_REBOOT_DISPATCH_READY=true
RELEASE_INPUTS_DISPATCH_READY_AFTER_F3_F4_PASS=true
FINAL_RELEASE_DISPATCH_READY_AFTER_INPUTS_PASS=true

WORKFLOW_DISPATCH_THIS_GATE=false
ARTIFACT_BUILD_THIS_GATE=false

NEXT_ONE_GATE=
N3W_T1_F5_V2_EXACT_MAIN_F3_F4_ARTIFACT_REBUILD_EXECUTION_20261021_01

AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~
