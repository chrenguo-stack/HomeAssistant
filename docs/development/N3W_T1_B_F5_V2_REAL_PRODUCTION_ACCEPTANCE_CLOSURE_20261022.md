# N3W T1-B F5 V2 exact-release real production acceptance closure — 2026-10-22

## 1. Closure result

~~~text
TASK=N3W_T1_B_F5_V2_EXACT_RELEASE_REAL_PRODUCTION_ACCEPTANCE_CLOSURE_20261022_01

SOURCE_HEAD=4733c09ab7653bacca6e197e63a583f500b45845
SOURCE_TREE=9ca2927c02e15ae4a0f18c475486e7bbf7206bc9
MAIN_DRIFT=false

PR650_MERGED=true
PRE_MUTATION_PRIVATE_EVIDENCE_REPAIR=PASS

EXACT_RELEASE_REBUILD=CLOSED_PASS
LOCAL_EXACT_RELEASE_VALIDATION=PASS
STANDARD_FRESH_ARMBIAN_QUALIFICATION=PASS

RUN_ID_RAW_PUBLICATION=false
RUN_ID_SHA256=e56b8a1a086f9ce5b196a5a97a7faff2d645ccf64b4254dd2c3150a1fe91d761
PLAN_SHA256=a11003bfb742612ab5a4f1652950c40a5c2d8fc50b445c30a5cd4326ad1afcba
TARGET_BINDING_SHA256=5760d55945216620ee7e3c3c75c1ec6255b3bad398657c548d18ca0fc5665141

PRODUCTION_RESULT_STATUS=PASS
MARKER_STATE=ACCEPTED
DEVICE_ACCEPTANCE=PASS
T1_PRODUCTION_READY=true
EVIDENCE_COMPLETE=true
OPERATOR_SESSION_CLOSED=true
REFLASH_REQUIRED=false
ERROR_CLASS=NONE
TERMINAL_STAGE=COMPLETE
PRIVATE_RESULT_SHA256=156f187413844a69b9ab429c857dd3dad312582fc837930d0f4ee0cec80e96a7
EXECUTOR_EXIT_CODE=0

FAILED_RUN_REPLAY=false
BOARD_ACCESS=false
~~~

The current exact-release T1-B production path completed end-to-end and reached the
durable `ACCEPTED` marker. Raw run ID, target address, credentials and operator-local
evidence paths remain private and are intentionally not recorded in repository docs.

## 2. Exact release authority

~~~text
F3_RUN_ID=39742649252
F3_ARTIFACT_ID=12410645037
F3_ARTIFACT_DIGEST=sha256:01fba75accb2e1bfe2b1df21c364659f383ee9cc4806ee342302e18c87f56711

F4_RUN_ID=39743991124
F4_CONTROL_ARTIFACT_ID=12410915115
F4_CONTROL_ARTIFACT_DIGEST=sha256:deabc8faa6860b3918875281674f4a5495fe1dee6d7c2880a081fba93f1bc087
F4_REBOOT_ARTIFACT_ID=12410182427
F4_REBOOT_ARTIFACT_DIGEST=sha256:77dbe54cba48c15185ab90f84cadae2bc14b264f32c1afcef51b873a4ec2dddb

F5_INPUTS_RUN_ID=39744225204
F5_INPUTS_ARTIFACT_ID=12410303815
F5_INPUTS_ARTIFACT_DIGEST=sha256:712fed6aa2533170dde12c716491e4e6e3eeedcc81203caeb19a6299bcc0fe9e

FINAL_RELEASE_RUN_ID=39744898094
FINAL_RELEASE_RUN_ATTEMPT=1
FINAL_ARTIFACT_ID=12410429647
FINAL_ARTIFACT_NAME=n3w-t1-f5-v2-exact-production-release-4733c09ab7653bacca6e197e63a583f500b45845
FINAL_ARTIFACT_ZIP_SHA256=2b7323e07575ef9a5703bbd7965af1278e3c7260c79fe9f1dcaab47dcc3424be

RELEASE_ID=d34e6d132518376a595e3d42f5acc64a904d2d809e2c80332635f35a16af00df
RELEASE_SHA256=74490f305fd47d22e968edff354debe96780c6369d6ce9d3d726f44874916748
~~~

The prior release bound to source `6bc1029d63160e1fce27f2c9d483d1b5cb5f6a2a`
remains historical/non-authoritative.

## 3. Fresh-target qualification

~~~text
HOST.OS_ARCH=PASS
HOST.ARMBIAN_IDENTITY=PASS
HOST.FIRSTBOOT=PASS
HOST.SSH_TRUST=PASS
HOST.PRIVILEGE=PASS
HOST.NETWORK_TIME=PASS
HOST.STORAGE=PASS
HOST.APT_SOURCE=PASS
HOST.DOCKER_ABSENT=PASS
HOST.PRODUCT_ABSENT=PASS

STANDARD_FRESH_ARMBIAN_QUALIFICATION=PASS
READ_ONLY=true
MUTATION_PERFORMED=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
REFLASH_REQUIRED=false
~~~

The earlier PRE_MUTATION failure remained terminal/no-replay. Because its marker was
ABSENT and no target mutation had started, a second reflash was not required before
this fresh qualification and new run.

## 4. Real production stage evidence

~~~text
HOST_BASELINE=PASS
F3_DEPLOY=PASS
PROVISION=PASS
F4_PREPARE=PASS
F4_ACTIVATE=PASS
F4_ACCEPT=PASS
F4_PERSISTENCE=PASS
F4_CERT_AUDIT=PASS
F4_CERT_TIMER=PASS

REBOOT_CONTROL_WAITING_FOR_OPERATOR=OBSERVED
REBOOT_CONTROL_ARMED=PASS
OLD_BOOT_SSH_DOWN=PASS
REBOOT_PENDING=PASS
WAIT_FOR_SSH=PASS
SSH_EPOCH_2=PASS
POST_REBOOT_READINESS=PASS
POST_REBOOT_ACCEPTANCE=PASS
MARKER_ACCEPTED=PASS
~~~

The repaired operator-presence boundary was exercised before the one-shot reboot.
The executor then proved old-boot SSH down, established SSH epoch #2, passed the
readiness barrier, completed strict post-reboot acceptance and committed ACCEPTED.

## 5. Known-failure live revalidation disposition

~~~text
KF_122=CLOSED_PASS_LIVE_REVALIDATED
KF_124=CLOSED_PASS_LIVE_REVALIDATED
KF_125=CLOSED_PASS_LIVE_REVALIDATED
KF_126=CLOSED_PASS_LIVE_REVALIDATED
KF_127=CLOSED_PASS_LIVE_REVALIDATED
KF_128=CLOSED_PASS_LIVE_REVALIDATED
~~~

Closure basis:

- KF-122: repaired non-disruptive post-reboot acceptance completed and the run reached ACCEPTED.
- KF-124: run-bound operator arming and the separate post-reboot password epoch both completed.
- KF-125: POST_REBOOT_READINESS passed before strict acceptance, and strict acceptance passed.
- KF-126: OLD_BOOT_SSH_DOWN passed before post-reboot SSH recovery, then SSH epoch #2 passed.
- KF-127: a fresh exact-release full run crossed the repaired readiness path and completed end-to-end. This does not claim every synthetic partial-unit branch occurred in this specific boot; those forced edge branches remain regression-test authority.
- KF-128: the accepted runtime/connection evidence path completed inside strict post-reboot acceptance. This does not claim every synthetic negative branch occurred live.

Historical failed runs remain terminal/no-replay; their evidence and regression guards
remain historical authority.

## 6. Current product state

~~~text
T1_B_PRODUCTION_ACCEPTANCE=CLOSED_PASS
T1_B_PRODUCTION_READY=true
T1_B_REFLASH_REQUIRED=false
CURRENT_EXACT_RELEASE_ACCEPTED=true

FAILED_RUN_REPLAY=false
AUTOMATIC_RETRY=false
BOARD_ACCESS=false
~~~

This closure is bounded to T1-B and the exact release/source identities above. It
does not authorize another T1 production run, reflash, board operation or unrelated
live mutation.

## 7. Repository alignment route

~~~text
ALIGNMENT_SCOPE=DOCS_ONLY
PRODUCT_SOURCE_MUTATION=false
WORKFLOW_DISPATCH=false
GITHUB_ARTIFACT_PRODUCTION=false
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
REFLASH=false
PRODUCTION_EXECUTION=false

NEXT_ONE_GATE=N3W_T1_B_F5_V2_REAL_PRODUCTION_ACCEPTANCE_ALIGNMENT_MERGE_DECISION_20261022_01
AUTO_EXECUTE_NEXT_GATE=false
~~~

Issue #651 is the exact-main release rebuild record. Issue #652 is the fresh target
qualification, exact-run authorization and real-production acceptance record.
