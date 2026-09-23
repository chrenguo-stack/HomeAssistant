# N3-W Production Multi-Relay Gateway Selection V1
# Board B Exact-Write Preflight
# 新会话交接文档 V1.0 — 2026-09-23

```text
HANDOFF_STANDARD_VERSION=1.0
EXECUTION_MODEL=HIGH_LEVEL_MODEL_PLUS_CODEX_LOW_ORDER_EXECUTION
DSL_EXECUTION_MODEL=true
PREWRITTEN_EXECUTOR_REQUIRED=false
NEXT_ONE_GATE_ONLY=true
```

> 本文符合 `docs/development/NEW_CHAT_HANDOFF_STANDARD.md`。  
> 如本文与 fresh exact repository/runtime/live evidence 冲突，以 fresh exact evidence 为准，并先停止执行、完成 rebind。  
> 本文承接 Board A exact write + postwrite readonly forensic + OTA-data post-reset validator source repair 的闭环状态。

---

## 0. 会话切换结论

本轮已经完成 Board A exact artifact 写入闭环，并完成执行器 OTA-data post-reset validator 的源码/测试修复。继续在原会话进入 Board B 会增加上下文漂移风险，因此在 Board B 物理访问前切换新会话。

```text
CURRENT_STAGE=
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1_THREE_BOARD_DEPLOYMENT

CURRENT_STOP_POINT=
BOARD_A_WRITE_CLOSED_PASS_AND_VALIDATOR_REPAIR_CLOSED_PASS

NEXT_ONE_GATE=
N3W_PRODUCTION_GWSEL_V1_BOARD_B_EXACT_WRITE_PREFLIGHT_20260923_01

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
HANDOFF_READY_FOR_NEW_CHAT=true
```

下一会话不是重新复盘历史，而是 fresh rebind 本文列出的 authorities，然后只进入 Board B fresh exact-write **只读预检**。

---

## 1. 执行模式

### 1.1 高阶模型职责

- 维护 Production Multi-Relay Gateway Selection V1 产品路线与 exact authority；
- 维护 artifact / exact executor / board identity / partition / authorization 边界；
- 设计每个 board gate，严格保持 A → STOP → B → STOP → C → STOP；
- 根据执行 closure 做 PASS / FAIL / STOP 分类；
- 区分产品缺陷、执行器/physical-harness 缺陷、网络/CI 缺陷；
- 禁止因为执行器问题自动改产品源码或重刷实板。

### 1.2 Codex 低阶执行职责

- 机械执行 exact contract；
- mutation 只能发生在独立、明确、board-specific authorization 内；
- 第一处 substantive mismatch fail-closed STOP；
- 不得扩大 scope、自动修复、自动重试、自动重刷、自动 erase；
- 不得重放 Board A 已消费的 authorization；
- 不得自动跨到 Board B write 或 Board C。

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

本阶段存在已经审计并 CI 验证的 exact executor，因此：

```text
STAGE_EXACT_EXECUTOR_AUTHORITY=true
STAGE_EXACT_EXECUTOR_PATH=
tools/execution_packages/n3w/production/gwsel_v1_three_board_write/executor.py

STAGE_EXACT_EXECUTOR_HEAD=
9c83c66de9fb64609e27437e1b392c2dd6f2f37f
```

下一会话不得用旧 executor HEAD `33e665...` 执行 Board B/C write/preflight authority。

### 1.4 标准交互循环

```text
高阶模型：fresh rebind / gate / authorization
        ↓
用户：确认 Board B 物理连接 + 只读 reset/ROM authorization
        ↓
exact executor：fresh readonly preflight
        ↓
高阶模型：裁决 PASS/FAIL
        ↓
STOP
```

Board B firmware write 必须是后续独立 gate 和独立授权。

---

## 2. Product North Star

当前产品路线：

```text
N3W_PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1
```

目标是把同一个 exact production artifact 顺序部署到 A/B/C，并在三块物理板上验证：

- A/B 都可作为 Direct-connected Relay/Gateway candidate；
- C 为移动 Child；
- Child 仅在 Discovery 期间做候选选择；
- 6500 ms candidate window；
- strongest RSSI + 3 dB equivalence band + deterministic SHA-256 tie-break；
- sticky active Relay；
- 不做 proactive roaming；
- 不做动态负载均衡；
- Gateway fail/reselection 与 same-boot Relay→Direct 恢复按冻结设计验证。

最终 physical acceptance 需要三块板，不允许用两块板替代。

当前不得进入：

```text
THREE_BOARD_RF_VALIDATION=false
MANAGER_RUNTIME_MUTATION=false
BROKER_MUTATION=false
BOARD_C_WRITE=false
BOARD_B_WRITE=false
BOARD_A_REFLASH=false
```

---

## 3. Frozen Authorities

### 3.1 Repository / main snapshot

交接时 fresh main：

```text
REPOSITORY=chrenguo-stack/HomeAssistant

MAIN_AT_HANDOFF=
3b4a75b039a8d5d9572b4a8f7cfb1e580e7f3476

MAIN_TREE_AT_HANDOFF=
f19701fb432f76d6913fed38891b8cbeedeb124f
```

main 是 repository snapshot authority；当前 Gateway Selection V1 product source 与 exact executor 分别由下面独立 authority 冻结。

### 3.2 Product source authority

```text
PRODUCT_SOURCE_BRANCH=
fix/n3w-production-multi-relay-gateway-selection-v1-source-repair-r2-20260922

PRODUCT_SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

PRODUCT_SOURCE_TREE=
e9c0216c4a25e99038ff81e54036455cb32b4181

PRODUCT_SOURCE_CI_RUN=
35708774330

PRODUCT_SOURCE_CI=PASS
```

产品固件源码没有因为本轮 OTA validator 缺陷而改变。

### 3.3 Exact production artifact

```text
ARTIFACT_ID=10693728323
ARTIFACT_NAME=
n3w-production-gwsel-v1-r2-8c445f2-exact-source

ARTIFACT_OUTER_SIZE=4281423
ARTIFACT_OUTER_SHA256=
e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814

RELEASE_BUNDLE_SHA256=
f7c7ac703e6b23040235020c92e480f08c602076d32afa18c8a37e5da3882598

ARTIFACT_EXPIRES_AT=
2026-10-22T12:38:37Z
```

关键 inner bindings：

```text
APPLICATION_OFFSET=0x10000
APPLICATION_SIZE=1392960
APPLICATION_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

OTADATA_OFFSET=0x9000
OTADATA_SIZE=8192
OTADATA_INITIAL_SHA256=
7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

PARTITION_TABLE_OFFSET=0x8000
PARTITION_TABLE_SIZE=3072
PARTITION_TABLE_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
```

如果 artifact 到期、不可下载或 hash 不匹配：

```text
AUTO_REBUILD=false
AUTO_SUBSTITUTE_ARTIFACT=false
STOP_FOR_EXACT_ARTIFACT_REBIND=true
```

### 3.4 Exact write executor repair authority

```text
EXECUTOR_REPAIR_BRANCH=
fix/n3w-production-gwsel-v1-otadata-postreset-validator-20260923

EXECUTOR_REPAIR_BASE=
33e6658244146d890887876ba18f32dd61a879b5

EXECUTOR_REPAIR_HEAD=
9c83c66de9fb64609e27437e1b392c2dd6f2f37f

EXECUTOR_REPAIR_TREE=
65b6e3c1465c49b40098154695d92370741ef487

EXECUTOR_REPAIR_CI_RUN=
35829956273

EXECUTOR_REPAIR_CI=PASS
```

CI:
https://github.com/chrenguo-stack/HomeAssistant/actions/runs/35829956273

### 3.5 Frozen write route

```text
WRITE 0x9000  ota_data_initial.bin
WRITE 0x10000 firmware.bin

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FACTORY_IMAGE_WRITE=false
FULL_FLASH_ERASE=false
BLIND_EXECUTION_OF_RELEASE_FLASH_ARGS=FORBIDDEN
```

该 write route **不是**下一门 Board B preflight 的授权；这里只作为后续 write authority 冻结。

### 3.6 OTA post-reset runtime contract

```text
OTADATA_POSTRESET_OTA_SEQ=1
OTADATA_POSTRESET_STATE=VALID
OTADATA_POSTRESET_CRC=0x4743989a

OTADATA_POSTRESET_RUNTIME_SHA256=
8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3
```

### 3.7 Board identity authority

Public-safe hardware identity SHA-256：

```text
BOARD_A=
f1f1e36fe4784a26b936d6a2bc5d239ab531f5683aca91356a5e39f3f566b1eb

BOARD_B=
cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0

BOARD_C=
d6ef3f98a35f06a5a8b8e7716a015e17336242128b314a1b3244b114fc6f72e2
```

Raw MAC 仍为 private physical identity，不得提交公共 GitHub。

### 3.8 Partition layout

```text
otadata  offset=0x9000   size=0x2000
phy_init offset=0xB000   size=0x1000
app0     offset=0x10000  size=0x3C0000
app1     offset=0x3D0000 size=0x3C0000
nvs      offset=0x790000 size=0x70000
```

---

## 4. Current Live Baseline

### 4.1 Board A

```text
BOARD_A_EXACT_WRITE_PHYSICAL_RESULT=
PASS_AFTER_READONLY_FORENSIC

BOARD_A_EXACT_ARTIFACT_APPLICATION_BINDING=PASS
BOARD_A_PARTITION_TABLE_PRESERVED=PASS
BOARD_A_BOOT_SELECTION_STATE=VALID_OTA0
BOARD_A_REFLASH_REQUIRED=false

BOARD_A_APPLICATION_READBACK_SHA256=
c98010719f37af69142a0ee318ff1577a064215e580b5182dc98556b11560a5a

BOARD_A_OTADATA_RUNTIME_SHA256=
8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3

BOARD_A_RUNTIME_DIRECT_BASELINE=NOT_EXECUTED
```

Board A 不得因为旧 executor 的 false-negative 再刷一次。

### 4.2 Board B

```text
BOARD_B_IDENTITY_BINDING=PASS
BOARD_B_STATIC_WRITE_TARGET_COMPATIBILITY=PASS

BOARD_B_CURRENT_EXACT_ARTIFACT_10693728323_DEPLOYMENT=
NOT_EXECUTED

BOARD_B_FRESH_EXACT_WRITE_PREFLIGHT=
NOT_EXECUTED
```

历史静态 preflight 不能代替下一门 fresh preflight。

### 4.3 Board C

```text
BOARD_C_IDENTITY_BINDING=PASS
BOARD_C_STATIC_WRITE_TARGET_COMPATIBILITY=PASS

BOARD_C_CURRENT_EXACT_ARTIFACT_10693728323_DEPLOYMENT=
NOT_EXECUTED
```

### 4.4 T1 / Manager / Broker / HA

本轮没有为三板 Gateway Selection physical acceptance fresh rebind T1 runtime。

```text
MANAGER_STATE=REQUIRES_FRESH_READONLY_REBIND_BEFORE_RF_ACCEPTANCE
BROKER_STATE=REQUIRES_FRESH_READONLY_REBIND_BEFORE_RF_ACCEPTANCE
HOMEASSISTANT_STATE=REQUIRES_FRESH_READONLY_REBIND_BEFORE_RF_ACCEPTANCE

T1_RUNTIME_MUTATION=false
```

这不阻塞下一门 Board B write-target readonly preflight。

### 4.5 Handoff physical boundary

```text
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
NVS_MUTATION=false
RF_EXECUTION=false
```

---

## 5. Proven Current Facts

```text
THREE_BOARD_STATIC_WRITE_TARGET_COMPATIBILITY=PASS

BOARD_A_EXACT_WRITE_PHYSICAL_RESULT=
PASS_AFTER_READONLY_FORENSIC

BOARD_A_REFLASH_REQUIRED=false

OTADATA_POSTRESET_VALIDATOR_SOURCE_REPAIR=CLOSED_PASS

EXECUTOR_FALSE_NEGATIVE_ROOT_CAUSE=PROVEN

PRODUCT_FIRMWARE_SOURCE_CHANGED_BY_VALIDATOR_REPAIR=false

GWSEL_V1_EXACT_WRITE_ROUTE_FROZEN=true
GWSEL_V1_EXACT_WRITE_EXECUTOR_REPAIR_CI=PASS

REAL_SENSOR_DATA_USED_IN_CURRENT_COMMUNICATION_PHYSICAL_TEST=false
REAL_SENSOR_TELEMETRY_END_TO_END_PHYSICAL_ACCEPTANCE=NOT_PROVEN
```

Board A physical forensic directly proved:

```text
OTA0_SEQ=1
OTA0_STATE=VALID
OTA0_CRC=0x4743989a
APPLICATION_EXACT_SHA=PASS
PARTITION_TABLE_EXACT_SHA=PASS
```

---

## 6. Current Root Cause / Blockers

### 6.1 Closed root cause — old post-reset validator false negative

```text
ROOT_CAUSE=
OLD_EXECUTOR_COMPARED_POST_HARD_RESET_OTADATA_TO_INITIAL_ALL_FF_IMAGE

SOURCE_DEFECT_PROVEN=true
DOMAIN=PHYSICAL_HARNESS
REPAIR=CLOSED_PASS
KF=KF-097
```

该问题已经关闭，不是当前 blocker。

### 6.2 Current deployment prerequisite

```text
CURRENT_SOURCE_BLOCKER_COUNT=0

CURRENT_DEPLOYMENT_PREREQUISITE=
BOARD_B_FRESH_EXACT_WRITE_PREFLIGHT_NOT_YET_EXECUTED
```

下一门只解决这个 prerequisite。

---

## 7. Closed / Forbidden Routes

除非出现新的 direct counter-evidence，不得重新进入：

```text
ARTIFACT_10691518958_GATEWAY_SELECTION_PHYSICAL_USE=FORBIDDEN

OLD_EXECUTOR_HEAD_33e665_FOR_BOARD_B_C_DEPLOYMENT=SUPERSEDED
OLD_POSTRESET_OTADATA_EQUALS_INITIAL_IMAGE_RULE=FORBIDDEN

BOARD_A_REFLASH_FOR_OLD_OTADATA_MISMATCH=FORBIDDEN

BLIND_EXECUTION_OF_RELEASE_FLASH_ARGS=FORBIDDEN
FACTORY_IMAGE_WRITE=FORBIDDEN
BOOTLOADER_WRITE=FORBIDDEN
PARTITION_TABLE_WRITE=FORBIDDEN
PRODUCT_NVS_WRITE=FORBIDDEN
FULL_FLASH_ERASE=FORBIDDEN

AUTO_RETRY_AFTER_CLAIM=FORBIDDEN
AUTO_REFLASH_AFTER_CLAIM=FORBIDDEN
AUTO_ERASE_AFTER_CLAIM=FORBIDDEN

TWO_BOARD_SUBSTITUTE_FOR_THREE_BOARD_ACCEPTANCE=FORBIDDEN

PROACTIVE_RELAY_ROAMING=OUT_OF_SCOPE
DYNAMIC_RELAY_LOAD_BALANCING=OUT_OF_SCOPE
```

历史 KF-096 保持 CLOSED_PASS / GUARDED，不重开。

---

## 8. Authorization Ledger

### 8.1 Board A exact firmware write R3

```text
AUTHORIZATION=
AUTHORIZE_BOARD_A_EXACT_FIRMWARE_WRITE_R3

CLAIMED=true
CONSUMED=true

RESULT=
PASS_AFTER_READONLY_FORENSIC

REPLAY_PERMITTED=false
SUPERSEDED_BY=NONE
```

旧 executor return code=2 不改变 authorization 已消费事实。

### 8.2 Board A postwrite readonly forensic

```text
AUTHORIZATION=
AUTHORIZE_BOARD_A_POSTWRITE_TEMPORARY_RESET_READONLY_FORENSIC

CLAIMED=true
CONSUMED=true
RESULT=PASS
REPLAY_PERMITTED=false
```

### 8.3 Prior Board A preflight/write attempts

```text
PRIOR_BOARD_A_PREFLIGHT_AUTHORIZATIONS=CLOSED_OR_SUPERSEDED
PRIOR_BOARD_A_WRITE_AUTHORIZATIONS=CLOSED_OR_SUPERSEDED
REPLAY_PERMITTED=false
```

不得复用 R1/R2/R3 的旧 preflight JSON 或旧 write authorization。

### 8.4 Proposed Board B preflight authorization

```text
PROPOSED_AUTHORIZATION=
AUTHORIZE_BOARD_B_TEMPORARY_RESET_READONLY_EXACT_WRITE_PREFLIGHT

GRANTED=false
CLAIMED=false
CONSUMED=false
REPLAY_PERMITTED=false
```

新会话必须先得到用户 fresh 明确授权。

### 8.5 Board B write authorization

```text
PROPOSED_AUTHORIZATION=
AUTHORIZE_BOARD_B_EXACT_FIRMWARE_WRITE

GRANTED=false
CLAIMED=false
CONSUMED=false
```

Board B preflight PASS 也不等于 write 授权。

---

## 9. Rollback Authority

下一门是 readonly preflight：

```text
ROLLBACK_AUTHORITY=NOT_APPLICABLE
REASON=NEXT_GATE_HAS_NO_PERSISTENT_MUTATION

FRESH_PRECHANGE_SNAPSHOT_REQUIRED=false
PERSISTENT_BOARD_MUTATION=false
```

ROM/esptool 只读检查可能临时 reset / 进入 ROM bootloader：

```text
ROM_OR_BOOTLOADER_ENTRY_MAY_REQUIRE_RESET=true
EPHEMERAL_RESET_IF_REQUIRED_MUST_BE_EXPLICITLY_AUTHORIZED=true
```

不得把“允许 reset”写成“已观察到 reset”；只有日志直接证明时才能记录实际发生。

如果未来进入 Board B write gate，rollback/retry contract 必须重新定义；本 handoff 不授予该 mutation。

---

## 10. Next ONE Gate

```text
NEXT_ONE_GATE=
N3W_PRODUCTION_GWSEL_V1_BOARD_B_EXACT_WRITE_PREFLIGHT_20260923_01
```

### 10.1 Purpose

Fresh 证明当前唯一连接的物理板确实是 frozen Board B，并证明它仍满足 exact artifact write target 的安全条件。

### 10.2 Operator physical precondition

必须先满足：

```text
BOARD_A_DISCONNECTED=true
BOARD_C_DISCONNECTED=true
BOARD_B_ONLY_CONNECTED=true
```

然后用户明确给出：

```text
BOARD_B_CONNECTED=true
AUTHORIZE_BOARD_B_TEMPORARY_RESET_READONLY_EXACT_WRITE_PREFLIGHT=true
```

没有这两个 fresh confirmation，不访问板卡。

### 10.3 Frozen inputs

```text
EXECUTOR_HEAD=
9c83c66de9fb64609e27437e1b392c2dd6f2f37f

EXPECTED_BOARD_B_HARDWARE_ID_SHA256=
cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0

ARTIFACT_ID=10693728323
ARTIFACT_OUTER_SHA256=
e57f71c8c2a4f3c722bde88fe7bfdde64fa48be8a11284009358990882286814

EXPECTED_PARTITION_TABLE_SHA256=
6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca

EXPECTED_CHIP=ESP32-C6
EXPECTED_FLASH_SIZE=8MB
EXPECTED_SECURE_BOOT=false
EXPECTED_FLASH_ENCRYPTION=false
```

### 10.4 Allowed operations

只允许：

```text
fresh Git/source/artifact rebind
artifact download/cache + exact size/hash verification
exact repaired executor materialization
exactly one eligible /dev/cu.usbmodem* locator
esptool get-security-info
esptool flash-id
read-flash 0x8000 0x0c00
read-flash 0x9000 0x2000
private mode-0600 preflight JSON creation
```

preflight JSON：

```text
MAX_AGE_SECONDS=900
SINGLE_USE_FOR_LATER_WRITE=true
PUBLICATION=FORBIDDEN
```

raw MAC 和 raw USB path 不得提交公共 GitHub。

### 10.5 Forbidden operations

```text
write-flash
erase-flash
erase-region
NVS mutation
partition-table write
bootloader write
factory-image write
full-flash erase
application serial open
RF test
T1 mutation
Board A access
Board C access
automatic Board B write
```

### 10.6 PASS conditions

全部成立才 PASS：

```text
BOARD_B_SINGLE_USB_TARGET=PASS
BOARD_B_FROZEN_IDENTITY_MATCH=PASS
CHIP=ESP32-C6
FLASH_SIZE=8MB
SECURE_BOOT=false
FLASH_ENCRYPTION=false

BOARD_B_FRESH_PARTITION_BINDING=PASS
BOARD_B_EXACT_ARTIFACT_BINDING=PASS
BOARD_B_MINIMAL_WRITE_ROUTE_BINDING=PASS

FLASH_WRITE=false
NVS_WRITE=false
WRITE_AUTHORIZATION_GRANTED=false
```

Board B 当前 OTA-data hash 只记录 boot-selection state，不参与 silicon identity。

### 10.7 FAIL / STOP conditions

任一项出现立即 STOP：

```text
identity mismatch
more than one or zero eligible USB modem target
wrong chip
flash size != 8MB
Secure Boot not proven disabled
Flash Encryption not proven disabled
partition-table hash mismatch
artifact unavailable/expired/hash mismatch
executor HEAD/tree drift
unsupported/malformed EUI64
unexpected write/mutation
```

失败后：

```text
AUTO_REPAIR=false
AUTO_RETRY=false
AUTO_REFLASH=false
AUTO_ERASE=false
STOP_AND_REVIEW=true
```

### 10.8 STOP boundary

无论 PASS 还是 FAIL，本 gate 结束后：

```text
BOARD_B_FIRMWARE_WRITE=false
STOP=true
```

---

## 11. Hard Allowed / Forbidden Scope

全局默认：

```text
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

本 gate 用户授权前：

```text
BOARD_ACCESS=false
```

得到 Board B readonly physical authorization 后：

```text
BOARD_ACCESS=true
READ_ONLY=true
FLASH_READ=true
FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_BOARD_MUTATION=false
```

强制禁止：

```text
AUTO_EXECUTE_NEXT_GATE=false
AUTO_WRITE_AFTER_PREFLIGHT=false
AUTHORIZATION_INHERITANCE_ACROSS_BOARDS=false
```

---

## 12. Codex DSL Execution Contract

下一会话首先 fresh rebind：

```text
READ handoff authority
READ NEW_CHAT_HANDOFF_STANDARD authority
READ N3W_CURRENT_STATE.md
READ N3W_CURRENT_STATE_INDEX.md
READ KNOWN_FAILURES_AND_REGRESSION_GUARDS.md

REBIND main
REBIND product source HEAD 8c445...
REBIND executor repair HEAD 9c83c66...
REBIND artifact 10693728323 metadata
VERIFY CI run 35829956273 belongs to exact executor repair HEAD
```

若 fresh rebind PASS，且用户提供 Board B connection/reset authorization：

```text
VERIFY exactly one USB modem locator
VALIDATE artifact exact size/hash
MATERIALIZE exact repaired executor
RUN executor preflight --board B
USE exact target token:
BOARD_B_CONNECTED_FOR_GWSEL_V1_EXACT_WRITE_PREFLIGHT
CAPTURE public-safe closure only
STOP
```

因为本阶段已经冻结 exact executor：

```text
AD_HOC_REIMPLEMENTATION_OF_BOARD_IDENTITY_PARSER=false
AD_HOC_REIMPLEMENTATION_OF_WRITE_ROUTE=false
OLD_EXECUTOR_FALLBACK=false
```

---

## 13. Expected Closure

下一门 stable closure 至少应输出：

```text
=== N3W GWSEL V1 BOARD B EXACT-WRITE READONLY PREFLIGHT CLOSURE ===

TASK=
N3W_PRODUCTION_GWSEL_V1_BOARD_B_EXACT_WRITE_PREFLIGHT_20260923_01

BOARD_LABEL=B

AUTHORIZATION=
AUTHORIZE_BOARD_B_TEMPORARY_RESET_READONLY_EXACT_WRITE_PREFLIGHT
AUTHORIZATION_CLAIMED=<true|false>
AUTHORIZATION_CONSUMED=<true|false>

EXECUTOR_HEAD_BINDING=<PASS|FAIL>
ARTIFACT_BINDING=<PASS|FAIL>
BOARD_B_SINGLE_USB_TARGET=<PASS|FAIL>
BOARD_B_FROZEN_IDENTITY_MATCH=<PASS|FAIL>

CHIP=<value>
FLASH_SIZE=<value>
SECURE_BOOT=<value>
FLASH_ENCRYPTION=<value>

PARTITION_TABLE_SHA256=<public safe hash>
CURRENT_OTADATA_SHA256=<public safe hash>

BOARD_B_FRESH_PARTITION_BINDING=<PASS|FAIL>
BOARD_B_EXACT_ARTIFACT_BINDING=<PASS|FAIL>
BOARD_B_MINIMAL_WRITE_ROUTE_BINDING=<PASS|FAIL>

FLASH_READ=<true|false>
FLASH_WRITE=false
NVS_WRITE=false
PERSISTENT_BOARD_MUTATION=false
WRITE_AUTHORIZATION_GRANTED=false

RESULT=<PASS|FAIL|STOP>

NEXT_ROUTE=
<BOARD_B_EXACT_WRITE_AUTHORIZATION_OR_STOP_AND_REVIEW>

STOP=true

=== END ===
```

不得输出 raw MAC、private USB path、credentials 或 raw NVS。

---

## 14. After PASS / FAIL

### After PASS

只允许提出下一门：

```text
PROPOSED_NEXT_ONE_GATE=
N3W_PRODUCTION_GWSEL_V1_BOARD_B_EXACT_WRITE_20260923_01
```

但：

```text
BOARD_B_WRITE_AUTHORIZATION_GRANTED=false
AUTO_EXECUTE=false
STOP=true
```

用户必须另外明确授权 Board B firmware write。

### After FAIL / STOP

```text
AUTO_SOURCE_CHANGE=false
AUTO_REPAIR=false
AUTO_RETRY=false
AUTO_REFLASH=false
AUTO_ERASE=false
STOP_AND_REVIEW=true
```

partition mismatch → `STOP_FOR_PARTITION_MIGRATION_REVIEW`。  
security mismatch → `STOP_FOR_SECURITY_COMPATIBILITY_REVIEW`。  
artifact unavailable/expired → `STOP_FOR_EXACT_ARTIFACT_REBIND`。

---

## 15. KNOWN_FAILURES Updates

本轮新增：

```text
KF-097
DOMAIN=PHYSICAL_HARNESS
STATUS=GUARDED
```

现象：Board A exact write command 已成功，但旧 executor 在 hard-reset 后用 initial all-erased OTA-data hash 校验 runtime OTA-data，产生 false-negative。

回归保护：

```text
POSTRESET_RUNTIME_OTADATA_CONTRACT=TESTED
INITIAL_ALL_FF_OTADATA_REJECTED_AS_POSTRESET_STATE=TESTED
WRITE_COMMAND_HARD_RESET=TESTED
APPLICATION_READBACK_EXACT_SHA=TESTED
PARTITION_TABLE_READBACK_EXACT_SHA=TESTED
NO_AUTOMATIC_DESTRUCTIVE_RECOVERY=TESTED
```

同时保持：

```text
KF-096=CLOSED_PASS/GUARDED
KF-092=CLOSED_PASS/GUARDED
```

不得因进入新会话重新打开。

---

## 16. New Chat Start Prompt

复制以下内容启动新会话：

```text
阅读：

docs/development/N3W_PRODUCTION_GWSEL_V1_BOARD_B_EXACT_WRITE_PREFLIGHT_NEW_CHAT_HANDOFF_V1.0_20260923.md

同时读取 exact handoff standard authority：
4300890dff0ce63d5a547df21426e287d084d9ee

- docs/development/NEW_CHAT_HANDOFF_STANDARD.md
- docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md

并 fresh rebind：
- repository main
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- fix/n3w-production-multi-relay-gateway-selection-v1-source-repair-r2-20260922
  exact product HEAD:
  8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c
- fix/n3w-production-gwsel-v1-otadata-postreset-validator-20260923
  exact executor repair HEAD:
  9c83c66de9fb64609e27437e1b392c2dd6f2f37f
- artifact 10693728323
- CI run 35829956273

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

每次回复先写：
主线任务：N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE
支线任务：Production Multi-Relay Gateway Selection V1
当前任务：<current gate>

必须先承认：
- Board A exact write 已经通过 postwrite readonly forensic 正式裁决为 PASS；
- Board A 不需要 reflash；
- 旧 executor HEAD 33e665... 的 OTA-data post-reset validator 有 false-negative 缺陷，已被 9c83c66... 修复并由 CI 35829956273 PASS；
- KF-097=GUARDED；
- Board B/C 还没有部署 current exact artifact 10693728323；
- 下一门只允许 Board B fresh exact-write readonly preflight，不允许直接写 Board B；
- 不继承任何 Board A authorization；
- 不自动进入后续 gate。

当前唯一下一门：
NEXT_ONE_GATE=
N3W_PRODUCTION_GWSEL_V1_BOARD_B_EXACT_WRITE_PREFLIGHT_20260923_01

在任何 Board B USB/ROM 访问前，必须要求：
BOARD_B_CONNECTED=true
AUTHORIZE_BOARD_B_TEMPORARY_RESET_READONLY_EXACT_WRITE_PREFLIGHT=true

保持：
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
AUTO_RETRY=false
AUTO_REFLASH=false
AUTO_ERASE=false
STOP_AND_REVIEW=true
```

---

## 17. Final Frozen State

```text
PRIMARY_TASK=
N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE

SUBTASK=
PRODUCTION_MULTI_RELAY_GATEWAY_SELECTION_V1

PRODUCT_SOURCE_HEAD=
8c445f2bdd60d9ac3a33fe7c20a01965360a3b1c

EXACT_ARTIFACT_ID=
10693728323

EXECUTOR_REPAIR_HEAD=
9c83c66de9fb64609e27437e1b392c2dd6f2f37f

EXECUTOR_REPAIR_CI_RUN=
35829956273

BOARD_A_EXACT_WRITE=
PASS_AFTER_READONLY_FORENSIC

BOARD_A_REFLASH_REQUIRED=false

BOARD_B_STATIC_WRITE_TARGET_COMPATIBILITY=PASS
BOARD_B_CURRENT_ARTIFACT_DEPLOYMENT=NOT_EXECUTED

BOARD_C_STATIC_WRITE_TARGET_COMPATIBILITY=PASS
BOARD_C_CURRENT_ARTIFACT_DEPLOYMENT=NOT_EXECUTED

KF097=GUARDED

NEXT_ONE_GATE=
N3W_PRODUCTION_GWSEL_V1_BOARD_B_EXACT_WRITE_PREFLIGHT_20260923_01

BOARD_ACCESS=false
FLASH_WRITE=false
NVS_WRITE=false
RF_EXECUTION=false
STOP=true
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
