# 温室环境监测系统 N3-W / FC4 Board C Setup Secret Recapture 收口暨 Fresh Pairing Rebind 前新会话交接文档

- 文档版本：V1.0
- 日期：2026-08-29
- 文档性质：public-safe / cross-session handoff
- NORTH_STAR：`FC4_FINAL_PHYSICAL_ACCEPTANCE`
- 当前路线节点：`BOARD_C_FIRST_REGISTRATION`
- 当前 detour：`NONE`
- `NEW_BRANCH_ALLOWED=false`
- 产品阻塞：未证明
- 当前需要在新会话继续的直接任务：`PRIVATE_HANDOFF_FRESH_PAIRING_REBIND_MUTATION_AUTHORIZATION`

> 本文只记录 public-safe authority、布尔状态、commit / blob authority、已消费 authorization 与下一 gate。严禁把 raw Board C hardware identity、raw pairing ID、Setup Secret、Setup Secret hash、private handoff 实际路径、private handoff hash、T1 私网地址或其他 private evidence 写入公共仓库。

---

## 1. 任务目标连续性

整个任务的 North Star 没有改变：完成 N3-W / FC4 Final Physical Acceptance。

当前主路线为：

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE
  -> T1_RUNTIME_BASELINE_RECOVERY
  -> R6_CONSOLIDATED_MANAGER_SUCCESSOR
  -> R6D2_DYNSEC_AUTHORITY_REPAIR
  -> BOARD_C_FIRST_REGISTRATION
  -> FC4_FINAL_PHYSICAL_ACCEPTANCE_CLOSURE
```

本轮已结束 P9 current-authority rebaseline、Board C Setup Secret 物理 recapture，以及 fresh-pairing rebind mutation 前的只读 preclaim。没有产生新的产品路线分支。

新会话必须从 `BOARD_C_FIRST_REGISTRATION` 继续，禁止退回重新 flash、清 NVS、重新 provision Board C，除非后续出现新的、独立证明的产品级根因并另立授权。

---

## 2. 本轮执行模式

继续采用已经冻结的协作模式：

```text
高阶模型：负责路线、authority、gate、失败分类、授权边界、结果复核
Codex / 低阶执行器：只执行高阶模型给出的 bounded executor / shell / Python contract
操作者：显式授予一次性 mutation / physical authorization，并回传机器可读结果
```

规则：

1. 一次只推进一个小 gate。
2. `UNKNOWN != FAIL`；未评估必须保持 `UNKNOWN / NOT_EVALUATED / UNPROVEN`。
3. executor/oracle defect 不得冒充 product defect。
4. 一次性物理授权在 CLAIM 后无论成功失败均不可重放。
5. pairing TTL 是瞬时事实；跨会话不得继承上一个观测值作为当前 authority。
6. 任何 mutation 前重新绑定 exact source、current runtime、current pairing 和目标对象。

---

## 3. Repository / source authority

### 3.1 Frozen product source

```text
FROZEN_PRODUCT_SOURCE_HEAD=1f80d54ff5f84056e0559a7d8cc80427c5e0bb14
FROZEN_PRODUCT_SOURCE_TREE=f3b8095c62e8a4838eb1b614f05c932f54f5226d
```

这是当前部署 / FC4 product semantics authority；repository `main` 的 documentation-only advancement 不得自动替代它。

### 3.2 KF073 / KF074 guarded source

```text
GUARDED_BRANCH=fix/fc4-boardc-p9-setup-secret-capture-risk-20260828
GUARDED_HEAD=867c84d9d90f9c56d2446d9aa1a13c31ac593480
GUARDED_TREE=de670366fe452637e802fb261929613047805964
```

关键 blobs：

```text
KF074_AUTHORITY_SOURCE_BLOB=d856d2f15b09d5335c56c2b9b2534c7341699878
KF074_AUTHORITY_TEST_BLOB=6521f4484a4b2d7c581ad077e93a430cd3d530c7
KF073_CAPTURE_SOURCE_BLOB=8c0bb91578c08cc1a298e0f1a57f63ddd63233a6
KF073_CAPTURE_TEST_BLOB=a5b0f3412ef76cdd125e6a6bda6b7a9b9df377e6
DELIVERY_GATE_SOURCE_BLOB=09270f4c512b83efecd438c9f26394f3e99b64f8
```

本交接文档所在 documentation branch 从 guarded branch 建立；文档提交后的 branch HEAD 不得冒充 `GUARDED_HEAD=867c84d9...`。

### 3.3 Repository main

本轮收口时已确认 repository `main` 为 documentation-history authority，不是 frozen product source authority。新会话必须显式区分：

```text
REPOSITORY_MAIN_AUTHORITY != FROZEN_PRODUCT_SOURCE_AUTHORITY
```

---

## 4. Current runtime authority（public-safe）

T1 的具体网络 locator、SSH private binding 和 private host state locator 不写入公共文档；新会话只能从已授权 private/operator context 恢复，禁止 LAN 扫描替代 exact-target authority。

已证明的 public-safe runtime facts：

```text
EXECUTION_TARGET=T1_REMOTE
T1_ARCH=aarch64
DOCKER_SERVER_VERSION=29.7.1
CURRENT_MANAGER_COUNT=1
CURRENT_MANAGER_REVISION=1f80d54ff5f84056e0559a7d8cc80427c5e0bb14
CURRENT_MANAGER_IMAGE=greenhouse-manager:fc4-r1v2n-1f80d54-native
CURRENT_MANAGER_NETWORK_MODE=host
CURRENT_MANAGER_ROOTFS_READONLY=true
PAIRING_TCP_READY=true
PAIRING_UDP_READY=true
PAIRING_LOCAL_IPC_SOCKET_READY=true
BROKER_COUNT=1
BROKER_IMAGE=local/mosquitto:pr260-source-exact
DYNSEC_ACTIVE_FILE_BASENAME=dynamic-security.json
```

current Manager 的选择必须使用 Compose service label + running state + exact revision 等组合 authority，禁止按历史 literal container name 选择。

---

## 5. 本轮 executor / oracle 纠偏

本轮出现过以下 executor/oracle defects，均未证明产品故障：

1. UDP `ss` oracle 使用错误字段，曾造成 listener false negative；纠正字段后 P2 PASS。
2. P3 首次误用 Mac local Docker，而不是 T1 remote Docker；重新绑定执行目标后 PASS。
3. 一次 `docker exec` heredoc 缺少 stdin attachment（`-i`），导致 inventory 实际未执行；纠正后 PASS。
4. Broker discovery 曾使用不适用的 Docker format `.Labels` 索引方式；改用 `.Label "com.docker.compose.service"` 后 PASS。

本轮执行过 mandatory route audit；route audit PASS 后 failure fuse 已 reset。此后 corrected gates 连续通过。

新会话必须继续遵守：

```text
CURRENT_CONSECUTIVE_EXECUTOR_PRECLAIM_FAILURE_COUNT=0
ROUTE_AUDIT_REQUIRED=false
PRODUCT_ROUTE_VALID=true
```

这些问题属于 executor/oracle hygiene，不得反推 Board C、Manager 或 Broker product regression。

---

## 6. P9 current-authority rebaseline closure

本轮完成：

```text
P0_CAPABLE_ENVIRONMENT=PASS
P1_EXACT_GUARDED_SOURCE=PASS
P2_CURRENT_MANAGER_AUTHORITY=PASS
P3_R4_DURABLE_AUTHORITY=PASS
P4_CURRENT_USB_TO_DURABLE_IDENTITY_BINDING=PASS
P5_KF074_SOURCE_OWNED_DRY_RUN=PASS
P6_SETUP_SECRET_LIFECYCLE=PASS
P7_CURRENT_PAIRING_EFFECTIVE_STATE=PASS
P9_CURRENT_AUTHORITY_REBASELINE_PRECLAIM_R2=PASS
```

### 6.1 P3 durable clean state

R4 first-registration failure lineage 已重新从 current T1 authority secret-safe 证明：

```text
R4_TOMBSTONE_LINEAGE=PASS
BOARD_C_DURABLE_IDENTITY_FROM_R4_TOMBSTONE=PASS
R4_FAILED_NODE_LEASE_STATE=RETIRED
R4_FAILED_RETIRED_NODE_ID_WILL_NOT_BE_REUSED=true
R4_FAILED_NODE_HISTORY_RELEASED=true
R4_FAILED_NODE_HISTORY_OPEN=false
BOARD_C_REGISTRATION_ROW_PRESENT=true
BOARD_C_NODE_ID_IS_NULL=true
BOARD_C_REPAIR_AUTHORIZED=false
BOARD_C_HARDWARE_RETIRED=false
BOARD_C_ACTIVE_NODE_LEASE_COUNT=0
BOARD_C_OPEN_NODE_HISTORY_COUNT=0
BOARD_C_CREDENTIAL_ASSIGNMENT_RECORD_COUNT=0
BOARD_C_ACTIVE_CREDENTIAL_ASSIGNMENT_COUNT=0
BOARD_C_PENDING_CREDENTIAL_GENERATION_COUNT=0
R4_FAILED_NODE_ACTIVE_RELAY_NODE_COUNT=0
R4_FAILED_NODE_ENABLED_RELAY_KEY_EPOCH_COUNT=0
R4_FAILED_NODE_KEY_OPERATION_RECORD_COUNT=0
```

Broker / DynSec 独立 authority 进一步证明：

```text
R4_FAILED_NODE_DYNSEC_USERNAME_MATCH_COUNT=0
R4_FAILED_NODE_DYNSEC_CLIENTID_MATCH_COUNT=0
R4_FAILED_NODE_DYNSEC_FULL_IDENTITY_MATCH_COUNT=0
R4_FAILED_NODE_DYNSEC_PARTIAL_IDENTITY_MATCH_COUNT=0
R4_FAILED_NODE_DYNSEC_ROLE_MATCH_COUNT=0
R4_FAILED_NODE_DYNSEC_CLIENT_RESIDUE_PRESENT=false
R4_FAILED_NODE_DYNSEC_ROLE_RESIDUE_PRESENT=false
BOARD_C_DYNSEC_CREDENTIAL_PRESENT=false
P3D2C_DYNSEC_ORPHAN_CHECK=PASS
```

结论：R4 失败事务已 clean rollback；旧 NODE_ID tombstone 保留且不可复用，Board C hardware 本身未退休，当前无 credential / DynSec orphan residue。

### 6.2 P4 current USB continuity

被动 `ioreg` + R4 durable identity 比较：

```text
LOCAL_CU_USBM0DEM_COUNT=1
IOREG_NORMALIZED_12HEX_SERIAL_UNIQUE_COUNT=1
R4_DURABLE_SUFFIX_MATCH_COUNT=1
CURRENT_USB_EQUALS_R4_DURABLE_BOARD_C=true
KF074_NORMALIZATION_SEMANTICS_APPLIED=true
HISTORICAL_C_FINGERPRINT_USED=false
P4_PASSIVE_USB_DURABLE_BINDING=PASS
```

历史 C fingerprint 已明确为 non-authoritative legacy evidence，不得重新进入 current identity gate。

### 6.3 P5 KF074 source-owned dry-run

```text
EXACT_GUARDED_HEAD=PASS
EXACT_GUARDED_TREE=PASS
EXACT_GUARDED_WORKTREE_CLEAN=true
KF074_AUTHORITY_BLOB=PASS
KF073_CAPTURE_BLOB=PASS
KF074_AUTHORITY_PREPARE=PASS
KF074_USB_CONTINUITY=PASS
KF074_CAPTURE_HARDWARE_FROM_DURABLE_AUTHORITY=true
KF074_CAPTURE_PAIRING_FROM_FRESH_POINTER=true
KF074_DRY_RUN_ACK_LIVE_SERIAL_OPEN_RISK=false
KF074_FAKE_ONLY_BOUNDARY=true
P5_KF074_SOURCE_OWNED_DRY_RUN=PASS
LOW_LEVEL_CAPTURE_PRIMITIVE_EXECUTED=false
SERIAL_OPEN=false
HANDOFF_FILE_WRITE=false
```

### 6.4 P6 Setup Secret lifecycle

当前语义：

```text
SETUP_SECRET_VALUE_CHANGED=false
SETUP_SECRET_REIMPORT_REQUIRED=true
```

R6 Manager recreate 丢失的是 Manager 内存中的 import authority，不是 Board C durable Setup Secret。

物理 recapture 前：

```text
PRIVATE_SETUP_SECRET_SAME_AUTHORITY=UNKNOWN
```

这是预期 evidence gap，不是 product failure。

---

## 7. Board C Setup Secret physical recapture — 已完成

一次性授权：

```text
AUTHORIZATION=R6-BOARD-C-SETUP-SECRET-PHYSICAL-RECAPTURE-20260829-01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
```

该 authorization 永久不可再次使用。

执行闭合：

```text
EXACT_GUARDED_SOURCE=PASS
PYSERIAL_AVAILABLE=true
MAX_LIVE_SERIAL_OPEN_COUNT=1
SERIAL_OPEN_NO_RESET_PROVEN=false
PREEXISTING_AUTHORIZATION_ARTIFACT_COUNT=0
KF074_AUTHORITY_PREPARE=PASS
KF074_USB_CONTINUITY=PASS
FINAL_CLAIM_BOUNDARY_BINDING=PASS
SERIAL_OPEN_COUNT=1
SERIAL_OPEN_EXACTLY_ONCE=true
PRIVATE_HANDOFF_MODE_0600=true
PRIVATE_HANDOFF_OWNER_MATCH=true
PRIVATE_HANDOFF_SCHEMA_VALID=true
CAPTURED_HARDWARE_EQUALS_DURABLE_AUTHORITY=true
CAPTURED_PAIRING_EQUALS_FRESH_CLAIM_AUTHORITY=true
SETUP_SECRET_ENCODING_VALID=true
SETUP_SECRET_DECODED_LENGTH_VALID=true
POST_CAPTURE_PAIRING_POINTER_STILL_MATCH=true
PRIVATE_PAIRING_PAYLOAD_CAPTURED=true
PRIVATE_HANDOFF_MATERIALIZED=true
PRIVATE_SETUP_SECRET_BOARD_AUTHORITY_BINDING=PASS
PRIVATE_SETUP_SECRET_PAIRING_AUTHORITY_BINDING=PASS
PRIVATE_SETUP_SECRET_SAME_AUTHORITY=PASS
PHYSICAL_RECAPTURE_GATE=PASS
FAIL_CLASS=NONE
```

明确未执行：

```text
EXPLICIT_RESET_COMMAND_EXECUTED=false
FLASH_EXECUTED=false
NVS_ERASE_EXECUTED=false
REPROVISION_EXECUTED=false
REGISTRATION_APPROVAL_EXECUTED=false
NODE_ID_ASSIGNMENT_EXECUTED=false
CREDENTIAL_PROVISIONING_EXECUTED=false
MQTT_PROVISIONING_EXECUTED=false
APPLICATION_KEY_ACTIVATION_EXECUTED=false
```

`HISTORICAL_PRIVATE_SECRET_BYTEWISE_COMPARISON=NOT_EVALUATED` 必须保持如此；没有旧 private secret byte copy 时不得伪造 bytewise-equality 证明。当前 gate 已证明的是 current Board C + current pairing + private handoff 的 same-authority binding。

---

## 8. Private handoff 状态

物理 recapture 产生了 private handoff。其 concrete path / digest 不进入公共仓库。

新会话若需要定位该 private artifact，只允许使用已消费 authorization 的 deterministic private discovery contract，并要求唯一匹配、owner/mode、claim marker、consumed marker、schema 全部 PASS。不得把任意同名 JSON 或历史 handoff 当作 current authority。

当前 frozen semantics：

```text
PRIVATE_HANDOFF_MATERIALIZED=true
PRIVATE_HANDOFF_MODE_0600=true
PRIVATE_HANDOFF_OWNER_MATCH=true
PRIVATE_HANDOFF_SCHEMA_VALID=true
PRIVATE_SETUP_SECRET_SAME_AUTHORITY=PASS
```

Setup Secret value 不允许打印、hash、复制到公共日志或公共仓库。

---

## 9. Setup Secret import preclaim — pairing 已自然前移

物理 recapture 后做只读 import preclaim 时，得到：

```text
SOURCE_OWNED_PRIVATE_HANDOFF_VALIDATION=PASS
DURABLE_HARDWARE_MATCH=true
HANDOFF_PAIRING_EQUALS_CURRENT=false
CURRENT_NODE_ID_IS_NULL=true
CURRENT_REPAIR_AUTHORIZED=false
CURRENT_HARDWARE_RETIRED=false
CURRENT_PAIRING_DB_STATE=PENDING
PAIRING_LOCAL_IPC_SOCKET_READY=true
PRIVATE_HANDOFF_PAIRING_REBIND_REQUIRED=true
SETUP_SECRET_IMPORT_PRECLAIM=PASS_REBIND_REQUIRED
PRODUCT_BLOCKER_PROVEN=false
FAIL_CLASS=NONE
```

当时 current pairing TTL 已很短。结论：不是 Setup Secret 或 hardware failure，而是短 TTL pairing 正常换代；旧 handoff pairing pointer 不能直接投递。

关键规则：

```text
OLD_PRIVATE_HANDOFF_PAIRING != CURRENT_PAIRING
=> DIRECT_IMPORT_FORBIDDEN
```

但 private Setup Secret 本身仍有效；不需要再次打开串口。

---

## 10. Fresh pairing rebind preclaim — 已通过

随后只读等待并选到 fresh current PENDING pairing：

```text
CURRENT_REGISTRATION_ROW_COUNT=1
CURRENT_PAIRING_FRESH_RELATIVE_TO_HANDOFF=true
CURRENT_NODE_ID_IS_NULL=true
CURRENT_REPAIR_AUTHORIZED=false
CURRENT_HARDWARE_RETIRED=false
CURRENT_PAIRING_DB_STATE=PENDING
CURRENT_CREDENTIAL_ASSIGNMENT_COUNT=0
FRESH_PAIRING_REBIND_PRECLAIM_READY=true
PRIVATE_HANDOFF_BOARD_AUTHORITY_CONTINUITY=PASS
PRIVATE_SETUP_SECRET_REUSE_AUTHORITY=PASS
PRIVATE_HANDOFF_FRESH_PAIRING_REBIND_PRECLAIM=PASS
PRODUCT_BLOCKER_PROVEN=false
FAIL_CLASS=NONE
```

当时 TTL margin 足够，但该 TTL 数值只证明“当时 ready”，不能跨会话继承。

本轮结束时：

```text
PRIVATE_HANDOFF_REWRITE_EXECUTED=false
SETUP_SECRET_IMPORT_EXECUTED=false
REGISTRATION_APPROVAL_EXECUTED=false
NODE_ID_ASSIGNMENT_EXECUTED=false
CREDENTIAL_PROVISIONING_EXECUTED=false
SERIAL_OPEN=false
BOARD_ACCESS=false
LIVE_PRODUCT_MUTATION=false
```

---

## 11. 下一 gate：Private handoff fresh-pairing rebind mutation

### 11.1 Proposed authorization

下一次建议的一次性 mutation authorization：

```text
R6-BOARD-C-PRIVATE-HANDOFF-FRESH-PAIRING-REBIND-20260829-01
```

本轮**尚未授权、尚未 CLAIM、尚未消费**。

新会话不得根据本文自动执行 mutation；必须先进行 read-only rebaseline，然后等待操作者明确批准该 authorization 或新生成的 successor authorization。

### 11.2 Allowed scope

```text
ALLOWED:
- fresh-read current Board C registration / pairing authority
- 要求同一 durable Board C
- 要求 node_id=NULL
- 要求 hardware not retired
- 要求 no credential assignment
- 要求 current pairing=PENDING 且 TTL margin 足够
- 读取已验证的 private handoff
- 保留完全相同的 Setup Secret value
- 仅把 handoff pairing_id 重绑定到 mutation 边界的 current fresh pairing
- 原子生成新的 private 0600 handoff
- source-owned predelivery validation
- 把旧 handoff 保留为不可再投递的历史 private evidence
```

### 11.3 Forbidden scope

```text
NOT_ALLOWED:
- serial open
- Board C access
- reset
- flash
- NVS erase
- reprovision
- Setup Secret import
- registration approval
- NODE_ID assignment
- credential provisioning / activation
- MQTT provisioning
- application-key activation
- unrelated T1 database mutation
```

### 11.4 Critical mutation-boundary rule

新会话绝对不能使用本轮最后一次 TTL 数值或 pairing hash 作为 mutation authority。

mutation 前必须：

1. 重新读取 current registration pointer。
2. 重新证明 current pairing 为 `PENDING`。
3. 重新证明 TTL margin 足够。
4. 若 pairing 再次前移，直接绑定当时最新、同 durable hardware 的 fresh pairing。
5. handoff 重绑定只改变 private `pairing_id`；Setup Secret value 必须 byte-for-byte 保持，不允许重新生成或再次 serial capture。

---

## 12. Fresh-pairing rebind 之后的预期路线

严格一 gate 一决策：

```text
PRIVATE_HANDOFF_FRESH_PAIRING_REBIND_MUTATION
  -> SOURCE_OWNED_PREDELIVERY_VALIDATION
  -> SETUP_SECRET_IMPORT_MUTATION_AUTHORIZATION
  -> MANAGER_OWNED_LOCAL_UDS_SETUP_SECRET_IMPORT
  -> BOARD_C_FIRST_REGISTRATION_CLAIM / AUTOMATIC_APPROVAL
  -> AUTOMATIC_NEW_NODE_ID
  -> INITIAL_APPLICATION_KEY_STAGING
  -> PEER_TRUST
  -> MQTT_CREDENTIAL_DELIVERY
  -> ACK / ACTIVATION / LIFECYCLE
  -> APPROVED
  -> MQTT AUTH
  -> DIRECT TELEMETRY
  -> MANAGER CANONICAL STATE
  -> HOME_ASSISTANT ACCEPTANCE
  -> FC4_FINAL_PHYSICAL_ACCEPTANCE_CLOSURE
```

注意：上述只是路线，不等于一次 authorization。每个显著 mutation 仍需单独 bounded gate。

NODE_ID 必须由 Manager 自动分配；R4 retired NODE_ID 永不复用；操作者不得手工指定。

---

## 13. Known Failures / guards 必须继续读取

新会话开始时至少复核 guarded branch 中：

```text
KF-069  DynSec active authority lineage
KF-071  current-runtime authority classifier
KF-072  UNKNOWN / negative evidence serialization
KF-073  serial RTS/DTR single-open capture guard
KF-074  Board C durable hardware single-authority capture guard
```

本轮额外观察到的 ad-hoc executor/oracle defects（UDP field、local-vs-remote Docker、missing `docker exec -i`、Docker label format）必须作为 executor hygiene 继续闪避；不得把这些 false negatives 归类为产品故障。

如果 central `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` 后续新增编号，必须先读取仓库当前编号再分配，禁止猜号。

---

## 14. Failure taxonomy / fuse

继续使用：

```text
PRODUCT_BLOCKER
INFRASTRUCTURE_BLOCKER
SECURITY_AUTHORITY_BLOCKER
PHYSICAL_HARNESS_DEFECT
EXECUTOR_OR_ORACLE_DEFECT
EVIDENCE_GAP
TRANSIENT_INFRASTRUCTURE_FAILURE
```

规则：

- 两次连续 executor/preclaim failure 后，在第三次 successor/preclaim 前 mandatory route audit。
- route audit PASS 后 failure fuse reset。
- 当前 fuse 已 reset；本轮结束没有 active failure streak。
- incidental anomaly 不开 sibling route。

---

## 15. 新会话启动顺序

新会话第一轮严格执行：

1. 读取本文。
2. 读取 `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`，重点 KF-069、071、072、073、074。
3. 核对 repository main 与 frozen product source authority 分离。
4. 核对 guarded source `867c84d9...`、tree 与关键 blobs。
5. 只读恢复 T1 exact target binding；不得扫描局域网替代 operator/private authority。
6. 只读核对 current Manager = one running Compose `manager` service + revision `1f80d54...`。
7. 只读核对 private recapture artifact 唯一、0600、owner、claim+consumed markers、schema；不打印内容、路径或 hash。
8. fresh-read current Board C registration / pairing；不要相信本文中的旧 TTL。
9. 如果 durable hardware continuity、`node_id=NULL`、hardware not retired、credential absent、current PENDING + TTL margin 全部 PASS，则输出新的 rebind mutation preclaim closure。
10. 然后等待操作者明确授权 `R6-BOARD-C-PRIVATE-HANDOFF-FRESH-PAIRING-REBIND-20260829-01`（或按新日期生成 successor token）。
11. 未授权前不得改写 handoff、不得 import、不得访问 Board C。

---

## 16. 新会话禁止误读的事实

- `PRIVATE_SETUP_SECRET_SAME_AUTHORITY=PASS` 已经由本轮真实单次 serial recapture 证明；不要退回 UNKNOWN，除非 private evidence 本身无法恢复或损坏。
- `HISTORICAL_PRIVATE_SECRET_BYTEWISE_COMPARISON=NOT_EVALUATED` 不影响上述 PASS，不需要追补旧 secret byte copy。
- `HANDOFF_PAIRING_EQUALS_CURRENT=false` 是短 TTL pairing 前移，不是 secret mismatch。
- fresh-pairing preclaim 的 TTL 是历史观测，不是 future claim authority。
- R4 failed NODE_ID 已 retired 且不可复用；Board C hardware 本身未退休。
- current Board C 没有 active NODE_ID、没有 credential lifecycle residue、没有 DynSec orphan credential。
- historical C fingerprint 不具 current authority。
- consumed physical recapture authorization 永不可重放；后续不需要再次 serial capture 来处理 pairing renewal。

---

## 17. Session closure

```text
NORTH_STAR=FC4_FINAL_PHYSICAL_ACCEPTANCE
CURRENT_ROUTE_NODE=BOARD_C_FIRST_REGISTRATION
ACTIVE_DETOUR=NONE
NEW_BRANCH_ALLOWED=false

LAST_COMPLETED_PHYSICAL_GATE=BOARD_C_SETUP_SECRET_PHYSICAL_RECAPTURE
LAST_COMPLETED_PHYSICAL_GATE_RESULT=PASS
PRIVATE_SETUP_SECRET_SAME_AUTHORITY=PASS

LAST_COMPLETED_GATE=PRIVATE_HANDOFF_FRESH_PAIRING_REBIND_PRECLAIM
LAST_COMPLETED_GATE_RESULT=PASS

NEXT_GATE=PRIVATE_HANDOFF_FRESH_PAIRING_REBIND_MUTATION_AUTHORIZATION
NEXT_AUTHORIZATION_PROPOSED=R6-BOARD-C-PRIVATE-HANDOFF-FRESH-PAIRING-REBIND-20260829-01
NEXT_AUTHORIZATION_GRANTED=false

PRODUCT_BLOCKER_PROVEN=false
SECURITY_PRODUCT_REGRESSION_PROVEN=false
ACTIVE_FAILURE_STREAK=0
ROUTE_AUDIT_REQUIRED=false

SERIAL_OPEN_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
SETUP_SECRET_IMPORT_AUTHORIZED=false
REGISTRATION_APPROVAL_AUTHORIZED=false
NODE_ID_ASSIGNMENT_AUTHORIZED=false
CREDENTIAL_PROVISIONING_AUTHORIZED=false
```

本轮对话在此结束。新会话必须从上述 `NEXT_GATE` 继续，保持任务目标和 authority 连续性，不重复已经证明的 P3/P4/P5/physical recapture，除非新的 read-only rebaseline 明确发现漂移。
