# 温室环境监测系统（ESP32-C6）
# N3-W / T1 首次配对 live activation
# 新会话交接文档 V1.1 — 2026-10-24

```text
HANDOFF_TEMPLATE_VERSION=1.3
HANDOFF_TEMPLATE_BLOB=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0
PROJECT_WORKING_CONTEXT_VERSION=1.1
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
HANDOFF_STANDARD_PATH=docs/development/NEW_CHAT_HANDOFF_STANDARD.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文严格使用当前 `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.3。  
> historical commit `4300890d...` 只作为 exact handoff standard authority，不使用其中旧 template。  
> 本文只保存当前阶段增量；长期工作规则统一引用 `N3W_PROJECT_WORKING_CONTEXT.md`。  
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并先 STOP。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=T1_FIRST_PAIRING_ONBOARDING
CURRENT_STOP_POINT=LIVE_READONLY_PREFLIGHT_CLOSED_PASS
NEXT_ONE_GATE=N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_AND_BOARD_D_FIRST_PAIR_20261024_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

本轮已完成 Board D 首次 T1 pairing activation 前的 source repair、exact-source review、CI 和 live read-only preflight。下一 gate 首次涉及真实 T1 pairing mutation，因此在这里切换新会话。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.1
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=2
STAGE_OVERRIDES=
1) PR664 source closure authority 与 docs-only branch advancement 必须分开；
2) 下一 gate 在任何 live mutation 前必须取得新的 exact one-shot authorization。
```

长期 GitHub、证据、授权、CI 轮询、Mac Terminal、STOP、隐私边界等规则统一引用 `N3W_PROJECT_WORKING_CONTEXT.md`，本文不重复展开。

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=
factory-accepted T1
→ user onboarding
→ Board D first secure pairing
→ pairing window closed
→ normal Manager/Broker/HA runtime
→ later MQTT/telemetry acceptance
→ later Direct/Relay/RF acceptance

FINAL_ACCEPTANCE_TARGET=
Board D 在真实产品路径完成首次安全配对，
凭据/key/peer-trust 正确提交，
pairing window 自动/显式关闭，
T1 恢复 factory pairing-disabled runtime，
Broker/HA continuity 保持。

DEFERRED_OR_OUT_OF_SCOPE=
MQTT end-to-end acceptance;
HA entity acceptance;
Direct/Relay/RF acceptance;
production exact R4 reflash;
PR663 merge;
PR664 merge。
```

---

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=dc596ad50eb2ea80ba55aa3af2413236321f1465
TREE=NOT_REQUIRED_NEXT_GATE:exact commit + fresh rebind is sufficient

CANDIDATE_REF=PR#664 / fix/n3w-t1-first-pairing-onboarding-activation-20261024
CANDIDATE_HEAD=FRESH_REBIND_REQUIRED:branch has docs-only handoff advancement after source closure
CANDIDATE_TREE=FRESH_REBIND_REQUIRED

PR664_SOURCE_CLOSURE_HEAD=820afb0f449e38e7937cda635a144b07b4df55d4
ONBOARDING_TOOL_PATH=tools/n3w_t1_first_pairing_onboarding.py
ONBOARDING_TOOL_GIT_BLOB=b1c41f81ef2493420e74010c8d788c797ad1cc6d

ARTIFACT_ID=NOT_APPLICABLE:no new firmware artifact in next gate
ARTIFACT_SHA256=NOT_APPLICABLE:no new firmware artifact in next gate

DEPLOYED_SOURCE_HEAD=a15daad779adde74cdead4702f017553118321f8
DEPLOYED_SOURCE_TREE=f86b8718df1225ab5f0435613f997011b8754bac

OTHER_REQUIRED_AUTHORITY=
Board D hardware identity SHA256:
3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5;
Compose project=n3wfc4;
Broker TLS server name=armbian;
Broker TLS port=8883。
```

Board D 当前运行 DEV low-battery-bypass image，不是 production exact R4。

公开 handoff 不保存 T1 私网 IP、SSH 密码、Board D 当前私网 locator、Setup Secret、原始 pairing identity。

Source closure exact head `820afb0f...` 的相关 CI：

```text
RELATED_CI=12_OF_12_PASS
N3W_T1_FIRST_PAIRING_ONBOARDING_CI=PASS
PUBLIC_REPOSITORY_SAFETY_CI=PASS
GREENHOUSE_MANAGER_CI=PASS
M2_DYNAMIC_SECURITY_CI=PASS
M2_PRIVATE_MOSQUITTO_CI=PASS
M2_MANAGER_RUNTIME_SECRET_OWNERSHIP_CI=PASS
H3_N2_STAGE2B3_PAIRING_RUNTIME_CI=PASS
M2_NODE_AUTH_NATIVE_BOARD_LAB_CI=PASS
M2_NODE_AUTH_BOARD_LAB_CI=PASS
M2_NODE_AUTH_ISOLATED_LAB_CI=PASS
C07_NODE_RETIREMENT_CI=PASS
M0_VERTICAL_SLICE_CI=PASS
```

---

## 4. Current Live Baseline

交接前 fresh live read-only evidence：

```text
MANAGER_STATE=RUNNING
MANAGER_RESTART_STATE=restart_count=0
BROKER_STATE=RUNNING;restart_count=0
HOMEASSISTANT_STATE=RUNNING;restart_count=0

PAIRING_ENABLED=false
PAIRING_ADVERTISED_HOST=auto
NODE_BROKER_HOST=gate-f-unbound.invalid
NODE_BROKER_PORT=8883
NODE_BROKER_TLS_SERVER_NAME=armbian

UDP_47111_LISTENER_COUNT=0
TCP_47112_LISTENER_COUNT=0
TCP_8883_LISTENER_COUNT=1

TRANSACTION_PRESENT=false
RUNTIME_ROOT_PRESENT=false
WATCHDOG_UNIT_COUNT=0

REGISTRATIONS_COUNT=0
PAIRING_SESSIONS_COUNT=0
REGISTRATION_EVENTS_COUNT=0
NODE_ID_LEASES_COUNT=0

CREDENTIAL_LIFECYCLE_DB_PRESENT=false
CREDENTIAL_ASSIGNMENTS_COUNT=0

SYSTEM_PEER_TRUST_DB_PRESENT=false
SYSTEM_PEER_TRUST_COUNT=0

APPLICATION_KEY_ACTIVE_NODES_COUNT=0
APPLICATION_KEY_EPOCHS_COUNT=0

BOARD_D_WIFI_PROVISIONING=PASS
BOARD_D_SOFTWARE_RESTART_LCD=PASS
BOARD_D_LCD_5_PAGE_CYCLE=PASS
BOARD_D_LCD_PAGE5=正在查找主机

BOARD_D_SOURCE_IS_LOCAL=true
ROUTE_SELECTED_IPV4_PRIVATE=PASS

EXPLICIT_PRODUCTION_TLS_SELECTED_LAN=PASS
LIVE_CERTIFICATE_MATCHES_INSTALLED_SERVER_CERT=PASS
MANAGER_NAMESPACE_BROKER_TLS=PASS
OPENSSL_CA_HOSTNAME_VERIFY=PASS

SYSTEMD_ON_ACTIVE_SUPPORT=PASS
SYSTEMD_PROPERTY_SUPPORT=PASS

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false
PAIRING_EXECUTION=false
```

新会话在 live mutation 前必须 fresh recheck：

```text
PR664_CURRENT_HEAD=UNKNOWN_FRESH
PR664_CURRENT_HEAD_REQUIRES_FRESH_READONLY_RECHECK=true

T1_RUNTIME_BASELINE=UNKNOWN_FRESH
T1_RUNTIME_BASELINE_REQUIRES_FRESH_READONLY_RECHECK=true

BOARD_D_NETWORK_ENDPOINT=UNKNOWN_FRESH
BOARD_D_NETWORK_ENDPOINT_REQUIRES_FRESH_READONLY_RECHECK=true
```

---

## 5. Proven Current Facts

```text
N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_READONLY_PREFLIGHT_20261024_01=CLOSED_PASS
LIVE_PAIRING_ACTIVATION_ELIGIBLE_FOR_SEPARATE_AUTHORIZATION=true

FACTORY_PAIRING_DISABLED_BASELINE=PASS
FIRST_PAIR_STATE_CLEAN=true
BOARD_D_AND_T1_LOCAL_ROUTE_BINDING=PASS
BROKER_TLS_PRODUCTION_AUTHORITY=PASS
WATCHDOG_PLATFORM_CAPABILITY=PASS

PAIRING_ONLY_SECURITY_DATABASES_MAY_BE_ABSENT_WHEN_PAIRING_DISABLED=true
PR664_SOURCE_FALSE_PASS_AND_FAIL_OPEN_REVIEW=CLOSED_PASS

T1_RUNTIME_FAILURE_PROVEN=false
BOARD_D_FAILURE_PROVEN=false
```

阶段中发现并修复的 checker/source 问题：

```text
1. docker exec heredoc 缺 -i → checker false stop
2. pairing-only DB 必须预存在 → false assumption
3. Python 3.14 create_default_context strict X.509 → 与既有 production TLS authority 不一致
4. unresolved factory restore 取消 watchdog → fail-open blocker
```

以上 source repair 均在 `PR664_SOURCE_CLOSURE_HEAD=820afb0f...` 前完成并经过 12/12 CI。

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=0
CURRENT_BLOCKER=NONE
ROOT_CAUSE=NOT_APPLICABLE
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
```

下一步唯一门槛是用户新的 live mutation 授权，不是技术 blocker。

非阻断 follow-up：

```text
STRICT_X509_AKI_HARDENING=FOLLOWUP_NONBLOCKING
```

---

## 7. Closed / Forbidden Routes

```text
GREENHOUSE_SSH_USER=CLOSED:当前 T1 管理 authority 为 root SSH
PAIRING_ENABLE_WITH_GATE_F_PLACEHOLDER=CLOSED:可能把 invalid Broker locator 写入节点
DIRECT_BASE_COMPOSE_EDIT=CLOSED:使用 reviewed transient onboarding override
PAIRING_ONLY_DB_MUST_PREEXIST=CLOSED:false assumption
PYTHON_CREATE_DEFAULT_CONTEXT_AS_TLS_AUTHORITY=CLOSED:与 frozen production TLS probe 不一致
REPLAY_WIFI_PROVISIONING_AUTH=CLOSED:consumed
REPLAY_SOFTWARE_RESTART_AUTH=CLOSED:consumed
SERIAL_PASSIVE_OBSERVER=CLOSED:可能 reset/disturb ESP32-C6
PR663_MERGE=CLOSED:DEV-only / DO NOT MERGE
PR664_AUTO_MERGE=CLOSED:需要用户明确授权
```

---

## 8. Authorization Ledger

```text
AUTHORIZATION=N3W_BOARD_D_FIRST_WIFI_PROVISIONING_ACCEPTANCE_20261024_01
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE

AUTHORIZATION=N3W_BOARD_D_SOFTWARE_ESP_RESTART_LCD_ACCEPTANCE_20261024_01
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE

AUTHORIZATION=N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_READONLY_PREFLIGHT_20261024_01
CLAIMED=false
CONSUMED=false
RESULT=PASS_READONLY
REPLAY_PERMITTED=NOT_APPLICABLE
SUPERSEDED_BY=NONE

PROPOSED_AUTHORIZATION=
N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_AND_BOARD_D_FIRST_PAIR_20261024_01

GRANTED=false
```

下一 live authorization 一旦 claim：

```text
REPLAY_PERMITTED=false
SECOND_ATTEMPT_ALLOWED=false
```

---

## 9. Rollback Authority

```text
ROLLBACK_BASELINE=
pairing=false;
node_broker_host=gate-f-unbound.invalid;
UDP47111=0;
TCP47112=0;
Manager/Broker/HA healthy;
Broker/HA container continuity preserved;
transaction absent;
runtime onboarding root absent;
watchdog absent;
first-pair security state clean。

FRESH_PRECHANGE_SNAPSHOT_REQUIRED=true
ROLLBACK_AUTHORITY_PATH_OR_ID=PR664 reviewed onboarding tool + fresh prechange private evidence
RESTART_SCOPE_ALLOWED=Manager-only recreate through reviewed tool
SECOND_ATTEMPT_ALLOWED=false
ROLLBACK_FAILURE_CLASS=ROLLBACK_INCOMPLETE
```

Immediate restore failure contract:

```text
OPEN_RESTORE_PENDING
→ watchdog retained
→ recovery starts immediately
→ systemd Restart=on-failure
→ RestartSec=10s
→ terminal only after observed factory-safe state
```

如果 credential 已被 Board acknowledge 并 commit，后续失败不得盲目删除 credential/key/peer-trust；必须 STOP 并另行设计 reconciliation。

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_AND_BOARD_D_FIRST_PAIR_20261024_01
```

### Purpose

- 使用 exact reviewed PR #664 onboarding tool 打开一次有 watchdog 上限的首配窗口；
- 只配对 Board D；
- 证明 Board acknowledge 后的 MQTT credential / N3-W application key / system peer trust 已正确 commit；
- 关闭 pairing window 并恢复 factory pairing-disabled runtime；
- 本 gate **不能**证明 MQTT telemetry、HA entity、Direct/Relay/RF 已通过。

### Inputs

```text
PR664_SOURCE_CLOSURE_HEAD=820afb0f449e38e7937cda635a144b07b4df55d4
ONBOARDING_TOOL_GIT_BLOB=b1c41f81ef2493420e74010c8d788c797ad1cc6d
BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
BROKER_TLS_SERVER_NAME=armbian
BROKER_TLS_PORT=8883
```

### Operations

```text
1. fresh read-only rebind PR #664 current head and prove no executable-source drift after 820afb0f...
2. fresh T1/Board D prechange baseline and rollback snapshot
3. present exact one-shot mutation authorization scope
4. wait for explicit user authorization
5. materialize/stage exact reviewed tool privately
6. run tool inspect
7. claim/open exactly one bounded pairing window
8. prove watchdog active
9. observe Board D normal product pairing-ready LCD/QR state
10. private Setup Secret handoff through existing Manager pairing socket/CLI
11. perform exactly one Board D first pair
12. verify acknowledged registration/credential/key/peer-trust evidence
13. close success only when exact success evidence exists; otherwise abort/recovery path
14. prove final factory pairing-disabled restoration
15. structured closure and STOP
```

### PASS / FAIL / STOP

```text
PASS_IF=
exact tool binding;
fresh clean baseline;
one authorization claim;
watchdog active;
Board D first pair acknowledged;
registration approved;
node lease active;
MQTT credential generation=1 active;
application key epoch=1 ACTIVE;
peer trust generation=1;
final pairing=false;
47111/47112 closed;
Broker/HA container continuity;
Manager→Broker TLS PASS。

FAIL_IF=
identity/source/runtime ambiguity;
watchdog absent;
credential/key/peer-trust mismatch;
non-target container drift;
factory-safe restore unproven;
authorization replay attempt。

STOP_BOUNDARY=
structured closure after success/failure/recovery;
do not enter MQTT/telemetry acceptance。

AUTO_EXECUTE_NEXT_GATE=false
```

---

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

仅在用户明确批准 proposed authorization 后：

```text
- T1 root SSH
- exact-tool private transient staging
- reviewed Manager-only Compose recreate
- bounded 47111/47112 pairing listeners
- private Setup Secret import
- Board D normal network pairing traffic
- reviewed watchdog/restore path
- bounded evidence filesystem writes owned by onboarding transaction
- read-only Docker/SQLite/listener/TLS verification
```

### FORBIDDEN

```text
- firmware/OTA write
- raw NVS write/restore
- physical EN/RESET
- USB power cycle
- serial passive monitoring
- second Wi-Fi provisioning
- second software restart
- factory/triple reset
- manual broad Compose edit
- Broker recreate
- Home Assistant recreate
- DynSec global reset
- credential database manual edit
- Direct/Relay/RF acceptance
- PR merge
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=false
```

以上两个字段保持到用户真正批准 live gate；授权后由该 gate 的 execution contract 精确重定义允许的 mutation。

---

## 12. Execution Contract

```text
EXECUTOR=HIGH_LEVEL_MODEL_PLUS_MAC_TERMINAL_EXACT_COMMANDS
EXECUTION_METHOD=mac-terminal
DIRECT_CODE_SUPPLIED=true
DSL_COMPILATION_USED=true

CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=true
```

新会话第一阶段只能做 fresh read-only rebind。任何 mutation 前必须先输出：

```text
FRESH_REBIND=
EXECUTABLE_SOURCE_DRIFT=
PRECHANGE_ROLLBACK_SNAPSHOT=
PROPOSED_AUTHORIZATION=
CLAIM_BOUNDARY=
STOP_BOUNDARY=
```

并等待用户明确授权。

同一已授权 gate 内已明确定位的低风险 source/test/CI repair 可按长期工作规则继续，但不得扩大到第二次 live pairing authorization。

---

## 13. Expected Closure

```text
=== N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=

PR664_HEAD=
PR664_SOURCE_CLOSURE_HEAD=
ONBOARDING_TOOL_BINDING=

PRECHANGE_FACTORY_BASELINE=
PAIRING_WINDOW_OPEN=
WATCHDOG_ACTIVE=

BOARD_D_PAIRING_READY=
SETUP_SECRET_HANDOFF=
BOARD_D_FIRST_PAIR_ACKNOWLEDGED=

REGISTRATION_STATE=
MQTT_CREDENTIAL_STATE=
APPLICATION_KEY_STATE=
PEER_TRUST_STATE=

PAIRING_WINDOW_CLOSE=
FINAL_FACTORY_PAIRING_DISABLED=
FINAL_PAIRING_LISTENERS_CLOSED=
BROKER_CONTAINER_CONTINUITY=
HOMEASSISTANT_CONTAINER_CONTINUITY=
FINAL_MANAGER_BROKER_TLS=

LIVE_RUNTIME_MUTATION=
BOARD_ACCESS=
BOARD_D_DURABLE_PAIRING_STATE_CHANGED=

ROLLBACK_OR_RECOVERY_STATE=

GATE_RESULT=
NEXT_ROUTE=
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=BOARD_D_NORMAL_RUNTIME_MQTT_MANAGER_HA_ACCEPTANCE_DESIGN
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

失败后保留 transaction/watchdog/recovery evidence，不重放 live authorization。

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
EXISTING_KF_GUARD_USED=
pairing/security lifecycle separation;
container recreate oracle;
Manager state schema/public-safe identity authority;
unknown propagation;
SSH stdin/TTY/shell portability;
exact-source binding;
no speculative fix。

NEW_KF_REQUIRED=false
```

本阶段新增但尚不要求 main KNOWN_FAILURES 修改的 follow-up：

```text
STRICT_X509_AKI_HARDENING=FOLLOWUP_NONBLOCKING
```

---

## 16. New Chat Start Prompt

```text
阅读：

docs/development/N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_NEW_CHAT_HANDOFF_V1.0_20261024.md

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

读取当前 formal template authority：
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
- expected HANDOFF_TEMPLATE_VERSION=1.3
- expected blob=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0

读取 exact handoff standard authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md

并 fresh rebind：
- repository main
- PR #664 current HEAD
- PR #664 diff since source closure head
- tools/n3w_t1_first_pairing_onboarding.py
- docs/development/N3W_T1_FIRST_PAIRING_ONBOARDING_ACTIVATION_SOURCE_DESIGN_AND_REPAIR_20261024.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3-W 量产主线收敛与 Board D 后续验收准备
支线任务：Board D 首次 T1 配对与产品运行通信验收
当前任务：N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_AND_BOARD_D_FIRST_PAIR_20261024_01

先做当前 gate 所需的最小 fresh 只读确认。

必须先承认：
- formal handoff template authority 是当前 NEW_CHAT_HANDOFF_TEMPLATE.md V1.3；
- historical 4300890d... 只作为 exact handoff standard authority；
- PR #664 source closure head=820afb0f449e38e7937cda635a144b07b4df55d4；
- handoff/docs-only 提交会继续推进 PR branch HEAD，因此必须 fresh rebind，并证明 820afb0f... 之后无 executable-source drift；
- live onboarding readonly preflight=CLOSED_PASS；
- TLS delta=PASS；
- pairing-only credential/peer-trust DB 在 pairing-disabled clean baseline 可合法不存在；
- T1 当前 pairing=false，47111/47112 closed，Manager/Broker/HA restart_count=0；
- Board D 当前为 DEV low-battery-bypass image，不是 production exact R4；
- Board D first Wi-Fi provisioning 与 software restart/LCD acceptance 已 PASS；
- 两项旧 Board D authorization 已 consumed，不得重放；
- 下一 live pairing authorization 尚未 granted；
- PR #664 不得自动 merge。

NEXT_ONE_GATE=
N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_AND_BOARD_D_FIRST_PAIR_20261024_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

在任何 mutation 前，先给出：
FRESH_REBIND
EXECUTABLE_SOURCE_DRIFT
PRECHANGE_ROLLBACK_SNAPSHOT
PROPOSED_AUTHORIZATION
CLAIM_BOUNDARY
STOP_BOUNDARY

然后等待用户明确授权。

不要重放 consumed authorization，不要重新进入 closed routes，不要自动跨越下一阶段。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=T1_FIRST_PAIRING_ONBOARDING
CURRENT_STOP_POINT=LIVE_READONLY_PREFLIGHT_CLOSED_PASS
CURRENT_BLOCKER=NONE

LIVE_SYSTEM_STATE=
T1 factory pairing-disabled;
first-pair state clean;
Broker/Manager/HA healthy;
Board D Wi-Fi/Native API/LCD healthy;
production TLS delta PASS。

NEXT_ONE_GATE=
N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_AND_BOARD_D_FIRST_PAIR_20261024_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.1
HANDOFF_TEMPLATE_VERSION=1.3

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
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
