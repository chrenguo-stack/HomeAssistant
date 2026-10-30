# 温室环境监测系统（ESP32-C6）
# N3-W T1 Portable Image Identity / E03 Successor Recovery
# Source Repair 新会话交接文档 V1.0 — 2026-10-30

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
```

> 本文只保存当前阶段增量。长期工作规则统一引用
> `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`。
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并先停止执行。
> 本文是公开 GitHub handoff，不包含私有 SSH 地址、私网地址、host key、密码、凭据或原始设备身份。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_P0
CURRENT_STOP_POINT=P0_DESIGN_FROZEN_GITHUB_ALIGNED_BEFORE_SOURCE_REPAIR
NEXT_ONE_GATE=N3W_T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_SOURCE_REPAIR_20261030_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

当前会话已经完成：

- 当前 E03 postclaim false STOP 的根因取证；
- Astra 独立架构复核；
- Portable Image Identity V1 / Maintenance Transaction V1 / E03 Successor Recovery V1 设计冻结；
- KF-132～KF-136 正式登记；
- current state/index 对齐；
- docs-only PR #739 建立。

下一会话从源码修复开始，不再在本会话继续扩展上下文。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.1
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=4
STAGE_OVERRIDES=
1) CURRENT_STAGE_AUTHORITY 不在 main 顶部；当前 exact 链为 main -> PR725 -> PR739，必须 fresh rebind 三者。
2) OLD_E03_AUTHORIZATION 已永久 consumed/no-replay；后续不得通过修改旧 executor 续跑旧 transaction。
3) 当前 E03 recovery 明确采用新的、单独授权的 successor transaction；旧 transaction 只作 immutable predecessor evidence。
4) ADR-0010 已退役 Golden Master / Final Seal / clone production；不得因 portable identity 收敛而复活该路线。
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=每台T1官方Armbian独立安装与firstboot→repository-owned自动产品部署→显式产品provisioning→正常运行→后续app维护通过可恢复transaction执行

CURRENT_MAINTENANCE_TARGET=一个版本化release合同＋一个Portable Image Identity公共校验内核＋一个小型可恢复的主机维护transaction入口＋既有systemd/Compose owner

FINAL_ACCEPTANCE_TARGET=普通用户只看到“准备升级/正在升级/升级成功/升级未完成原版本继续运行”；内部能够证明artifact、candidate、cutover、MQTT、状态协调与rollback

DEFERRED_OR_OUT_OF_SCOPE=全仓历史executor一次性重写;Docker大版本升级;Armbian升级;GoldenMaster/clone生产;A/B rootfs;通用编排平台;live E03 recovery
```

---

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant

MAIN=2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e
MAIN_TREE=3064ab74ac96bbce44a0bf880ab53c7afc5bc134
MAIN_ROLE=R5_DOCS_ALIGNMENT_ONLY_NOT_CURRENT_R10_OR_P0_AUTHORITY

PR725_STATE=OPEN_DRAFT
PR725_HEAD=614c08a397462850f0167b77c9da45ae69a323ad
PR725_TREE=9fb33d6ca3e0d665e45924229048b3b502091ccc
PR725_ROLE=R10_E03_PRODUCT_SOURCE_AND_LIVE_EVIDENCE_AUTHORITY

CANDIDATE_REF=design/n3w-t1-portable-image-identity-e03-successor-20261030
CANDIDATE_HEAD_BEFORE_HANDOFF=9f0b6d7f50af565406150d64ba6e57aa307deeab
CANDIDATE_ROLE=PR739_DOCS_ONLY_P0_DESIGN_CURRENT_STATE_AND_HANDOFF
CANDIDATE_FINAL_HEAD_REQUIRES_FRESH_REBIND=true

PR739_STATE=OPEN_DRAFT
PR739_BASE=fix/n3w-r10-phone-centric-pairing-ui-lcd-cycle-20261029
PR739_BASE_SHA=614c08a397462850f0167b77c9da45ae69a323ad
PR739_AHEAD_OF_PR725_BEFORE_HANDOFF=5
PR739_BEHIND_PR725=0
PR739_PRODUCT_SOURCE_CHANGES=0
PR739_WORKFLOW_CHANGES=0

TARGET_MANAGER_SOURCE_HEAD=f8876fd87165df731d792690a8288867c3eeef55
ARTIFACT_RUN_ID=40880705472
ARTIFACT_ID=12900601779
ARTIFACT_SHA256=c94568f740b911eee0f4238207249b1e98f84748c17a902938ccc35293e4b183
MANAGER_TAR_SHA256=d129a33ea628d8bdd1361e0b1bf727175515b4a2afc1851e6ac14ec510895fb5

DEPLOYED_SOURCE_HEAD=UNKNOWN_FRESH
DEPLOYED_SOURCE_TREE=UNKNOWN_FRESH

OTHER_REQUIRED_AUTHORITY=
docs/adr/0010-t1-per-device-fresh-armbian-automated-product-deployment.md;
docs/development/N3W_T1_MAINTENANCE_IDENTITY_REVIEW_20261030.md;
docs/development/N3W_T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_SOURCE_DESIGN_FREEZE_20261030.md;
docs/development/N3W_CURRENT_STATE.md;
docs/development/N3W_CURRENT_STATE_INDEX.md;
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md;
tools/n3w_t1_production_v2_contract.py;
tools/n3w_t1_fresh_product_bootstrap.py;
tools/execution_packages/n3w/kf098/t1_live_cutover/remote_cutover.py;
tools/n3w_t1_r10_e03_manager_successor_refresh_live.py
```

说明：

- main 当前不是 R10/P0 最新状态，不能只读 main 后宣称“当前项目仍在 R5”；
- PR #725 是当前 R10/E03 产品源码和现场证据 authority；
- PR #739 只推进设计、KF、current state/index 和 handoff，不含产品源码修改；
- handoff 提交本身会使 PR #739 HEAD 再前进，新会话必须 fresh rebind，不能把 `9f0b6d7...` 当最终 HEAD。

---

## 4. Current Live Baseline

本次最终对齐阶段没有 fresh 访问 T1、Broker、Home Assistant 或板卡，因此按模板要求：

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

LIVE_STATE_REQUIRES_FRESH_READONLY_RECHECK=false:SOURCE_REPAIR_GATE_DOES_NOT_REQUIRE_T1
```

最后一次已归档的现场证据仅作历史基线，不冒充当前 fresh state：

```text
LAST_PROVEN_OLD_TRANSACTION_STATUS=CLAIMED
LAST_PROVEN_OLD_TRANSACTION_PHASE=AUTHORIZATION_CLAIMED
LAST_PROVEN_OLD_AUTHORIZATION_CONSUMED=true
LAST_PROVEN_OLD_REPLAY_ALLOWED=false

LAST_PROVEN_PRODUCTION_CUTOVER_OCCURRED=false
LAST_PROVEN_PREDECESSOR_MANAGER_STILL_RUNNING=true
LAST_PROVEN_HOMEASSISTANT_STILL_RUNNING=true
LAST_PROVEN_BROKER_CONTINUITY=true
LAST_PROVEN_E03_COMMIT_CLASSIFICATION=DEFINITELY_NOT_COMMITTED
LAST_PROVEN_E03_REGISTRATION_COUNT=1
LAST_PROVEN_E03_UNRESOLVED_COUNT=1
```

这些状态在未来 live preauthorization 前必须重新只读确认。

---

## 5. Proven Current Facts

```text
FACT_1=ROOT_CAUSE_IS_NOT_ARTIFACT_CORRUPTION
FACT_2=EXACT_MANAGER_TAR_CONFIG_DIGEST_IS_089153FA...
FACT_3=EXACT_MANAGER_TAR_OCI_MANIFEST_DIGEST_IS_7751D483...
FACT_4=T1_CONTAINERD_STORE_LAST_PROVEN_TARGET_TAG_ID_EQUALLED_7751D483...
FACT_5=BUILD_SIDE_SINGLE_DOT_ID_AS_CROSS_HOST_ORACLE_CAUSED_FALSE_STOP
FACT_6=PROJECT_HAS_AT_LEAST_3_FIELD_OCCURRENCES_OF_THIS_CROSS_STORE_FALSE_STOP_PATTERN
FACT_7=CORRECT_CROSS_STORE_RULE_ALREADY_EXISTED_IN_KF098_AND_FRESH_BOOTSTRAP_HISTORY_BUT_WAS_NOT_A_SINGLE_COMMON_AUTHORITY
FACT_8=ASTRA_INDEPENDENT_REVIEW_RAN_46_FOCUSED_TESTS_PASS_AND_FOUND_TWO_ADDITIONAL_ISOLATED_SAFETY_REPRODUCTIONS
FACT_9=PORTABLE_IMAGE_IDENTITY_V1_DESIGN_FROZEN
FACT_10=MAINTENANCE_TRANSACTION_V1_DESIGN_FROZEN
FACT_11=E03_SUCCESSOR_RECOVERY_V1_DESIGN_FROZEN
FACT_12=KF132_THROUGH_KF136_REGISTERED
FACT_13=CURRENT_E03_RECOVERY_CHOICE_IS_NEW_SUCCESSOR_TRANSACTION_NOT_OLD_TRANSACTION_RESUME
FACT_14=ADR0010_RETIRES_GOLDEN_MASTER_FINAL_SEAL_AND_CLONE_PRODUCTION
FACT_15=PR739_INITIAL_DESIGN_HEAD_CI_WAS_11_OF_11_SUCCESS
FACT_16=SOURCE_REPAIR_HAS_NOT_STARTED
FACT_17=NO_T1_BOARD_LIVE_MUTATION_OCCURRED_IN_P0_DESIGN_FREEZE
```

注意：

```text
INFERENCE_CURRENT_T1_STILL_EQUALS_LAST_PROVEN_BASELINE=NOT_PROVEN_FRESH
INFERENCE_SOURCE_REPAIR_CAN_BE_IMPLEMENTED_WITHOUT_NEW_T1_ACCESS=SUPPORTED_BY_SCOPE_BUT_MUST_STILL_FRESH_REBIND_REPOSITORY
```

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=5

CURRENT_BLOCKER_1=KF132:CROSS_IMAGE_STORE_SINGLE_DOT_ID_RELEASE_IDENTITY_FALSE_STOP
CURRENT_BLOCKER_2=KF133:B1_TRANSACTION_AUTHORITY_BINDING_INCOMPLETE
CURRENT_BLOCKER_3=KF134:B2_UNKNOWN_COMPOSE_OVERWRITE_RISK
CURRENT_BLOCKER_4=KF135:B3_CRASH_POWER_LOSS_AND_SERVICE_OWNER_ORDERING_GAP
CURRENT_BLOCKER_5=KF136:B4_MQTT_AND_BUSINESS_ACCEPTANCE_INSUFFICIENT

ROOT_CAUSE=CROSS_HOST_IMAGE_IDENTITY_CONTRACT_ERROR_PLUS_DUPLICATED_VALIDATORS_PLUS_INCOMPLETE_MAINTENANCE_TRANSACTION_BOUNDARIES

PROVEN_BY=
2026-10-11_staging_history;
2026-10-12_fresh_bootstrap_R3_history;
2026-10-30_PR725_live_forensic;
Astra_independent_source_review_and_isolated_reproductions

SOURCE_DEFECT_PROVEN=true
RUNTIME_DEFECT_PROVEN=true:KF132_FALSE_STOP
RUNTIME_OCCURRENCE_PROVEN_FOR_B1_B4=false:B1_B4_ARE_SOURCE_SAFETY_BLOCKERS_NOT_CLAIMS_OF_LIVE_INCIDENT
```

### KF-132

跨 host/store 不再允许把 build-side `docker image inspect .Id` 当唯一 release identity。

### KF-133 / B1

mutation entry 必须重新绑定 exact transaction、authorization、host、release/artifact、executor/module、scope、phase 与现实 prestate。

### KF-134 / B2

Compose 必须执行 before / after / unknown 三态；unknown 永不自动覆盖。

### KF-135 / B3

必须 durable intent + activation gate + stop owner before candidate publish；不能依赖进程内 `candidate_sha/stopped` 或 Python exception 承担断电恢复。

### KF-136 / B4

readiness 与 acceptance 分离；容器 running、端口监听、配置 hash 不能替代 Manager/HA 实际 MQTT 和业务状态验收。

---

## 7. Closed / Forbidden Routes

```text
OLD_E03_AUTHORIZATION_REPLAY=CLOSED:CONSUMED_NO_REPLAY
OLD_E03_TRANSACTION_DIRECT_RESUME_WITH_MODIFIED_EXECUTOR=CLOSED:AUTHORITY_SCOPE_CHANGED_SUCCESSOR_REQUIRED
PRIVATE_R10_ONLY_IMAGE_VALIDATOR=CLOSED:PORTABLE_IDENTITY_MUST_BE_COMMON_MODULE
UNKNOWN_COMPOSE_AUTOMATIC_RESTORE=CLOSED:UNKNOWN_MUST_BLOCK
PUBLISH_CANDIDATE_BEFORE_CONTROLLING_APPLICATION_OWNER=CLOSED:B3
COMMIT_ON_CONTAINER_PORT_CONFIG_HASH_ONLY=CLOSED:B4
GOLDEN_MASTER_CLONE_PRODUCTION_REACTIVATION=CLOSED:ADR0010
MANUAL_SQLITE_E03_CLEANUP=CLOSED:MANAGER_STARTUP_RECONCILIATION_OWNS_E03
APP_UPDATE_IMPLICIT_DOCKER_OR_OS_UPGRADE=CLOSED:LIFECYCLES_SPLIT
FULL_HISTORY_EXECUTOR_BIG_BANG_REWRITE=CLOSED:P0_P5_INCREMENTAL_MIGRATION
```

---

## 8. Authorization Ledger

影响下一步的已消费授权：

```text
AUTHORIZATION=N3W_R10_E03_MANAGER_SUCCESSOR_REFRESH_LIVE_APPLY_20261030_01
CLAIMED=true
CONSUMED=true
RESULT=STOP_POSTCLAIM_AT_AUTHORIZATION_CLAIMED_AFTER_EXACT_CANDIDATE_LOAD
REPLAY_PERMITTED=false
SUPERSEDED_BY=FUTURE_SUCCESSOR_RECOVERY_AUTHORIZATION_NOT_YET_GRANTED
```

设计冻结 Gate：

```text
AUTHORIZATION=N3W_T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_SOURCE_DESIGN_FREEZE_20261030_01
CLAIMED=true
CONSUMED=true
RESULT=CLOSED_PASS_DOCS_ONLY
REPLAY_PERMITTED=false
```

下一 Gate：

```text
PROPOSED_AUTHORIZATION=N3W_T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_SOURCE_REPAIR_20261030_01
GRANTED=false
```

新对话只有用户再次明确同意该 exact NEXT_ONE_GATE 后，才进入源码修改。

---

## 9. Rollback Authority

下一 Gate 是 repository source/test repair，不涉及生产 mutation。

```text
ROLLBACK_AUTHORITY=GIT_BRANCH_ONLY:NO_T1_MUTATION
FRESH_PRECHANGE_REPOSITORY_REBIND_REQUIRED=true
T1_ROLLBACK_AUTHORITY=NOT_APPLICABLE:SOURCE_REPAIR_ONLY
LIVE_SECOND_ATTEMPT_ALLOWED=false
```

source repair 必须在独立 source branch / PR 中进行，不直接把 PR #739 docs branch 变成产品源码 branch，除非 fresh review 明确证明这样更符合现有 stack 结构并先说明原因。

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_SOURCE_REPAIR_20261030_01
```

### Purpose

这一 Gate 要把已冻结的 P0 设计实现成可独立测试、可复核的源码：

1. 一个公共 Portable Image Identity 内核；
2. 一个最小 durable Maintenance Transaction 内核；
3. 一个 E03 successor recovery executor；
4. 修复/封锁旧 R10 executor 的 KF-132～136 路径；
5. 复用/扩展现有 F5 V2 release contract，而不是再建平行 release authority；
6. 建立 regression tests，防止 single-`.Id` 假设第四次回归。

这一 Gate **不能证明**：

- 当前 T1 仍与最后现场基线一致；
- 当前 candidate 仍存在；
- E03 已恢复；
- successor authorization 已获得；
- live recovery 已执行；
- PR 可合并到 main。

### Inputs

```text
INPUT_1=FRESH_MAIN
INPUT_2=FRESH_PR725_HEAD_AND_TREE
INPUT_3=FRESH_PR739_HEAD_AND_DIFF
INPUT_4=N3W_T1_MAINTENANCE_IDENTITY_REVIEW_20261030
INPUT_5=N3W_T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_SOURCE_DESIGN_FREEZE_20261030
INPUT_6=KNOWN_FAILURES_KF132_TO_KF136
INPUT_7=ADR0010
INPUT_8=tools/n3w_t1_production_v2_contract.py
INPUT_9=tools/n3w_t1_fresh_product_bootstrap.py
INPUT_10=tools/execution_packages/n3w/kf098/t1_live_cutover/remote_cutover.py
INPUT_11=tools/n3w_t1_r10_e03_manager_successor_refresh_live.py
INPUT_12=current_focused_tests
```

### Operations

```text
1. fresh rebind main, PR #725, PR #739; confirm PR739 docs-only lineage and no unexpected source drift.
2. read current working context, current state/index, KF-132..136, ADR-0010, Astra review and P0 frozen design.
3. inspect current release producer/consumer paths; prove which existing F5 V2 schema/API should be extended rather than creating a parallel release authority.
4. implement common host-side Portable Image Identity module:
   - pure archive/OCI parser
   - Docker observation adapter
   - VERIFIED/MISMATCH/UNSUPPORTED/UNAVAILABLE verifier
   - no Manager runtime dependency
5. add exact parser safety guards:
   - duplicate members
   - path traversal
   - unsafe links
   - duplicate JSON keys
   - missing blobs
   - digest/size mismatch
   - ambiguous platform
   - unsupported layout
6. implement durable Maintenance Transaction minimal module:
   - PREPARING/READY/APPLYING/VERIFYING/COMMITTED
   - ROLLING_BACK/ROLLED_BACK/BLOCKED/ABORTED
   - authorization/transaction/execution-session separation
   - generation + operation sequence + before/intended-after/observed-after
7. implement B1 guards at every mutation entry.
8. implement B2 before/after/unknown Compose semantics; unknown must not write.
9. implement B3 activation-gate / stop-before-publish / durable recovery ordering suitable for current systemd owner.
10. implement B4 bounded readiness plus strict Manager/HA MQTT/business acceptance using existing proven F4/F5 mechanisms where applicable.
11. implement E03 successor recovery executor on top of common modules:
    - immutable predecessor evidence
    - new transaction path/id
    - no replay of old authorization
    - reuse exact candidate only after portable verification
    - no docker load/tag/rmi when exact candidate already verified
12. ensure old R10 executor cannot become an accidental resume authority after source repair; add explicit regression tests.
13. extend/reuse existing Production V2 release contract with versioned semantics; do not reinterpret old schema in place.
14. add tests for classic/containerd representations, wrong config/manifest/index/platform/RootFS/Config semantics, daemon unavailable vs image missing, wrong transaction binding, unknown Compose, crash/re-entry, MQTT delayed/failed readiness and E03 reconciliation.
15. run focused local/source tests.
16. create source-repair PR on an appropriate branch stacked on current PR #725 product source; keep PR #739 as design/docs authority unless a fresh repository constraint requires another route.
17. observe CI; if heavy CI remains pending, provide direct links rather than repeated polling.
18. perform an independent focused source review of KF-132..136 and false-PASS/false-STOP paths.
19. update GitHub progress/KF status only after exact reviewed source and tests support it.
20. STOP before any T1 access or successor live preauthorization.
```

### PASS / FAIL / STOP

```text
PASS_IF=
PORTABLE_IMAGE_IDENTITY_SOURCE=PASS
AND_TRANSACTION_BINDING_KF133=PASS
AND_UNKNOWN_COMPOSE_KF134=PASS
AND_CRASH_OWNER_KF135=PASS
AND_MQTT_ACCEPTANCE_KF136=PASS
AND_CROSS_STORE_KF132=PASS
AND_SUCCESSOR_RECOVERY_SOURCE=PASS
AND_OLD_AUTHORIZATION_REPLAY_TEST=PASS
AND_PREDECESSOR_IMMUTABILITY_TEST=PASS
AND_NO_PRIVATE_VALIDATOR_REGRESSION=PASS
AND_FOCUSED_TESTS=PASS
AND_APPLICABLE_CI=PASS
AND_INDEPENDENT_SOURCE_REVIEW=PASS
AND_NEW_FALSE_PASS_PATH_COUNT=0
AND_NEW_BLOCKING_FALSE_STOP_PATH_COUNT=0

FAIL_IF=
PORTABLE_IDENTITY_CANNOT_BE_PROVEN_FROM_RELEASE_CONTENT
OR_SUCCESSOR_RECOVERY_REQUIRES_REINTERPRETING_OLD_AUTHORIZATION
OR_UNKNOWN_STATE_CAN_STILL_BE_AUTO_OVERWRITTEN
OR_CRASH_REENTRY_CAN_ESCAPE_BEFORE_AFTER_UNKNOWN_MODEL
OR_COMMIT_CAN_OCCUR_WITHOUT_REAL_MQTT_HEALTH
OR_SOURCE_REPAIR_REQUIRES_REACTIVATING_RETIRED_GOLDEN_MASTER_ROUTE

STOP_BOUNDARY=E03_SUCCESSOR_RECOVERY_READONLY_PREAUTH_ENTRY

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
- fresh GitHub read-only rebind
- source/design/test inspection
- repository branch creation
- product source and test modification for KF-132..136/P0
- docs/KF progress updates
- local/focused tests
- CI observation
- source-repair Draft PR
- independent source review
```

### FORBIDDEN

```text
- T1 access
- T1 mutation
- docker load/tag/rmi on production T1
- Compose mutation on production T1
- systemd stop/start on production T1
- SQLite/manual state mutation
- old authorization replay
- successor live authorization claim
- board access/flash/NVS mutation
- physical E03 retry
- source PR merge unless separately authorized
- Golden Master / Final Seal / clone production reactivation
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
T1_ACCESS=false
BOARD_ACCESS=false
MERGE=false
```

---

## 12. Execution Contract

```text
EXECUTOR=CHATGPT_GITHUB_CONNECTOR_PLUS_LOCAL_SOURCE_TESTS_AS_AVAILABLE
EXECUTION_METHOD=phased_source_repair
DIRECT_CODE_AUTHORING=HIGH_LEVEL_MODEL
CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_DOES_NOT_REPLACE_SOURCE_REVIEW=true
SAME_GATE_LOW_RISK_TEST_OR_DOC_REPAIR_CONTINUE=true
LIVE_GATE_AUTO_CONTINUE=false
```

要求：

- source repair 分阶段执行，避免一次超长 GitHub 操作；
- 先实现公共内核和 regression tests，再接 successor executor；
- 发现 substantive design contradiction 时 STOP，不得跨 gate 临时重新设计生产行为；
- GitHub 是长期证据，不能把关键结果只留在聊天。

---

## 13. Expected Closure

```text
=== N3W_T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_SOURCE_REPAIR_20261030_01 CLOSURE ===

FRESH_MAIN=
FRESH_PR725_HEAD=
FRESH_PR739_HEAD=

SOURCE_REPAIR_PR=
SOURCE_REPAIR_HEAD=
SOURCE_REPAIR_TREE=

PORTABLE_IMAGE_IDENTITY_SOURCE=
PORTABLE_IMAGE_IDENTITY_TESTS=
REAL_OR_ISOLATED_CROSS_STORE_COVERAGE=

KF132_CROSS_STORE_IDENTITY=
KF133_TRANSACTION_BINDING=
KF134_UNKNOWN_COMPOSE=
KF135_CRASH_OWNER=
KF136_MQTT_ACCEPTANCE=

MAINTENANCE_TRANSACTION_SOURCE=
E03_SUCCESSOR_RECOVERY_SOURCE=
OLD_AUTHORIZATION_REPLAY_GUARD=
PREDECESSOR_IMMUTABILITY_GUARD=

FOCUSED_TESTS=
APPLICABLE_CI=
INDEPENDENT_SOURCE_REVIEW=
NEW_SOURCE_BLOCKER_COUNT=
NEW_FALSE_PASS_PATH_COUNT=
NEW_BLOCKING_FALSE_STOP_PATH_COUNT=

T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
LIVE_RECOVERY=false
MERGE=false

SOURCE_REPAIR_CLOSURE=
READONLY_PREAUTH_READY=
NEXT_ROUTE=E03_SUCCESSOR_RECOVERY_READONLY_PREAUTH
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=N3W_T1_E03_SUCCESSOR_RECOVERY_READONLY_PREAUTH
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true

AFTER_PREAUTH_PASS_NEXT_STAGE=E03_SUCCESSOR_RECOVERY_LIVE_AUTHORIZATION
AUTO_EXECUTE_AFTER_PREAUTH=false

AFTER_LIVE_RECOVERY_PASS_NEXT_STAGE=R10_FIRST_REGISTRATION_PHYSICAL_REVALIDATION
AUTO_EXECUTE_AFTER_LIVE=false

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

后续顺序原则：

```text
SOURCE_REPAIR
→ INDEPENDENT_REVIEW
→ READONLY_PREAUTH
→ NEW_SUCCESSOR_AUTHORIZATION
→ LIVE_SUCCESSOR_RECOVERY
→ R10_PHYSICAL_REVALIDATION
```

每一阶段单独授权，不跨 gate。

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true

KF132=OPEN_SOURCE_DESIGN_FROZEN
KF133=OPEN_SOURCE_DESIGN_FROZEN
KF134=OPEN_SOURCE_DESIGN_FROZEN
KF135=OPEN_SOURCE_DESIGN_FROZEN
KF136=OPEN_SOURCE_DESIGN_FROZEN

SOURCE_REPAIR_MAY_ADVANCE_STATUS_ONLY_AFTER_EXACT_TESTED_REVIEWED_SOURCE=true
DO_NOT_CLOSE_ON_DESIGN_OR_CI_ONLY=true
```

不要把 KF-133～136 写成“已在现场真实发生”。它们是当前 executor 的已证明 source safety blockers；只有 KF-132 的本次 runtime false STOP 已现场发生。

---

## 16. New Chat Start Prompt

新对话默认读取：

```text
1. 本 handoff
2. docs/development/N3W_PROJECT_WORKING_CONTEXT.md
3. docs/development/N3W_CURRENT_STATE.md
4. docs/development/N3W_CURRENT_STATE_INDEX.md
5. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
6. docs/development/N3W_T1_MAINTENANCE_IDENTITY_REVIEW_20261030.md
7. docs/development/N3W_T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_SOURCE_DESIGN_FREEZE_20261030.md
8. docs/adr/0010-t1-per-device-fresh-armbian-automated-product-deployment.md
9. historical handoff standard authority 4300890dff0ce63d5a547df21426e287d084d9ee（只读取 process/standard；formal template 使用 current V1.3）
```

建议启动文本：

```text
阅读《N3W_T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_SOURCE_REPAIR_NEW_CHAT_HANDOFF_V1.0_20261030.md》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_T1_MAINTENANCE_IDENTITY_REVIEW_20261030.md
- docs/development/N3W_T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_SOURCE_DESIGN_FREEZE_20261030.md
- docs/adr/0010-t1-per-device-fresh-armbian-automated-product-deployment.md

并 fresh rebind：
- repository main
- PR #725
- PR #739
- PR #725 exact product/source lineage
- PR #739 exact docs/design lineage
- tools/n3w_t1_production_v2_contract.py
- tools/n3w_t1_fresh_product_bootstrap.py
- tools/execution_packages/n3w/kf098/t1_live_cutover/remote_cutover.py
- tools/n3w_t1_r10_e03_manager_successor_refresh_live.py
- relevant tests

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3-W T1 生产维护与发布物身份验证架构收敛
当前任务：Portable Image Identity + E03 Successor Recovery P0 source repair

先 fresh 只读确认 GitHub authority，然后等待/使用本新会话中的明确授权进入：

NEXT_ONE_GATE=
N3W_T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_SOURCE_REPAIR_20261030_01

本 gate：
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
OLD_AUTHORIZATION_REPLAY=false
LIVE_RECOVERY=false
MERGE=false

必须先承认：
- main 仍可能停在 R5，不能把 main 单独当成当前 R10/P0 authority；
- PR #725 是当前 R10/E03 产品源码与 live evidence authority；
- PR #739 是 P0 docs/design authority；
- Astra 已确认至少三次同类 cross-store single-.Id false STOP；
- 当前问题不能只修镜像 ID；
- KF-132～136 均需在 P0 source repair 中处理；
- Docker .Id 允许作为 host-local binding，但不得由 executor 自行当跨 host release oracle；
- 当前 E03 旧 authorization 已 consumed/no-replay；
- 当前 E03 不直接 resume 旧 transaction；
- 后续使用新的、单独授权的 successor transaction；
- 旧 transaction 和已加载 candidate 保留为 evidence；
- unknown Compose 必须 BLOCKED/no write；
- candidate Compose 不得在 application owner 未受控时先发布；
- COMMIT 前必须证明 Manager/HA 真实 MQTT 与业务合同；
- ADR-0010 已退役 Golden Master / Final Seal / clone production；
- 本 gate 不访问 T1/Board，不执行 live recovery，不合并。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_P0
CURRENT_STOP_POINT=P0_DESIGN_FROZEN_GITHUB_ALIGNED_BEFORE_SOURCE_REPAIR

MAIN=2fbd0e9c2d3bf8a513ac318034e249511ffb6a2e
MAIN_CURRENT_FOR_R10=false

PR725_STATE=OPEN_DRAFT
PR725_HEAD=614c08a397462850f0167b77c9da45ae69a323ad

PR739_STATE=OPEN_DRAFT
PR739_HEAD_BEFORE_HANDOFF=9f0b6d7f50af565406150d64ba6e57aa307deeab
PR739_FINAL_HEAD_REQUIRES_FRESH_REBIND=true

P0_DESIGN_FROZEN=true
SOURCE_REPAIR_STARTED=false

KF132=OPEN_SOURCE_DESIGN_FROZEN
KF133=OPEN_SOURCE_DESIGN_FROZEN
KF134=OPEN_SOURCE_DESIGN_FROZEN
KF135=OPEN_SOURCE_DESIGN_FROZEN
KF136=OPEN_SOURCE_DESIGN_FROZEN

OLD_E03_AUTHORIZATION=CONSUMED_NO_REPLAY
OLD_E03_TRANSACTION=IMMUTABLE_PREDECESSOR_EVIDENCE
SUCCESSOR_RECOVERY_AUTHORIZATION=NOT_GRANTED

GOLDEN_MASTER_PRODUCTION_ROUTE=RETIRED_BY_ADR0010

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0_AFTER_THIS_HANDOFF_COMMIT
TEAM_SHARE_COMPLETENESS=PASS

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

NEXT_ONE_GATE=N3W_T1_PORTABLE_IMAGE_IDENTITY_AND_E03_SUCCESSOR_RECOVERY_SOURCE_REPAIR_20261030_01
AUTO_EXECUTE_NEXT_GATE=false
```

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
