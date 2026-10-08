# 温室环境监测系统（ESP32-C6）— N3-W
# Auto Safe Fallback Gate F — Clean Product-State Final Acceptance Preparation
# 新会话交接文档 V1.0 — 2026-10-05

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

> Formal process authority: exact historical handoff standard at `4300890dff0ce63d5a547df21426e287d084d9ee`, especially `docs/development/NEW_CHAT_HANDOFF_STANDARD.md` and `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`.
>
> If this handoff conflicts with fresh exact repository/runtime/live evidence, stop and rebind to the higher authority before execution.

---

## 0. 会话切换结论

本轮已经完成 Board B 的 Gate F R2 物理取证与根因闭环。Board B 证明了 stale Broker 自动发现/运行时 retarget/MQTT 恢复/业务 telemetry 到达 Manager 的主链路；最终 canonical 被 `stale_boot_session` 阻断，根因是 Board B 的历史 KF-050 boot-session 兼容性污染，而不是 R2 fallback 源码缺陷。

用户确认有全新未使用 ESP32-C6 板卡可用于最终 clean product-state 验收。正式产品路线因此从 Board B legacy migration 切换到全新板卡 clean-state Gate F。

```text
CURRENT_STAGE=GATE_F_CLEAN_PRODUCT_STATE_FINAL_ACCEPTANCE_PREPARATION
CURRENT_STOP_POINT=BOARD_B_ROOT_CAUSE_CLOSED_NEW_BOARD_NOT_YET_TOUCHED
NEXT_ONE_GATE=N3W_AUTO_SAFE_FALLBACK_GATE_F_CLEAN_PRODUCT_STATE_PREEXECUTION_DESIGN_20261005_01
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话不是重新复盘 Board B 全部历史，也不是执行 legacy recovery-floor helper；只从 `NEXT_ONE_GATE` 开始。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护 clean product-state Final Acceptance 产品路线；
- fresh rebind repository / PR / exact source / exact artifact / live T1 authority；
- 设计 clean board 资格、stale-Broker oracle、Gate F 物理验收、authorization 和 rollback；
- 根据 closure 做 PASS / FAIL / STOP；
- 区分 R2 fallback、legacy Board B compatibility、T1 deployment、physical harness 问题；
- 禁止为绕过 `stale_boot_session` 而降低 replay 安全语义。

### 1.2 Codex 低阶执行职责

- 机械执行 exact DSL contract；
- 运行最低必要 GitHub/SSH/Docker/network read-only 命令；
- 只在明确授权后访问/写入板卡或修改 T1；
- 第一处 substantive mismatch 后 STOP；
- 返回结构化 closure；
- 不自动设计 repair，不跨下一 gate。

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
高阶模型：fresh rebind / 设计单一 gate
        ↓
Codex：最低必要 read-only execution / evidence
        ↓
高阶模型：冻结 clean acceptance 方案
        ↓
用户：批准后续 exact physical mutation authorization（如需要）
        ↓
Codex：物理 preflight / write / acceptance
```

---

## 2. Product North Star

当前产品路线：

```text
T1 使用 DHCP / auto advertised host。
节点已经正常配对和运行后，即使 T1 的 LAN IPv4 地址变化，节点也不要求用户清配置或重新配对；
节点在持续 MQTT 失败达到阈值后，通过 Manager discovery 找到当前 T1，
只在 RAM 中临时 retarget Broker 地址，保留 TLS server name、CA、MQTT 身份和 durable pairing state，
恢复 Direct MQTT 与 canonical telemetry。
```

Final Gate F 目标：

```text
CLEAN_PRODUCT_STATE=true
STALE_BROKER_PRECONDITION=PROVEN
DISCOVERY_AND_RETARGET=PASS
MQTT_RECOVERY=PASS
CANONICAL_TELEMETRY_RECOVERY=PASS
NO_MANAGER_RESTART=true
NO_REPAIR_PAIRING=true
NO_REPLAY_HIGH_WATER_CLEAR=true
RECOVERY_WITHIN_NO_RELAY_BUDGET=true
```

当前不得进入：

```text
BOARD_B_LEGACY_RECOVERY_FLOOR_AS_PRODUCT_ACCEPTANCE
MANAGER_REPLAY_RELAXATION
MANAGER_HIGH_WATER_CLEAR
PR_522_MERGE
R3_SOURCE_MUTATION
```

---

## 3. Frozen Authorities

### 3.1 Repository / main / PR

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
MAIN_TREE=ee977996a4c962097684519841dce2e3bcba23f2
PR=522
PR_HEAD_BRANCH=fix/n3w-auto-safe-fallback-production-core-convergence-20261003
PR_STATE=OPEN_DRAFT
PR_MERGED=false
PR_HEAD_BEFORE_HANDOFF=00f34715c2ad3b97e46f5041bcb4ecf151ef9114
MERGE=false
```

Fresh new-chat PR HEAD read is still required because this handoff commit itself advances the branch.

### 3.2 Frozen R2 source

```text
R2_SOURCE_HEAD=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
R2_SOURCE_TREE=13354818653e27cad8891bd2f3555e4f3feccc2b
R2_SOURCE_REPAIR=PASS
R3_MUTATION=false
```

Later documentation commits are not product-source authority.

### 3.3 Exact artifact

```text
EXACT_ARTIFACT_WORKFLOW_RUN=37204582611
EXACT_ARTIFACT_ID=11303803442
EXACT_ARTIFACT_NAME=n3w-auto-safe-fallback-f1rc2-67a0460-r2-exact-source
ARTIFACT_OUTER_SHA256=be604ae4bba09d1a675017518a8847fdd655f2f5bb64dca200bb6e8d49378582
ARTIFACT_INNER_ZIP_SHA256=ae80eeb6a36d250ecdd3123f8ac084e40d7f4a47f7331b91a1d8b91818c74e7c
FIRMWARE_BIN_SHA256=7a4a53f08fd9550f46637a216f8bee89903428805f5de40d1e3bec9b17bc05ef
BOOTLOADER_SHA256=99662c9b4bc1ac74a6e38ac95c9340b72d0f08e43fdf546c080e56c976cfc3e5
PARTITIONS_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
OTADATA_INITIAL_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

### 3.4 Process / product authorities

```text
HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee
ADR_0008=docs/adr/0008-n3w-pairing-recovery-simplification-v2.md
KF050_AUTHORITY=docs/development/KF-050_N3W_BOOT_SESSION_CONTRACT_REPAIR.md
CURRENT_PROGRESS=docs/development/N3W_AUTO_SAFE_FALLBACK_GATE_F_CLEAN_PRODUCT_STATE_PROGRESS_ALIGNMENT_20261005.md
BOARD_B_ROOT_CAUSE=docs/development/N3W_AUTO_SAFE_FALLBACK_GATE_F_R2_POST_MQTT_TELEMETRY_FORENSIC_20261004.md
```

### 3.5 Target host / private network authority

```text
TARGET_HOST=T1
TARGET_ARCH=FRESH_READONLY_REBIND_REQUIRED
PRIVATE_LAN_ADDRESSES=DO_NOT_COMMIT_DERIVE_LIVE
MANAGER_CONTAINER=greenhouse-manager
BROKER_CONTAINER=FRESH_RUNTIME_RESOLUTION_REQUIRED
PAIRING_ADVERTISED_HOST_MODE=auto
```

---

## 4. Current Live Baseline

Latest direct evidence before handoff:

```text
MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=1
BROKER_RUNNING=true
MANAGER_DIRECT_SUBSCRIPTION=gh/v1/greenhouse/ingress/node/+/telemetry
T1_MUTATION_AFTER_FORENSIC=false
```

Board B:

```text
BOARD_B_R2_ARTIFACT_PRESENT=true
BOARD_B_LEGACY_KF050_CONTAMINATION=true
BOARD_B_MANAGER_RESULT=stale_boot_session
BOARD_B_FINAL_ACCEPTANCE_TARGET=false
```

Clean board route:

```text
CLEAN_BOARD_AVAILABLE=true
CLEAN_BOARD_IDENTITY_BOUND=false
CLEAN_BOARD_USB_CONNECTED=false
CLEAN_BOARD_FLASH_READ=false
CLEAN_BOARD_NVS_READ=false
CLEAN_BOARD_FLASH_WRITE=false
CLEAN_BOARD_PAIRED=false
CLEAN_BOARD_RF_EXECUTION=false
```

The new chat must fresh-read T1 runtime state before using it as current authority.

---

## 5. Proven Current Facts

```text
R2_STALE_BROKER_FAILURE_OBSERVED=true
R2_MANAGER_DISCOVERY=PASS
R2_RAM_ONLY_BROKER_RETARGET=PASS
R2_MQTT_RECONNECT=PASS
R2_BROKER_CANDIDATE_PROMOTION=PASS
R2_PRODUCTION_TELEMETRY_GENERATION=PASS
R2_DIRECT_MQTT_LOCAL_SUBMISSION=PASS
R2_BROKER_TO_MANAGER_DELIVERY=PASS
R2_MANAGER_DIRECT_SUBSCRIPTION=PASS
```

Board B root cause:

```text
MANAGER_HIGHEST_SESSION_HEX=dc40c82e1467cf88
MANAGER_HIGHEST_SESSION_DECIMAL=15870905187090026376
BOARD_B_BOOT_STATE_MAX_HEX_AT_READ=0000000000000011
BOARD_B_BOOT_STATE_MAX_DECIMAL_AT_READ=17
BOARD_B_COUNTER_LT_MANAGER_HIGH_WATER=true
MANAGER_RESULT=stale_boot_session
KF050_COMPATIBILITY_MIGRATION_GAP=CONFIRMED
R2_SOURCE_DEFECT=false
MANAGER_DEFECT=false
```

User-provided current fact:

```text
BRAND_NEW_UNUSED_BOARDS_AVAILABLE=true
```

Inference kept separate:

```text
INFERENCE_CLEAN_BOARD_CAN_AVOID_KF050_HISTORY=true
```

This must be proven by physical read-only preflight before the board is accepted as clean.

---

## 6. Current Root Cause / Blockers

### Blocker A — Final Gate F still lacks clean-state end-to-end canonical proof

```text
ROOT_CAUSE=BOARD_B_IS_NOT_A_VALID_CLEAN_FINAL_ACCEPTANCE_TARGET
PROVEN_BY=KF050_HIGH_WATER_COMPARISON_AND_ADR0008_BOUNDARY
SOURCE_DEFECT_PROVEN=false
RUNTIME_DEFECT_PROVEN=false
```

### Blocker B — Safe stale-Broker oracle for a clean board is not yet frozen

A brand-new board paired today will initially receive the current T1 Broker address. Final acceptance therefore needs a bounded, reversible method to make that durable address stale after a healthy clean baseline, without importing Board B historical state or editing replay high-water.

```text
STALE_BROKER_ORACLE_METHOD=NOT_YET_FROZEN
T1_NETWORK_MUTATION_REQUIRED=TO_BE_DETERMINED_BY_NEXT_GATE
ROLLBACK_PLAN_REQUIRED=true
```

---

## 7. Closed / Forbidden Routes

Unless new direct counter-evidence appears, do not reopen:

```text
R2_TRIGGER_NOT_RUNNING=CLOSED:R2 physical trigger/discovery observed
DISCOVERY_NOT_EMITTED=CLOSED:Manager request/response physically observed
BROKER_DISCOVERY_FAILURE=CLOSED
TLS_SERVER_NAME_MISMATCH=CLOSED:certificate SAN matches configured identity
MQTT_CREDENTIAL_MISMATCH=CLOSED:MQTT connects and Broker authenticates node
BROKER_ACL_BLOCK=CLOSED:Manager receives Direct ingress
MANAGER_DIRECT_SUBSCRIPTION_MISSING=CLOSED
R2_SOURCE_DEFECT_AFTER_R2_PHYSICAL=CLOSED
```

Forbidden:

```text
MANAGER_REPLAY_RELAXATION=FORBIDDEN
MANAGER_HIGH_WATER_CLEAR=FORBIDDEN
BOARD_B_LEGACY_HELPER_AS_FINAL_PRODUCT_ACCEPTANCE=FORBIDDEN
R3_SOURCE_MUTATION_WITHOUT_NEW_SOURCE_DEFECT=FORBIDDEN
PR_522_MERGE_BEFORE_FINAL_ACCEPTANCE=FORBIDDEN
```

---

## 8. Authorization Ledger

Historical physical authorization relevant to Board B:

```text
AUTHORIZATION=GATE_F_BOARD_B_R2_EXACT_ARTIFACT_MINIMAL_WRITE
CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
SUPERSEDED_BY=CLEAN_PRODUCT_STATE_ROUTE
```

```text
AUTHORIZATION=GATE_F_BOARD_B_CONTROLLED_FORENSIC_RESETS_AND_READS
CLAIMED=true
CONSUMED=true
RESULT=ROOT_CAUSE_CLOSED
REPLAY_PERMITTED=false
SUPERSEDED_BY=CLEAN_PRODUCT_STATE_ROUTE
```

User route approval on 2026-10-05:

```text
AUTHORIZATION=CLEAN_PRODUCT_STATE_FINAL_ACCEPTANCE_ROUTE
CLAIMED=false
CONSUMED=false
RESULT=ROUTE_APPROVED
REPLAY_PERMITTED=NOT_APPLICABLE
```

Next gate is read-only design/rebind and does not consume a physical mutation authorization.

```text
PROPOSED_AUTHORIZATION=CLEAN_PRODUCT_STATE_NEW_BOARD_PHYSICAL_PREFLIGHT
GRANTED=false
```

The exact physical scope must be designed first; `READY_FOR_NEW_AUTHORIZATION=true` is not itself authorization.

---

## 9. Rollback Authority

Next gate is read-only with optional bounded GitHub documentation write only.

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE:READONLY_DESIGN_GATE
FRESH_PRECHANGE_SNAPSHOT_REQUIRED=false
LIVE_RUNTIME_MUTATION=false
BOARD_MUTATION=false
```

Any later T1 address/network mutation must define a fresh rollback snapshot and exact reconnect/recovery path before authorization is claimed.

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_AUTO_SAFE_FALLBACK_GATE_F_CLEAN_PRODUCT_STATE_PREEXECUTION_DESIGN_20261005_01
```

### 10.1 Purpose

Without touching the new board or mutating T1, fresh-rebind the current repository/T1 authority and freeze the exact clean product-state Gate F execution design. The gate must determine how to prove a board is clean, how to create the stale-Broker condition after clean provisioning, how to roll it back, and what exact physical authorization is needed for the next gate.

### 10.2 Frozen inputs

```text
PR=522
R2_SOURCE_HEAD=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
R2_SOURCE_TREE=13354818653e27cad8891bd2f3555e4f3feccc2b
EXACT_ARTIFACT_ID=11303803442
PAIRING_ADVERTISED_HOST_MODE=auto
CLEAN_BOARD_AVAILABLE=true
BOARD_B_KF050_CONTAMINATION=EXCLUDED_FROM_FINAL_ACCEPTANCE
```

### 10.3 Required proof / operations

```text
1. Fresh rebind main, PR #522 HEAD/state, current progress docs, ADR-0008, KF-050 and exact artifact authority.
2. Read-only T1 rebind: Manager/Broker running state, restart counts, active Broker publication, current IPv4/network topology, pairing advertised-host mode, Manager loopback/Broker topology.
3. Do not commit private LAN addresses; use them only as live design evidence.
4. Define CLEAN_BOARD_ELIGIBILITY contract for the later physical preflight, including ROM identity, security flags, flash size, partition/NVS read and proof that no prior N3-W product identity/boot-state exists.
5. Define the clean baseline flow: exact artifact write -> first clean pairing/provisioning -> healthy Direct canonical baseline.
6. Compare candidate stale-Broker oracle methods and freeze exactly one reversible method. Prefer the method with the smallest T1/network blast radius and strongest proof that only Broker address becomes stale while TLS identity/credentials/node identity remain unchanged.
7. Define exact rollback authority for that stale-address mutation before any live mutation is authorized.
8. Define final acceptance clocks/oracles: stale-address precondition, discovery timing, MQTT reconnect, candidate promotion, first canonical telemetry, Manager restart invariants and <=120s no-Relay budget.
9. Produce one design closure and one exact next physical gate name. Do not access a board and do not execute the physical gate.
```

### 10.4 PASS

```text
CLEAN_PRODUCT_STATE_PREEXECUTION_DESIGN=PASS
CLEAN_BOARD_ELIGIBILITY_FROZEN=true
STALE_BROKER_ORACLE_METHOD_FROZEN=true
ROLLBACK_CONTRACT_FROZEN=true
FINAL_ACCEPTANCE_ORACLES_FROZEN=true
READY_FOR_CLEAN_BOARD_READONLY_PREFLIGHT=true
```

### 10.5 FAIL

```text
CLEAN_PRODUCT_STATE_PREEXECUTION_DESIGN=FAIL_<EXACT_CLASS>
READY_FOR_CLEAN_BOARD_READONLY_PREFLIGHT=false
AUTO_REPAIR=false
STOP=true
```

Codex/high-level model must not automatically enter the physical board gate.

---

## 11. Hard Allowed / Forbidden Scope

Default:

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

### ALLOWED

```text
- GitHub/repository read-only rebind
- PR #522 metadata/status read
- exact source/artifact authority verification
- T1 SSH read-only inspection
- docker inspect/log/config read
- ip addr/route/neigh/read-only network topology inspection
- architecture/design reasoning
- bounded documentation write under docs/development/ on the PR branch
```

```text
LIVE_RUNTIME_MUTATION=false
BOUNDED_EVIDENCE_FILESYSTEM_WRITE=true
BOUNDED_WRITE_SCOPE=docs/development/* on PR #522 branch only
```

### FORBIDDEN

```text
- any new-board USB/serial/flash/NVS access
- any Board B repair/migration
- T1 IP/address/interface/DHCP/route mutation
- Broker/Manager restart/recreate/config mutation
- pairing/credential mutation
- Manager replay/canonical high-water mutation
- source-code repair
- R3
- PR merge
```

---

## 12. Codex DSL Execution Contract

```text
ROLE:
Low-order executor.

This document is an executable DSL protocol.
A separately supplied Bash/Python executor is NOT required unless
this protocol explicitly says so.

Mechanically compile this DSL into the minimum necessary commands
using already-installed tools, then execute exactly the bounded gate.

DSL_TO_COMMAND_COMPILATION=true
SCOPE_EXPANSION=false
REPAIR=false
DESIGN_CHANGE=false

Do not repair.
Do not retry a substantive failed operation unless explicitly permitted.
Do not enter the next physical gate.
```

```text
============================================================
0. EXECUTION / AUTHORIZATION STATUS
============================================================
EXECUTION_ID=N3W_AUTO_SAFE_FALLBACK_GATE_F_CLEAN_PRODUCT_STATE_PREEXECUTION_DESIGN_20261005_01
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
T1_MUTATION=false
SOURCE_MUTATION=false
MERGE=false

============================================================
1. FROZEN INPUTS
============================================================
REPOSITORY=chrenguo-stack/HomeAssistant
PR=522
EXPECTED_PR_BRANCH=fix/n3w-auto-safe-fallback-production-core-convergence-20261003
R2_SOURCE_HEAD=67a0460231867b8e9b4cb7b7d5b0bd73478f4fc1
R2_SOURCE_TREE=13354818653e27cad8891bd2f3555e4f3feccc2b
EXACT_ARTIFACT_ID=11303803442
HANDOFF_STANDARD_AUTHORITY=4300890dff0ce63d5a547df21426e287d084d9ee

============================================================
2. HARD SCOPE
============================================================
ALLOW repository/GitHub reads.
ALLOW T1 live read-only inspect/log/network-state reads.
ALLOW bounded docs/development design/evidence write on PR branch.
DENY board access.
DENY T1 mutation.
DENY source mutation.
DENY replay/high-water mutation.
DENY merge.

============================================================
3. REPOSITORY REBIND
============================================================
Resolve current main HEAD/tree.
Resolve current PR #522 head/state/base/draft/merged/mergeable.
Verify the frozen R2 source commit/tree remains reachable.
Verify exact artifact metadata remains the intended Gate F artifact.
Read current Gate F progress/root-cause docs, ADR-0008, KF-050 and KNOWN_FAILURES.
If any authority materially contradicts this handoff: FAIL_AUTHORITY_DRIFT and STOP.

============================================================
4. T1 READONLY REBIND
============================================================
Resolve running Manager and Broker containers from live Docker metadata.
Read Manager restart count and relevant non-secret environment contract.
Read Broker 8883 publication/bind and Manager loopback topology.
Read host IPv4/interface/route state needed to reason about controlled address change.
Read pairing advertised-host mode and confirm auto semantics.
Do not change any address, route, container or config.
Do not persist private LAN addresses in public repository documents.

============================================================
5. CLEAN BOARD ELIGIBILITY DESIGN
============================================================
Freeze later physical-preflight criteria proving a candidate board is clean.
At minimum cover:
- expected ESP32-C6 target/revision/flash-size/security flags;
- unique ROM/base-MAC binding;
- read-only flash/partition/NVS inspection before first project write;
- absence of prior project N3-W durable peer/broker/setup/boot-state identity;
- no reuse of Board A/B stable identities;
- exact artifact binding before any write.
No board access in this gate.

============================================================
6. STALE-BROKER ORACLE DESIGN
============================================================
Enumerate only bounded feasible methods supported by current T1 topology.
Freeze exactly one method that, after clean pairing/baseline, makes the board's durable Broker host stale while preserving:
- same T1 logical identity;
- same Broker TLS server identity/CA;
- same node identity and MQTT credentials;
- Manager/Broker service continuity as far as the test requires.
Prefer minimum blast radius and deterministic rollback.
If no safe bounded method exists: FAIL_ORACLE_DESIGN and STOP.

============================================================
7. ROLLBACK / ACCEPTANCE CONTRACT
============================================================
Define fresh prechange snapshot requirements.
Define exact rollback order and reconnect proof.
Define stale-address precondition proof.
Define recovery timestamps and <=120s no-Relay budget.
Define successful Manager canonical advancement on the new boot/session.
Define Manager/Broker restart-count invariants.
Define hard STOPs.

============================================================
8. DESIGN CLOSURE
============================================================
Write one bounded design/progress document under docs/development/ if useful.
Return the structured closure below.
Do not access any board.
Do not claim physical acceptance.
Do not merge.

============================================================
9. HARD STOP
============================================================
STOP after design closure.
```

---

## 13. Expected Closure

```text
=== N3W CLEAN PRODUCT STATE PREEXECUTION DESIGN CLOSURE ===

EXECUTION_ID=N3W_AUTO_SAFE_FALLBACK_GATE_F_CLEAN_PRODUCT_STATE_PREEXECUTION_DESIGN_20261005_01

MAIN_HEAD=
PR522_HEAD=
PR522_STATE=
PR522_MERGED=
R2_SOURCE_BINDING=
EXACT_ARTIFACT_BINDING=

T1_READONLY_REBIND=
PAIRING_ADVERTISED_HOST_MODE=
BROKER_PUBLICATION_CONTRACT=
T1_NETWORK_TOPOLOGY_SUFFICIENT_FOR_DESIGN=

CLEAN_BOARD_ELIGIBILITY_FROZEN=
STALE_BROKER_ORACLE_METHOD=
T1_NETWORK_MUTATION_REQUIRED=
FRESH_ROLLBACK_SNAPSHOT_REQUIRED=
ROLLBACK_CONTRACT_FROZEN=
FINAL_ACCEPTANCE_ORACLES_FROZEN=

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
T1_MUTATION=false
SOURCE_MUTATION=false
MERGE=false

CLEAN_PRODUCT_STATE_PREEXECUTION_DESIGN=PASS|FAIL_<EXACT_CLASS>
READY_FOR_CLEAN_BOARD_READONLY_PREFLIGHT=true|false
NEXT_ROUTE=

STOP=true
=== END ===
```

---

## 14. After PASS / FAIL

### PASS 后

```text
AFTER_PASS_NEXT_STAGE=N3W_AUTO_SAFE_FALLBACK_GATE_F_CLEAN_PRODUCT_STATE_BOARD_READONLY_PREFLIGHT
AUTO_EXECUTE_AFTER_PASS=false
NEW_PHYSICAL_SCOPE_AUTHORIZATION_REQUIRED=true
```

### FAIL 后

```text
AUTO_REPAIR=false
AUTO_RETRY=false
RETURN_TO_HIGH_LEVEL_MODEL=true
```

---

## 15. KNOWN_FAILURES Updates

```text
KNOWN_FAILURES_UPDATE_REQUIRED=false
EXISTING_KF=KF-050
REASON=Current Board B stale_boot_session root cause is covered by existing KF-050 compatibility contract; this handoff introduces no new defect class.
```

Current route guard to preserve in progress docs:

```text
KF050_LEGACY_MIGRATION_NOT_FINAL_ACCEPTANCE=true
CLEAN_PRODUCT_STATE_REQUIRED_FOR_FINAL_GATE_F=true
```

---

## 16. New Chat Start Prompt

```text
阅读：

docs/development/N3W_AUTO_SAFE_FALLBACK_GATE_F_CLEAN_PRODUCT_STATE_PREEXECUTION_NEW_CHAT_HANDOFF_V1.0_20261005.md

同时读取 exact handoff process authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- PR #522
- docs/development/N3W_AUTO_SAFE_FALLBACK_GATE_F_CLEAN_PRODUCT_STATE_PROGRESS_ALIGNMENT_20261005.md
- docs/development/N3W_AUTO_SAFE_FALLBACK_GATE_F_R2_POST_MQTT_TELEMETRY_FORENSIC_20261004.md
- docs/development/KF-050_N3W_BOOT_SESSION_CONTRACT_REPAIR.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/adr/0008-n3w-pairing-recovery-simplification-v2.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3-W auto 安全回退路线
支线任务：Gate F clean product-state 最终验收
当前任务：N3W_AUTO_SAFE_FALLBACK_GATE_F_CLEAN_PRODUCT_STATE_PREEXECUTION_DESIGN_20261005_01

本轮继续采用高阶模型思考 + Codex 低阶执行。
Codex 可将 exact DSL contract 机械编译为最低必要命令；PREWRITTEN_EXECUTOR_REQUIRED=false。

必须先承认：
- Board B 已物理证明 R2 stale-Broker fallback 主链路通过；
- Board B canonical FAIL 的直接原因是 KF-050 历史 boot-session high-water 污染，不是 R2 source defect；
- ADR-0008 禁止把 legacy recovery-floor helper 当作 Final Product Acceptance authority；
- 用户有全新未使用板卡，最终 Gate F 改走 clean product-state 路线；
- PR #522 保持 OPEN/DRAFT/未合并，MERGE=false。

当前只进入：
NEXT_ONE_GATE=N3W_AUTO_SAFE_FALLBACK_GATE_F_CLEAN_PRODUCT_STATE_PREEXECUTION_DESIGN_20261005_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

先 fresh rebind repository/T1 read-only authority，冻结 clean board eligibility、stale-Broker oracle、rollback 和 final acceptance contract。
不要访问新板卡，不要改 T1，不要执行 recovery-floor，不要清 Manager replay/high-water，不要改 source，不要合并 PR。
完成 design closure 后 STOP。
```

---

## 17. Final Frozen State

```text
CURRENT_STAGE=GATE_F_CLEAN_PRODUCT_STATE_FINAL_ACCEPTANCE_PREPARATION
CURRENT_STOP_POINT=BOARD_B_KF050_ROOT_CAUSE_CLOSED_CLEAN_BOARD_ROUTE_SELECTED

R2_SOURCE_DEFECT_PROVEN=false
R2_FALLBACK_PHYSICAL_CHAIN=PASS
BOARD_B_CANONICAL_BLOCKER=KF050_LEGACY_BOOT_SESSION_HIGH_WATER
BOARD_B_FINAL_ACCEPTANCE_TARGET=false

CLEAN_BOARD_AVAILABLE=true
CLEAN_BOARD_TOUCHED=false
CLEAN_BOARD_IDENTITY_BOUND=false

PR=522
PR_STATE=OPEN_DRAFT
MERGE=false

NEXT_ONE_GATE=N3W_AUTO_SAFE_FALLBACK_GATE_F_CLEAN_PRODUCT_STATE_PREEXECUTION_DESIGN_20261005_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false

HANDOFF_STANDARD_VERSION=1.0
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
