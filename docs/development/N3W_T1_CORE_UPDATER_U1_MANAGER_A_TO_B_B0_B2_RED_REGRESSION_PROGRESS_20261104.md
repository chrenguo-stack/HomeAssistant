# N3-W T1 Core Updater U1 — Manager A -> B B0/B2 RED regression progress

Date: 2026-11-04

## Gate

```text
TASK=N3W_T1_CORE_UPDATER_U1_MANAGER_A_TO_B_B0_B2_RED_REGRESSION_20261104_01
MANAGER_A_TO_B_RESUME_DECISION=true
U1_LIVE_APPLY_AUTHORIZED=false
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
MANAGER_PRODUCT_SOURCE_MUTATION=false
TARGET_B_ARTIFACT_PRODUCTION=false
T1_ACCESS=false
BOARD_ACCESS=false
MERGE=false
AUTO_ENTER_B3=false
```

## B0 fresh rebind

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=86b61479e1f42fd6eea9e2c34fb9c5047f9c088d
MAIN_TREE=1a98304e1231310adc799f00a338e706f90f4b20
HANDOFF_PR=776
HANDOFF_HEAD=04efc887cc9694692df215fb3fcc39229181630b
HANDOFF_BRANCH=docs/n3w-u1-manager-a-to-b-resume-handoff-20261104
HANDOFF_CHANGED_FILES=3
HANDOFF_DOCS_ONLY=true

MANAGER_A_PRODUCT_SOURCE=b863ddd959090ca139af76bd68dbef31d773e6de
HA_DISCOVERY_BLOB_MANAGER_A=912eaf5e28a6cb3cd516fd376c09a6a3ac9601f6
HA_DISCOVERY_BLOB_CURRENT_MAIN=912eaf5e28a6cb3cd516fd376c09a6a3ac9601f6
MQTT_SERVICE_BLOB_MANAGER_A=66b83b96a4fa320ef92912a16063b507e8d7f7f5
MQTT_SERVICE_BLOB_CURRENT_MAIN=66b83b96a4fa320ef92912a16063b507e8d7f7f5
TEST_HA_DISCOVERY_BLOB_MANAGER_A=b5cff83973cb8cc56f2e0d79a86bb8f3be80c22b
TEST_HA_DISCOVERY_BLOB_CURRENT_MAIN=b5cff83973cb8cc56f2e0d79a86bb8f3be80c22b

PRODUCT_SOURCE_DRIFT=false
B0=PASS
```

PR #776 changes only:

- `docs/development/N3W_CURRENT_STATE.md`
- `docs/development/N3W_CURRENT_STATE_INDEX.md`
- `docs/development/N3W_T1_CORE_UPDATER_U1_MANAGER_A_TO_B_RESUME_RED_REGRESSION_NEW_CHAT_HANDOFF_V1.0_20261104.md`

The current main Manager discovery source is byte-identical to the frozen Manager A review authority.

## B1 minimum RED regression

Dedicated branch:

```text
BRANCH=test/n3w-u1-manager-a-to-b-red-regression-20261104
BASE=main@86b61479e1f42fd6eea9e2c34fb9c5047f9c088d
RED_TEST_COMMIT=858b983fc4bcc4a652169ea07d2b24d128dad6dd
RED_PR=777
RED_PR_DRAFT=true
```

The commit adds exactly one file:

`host/greenhouse-manager/tests/runtime/test_mqtt_discovery_retry.py`

No Manager production source is modified.

The regression models:

1. unchanged canonical telemetry produces two Home Assistant Discovery messages;
2. the first discovery transport publish returns immediate failure;
3. the second discovery publish succeeds;
4. the next identical telemetry is delivered again;
5. expected behavior is to retry discovery;
6. current Manager A is expected to suppress the retry if the discovery cache was already committed.

Existing Manager tests already use `ManagerMqttService(Settings(system_id="dev"))` with the MQTT client patched, so the new test follows an established test initialization path.

```text
B1=PASS
```

## B2 source-semantic RED reproduction

Independent method-level execution used the exact current Manager A semantics of:

- `HomeAssistantDiscovery.messages_for_telemetry()`
- `ManagerMqttService._publish_discovery()`

Observed:

```text
first_publish_calls=2
first_topics=[
  homeassistant/device/node-0001/config,
  homeassistant/binary_sensor/node-0001_connectivity/config
]
second_retry_publish_calls=0
total_publish_calls=2
desired_total_publish_calls=4
red_regression=FAIL_EXPECTED

adjacent_dedup_first=2
adjacent_dedup_second=0
adjacent_dedup=PASS
```

Root-cause binding:

```text
DISCOVERY_HASH_CACHE_COMMIT_BEFORE_PUBLISH_SUCCESS=true
PUBLISH_RESULT_CONTROLS_CACHE_COMMIT=false
IMMEDIATE_PUBLISH_FAILURE_INVALIDATES_CACHE=false
NEXT_IDENTICAL_TELEMETRY_RETRY_SUPPRESSED=true
CANDIDATE_ROOT_CAUSE_CONFIRMED_BY_SOURCE_SEMANTICS=true
```

This reproduces the expected retry suppression while preserving the adjacent successful de-duplication behavior.

## Exact PR pytest / CI state

The exact RED test commit triggered ordinary PR CI.

```text
CI_EXACT_HEAD=858b983fc4bcc4a652169ea07d2b24d128dad6dd
GREENHOUSE_MANAGER_CI_RUN_ID=41811577586
PUBLIC_REPOSITORY_SAFETY_CI=SUCCESS
GREENHOUSE_MANAGER_CI_POLL_1=QUEUED
GREENHOUSE_MANAGER_CI_POLL_2=IN_PROGRESS
GREENHOUSE_MANAGER_CI_POLL_3=IN_PROGRESS
CI_POLL_MAX_REACHED=true
FURTHER_POLLING_STOPPED=true
```

Direct CI URL:

`https://github.com/chrenguo-stack/HomeAssistant/actions/runs/41811577586`

The local container could not clone GitHub because DNS resolution is unavailable in that execution environment. That is a local tooling limitation, not a product/test result.

The method-level source-semantic proof is already deterministic for the candidate defect, but the exact repository pytest result is intentionally not claimed until the already-running CI result is observed later.

```text
B2_SOURCE_SEMANTIC_RED_PROOF=PASS
B2_EXACT_REPOSITORY_PYTEST=CI_PENDING_AT_POLL_LIMIT
GATE_FINAL_CLOSE=PENDING_EXACT_CI_RESULT
SOURCE_REPAIR_REQUIRED_IF_EXACT_CI_FAILS_FOR_EXPECTED_ASSERTION=true
AUTO_ENTER_B3=false
```

## Stop boundary

No Manager product repair, Target B artifact, T1 access, updater apply/rollback, service restart, Broker/Home Assistant/credential/registration/pairing mutation, board access, merge, or automatic B3 entry is performed in this gate.
