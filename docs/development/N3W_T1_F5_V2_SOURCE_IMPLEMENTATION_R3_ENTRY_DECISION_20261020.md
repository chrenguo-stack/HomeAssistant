# N3W T1 F5 V2 R3 entry decision — 2026-10-20

> 2026-10-20 后续修订：本文保留历史决策与当时测试事实。生产身份 Mac 正向 MQTT 探测、旧外部探测集合及仅首尾重启计数的验收语义已被 `N3W_T1_F5_V2_NONDISRUPTIVE_POST_REBOOT_ACCEPTANCE_SOURCE_REPAIR_20261020.md` 取代；本文历史 PASS 不代表新的非扰动合同已完成实机验收。

## 0. Gate

~~~text
TASK=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R3_ENTRY_DECISION_20261020_01
AUTHORIZATION=N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R3_ENTRY_DECISION_20261020_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true

SOURCE_PR=624
SOURCE_BRANCH=feat/n3w-t1-f5-v2-source-implementation-20261019

R2_FINAL_EXACT_SOURCE_HEAD=29cf8fee111f3bf9e525e396a0a8f270349ede7f
R2_CLOSURE_DOCS_HEAD=e4f41b8e16e5f5f91e3c66798090a703dabd86ee
BASE_MAIN=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
BEHIND_MAIN=0

PR_STATE=OPEN_DRAFT
PR_MERGEABLE=true

T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false
MERGE=false
~~~

This gate is an R3 source-entry decision only. It does not implement R3 source.

## 1. Fresh rebind result

Fresh rebind confirms:

~~~text
BRANCH_HEAD=e4f41b8e16e5f5f91e3c66798090a703dabd86ee
MAIN_HEAD=4223f23d2579241f6568a1ba3fbbccf26b3bc3c1
R2_SOURCE_TO_CLOSURE_DOCS=DOCS_ONLY
R2_CLOSED_PASS=true
READY_FOR_R3_ENTRY_DECISION=true
~~~

The R2 exact source head remains unchanged beneath one docs-only closure commit.

## 2. R3 prerequisites

### 2.1 R2 closure

The exact R2 source head has:

~~~text
WORKFLOWS=17_OF_17_PASS
F2_SOURCE_CI=72_PASS
F5_V2_R2_FOCUSED_TESTS=86_PASS
FRESH_BOOTSTRAP_PAYLOAD=104_PASS
PRODUCTION_STACK_PAYLOAD=60_PASS
FOCUSED_REVIEW_BLOCKERS=0
UNRESOLVED_REVIEW_THREADS=0
REVIEWS_REQUIRING_CHANGES=0
~~~

No R2 source or repository-integration blocker remains.

### 2.2 Existing reusable target-local reboot verifier

Existing:

~~~text
tools/n3w_t1_f4_reboot_verify.py
tests/tools/test_n3w_t1_f4_reboot_verify.py
~~~

already proves the target-local reboot side needed by R3:

~~~text
REAL_BOOT_ID_CHANGE_REQUIRED=true
F4_TRANSACTION_UNCHANGED_REQUIRED=true
PROVISION_AND_FACTORY_BINDING_RECHECK=true
RUNTIME_SERVICE_SET_RECHECK=true
IMAGE_AND_CONTAINER_RUNTIME_BINDING_RECHECK=true
TLS_RUNTIME_RECHECK=true
MANAGER_RUNTIME_STABILITY_RECHECK=true
HOMEASSISTANT_READINESS_RECHECK=true
NEGATIVE_BROKER_AUTH_PROBE=true
REBOOT_VERIFY_READ_ONLY=true
~~~

The verifier returns PASS / REBOOT_ACCEPTED and does not write the V2 marker. That separation is correct for R3.

Therefore:

~~~text
F4_REBOOT_VERIFY_REQUIRED_ADAPTATION=false
~~~

unless a later focused source test proves a concrete interface gap.

### 2.3 Existing V2 marker surface

Existing:

~~~text
tools/n3w_t1_production_marker.py
~~~

already exposes a terminal accept transition that requires:

~~~text
CURRENT_STATE=STARTED
EXACT_RUN_RELEASE_SOURCE_TARGET_HOST_PLAN_BINDING=true
ACCEPTANCE_SHA256_REQUIRED=true
ACCEPTED_AT_REQUIRED=true
T1_PRODUCTION_READY=true
ATOMIC_REPLACE_AND_FSYNC=true
SECOND_ACCEPT_REJECTED=true
~~~

Therefore R3 must call this existing accept surface only after all target-local and external acceptance checks pass.

### 2.4 Existing V2 contract

The V2 contract already contains:

~~~text
ACTION=POST_REBOOT_ACCEPTANCE
MARKER_STATES=STARTED|ACCEPTED
ERROR_CLASS=POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED
FINAL_RESULT_SCHEMA=true
V2_RELEASE_SCHEMA=true
SOURCE_TREE_BINDING=true
EXACT_PACKAGE_VERSION_BINDING=true
REQUIRED_ARTIFACT_BINDINGS=true
~~~

No contract change is required for R3 entry.

## 3. Missing R3 source surfaces

The following frozen R3 files are currently absent, as expected:

~~~text
tools/n3w_t1_post_reboot_acceptance.py
tests/tools/test_n3w_t1_post_reboot_acceptance.py

tools/n3w_t1_f5_v2_release_builder.py
tests/tools/test_n3w_t1_f5_v2_release_builder.py

.github/workflows/n3w-t1-f5-v2-exact-production-release-ci.yml
~~~

The existing R2 orchestrator intentionally stops at:

~~~text
R2_TERMINAL_STATE=REBOOT_PENDING
post_reboot_acceptance_complete=false
~~~

The current V2 source CI contains R1 and R2 jobs only.

These are R3 implementation targets, not entry blockers.

## 4. Frozen R3 implementation scope

### 4.1 Required additions

~~~text
tools/n3w_t1_post_reboot_acceptance.py
tests/tools/test_n3w_t1_post_reboot_acceptance.py

tools/n3w_t1_f5_v2_release_builder.py
tests/tools/test_n3w_t1_f5_v2_release_builder.py

.github/workflows/n3w-t1-f5-v2-exact-production-release-ci.yml
~~~

### 4.2 Required adaptations

~~~text
tools/n3w_t1_production_v2.py
tests/tools/test_n3w_t1_production_v2.py

.github/workflows/n3w-t1-f5-v2-source-ci.yml
~~~

The orchestrator must extend the already-closed R2 path after controlled reboot:

~~~text
REBOOT_PENDING
-> WAIT_FOR_SSH
-> SSH_EPOCH_2
-> TARGET_LOCAL_REBOOT_VERIFY
-> EXTERNAL_POST_REBOOT_ACCEPTANCE
-> 90_SECOND_BOUNDED_OBSERVATION
-> ACCEPTANCE_HASH
-> MARKER_ACCEPTED
-> SSH_EPOCH_2_CLOSE
-> FINAL_RESULT
~~~

No automatic replay is allowed.

### 4.3 Reuse without modification by default

~~~text
tools/n3w_t1_f4_reboot_verify.py
tests/tools/test_n3w_t1_f4_reboot_verify.py

tools/n3w_t1_production_marker.py
tests/tools/test_n3w_t1_production_marker.py

tools/n3w_t1_production_v2_contract.py
tests/tools/test_n3w_t1_production_v2_contract.py
~~~

These files may only be changed inside R3 if focused tests prove a concrete frozen-contract interface gap. Such a change must be separately justified in the R3 progress authority.

## 5. R3 acceptance contract

R3 must require all of the following before marker ACCEPTED:

~~~text
TARGET_LOCAL_F4_REBOOT_VERIFY=PASS
REAL_BOOT_ID_CHANGED=true
RELEASE_SOURCE_BINDING=PASS
V2_STARTED_MARKER_BINDING=PASS

TCP_8883=PASS
TLS_CA=PASS
TLS_HOSTNAME_SNI=PASS
MANAGER_MQTT_AUTH=PASS
HOMEASSISTANT_MQTT_AUTH=PASS
INVALID_CREDENTIAL_REJECTED=PASS
HOMEASSISTANT_HTTP_READY=PASS
NO_CRITICAL_RESTART_DURING_90S_OBSERVATION=PASS

ACCEPTANCE_HASH_BOUND=true
MARKER_ACCEPTED_LAST=true
~~~

The external probes are Mac-side acceptance evidence. Existing target-local F4 checks must be reused instead of copied.

Any failure before durable ACCEPTED must enter the already-frozen failure finalization path and end:

~~~text
ERROR_CLASS=POST_REBOOT_ACCEPTANCE_FAIL_REFLASH_REQUIRED
TARGET_DISPOSITION=REFLASH_REQUIRED
AUTOMATIC_RETRY=false
~~~

If durable ACCEPTED is already written and only later Mac/session/public-result cleanup fails:

~~~text
DEVICE_ACCEPTANCE=PASS
T1_PRODUCTION_READY=true
REFLASH_REQUIRED=false
ERROR_CLASS=PROCESS_CLEANUP_FAIL
~~~

## 6. Release builder and exact release policy

R3 source work must add a testable V2 release builder/validator.

The builder must bind at least:

~~~text
V2_RELEASE_SCHEMA
EXACT_SOURCE_HEAD
EXACT_SOURCE_TREE
RELEASE_ID
RELEASE_SHA256
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

The exact production release is not authorized from a PR head.

~~~text
PR_RELEASE_PRODUCTION_AUTHORITY=false
EXACT_PRODUCTION_RELEASE_AFTER_SOURCE_MERGE_ONLY=true
EXACT_RELEASE_SOURCE_MUST_BE_MERGED_MAIN=true
OLD_ARTIFACT_ID_AS_LONG_TERM_AUTHORITY=false
~~~

The exact-production-release workflow may be added during R3 source implementation, but its production authority must only become valid after source closure, merge, and fresh exact-main rebind.

## 7. R3 source CI closure requirements

The V2 source workflow must gain an R3-focused job that proves at minimum:

~~~text
POST_REBOOT_ACCEPTANCE_MODULE_COMPILES=true
RELEASE_BUILDER_MODULE_COMPILES=true
R3_FOCUSED_TESTS=PASS
R1_REGRESSIONS=PASS
R2_REGRESSIONS=PASS

REAL_BOOT_CHANGE_REQUIRED=true
F4_REBOOT_VERIFY_PASS_REQUIRED=true
EXTERNAL_ACCEPTANCE_ALL_REQUIRED=true
OBSERVATION_WINDOW_SECONDS=90
MARKER_ACCEPTED_LAST=true

PRE_ACCEPT_FAILURE_REFLASH_REQUIRED=true
POST_ACCEPT_PROCESS_FAILURE_NO_REFLASH=true
NO_AUTOMATIC_RETRY=true
NORMAL_PATH_REPAIR_COMMANDS_UNREACHABLE=true

PR_RELEASE_PRODUCTION_AUTHORITY=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
~~~

R3 source closure does not itself authorize a real T1 run or produce a production-authoritative release.

## 8. Explicit exclusions

R3 must not expand into:

~~~text
firmware
ESP32
radio
pairing business logic
target-local repair
V1 recovery path
F3/F4 repair commands
real T1 deployment
real board access
merge
production release authority before merge
~~~

Provision/F4 existing sources remain untouched unless a focused test proves a real interface blocker.

## 9. Entry decision

~~~text
R2_CLOSED_PASS=true
R3_ENTRY_PREREQUISITES=PASS
R3_ENTRY_BLOCKER_COUNT=0

R3_ENTRY_GRANTED=true
R3_STARTED=false

NEXT_ONE_GATE=
N3W_T1_F5_V2_SOURCE_IMPLEMENTATION_R3_POST_REBOOT_ACCEPTANCE_AND_RELEASE_INTEGRATION_20261020_01

AUTO_EXECUTE_NEXT_GATE=false
NEW_AUTHORIZATION_REQUIRED=true
STOP=true
~~~

## 10. Hard safety boundary

~~~text
T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false
MERGE=false
~~~
