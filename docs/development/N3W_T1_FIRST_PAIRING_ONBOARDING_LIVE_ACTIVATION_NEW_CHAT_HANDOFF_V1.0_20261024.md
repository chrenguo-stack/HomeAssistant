# 温室环境监测系统（ESP32-C6）
# N3-W / T1 首次配对 live activation
# 新会话交接文档 V1.0 — 2026-10-24

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

> 本文按 exact handoff process authority `4300890dff0ce63d5a547df21426e287d084d9ee` 中的  
> `docs/development/NEW_CHAT_HANDOFF_STANDARD.md` 与  
> `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` 编写。  
> 如本文与 fresh exact repository/runtime/live evidence 冲突，以更高 authority 为准并 STOP。

---

## 0. 会话切换结论

本轮已经完成 Board D 首次 T1 pairing activation 前的源码设计、source repair、独立 false-PASS/fail-open review，以及 live read-only preflight。

当前恰好位于明确的 mutation 边界：

```text
CURRENT_STAGE=T1_FIRST_PAIRING_ONBOARDING
CURRENT_STOP_POINT=LIVE_READONLY_PREFLIGHT_CLOSED_PASS
NEXT_ONE_GATE=N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_AND_BOARD_D_FIRST_PAIR_20261024_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话不是重新复盘全部历史；先 fresh rebind 本文 frozen authorities，再进入下一门授权设计。任何 live pairing mutation 仍需用户重新明确授权。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护 product route、exact repository/source/runtime authority；
- 设计 live gate、authorization、rollback 与 STOP；
- 复核 pairing/credential/runtime closure；
- 区分 checker/source/runtime/product failure；
- 不因新会话重建新的 parallel execution framework。

### 1.2 Codex 低阶执行职责

- 机械执行 exact DSL contract；
- 仅在授权后执行 SSH/Docker/Compose/文件 staging/Manager recreate；
- 第一处 substantive mismatch 后 fail-closed STOP；
- 不扩大 scope、不重放 consumed authorization、不自行进入后续 MQTT/RF gate。

### 1.3 DSL execution semantics

```text
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
DSL_COMPILATION_AUTHORIZED=true

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false
```

### 1.4 标准交互循环

```text
高阶模型：fresh rebind + live gate/authorization
        ↓
用户：批准 exact live authorization
        ↓
Codex：staging/open/pair/close/closure
        ↓
高阶模型：复核，不自动进入下一门
```

---

## 2. Product North Star

当前产品路线：

```text
factory-accepted T1
→ user onboarding
→ Board D first secure pairing
→ pairing window closed
→ normal Manager/Broker/HA runtime
→ later MQTT/telemetry acceptance
→ later Direct/Relay/RF acceptance
```

当前阶段目标：

```text
完成 Board D 与当前 T1 的首次产品配对，
同时保证：
- factory pairing-disabled 默认不被永久改写；
- Broker locator 使用当前 route-selected T1 LAN IPv4；
- TLS identity 仍为 armbian；
- Setup Secret 只走 private pairing path；
- pairing window 有 watchdog 上限；
- 完成后恢复 pairing-disabled；
- Broker 与 Home Assistant 不被重建。
```

当前不得自动进入：

```text
MQTT_END_TO_END_ACCEPTANCE
DIRECT_RELAY_ACCEPTANCE
RF_ACCEPTANCE
PRODUCTION_EXACT_R4_REFLASH
PR664_MERGE
PR663_MERGE
```

---

## 3. Frozen Authorities

### 3.1 Repository / main / PR

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=dc596ad50eb2ea80ba55aa3af2413236321f1465

PR=664
PR_STATE=OPEN_DRAFT
PR_BASE=main
PR_BASE_SHA=dc596ad50eb2ea80ba55aa3af2413236321f1465
PR_SOURCE_CLOSURE_HEAD=0f82941a73a73730631d8b8da22ce43d7d756708
PR_MERGEABLE=true
MERGE_AUTHORIZED=false
```

PR #664 source closure authority is frozen at `0f82941a73a73730631d8b8da22ce43d7d756708`. The branch HEAD advances by docs-only handoff commits; the new chat must fresh rebind the actual current HEAD and prove no executable-source drift.

### 3.2 Onboarding source authority

```text
ONBOARDING_TOOL_PATH=tools/n3w_t1_first_pairing_onboarding.py
ONBOARDING_TOOL_GIT_BLOB=b1c41f81ef2493420e74010c8d788c797ad1cc6d

SOURCE_DESIGN_PATH=docs/development/N3W_T1_FIRST_PAIRING_ONBOARDING_ACTIVATION_SOURCE_DESIGN_AND_REPAIR_20261024.md
SOURCE_DESIGN_GIT_BLOB=73bc936a432fee90e95167e00360801d5bb173b5
```

Exact source/test/workflow CI on PR #664 current branch:

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

### 3.3 Board D authority

```text
BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5

CURRENT_BOARD_D_APPLICATION=DEV_LOW_BATTERY_BYPASS
CURRENT_BOARD_D_APPLICATION_IS_PRODUCTION_EXACT_R4=false

DEV_SOURCE_HEAD=a15daad779adde74cdead4702f017553118321f8
DEV_SOURCE_TREE=f86b8718df1225ab5f0435613f997011b8754bac
DEV_ARTIFACT_ID=12538399121
DEV_ARTIFACT_DIGEST=75b3206cd9d7d2a8d30ad49a0ff224981eaab770bad01dde8b6f1d69686bf88a
```

Do not expose Board D local hostname/IP in public GitHub evidence. Fresh live resolution may be used privately at execution time.

### 3.4 T1 authority

```text
TARGET_PLATFORM=T1 / Armbian / Aml.S912
SSH_AUTHORITY=root account using operator-local password
COMPOSE_PROJECT=n3wfc4
MANAGER_NETWORK_MODE=host
BROKER_TLS_SERVER_NAME=armbian
BROKER_TLS_PORT=8883
```

Private LAN address is runtime-local evidence and is not frozen into public repository docs.

---

## 4. Current Live Baseline

Latest live read-only evidence:

```text
MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0
MANAGER_NETWORK_MODE=host

BROKER_RUNNING=true
BROKER_RESTART_COUNT=0

HOMEASSISTANT_RUNNING=true
HOMEASSISTANT_RESTART_COUNT=0

GH_N3W_RUNTIME_ENABLED=true
GH_N3W_PRODUCT_PAIRING_ENABLED=false
GH_N3W_PAIRING_ADVERTISED_HOST=auto
GH_N3W_NODE_BROKER_HOST=gate-f-unbound.invalid
GH_N3W_NODE_BROKER_PORT=8883
GH_N3W_NODE_BROKER_TLS_SERVER_NAME=armbian

UDP_47111_LISTENER_COUNT=0
TCP_47112_LISTENER_COUNT=0
TCP_8883_LISTENER_COUNT=1

TRANSACTION_PRESENT=false
RUNTIME_ROOT_PRESENT=false
WATCHDOG_UNIT_COUNT=0
```

Clean first-pair state:

```text
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
```

Board/T1 network and TLS evidence:

```text
BOARD_D_MDNS_RESOLUTION=PASS
BOARD_D_SOURCE_IS_LOCAL=true
ROUTE_SELECTED_IPV4_PRIVATE=PASS

EXPLICIT_PRODUCTION_TLS_SELECTED_LAN=PASS
LIVE_CERTIFICATE_MATCHES_INSTALLED_SERVER_CERT=PASS
MANAGER_NAMESPACE_BROKER_TLS=PASS
OPENSSL_CA_HOSTNAME_VERIFY=PASS
T1_ONBOARDING_TLS_DELTA=PASS

SYSTEMD_ON_ACTIVE_SUPPORT=PASS
SYSTEMD_PROPERTY_SUPPORT=PASS
```

Board D current product-visible state:

```text
FIRST_WIFI_PROVISIONING_ACCEPTANCE=PASS
SOFTWARE_RESTART_LCD_ACCEPTANCE=PASS
LCD_5_PAGE_CYCLE=PASS
LCD_FREEZE_OR_CORRUPTION=false
LCD_PAGE5=正在查找主机
```

Mutation state at handoff:

```text
T1_MUTATION=false
BOARD_D_MUTATION=false
PAIRING_EXECUTION=false
LIVE_AUTHORIZATION_CONSUMED=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
NVS_MUTATION=false
RF_EXECUTION=false
```

New chat must fresh read-only rebind these live facts before mutation.

---

## 5. Proven Current Facts

```text
LIVE_READONLY_PREFLIGHT_CORE=PASS
LIVE_TLS_DELTA=PASS
N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_READONLY_PREFLIGHT_20261024_01=CLOSED_PASS

LIVE_PAIRING_ACTIVATION_ELIGIBLE_FOR_SEPARATE_AUTHORIZATION=true

FACTORY_PAIRING_DISABLED_BASELINE=PASS
FIRST_PAIR_DATABASE_STATE_CLEAN=true
BOARD_D_AND_T1_LOCAL_ROUTE_BINDING=PASS
BROKER_TLS_PRODUCTION_AUTHORITY=PASS
WATCHDOG_PLATFORM_CAPABILITY=PASS

T1_RUNTIME_FAILURE_PROVEN=false
BOARD_D_FAILURE_PROVEN=false
```

The read-only preflight had three checker/source findings, all repaired in PR #664 before live mutation:

1. `docker exec ... python -` without `-i` caused an empty JSON checker false stop;
2. pairing-only credential/peer-trust databases may validly be absent while pairing is disabled;
3. Python 3.14 `create_default_context()` strict X.509 defaults rejected the existing certificate chain for missing AKI, while the established production TLS authority uses an explicit client context.

All three are source/checker issues, not proven product failures.

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=0
LIVE_MUTATION_AUTHORIZATION_REQUIRED=true
```

There is no remaining source/runtime blocker to the next logical gate based on current evidence.

Non-blocking follow-up:

```text
STRICT_X509_AKI_HARDENING=FOLLOWUP_NONBLOCKING
```

The currently deployed certificate chain is not compatible with Python 3.14's stricter default X.509 policy because of the missing Authority Key Identifier. Existing production CA + hostname + exact live certificate verification passes. Do not silently close the certificate-profile hardening item, but do not classify current Broker runtime as failed.

---

## 7. Closed / Forbidden Routes

```text
GREENHOUSE_SSH_USER=CLOSED_WRONG_ACCOUNT
SSH_ROOT_AUTHORITY=PROVEN

PAIRING_ENABLE_ONLY_WITH_GATE_F_PLACEHOLDER=FORBIDDEN
DIRECT_COMPOSE_EDIT_FOR_PAIRING=FORBIDDEN

PAIRING_ONLY_DB_MUST_PREEXIST=CLOSED_FALSE_ASSUMPTION
PYTHON_CREATE_DEFAULT_CONTEXT_IS_PRODUCTION_TLS_AUTHORITY=CLOSED_FALSE_ASSUMPTION

SECOND_BOARD_D_SOFTWARE_RESTART_UNDER_CONSUMED_AUTH=FORBIDDEN
SECOND_WIFI_PROVISIONING_UNDER_CONSUMED_AUTH=FORBIDDEN

SERIAL_AS_PASSIVE_OBSERVER=FORBIDDEN
PR663_MERGE=FORBIDDEN
PR664_MERGE=FORBIDDEN_WITHOUT_EXPLICIT_USER_APPROVAL
```

---

## 8. Authorization Ledger

### Board D first Wi-Fi provisioning

```text
AUTHORIZATION=N3W_BOARD_D_FIRST_WIFI_PROVISIONING_ACCEPTANCE_20261024_01
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
```

### Board D software restart acceptance

```text
AUTHORIZATION=N3W_BOARD_D_SOFTWARE_ESP_RESTART_LCD_ACCEPTANCE_20261024_01
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
```

### T1 onboarding live read-only preflight

```text
AUTHORIZATION=NOT_REQUIRED_READONLY
CLAIMED=false
CONSUMED=false
RESULT=PASS
REPLAY_PERMITTED=NOT_APPLICABLE
```

### Proposed next live authorization

```text
PROPOSED_AUTHORIZATION=N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_AND_BOARD_D_FIRST_PAIR_20261024_01
GRANTED=false
CLAIMED=false
CONSUMED=false
REPLAY_PERMITTED=false_AFTER_CLAIM
```

No authorization from this conversation carries into the new chat automatically.

---

## 9. Rollback Authority

Next gate is live mutation and must fresh-bind rollback immediately before claim.

Prechange rollback target:

```text
PAIRING_ENABLED=false
NODE_BROKER_HOST=gate-f-unbound.invalid
UDP_47111=0
TCP_47112=0
MANAGER_RUNNING=true
BROKER_RUNNING=true
HOMEASSISTANT_RUNNING=true
BROKER_CONTAINER_CONTINUITY_REQUIRED=true
HOMEASSISTANT_CONTAINER_CONTINUITY_REQUIRED=true
TRANSACTION_PRESENT=false
RUNTIME_ROOT_PRESENT=false
WATCHDOG_UNIT_COUNT=0
FIRST_PAIR_SECURITY_STATE_CLEAN=true
```

Required prechange fresh evidence:

```text
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=true

snapshot:
- exact PR/tool authority;
- factory acceptance marker binding;
- rendered factory Compose pairing contract;
- Manager/Broker/HA container identity hashes and restart counts;
- pairing/credential/key/peer-trust counts;
- listener state;
- route-selected Broker locator hash only;
- TLS production probe;
- watchdog platform capability.
```

Rollback execution authority after claim is the reviewed PR #664 tool:

```text
factory Manager restore
→ remove runtime override
→ pairing=false
→ gate-f-unbound.invalid restored
→ UDP/47111=0
→ TCP/47112=0
→ Manager→Broker TLS PASS
→ Broker/HA container continuity PASS
```

If immediate restore fails:

```text
OPEN_RESTORE_PENDING
→ watchdog retained
→ immediate recovery service
→ Restart=on-failure
→ RestartSec=10s
→ terminal only after observed factory-safe state
```

No second live activation attempt is permitted under a claimed authorization.

If credentials have already been acknowledged/committed and later runtime acceptance fails, do not blindly delete credentials or restore a historical database. STOP and classify reconciliation separately.

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_AND_BOARD_D_FIRST_PAIR_20261024_01
```

Purpose:

```text
Use exact reviewed PR #664 onboarding authority to open one bounded first-pair window,
pair exactly Board D,
close the pairing window,
and prove first-pair credential commitment plus factory pairing-disabled restoration.
```

Frozen inputs:

```text
PR664_SOURCE_CLOSURE_HEAD=0f82941a73a73730631d8b8da22ce43d7d756708
ONBOARDING_TOOL_GIT_BLOB=b1c41f81ef2493420e74010c8d788c797ad1cc6d
BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
BROKER_TLS_SERVER_NAME=armbian
PAIRING_FACTORY_DEFAULT=false
```

Allowed only after explicit authorization:

1. fresh read-only authority rebind;
2. materialize exact PR #664 onboarding tool from exact ref;
3. stage exact tool to a private transient T1 path with hash/blob verification;
4. invoke tool `inspect`;
5. derive Board D current private endpoint and route-selected T1 Broker locator;
6. exactly one `open` transaction with bounded window;
7. observe Board D LCD transition into product pairing QR state;
8. private operator Setup Secret handoff through existing product CLI/socket path;
9. exactly one Board D first-pair transaction;
10. `close --outcome success` only if exact acknowledged credential evidence exists;
11. otherwise `close --outcome abort` or watchdog recovery as contract requires;
12. read-only final closure capture.

PASS requires:

```text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false

PAIRING_WINDOW_OPENED=true
PAIRING_WATCHDOG_ACTIVE=true

BOARD_D_FIRST_PAIR_ACKNOWLEDGED=true

REGISTRATIONS=1
NODE_ID_LEASES=1
PAIRING_STATE=approved
LEASE_STATE=active

CREDENTIAL_ASSIGNMENTS=1
MQTT_CREDENTIAL_STATE=active
MQTT_CREDENTIAL_GENERATION=1
MQTT_PENDING_GENERATION=null

APPLICATION_KEY_ACTIVE_NODES=1
APPLICATION_KEY_EPOCHS=1
APPLICATION_KEY_STATE=ACTIVE
APPLICATION_KEY_EPOCH=1

PEER_TRUST_RECORDS=1
PEER_TRUST_SYSTEM_ID_MATCH=true
PEER_TRUST_GENERATION=1

FINAL_PAIRING_ENABLED=false
FINAL_NODE_BROKER_HOST=gate-f-unbound.invalid
FINAL_UDP_47111=0
FINAL_TCP_47112=0

BROKER_CONTAINER_UNCHANGED=true
HOMEASSISTANT_CONTAINER_UNCHANGED=true
MANAGER_BROKER_TLS=PASS

T1_FIRST_PAIRING_GATE=PASS
```

FAIL/STOP:

- exact source/tool binding drift;
- prechange clean state no longer true;
- route-selected Broker/TLS check fails;
- Board D identity ambiguous;
- tool claim/open result ambiguous;
- watchdog not active after open;
- Setup Secret handoff ambiguous;
- credential/key/peer-trust identity mismatch;
- non-target Broker/HA container drift;
- factory-safe restore unproven;
- any attempt to reuse claimed authorization.

STOP after structured closure. Do not automatically enter MQTT/telemetry acceptance.

---

## 11. Hard Allowed / Forbidden Scope

Defaults:

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

After exact authorization, ALLOWED:

```text
T1 root SSH
private transient exact-tool staging
Manager-only Compose recreate through reviewed tool
bounded pairing listeners 47111/47112
private Setup Secret import
Board D normal network pairing traffic
reviewed watchdog/restore path
read-only Docker/SQLite/listener/TLS verification
```

FORBIDDEN:

```text
firmware write
OTA write
raw NVS write/restore
physical EN/RESET
USB power cycle
second Wi-Fi provisioning
second software restart
factory/triple reset
manual broad Compose edits
Broker recreate
Home Assistant recreate
DynSec global reset
credential database manual edits
Direct/Relay/RF acceptance
merge
```

---

## 12. Codex DSL Execution Contract

New chat must first perform:

```text
READONLY:
- fresh rebind main / PR #664 / exact tool blob / CI;
- fresh T1 service/container/listener baseline;
- fresh Board D mDNS + Native API reachability;
- exact factory clean-state counts;
- exact production TLS delta;
- no stale transaction/runtime-root/watchdog.
```

If any frozen assumption drifted:

```text
STOP
MUTATION=false
RETURN_TO_HIGH_LEVEL_MODEL=true
```

If all PASS and user grants exact authorization:

```text
CLAIM exactly once
→ stage exact tool
→ open bounded window
→ wait for pairing-ready LCD/QR
→ private Setup Secret handoff
→ first pair exactly once
→ verify acknowledged credential/key/peer-trust state
→ close success
→ verify factory pairing-disabled restoration
→ structured closure
→ STOP
```

No hidden retry.

---

## 13. Expected Closure

```text
=== N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_CLOSURE_BEGIN ===

TASK=
AUTHORIZATION=
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=
REPLAY_PERMITTED=

PR664_HEAD=
ONBOARDING_TOOL_BINDING=

PRECHANGE_FACTORY_BASELINE=
BROKER_CONTAINER_CONTINUITY=
HOMEASSISTANT_CONTAINER_CONTINUITY=

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
FINAL_MANAGER_BROKER_TLS=

T1_MUTATION=
BOARD_D_DURABLE_PAIRING_STATE_CHANGED=

ROLLBACK_OR_RECOVERY_STATE=

GATE_RESULT=
NEXT_ROUTE=

STOP=true
=== END ===
```

Do not claim MQTT telemetry/HA entity/Direct/Relay PASS from this closure unless separately proven by a later gate.

---

## 14. After PASS / FAIL

After PASS:

```text
NEXT_ROUTE=DESIGN_NEXT_READONLY_RUNTIME_ACCEPTANCE
AUTO_EXECUTE_NEXT_GATE=false
```

Likely later subject: Board D MQTT → Manager → Home Assistant normal runtime acceptance.

After FAIL:

```text
NO_RETRY=true
RETURN_TO_HIGH_LEVEL_MODEL=true
PRESERVE_TRANSACTION_AND_RECOVERY_EVIDENCE=true
```

If watchdog is still recovering, do not interfere with it unless a separately designed emergency recovery gate is authorized.

---

## 15. KNOWN_FAILURES Updates

Current relevant guards already include:

- pairing/security lifecycle separation;
- exact-target recovery and no replay after claim;
- container recreate oracle;
- Manager state schema / public-safe identity authority;
- unknown propagation;
- SSH stdin/TTY/shell portability;
- no speculative fix;
- single authority / exact binding.

New findings from this stage are recorded in the PR #664 design/closure document and PR Conversation:

```text
PAIRING_ONLY_DB_ABSENCE_VALID_WHEN_PAIRING_DISABLED=true
PYTHON314_STRICT_DEFAULT_TLS_NOT_PRODUCTION_TLS_AUTHORITY=true
STRICT_X509_AKI_HARDENING=FOLLOWUP_NONBLOCKING
```

No main-branch KNOWN_FAILURES mutation is authorized by this handoff.

---

## 16. New Chat Start Prompt

```text
阅读：

docs/development/N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_NEW_CHAT_HANDOFF_V1.0_20261024.md

同时读取 exact handoff process authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- PR #664
- tools/n3w_t1_first_pairing_onboarding.py
- docs/development/N3W_T1_FIRST_PAIRING_ONBOARDING_ACTIVATION_SOURCE_DESIGN_AND_REPAIR_20261024.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3-W 量产主线收敛与 Board D 后续验收准备
支线任务：Board D 首次 T1 配对与产品运行通信验收
当前任务：N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_AND_BOARD_D_FIRST_PAIR_20261024_01

先 fresh read-only rebind，不执行 mutation。

必须先承认：
- live onboarding readonly preflight 已 CLOSED_PASS；
- TLS delta 已 PASS；
- pairing-only credential/peer-trust DB 在 pairing-disabled clean baseline 可合法不存在；
- PR #664 source closure head 为 0f82941a73a73730631d8b8da22ce43d7d756708；handoff docs-only 提交会继续推进分支 HEAD，必须 fresh rebind 并证明无 executable-source drift 后再使用；
- 当前 T1 pairing=false，47111/47112 closed，Broker/Manager/HA restart_count=0；
- Board D 当前为 DEV low-battery-bypass image，不是 production exact R4；
- Board D first Wi-Fi provisioning 和 software restart/LCD acceptance 均已 PASS；
- 之前 Wi-Fi provisioning 与 software restart authorization 已 consumed，不得重放；
- 下一 live pairing authorization 尚未 granted；
- PR #664 不得自动 merge。

NEXT_ONE_GATE=
N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_AND_BOARD_D_FIRST_PAIR_20261024_01

在任何 mutation 前，先给出 fresh rebind 结果、exact authorization scope、rollback snapshot/STOP 边界，并等待用户明确授权。
```

---

## 17. Final Frozen State

```text
HANDOFF_DATE=2026-10-24

MAIN=dc596ad50eb2ea80ba55aa3af2413236321f1465
PR664=OPEN_DRAFT
PR664_SOURCE_CLOSURE_HEAD=0f82941a73a73730631d8b8da22ce43d7d756708
PR664_CI=12_OF_12_PASS
PR664_MERGE=false

ONBOARDING_TOOL_GIT_BLOB=b1c41f81ef2493420e74010c8d788c797ad1cc6d

LIVE_READONLY_PREFLIGHT=CLOSED_PASS
LIVE_PAIRING_ACTIVATION_ELIGIBLE=true
LIVE_PAIRING_AUTHORIZATION_GRANTED=false

T1_MUTATION=false
BOARD_D_MUTATION=false
PAIRING_EXECUTION=false

T1_PAIRING_ENABLED=false
PAIRING_LISTENERS_CLOSED=true
FIRST_PAIR_STATE_CLEAN=true
BROKER_TLS_DELTA=PASS

BOARD_D_CURRENT_IMAGE=DEV_LOW_BATTERY_BYPASS
BOARD_D_WIFI_PROVISIONING=PASS
BOARD_D_SOFTWARE_RESTART_LCD=PASS

NEXT_ONE_GATE=N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_AND_BOARD_D_FIRST_PAIR_20261024_01
```

---

## 18. Handoff Compliance Audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_STANDARD_VERSION=1.0

EXECUTION_MODEL_EXPLICIT=PASS
HIGH_LEVEL_CODEX_ROLE_BOUNDARY=PASS
DSL_EXECUTION_SEMANTICS_EXPLICIT=PASS

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
EXPECTED_CLOSURE_PRESENT=PASS
AFTER_PASS_DOES_NOT_AUTO_EXECUTE=PASS

KNOWN_FAILURES_UPDATE_CLASSIFIED=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
FINAL_FROZEN_STATE_PRESENT=PASS

HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_EXECUTION_SEMANTICS_COMPLETENESS=PASS

HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```
