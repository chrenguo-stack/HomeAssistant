# 温室环境监测系统（ESP32-C6）
# N3-W Auto Safe Fallback — Gate A CLOSED / Gate B Ready
# 新会话交接文档 V1.0 — 2026-10-02

```text
HANDOFF_TEMPLATE_VERSION=1.2
PROJECT_WORKING_CONTEXT_VERSION=1.0
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文只保存当前 `auto` 安全回退路线的阶段增量。长期工作规则统一引用 `N3W_PROJECT_WORKING_CONTEXT.md`。  
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并先停止执行。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=N3W_AUTO_SAFE_FALLBACK_GATE_A_CLOSED_GATE_B_READY
CURRENT_STOP_POINT=GATE_A_CLOSED_PASS_NO_FURTHER_PHYSICAL_ACTION
NEXT_ONE_GATE=N3W_AUTO_SAFE_FALLBACK_GATE_B_DISCOVERY_PAIRING_DECOUPLING_SOURCE_REPAIR_20261002_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

本轮 Gate A 已完成真实 ESP32-C6 MQTT runtime retarget 时序验证、T1 临时实验环境清理、Board B exact KF-099 回滚和回滚后 WAIT 行为复验。新会话不再重复 Gate A，直接从 Gate B 的源码/测试工作继续。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.0
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=2
STAGE_OVERRIDES=GATE_B_SOURCE_TEST_ONLY_AT_ENTRY;NO_GATE_C_AUTO_ENTRY
```

本阶段临时收紧：Gate B 入场只做源码、测试、文档和必要 CI，不做 Board/T1 live mutation；Gate B PASS 后也必须 STOP，不自动进入 Gate C。

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=AUTO_MODE_STALE_T1_IPV4_SAFE_RAM_ONLY_REDISCOVERY
FINAL_ACCEPTANCE_TARGET=PROVISIONED_NODE_RECOVERS_FROM_STALE_T1_IPV4_WITHOUT_REPAIRING_OR_DURABLE_IDENTITY_CHANGE
DEFERRED_OR_OUT_OF_SCOPE=B2_STABLE_HOSTNAME_MDNS_TLS_IDENTITY;DYNAMIC_LOAD_BALANCING;FULL_GATE_F_PHYSICAL_ACCEPTANCE
```

目标是在 `GH_N3W_PAIRING_ADVERTISED_HOST=auto` 下，当已经配对节点保存的 T1/Broker IPv4 失效时，节点可以在保留既有身份、证书信任和 MQTT 凭据的前提下重新发现候选地址，并仅在 RAM 中临时使用新地址。

当前方案不是完整 B2 稳定主机名方案；B2 仍作为未来产品升级方向。当前路线是更小、更现实的安全回退机制。

---

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
MAIN_TREE=ee977996a4c962097684519841dce2e3bcba23f2

CANDIDATE_REF=fix/n3w-auto-safe-fallback-v1-20260929
CANDIDATE_HEAD=8cadebfb03fec98c7c503fe827b5abefc4f9021a
CANDIDATE_TREE=c16eb1601d56e11c380fe43ac3f6d9c6f8c9610e
CANDIDATE_HEAD_ROLE=GATE_A_CLOSURE_ALIGNED_PRE_HANDOFF_HEAD
HANDOFF_COMMIT_REQUIRES_FRESH_REBIND=true

ARTIFACT_ID=NOT_APPLICABLE:GATE_B_SOURCE_TEST_GATE
ARTIFACT_SHA256=NOT_APPLICABLE:GATE_B_SOURCE_TEST_GATE

DEPLOYED_SOURCE_HEAD=c578bcb2e31f50771b6b08c231704da6bf36b729
DEPLOYED_SOURCE_TREE=1678c7fa571db9b8f47b7b8a03dbd332620d1e19

OTHER_REQUIRED_AUTHORITY=docs/development/N3W_AUTO_SAFE_FALLBACK_DEVELOPMENT_TEST_PLAN_V1_20260929.md;docs/development/N3W_AUTO_SAFE_FALLBACK_SOURCE_REPAIR_EXECUTION_PLAN_20260929.md;docs/development/N3W_AUTO_SAFE_FALLBACK_GATE_A_PHYSICAL_CLOSURE_20261002.md;docs/development/N3W_KF099_PHYSICAL_VALIDATION_CLOSURE_20260928.md
```

Fresh main/branch drift check at handoff preparation:

```text
MERGE_BASE=a363962a118e823f97022a6c398383e9e43fc830
BRANCH_AHEAD_OF_CURRENT_MAIN=82
BRANCH_BEHIND_CURRENT_MAIN=39
BRANCH_STATUS=diverged

MAIN_COMMITS_SINCE_MERGE_BASE=39
RELEVANT_GREENHOUSE_N3W_CORE_SOURCE_DRIFT_ON_MAIN=false
MAIN_DRIFT_DOMAIN=DOCS_KF100_TOOLING_WORKFLOW_ONLY
GATE_B_PRODUCT_SOURCE_REDESIGN_REQUIRED_BEFORE_ENTRY=false
FRESH_REBIND_STILL_REQUIRED=true
```

The 39 current-main commits after the PR merge base do not modify `firmware/esphome_rc/components/greenhouse_n3w_core/`. Therefore Gate B can continue on the existing PR branch after a fresh read-only rebind; however the branch must eventually reconcile current-main documentation/workflow drift before merge.

Gate A source authority retained for regression context:

```text
GATE_A_SOURCE_HEAD=8210cf7b53e9ec934d145f1c15e9619579c923be
GATE_A_SOURCE_TREE=5d3e6ad7151938ffa7ac23b2b6af6663bcd10c7c
GATE_A_TARGET_BLOB=7279271d469958940c2b51aa4a80602078470891
GATE_A_PATCH_BLOB=49570a83ead08158d4d99c385740fa6d646b5e3d
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
```

---

## 4. Current Live Baseline

Only facts freshly relevant to the completed Gate A physical closeout are frozen here. Gate B does not require live runtime access.

```text
MANAGER_STATE=PASS_AT_LAST_FRESH_OBSERVATION:12_REPAIR_INTENT_REQUIRED_RESPONSES_OVER_TCP47112
MANAGER_RESTART_STATE=LAST_PROVEN_1_EXPECTED_FROM_USER_INITIATED_T1_RESTART;FRESH_RECHECK_IF_LATER_USED
BROKER_STATE=LAST_PROVEN_PRODUCTION_CONTINUITY_PASS_RESTART_COUNT_0;NOT_REQUIRED_FOR_GATE_B_ENTRY
HOMEASSISTANT_STATE=UNKNOWN_FRESH:NOT_REQUIRED_FOR_GATE_B_ENTRY

BOARD_A_POWER_STATE=UNKNOWN_FRESH:NOT_REQUIRED_FOR_GATE_B_ENTRY
BOARD_A_LOCATION_ROLE=UNKNOWN_FRESH:NOT_REQUIRED_FOR_GATE_B_ENTRY
BOARD_B_POWER_STATE=ON_AT_LAST_FRESH_GATE_A_CLOSEOUT
BOARD_B_LOCATION_ROLE=KF099_BASELINE_DUT
BOARD_B_APPLICATION_SHA256=d0875ca692f7bd4349fd7d8bcdab69318e6c8b737b69a48f667b6e72cb89cb60
BOARD_B_PAIRING_ID_SHA256=142d1e0c9fc035645ce38e4681add39ba3ed5b3b0d60e14a4a1dfa398ab2472e
BOARD_B_POST_RESET_WIFI_CONNECTED=true

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false
```

No private LAN address, SSH locator, Wi-Fi credential, setup secret, QR payload, private key or raw secret-bearing capture belongs in the public handoff.

---

## 5. Proven Current Facts

```text
GATE_A=PASS
GATE_A_RUNTIME_BOUNDED_CANCEL_PROVEN=true
FULL_AUTO_FALLBACK_IMPLEMENTATION_ALLOWED=true

LIVE_RECONNECT_MS=15704
BLACKHOLE_ACTIVE_RECOVER_MS=8711
BLACKHOLE_WAIT_RECOVER_MS=12960
MQTT_STAGE_BUDGET_MS=25000

GATE_A_T1_LAB_CLEANUP=PASS
GATE_A_T1_LAB_RESIDUE=false
PRODUCTION_BROKER_RESTART_COUNT_LAST_PROVEN=0

BOARD_B_KF099_ROLLBACK=PASS
PAIRING_TRANSACTION_PRESERVED=true
PAIRING_ID_HASH_MATCH_HISTORICAL_KF099=true
KF099_POST_ROLLBACK_WAIT_BEHAVIOR=PASS
BEGIN_SUPPRESSION=PASS

VALID_POST_ROLLBACK_CAPTURE_SECONDS=60
BOARD_B_IPV4_PACKET_COUNT=168
TCP47112_CLIENT_CONNECTION_COUNT=12
HELLO_COUNT=12
REPAIR_INTENT_REQUIRED_COUNT=12
BEGIN_COUNT=0
CLIENT_STREAM_GAP_COUNT=0
SERVER_STREAM_GAP_COUNT=0
CLIENT_CAPTURE_COMPLETE=true

FULL_AUTO_FALLBACK_SOURCE_REPAIR_COMPLETE=false
FULL_AUTO_FALLBACK_PHYSICAL_ACCEPTANCE_COMPLETE=false
B3_CLOSED=false
PR516_DRAFT=true
MERGE=false
```

Observer corrections that must carry forward:

```text
INVALID_OBSERVER_FIELD_1=gh.discovery.request
ACTUAL_DISCOVERY_QUERY_SCHEMA=gh.discovery.query/1
DISCOVERY_RESPONSE_COUNT_OBSERVED=12

INVALID_OBSERVER_FIELD_2=nonce
ACTUAL_HELLO_RANDOM_FIELD=node_nonce
HELLO_DISTINCT_NONCE_COUNT_ZERO_FROM_LAST_OBSERVER=INVALID_MEASUREMENT_NOT_PRODUCT_EVIDENCE
```

Firmware source generates a fresh 32-byte random `node_nonce` for every `send_hello_()` call. Historical KF-099 exact physical validation already proved 18 distinct hello nonces with this same accepted product source.

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=0
CURRENT_BLOCKER=NONE_FOR_GATE_B_ENTRY
ROOT_CAUSE=NOT_APPLICABLE:NO_OPEN_GATE_B_BLOCKER
PROVEN_BY=GATE_A_PHYSICAL_CLOSURE_PLUS_FRESH_MAIN_PRODUCT_SOURCE_DRIFT_CHECK
SOURCE_DEFECT_PROVEN=NOT_APPLICABLE:GATE_B_NOT_STARTED
RUNTIME_DEFECT_PROVEN=NOT_APPLICABLE:GATE_B_NOT_STARTED
```

The branch is 39 commits behind current main, but the fresh comparison shows no relevant `greenhouse_n3w_core` product-source drift on main. This is a merge/repository-alignment item, not a Gate B source blocker.

---

## 7. Closed / Forbidden Routes

```text
GATE_A=CLOSED_PASS:DO_NOT_REENTER_OR_REPEAT_PHYSICAL_FIXTURE
FIRST_GATE_A_PRIVATE_APPLICATION=CLOSED_SUPERSEDED:DO_NOT_FLASH_OR_REUSE
FIRST_T1_LAB_ACTIVATION_AUTHORIZATION=CLOSED_CONSUMED:DO_NOT_REPLAY
GATE_A_BOARD_B_WRITE_AUTHORIZATION=CLOSED_CONSUMED:DO_NOT_REPLAY
KF099_ROLLBACK_WRITE_AUTHORIZATION=CLOSED_CONSUMED:DO_NOT_REPLAY
BOARD_B_RESET_ONLY_AUTHORIZATION=CLOSED_CONSUMED:DO_NOT_REPLAY
WIFI_RECONFIG_AUTHORIZATION=CLOSED_UNUSED:DO_NOT_CARRY_INTO_GATE_B
REMOTE_TIMEOUT_TCPDUMP_EMPTY_CAPTURES=CLOSED_INVALID_NEGATIVE_EVIDENCE
PAIRING_REPAIR_ROUTE=FORBIDDEN:NOT_AUTHORIZED_AND_NOT_REQUIRED
ORDINARY_PAIRING_RUN_ONCE_FOR_AUTO_ADDRESS_RECOVERY=FORBIDDEN_BY_DESIGN
DURABLE_DISCOVERED_IP_WRITE=FORBIDDEN_BY_V1_DESIGN
PR516_MERGE=FORBIDDEN:FULL_ROUTE_NOT_COMPLETE
GATE_C=FORBIDDEN_UNTIL_GATE_B_PASS_AND_NEW_STOP_REVIEW
```

KF-098 and KF-099 remain `GUARDED`; do not reopen them based on the invalid empty capture attempts. Current main known-failure authority records KF-098 and KF-099 as closed/guarded.

---

## 8. Authorization Ledger

```text
AUTHORIZATION=GATE_A_T1_LAB_V2_ACTIVATION
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=GATE_A_CLOSURE

AUTHORIZATION=GATE_A_BOARD_B_V2_WRITE
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=KF099_ROLLBACK

AUTHORIZATION=GATE_A_KF099_EXACT_ROLLBACK_WRITE
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=KF099_BASELINE_RESTORED

AUTHORIZATION=BOARD_B_RESET_ONLY
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=POST_RESET_WAIT_BEHAVIOR_PASS

AUTHORIZATION=BOARD_B_WIFI_RECONFIG
CLAIMED=false
CONSUMED=false
RESULT=NOT_EXECUTED:NO_FALLBACK_AP_RECONFIG_OCCURRED
REPLAY_PERMITTED=false
SUPERSEDED_BY=EXISTING_WIFI_RECONNECTED_AFTER_CONTROLLED_RESET

PROPOSED_AUTHORIZATION=LIVE_BOARD_OR_T1_MUTATION_FOR_GATE_B
GRANTED=false
REQUIRED=false
```

Gate B source/tests/docs/GitHub work stays inside the normal repository-development scope. Any later Board/T1/live/credential/firmware mutation requires a new bounded authorization.

---

## 9. Rollback Authority

Gate B changes repository source/tests only; there is no live mutation rollback in this gate.

```text
ROLLBACK_BASELINE=CANDIDATE_HEAD_8cadebfb03fec98c7c503fe827b5abefc4f9021a_PLUS_HANDOFF_COMMIT
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=true
ROLLBACK_AUTHORITY_PATH_OR_ID=GIT_BRANCH_HISTORY_AND_PR516
RESTART_SCOPE_ALLOWED=false
SECOND_ATTEMPT_ALLOWED=ONLY_AFTER_FAILURE_CLASSIFICATION_AND_SOURCE_REVIEW
ROLLBACK_FAILURE_CLASS=SOURCE_REPAIR_INCOMPLETE
LIVE_RUNTIME_ROLLBACK_AUTHORITY=NOT_APPLICABLE:NO_LIVE_MUTATION
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_AUTO_SAFE_FALLBACK_GATE_B_DISCOVERY_PAIRING_DECOUPLING_SOURCE_REPAIR_20261002_01
```

### Purpose

Gate B must separate reusable Manager discovery from ordinary initial pairing so an already-provisioned node can later rediscover a T1 address without entering `SimplePairingClient::run_once()` and without touching durable identity/trust.

This gate proves only the discovery protocol/filtering layer and its source contracts. It does **not** integrate the new discovery path into Direct recovery; that is Gate C.

### Inputs

```text
INPUT_1=docs/development/N3W_AUTO_SAFE_FALLBACK_DEVELOPMENT_TEST_PLAN_V1_20260929.md
INPUT_2=docs/development/N3W_AUTO_SAFE_FALLBACK_SOURCE_REPAIR_EXECUTION_PLAN_20260929.md
INPUT_3=firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_pairing_client.cpp
INPUT_4=firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.cpp
INPUT_5=existing pairing/discovery tests and KF098/KF099 regression guards
INPUT_6=durable trusted Broker record semantics
```

### Operations

```text
1. Fresh rebind PR #516 head and current main; re-confirm relevant greenhouse_n3w_core product-source drift is still absent.
2. Inspect current discovery query/response construction/parsing and network responsibilities without changing runtime behavior yet.
3. Extract/reuse discovery protocol logic so provisioned-node recovery can call it without entering SimplePairingClient::run_once().
4. Require a fresh request_id and discovery nonce for every round.
5. Collect responses with hard bounds: parse <=8 datagrams, retain <=3 deduplicated candidates, later attempt <=2 candidate addresses.
6. Validate candidate system_id, IPv4 unicast, same-subnet, and source IP == advertised host.
7. Keep Broker port from the durable trusted Broker record; treat discovered host only as an untrusted candidate address.
8. Prove discovery cannot overwrite CA, TLS server name, MQTT username/password/client_id, NODE_ID, SYSTEM_ID, peer trust, credential generation, or durable broker_host/NVS.
9. Add focused pure protocol/filter/source-contract tests, including malformed/duplicate/off-subnet/source-mismatch/too-many-response cases.
10. Run focused tests and relevant repository CI. Stop at Gate B closure; do not integrate Direct recovery state machine yet.
```

### PASS / FAIL / STOP

```text
PASS_IF=REUSABLE_DISCOVERY_DECOUPLED_FROM_PAIRING_AND_ALL_BOUNDED_PROTOCOL_FILTER_TESTS_PASS_WITH_TRUST_AND_NVS_GUARDS_INTACT
FAIL_IF=ANY_PROVISIONED_RECOVERY_PATH_ENTERS_ORDINARY_PAIRING_OR_ANY_UNTRUSTED_DISCOVERY_FIELD_CAN_MUTATE_DURABLE_IDENTITY_TRUST_CREDENTIALS_OR_BUDGET_BOUNDS_ARE_UNENFORCED
STOP_BOUNDARY=GATE_B_TESTS_AND_SOURCE_REVIEW_COMPLETE_BEFORE_ANY_GATE_C_INTEGRATION

AUTO_EXECUTE_NEXT_GATE=false
```

---

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- read-only fresh GitHub/main/PR rebind
- source inspection under greenhouse_n3w_core
- bounded source refactor for reusable discovery logic
- unit/source-contract tests for Gate B
- documentation updates directly required by Gate B
- normal repository CI for source/test validation
- GitHub commits to PR #516 branch within Gate B scope
```

### FORBIDDEN

```text
- Board A or Board B access, reset, erase, flash, NVS write or serial-based physical mutation
- T1/Broker/Manager live mutation
- pairing repair or new pairing session
- changing NODE_ID, SYSTEM_ID, peer trust, CA, TLS server name or MQTT credentials
- persisting discovered candidate address into NVS/durable broker record
- using ordinary SimplePairingClient::run_once() as the provisioned-node address-recovery path
- Gate C Direct-recovery state-machine integration
- Gate F physical acceptance
- PR #516 merge or conversion out of Draft solely because Gate B passes
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
BOUNDED_WRITE_SCOPE=NOT_APPLICABLE
```

---

## 12. Execution Contract

```text
EXECUTOR=DIRECT_REPOSITORY_SOURCE_TEST_WORKFLOW
EXECUTION_METHOD=chat-tool+repository-source-tests+ci
DIRECT_CODE_SUPPLIED=true
DSL_COMPILATION_USED=false
```

Use phased GitHub operations. First rebind, then inspect the small source set, then make bounded changes, then run focused tests, then CI. Do not create a new physical executor or live harness for Gate B.

On a substantive mismatch or unexpected relevant main-source drift: STOP, classify first, and do not auto-rebase/auto-repair into a different architecture.

---

## 13. Expected Closure

```text
=== N3W AUTO SAFE FALLBACK GATE B CLOSURE ===

EXECUTION_ID=N3W_AUTO_SAFE_FALLBACK_GATE_B_DISCOVERY_PAIRING_DECOUPLING_SOURCE_REPAIR_20261002_01
AUTHORIZATION=SOURCE_TEST_DOCS_ONLY
AUTHORIZATION_CLAIMED=NOT_APPLICABLE_LIVE_MUTATION_FALSE
AUTHORIZATION_CONSUMED=NOT_APPLICABLE_LIVE_MUTATION_FALSE

FRESH_MAIN=
FRESH_PR_HEAD=
RELEVANT_PRODUCT_SOURCE_DRIFT=

DISCOVERY_PAIRING_DECOUPLED=
PROVISIONED_PATH_CALLS_PAIRING_RUN_ONCE=false
FRESH_REQUEST_ID_PER_ROUND=
FRESH_DISCOVERY_NONCE_PER_ROUND=
MAX_PARSED_RESPONSES=8
MAX_RETAINED_CANDIDATES=3
MAX_ATTEMPTED_CANDIDATE_ADDRESSES=2
SYSTEM_ID_FILTER=
IPV4_UNICAST_FILTER=
SAME_SUBNET_FILTER=
SOURCE_IP_EQUALS_ADVERTISED_HOST_FILTER=
BROKER_PORT_FROM_DURABLE_TRUSTED_RECORD=
DISCOVERY_CAN_OVERWRITE_CA=false
DISCOVERY_CAN_OVERWRITE_TLS_NAME=false
DISCOVERY_CAN_OVERWRITE_MQTT_CREDENTIALS=false
DISCOVERY_CAN_WRITE_NVS=false

FOCUSED_TESTS=
SOURCE_REVIEW=
RELEVANT_CI=

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

GATE_B_RESULT=PASS|FAIL
NEXT_ROUTE=STOP_FOR_GATE_C_DECISION
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=N3W_AUTO_SAFE_FALLBACK_GATE_C_DIRECT_RECOVERY_STATE_MACHINE_INTEGRATION_DESIGN_OR_SOURCE_REPAIR
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=NO_FOR_SOURCE_ONLY_GATE_C_PREPARATION;YES_BEFORE_ANY_LIVE_OR_BOARD_MUTATION

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

Gate B PASS is not full source-repair completion and is not merge authorization.

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
EXISTING_KF_GUARD_USED=KF098;KF099
NEW_KF_REQUIRED=false
```

Do not allocate a new KF merely because Gate B is new work. Add a KF only if Gate B produces a real reproduced/confirmed defect with an established symptom/root-cause boundary.

Current main authority keeps:

```text
KF098=GUARDED
KF099=GUARDED
```

---

## 16. New Chat Start Prompt

Default read set:

```text
1. docs/development/N3W_AUTO_SAFE_FALLBACK_GATE_B_NEW_CHAT_HANDOFF_V1.0_20261002.md
2. docs/development/N3W_PROJECT_WORKING_CONTEXT.md
3. docs/development/N3W_CURRENT_STATE.md
4. docs/development/N3W_CURRENT_STATE_INDEX.md
5. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
```

Suggested start text:

```text
阅读《docs/development/N3W_AUTO_SAFE_FALLBACK_GATE_B_NEW_CHAT_HANDOFF_V1.0_20261002.md》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_AUTO_SAFE_FALLBACK_DEVELOPMENT_TEST_PLAN_V1_20260929.md
- docs/development/N3W_AUTO_SAFE_FALLBACK_SOURCE_REPAIR_EXECUTION_PLAN_20260929.md
- docs/development/N3W_AUTO_SAFE_FALLBACK_GATE_A_PHYSICAL_CLOSURE_20261002.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W auto 安全回退路线。

Gate A 已 CLOSED_PASS，不重新进入、不重复物理测试、不重放任何 consumed authorization。

先 fresh rebind：
- repository main
- Draft PR #516
- fix/n3w-auto-safe-fallback-v1-20260929
- greenhouse_n3w_core 相关源码

确认 current main 自 merge-base 以来仍无相关产品源码漂移后，只进入：

NEXT_ONE_GATE=N3W_AUTO_SAFE_FALLBACK_GATE_B_DISCOVERY_PAIRING_DECOUPLING_SOURCE_REPAIR_20261002_01

Gate B 只做 discovery 与 pairing 解耦的源码/测试：
- 已配对节点不得走 SimplePairingClient::run_once()
- 每轮 fresh request_id + nonce
- 最多解析 8、保留 3、尝试 2 个候选
- 校验 system_id、IPv4 单播、同子网、source IP == advertised host
- Broker port 继续来自 durable trusted record
- discovery 不得修改 CA/TLS name/MQTT credentials/身份/peer trust/NVS

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
MERGE=false
AUTO_EXECUTE_GATE_C=false

Gate B tests/source review 完成后 STOP，再决定 Gate C。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=N3W_AUTO_SAFE_FALLBACK_GATE_A_CLOSED_GATE_B_READY
CURRENT_STOP_POINT=GATE_A_CLOSED_PASS
CURRENT_BLOCKER=NONE_FOR_GATE_B_ENTRY
LIVE_SYSTEM_STATE=KF099_BASELINE_RESTORED_AND_WAIT_BEHAVIOR_PASS_AT_LAST_FRESH_OBSERVATION
NEXT_ONE_GATE=N3W_AUTO_SAFE_FALLBACK_GATE_B_DISCOVERY_PAIRING_DECOUPLING_SOURCE_REPAIR_20261002_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
PRIVATE_EVIDENCE_OUTSIDE_GITHUB_COUNT=NONZERO_BY_DESIGN_PUBLIC_SAFE_RESULTS_COMMITTED
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.0
HANDOFF_TEMPLATE_VERSION=1.2

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

Important private evidence remains outside public GitHub by design: temporary Gate A private build/bundle material, private LAN locators, Wi-Fi credentials, raw secret-bearing serial/network captures and other private runtime material. All engineering conclusions required to continue Gate B are now durably represented by public-safe hashes/counts/status documents in PR #516.

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.2
PROJECT_WORKING_CONTEXT_VERSION=1.0

PROJECT_WORKING_CONTEXT_REFERENCED=PASS
LONG_TERM_RULE_DUPLICATION_MINIMIZED=PASS
STAGE_SPECIFIC_OVERRIDES_EXPLICIT=PASS
PRIVATE_CONTEXT_EXCLUDED_FROM_PUBLIC_HANDOFF=PASS

PRODUCT_NORTH_STAR_PRESENT=PASS
FROZEN_AUTHORITIES_COMPLETE=PASS
CURRENT_LIVE_BASELINE_COMPLETE=PASS
PROVEN_FACTS_SEPARATED_FROM_INFERENCE=PASS
CURRENT_BLOCKERS_EXPLICIT=PASS
CLOSED_ROUTES_EXPLICIT=PASS

AUTHORIZATION_LEDGER_COMPLETE=PASS
CONSUMED_AUTH_REPLAY_GUARD=PASS
ROLLBACK_AUTHORITY_EXPLICIT=PASS

NEXT_ONE_GATE_EXPLICIT=PASS
NEXT_GATE_SCOPE_BOUNDED=PASS
ALLOWED_FORBIDDEN_SCOPE_EXPLICIT=PASS
EXECUTION_CONTRACT_SELF_CONTAINED=PASS
EXPECTED_CLOSURE_PRESENT=PASS
AFTER_PASS_DOES_NOT_AUTO_EXECUTE=PASS

KNOWN_FAILURES_UPDATE_CLASSIFIED=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
TEAM_WORKSPACE_STATUS_PRESENT=PASS
FINAL_FROZEN_STATE_PRESENT=PASS

HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```
