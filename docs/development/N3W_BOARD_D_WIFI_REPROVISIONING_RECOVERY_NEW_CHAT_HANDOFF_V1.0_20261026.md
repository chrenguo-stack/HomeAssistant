# 温室环境监测系统（ESP32-C6）
# N3-W / Board D Wi-Fi 重新配置与首次配对恢复
# 新会话交接文档 V1.0 — 2026-10-26

```text
HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.1
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
HANDOFF_TEMPLATE_BLOB=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0
HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
HANDOFF_STANDARD_BLOB=0ca966bd3417d8817ca79686b70772c1cb57730b
```

> 本文严格使用当前 `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.3。  
> historical commit `4300890d...` 只作为 exact handoff standard authority；执行方法以当前 `N3W_PROJECT_WORKING_CONTEXT.md` 与 V1.3 template 为准，不重新启用已经淘汰的 handoff DSL 执行模式。  
> 本文只保存当前阶段增量；长期工作规则统一引用 `N3W_PROJECT_WORKING_CONTEXT.md`。  
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并先 STOP。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=BOARD_D_POST_SCOPED_NVS_RESET_WIFI_RECOVERY
CURRENT_STOP_POINT=BOARD_D_COLD_BOOT_APPLICATION_PASS_FALLBACK_AP_ACTIVE
NEXT_ONE_GATE=N3W_T1_BOARD_D_WIFI_REPROVISIONING_RECOVERY_20261026_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

本轮已经完成 T1 clean reinstall 后 exact production activation、Board D stale pairing-state 根因确认、scoped full-NVS reset、preboot all-FF oracle、应用冷启动诊断以及 T1 post-reset clean baseline。

切换会话的原因：Board D 当前已经能正常冷启动，LCD 正常，fallback AP 可见；后续需要执行新的 Wi-Fi 重新配置，再进入新的 first-pair 准备与授权。Wi-Fi 配置会写入 Board D 持久状态，必须在新会话中作为新的单独 gate 处理。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.1
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=4
STAGE_OVERRIDES=
1) historical 4300890d... 只保留 handoff standard / replay / completeness 语义；当前执行采用 direct orchestration + Mac Terminal / manual physical，不采用旧 DSL compilation；
2) Board D 之前的 Wi-Fi provisioning authorization 已消费，不能因为 full-NVS erase 清掉 Wi-Fi 就重放旧授权；
3) scoped NVS reset authorization 已消费且永久禁止重放；private pre-reset NVS backup 仅作 forensic evidence，禁止恢复；
4) 当前 fallback AP 的原始 SSID、T1 私网 locator、Wi-Fi SSID/password、Setup Secret、raw pairing identity 不进入公开 GitHub handoff。
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=
T1 exact production ready
→ Board D stale pairing state removed
→ Board D Wi-Fi reprovisioning
→ fresh first-pair preparation
→ new explicit first-pair authorization
→ Board D first secure pairing
→ pairing window CLOSED
→ normal Manager/Broker/HA runtime
→ later MQTT/telemetry acceptance
→ later Direct/Relay/RF acceptance

FINAL_ACCEPTANCE_TARGET=
Board D 在当前 clean T1 上完成一次新的、安全的 first pair；
注册、MQTT credential、N3-W application key、system peer trust 正确提交；
pairing window 关闭；
Board D 恢复正常网络运行；
后续再分别完成 MQTT/HA 与 Direct/Relay/RF 物理验收。

DEFERRED_OR_OUT_OF_SCOPE=
本 handoff 不执行 Wi-Fi 写入；
不打开 T1 pairing window；
不捕获/传输 Setup Secret；
不执行 first pair；
不执行 MQTT/HA/Direct/Relay/RF acceptance；
不执行 firmware/OTA/Flash/NVS erase；
不恢复 pre-reset NVS backup。
```

---

## 3. Frozen Authorities

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=507dbd49495c558b1344f7d713938b733b3bad18
TREE=NOT_REQUIRED_NEXT_GATE:exact main commit + exact deployed artifact hashes are sufficient

CANDIDATE_REF=NOT_APPLICABLE:no product-source candidate in Wi-Fi recovery gate
CANDIDATE_HEAD=NOT_APPLICABLE:no product-source candidate
CANDIDATE_TREE=NOT_APPLICABLE:no product-source candidate

ARTIFACT_ID=12478974186
ARTIFACT_SHA256=898ef722cd4af37ae5472583b1874f7724e9444e8837462d36f4e6be7eea092f

DEPLOYED_SOURCE_HEAD=ec5f6d68e33db7757d91c807fff708ca81b075dc
DEPLOYED_SOURCE_TREE=16740efa8ad24d423adc0b2de32b99d56e2d23d1

OTHER_REQUIRED_AUTHORITY=
Board D hardware_id_sha256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5;
Board D R4 release_bundle_sha256=b55aba9c3fad85da39eab63157c3de7c42f311970bfb61f8b0e9a52ddcba7dd5;
Board D partition_table_sha256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca;
Board D bootloader_sha256=ae9656d4a6fca0f1149d443b8ced537efe3b68af8fe600ef9ad9b8c9c7b2ca46;
Board D NVS range=0x790000+0x70000;
PR675 reviewed exact head=f5f8978f28324918329e337d79332fe08f28133c;
PR675 merge/main authority=507dbd49495c558b1344f7d713938b733b3bad18;
T1 production source_head=03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6;
T1 production source_tree=279914967d0368254e6c56283d59b182a0b8537a;
T1 release_id=c4df6f80d779f4091de6dc17df9e7c82131fe4c43da1f2e46df884b541e58b83;
T1 release_sha256=47afb04dd9b518218cc03fbbec47e21efb8599957f728e353a83010dff9d1a1b;
T1 SSH host-key sha256=2e6cae2b43ba5d7d0818fa53b4175a6bf58442077b32caf44b0bf886e6e4a901;
Issue #670 public-safe evidence comments=6405880277,6405935247。
```

公开 handoff 不保存 T1 私网地址、SSH 密码、Board D raw MAC/原始 fallback SSID、Wi-Fi SSID/password、Setup Secret、原始 pairing identity。

---

## 4. Current Live Baseline

交接前 fresh live evidence：

```text
MANAGER_STATE=RUNNING
MANAGER_RESTART_STATE=restart_count=0
BROKER_STATE=RUNNING;restart_count=0
HOMEASSISTANT_STATE=RUNNING;restart_count=0

T1_FACTORY_ACCEPTED=true
T1_PAIRING_WINDOW_STATE=CLOSED
T1_PAIRING_UDP_LISTENER_COUNT=0
T1_PAIRING_HTTP_LISTENER_COUNT=0
T1_TRANSACTION_PRESENT=false
T1_SUCCESSOR_RECOVERY_PRESENT=false

T1_REGISTRATIONS_COUNT=0
T1_PAIRING_SESSIONS_COUNT=0
T1_REGISTRATION_EVENTS_COUNT=0
T1_NODE_ID_LEASES_COUNT=0
T1_CREDENTIAL_ASSIGNMENTS_COUNT=0
T1_PEER_TRUST_RECORDS_COUNT=0
T1_APPLICATION_KEY_ACTIVE_NODES_COUNT=0
T1_APPLICATION_KEY_EPOCHS_COUNT=0

BOARD_D_POWER_STATE=ON_AFTER_COLD_BOOT
BOARD_D_APPLICATION_BOOT=PASS
BOARD_D_LCD_STATE=NORMAL
BOARD_D_USB_ENUMERATION=PASS
BOARD_D_FALLBACK_AP_ACTIVE=true
BOARD_D_SAVED_STA_WIFI_STATE=ABSENT_AFTER_FULL_NVS_ERASE
BOARD_D_NATIVE_API_OVER_PRIOR_STA=NOT_AVAILABLE_BEFORE_REPROVISIONING

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION_CURRENT_GATE=false
NVS_MUTATION_PREVIOUS_GATE=COMPLETED_SCOPED_FULL_NVS_ERASE
T1_RUNTIME_MUTATION=false
```

新会话必须 fresh recheck：

```text
REPOSITORY_MAIN=UNKNOWN_FRESH
REPOSITORY_MAIN_REQUIRES_FRESH_READONLY_RECHECK=true

T1_PAIRING_WINDOW_STATE=UNKNOWN_FRESH
T1_FIRST_PAIR_COUNTS=UNKNOWN_FRESH
T1_RUNTIME_BASELINE_REQUIRES_FRESH_READONLY_RECHECK=true

BOARD_D_FALLBACK_AP_ACTIVE=UNKNOWN_FRESH
BOARD_D_LCD_STATE=UNKNOWN_FRESH
BOARD_D_WIFI_STATE_REQUIRES_FRESH_READONLY_RECHECK=true
```

---

## 5. Proven Current Facts

```text
T1_FRESH_HOST_QUALIFICATION=PASS
T1_EXACT_PRODUCTION_EXECUTION=PASS
T1_PRODUCTION_READY=true

BOARD_D_SCOPED_NVS_RESET_SOURCE_GATE=CLOSED_PASS
BOARD_D_SCOPED_NVS_RESET_LIVE_PREBOOT=PASS
BOARD_D_NVS_BACKUP_SHA256=3614a0aac45bd6755407c90695788cb8e810e09eb6dd50517c510b5e0f924911
BOARD_D_NVS_BACKUP_NON_FF_BYTES=27719
BOARD_D_ERASED_PREBOOT_SHA256=6c28586364462df0ca5704154d2962e6d2a714a2443388b2a97220269188dcac
BOARD_D_ERASED_PREBOOT_NON_FF_BYTES=0
BOARD_D_BOOTLOADER_UNCHANGED=true
BOARD_D_PARTITION_TABLE_UNCHANGED=true
BOARD_D_APPLICATION_FLASH_REWRITE=false
BOARD_D_FULL_FLASH_ERASE=false
BOARD_D_RESET_PRIVATE_RESULT_SHA256=0ae18c57ef40bcecae86d6020c1b1c3809625e7370747154fe1873612c4dff8f

BOARD_D_RESET_AUTHORIZATION_CONSUMED=true
BOARD_D_RESET_REPLAY_ALLOWED=false

BOARD_D_POSTRESET_COLD_BOOT=PASS
BOARD_D_LCD_NORMAL=true
BOARD_D_FALLBACK_AP_OBSERVED=true

T1_POST_BOARD_D_RESET_BASELINE=PASS
T1_FIRST_PAIR_STATE_STILL_CLEAN=true
T1_PAIRING_WINDOW_CLOSED=true

PRIVATE_PRE_RESET_NVS_BACKUP_RETAINED=true
PRIVATE_PRE_RESET_NVS_BACKUP_RESTORE_ALLOWED=false
```

直接证据支持的根因事实：

```text
PROVEN_FULL_NVS_ERASE_SCOPE=true
PROVEN_WIFI_CONFIGURATION_WAS_LOST_AFTER_FULL_NVS_ERASE=true
PROVEN_BOARD_APPLICATION_FAILURE=false
PROVEN_BOARD_HARDWARE_FAILURE=false
```

不能继续沿用的旧推断：

```text
INFERENCE_SCOPED_PAIRING_NVS_ERASE_PRESERVES_WIFI=REJECTED_BY_LIVE_EVIDENCE
```

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=1
CURRENT_BLOCKER=BOARD_D_STA_WIFI_CONFIGURATION_ABSENT
ROOT_CAUSE=FULL_PRODUCT_NVS_ERASE_REMOVED_SAVED_WIFI_STATE_TOGETHER_WITH_PAIRING_STATE
PROVEN_BY=exact full-NVS preboot all-FF oracle + post-cold-boot fallback AP + normal LCD/application boot + exact R4 Wi-Fi configuration
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
```

这是 recovery prerequisite，不是 Board D 产品应用故障。当前正确路线是重新配置 Wi-Fi，而不是重新擦 NVS、重刷固件或修 Board。

---

## 7. Closed / Forbidden Routes

```text
REPLAY_SCOPED_NVS_RESET=CLOSED:authorization consumed; erased state already proven
RESTORE_PRE_RESET_NVS_BACKUP=CLOSED:would reintroduce stale pairing identity/Setup Secret state and old Wi-Fi state
ASSUME_WIFI_SURVIVES_FULL_NVS_ERASE=CLOSED:disproved by live evidence
BOARD_D_FIRMWARE_REFLASH=CLOSED:not justified; application cold boot/LCD/fallback AP are healthy
BOARD_D_HARDWARE_FAILURE=CLOSED:not supported by current evidence
SERIAL_PASSIVE_MONITORING=CLOSED:serial open can reset/disturb board and may expose raw pairing material
OPEN_T1_PAIRING_WINDOW_NOW=CLOSED:Wi-Fi recovery must finish first
REPLAY_OLD_WIFI_PROVISIONING_AUTH=CLOSED:consumed authorization is non-replayable
REPLAY_OLD_FIRST_PAIR_AUTH=CLOSED:any predecessor first-pair authorization is consumed/obsolete after T1 reinstall and Board D identity reset
```

---

## 8. Authorization Ledger

```text
AUTHORIZATION=N3W_T1_BOARD_D_SCOPED_PAIRING_NVS_RESET_20261025_01
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE

AUTHORIZATION=N3W_BOARD_D_FIRST_WIFI_PROVISIONING_ACCEPTANCE_20261024_01
CLAIMED=true
CONSUMED=true
RESULT=PASS_HISTORICAL_BEFORE_FULL_NVS_ERASE
REPLAY_PERMITTED=false
SUPERSEDED_BY=N3W_T1_BOARD_D_WIFI_REPROVISIONING_RECOVERY_20261026_01

PROPOSED_AUTHORIZATION=N3W_T1_BOARD_D_WIFI_REPROVISIONING_RECOVERY_20261026_01
GRANTED=false
```

新 Wi-Fi recovery authorization 只允许恢复 Board D 的 STA Wi-Fi 配置。它不包含 pairing window、Setup Secret、first pair、Flash、NVS erase 或 firmware mutation。

---

## 9. Rollback Authority

```text
ROLLBACK_BASELINE=
Board D cold-boots normally;
LCD normal;
fallback AP active;
T1 pairing window CLOSED;
T1 first-pair/security state all zero;
no current registration;
no pairing transaction.

FRESH_PRECHANGE_SNAPSHOT_REQUIRED=true

ROLLBACK_AUTHORITY_PATH_OR_ID=
fresh public-safe T1 inspect + fresh Board D fallback-AP/LCD state;
private pre-reset NVS backup is forensic-only and is NOT a restore authority.

RESTART_SCOPE_ALLOWED=
normal Board D restart/power-cycle only if required by the normal captive-portal Wi-Fi flow or post-write verification;
no Flash write;
no NVS erase;
no NVS raw restore;
no T1 service restart.

SECOND_ATTEMPT_ALLOWED=false
ROLLBACK_FAILURE_CLASS=ROLLBACK_INCOMPLETE
```

如果 Wi-Fi provisioning 失败：

- 不恢复旧 NVS；
- 不自动再次写入；
- 不打开 pairing window；
- 保持 T1 clean/CLOSED；
- STOP 并重新分类现场状态。

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_BOARD_D_WIFI_REPROVISIONING_RECOVERY_20261026_01
```

### Purpose

这一步只做一件事：把 Board D 在 full-NVS erase 后丢失的 STA Wi-Fi 配置重新写入，并证明 Board D 能重新进入正常局域网运行。

这一步现在必须先做，因为 first pair 需要 Board D 与 clean T1 在同一正常网络路径上通信。

这一步不能证明：

- first pair 成功；
- Setup Secret handoff 成功；
- registration/credential/key/peer-trust 成功；
- MQTT/HA telemetry 成功；
- Direct/Relay/RF 成功。

### Inputs

```text
BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
BOARD_D_PRODUCT_SOURCE_HEAD=ec5f6d68e33db7757d91c807fff708ca81b075dc
BOARD_D_ARTIFACT_ID=12478974186
BOARD_D_FALLBACK_AP_OBSERVED=true
BOARD_D_LCD_NORMAL=true
T1_FIRST_PAIR_STATE_CLEAN=true
T1_PAIRING_WINDOW=CLOSED
WIFI_CREDENTIAL_SOURCE=PRIVATE_OPERATOR_INPUT_NOT_GITHUB
```

### Operations

```text
1. fresh rebind repository main and this handoff; confirm no relevant product-source drift invalidates the current deployed Board D/T1 facts.
2. fresh read-only T1 onboarding inspect; require pairing window CLOSED, listeners 0, transaction absent, all first-pair/security counts 0.
3. fresh physical/read-only Board D check; require LCD normal and the expected fallback AP visible. Do not open serial.
4. archive/update the KF-131 known-failure guard if not already present; docs-only, no live mutation.
5. present exact proposed Wi-Fi recovery authorization and wait for explicit user approval.
6. after approval, user connects to the already-observed Board D fallback AP and uses the normal ESPHome captive portal to provide the private site Wi-Fi SSID/password. Never paste Wi-Fi password into chat or GitHub.
7. allow the normal product flow to save Wi-Fi state and reconnect. Do not erase NVS and do not restore the old backup.
8. discover the actual ESPHome mDNS service fresh; do not hard-code a hostname from MAC suffix as the sole oracle.
9. verify Board D network liveness via the normal ESPHome Native API path / TCP reachability without opening serial.
10. verify the fallback AP is no longer the active recovery path after successful STA reconnect, where observable.
11. rerun T1 read-only inspect and prove pairing remains CLOSED and first-pair/security state remains clean.
12. emit closure and STOP. Do not open pairing window or enter first pair automatically.
```

### PASS / FAIL / STOP

```text
PASS_IF=
fresh Board D identity/context remains unambiguous;
normal captive-portal Wi-Fi write succeeds under the new authorization;
Board D reconnects to site Wi-Fi;
fresh mDNS/Native API network liveness is proven;
LCD remains healthy;
T1 pairing window remains CLOSED;
T1 first-pair/security counts remain zero;
no Flash erase/write, raw NVS restore, pairing, Setup Secret transfer or T1 mutation occurs.

FAIL_IF=
wrong/ambiguous board;
fallback AP unexpectedly absent before mutation without an alternate proven normal STA path;
Wi-Fi write is not proven;
Board D fails to reconnect;
application/LCD becomes unhealthy;
T1 pairing state changes;
any forbidden mutation occurs;
authorization replay or second automatic attempt is attempted.

STOP_BOUNDARY=
structured Wi-Fi recovery closure after PASS or FAIL;
do not enter first-pair preparation or pairing-window activation in the same authorization.

AUTO_EXECUTE_NEXT_GATE=false
```

---

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

只在用户明确批准 `N3W_T1_BOARD_D_WIFI_REPROVISIONING_RECOVERY_20261026_01` 后：

```text
- manual connection to the already-observed Board D fallback AP
- normal ESPHome captive-portal Wi-Fi provisioning
- writing only the Wi-Fi configuration produced by that normal product flow
- normal board restart/reconnect caused by that product flow
- read-only mDNS / Native API / TCP liveness checks
- read-only T1 onboarding inspect
- bounded private local evidence that does not expose Wi-Fi password, Setup Secret or raw pairing identity
```

授权前允许：

```text
- repository read-only rebind
- T1 read-only inspect
- Board D visual/fallback-AP presence check
- docs-only KF-131 alignment
```

### FORBIDDEN

```text
- replay N3W_T1_BOARD_D_SCOPED_PAIRING_NVS_RESET_20261025_01
- any erase-region / erase-flash
- raw NVS restore
- restoring the private pre-reset NVS backup
- firmware/OTA/app/bootloader/partition-table/otadata write
- serial passive monitoring
- factory reset / triple reset
- T1 pairing-window open
- Setup Secret capture/import/delivery
- first pair
- Manager/Broker/HA mutation
- credential/key/peer-trust mutation
- MQTT/HA/Direct/Relay/RF acceptance
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=private local hashes/status only; no secret values
```

---

## 12. Execution Contract

```text
EXECUTOR=HIGH_LEVEL_MODEL_DIRECT_ORCHESTRATION_WITH_MAC_TERMINAL_OPERATOR
EXECUTION_METHOD=manual-physical
DIRECT_CODE_SUPPLIED=true
DSL_COMPILATION_USED=false

CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=true
```

执行原则：

- 新会话先做最小 fresh 只读确认；
- 用户是物理操作者；
- Wi-Fi SSID/password 始终由用户直接在 captive portal 输入，不进入聊天命令；
- 能用现有系统工具完成时不新增 executor；
- 只有 fresh evidence 决定后续是否安全时才拆步；
- 不自动跨入 first-pair gate。

---

## 13. Expected Closure

```text
=== N3W_T1_BOARD_D_WIFI_REPROVISIONING_RECOVERY CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=N3W_T1_BOARD_D_WIFI_REPROVISIONING_RECOVERY_20261026_01
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=

MAIN=
BOARD_D_IDENTITY_BOUND=
PRECHANGE_FALLBACK_AP=
PRECHANGE_LCD=
PRECHANGE_T1_PAIRING_CLOSED=
PRECHANGE_T1_FIRST_PAIR_CLEAN=

WIFI_PROVISIONING_STARTED=
WIFI_PROVISIONING_RESULT=
BOARD_D_STA_RECONNECTED=
BOARD_D_MDNS_DISCOVERY=
BOARD_D_NATIVE_API_LIVENESS=
BOARD_D_LCD_HEALTHY=
FALLBACK_AP_POSTSTATE=

POST_T1_PAIRING_CLOSED=
POST_T1_FIRST_PAIR_CLEAN=

FLASH_WRITE=false
NVS_ERASE=false
RAW_NVS_RESTORE=false
T1_RUNTIME_MUTATION=false
PAIRING_EXECUTION=false
SETUP_SECRET_TRANSFER=false

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=true

WIFI_REPROVISIONING_GATE_RESULT=
NEXT_ROUTE=
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=N3W_T1_BOARD_D_FIRST_PAIR_PREPARATION_AND_NEW_AUTHORIZATION
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

PASS 后的新阶段必须先解决 KF-043/KF-044 类顺序问题：

- 在产生/使用 fresh pairing identity 前预置 hash-safe identity observation；
- 预置 Setup Secret 私密 capture；
- 预置 pending TTL pretransfer/predelivery 双 gate；
- 预置敏感传输/原子消费路径；
- 然后申请全新的 first-pair authorization。

不得在 Wi-Fi recovery PASS 后直接打开 pairing window。

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=true
EXISTING_KF_GUARD_USED=KF-042,KF-043,KF-044,KF-046,KF-129
NEW_KF_REQUIRED=true

KF_ID=KF-131
SYMPTOM=Board D scoped pairing-state reset completed correctly, but after application start prior STA network/native API disappeared; cold boot showed normal LCD/application plus fallback AP.
ROOT_CAUSE=The reviewed reset erased the entire product NVS partition 0x790000+0x70000. The design treated that range as pairing-reset scope, but the same NVS also contained ESPHome persisted Wi-Fi state. Full-NVS erase therefore removed Wi-Fi configuration together with pairing state.
FIX_OR_GUARD=Never claim Wi-Fi continuity after whole-product-NVS erase unless proven on the exact image. After full NVS erase, expect/verify fallback AP and run a separate newly-authorized Wi-Fi reprovisioning gate. Pre-reset private NVS backup is forensic-only and must not be restored because it would reintroduce stale pairing/Setup Secret state. Future pairing-only reset design should erase only exact pairing keys/namespaces or otherwise explicitly account for Wi-Fi loss.
STATUS=OPEN_GUARDED_BY_CURRENT_HANDOFF_PENDING_KNOWN_FAILURES_TABLE_ALIGNMENT
```

---

## 16. New Chat Start Prompt

```text
阅读：

docs/development/N3W_BOARD_D_WIFI_REPROVISIONING_RECOVERY_NEW_CHAT_HANDOFF_V1.0_20261026.md

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

读取 exact handoff standard authority：
4300890dff0ce63d5a547df21426e287d084d9ee
- docs/development/NEW_CHAT_HANDOFF_STANDARD.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3W_T1_DYNAMIC_FIRST_PAIRING_CLEAN_ARMBIAN_REINSTALL_AND_EXACT_RELEASE_ACCEPTANCE
当前任务：N3W_T1_BOARD_D_WIFI_REPROVISIONING_RECOVERY_20261026_01

先承认并保持：
- 当前 formal handoff template 是 V1.3，blob=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0；
- historical 4300890d... 只作为 exact handoff standard authority；
- repository main 在交接时为 507dbd49495c558b1344f7d713938b733b3bad18，必须 fresh rebind；
- T1 exact production ready；
- T1 post-Board-D-reset inspect PASS，pairing window CLOSED，47111/47112 closed，first-pair/security counts 全 0；
- Board D scoped full-NVS reset已 PASS，reset authorization consumed，禁止重放；
- Board D pre-reset private NVS backup 只作 forensic evidence，禁止 restore；
- Board D 冷启动 application/LCD/USB 正常，fallback AP 已观察到；
- full NVS erase 同时清掉了保存的 Wi-Fi 配置；
- 不能再假设“pairing NVS reset 会保留 Wi-Fi”；
- 旧 Wi-Fi provisioning authorization 已 consumed，不能重放；
- 新 Wi-Fi recovery authorization 尚未 granted；
- 不打开串口监视器；
- 不打开 T1 pairing window；
- 不进入 Setup Secret/first-pair，直到 Wi-Fi recovery 单独 PASS 并 STOP。

NEXT_ONE_GATE=
N3W_T1_BOARD_D_WIFI_REPROVISIONING_RECOVERY_20261026_01

PROPOSED_AUTHORIZATION=
N3W_T1_BOARD_D_WIFI_REPROVISIONING_RECOVERY_20261026_01

GRANTED=false

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

先做当前 gate 所需的最小 fresh 只读确认：
1. fresh repository/main/handoff rebind；
2. fresh T1 onboarding inspect；
3. fresh Board D LCD + fallback AP presence；
4. 如 KNOWN_FAILURES 尚无 KF-130，先做 docs-only alignment；
5. 然后给出 exact Wi-Fi recovery mutation scope，并等待我明确授权。

不要重放 consumed authorization，不要 restore old NVS，不要自动跨越到 first pair。
```

如新会话需要私有 T1 locator、现场 Wi-Fi credential 或 exact fallback AP SSID，应从用户私有上下文/现场重新取得，不从公开 GitHub 推断或保存。

---

## 17. Final Frozen State

```text
CURRENT_STAGE=BOARD_D_POST_SCOPED_NVS_RESET_WIFI_RECOVERY
CURRENT_STOP_POINT=BOARD_D_COLD_BOOT_APPLICATION_PASS_FALLBACK_AP_ACTIVE
CURRENT_BLOCKER=BOARD_D_STA_WIFI_CONFIGURATION_ABSENT

LIVE_SYSTEM_STATE=
T1 exact production ready and healthy;
T1 pairing window CLOSED;
T1 first-pair/security state clean;
Board D application cold-boot PASS;
Board D LCD normal;
Board D fallback AP active;
Board D saved STA Wi-Fi state absent;
no first-pair transaction active.

NEXT_ONE_GATE=N3W_T1_BOARD_D_WIFI_REPROVISIONING_RECOVERY_20261026_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.1
HANDOFF_TEMPLATE_VERSION=1.3

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

Private material deliberately not committed:

```text
PRIVATE_PRE_RESET_NVS_BACKUP=RETAINED_OUTSIDE_GITHUB
PRIVATE_PRE_RESET_NVS_BACKUP_SHA256=3614a0aac45bd6755407c90695788cb8e810e09eb6dd50517c510b5e0f924911
PRIVATE_BACKUP_REASON=contains private persistent device/network/pairing state
PRIVATE_BACKUP_RESTORE_ALLOWED=false

PRIVATE_WIFI_CREDENTIALS=USER_MANAGED_OUTSIDE_GITHUB
PRIVATE_T1_LOCATOR=USER_MANAGED_OUTSIDE_GITHUB
RAW_PAIRING_ID=NOT_PUBLIC
SETUP_SECRET=NOT_PUBLIC
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


---

## 19. Executed Wi-Fi Recovery Closure — 2026-10-26

```text
=== N3W_T1_BOARD_D_WIFI_REPROVISIONING_RECOVERY CLOSURE ===

EXECUTION_ID=N3W_T1_BOARD_D_WIFI_REPROVISIONING_RECOVERY_20261026_01
AUTHORIZATION=N3W_T1_BOARD_D_WIFI_REPROVISIONING_RECOVERY_20261026_01
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true

MAIN=507dbd49495c558b1344f7d713938b733b3bad18
BOARD_D_IDENTITY_BOUND=true
PRECHANGE_FALLBACK_AP=PASS
PRECHANGE_LCD=PASS
PRECHANGE_T1_PAIRING_CLOSED=true
PRECHANGE_T1_FIRST_PAIR_CLEAN=true

WIFI_PROVISIONING_STARTED=true
WIFI_PROVISIONING_RESULT=PASS
BOARD_D_STA_RECONNECTED=true
BOARD_D_MDNS_DISCOVERY=PASS:gh-912224
BOARD_D_NATIVE_API_LIVENESS=PASS:TCP_6053
BOARD_D_LCD_HEALTHY=true
FALLBACK_AP_POSTSTATE=GONE

POST_T1_PAIRING_CLOSED=true
POST_T1_FIRST_PAIR_CLEAN=true

FLASH_WRITE=false
NVS_ERASE=false
RAW_NVS_RESTORE=false
T1_RUNTIME_MUTATION=false
PAIRING_EXECUTION=false
SETUP_SECRET_TRANSFER=false

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=true

WIFI_REPROVISIONING_GATE_RESULT=CLOSED_PASS
NEXT_ROUTE=N3W_T1_BOARD_D_FIRST_PAIR_PREPARATION_AND_NEW_AUTHORIZATION
STOP=true

=== END ===
```

Closure notes:

- The single authorized captive-portal Wi-Fi reprovisioning attempt was executed once and is non-replayable.
- Fresh mDNS discovery resolved `gh-912224._esphomelib._tcp.local.` to `gh-912224.local.:6053`; TCP reachability to the discovered ESPHome Native API endpoint passed.
- Final T1 onboarding inspect remained PASS with pairing window CLOSED, UDP/HTTP pairing listeners 0, all first-pair/security counts 0, no transaction/successor recovery, Broker/Manager/Home Assistant running with restart_count 0, and `mutation=false`.
- This closure does not authorize or execute pairing-window activation, Setup Secret transfer, first pair, MQTT/HA acceptance, Direct/Relay acceptance, or RF acceptance.
- Per the frozen handoff, the next stage is preparation plus a new authorization for first pair; it must not auto-start from this closure.
