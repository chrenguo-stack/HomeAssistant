# 温室环境监测系统（ESP32-C6）
# N3-W / PR #437 Wi-Fi Recovery Budget Source Repair
# 新会话交接文档 V1.0 — 2026-09-21

```text
HANDOFF_TEMPLATE_VERSION=1.2
PROJECT_WORKING_CONTEXT_VERSION=1.0
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文只保存当前阶段增量。长期工作规则引用 `N3W_PROJECT_WORKING_CONTEXT.md`。  
> 当前该 working-context 文件与本 handoff 一起位于文档对齐 PR #447；在 PR #447 合并前，不要假定 `main` 已包含它。  
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并先停止执行。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=PR437_WIFI_RECOVERY_BUDGET_SOURCE_REPAIR_EXACT_HEAD_CI_PASS
CURRENT_STOP_POINT=4270F24_SOURCE_REVIEW_PASS_AND_11_OF_11_CI_PASS_BEFORE_NEW_EXACT_ARTIFACT
NEXT_ONE_GATE=N3W_PR437_4270F24_EXACT_ARTIFACT_BUILD_AND_BINDING_PREPARATION_20260921_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

当前对话在 PR #437 的 Wi-Fi recovery budget 修复、源码复核和 exact-head CI 全部通过后切换。新会话不重新复盘历史，先 fresh 绑定 GitHub，然后只准备 `4270f24...` 的新 exact artifact。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.0
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=1
STAGE_OVERRIDES=PR447_IS_OPEN_DRAFT_UNMERGED; read working-context/current-state/handoff from PR447 branch until merged
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
FINAL_ACCEPTANCE_TARGET=Board B same-boot Direct -> Relay -> Direct with bounded recovery latency, single-radio safety, stable Relay service, and Manager-visible telemetry continuity under the accepted Option-B delivery contract
DEFERRED_OR_OUT_OF_SCOPE=Option-C durable every-sample delivery architecture; PR437 merge; any Board flash before a new exact artifact is built and separately authorized
```

---

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=a5a4dc06e86374287348bb8718e7f7fb7d6c42d2
TREE=291cd078000d82e811a65d44ae782aa0b044bda9

CANDIDATE_REF=test/n3w-kf096-direct-recovery-liveness-red-20260918
CANDIDATE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
CANDIDATE_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f

ARTIFACT_ID=NOT_APPLICABLE:current exact head not built yet
ARTIFACT_SHA256=NOT_APPLICABLE:current exact head not built yet

DEPLOYED_SOURCE_HEAD=177468e290a207f2fb7f6c554aedf60b61373b4d
DEPLOYED_SOURCE_TREE=a50ff98887b14b70cf9d278c6f8b7edf536eae88

OTHER_REQUIRED_AUTHORITY=DEPLOYED_ARTIFACT_ID_10607030747; DEPLOYED_APPLICATION_SHA256_74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093; DOCS_ALIGNMENT_PR_447
```

PR #437 is `OPEN_DRAFT`, unmerged, and current exact-head CI is 11/11 PASS. PR #437 vs current main is diverged: ahead 50, behind 28, merge-base `d9afc55b04042806ed8b6e1b1ae3553742aba2be`. No rebase or merge is authorized by this handoff.

---

## 4. Current Live Baseline

```text
MANAGER_STATE=UNKNOWN_FRESH
MANAGER_RESTART_STATE=UNKNOWN_FRESH
BROKER_STATE=UNKNOWN_FRESH
HOMEASSISTANT_STATE=UNKNOWN_FRESH

BOARD_A_POWER_STATE=UNKNOWN_FRESH
BOARD_A_LOCATION_ROLE=UNKNOWN_FRESH
BOARD_B_POWER_STATE=UNKNOWN_FRESH:last observed USB enumeration PASS
BOARD_B_LOCATION_ROLE=PRIMARY_DUT; physical location requires fresh confirmation before any physical gate

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false
```

Most recent read-only evidence before handoff showed Manager and Broker continuity PASS, Board B native USB still enumerated, and zero local serial owner. These are historical-to-this-handoff observations, not substitutes for the next live gate's fresh checks.

```text
MANAGER_STATE_REQUIRES_FRESH_READONLY_RECHECK=true
BROKER_STATE_REQUIRES_FRESH_READONLY_RECHECK=true
BOARD_B_POWER_STATE_REQUIRES_FRESH_READONLY_RECHECK=true
```

---

## 5. Proven Current Facts

```text
PR437_CURRENT_HEAD_SOURCE_REVIEW=PASS
PR437_CURRENT_HEAD_CI=11_OF_11_PASS

DEPLOYED_APPLICATION_READBACK=PASS
POSTWRITE_DIRECT_BASELINE=FAIL
LAST_MANAGER_CANONICAL_SEQ=49
LAST_MANAGER_CANONICAL_SOURCE=direct

EXACT_BOARD_B_MQTT_DISCONNECT=PROVEN
EXACT_BOARD_B_MQTT_RECONNECT_AFTER_ANCHOR_OBSERVED=false
MANAGER_RESTART_DURING_FORENSIC=0
BROKER_RESTART_DURING_FORENSIC=0
MASS_CLIENT_DISCONNECT_NEAR_EVENT=false
BROKER_ERROR_CLUSTER_NEAR_EVENT=false

DIRECT_RECOVERY_WINDOW_SECONDS=150
DIRECT_RECOVERY_PING_SAMPLE_COUNT=25
DIRECT_RECOVERY_PING_SUCCESS_COUNT=0
DIRECT_RECOVERY_NEIGHBOR_STATE=INCOMPLETE_FOR_ALL_25_SAMPLES

BOARD_B_USB_ENUMERATION_LAST_OBSERVED=PASS
LOCAL_SERIAL_OWNER_LAST_OBSERVED=0

ESPHOME_2026_4_3_WIFI_SCAN_FALLBACK_MS=31000
ESPHOME_2026_4_3_WIFI_CONNECT_FALLBACK_MS=46000
SEQUENTIAL_WIFI_FALLBACK_MS=77000

NO_RELAY_WIFI_RECOVERY_BUDGET_MS=85000
NO_RELAY_ABSOLUTE_RECOVERY_BUDGET_MS=120000
HEALTHY_RELAY_ABSOLUTE_RECOVERY_BUDGET_MS=30000
MQTT_RECOVERY_BUDGET_MS=25000
DIRECT_CONFIRM_BUDGET_MS=5000
```

```text
INFERENCE_PHYSICAL_SYMPTOM_MATCHES_CONFIRMED_SOURCE_DEFECT=true
INFERENCE_UNIQUE_PHYSICAL_CAUSATION=NOT_PROVEN
```

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=2
CURRENT_BLOCKER_1=No exact artifact exists for current repaired HEAD 4270f24
CURRENT_BLOCKER_2=Current repaired HEAD has not been physically revalidated on Board B

ROOT_CAUSE=SOURCE_LEVEL_WIFI_RECOVERY_BUDGET_INTEGRATION_DEFECT_CONFIRMED; unique mapping to the observed Board-B stall remains unproven until repaired physical validation
PROVEN_BY=ESPHome 2026.4.3 source timing + PR437 exact-source review + Board-B/T1/LAN/USB read-only evidence
SOURCE_DEFECT_PROVEN=true
RUNTIME_DEFECT_PROVEN=true
RUNTIME_ROOT_CAUSE_UNIQUE=false
```

Two source-review blockers from intermediate HEAD `164def447...` are closed:

```text
SR-B1_50S_WIFI_PHASE_TOO_SHORT=CLOSED_BY_SOURCE
SR-B2_HEALTHY_RELAY_90S_OWNERSHIP_EXPANSION=CLOSED_BY_SOURCE
```

---

## 7. Closed / Forbidden Routes

```text
BROKER_OR_MANAGER_GLOBAL_OUTAGE_AS_CURRENT_CAUSE=CLOSED:not supported by event-window continuity evidence
DYNSEC_ACL_AS_CURRENT_CAUSE=CLOSED:expected role/publish ACL present and no exact-client auth/ACL failure observed
REWRITE_OLD_177468E_ARTIFACT=CLOSED:current route requires new artifact from repaired head
REUSE_PRIOR_BOARD_WRITE_AUTHORIZATION=CLOSED:consumed one-shot authorization
AUTO_MERGE_PR437=CLOSED:not merge-ready and not authorized
```

Do not claim Board power loss, application hang, changed DHCP address, or Wi-Fi enable-call absence as proven; those remain unproven alternatives in the old deployed runtime.

---

## 8. Authorization Ledger

```text
AUTHORIZATION=PR437 prior one-shot Board B application write
CLAIMED=true
CONSUMED=true
RESULT=application write/readback succeeded; postwrite OTA-data verifier stopped on an invalid post-boot byte-equality oracle
REPLAY_PERMITTED=false
SUPERSEDED_BY=none
```

```text
PROPOSED_AUTHORIZATION=FUTURE_BOARD_B_REFLASH_WITH_4270F24_EXACT_ARTIFACT
GRANTED=false
```

The next gate is GitHub/build-only and does not consume or imply physical Board authorization.

---

## 9. Rollback Authority

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:NO_LIVE_OR_BOARD_MUTATION_IN_NEXT_GATE
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_PR437_4270F24_EXACT_ARTIFACT_BUILD_AND_BINDING_PREPARATION_20260921_01
```

### Purpose

- Freshly bind the build input to exact PR #437 HEAD/tree and target config.
- Prepare a build-only workflow/branch/package that cannot silently build another revision.
- Define artifact hash/binding checks before any build result can become a Board candidate.
- This gate does not build/flash Board B and cannot prove the physical recovery defect fixed.

### Inputs

```text
INPUT_1=PR437_HEAD_4270f24a92a87dd5239d781ebba624c2f34b7fc2
INPUT_2=PR437_TREE_a2f445bf2ea60ba9994a7a467f6492975d399c4f
INPUT_3=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
INPUT_4=CURRENT_HEAD_CI_11_OF_11_PASS
```

### Operations

```text
1. Fresh read-only rebind main, PR437 state/head/tree, target config blob and current-head CI.
2. Prepare a build-only branch/workflow/package whose source parent is exact 4270f24.
3. Freeze expected source head/tree/config blob and toolchain identity in the build manifest.
4. Verify changed-file scope is build/documentation only; no product-source edits.
5. Stop and report the exact preparation commit/branch and the build command/workflow to use in the next gate.
```

### PASS / FAIL / STOP

```text
PASS_IF=exact source/head/tree/config are bound and build preparation is reproducible, public-safe, and product-source-clean
FAIL_IF=any source/ref/config mismatch, unexpected product-source change, unsafe secret/private locator exposure, or build preparation cannot bind exact source
STOP_BOUNDARY=after preparation verification; do not trigger Board flash/reset/NVS and do not merge PR437

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
- GitHub read-only rebind of main / PR437 / commits / trees / CI
- create/update a purpose-specific build-only branch or workflow/package
- static review of build manifest and changed-file scope
- public-safe documentation/evidence updates
```

### FORBIDDEN

```text
- Board B serial open, reset, flash, OTA-data write, NVS write or erase
- T1/Broker/Manager/Home Assistant runtime mutation
- credential/DynSec/security lifecycle mutation
- PR437 merge, auto-merge, rebase or base rewrite
- reuse of any consumed Board authorization
- treating a source rebuild as physically accepted before physical validation
```

---

## 12. Execution Contract

```text
EXECUTOR=TO_BE_PREPARED_IN_NEXT_GATE
EXECUTION_METHOD=chat-tool
DIRECT_CODE_SUPPLIED=false
DSL_COMPILATION_USED=false
```

GitHub operations remain phased and short. Stop at the first source-binding or changed-file mismatch.

---

## 13. Expected Closure

```text
=== N3W_PR437_4270F24_EXACT_ARTIFACT_BUILD_AND_BINDING_PREPARATION_20260921_01 CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=GITHUB_BUILD_PREPARATION_ONLY
AUTHORIZATION_CLAIMED=NOT_APPLICABLE
AUTHORIZATION_CONSUMED=NOT_APPLICABLE

FRESH_MAIN=
PR437_HEAD=
PR437_TREE=
TARGET_CONFIG=
TARGET_CONFIG_BLOB=
CURRENT_HEAD_CI=

BUILD_BRANCH=
BUILD_PREPARATION_HEAD=
BUILD_WORKFLOW_OR_EXECUTOR=
PRODUCT_SOURCE_CHANGED=false
PUBLIC_SAFETY_CHECK=

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

PREPARATION_RESULT=
NEXT_ROUTE=
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=N3W_PR437_4270F24_EXACT_ARTIFACT_BUILD_AND_BINDING_EXECUTION_20260921_01
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=false for build execution; separate explicit authorization remains required before any future Board mutation

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true
EXISTING_KF_GUARD_USED=KF-096
NEW_KF_REQUIRED=false
```

PR #447 updates KF-096 back to `OPEN` and adds the Wi-Fi recovery budget integration guard. No new KF number is allocated at this point.

---

## 16. New Chat Start Prompt

默认读取集在 PR #447 合并前应从 PR #447 文档分支读取，而不是假定 main 已包含 working-context 文件。

```text
阅读《docs/development/N3W_PR437_WIFI_RECOVERY_BUDGET_SOURCE_REPAIR_NEW_CHAT_HANDOFF_V1.0_20260921.md》。

同时读取同一文档对齐分支 / PR #447 中：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

然后 fresh rebind：
- repository main
- PR #437 exact head/tree/state
- PR #437 current-head CI

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
支线任务：PR #437 切换过程遥测丢失复核
当前任务：N3W_PR437_4270F24_EXACT_ARTIFACT_BUILD_AND_BINDING_PREPARATION_20260921_01

先做当前 gate 所需的最小 fresh 只读确认，然后只进入：

NEXT_ONE_GATE=N3W_PR437_4270F24_EXACT_ARTIFACT_BUILD_AND_BINDING_PREPARATION_20260921_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

不要重放 consumed authorization，不要重新进入已关闭路线，不要自动刷 Board B，不要 merge PR #437，不要自动跨越下一阶段。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=PR437_WIFI_RECOVERY_BUDGET_SOURCE_REPAIR_EXACT_HEAD_CI_PASS
CURRENT_STOP_POINT=BEFORE_4270F24_EXACT_ARTIFACT_BUILD_PREPARATION
CURRENT_BLOCKER=NO_CURRENT_EXACT_ARTIFACT_AND_NO_CURRENT_HEAD_PHYSICAL_REVALIDATION
LIVE_SYSTEM_STATE=UNKNOWN_FRESH; last read-only evidence had Manager/Broker continuity PASS and Board-B USB enumeration PASS
NEXT_ONE_GATE=N3W_PR437_4270F24_EXACT_ARTIFACT_BUILD_AND_BINDING_PREPARATION_20260921_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.0
HANDOFF_TEMPLATE_VERSION=1.2

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

Public-safe current evidence, source review, known-failure status, and next route are durably recorded in PR #447. Private runtime locators and raw identities remain intentionally outside public GitHub.

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
