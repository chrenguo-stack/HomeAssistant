# 温室环境监测系统（ESP32-C6）
# N3-W / T1 Board D 首次安全配对：pre-claim executor false-stop
# 新会话交接文档 V1.0 — 2026-10-25

```text
HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.1
PROJECT_WORKING_CONTEXT=docs/development/N3W_PROJECT_WORKING_CONTEXT.md
NEXT_ONE_GATE_ONLY=true
TEAM_SHARED_WORKSPACE=GITHUB
```

> 本文按当前 `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.3 编写，
> 长期执行规则来自 current-main `docs/development/N3W_PROJECT_WORKING_CONTEXT.md` V1.1。
> 历史 commit `4300890dff0ce63d5a547df21426e287d084d9ee` 中的 DSL handoff standard
> 不作为本阶段 current execution authority。
> fresh repository/runtime/live evidence 与本文冲突时，以 fresh 直接证据为准并先 STOP。

---

## 0. 会话切换结论

```text
CURRENT_STAGE=N3W_T1_BOARD_D_FIRST_SECURE_PAIRING_LIVE_ACCEPTANCE
CURRENT_STOP_POINT=PRECLAIM_EXECUTOR_HELPER_PERMISSION_DENIED_FALSE_STOP
NEXT_ONE_GATE=N3W_T1_BOARD_D_FIRST_SECURE_PAIRING_LIVE_ACCEPTANCE_20261025_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

现在切换会话是安全且合适的：最新一轮仍停在 onboarding `open` 之前，
fresh `inspect` 继续证明 pairing window 为 CLOSED、transaction absent、first-pair/security state 为零，
因此本轮已批准的一次性 Board D 首配 authorization **尚未 claim，也尚未 consume**。

最新停止点不是产品失败，而是 staged test helper
`/run/n3w-board-d-first-pair-20261025/continuity-probe.sh`
在直接执行时返回 `Permission denied`。不要在新会话继续堆叠 wrapper/monitor/dry-run。
下一会话由高阶模型直接编排最小、分阶段的 Mac Terminal / SSH / Docker / Python 命令，
使用 current-main onboarding Python tool 完成唯一一次真实 Board D 首配。
不再引入 DSL 编译层，也不再制造新的 wrapper/monitor executor。

---

## 1. 长期上下文引用与本阶段例外

```text
PROJECT_WORKING_CONTEXT_LOADED=true
PROJECT_WORKING_CONTEXT_VERSION=1.1
LONG_TERM_RULES_REPEATED_IN_HANDOFF=false

STAGE_SPECIFIC_OVERRIDE_COUNT=5
STAGE_OVERRIDES=
1. N3W_T1_FIRST_PAIRING_BOARD_D_20261025_01 已明确 GRANTED，且当前未 claim/consume；
2. 下一 gate 不需要再次申请同一 authorization，但必须 fresh 证明仍未 claim；
3. DSL_COMPILATION_USED=false；采用高阶模型直接编排 + Mac Terminal 操作，不得再 staging/执行 continuity-*.sh wrapper；
4. Board D 网络访问仅限本 gate 的正常 discovery/QR/first-pair traffic；
5. open 一旦 PASS，authorization 立即 consumed，任何失败都禁止重跑 open。
```

长期执行原则继续来自 `N3W_PROJECT_WORKING_CONTEXT.md`：

```text
PRIMARY_EXECUTION_PRINCIPLE=ACCURACY_SAFETY_EFFICIENCY_VERIFIABILITY_FIRST
TEST_PRODUCT_NOT_TEST_FRAMEWORK=true
TEAM_SHARED_WORKSPACE=GITHUB
FRESH_READONLY_REBIND_BEFORE_LIVE_CLAIM=true
```

---

## 2. Product North Star

```text
CURRENT_PRODUCT_ROUTE=
accepted production T1
→ Manager in-process dynamic pairing window
→ Board D normal product discovery/QR
→ private Setup Secret import
→ exactly one first secure pair
→ registration + active lease
→ MQTT credential generation 1
→ ACTIVE application key epoch 1
→ system peer-trust generation 1
→ dynamic pairing close
→ Broker/Manager/Home Assistant zero-interruption proof

FINAL_ACCEPTANCE_TARGET=
Board D first secure pairing is acknowledged and durable,
pairing exposure is fully closed,
and Broker/Manager/Home Assistant identities/restart counts remain unchanged.

DEFERRED_OR_OUT_OF_SCOPE=
Board D firmware/OTA/Flash/NVS writes;
physical reset;
second Wi-Fi provisioning;
second software restart;
serial capture;
Direct/Relay/RF acceptance;
dynamic load balancing;
normal post-pair telemetry/HA entity acceptance;
PR merge.
```

本 gate 只关闭 KF-129 的首次配对/零中断 live acceptance。
它不自动进入后续 Board D 正常运行遥测、Home Assistant entity 或 Direct/Relay 验收。

---

## 3. Frozen Authorities

### 3.1 Repository / current source

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=f8b16f70867324b57ea65aef2a3b579fcb00917a
TREE=07cc4ba0acc1b64189d4da92d94bf668c405a43d
MAIN_DRIFT=false

PR664_STATE=MERGED
PR664_MERGE_COMMIT=b31d86a66d7c4fc10370606b610aab3203a91d94
DYNAMIC_PAIRING_SOURCE_TEST_AUTHORITY=d63cba066201df355bf9ceb0fbb330c00dfee24d
```

### 3.2 Handoff/process authority

```text
HANDOFF_TEMPLATE_BLOB=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0
HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_BLOB=23c227528c2a388bebe886145aa36bb9a199807b
PROJECT_WORKING_CONTEXT_VERSION=1.1

HISTORICAL_DSL_STANDARD_COMMIT=4300890dff0ce63d5a547df21426e287d084d9ee
HISTORICAL_DSL_STANDARD_IS_CURRENT_AUTHORITY=false
```

### 3.3 Onboarding tool

```text
ONBOARDING_TOOL_PATH=tools/n3w_t1_first_pairing_onboarding.py
ONBOARDING_TOOL_GIT_BLOB=cd759f9a4e3bc16ad0da30e0f79cf36df08b9d39
ONBOARDING_TOOL_SHA256=2404f9a754ba6e60fdaed725ce50641054b485679ace7ff7a355e2525ac58328
STAGED_PRIVATE_TOOL_PATH=/run/n3w-board-d-first-pair-20261025/n3w_t1_first_pairing_onboarding.py
```

调用方式必须是：

```text
python3 <staged onboarding tool> inspect|open|close
```

不要把 staged shell helper 当作 authority。

### 3.4 Target / Board D public-safe bindings

```text
TARGET_PRIVATE_LOCATOR_PUBLICATION=false
TARGET_BINDING_SHA256=5760d55945216620ee7e3c3c75c1ec6255b3bad398657c548d18ca0fc5665141

BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
BOARD_D_PEER_IP_SHA256=3b25e4e29ee1a41aff1428c11c8eedbe48eb8d1731ac4abace9e65b9cc2bd8c5
ROUTE_SELECTED_T1_IPV4_SHA256=51c82bc9a7bd2c94d21dbdf863d13b0faedfab29e113b36b44054762ea2f75d2

PRIVATE_BOARD_ENDPOINT_POINTER=~/Documents/N3W/board-d-endpoint-current.path
RAW_BOARD_IP_IN_GITHUB=false
RAW_SETUP_SECRET_IN_GITHUB=false
RAW_PAIRING_ID_IN_GITHUB=false
```

### 3.5 Exact production release

当前 live pairing gate 不重新构建 release：

```text
CANDIDATE_REF=NOT_APPLICABLE:already accepted exact production T1
ARTIFACT_ID=12564745527
RELEASE_ID=338cb68f7d315b3386f65fec166a6be05e3dafe05e3612569fc2fd21b304c2cf
RELEASE_SHA256=ebec57947b2d29e5efee27c76f4f10f74df8414f02cbb94400e73c39fafba076
PRODUCTION_RESULT_SHA256=d4ba36db8d2c69f7bd1a2a4bc4d843a65c280c6a2e63fada13db449790d002e7
```

---

## 4. Current Live Baseline

最近一次 fresh pre-claim `inspect` 直接证明：

```text
FACTORY_ACCEPTED=true
FACTORY_RELEASE_SHA256=97ab3a2d9d571e317d1b8a3c884f1724047a4432809faa0b61ea4364517f1976

PAIRING_WINDOW_STATE=CLOSED
PAIRING_UDP_47111_LISTENER_COUNT=0
PAIRING_HTTP_47112_LISTENER_COUNT=0
PAIRING_TRANSACTION_PRESENT=false
AUTHORIZATION_REUSABLE_FIELD=null

REGISTRATIONS=0
PAIRING_SESSIONS=0
REGISTRATION_EVENTS=0
NODE_ID_LEASES=0

CREDENTIAL_ASSIGNMENTS=0
PEER_TRUST_RECORDS=0
APPLICATION_KEY_ACTIVE_NODES=0
APPLICATION_KEY_EPOCHS=0

MANAGER_STATE=RUNNING
MANAGER_NETWORK_MODE=host
MANAGER_RESTART_COUNT=0
MANAGER_CONTAINER_ID_SHA256=1c0f3a9a1788ea63d120dac3b2e5e03a639e2984232d6b6fd4912e9452562dd9

BROKER_STATE=RUNNING
BROKER_RESTART_COUNT=0
BROKER_CONTAINER_ID_SHA256=d902ac2736d6cc83af959f7306c18a84571ccf749ccd7542d77dfccfccf7f86e

HOMEASSISTANT_STATE=RUNNING
HOMEASSISTANT_RESTART_COUNT=0
HOMEASSISTANT_CONTAINER_ID_SHA256=1738832683435fde6461140360e8d19aa2169595aa07de7c75ae442515db94b5
HOMEASSISTANT_HTTP=PASS

NO_BOARD_DYNAMIC_PAIRING_LIVE_ACCEPTANCE=CLOSED_PASS
ISSUE669=CLOSED
ISSUE670=OPEN
```

Board D endpoint 已用 macOS Bonjour fresh rediscover：

```text
BOARD_D_BONJOUR_RESOLUTION=PASS
BOARD_D_PEER_IP_SHA256=3b25e4e29ee1a41aff1428c11c8eedbe48eb8d1731ac4abace9e65b9cc2bd8c5
BOARD_D_ROUTE_BINDING=PASS
BOARD_D_SOURCE_IS_LOCAL=true
ROUTE_SELECTED_IPV4_PRIVATE=true
```

当前没有发生：

```text
APPLICATION_SERIAL_OPEN=false
FLASH_MUTATION=false
NVS_MUTATION=false
FIRMWARE_FLASH=false
OTA=false
PHYSICAL_RESET=false
PAIRING_WINDOW_OPEN=false
BOARD_PAIRING_EXECUTED=false
SETUP_SECRET_IMPORTED=false
T1_PRODUCT_RUNTIME_MUTATION=false
```

但存在非产品 current-boot staging：

```text
BOUNDED_PRIVATE_HELPER_STAGING_OCCURRED=true
STAGED_TEST_HELPER_MAY_EXIST=true
STAGED_TEST_HELPER_IS_AUTHORITY=false
```

新会话必须 fresh read-only rebind 后再把这些 live facts 视为 current。

---

## 5. Proven Current Facts

```text
NO_BOARD_MANUAL_OPEN_CLOSE=PASS
NO_BOARD_MANAGER_OWNED_SELF_TIMEOUT=PASS
NO_BOARD_BROKER_MANAGER_HA_ZERO_INTERRUPTION=PASS

PR664_DYNAMIC_PAIRING_CONTROLLER=MERGED_CURRENT_MAIN
NORMAL_PAIRING_PATH_MANAGER_RECREATE=false
NORMAL_PAIRING_PATH_IN_PROCESS=true

BOARD_D_ENDPOINT_REDISCOVERY=PASS
FIRST_PAIR_STATE_CLEAN=PASS
FIRST_PAIR_SECURITY_STATE_CLEAN=PASS
PRECHANGE_FACTORY_BASELINE=PASS
EXACT_ONBOARDING_TOOL_STAGING=PASS

CURRENT_AUTHORIZATION_GRANTED=true
CURRENT_AUTHORIZATION_CLAIMED=false
CURRENT_AUTHORIZATION_CONSUMED=false

LATEST_ONBOARDING_OPEN_EXECUTED=false
LATEST_BOARD_PAIR_EXECUTED=false
LATEST_SETUP_SECRET_IMPORTED=false
PRODUCT_FAILURE_PROVEN=false
```

Latest exact executor stop:

```text
CONTINUITY_PROBE_STAGING=PASS
PRE_OPEN_INSPECT=PASS
STAGED_CONTINUITY_PROBE_EXECUTION=PERMISSION_DENIED
STOP_BEFORE_OPEN=true
```

当前只允许以下推断，不得升级为 proven fact：

```text
INFERENCE_PERMISSION_DENIED_MAY_BE_NOEXEC_OR_EXEC_POLICY=
POSSIBLE_ONLY_NOT_PROVEN
```

不需要证明该 inference 才能继续产品 gate，因为新会话不得再执行该 staged helper。

---

## 6. Current Root Cause / Blockers

```text
CURRENT_BLOCKER_COUNT=1
CURRENT_BLOCKER=TEST_EXECUTOR_WRAPPER_PATH_NOT_PRODUCT_PATH

ROOT_CAUSE=
exact low-level cause of staged continuity-probe.sh execute denial is UNPROVEN;
the proven engineering issue is repeated dependence on unnecessary staged/background wrappers before the real product open.

PROVEN_BY=
Issue #670 live preclaim attempts;
latest exact "Permission denied" after CONTINUITY_PROBE_STAGING=PASS;
all attempts stopped before onboarding open.

SOURCE_DEFECT_PROVEN=false
PRODUCT_RUNTIME_DEFECT_PROVEN=false
BOARD_D_DEFECT_PROVEN=false
```

处理方式不是继续修 test framework，而是遵守：

```text
TEST_PRODUCT_NOT_TEST_FRAMEWORK=true
EXECUTION_MODE=HIGH_LEVEL_MODEL_DIRECT_ORCHESTRATION_WITH_MAC_TERMINAL_OPERATOR
DIRECT_CODE_SUPPLIED=true
DSL_COMPILATION_USED=false
```

---

## 7. Closed / Forbidden Routes

下一会话不得重新进入：

```text
STAGED_CONTINUITY_SHELL_HELPER=CLOSED:repeated preclaim wrapper failures; not product authority
BACKGROUND_CONTINUITY_STATUS_FILE=CLOSED:unnecessary asynchronous wrapper
MORE_MONITOR_DRYRUN_GATES=CLOSED:already localized to execution framework
OLD_MANAGER_COMPOSE_RECREATE_PAIRING_PATH=CLOSED:KF-129 root cause; superseded by current in-process controller
REPLAY_20261024_FIRST_PAIR_AUTH=CLOSED:consumed historical authorization
REPLAY_CURRENT_AUTH_AFTER_OPEN=CLOSED:one-shot contract
MANUAL_DELETE_FIRST_PAIR_TRANSACTION=CLOSED:destroys no-replay evidence
MANUAL_CLEAR_REGISTRATION_OR_SECURITY_DB=CLOSED:not an authorized rollback
RAW_BOARD_IP_PUBLICATION=CLOSED:private locator
RAW_QR_OR_SETUP_SECRET_IN_CHAT_OR_GITHUB=CLOSED:private secret
SERIAL_QR_CAPTURE=CLOSED:normal product path is LCD QR; serial may disturb board
BOARD_FLASH_NVS_RESET=CLOSED:out of scope
DIRECT_RELAY_RF_ACCEPTANCE=CLOSED:out of current gate
AUTO_MERGE=CLOSED:MERGE=false
```

---

## 8. Authorization Ledger

### Current live authorization

```text
AUTHORIZATION=N3W_T1_FIRST_PAIRING_BOARD_D_20261025_01
GRANTED=true
CLAIMED=false
CONSUMED=false
RESULT=NOT_EXECUTED_PRECLAIM_FALSE_STOPS
FIRST_CLAIM_AVAILABLE=true
REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE
```

This is an already-granted authorization. A new chat must **not ask the user to grant the same scope again**
if fresh rebind still proves:

```text
PAIRING_TRANSACTION_PRESENT=false
PAIRING_WINDOW_STATE=CLOSED
FIRST_PAIR_STATE_CLEAN=true
```

Claim boundary:

```text
python3 <exact tool> open ... returns status=PASS
→ AUTHORIZATION_CLAIMED=true
→ AUTHORIZATION_CONSUMED=true
→ SECOND_ATTEMPT_ALLOWED=false
```

### Historical consumed authorization

```text
AUTHORIZATION=N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_AND_BOARD_D_FIRST_PAIR_20261024_01
CLAIMED=true
CONSUMED=true
RESULT=FAILED_SUPERSEDED_OLD_MANAGER_RECREATE_PATH
REPLAY_PERMITTED=false
SUPERSEDED_BY=N3W_T1_FIRST_PAIRING_BOARD_D_20261025_01
```

Do not reuse any older Board D Wi-Fi/restart authorization.

---

## 9. Rollback Authority

```text
ROLLBACK_BASELINE=
factory accepted;
dynamic pairing CLOSED;
UDP47111=0;
TCP47112=0;
pairing.sock absent;
first-pair DB/security counts zero;
Broker/Manager/HA running with restart_count=0;
transaction absent.

FRESH_PRECHANGE_SNAPSHOT_REQUIRED=true
ROLLBACK_AUTHORITY_PATH_OR_ID=
fresh onboarding inspect + current container identity hashes + current onboarding transaction after claim

NORMAL_PATH_RESTART_ALLOWED=false
ROLLBACK_ONLY_RESTART_LIMIT=0
SECOND_ATTEMPT_ALLOWED=false
ROLLBACK_FAILURE_CLASS=ROLLBACK_INCOMPLETE
```

Current-main rollback/safety behavior:

1. Before claim: any mismatch → STOP, no authorization consumed.
2. After successful `open`: Manager in-process dynamic controller owns the 180–600s deadline.
3. Host onboarding watchdog is a second fail-closed layer.
4. If execution fails while transaction is `OPEN` and pairing window is still open:
   use the **same consumed transaction** once with
   `close --outcome abort` to close exposure.
5. `abort` is safety closure only; it is not a retry and does not manufacture PASS.
6. After claim, never call `open` again under the same authorization.
7. If any registration/credential/application-key/peer-trust state has committed,
   do **not** delete or reset it automatically. Preserve evidence and STOP for reconciliation design.
8. If final CLOSED state/listener closure cannot be proven:

```text
ROLLBACK_INCOMPLETE=true
MANUAL_RECOVERY_REQUIRED=true
AUTO_RETRY=false
```

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_BOARD_D_FIRST_SECURE_PAIRING_LIVE_ACCEPTANCE_20261025_01
```

### Purpose

Use current-main in-process dynamic pairing and the already-granted unconsumed authorization to perform
exactly one Board D first secure pairing. Avoid the failed wrapper path entirely.
Prove Board acknowledge through the approved first-pair state, generation-1 credential/key/trust binding,
close the dynamic window, and prove Broker/Manager/Home Assistant zero interruption.

This gate does not prove later normal telemetry, HA entity creation, Direct/Relay or RF behavior.

### Inputs

```text
MAIN=f8b16f70867324b57ea65aef2a3b579fcb00917a
TREE=07cc4ba0acc1b64189d4da92d94bf668c405a43d

ONBOARDING_TOOL_GIT_BLOB=cd759f9a4e3bc16ad0da30e0f79cf36df08b9d39
ONBOARDING_TOOL_SHA256=2404f9a754ba6e60fdaed725ce50641054b485679ace7ff7a355e2525ac58328

AUTHORIZATION=N3W_T1_FIRST_PAIRING_BOARD_D_20261025_01
BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5

EXPECTED_BROKER_CONTAINER_ID_SHA256=d902ac2736d6cc83af959f7306c18a84571ccf749ccd7542d77dfccfccf7f86e
EXPECTED_MANAGER_CONTAINER_ID_SHA256=1c0f3a9a1788ea63d120dac3b2e5e03a639e2984232d6b6fd4912e9452562dd9
EXPECTED_HOMEASSISTANT_CONTAINER_ID_SHA256=1738832683435fde6461140360e8d19aa2169595aa07de7c75ae442515db94b5

BOARD_D_PRIVATE_ENDPOINT_POINTER=~/Documents/N3W/board-d-endpoint-current.path
WINDOW_SECONDS=600
```

### Operations

```text
1. Fresh repository rebind:
   prove main == f8b16f... and tool blob unchanged.
2. Fresh Issue #670 / live rebind.
3. Read-only onboarding inspect.
4. Require:
   transaction absent;
   window CLOSED;
   47111/47112 zero;
   all first-pair/security counts zero;
   three production services running/restart_count=0.
5. Resolve/read Board D peer only from private local source;
   keep raw IP out of chat/GitHub.
6. Direct synchronous continuity probe only:
   no staged executable;
   use direct docker inspect and container-local python3 -c socket checks;
   Manager remote 8883 count == 1;
   HA remote 1883 count >= 1;
   HA HTTP reachable.
7. If any step 1–6 fails:
   STOP_PRECLAIM;
   authorization remains unconsumed.
8. Execute exact onboarding open once:
   confirmation = OPEN FIRST PAIRING WINDOW: YES;
   window=600;
   exact current authorization;
   exact private Board peer.
9. Require open PASS:
   authorization_consumed=true;
   replay_allowed=false;
   window OPEN;
   watchdog active;
   UDP/TCP listeners exactly one;
   pairing.sock ready;
   Manager/Broker TLS probes PASS;
   three services unchanged.
10. Immediately classify:
    AUTHORIZATION_CLAIMED=true;
    AUTHORIZATION_CONSUMED=true;
    SECOND_ATTEMPT_ALLOWED=false.
11. Operator scans Board D LCD QR.
    The complete GHN3W2 payload stays in private Mac Terminal only.
12. Locally validate hardware_id SHA256 equals frozen Board D hash.
13. Pipe Setup Secret through stdin only to:
    greenhouse-manager-pairing import
    with exact hardware_id + pairing_id.
14. Never print/store raw Setup Secret in chat/GitHub.
15. Poll current onboarding inspect/direct DB evidence while window remains OPEN.
16. Require Board acknowledge semantics before success close:
    current pairing session state == approved;
    registration bound to same pairing/hardware/node;
    active node lease;
    exact security state below.
17. Require:
    credential_assignments=1;
    credential active_generation=1;
    pending_generation=null;
    state=active;
    application key active node=1;
    key epoch=1;
    key state=ACTIVE;
    key material hash/file validation PASS;
    peer-trust record=1;
    generation=1;
    same expected system_id;
    32-byte nonzero peer key.
18. Run exact onboarding close once with outcome=success.
19. Require CLOSED_PASS and hardware_id SHA binding to Board D.
20. Fresh final inspect:
    dynamic state CLOSED;
    47111/47112 zero;
    pairing.sock absent;
    transaction state CLOSED_PASS;
    authorization_reusable=false;
    all service identities unchanged;
    all restart counts zero.
21. Direct final MQTT/HTTP continuity probe.
22. Verify no active onboarding watchdog remains.
23. Return structured closure and STOP.
```

### PASS / FAIL / STOP

```text
PASS_IF=
one and only one authorization claim;
Board D QR hardware hash exact;
private Setup Secret import accepted;
pairing session approved;
registration/lease exact;
credential generation 1 active;
application key epoch 1 ACTIVE;
peer-trust generation 1 exact system binding;
CLOSED_PASS;
47111/47112 closed;
pairing.sock absent;
Broker/Manager/HA identities unchanged;
restart_count=0;
Manager MQTT + HA MQTT + HA HTTP continuity PASS.

FAIL_IF=
post-claim identity/security binding mismatch;
window closes before success;
watchdog lost;
authorization replay;
partial credential/key/trust commit;
service identity/restart drift;
final pairing closure unproven.

STOP_BOUNDARY=
always STOP after structured PASS/FAIL/rollback closure;
never auto-enter telemetry/HA/RF acceptance.

AUTO_EXECUTE_NEXT_GATE=false
```

---

## 11. Hard Allowed / Forbidden Scope

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

The exact granted authorization is the only exception after fresh preclaim PASS.

### ALLOWED

```text
- fresh read-only repository/T1/Board endpoint rebind
- T1 root SSH using existing private operator authority
- invoke exact staged onboarding Python tool via python3
- direct inline read-only Docker/container/socket/HTTP checks
- exactly one dynamic pairing open under N3W_T1_FIRST_PAIRING_BOARD_D_20261025_01
- Board D normal product discovery/HTTP secure pairing traffic
- private LCD QR handoff
- Setup Secret stdin import only
- registration/credential/application-key/peer-trust product commit
- exactly one success close, or one abort safety close after post-claim failure
- onboarding transaction/watchdog bounded private writes
- Issue #670 public-safe evidence update after closure
```

### FORBIDDEN

```text
- staging/executing continuity-probe.sh or another wrapper/monitor framework
- another dry-run gate
- second onboarding open after first successful claim
- raw Board D IP in GitHub/chat
- raw QR, pairing ID, Setup Secret or credential in GitHub/chat
- serial QR capture
- firmware flash / OTA
- raw NVS mutation/reset
- physical reset/power-cycle for this gate
- second Wi-Fi provisioning
- second software restart
- manual DB cleanup/edit
- manual DynSec reset
- Broker/Manager/HA recreate/restart as normal path
- Direct/Relay/RF acceptance
- PR merge
```

```text
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=
existing onboarding transaction/watchdog runtime paths only;
private local terminal handoff state only.
```

---

## 12. Execution Contract

```text
EXECUTOR=HIGH_LEVEL_MODEL_DIRECT_ORCHESTRATION_WITH_MAC_TERMINAL_OPERATOR
EXECUTION_METHOD=mac-terminal
DIRECT_CODE_SUPPLIED=true
DSL_COMPILATION_USED=false

CI_POLL_MAX=3
CI_PENDING_DIRECT_LINKS_REQUIRED=true
CI_ALL_GREEN_CONTINUE_REQUIRED_REVIEW=true
SAME_GATE_LOW_RISK_REPAIR_CONTINUE=false
```

Execution rules:

```text
1. 高阶模型直接给出当前步骤所需的最小 Mac Terminal 命令。
2. 只有前一步结果决定后一步是否安全时才分段执行。
3. current-main tools/n3w_t1_first_pairing_onboarding.py 是 pairing open/inspect/close 的 exact tool authority。
4. 不新增 versioned executor，不新增 staged shell wrapper，不新增 background monitor。
5. 简单只读解析可直接使用内联 Python -c / stdin，不把它升级为新的执行框架。

BEFORE_CLAIM:
  any mismatch => STOP;
  no pairing mutation;
  authorization remains available.

AFTER_CLAIM:
  authorization is consumed;
  never rerun open;
  inspect current state first on any command ambiguity;
  if OPEN and closure is needed, one abort safety close is allowed;
  preserve transaction and partial durable state;
  no auto-repair/no reset.

SETUP_SECRET:
  private operator input only;
  stdin only;
  never echo;
  never send to chat/GitHub.

HARD_STOP:
  after structured closure;
  do not enter next product stage.
```

本 gate 不使用 DSL compilation。

---

## 13. Expected Closure

```text
=== N3W_T1_BOARD_D_FIRST_SECURE_PAIRING_LIVE_ACCEPTANCE CLOSURE ===

EXECUTION_ID=
AUTHORIZATION=N3W_T1_FIRST_PAIRING_BOARD_D_20261025_01
AUTHORIZATION_CLAIMED=
AUTHORIZATION_CONSUMED=
REPLAY_PERMITTED=false

MAIN=
ONBOARDING_TOOL_BINDING=
PRECHANGE_FACTORY_BASELINE=
PRECHANGE_FIRST_PAIR_STATE_CLEAN=
PRECHANGE_CONTINUITY=

PAIRING_WINDOW_OPEN=
WATCHDOG_ACTIVE=
BOARD_D_PAIRING_READY=
BOARD_D_QR_IDENTITY_BINDING=
SETUP_SECRET_HANDOFF=
BOARD_D_FIRST_PAIR_ACKNOWLEDGED=

REGISTRATION_STATE=
NODE_LEASE_STATE=
MQTT_CREDENTIAL_STATE=
MQTT_CREDENTIAL_GENERATION=
APPLICATION_KEY_STATE=
APPLICATION_KEY_EPOCH=
PEER_TRUST_STATE=
PEER_TRUST_GENERATION=

PAIRING_WINDOW_CLOSE=
FINAL_TRANSACTION_STATE=
FINAL_FACTORY_PAIRING_DISABLED=
FINAL_PAIRING_LISTENERS_CLOSED=
FINAL_PAIRING_SOCKET=
FINAL_WATCHDOG_STATE=

BROKER_CONTAINER_CONTINUITY=
MANAGER_CONTAINER_CONTINUITY=
HOMEASSISTANT_CONTAINER_CONTINUITY=
MANAGER_MQTT_CONTINUITY=
HOMEASSISTANT_MQTT_CONTINUITY=
HOMEASSISTANT_HTTP_CONTINUITY=

LIVE_RUNTIME_MUTATION=
BOARD_ACCESS=
BOARD_D_DURABLE_PAIRING_STATE_CHANGED=

ROLLBACK_OR_RECOVERY_STATE=

GATE_RESULT=
NEXT_ROUTE=
STOP=true

=== END ===
```

No closure field may claim Board acknowledge unless the approved pairing-session path is directly proven.

---

## 14. After PASS / FAIL

### PASS

```text
AFTER_PASS_NEXT_STAGE=KF129_FINAL_GITHUB_CLOSURE_ALIGNMENT
AUTO_EXECUTE_AFTER_PASS=false
NEW_LIVE_AUTHORIZATION_REQUIRED_FOR_POST_PAIR_RUNTIME_GATE=true
```

After the high-level model accepts the closure, update Issue #670 / KF-129 with public-safe evidence.
Only then separately design Board D normal MQTT/Manager/HA runtime acceptance if still required.

### FAIL

```text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
SAME_AUTHORIZATION_REOPEN=false
```

If post-claim failure occurs, preserve the transaction and exact durable state.
Do not clear credential/key/trust data to manufacture a clean retry.

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
NEW_KF_REQUIRED=false
```

Reason:

- KF-129 already captures the real product defect and its current in-process repair;
- the latest `Permission denied` is an acceptance-wrapper/tooling failure before product mutation;
- Issue #670 is the durable record for this gate;
- adding another KF for an avoidable test wrapper would increase test-framework complexity without protecting product behavior.

Current Issue #670 evidence includes:

```text
AUTHORIZATION_BINDING=RECORDED
BOARD_D_ENDPOINT_REDISCOVERY=RECORDED
PRECHANGE_SNAPSHOT=RECORDED
PRECLAIM_WRAPPER_FALSE_STOPS=RECORDED
LATEST_PERMISSION_DENIED_PREOPEN=TO_BE_RECORDED_BY_HANDOFF/PR
```

---

## 16. New Chat Start Prompt

```text
阅读：

docs/development/N3W_T1_BOARD_D_FIRST_SECURE_PAIRING_PRECLAIM_EXECUTOR_STOP_NEW_CHAT_HANDOFF_V1.0_20261025.md

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_MANAGER_DYNAMIC_FIRST_PAIRING_WINDOW_SOURCE_DESIGN_AND_ACCEPTANCE_PLAN_20261024.md

读取当前 handoff template：
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md
- expected HANDOFF_TEMPLATE_VERSION=1.3
- expected blob=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0

不要把历史 commit 4300890dff0ce63d5a547df21426e287d084d9ee 中的 DSL handoff standard
重新当作 current execution authority。

并 fresh rebind：
- repository main
- Issue #670
- PR #664 merged state
- tools/n3w_t1_first_pairing_onboarding.py
- current T1 pairing/window/transaction state
- current Broker/Manager/Home Assistant identities/restart counts
- private Board D endpoint binding

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3W_T1_DYNAMIC_FIRST_PAIRING_CLEAN_ARMBIAN_REINSTALL_AND_EXACT_RELEASE_ACCEPTANCE
当前任务：N3W_T1_BOARD_D_FIRST_SECURE_PAIRING_LIVE_ACCEPTANCE_20261025_01

必须先承认：
- main authority=f8b16f70867324b57ea65aef2a3b579fcb00917a；
- PR #664 已 merged，当前正常 pairing 是 Manager in-process dynamic window，不 recreate Manager；
- Issue #669 no-Board dynamic pairing acceptance 已 CLOSED_PASS；
- Issue #670 当前 OPEN；
- Board D endpoint 已 fresh rediscover，但 raw private IP 不得写入 chat/GitHub；
- fresh prechange inspect 已证明 window CLOSED、transaction absent、first-pair/security counts 全零；
- Broker/Manager/HA restart_count=0；
- 本轮用户已经明确授权 N3W_T1_FIRST_PAIRING_BOARD_D_20261025_01；
- 当前 authorization CLAIMED=false、CONSUMED=false；
- 过去所有正式 open 尝试都在 open 前停止，因此当前 authorization 仍可进行第一次 claim；
- 最新停止是 staged continuity-probe.sh Permission denied，属于 preclaim executor/tooling failure，不是 product failure；
- 不再修/执行 staged shell wrapper，不再增加 monitor dry-run；
- 当前执行方式是 HIGH_LEVEL_MODEL_DIRECT_ORCHESTRATION_WITH_MAC_TERMINAL_OPERATOR；
- DIRECT_CODE_SUPPLIED=true；
- DSL_COMPILATION_USED=false；
- 由高阶模型按步骤直接给出最小 Mac Terminal/SSH/Docker/Python 命令；
- open 一旦 PASS，本 authorization 永久 consumed，禁止第二次 open；
- Setup Secret 只能在私有 Terminal 经 stdin 导入，禁止进入 chat/GitHub。

NEXT_ONE_GATE=
N3W_T1_BOARD_D_FIRST_SECURE_PAIRING_LIVE_ACCEPTANCE_20261025_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

当前 exact authorization 是已经批准的 stage-specific exception。
先 fresh read-only rebind；如果仍满足 preclaim 条件，直接进入该已授权 gate，
不要再次要求相同授权，不要自动跨越下一阶段。

不要重放 consumed authorization，不要重新进入 old Manager recreate path，
不要运行 staged continuity shell helper，不要发布 raw Board IP/QR/Setup Secret。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=N3W_T1_BOARD_D_FIRST_SECURE_PAIRING_LIVE_ACCEPTANCE
CURRENT_STOP_POINT=PRECLAIM_STAGED_CONTINUITY_PROBE_PERMISSION_DENIED

SOURCE_DEFECT_PROVEN=false
PRODUCT_RUNTIME_DEFECT_PROVEN=false
BOARD_D_DEFECT_PROVEN=false
CURRENT_BLOCKER=UNNECESSARY_TEST_EXECUTOR_WRAPPER_PATH

LIVE_SYSTEM_STATE=
pairing CLOSED;
transaction absent;
first-pair/security state clean;
Broker/Manager/HA running;
restart_count=0/0/0;
Board D private endpoint rediscovered;
no pairing mutation executed.

AUTHORIZATION=N3W_T1_FIRST_PAIRING_BOARD_D_20261025_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
FIRST_CLAIM_AVAILABLE=true
SECOND_ATTEMPT_AFTER_CLAIM=false

NEXT_ONE_GATE=N3W_T1_BOARD_D_FIRST_SECURE_PAIRING_LIVE_ACCEPTANCE_20261025_01

TEAM_SHARED_WORKSPACE=GITHUB
ISSUE670=OPEN

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.1
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
