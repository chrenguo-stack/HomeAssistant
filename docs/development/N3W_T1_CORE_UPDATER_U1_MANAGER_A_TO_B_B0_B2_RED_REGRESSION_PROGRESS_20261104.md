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

The exact repository CI later completed and reproduced the expected RED precisely. The only failing test was the newly added discovery retry regression; all 1489 pre-existing tests passed and one test was skipped. The failure was the expected assertion that four publish calls should have occurred after retry, while Manager A produced only two.

```text
B2_SOURCE_SEMANTIC_RED_PROOF=PASS
B2_EXACT_REPOSITORY_PYTEST=PASS_EXPECTED_RED
B2_EXACT_CI_RUN_ID=41811967169
B2_EXACT_CI_TEST_RESULT=1_FAILED_1489_PASSED_1_SKIPPED
B2_EXACT_FAILURE=test_discovery_publish_failure_retries_unchanged_telemetry
B2_EXACT_FAILURE_ASSERTION=ASSERT_2_EQUALS_4
GATE_FINAL_CLOSE=CLOSED_PASS
SOURCE_REPAIR_REQUIRED=true
AUTO_ENTER_B3=false
```

## Stop boundary

No Manager product repair, Target B artifact, T1 access, updater apply/rollback, service restart, Broker/Home Assistant/credential/registration/pairing mutation, board access, merge, or automatic B3 entry is performed in this gate.


## Final exact CI closure

```text
EXACT_PR_HEAD=47204c8c59201dc1b3d3b6ff0d9fbe74833611d6
GREENHOUSE_MANAGER_CI_RUN_ID=41811967169
GREENHOUSE_MANAGER_CI=FAIL_EXPECTED_RED
RUFF=PASS
PYTEST_TOTAL_RESULT=1_FAILED_1489_PASSED_1_SKIPPED
FAILED_TEST=tests/runtime/test_mqtt_discovery_retry.py::test_discovery_publish_failure_retries_unchanged_telemetry
FAILED_ASSERTION=assert service._publish.call_count == 4
OBSERVED_CALL_COUNT=2
EXPECTED_CALL_COUNT=4
UNRELATED_TEST_FAILURE_COUNT=0
HARNESS_FAILURE=false
PRODUCT_SOURCE_REPAIR_PERFORMED=false
B0=PASS
B1=PASS
B2=PASS
GATE_RESULT=CLOSED_PASS
NEXT_GATE_NOT_ENTERED=B3
AUTO_ENTER_B3=false
```

The exact CI result confirms the candidate defect without ambiguity: after the first discovery publish attempt reports an immediate failure, unchanged telemetry does not cause a second discovery publish attempt. The existing Manager A cache semantics suppress the retry exactly as predicted.

This closes only the RED-proof gate. It does not authorize or perform the Manager production-code repair, Target B artifact build, live T1 apply, board access, service restart, merge, or B3 entry.


## Post-closure CI hygiene

After the RED proof was closed, PR #777 still showed a failing `greenhouse-manager CI` because the
new regression remained an ordinary failing test against the intentionally-unrepaired Manager A.

To keep the proof while avoiding a permanently red test-only PR, the proven regression was changed
to a strict expected failure:

```text
CI_HYGIENE_COMMIT=b699bea5ad95fbb422f6e5f6c77cd978b4626c81
CHANGE_SCOPE=TEST_ONLY
PYTEST_MARKER=xfail(strict=True)
XFAIL_REASON=Manager_A_commits_discovery_cache_before_MQTT_publish_success
MANAGER_PRODUCT_SOURCE_MUTATION=false
B3_ENTERED=false
```

This does not weaken the future regression. While Manager A remains unfixed, the test is expected to
XFAIL and CI may pass. Once B3 repairs the product behavior, the test will XPASS and strict mode will
fail CI until the temporary xfail marker is removed, converting it into a normal permanent regression
test.


## B3 minimum Manager product-source repair

User authorization to enter B3 was granted after CI #6060 confirmed the post-RED strict-xfail branch
was green.

```text
B3_AUTHORIZED=true
B3_SCOPE=DISCOVERY_PUBLISH_FAILURE_RETRY_CORRECTNESS_ONLY
FINDING_2_INCLUDED=false
FINDING_3_INCLUDED=false
BROKER_CHANGE=false
HOMEASSISTANT_CHANGE=false
DATABASE_MIGRATION=false
CONFIG_MIGRATION=false
T1_ACCESS=false
BOARD_ACCESS=false
U1_LIVE_APPLY_AUTHORIZED=false
```

The minimum repair changes only `ManagerMqttService._publish_discovery()`:

- inspect each immediate `_publish()` boolean result;
- log success only for successful immediate publishes;
- log a bounded deferred/retry warning for immediate failure;
- if any discovery publish fails, clear that node's discovery cache after the publish loop;
- allow the next identical telemetry to regenerate and retry both discovery documents;
- keep normal successful discovery de-duplication unchanged;
- do not wait for PUBACK and do not change canonical telemetry commit semantics.

The RED test is simultaneously converted from temporary strict-xfail back into an ordinary permanent
regression test. It additionally proves that a fully successful retry restores normal de-duplication
and that the failed topic is not falsely logged as successfully published.

```text
B3_PRODUCT_SOURCE_MUTATION=true
B3_PRODUCT_FILE=host/greenhouse-manager/src/greenhouse_manager/runtime/mqtt_service.py
B3_TEST_FILE=host/greenhouse-manager/tests/runtime/test_mqtt_discovery_retry.py
B3_STATUS=IMPLEMENTED_PENDING_CI
AUTO_ENTER_B4=false
```
