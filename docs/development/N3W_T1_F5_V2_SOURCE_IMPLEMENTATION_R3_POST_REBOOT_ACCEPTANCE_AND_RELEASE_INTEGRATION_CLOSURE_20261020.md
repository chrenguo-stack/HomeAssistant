# N3W T1 F5 V2 R3 post-reboot acceptance and release integration closure — 2026-10-20

> 2026-10-20 后续修订：本文保留历史决策与当时测试事实。生产身份 Mac 正向 MQTT 探测、旧外部探测集合及仅首尾重启计数的验收语义已被 `N3W_T1_F5_V2_NONDISRUPTIVE_POST_REBOOT_ACCEPTANCE_SOURCE_REPAIR_20261020.md` 取代；本文历史 PASS 不代表新的非扰动合同已完成实机验收。

## 0. Gate identity

~~~text
TASK=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R3_POST_REBOOT_ACCEPTANCE_AND_RELEASE_INTEGRATION_20261020_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true

SOURCE_PR=624
SOURCE_BRANCH=feat/n3w-t1-f5-v2-source-implementation-20261019
R3_ENTRY_DOCS_HEAD=2943359a806784b0a6f56a13a7f94973bafd1d1f
R3_FINAL_EXACT_SOURCE_HEAD=5233b08743f40a021844e4ce7f464f444de86ae1
R3_FINAL_EXACT_SOURCE_TREE=dfab4b7ffc455a3b1c26956744fa1197bbd55006
BASE_MAIN=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
BEHIND_MAIN=0

T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

## 1. Whole-source delta

From the R3 entry-decision head to the final exact R3 source head, the source delta is limited to the frozen R3 boundary:

~~~text
.github/workflows/n3w-t1-f5-v2-exact-production-release-ci.yml
.github/workflows/n3w-t1-f5-v2-source-ci.yml

tools/n3w_t1_f5_v2_release_builder.py
tools/n3w_t1_post_reboot_acceptance.py
tools/n3w_t1_production_v2.py

tests/tools/test_n3w_t1_f5_v2_release_builder.py
tests/tools/test_n3w_t1_post_reboot_acceptance.py
tests/tools/test_n3w_t1_production_v2.py
~~~

No Provision/F4 conditional source file, firmware, ESP32, radio, or pairing business logic changed in R3.

## 2. R3 implementation closure

The exact reviewed source now enforces:

~~~text
REBOOT_PENDING
-> WAIT_FOR_SSH
-> SSH_EPOCH_2
-> POST_REBOOT_ACCEPTANCE
-> ACCEPTANCE_HASH
-> MARKER_ACCEPTED
-> SSH_EPOCH_2_CLOSE
-> FINAL_RESULT
~~~

Acceptance requires the existing target-local F4 reboot verification result to be PASS / REBOOT_ACCEPTED with a real boot-identity change, then requires every frozen Mac-side external probe, followed by the exact 90-second critical-service restart observation.

Required external acceptance set:

~~~text
TCP_8883
TLS_CA
TLS_HOSTNAME_SNI
MANAGER_MQTT_AUTH
HOMEASSISTANT_MQTT_AUTH
INVALID_CREDENTIAL_REJECTED
HOMEASSISTANT_HTTP_READY
NO_CRITICAL_RESTART_DURING_OBSERVATION
~~~

The V2 STARTED marker, release/source/target/host/plan binding, acceptance hash, and terminal ACCEPTED transition remain separated from deployment success. Durable ACCEPTED is written only after acceptance PASS.

## 3. Failure-ordering closure

Focused closure review found and repaired the remaining conservative-boundary defects.

Final behavior:

~~~text
PRE_MUTATION_FAILURE
-> no reflash authority
-> operator_session_closed reflects proven cleanup state only

STARTED mutation attempted or state uncertain
-> never downgrade to PRE_MUTATION
-> FREEZE_EVIDENCE
-> FORENSIC_SNAPSHOT_COMPLETE
-> SESSION_CLOSE
-> REFLASH_REQUIRED

DURABLE_ACCEPTED + later Mac/session cleanup failure
-> DEVICE_ACCEPTANCE=PASS
-> T1_PRODUCTION_READY=true
-> PROCESS_CLEANUP_FAIL
-> REFLASH_REQUIRED=false
~~~

The R2 outward exception/test contract remains preserved while R3 tracks the STARTED/session boundary conservatively.

## 4. Release integration closure

The V2 release builder binds:

~~~text
V2_RELEASE_SCHEMA
EXACT_SOURCE_HEAD
EXACT_SOURCE_TREE
EXACT_DOCKER_IO_PACKAGE_VERSION
EXACT_DOCKER_COMPOSE_V2_PACKAGE_VERSION
APT_SOURCE_POLICY
F3_PAYLOAD
F3_IMAGE
F4_CONTROL
REBOOT_CONTROL
V2_MAC_TOOLS
TRANSPORT_CONTRACT
CAPACITY_CONTRACT
PUBLIC_EVIDENCE_FIELD_ALLOWLIST
~~~

Release input source head/tree must match the exact checkout, the input artifact set must equal the frozen V2 set, artifact paths/symlinks are fail-closed, and every copied artifact is hash/size bound.

The exact-production-release workflow is manual-only and enforces merged-main authority. It additionally requires the reviewed release-input artifact to be uniquely named for the exact merged-main SHA and produced by a successful run with that same main head.

~~~text
PR_RELEASE_PRODUCTION_AUTHORITY=false
EXACT_PRODUCTION_RELEASE_AFTER_SOURCE_MERGE_ONLY=true
EXACT_RELEASE_SOURCE_MUST_BE_MERGED_MAIN=true
EXACT_PRODUCTION_RELEASE_BUILD_EXECUTED=false
~~~

No production-authoritative release was built from PR #624.

## 5. Exact-head CI

At exact source head `5233b08743f40a021844e4ce7f464f444de86ae1`:

~~~text
WORKFLOW_TOTAL=17
WORKFLOW_SUCCESS=17
WORKFLOW_FAILURE=0
WORKFLOW_PENDING=0

N3W_T1_F5_V2_SOURCE_CI_RUN=39371652141
RESULT=PASS
R1_FOUNDATIONS=PASS
R2_SOURCE=PASS
R2_FOCUSED_TESTS=96_PASS
R2_BOUNDARY=PASS
R3_SOURCE=PASS
R3_FOCUSED_TESTS=64_PASS
R3_BOUNDARY=PASS
OBSERVATION_WINDOW_SECONDS=90
PR_RELEASE_PRODUCTION_AUTHORITY=false

N3W_T1_F2_READONLY_PREFLIGHT_SOURCE_CI_RUN=39371652091
RESULT=PASS

N3W_T1_FRESH_BOOTSTRAP_DEPLOYABLE_PAYLOAD_CI_RUN=39371652102
RESULT=PASS

N3W_T1_PRODUCTION_STACK_STAGING_PAYLOAD_CI_RUN=39371652098
RESULT=PASS

N3W_T1_FRESH_INSTALL_HOST_ONLY_CI=PASS
N3W_T1_GOLDEN_MASTER_SOURCE_CI=PASS
PUBLIC_REPOSITORY_SAFETY_CI=PASS
GREENHOUSE_MANAGER_CI=PASS
~~~

## 6. Whole-source review

Fresh rebind and whole-source review confirm:

~~~text
PR_STATE=OPEN_DRAFT
PR_MERGEABLE=true
MAIN_HEAD=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
BRANCH_HEAD=5233b08743f40a021844e4ce7f464f444de86ae1
BEHIND_MAIN=0

R3_FILE_BOUNDARY=PASS
R1_REGRESSIONS=PASS
R2_REGRESSIONS=PASS
DEPENDENT_F2_BINDINGS=PASS
FRESH_BOOTSTRAP_PAYLOAD_REGRESSION=PASS
PRODUCTION_STACK_PAYLOAD_REGRESSION=PASS

CONDITIONAL_PROVISION_F4_SOURCE_CHANGED=false
FIRMWARE_CHANGED=false
ESP32_RADIO_PAIRING_CHANGED=false

UNRESOLVED_REVIEW_THREADS=0
REVIEWS_REQUIRING_CHANGES=0
WHOLE_SOURCE_BLOCKER_COUNT=0
~~~

R3 does not authorize a real T1 run. Existing F4 target-local verification remains reused through the R3 acceptance boundary and was not modified.

## 7. R3 and source implementation closure

~~~text
R1_CLOSED_PASS=true
R2_CLOSED_PASS=true
R3_CLOSED_PASS=true

F5_V2_SOURCE_IMPLEMENTATION_CLOSED_PASS=true
SOURCE_PR624_MERGED=false
READY_FOR_PR624_MERGE_DECISION=true

T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~

## 8. Next gate

~~~text
NEXT_ONE_GATE=N3W_T1_F5_V2_PR624_MERGE_DECISION_20261020_01
AUTO_EXECUTE_NEXT_GATE=false
NEW_AUTHORIZATION_REQUIRED=true
~~~

The merge decision must fresh-rebind PR #624, current main, this docs-only closure head, exact source ancestry, and required CI/review state. It must not treat this closure as merge authorization.

## 9. Hard stop

~~~text
GATE_RESULT=CLOSED_PASS
STOP=true

T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
~~~
