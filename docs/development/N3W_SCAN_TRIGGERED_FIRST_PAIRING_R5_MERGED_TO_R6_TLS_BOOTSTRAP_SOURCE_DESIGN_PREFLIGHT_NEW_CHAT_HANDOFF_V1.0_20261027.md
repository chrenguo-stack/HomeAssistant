# 温室环境监测系统（ESP32-C6）
# N3-W 扫描触发首次配对：R5 已合并 → R6 TLS bootstrap source design / preflight
# 新会话交接文档 V1.0 — 2026-10-27

```text
HANDOFF_TEMPLATE_VERSION=1.3
SOLE_VALID_HANDOFF_TEMPLATE_VERSION=1.3
OLDER_HANDOFF_TEMPLATE_VERSIONS=INVALID_FOR_NEW_HANDOFF_GENERATION
HISTORICAL_TEMPLATE_COPIES=HISTORICAL_EVIDENCE_ONLY
HISTORICAL_HANDOFF_STANDARD_DOES_NOT_AUTHORIZE_OLD_TEMPLATE=true
PROJECT_WORKING_CONTEXT_VERSION=1.1
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB

HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
HANDOFF_STANDARD_PATH=docs/development/NEW_CHAT_HANDOFF_STANDARD.md
HANDOFF_TEMPLATE_PATH=docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
HANDOFF_TEMPLATE_BLOB=6ecb74451c4bb35f57c8003ee15fbdf65f7dad15
```

> 本文只保存当前阶段增量。长期工作规则统一引用
> `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`。
> historical handoff standard authority 只提供 process/standard 规则；新 handoff 始终使用当前 V1.3 template。
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并先停止执行。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=SCAN_TRIGGERED_FIRST_PAIRING_R5_MERGED_TO_R6_ENTRY
CURRENT_STOP_POINT=R5_MERGED_AND_GITHUB_STATE_SYNC_PREPARED_BEFORE_R6
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R6_TLS_BOOTSTRAP_SOURCE_DESIGN_AND_PREFLIGHT_20261027_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

PR #694 R5 已按 exact reviewed head 合并。当前会话在 R6 产品源码实现前停止。
新会话先 fresh rebind 合并后的仓库和 R6 相关源码，只进入 R6 TLS bootstrap source design / preflight。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.1
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=1
STAGE_OVERRIDES=
1) EXECUTABLE_SOURCE_AUTHORITY 固定为 R5 merge commit 32c4eef68bce48ff7a379381ab0bfad60557ef57；本 handoff/current-state 同步属于 docs-only advancement，不得误判为 R6 executable source drift。
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=用户扫描节点QR→节点bounded发现T1→用户确认选中的T1→节点TLS pinning后自动交接Setup Secret→identity-bound first-registration transaction→existing simplified pairing→durable commit→正常运行

FINAL_ACCEPTANCE_TARGET=按冻结顺序完成R6_TLS_BOOTSTRAP→R7_LCD_UX→R8_SIMULATED_E2E→R9_EXACT_ARTIFACT_AND_INDEPENDENT_REVIEW→再单独授权R10_PHYSICAL_ACCEPTANCE

DEFERRED_OR_OUT_OF_SCOPE=R7_LCD_FULL_STATE_ERROR_MAPPING;R8_FULL_SIMULATED_E2E;R9_EXACT_ARTIFACT;R10_T1_BOARD_PHYSICAL_ACCEPTANCE
```

---

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant

MAIN=32c4eef68bce48ff7a379381ab0bfad60557ef57
TREE=303378f5cffef4e4f1f71881b1955baed5b7d220
MAIN_ROLE=LAST_EXECUTABLE_SOURCE_MAIN_AFTER_R5_MERGE

CANDIDATE_REF=docs/n3w-r5-postmerge-r6-handoff-20261027
CANDIDATE_HEAD=a5fe7740d865806d71bf3bb38bd81a9c717845a5
CANDIDATE_TREE=185153b564577e05479978c21672241aab8bdb3d
CANDIDATE_ROLE=DOCS_ONLY_CURRENT_STATE_AND_INDEX_ALIGNMENT_BEFORE_HANDOFF_FILE_COMMIT

ARTIFACT_ID=NOT_APPLICABLE:R6_SOURCE_DESIGN_PREFLIGHT
ARTIFACT_SHA256=NOT_APPLICABLE:R6_SOURCE_DESIGN_PREFLIGHT

DEPLOYED_SOURCE_HEAD=NOT_APPLICABLE:NO_LIVE_DEPLOYMENT_IN_R4_R5_SOURCE_GATES
DEPLOYED_SOURCE_TREE=NOT_APPLICABLE:NO_LIVE_DEPLOYMENT_IN_R4_R5_SOURCE_GATES

OTHER_REQUIRED_AUTHORITY=
docs/adr/0011-n3w-scan-triggered-first-registration.md;
docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026.md;
docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_R5_DISCOVERY_AND_MULTI_T1_SELECTION_SOURCE_DESIGN_AND_PREFLIGHT_20261027.md;
docs/development/N3W_CURRENT_STATE.md;
docs/development/N3W_CURRENT_STATE_INDEX.md;
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
```

R3/R4/R5 exact merge lineage:

```text
PR692_R3_STATE=MERGED
PR692_R3_MERGE_COMMIT=336835454211257f997d86d9c2f3208acbd7c03f

PR693_R4_STATE=MERGED
PR693_R4_FINAL_HEAD=ac787092f3a063c39d63580f562ac600f07aafae
PR693_R4_MERGE_COMMIT=1ae096f334b7c0b19800bdec02a2c63d6166ec08

PR694_R5_STATE=MERGED
PR694_R5_FINAL_HEAD=86501708eb17e3f946bb7a2abcd783db5fc3b041
PR694_R5_FINAL_CI=16_OF_16_SUCCESS
PR694_R5_SOURCE_REVIEW=PASS
PR694_R5_MERGE_COMMIT=32c4eef68bce48ff7a379381ab0bfad60557ef57
```

本 handoff 文件本身会在 `a5fe7740...` 之后再产生一个 docs-only commit；
新会话必须 fresh rebind current main，不能把上面的 docs candidate head 当作最终 main。

---

## 4. Current Live Baseline

本阶段没有 fresh 访问 T1、Broker、Home Assistant 或板卡，不得把历史现场状态冒充当前状态。

```text
MANAGER_STATE=UNKNOWN_FRESH
MANAGER_RESTART_STATE=UNKNOWN_FRESH
BROKER_STATE=UNKNOWN_FRESH
HOMEASSISTANT_STATE=UNKNOWN_FRESH

BOARD_A_POWER_STATE=UNKNOWN_FRESH
BOARD_A_LOCATION_ROLE=UNKNOWN_FRESH
BOARD_B_POWER_STATE=UNKNOWN_FRESH
BOARD_B_LOCATION_ROLE=UNKNOWN_FRESH

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false

LIVE_STATE_REQUIRES_FRESH_READONLY_RECHECK_ONLY_IF_R6_GATE_LATER_REQUIRES_LIVE_EVIDENCE=true
```

R6 source-design/preflight 不需要为了“确认现场”主动访问 T1 或板卡。

---

## 5. Proven Current Facts

```text
FACT_1=R3_IDENTITY_BOUND_TRANSACTION_WINDOW_SOURCE_IS_MERGED
FACT_2=R4_NODE_LOCAL_REGISTRATION_PORTAL_AND_PRODUCT_QR_SOURCE_IS_MERGED
FACT_3=R5_SCAN_TRIGGERED_T1_DISCOVERY_AND_MULTI_T1_SELECTION_SOURCE_IS_MERGED
FACT_4=R5_FINAL_HEAD_86501708_PASSED_16_OF_16_LATEST_HEAD_CI
FACT_5=R5_FOCUSED_SOURCE_REVIEW_PASS_WITH_ZERO_NEW_BLOCKERS
FACT_6=UNREGISTERED_IDLE_PRODUCT_PATH_DOES_NOT_RUN_NORMAL_REGISTRATION_DISCOVERY
FACT_7=R5_DISCOVERY_IS_MDNS_GREENHOUSE_REG_FIRST_AND_UDP47111_FALLBACK_ONLY
FACT_8=R5_RETAINS_AT_MOST_FOUR_DEDUPED_CANDIDATES_AND_NEVER_AUTO_SELECTS_MULTIPLE_T1S
FACT_9=R5_BROWSER_EXPOSES_ONLY_FRIENDLY_NODE_SUFFIX_OPAQUE_CANDIDATE_ID_AND_PRODUCT_SAFE_T1_LABEL
FACT_10=R5_DISCOVERY_SESSION_BINDS_CURRENT_PAIRING_ID_AND_SELECTION_RECHECKS_IT
FACT_11=R5_SELECTED_FULL_CANDIDATE_IS_RAM_ONLY_FOR_R6
FACT_12=R5_CONFIRM_STOPS_AT_BOOTSTRAP_STAGE_PENDING_AND_DOES_NOT_CALL_47110_OR_SEND_SETUP_SECRET
FACT_13=PENDING_FINAL_ACK_RECOVERY_REMAINS_A_SEPARATE_HIGHER_PRIORITY_PATH
FACT_14=R6_NODE_TO_T1_TLS_BOOTSTRAP_IS_NOT_IMPLEMENTED_BY_R5
FACT_15=NO_T1_BOARD_FLASH_NVS_OR_LIVE_RUNTIME_MUTATION_OCCURRED_IN_R4_R5_SOURCE_CLOSURE
```

下一步需要 fresh 源码确认、不能直接假定：

```text
INFERENCE_R6_EXACT_REUSE_BOUNDARY=TO_BE_PROVEN_FROM_CURRENT_MAIN
INFERENCE_CURRENT_47110_NODE_CLIENT_CAPABILITY=TO_BE_PROVEN_FROM_CURRENT_MAIN
INFERENCE_SIMPLE_PAIRING_CLIENT_MINIMAL_SAFE_REFACTOR=TO_BE_PROVEN_FROM_CURRENT_MAIN
```

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=0
CURRENT_BLOCKER=NONE:R6_SOURCE_DESIGN_PREFLIGHT_IS_NEXT_STAGE_NOT_A_BLOCKER
ROOT_CAUSE=NOT_APPLICABLE
PROVEN_BY=PR694_FINAL_SOURCE_REVIEW_PLUS_16_OF_16_CI_PLUS_POSTMERGE_PARENT_CHECK
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
```

---

## 7. Closed / Forbidden Routes

```text
IDLE_BACKGROUND_T1_DISCOVERY=CLOSED:FROZEN_SCAN_TRIGGERED_PRODUCT_DESIGN
RAW_GHN3W2_OR_SETUP_SECRET_IN_QR_OR_PHONE=CLOSED:R4_R5_PRODUCT_SECURITY_BOUNDARY
PHONE_TO_T1_DIRECT_BOOTSTRAP=CLOSED:NODE_OWNS_T1_BOOTSTRAP
MULTI_T1_AUTOMATIC_RANKING_OR_SELECTION=CLOSED:R5_EXPLICIT_USER_SELECTION
APPLICATION_LAYER_X25519_REINTRODUCTION=CLOSED:ADR0007_HMAC_HKDF_PATH_REUSED
R6_IMPLEMENTATION_BEFORE_R6_SOURCE_DESIGN_PREFLIGHT=CLOSED:NEXT_GATE_IS_DESIGN_PREFLIGHT_ONLY
REOPEN_R5_DISCOVERY_AS_LEGACY_SIMPLEPAIRINGCLIENT_RUN_ONCE_DISCOVERY=CLOSED:R5_OWNS_NORMAL_DISCOVERY
WHOLE_NVS_RESET_ON_TERMINAL_PAIRING=CLOSED:ADR0008_DURABLE_RENEWAL_ONLY
```

---

## 8. Authorization Ledger

已消费的授权：

```text
AUTHORIZATION=USER_AUTHORIZED_PR694_MERGE_AND_POSTMERGE_GITHUB_SYNC
CLAIMED=true
CONSUMED=true
RESULT=PR694_MERGED_AND_DOCS_SYNC_PREPARED
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE
```

下一 gate：

```text
PROPOSED_AUTHORIZATION=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R6_TLS_BOOTSTRAP_SOURCE_DESIGN_AND_PREFLIGHT_20261027_01
GRANTED=true:USER_EXPLICITLY_DIRECTED_R6_TO_CONTINUE_IN_NEW_CHAT
AUTHORIZATION_SCOPE=SOURCE_READONLY_REBIND_PLUS_DOCS_ONLY_DESIGN_PREFLIGHT
LIVE_T1_BOARD_FLASH_NVS_MUTATION_AUTHORIZED=false
SOURCE_IMPLEMENTATION_AUTHORIZED=false
MERGE_AUTHORIZED=false
```

---

## 9. Rollback Authority

下一 gate 是 source design / preflight，不做产品源码或 live mutation。

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_SOURCE_REBIND_PLUS_DOCS_ONLY_DESIGN_GATE
```

如新会话发现必须先修 R5/R3 已合并源码才能设计 R6，应 STOP 并重新分类，不能在本 gate 隐式扩大成 source-repair gate。

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R6_TLS_BOOTSTRAP_SOURCE_DESIGN_AND_PREFLIGHT_20261027_01
```

### Purpose

这一步要冻结 R6 的 exact 实现边界：

- 从 R5 已选中的 RAM candidate 到节点→T1 47110 TLS bootstrap；
- 在发送 Setup Secret 前严格 pin 用户所选 candidate 的 `bootstrap_tls_sha256`；
- 复用现有 T1 `gh.registration.confirm/1` / first-registration transaction，不重新设计第二套 bootstrap；
- 成功确认后消费 T1 返回的 exact 47112 locator / deadline；
- 把普通配对流程从 legacy `run_once()->discover_()` 拆成针对已确认 candidate 的显式阶段；
- 保留现有 HMAC Setup Secret proof、HKDF、加密 credential delivery、final delivery digest ACK；
- 明确 terminal expiry / replay / Manager-restart invalidation 后的 ADR-0008 pairing-ID renewal；
- 明确 ACK_PENDING/TERMINAL_CLEANUP 的 47110 status recovery；
- 不把 R7 LCD、R8 E2E、R9 artifact 或 R10 physical acceptance 偷渡进 R6。

这一步不能证明：

- R6 产品源码已经实现；
- 真实 T1 47110/TLS 已现场验证；
- Setup Secret 已真实发送；
- 真实板卡已完成首次注册；
- R7/R8/R9/R10 已完成。

### Inputs

```text
INPUT_1=FRESH_CURRENT_MAIN_AFTER_DOCS_SYNC
INPUT_2=EXECUTABLE_SOURCE_MAIN_32c4eef68bce48ff7a379381ab0bfad60557ef57
INPUT_3=ADR0011_SCAN_TRIGGERED_FIRST_REGISTRATION
INPUT_4=N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026
INPUT_5=PR694_R5_MERGED_SOURCE
INPUT_6=CURRENT_NODE_REGISTRATION_PORTAL_DISCOVERY_AND_SIMPLE_PAIRING_CLIENT_SOURCE
INPUT_7=CURRENT_T1_REGISTRATION_BOOTSTRAP_LEDGER_WINDOW_STATUS_SOURCE
```

### Operations

```text
1. fresh rebind repository main; confirm docs-only advancement after 32c4eef6 does not change executable R5 product bytes.
2. confirm PR #694 remains merged and re-read the exact R5 source now present on main.
3. read ADR-0011 and the frozen source-design sections covering Setup Secret handoff, identity-bound 47112, pending-ACK recovery, pairing-client refactor, terminal renewal and error/QR renewal semantics.
4. inspect current node source:
   - n3w_registration_discovery.*
   - n3w_registration_portal.*
   - n3w_simple_product_component.*
   - n3w_simple_pairing_client.*
   - pending ACK / setup-secret / pairing-intent persistence.
5. inspect current T1 source for 47110 confirm/status, first-registration intent/ledger, identity/source-bound 47112 window and terminal result semantics.
6. prove the exact existing request/response schemas from source; do not invent or silently widen them.
7. freeze node TLS client behavior:
   - endpoint comes only from the selected R5 candidate;
   - certificate leaf SHA-256 must match the selected candidate before Setup Secret bytes are sent;
   - redirects / endpoint substitution / unauthenticated fallback are fail-closed;
   - browser remains uninvolved.
8. freeze bootstrap success behavior:
   - accepted 47110 response yields only the exact 47112 locator/deadline/transaction data required by the existing pairing path;
   - R6 must not create a second discovery step after user selection.
9. freeze busy/failure semantics:
   - pre-transaction discovery/bootstrap failure keeps current pairing ID and QR;
   - registration_busy keeps pre-transaction identity and allows later retry;
   - active transaction retry stays inside the same absolute 1800-second deadline;
   - expired/replay/restart-invalidated terminal identity follows ADR-0008 durable pairing-ID renewal and QR refresh;
   - no whole-NVS reset.
10. freeze SimplePairingClient refactor boundaries, conceptually preserving:
   - prepare_bootstrap()
   - pair_with_candidate(...)
   - resume_pending_ack()
   - recover_pending_ack_status()
   - resume_terminal_cleanup()
   while preserving the proven pairing cryptographic/provisioning protocol.
11. define bounded source tests, host tests, ESP32-C6 compile gates and false-PASS guards for R6.
12. write the R6 stage-specific source design/preflight document and, if useful, a Draft docs-only PR.
13. perform focused design review against current source.
14. STOP before R6 product-source implementation.
```

### PASS / FAIL / STOP

```text
PASS_IF=R6_REUSE_BOUNDARY_EXACT_AND_TLS_PINNING_CONTRACT_EXACT_AND_47110_47112_SCHEMAS_SOURCE_PROVEN_AND_TERMINAL_RENEWAL_SEMANTICS_EXACT_AND_SIMPLEPAIRINGCLIENT_REFACTOR_BOUNDED_AND_TEST_PLAN_COMPLETE_AND_NEW_DESIGN_BLOCKER_COUNT_0

FAIL_IF=47110_OR_47112_CONTRACT_CANNOT_BE_PROVEN_OR_TLS_PINNING_REQUIRES_UNFROZEN_SECURITY_CHOICE_OR_R6_WOULD_WEAKEN_EXISTING_PAIRING_INVARIANTS_OR_SOURCE_HAS_UNRESOLVED_R3_R4_R5_CONTRADICTION

STOP_BOUNDARY=R6_SOURCE_IMPLEMENTATION_ENTRY

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
- fresh GitHub main/commit/file/PR read-only rebind
- current merged R3/R4/R5 source inspection
- current T1 registration source inspection
- exact schema and state-machine comparison
- R6 source-design reasoning and source-test plan
- docs-only R6 design/preflight file creation
- docs-only Draft PR if required by repository rules
- docs-only CI observation
```

### FORBIDDEN

```text
- R6 firmware/T1 product-source implementation
- changing 47110/47111/47112 runtime behavior
- transmitting Setup Secret
- accessing or mutating live T1
- board access
- flash/NVS mutation
- live service start/restart
- credential/DynSec mutation
- source implementation PR merge
- R7 LCD implementation
- R8 simulated E2E execution
- R9 artifact production
- R10 physical acceptance
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
BOUNDED_WRITE_SCOPE=NOT_APPLICABLE
```

---

## 12. Execution Contract

```text
EXECUTOR=CHATGPT_GITHUB_CONNECTOR
EXECUTION_METHOD=chat-tool
DIRECT_CODE_SUPPLIED=false
DSL_COMPILATION_USED=false
CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=true
```

本 gate 仅允许 docs/design 级小修。若发现需要修改产品源码才能消除 substantive contradiction，应 STOP，不得把 design/preflight 自动升级成 implementation/source-repair。

---

## 13. Expected Closure

```text
=== N3W_SCAN_TRIGGERED_FIRST_PAIRING_R6_TLS_BOOTSTRAP_SOURCE_DESIGN_AND_PREFLIGHT_20261027_01 CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=USER_DIRECTED_R6_NEW_CHAT_CONTINUATION
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=

FRESH_MAIN=
EXECUTABLE_SOURCE_ANCESTOR_32C4EE=PASS|FAIL
R5_SOURCE_DRIFT_AFTER_MERGE=NONE|<details>

R6_47110_CONFIRM_SCHEMA_SOURCE_PROVEN=
R6_47110_STATUS_SCHEMA_SOURCE_PROVEN=
R6_SELECTED_CANDIDATE_TLS_PINNING_CONTRACT=
R6_SETUP_SECRET_PHONE_EXPOSURE=NONE
R6_REDIRECT_OR_ENDPOINT_SUBSTITUTION_POLICY=
R6_47112_LOCATOR_DEADLINE_HANDOFF=
R6_SIMPLEPAIRINGCLIENT_REFACTOR_BOUNDARY=
R6_PRETRANSACTION_FAILURE_IDENTITY_POLICY=
R6_ACTIVE_TRANSACTION_RETRY_POLICY=
R6_TERMINAL_RENEWAL_POLICY=
R6_PENDING_ACK_STATUS_RECOVERY_POLICY=
R6_TEST_AND_CI_PLAN=
NEW_DESIGN_BLOCKER_COUNT=
NEW_FALSE_PASS_PATH_COUNT=

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

R6_DESIGN_PREFLIGHT=
R6_SOURCE_IMPLEMENTATION_READY=
SOURCE_IMPLEMENTATION=false
MERGE=false
NEXT_ROUTE=R6_SOURCE_IMPLEMENTATION_ENTRY
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R6_TLS_BOOTSTRAP_SOURCE_IMPLEMENTATION
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=R6_SOURCE_IMPLEMENTATION_ENTRY

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

同一 design gate 内的文档错字、错误引用、测试计划表达等低风险问题可直接修；
涉及产品协议、安全边界、R3/R4/R5 merged source repair 的问题必须停止并重新分类。

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
EXISTING_KF_GUARD_USED=KF060_OWNERSHIP_PROOF_AND_EXISTING_ADR0008_REPLAY_TERMINAL_GUARDS_AS_RELEVANT
NEW_KF_REQUIRED=false
```

R5 CI 过程中出现的 lwIP include、source-test brittle assertion 和 shared mDNS AUTO_LOAD 问题均已在 PR #694 同 gate 修复并回归保护，不需要新开 KF。

---

## 16. New Chat Start Prompt

默认读取集：

```text
1. 本 handoff
2. docs/development/N3W_PROJECT_WORKING_CONTEXT.md
3. docs/development/N3W_CURRENT_STATE.md
4. docs/development/N3W_CURRENT_STATE_INDEX.md
5. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
6. exact historical handoff standard authority 4300890dff0ce63d5a547df21426e287d084d9ee（只读取 standard/process，不使用旧 template）
```

建议启动文本：

```text
阅读《N3W_SCAN_TRIGGERED_FIRST_PAIRING_R5_MERGED_TO_R6_TLS_BOOTSTRAP_SOURCE_DESIGN_PREFLIGHT_NEW_CHAT_HANDOFF_V1.0_20261027.md》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/adr/0011-n3w-scan-triggered-first-registration.md
- docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026.md
- docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_R5_DISCOVERY_AND_MULTI_T1_SELECTION_SOURCE_DESIGN_AND_PREFLIGHT_20261027.md

历史 handoff standard authority：
4300890dff0ce63d5a547df21426e287d084d9ee
只读取其中 NEW_CHAT_HANDOFF_STANDARD.md 的 process/standard 规则；
formal handoff template 继续使用 current main 的 V1.3，不回退旧模板。

并 fresh rebind：
- repository main
- PR #694 状态与 merge commit
- executable/source main lineage from 32c4eef68bce48ff7a379381ab0bfad60557ef57
- current R5 node registration source
- current SimplePairingClient / pending-ACK source
- current T1 47110/47112 first-registration source

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3-W 扫描触发首次配对收口
当前任务：R6 TLS bootstrap source design / preflight

先做当前 gate 所需的最小 fresh 只读确认，然后只进入：

NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R6_TLS_BOOTSTRAP_SOURCE_DESIGN_AND_PREFLIGHT_20261027_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
SOURCE_IMPLEMENTATION=false
MERGE=false

必须先承认：
- R3/R4/R5 已合并；
- R5 final reviewed head=86501708eb17e3f946bb7a2abcd783db5fc3b041；
- R5 merge/source main=32c4eef68bce48ff7a379381ab0bfad60557ef57；
- R5 final CI=16/16 SUCCESS；
- idle 未注册节点不主动发现 T1；
- R5 已完成扫码触发发现和多 T1 明确选择；
- selected full candidate 仅在节点 RAM 中；
- R5 confirm 仍停在 bootstrap_stage_pending；
- R6 尚未实现 47110 TLS bootstrap / Setup Secret handoff；
- 手机不得接触 Setup Secret；
- R6 必须 pin 用户所选 candidate 的 TLS fingerprint 后才允许发送 Setup Secret；
- R6 必须复用既有 pairing HMAC/HKDF/credential delivery/final ACK 逻辑，不重建第二套配对协议；
- pre-transaction failure 不消费 pairing ID；
- terminal expiry/replay/restart-invalidated 必须走 ADR-0008 durable renewal；
- pending ACK/status recovery 与 ordinary registration discovery 是不同状态；
- 本 gate 不访问 T1/Board，不做产品源码修改，不自动跨入 R6 implementation。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=SCAN_TRIGGERED_FIRST_PAIRING_R5_MERGED_TO_R6_ENTRY
CURRENT_STOP_POINT=R5_MERGED_AND_GITHUB_STATE_SYNC_BEFORE_R6
CURRENT_BLOCKER=NONE
LIVE_SYSTEM_STATE=UNKNOWN_FRESH_NOT_REQUIRED_FOR_R6_SOURCE_DESIGN_PREFLIGHT
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R6_TLS_BOOTSTRAP_SOURCE_DESIGN_AND_PREFLIGHT_20261027_01

EXECUTABLE_SOURCE_MAIN=32c4eef68bce48ff7a379381ab0bfad60557ef57
R5_FINAL_REVIEWED_HEAD=86501708eb17e3f946bb7a2abcd783db5fc3b041
R5_FINAL_CI=16_OF_16_SUCCESS
R5_MERGED=true
R6_IMPLEMENTED=false

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.1
HANDOFF_TEMPLATE_VERSION=1.3

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

本阶段重要工程事实已进入 GitHub current state/index + 本 formal handoff；
新会话不需要依赖本聊天记录恢复 R5/R6 入口状态。

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.1

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
CI_CONTINUATION_HARD_RULES_PRESENT=PASS
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
