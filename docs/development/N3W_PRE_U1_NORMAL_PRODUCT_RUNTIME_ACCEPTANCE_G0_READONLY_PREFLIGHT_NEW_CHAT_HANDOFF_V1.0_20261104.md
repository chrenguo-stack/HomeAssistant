# 温室环境监测系统（ESP32-C6） / N3-W
# Pre-U1 normal product runtime acceptance / G0 read-only preflight
# 新会话交接文档 V1.0 — 2026-11-04

```text
HANDOFF_TEMPLATE_VERSION=1.3
SOLE_VALID_HANDOFF_TEMPLATE_VERSION=1.3
OLDER_HANDOFF_TEMPLATE_VERSIONS=INVALID_FOR_NEW_HANDOFF_GENERATION
HISTORICAL_TEMPLATE_COPIES=HISTORICAL_EVIDENCE_ONLY
HISTORICAL_HANDOFF_STANDARD_DOES_NOT_AUTHORIZE_OLD_TEMPLATE=true
PROJECT_WORKING_CONTEXT_VERSION=1.4
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文只保存当前阶段增量。长期工作规则统一引用
> `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`。
>
> 本 handoff 不包含私有 SSH 地址、私网地址、密码、Home Assistant 登录材料、
> Setup Secret、原始硬件身份、MQTT 密码或密钥。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE
CURRENT_STOP_POINT=PLAN_FROZEN_GITHUB_ALIGNED_BEFORE_G0
NEXT_ONE_GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G0_READONLY_PREFLIGHT_20261104_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

U0 已完成；Manager A -> B U1 已按用户决定挂起但完整保留。下一会话先重新确认
T1_B / Home Assistant / 当前节点的 fresh 只读状态，只进入 G0，不自动创建 HA 用户、
接传感器、注册第二节点或升级 Manager。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.4
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=1
STAGE_OVERRIDES=U1_MANAGER_A_TO_B_SUSPENDED_UNTIL_PRE_U1_ACCEPTANCE_CLOSED_PASS
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=U0_CLOSED_PASS -> PRE_U1_REAL_USER_AND_MULTI_NODE_RUNTIME -> LATER_U1_MANAGER_A_TO_B
FINAL_ACCEPTANCE_TARGET=HOME_ASSISTANT_LOCAL_USER + NODE_A_REAL_SENSORS + NODE_B_NORMAL_REGISTRATION + TWO_NODE_RUNTIME + UPGRADE_HARD_BASELINE_REVALIDATION
DEFERRED_OR_OUT_OF_SCOPE=MANAGER_A_TO_B_LIVE_UPGRADE,HA_OR_BROKER_UPGRADE,HOME_ASSISTANT_CLOUD,DIRECT_RELAY_FAILOVER,LONG_SOAK,LORA,SOLAR_BATTERY_ENDURANCE
```

---

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=FRESH_REBIND_REQUIRED_IN_G0
TREE=NOT_APPLICABLE:G0 must fresh-rebind current repository rather than trust a historical tree

CANDIDATE_REF=feat/n3w-t1-core-updater-a2-per-module-20261103
HANDOFF_INPUT_CANDIDATE_HEAD=5fd7b24a3b655d49ff50738893a2bb84af73c3af
CANDIDATE_HEAD=FRESH_REBIND_REQUIRED_IN_G0
CANDIDATE_TREE=NOT_APPLICABLE:fresh candidate binding required

ARTIFACT_ID=NOT_APPLICABLE:G0 uses existing reviewed updater only for read-only baseline if exact local binding is re-proven
ARTIFACT_SHA256=NOT_APPLICABLE:G0 must rebind exact updater transport before execution if needed

DEPLOYED_SOURCE_HEAD=b863ddd959090ca139af76bd68dbef31d773e6de
DEPLOYED_SOURCE_TREE=NOT_APPLICABLE:current product authority is bound by canonical manifest/images/runtime contracts

OTHER_REQUIRED_AUTHORITY=
  infra/n3w-t1/production/t1-core-stack-current.json;
  infra/n3w-t1/clean-reference/u0-upgrade-baseline-a-20261104.json;
  docs/development/N3W_T1_CORE_UPDATER_U0_REAL_T1_READONLY_BASELINE_CLOSURE_20261104.md;
  docs/development/N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_PLAN_20261104.md;
  docs/development/N3W_T1_CORE_UPDATER_U1_MANAGER_A_TO_B_SUSPENDED_PLAN_20261104.md;
  docs/development/N3W_MANAGER_A_PRODUCT_GAP_REVIEW_FOR_U1_TARGET_B_20261104.md
```

Frozen product identities:

```text
MANAGER_A_IMAGE=local/greenhouse-manager:fresh-b863ddd95909
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
PLATFORM_ALL=linux/arm64
BASELINE_A_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc
BASELINE_A_BYTES=2275
A1_CLASSIFICATION_SHA256=e664ced300ea2bb743b116550b7a3e22237e7f556f54400a060eef30671d30e7
A2_ARCHITECTURE_SHA256=447f57f3563cb7766f145a2ea005d5d79d1beee7585ed07c6572ce2b3a833faa
```

---

## 4. Current Live Baseline

No T1 or Board access occurred during the planning/alignment turn. Therefore do not promote the
last U0 observation to a fresh live claim.

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
```

Last accepted historical/live evidence still relevant to G0:

```text
LAST_CONFIRMED_U0_MANAGER_IMAGE=local/greenhouse-manager:fresh-b863ddd95909
LAST_CONFIRMED_U0_HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
LAST_CONFIRMED_U0_BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
LAST_CONFIRMED_U0_PLATFORM_ALL=linux/arm64
LAST_CONFIRMED_U0_RESULT=CLOSED_PASS
CURRENT_LIVE_STATE_REQUIRES_FRESH_READONLY_RECHECK=true
```

---

## 5. Proven Current Facts

```text
U0_RESULT=CLOSED_PASS
U0_REOPEN=false
U0_TWO_READ_BYTE_IDENTICAL=true
BASELINE_A_SHA256=a791377083e76f765ddf978c09025674eda3586d33892e4b609a814706bdfbbc

U1_MANAGER_A_TO_B_STATUS=SUSPENDED
U1_PLAN_PRESERVED=true
U1_LIVE_APPLY_AUTHORIZED=false
MANAGER_B_SOURCE_CREATED=false
RETAG_IDENTICAL_MANAGER_AS_B_FORBIDDEN=true

PRE_U1_PLAN_FROZEN=true
PRE_U1_GATE_SEQUENCE=G0,G1,G2,G3,G4,G5
HOME_ASSISTANT_CLOUD_REQUIRED=false
HOME_ASSISTANT_LOCAL_OWNER_ALLOWED_IN_G1=true
NODE_A_REAL_SENSOR_RUNTIME_PLANNED_IN_G2=true
NODE_B_NORMAL_FIRST_REGISTRATION_PLANNED_IN_G3=true
TWO_NODE_RUNTIME_PLANNED_IN_G4=true
PRE_U1_BUSINESS_REFERENCE_PLANNED_IN_G5=true
```

Manager A source review found a low-risk candidate improvement for a later real Manager B:
Home Assistant Discovery immediate publish failure can leave de-duplication cache suppressing the
next unchanged attempt. This is a candidate defect until a bounded RED regression proves it.

```text
INFERENCE_MANAGER_B_BEST_CANDIDATE=DISCOVERY_PUBLISH_FAILURE_RETRY_CORRECTNESS
```

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=0
CURRENT_BLOCKER=NONE_FOR_G0
ROOT_CAUSE=NOT_APPLICABLE
PROVEN_BY=U0_CLOSED_PASS_AND_PRE_U1_ROUTE_SELECTION
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
```

U1 has no defined Target B yet by design, but this is not a G0 blocker because U1 is intentionally
suspended.

---

## 7. Closed / Forbidden Routes

```text
IMMEDIATE_U1_MANAGER_A_TO_B=CLOSED_FOR_NOW:suspended until Pre-U1 acceptance and explicit resume
RETAG_B863_AS_MANAGER_B=CLOSED:not a real A->B upgrade
DIRECT_HOMEASSISTANT_STORAGE_PATCH=CLOSED:unsupported product mutation
DIRECT_T1_DATABASE_OR_CREDENTIAL_INJECTION=CLOSED:must use normal product lifecycle
HOME_ASSISTANT_CLOUD_AS_TEST_DEPENDENCY=CLOSED:offline product path must remain valid
REPLAY_CONSUMED_PAIRING_AUTHORIZATION=CLOSED:forbidden
```

---

## 8. Authorization Ledger

```text
AUTHORIZATION=G0_READONLY_ENTRY
CLAIMED=NOT_APPLICABLE
CONSUMED=NOT_APPLICABLE
RESULT=ALLOWED_BY_USER_SELECTED_NEXT_CHAT_EXECUTION_ROUTE
REPLAY_PERMITTED=true
SUPERSEDED_BY=NONE

PROPOSED_AUTHORIZATION=G1_HOMEASSISTANT_LOCAL_ONBOARDING_NORMAL_USER_STATE_MUTATION
GRANTED=false
```

No G1/G2/G3 mutation is implied by G0 PASS.

---

## 9. Rollback Authority

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G0_READONLY_PREFLIGHT_20261104_01
```

### Purpose

G0 must prove the live T1_B is still a safe and healthy starting point after U0 and before normal
business writes.

It must establish:

- fresh repository/PR binding;
- fresh T1 host/product health;
- current hard baseline compatibility with U0;
- no active updater/pairing mutation;
- Home Assistant HTTP/UI reachability;
- whether local Home Assistant onboarding is already complete or still required;
- current registered-node state in public-safe form.

G0 cannot prove Home Assistant user onboarding, real sensor telemetry, second-node registration,
two-node continuity, or U1 upgrade behavior.

### Inputs

```text
INPUT_1=docs/development/N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_PLAN_20261104.md
INPUT_2=infra/n3w-t1/clean-reference/u0-upgrade-baseline-a-20261104.json
INPUT_3=docs/development/N3W_T1_CORE_UPDATER_U1_MANAGER_A_TO_B_SUSPENDED_PLAN_20261104.md
INPUT_4=PR_774_FRESH_REBIND
```

### Operations

```text
1. fresh-rebind repository candidate and PR #774; confirm no source/state drift invalidates this handoff.
2. confirm current relevant CI state without more than three polls.
3. rebind the reviewed read-only updater baseline transport if a local exact copy is required.
4. read T1 system/service/runtime health without mutation.
5. run/read the updater baseline and compare hard authority to U0 Baseline A.
6. prove there is no unresolved updater transaction or active product mutation window.
7. verify Home Assistant HTTP/UI is reachable without creating/changing a user.
8. classify current HA onboarding state without exposing auth secrets/tokens.
9. collect public-safe current-node counts/status only.
10. archive G0 closure to GitHub; STOP before G1.
```

### PASS / FAIL / STOP

```text
PASS_IF=U0_HARD_BASELINE_COMPATIBLE AND PRODUCT_SERVICES_HEALTHY AND NO_ACTIVE_MUTATION AND HOMEASSISTANT_REACHABLE
FAIL_IF=READONLY_EVIDENCE_PROVES_CURRENT_PRODUCT_RUNTIME_UNHEALTHY_OR_UNSUPPORTED
STOP_BOUNDARY=BEFORE_ANY_HA_ACCOUNT_CREATION_BOARD_WIRING_NODE_REGISTRATION_MANAGER_SOURCE_CHANGE_OR_UPDATER_APPLY

AUTO_EXECUTE_NEXT_GATE=false
```

A baseline mismatch is a STOP/classification condition, not an automatic product failure and not an
authorization to reset the T1.

---

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- GitHub fresh read-only rebind and source/state review
- CI status inspection, max 3 polls per HEAD
- T1 read-only host/service/container/listener inspection
- reviewed updater baseline read only
- read-only Home Assistant reachability/onboarding-state check without auth-secret extraction
- public-safe node/business-state counts/status
- GitHub documentation/evidence archival for the G0 closure
```

### FORBIDDEN

```text
- create/change/delete Home Assistant user
- Home Assistant Cloud/Nabu Casa setup
- edit Home Assistant YAML or .storage
- reconfigure MQTT integration
- connect/re-wire sensors or power-cycle a board as part of G0
- erase/flash/NVS mutation
- open pairing window or register Node B
- write registration/credential/DynSec databases
- Manager B source repair/build
- updater plan/apply/rollback transaction
- service restart/recreate used as repair
- PR merge
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=operator-local temporary read-only evidence files and repository-safe G0 closure artifacts only
```

---

## 12. Execution Contract

```text
EXECUTOR=CHATGPT_HIGH_LEVEL_REVIEW_PLUS_OPERATOR_MAC_FOR_PRIVATE_LAN_READONLY_COMMANDS
EXECUTION_METHOD=chat-tool+mac-terminal
DIRECT_CODE_SUPPLIED=true
DSL_COMPILATION_USED=false
CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=true
```

If a small repository-only documentation/test harness issue is proven and its repair is local,
unambiguous and cannot widen the live scope, repair it and continue within G0.

Do not automatically cross into G1.

---

## 13. Expected Closure

```text
=== N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G0_READONLY_PREFLIGHT_20261104_01 CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=READONLY_G0
AUTHORIZATION_CLAIMED=NOT_APPLICABLE
AUTHORIZATION_CONSUMED=NOT_APPLICABLE

REPOSITORY_FRESH_REBIND=
PR774_HEAD=
PRODUCT_SERVICES_HEALTHY=
RELEVANT_FAILED_UNITS=
UPDATER_TRANSACTION_STATE=
PAIRING_MUTATION_STATE=
HOMEASSISTANT_HTTP_REACHABLE=
HOMEASSISTANT_ONBOARDING_STATE=
CURRENT_NODE_COUNT_PUBLIC_SAFE=
FRESH_BASELINE_SHA256=
FRESH_BASELINE_COMPATIBLE_WITH_U0=

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

G0_RESULT=
NEXT_ROUTE=G1_HOMEASSISTANT_LOCAL_ONBOARDING_IF_G0_PASS
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G1_HA_LOCAL_ONBOARDING_20261104_01
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
EXISTING_KF_GUARD_USED=KF-129:no out-of-band Manager recreate during onboarding/registration
NEW_KF_REQUIRED=false
```

A new KF is created only if fresh G0/later evidence proves a new defect.

---

## 16. New Chat Start Prompt

默认读取集：

```text
1. 本 handoff
2. docs/development/N3W_PROJECT_WORKING_CONTEXT.md
3. docs/development/N3W_CURRENT_STATE.md
4. docs/development/N3W_CURRENT_STATE_INDEX.md
5. docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
```

建议启动文本：

```text
阅读《docs/development/N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G0_READONLY_PREFLIGHT_NEW_CHAT_HANDOFF_V1.0_20261104.md》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_PLAN_20261104.md
- docs/development/N3W_T1_CORE_UPDATER_U1_MANAGER_A_TO_B_SUSPENDED_PLAN_20261104.md
- docs/development/N3W_MANAGER_A_PRODUCT_GAP_REVIEW_FOR_U1_TARGET_B_20261104.md
- infra/n3w-t1/clean-reference/u0-upgrade-baseline-a-20261104.json

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

必须先承认：
- U0 已 CLOSED_PASS，不重开；
- Manager A -> B U1 已挂起但方案保留；
- 当前先做 Pre-U1 正常产品运行验收；
- 本轮唯一入口是 G0 只读预检；
- 当前 live 状态不是 fresh，必须重新只读确认；
- 不得把业务数据增长误判为 U0 失效；
- 不得自动创建 HA 用户、接传感器、注册第二节点或进入 U1。

先 fresh rebind repository / PR #774 / current state，然后只进入：

NEXT_ONE_GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G0_READONLY_PREFLIGHT_20261104_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

G0 PASS 后停止，先输出 closure；不要自动进入 G1。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE
CURRENT_STOP_POINT=G0_READONLY_PREFLIGHT_READY_FOR_NEW_CHAT
CURRENT_BLOCKER=NONE_FOR_G0
LIVE_SYSTEM_STATE=UNKNOWN_FRESH
NEXT_ONE_GATE=N3W_PRE_U1_NORMAL_PRODUCT_RUNTIME_ACCEPTANCE_G0_READONLY_PREFLIGHT_20261104_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.4
HANDOFF_TEMPLATE_VERSION=1.3

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.4

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
