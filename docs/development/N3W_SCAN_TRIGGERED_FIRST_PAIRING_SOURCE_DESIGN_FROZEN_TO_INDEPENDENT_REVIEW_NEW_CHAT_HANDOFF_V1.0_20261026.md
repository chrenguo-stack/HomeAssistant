# 温室环境监测系统（ESP32-C6）
# N3-W / 扫码触发联机注册 source design 冻结 → 独立复核
# 新会话交接文档 V1.0 — 2026-10-26

```text
HANDOFF_TEMPLATE_VERSION=1.3
HANDOFF_TEMPLATE_BLOB=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0
PROJECT_WORKING_CONTEXT_VERSION=1.1
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md

HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
HANDOFF_STANDARD_PATH=docs/development/NEW_CHAT_HANDOFF_STANDARD.md

EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文严格使用当前 `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.3 / blob
> `b9ef40acdaa8fae37feb5ffe5662afd0e89462a0`。
> exact handoff standard 仍按历史 authority commit
> `4300890dff0ce63d5a547df21426e287d084d9ee` 读取。
> 本文只保存当前阶段增量；长期工作规则统一引用 `N3W_PROJECT_WORKING_CONTEXT.md`。
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并先 STOP。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=SCAN_TRIGGERED_FIRST_REGISTRATION_SOURCE_DESIGN
CURRENT_STOP_POINT=SOURCE_DESIGN_FROZEN_AND_CI_PASS
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_INDEPENDENT_REVIEW_20261026_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

本轮已经完成产品流程纠偏、架构 review、source design 和用户最终确认。对话已经较长，因此在“设计冻结、实现尚未开始”的清晰 STOP 点切换会话。

下一会话不是重新讨论产品需求，也不是直接写代码，而是从 frozen source design 做一次独立源码/架构复核。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.1
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=4
STAGE_OVERRIDES=
1) PR #679 后续 handoff/docs-only 提交可以推进 branch HEAD，但 SOURCE_DESIGN_FROZEN_HEAD=2361bdfb... 仍是独立复核的 exact design authority；
2) “47110/47111 常驻、47112 idle closed”是目标产品设计，不得误报为当前 live T1 已实现；
3) 用户界面术语冻结为“联机注册”，但内部 pairing/registration/Setup Secret 协议命名不做无意义全局重命名；
4) 节点退役架构保留，但当前不开发新的 retirement 功能。
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=
generic factory node
→ Wi-Fi provisioning
→ LCD 联机注册 QR
→ idle node does not discover T1
→ phone camera opens node-local page
→ scan request triggers bounded T1 discovery
→ user chooses/confirms local T1
→ node automatically hands Setup Secret to selected T1
→ one exact identity/source-bound first-registration transaction
→ encrypted credential/key/trust delivery
→ Manager COMMIT
→ LCD 注册成功
→ normal product runtime

FINAL_ACCEPTANCE_TARGET=
普通用户只使用节点 LCD + 手机系统相机 + 极简本地浏览器页面，
不安装专用 App，
不进入后台，
不输入 IP/端口，
不使用 SSH/CLI，
不复制 raw QR/Setup Secret，
即可顺序完成 A/B/C 等多个节点的首次联机注册；
每台节点事务独立、成功即关闭敏感窗口、下一台重新获得完整 1800 秒。

DEFERRED_OR_OUT_OF_SCOPE=
new node-retirement development;
Home Assistant user-management UI;
dedicated mobile app;
second Board D first-pair attempt before product flow implementation;
Direct/Relay/RF revalidation;
live T1 deployment;
board flash/NVS work;
PR merge without explicit authorization。
```

---

## 3. Frozen Authorities

### 3.1 Repository / exact-main

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=507dbd49495c558b1344f7d713938b733b3bad18
TREE=FRESH_REBIND_REQUIRED

HANDOFF_TEMPLATE_VERSION=1.3
HANDOFF_TEMPLATE_BLOB=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0
HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
```

### 3.2 Candidate design authority

```text
CANDIDATE_REF=PR#679 / docs/n3w-scan-triggered-first-pairing-source-design-20261026
SOURCE_DESIGN_FROZEN_HEAD=2361bdfbd30d6ad2ede8c52e830cf1902edb4f86
SOURCE_DESIGN_FROZEN_CI=13_OF_13_SUCCESS

ADR0011_PATH=docs/adr/0011-n3w-scan-triggered-first-registration.md
ADR0011_BLOB=b5e27296f273e2eda415f9b31e44516c57269bb4

SOURCE_DESIGN_PATH=docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026.md
SOURCE_DESIGN_BLOB=26533c3091b664e609e06704876b820cfefb276d

PR679_CURRENT_HEAD=FRESH_REBIND_REQUIRED:handoff/docs-only advancement follows frozen design head
PR679_STATE=OPEN_DRAFT
PR679_MERGE_AUTHORIZED=false
```

Predecessor architecture review:

```text
PR678=OPEN_DRAFT
PR678_HEAD=93960e0af24cd9ad68b67518cbb002836362723a
ARCH_REVIEW_PATH=docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_AND_LCD_FEEDBACK_ARCHITECTURE_REVIEW_20261026.md
```

### 3.3 Related Board D identity authority

```text
RUNTIME_BOARD_D_HARDWARE_ID_SHA256=3a76b39f066e09de0a285b81319eec20f29c8fd4136b61dc5a86ace01c1e1d55
HISTORICAL_FROZEN_3991_AUTHORITY=INVALID_AS_PRODUCT_HARDWARE_ID
IDENTITY_ROOT_CAUSE=ESPTOOL_EUI64_TRUNCATED_TO_FAKE_6_BYTE_MAC

PR677=OPEN_DRAFT
PR677_HEAD=032f4f1dd339997ad83a7946f742e4d50a388d5a
PR677_LAST_SOURCE_TEST_HEAD=d6745d39881d50864b6f90b04ea36b2c4c548d3f
PR677_SOURCE_CI=14_OF_14_SUCCESS
BOARD_D_PHYSICAL_IDENTITY_REVALIDATION=PENDING
```

### 3.4 Artifact / runtime authority

```text
ARTIFACT_ID=NOT_APPLICABLE:next gate is docs/source independent review
ARTIFACT_SHA256=NOT_APPLICABLE

DEPLOYED_SOURCE_HEAD=NOT_REQUIRED_FOR_NEXT_GATE
DEPLOYED_SOURCE_TREE=NOT_REQUIRED_FOR_NEXT_GATE

SUCCESSOR_AUTHORITY=NOT_APPLICABLE:next gate is read-only design review
```

公开 handoff 不保存 T1/Board 私网 locator、SSH 信息、raw hardware ID、raw pairing ID、QR payload 或 Setup Secret。

---

## 4. Current Live Baseline

本轮 source-design 阶段没有重新访问 live T1/Board，因此不得把历史状态冒充 fresh 当前状态。

最后一次直接 live first-pair closure 已证明：

```text
LAST_PROVEN_FIRST_PAIR_RESULT=CLOSED_ABORTED
LAST_PROVEN_PAIRING_WINDOW_FINAL=CLOSED_ABORTED
LAST_PROVEN_PAIRING_LISTENER_COUNT=0
LAST_PROVEN_SECURITY_CREDENTIAL_ASSIGNMENTS=0
LAST_PROVEN_SECURITY_PEER_TRUST_RECORDS=0
LAST_PROVEN_SECURITY_APPLICATION_KEY_ACTIVE_NODES=0
LAST_PROVEN_SECURITY_APPLICATION_KEY_EPOCHS=0

FIRST_PAIR_AUTHORIZATION_CLAIMED=true
FIRST_PAIR_AUTHORIZATION_CONSUMED=true
FIRST_PAIR_AUTHORIZATION_REPLAY_ALLOWED=false

BOARD_D_RUNTIME_IDENTITY_SHA256=3a76b39f066e09de0a285b81319eec20f29c8fd4136b61dc5a86ace01c1e1d55
QR_T1_ARP_RUNTIME_IDENTITY_CROSS_BINDING=PASS
```

交接时 current live state：

```text
MANAGER_STATE=UNKNOWN_FRESH
MANAGER_RESTART_STATE=UNKNOWN_FRESH
BROKER_STATE=UNKNOWN_FRESH
HOMEASSISTANT_STATE=UNKNOWN_FRESH

PAIRING_WINDOW_STATE=UNKNOWN_FRESH
PAIRING_DATABASE_STATE=UNKNOWN_FRESH
BOARD_D_NETWORK_STATE=UNKNOWN_FRESH
BOARD_D_LCD_STATE=UNKNOWN_FRESH

APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
T1_RUNTIME_MUTATION=false
PAIRING_EXECUTION=false
BOARD_ACCESS=false
```

```text
LIVE_STATE_REQUIRES_FRESH_READONLY_RECHECK_BEFORE_ANY_FUTURE_LIVE_GATE=true
LIVE_RECHECK_NOT_REQUIRED_FOR_NEXT_SOURCE_DESIGN_REVIEW=true
```

---

## 5. Proven Current Facts

```text
PRODUCT_UI_TERM=联机注册

WIFI_PROVISIONED_UNREGISTERED_QR_SHOULD_BE_ALWAYS_AVAILABLE=true
IDLE_NODE_ACTIVE_T1_DISCOVERY=false
SCAN_REQUEST_TRIGGERS_T1_DISCOVERY=true
USER_CONFIRM_TRIGGERS_FIRST_REGISTRATION_TRANSACTION=true

DEDICATED_APP_REQUIRED=false
NORMAL_USER_BACKEND_ACCESS=false
NORMAL_USER_CLI_ACCESS=false
MANUAL_IP_INPUT=false
MANUAL_SECRET_COPY=false

PHONE_ROLE=CAMERA_SCAN_PLUS_MINIMAL_BROWSER_CONFIRM
LCD_PRIMARY_PROGRESS_FEEDBACK=true
LCD_PRIMARY_FAILURE_FEEDBACK=true

T1_TARGET_47110_BOOTSTRAP_ALWAYS_ON=true
T1_TARGET_47111_DISCOVERY_ALWAYS_ON=true
T1_TARGET_47112_PAIRING_IDLE_CLOSED=true

SETUP_SECRET_PHONE_EXPOSURE=false
SETUP_SECRET_NODE_TO_T1_TLS=true
TLS_CERTIFICATE_PIN_CHECK_REQUIRED_BEFORE_SECRET_BODY=true

FIRST_REGISTRATION_TTL_SECONDS=1800
FIRST_REGISTRATION_TTL_SCOPE=PER_TRANSACTION
MAX_CONCURRENT_FIRST_REGISTRATIONS_V1=1
SUCCESS_CLOSES_PRIVILEGED_WINDOW_IMMEDIATELY=true
UNUSED_TTL_CARRIED_FORWARD=false
NEXT_NODE_REQUIRES_NEW_CONFIRMATION=true
NEXT_NODE_GETS_FRESH_1800S_DEADLINE=true

ORDINARY_REPAIR_TTL_UNCHANGED=true
NODE_RETIREMENT_NEW_DEVELOPMENT=DEFERRED
```

A/B/C 顺序注册冻结语义：

```text
A_CONFIRM
→ Transaction-A deadline=A_confirm+1800
→ A commits at e.g. 80 s
→ Transaction-A closes immediately
→ remaining A time discarded

B_CONFIRM
→ fresh Transaction-B
→ fresh B_confirm+1800 deadline

B while A active
→ registration_busy
→ B pre-transaction pairing identity not consumed/renewed
```

当前实现偏差已有源码直接证据：

```text
CURRENT_IDLE_AUTO_DISCOVERY_PRESENT=true
CURRENT_QR_VISIBILITY_GATED_BY_PAIRING_HANDOFF_READY=true
CURRENT_PAIRING_HANDOFF_READY_REQUIRES_MANAGER_HELLO_PROCEED=true
CURRENT_ENGINEERING_RAW_QR_TO_TERMINAL_FLOW_NOT_PRODUCT_ACCEPTABLE=true
CURRENT_T1_DISCOVERY_AND_PRIVILEGED_PAIRING_RUNTIME_COUPLED=true
CURRENT_DYNAMIC_WINDOW_REQUIRES_OPERATOR_PEER_IP=true
CURRENT_FIRST_PAIR_TIMERS_CONFLICT_120_300_600=true
```

---

## 6. Current Root Cause / Blockers

### Blocker A — source design has not received independent closure review

```text
ROOT_CAUSE=NEW_PRODUCT_ARCHITECTURE_NOT_YET_INDEPENDENTLY_REVIEWED
PROVEN_BY=PR#679 frozen design exists but no independent closure result yet
SOURCE_DEFECT_PROVEN=NOT_APPLICABLE
RUNTIME_DEFECT_PROVEN=false
```

### Blocker B — product implementation does not yet match frozen design

```text
ROOT_CAUSE=CURRENT_IMPLEMENTATION_IS_PREDECESSOR_ENGINEERING_FLOW
PROVEN_BY=current firmware/Manager source inspection
SOURCE_DEFECT_PROVEN=true
RUNTIME_DEFECT_PROVEN=NOT_REQUIRED_FOR_SOURCE_DESIGN
```

### Blocker C — Board D physical identity source repair is not yet merged/physically revalidated

```text
ROOT_CAUSE=HISTORICAL_PHYSICAL_IDENTITY_PARSER_FALSE_PASS
PROVEN_BY=QR/T1/ARP cross-binding + esptool v5.3.1 source behavior + PR#677 repair
SOURCE_DEFECT_PROVEN=true
RUNTIME_PRODUCT_IDENTITY_CHAIN_PROVEN=true
PHYSICAL_BASE_MAC_REVALIDATION=PENDING
```

```text
CURRENT_BLOCKER_COUNT=3
SECOND_BOARD_D_FIRST_PAIR_ELIGIBLE=false
```

Blocker C does not block the next docs/source review; it must be closed before later physical acceptance.

---

## 7. Closed / Forbidden Routes

```text
IDLE_LCD_正在查找主机=CLOSED:superseded product behavior
QR_VISIBILITY_REQUIRES_MANAGER_DISCOVERY=CLOSED:product mismatch
IDLE_UNREGISTERED_AUTO_DISCOVERY=CLOSED:user scan must trigger discovery
RAW_GHN3W2_COPY_TO_TERMINAL_PRODUCT_FLOW=CLOSED:engineering-only
NORMAL_USER_CLI_OR_BACKEND_FLOW=CLOSED:violates product north star
NORMAL_USER_MANUAL_PEER_IP=CLOSED:product path derives source IP automatically
PHONE_RECEIVES_SETUP_SECRET=CLOSED:secret remains node/T1 only
PAIRING_30_MINUTE_GLOBAL_MODE=CLOSED:TTL is per transaction
MULTIPLE_NODES_SHARE_ONE_OPEN_WINDOW=CLOSED:V1 max concurrency=1
AUTO_SELECT_MULTIPLE_T1=CLOSED:user must select
REUSE_FIRST_PAIR_AUTHORIZATION=CLOSED:consumed and non-replayable
REUSE_ABORTED_QR_OR_SETUP_SECRET=CLOSED:forbidden
SECOND_BOARD_D_FIRST_PAIR_NOW=CLOSED:wait for product-flow implementation/acceptance route
WHOLE_NVS_RESET=CLOSED:not part of current route
NEW_RETIREMENT_DEVELOPMENT=CLOSED_FOR_CURRENT_SCOPE:deferred
AUTO_MERGE_PR677_PR678_PR679=CLOSED:explicit user authorization required
```

---

## 8. Authorization Ledger

```text
AUTHORIZATION=N3W_T1_FIRST_PAIRING_BOARD_D_LIVE_ACCEPTANCE_20261026_01
CLAIMED=true
CONSUMED=true
RESULT=CLOSED_ABORTED
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE

AUTHORIZATION=N3W_T1_BOARD_D_WIFI_REPROVISIONING_RECOVERY_20261026_01
CLAIMED=true
CONSUMED=true
RESULT=CLOSED_PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE

AUTHORIZATION=N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026_01
CLAIMED=NOT_APPLICABLE:DOCS_SOURCE_DESIGN
CONSUMED=NOT_APPLICABLE
RESULT=CLOSED_FROZEN
REPLAY_PERMITTED=NOT_APPLICABLE
SUPERSEDED_BY=NONE

PROPOSED_AUTHORIZATION=NONE:next gate is read-only independent review
GRANTED=false
```

No previous live/physical authorization may be reused for future physical acceptance.

---

## 9. Rollback Authority

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_GATE
```

The next gate must not modify:
- product source;
- live T1;
- Board firmware/NVS;
- credentials;
- services;
- pairing state;
- PR merge state.

A docs-only review record/comment may be written after the review result is known; this is evidence archival, not product mutation.

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_INDEPENDENT_REVIEW_20261026_01
```

### Purpose

Independently challenge the frozen PR #679 design against current repository source and the retained ADR-0007/ADR-0008 security contracts.

This gate must determine whether the design is coherent and implementable **before any product source implementation starts**.

It cannot merge PR #679, modify product source, access live T1/Board, or authorize physical execution.

### Inputs

```text
REPOSITORY_MAIN=507dbd49495c558b1344f7d713938b733b3bad18
PR679_SOURCE_DESIGN_FROZEN_HEAD=2361bdfbd30d6ad2ede8c52e830cf1902edb4f86
ADR0011_BLOB=b5e27296f273e2eda415f9b31e44516c57269bb4
SOURCE_DESIGN_BLOB=26533c3091b664e609e06704876b820cfefb276d

ADR0007=docs/adr/0007-n3w-security-simplification-long-lived-peer-trust.md
ADR0008=docs/adr/0008-n3w-pairing-recovery-simplification-v2.md

CURRENT_IMPLEMENTATION_FILES=
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_product_component.cpp;
firmware/esphome_rc/components/greenhouse_n3w_core/n3w_simple_pairing_client.cpp;
firmware/esphome_rc/f1_0_rc2/packages/n3w_product_transport.yml;
host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_dynamic_pairing_window.py;
host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_simplified_pairing.py;
host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_simplified_pairing_endpoint.py;
host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_simplified_pairing_runtime.py;
host/greenhouse-manager/src/greenhouse_manager/runtime/registration.py。
```

### Operations

```text
1. fresh rebind repository main and PR #679;
2. prove handoff/docs-only commits after frozen head do not alter ADR0011/source-design blobs;
3. independently read frozen ADR/source design and current implementation; do not accept PR comments as proof;
4. review A1 idle QR / no background discovery;
5. review A2 node-local app-less portal and scan-token boundary;
6. review A3 always-on low-privilege 47110/47111 vs privileged 47112 split and attack surface;
7. review A4 TLS user-confirmed TOFU / pre-body leaf-fingerprint pinning feasibility and residual risk;
8. review A5 Setup Secret lifecycle, zeroization and automatic node→T1 handoff;
9. review A6 hardware_id + pairing_id + source_ip binding before any durable registration mutation;
10. review A7 one canonical 1800 s per-transaction deadline across intent/window/registration/session, with V1 concurrency=1;
11. review A8 A/B/C sequential-registration semantics and busy behavior;
12. review A9 LCD/error mapping and phone-only normal UX;
13. review A10 ADR-0007/0008 successor authority and absence of accidental security regression;
14. search current tests/workflows/docs for stale assumptions such as idle UDP47111=0, max window=600, pending/session TTL=120, raw QR handoff;
15. classify each issue as BLOCKER / NONBLOCKING / NO_ISSUE;
16. output structured closure and STOP.
```

External official ESP-IDF/ESPHome documentation may be consulted only where implementation feasibility materially depends on it, and must be distinguished from repository-derived facts.

### PASS / FAIL / STOP

```text
PASS_IF=
all A1-A10 closed;
no unaddressed secret-exposure or pre-DB identity-binding false-PASS;
1800 s deadline propagation implementable without widening ordinary repair;
47110/47111 exposure has bounded source-design controls;
TLS pinning can be enforced before Setup Secret body transmission;
no hidden dependency requires a dedicated app or manual backend operation.

FAIL_IF=
any security boundary depends on post-secret verification;
Setup Secret must enter phone/browser to make design work;
wrong-node traffic can create durable registration before exact binding;
a hidden 120/600 s timeout remains authoritative;
always-on discovery requires privileged pairing exposure;
browser/scan trigger cannot be bounded without changing product assumptions;
ADR successor authority is contradictory or incomplete.

STOP_BOUNDARY=
independent closure only;
no source implementation;
no PR merge;
no live access.

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
- GitHub read-only repository/PR/history/source/test/workflow inspection
- exact blob/commit/diff verification
- read-only official technical documentation where necessary
- bounded local reasoning/simulation
- docs-only independent-review evidence/comment after classification
```

### FORBIDDEN

```text
- product source edits
- firmware build/write/OTA
- T1 SSH/live access
- Docker/service mutation
- credential/SQLite mutation
- pairing window open
- Setup Secret transfer
- Board USB/serial/Flash/NVS/RF access
- second first-pair attempt
- merge PR #677/#678/#679
- new retirement development
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=public-safe docs-only independent-review record on PR #679 if needed
```

---

## 12. Execution Contract

```text
EXECUTOR=HIGH_LEVEL_MODEL_WITH_GITHUB_READONLY_TOOLS
EXECUTION_METHOD=chat-tool
DIRECT_CODE_SUPPLIED=false
DSL_COMPILATION_USED=false

CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=false
```

Independent review must remain independent:
- do not silently repair the design while reviewing it;
- if a blocker is found, record it and STOP;
- minor wording-only documentation issues may be classified NONBLOCKING but not used to conceal a design defect.

No live evidence is required for this gate.

---

## 13. Expected Closure

```text
=== N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_INDEPENDENT_REVIEW CLOSURE ===

EXECUTION_ID=N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_INDEPENDENT_REVIEW_20261026_01
AUTHORIZATION=NOT_REQUIRED_READONLY
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

REPOSITORY_MAIN=
PR679_CURRENT_HEAD=
SOURCE_DESIGN_FROZEN_HEAD=
FROZEN_BLOB_BINDING=

A1_IDLE_QR_NO_BACKGROUND_DISCOVERY=
A2_NODE_LOCAL_APPLESS_PORTAL=
A3_PASSIVE_DISCOVERY_VS_PAIRING_EXPOSURE=
A4_TLS_TOFU_PREBODY_PINNING=
A5_SETUP_SECRET_LIFECYCLE=
A6_PRE_DB_IDENTITY_SOURCE_BINDING=
A7_PER_TRANSACTION_1800S_DEADLINE=
A8_SEQUENTIAL_MULTI_NODE_SEMANTICS=
A9_LCD_PHONE_ONLY_UX=
A10_ADR_SUCCESSOR_SECURITY_CONTINUITY=

STALE_ASSUMPTION_COUNT=
NEW_BLOCKER_COUNT=
NONBLOCKING_FINDING_COUNT=

SOURCE_DESIGN_REPAIR_REQUIRED=
PR679_MERGE_READY=

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

GATE_RESULT=
NEXT_ROUTE=
STOP=true

=== END ===
```

---

## 14. After PASS / FAIL

```text
AFTER_PASS_NEXT_STAGE=PR679_EXPLICIT_MERGE_AUTHORIZATION_THEN_SOURCE_IMPLEMENTATION_R1
AUTO_EXECUTE_AFTER_PASS=false
NEW_AUTHORIZATION_REQUIRED=true

AUTO_REPAIR_AFTER_FAIL=false
AUTO_RETRY_AFTER_FAIL=false
STOP_AND_REVIEW_AFTER_FAIL=true
```

Planned later route after independent PASS and explicit PR #679 merge authorization; **not executable from this handoff**:

```text
R1 T1 passive discovery + registration bootstrap service + tests
→ R2 exact identity/source-bound 47112 + unified 1800 s deadline
→ R3 node-local registration portal + QR
→ R4 scan-triggered discovery + multi-T1 user selection
→ R5 node→T1 TLS bootstrap + SimplePairingClient refactor
→ R6 LCD state/error integration
→ R7 simulated phone-browser end-to-end + security/regression closure
→ R8 exact artifact build + independent source review
→ close/merge Board D identity repair and perform corrected read-only physical identity revalidation
→ R9 separately authorized physical product acceptance using phone scan + browser confirm
→ only then revisit MQTT/HA/Direct/Relay acceptance
```

Do not collapse these stages into one implementation gate.

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
EXISTING_KF_GUARD_USED=
KF-129 dynamic pairing fail-closed principles;
pairing/security lifecycle separation;
LAB inbox ownership;
unknown propagation;
exact-source binding;
no speculative fix;
GitHub connector authority;
physical target confirmation;
public-safe identity authority。

NEW_KF_REQUIRED=false
```

Reason:
the current issue is being captured as a successor product architecture ADR/source-design correction before final product acceptance; no additional KF is required at this point. If independent review proves a new concrete implementation/security defect outside the already-recorded predecessor behavior, classify it then.

---

## 16. New Chat Start Prompt

```text
阅读：

docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_FROZEN_TO_INDEPENDENT_REVIEW_NEW_CHAT_HANDOFF_V1.0_20261026.md

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/adr/0011-n3w-scan-triggered-first-registration.md
- docs/development/N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_20261026.md
- docs/adr/0007-n3w-security-simplification-long-lived-peer-trust.md
- docs/adr/0008-n3w-pairing-recovery-simplification-v2.md

读取当前 formal template authority：
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
- expected HANDOFF_TEMPLATE_VERSION=1.3
- expected blob=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0

读取 exact handoff standard authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md

并 fresh rebind：
- repository main
- PR #679 current HEAD
- diff after SOURCE_DESIGN_FROZEN_HEAD=2361bdfbd30d6ad2ede8c52e830cf1902edb4f86
- PR #677 status only for Board D identity dependency
- current firmware pairing/display source
- current Manager dynamic pairing/discovery/registration source

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3W_T1_DYNAMIC_FIRST_PAIRING_CLEAN_ARMBIAN_REINSTALL_AND_EXACT_RELEASE_ACCEPTANCE
当前任务：N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_INDEPENDENT_REVIEW_20261026_01

先做当前 gate 所需的最小 fresh 只读 rebind，然后只进入：

NEXT_ONE_GATE=
N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_INDEPENDENT_REVIEW_20261026_01

必须先承认：
- PR #679 frozen source-design authority 是 2361bdfbd30d6ad2ede8c52e830cf1902edb4f86；
- 后续 handoff/docs-only commit 可以推进 PR HEAD，但不得重定义 frozen design blobs；
- frozen design CI=13/13 SUCCESS；
- 产品 UI 术语是“联机注册”；
- idle 未注册节点不主动发现 T1；
- 扫码请求到达节点才触发发现；
- 用户确认才创建正式 first-registration transaction；
- TTL=1800 s 是 per-transaction，不是 T1 全局配对模式；
- V1 max concurrent first-registration=1；
- A 成功立即关闭敏感窗口并丢弃剩余 TTL，B 重新确认后获得新的完整 1800 s；
- 手机不接触 Setup Secret；
- 47110/47111 常驻低权限、47112 idle closed 是 target design，不是 current live fact；
- Board D historical 3991... identity authority 已证明无效，runtime/product authority 是 3a76...；PR #677 仍未 merge/physical revalidate；
- prior Board D first-pair authorization 已 consumed/non-replayable；
- 不得继续旧 raw QR → Terminal 粘贴流程；
- PR #679 尚未 merge，merge authorization 尚未 granted。

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

严格独立复核设计和当前源码，不接受 PR comment 结论作为证明。
输出 handoff 中定义的 A1-A10 closure。
不要修源码、不要 merge、不要访问 T1/Board、不要自动跨越到 implementation。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=SCAN_TRIGGERED_FIRST_REGISTRATION_SOURCE_DESIGN
CURRENT_STOP_POINT=SOURCE_DESIGN_FROZEN_AND_CI_PASS
CURRENT_BLOCKER=INDEPENDENT_SOURCE_DESIGN_REVIEW_NOT_YET_COMPLETED

LIVE_SYSTEM_STATE=UNKNOWN_FRESH:not required for next source-design review

SOURCE_DESIGN_FROZEN_HEAD=2361bdfbd30d6ad2ede8c52e830cf1902edb4f86
SOURCE_DESIGN_FROZEN_CI=13_OF_13_SUCCESS

NEXT_ONE_GATE=
N3W_SCAN_TRIGGERED_FIRST_PAIRING_SOURCE_DESIGN_INDEPENDENT_REVIEW_20261026_01

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
