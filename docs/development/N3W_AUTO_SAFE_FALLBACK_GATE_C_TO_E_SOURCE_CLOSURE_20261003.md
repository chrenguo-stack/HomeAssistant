# N3-W auto 安全回退 Gate C–E 源码侧收口与生产路径纠偏

日期：2026-10-03  
分支：`fix/n3w-auto-safe-fallback-v1-20260929`  
PR：#516（Draft）

> 2026-10-03 后续 F1 准备时发现：本轮 Gate B/C 实现和 CI 绑定的是 `greenhouse_n3w_core` lab/physical-harness 路径，而正式 F1.0-RC2 生产固件加载独立 `greenhouse_n3w_product_core`。因此本文件保留 Gate C lab/reference 路径的闭合证据，但**撤销此前“整个产品 SOURCE_REPAIR_COMPLETE=true”的表述**。正式生产路径必须先做 production-core convergence，才能进入 Gate F 物理验收。

```text
TASK=N3W_AUTO_SAFE_FALLBACK_GATE_C_TO_E_SOURCE_CLOSURE_20261003_01
GATE_A=CLOSED_PASS
GATE_B=CLOSED_PASS

REFERENCE_VALIDATED_HEAD=ed399eebb2d6a614ffa97f6567ee9163d53b5262
REFERENCE_CORE=firmware/esphome_rc/components/greenhouse_n3w_core
REFERENCE_GATE_C_IMPLEMENTATION=COMPLETE
REFERENCE_GATE_C_SOURCE_REVIEW=PASS
REFERENCE_GATE_C_AUTOMATED_TESTS=PASS
REFERENCE_GATE_C_EXACT_COMPILE=PASS
REFERENCE_GATE_D_SOURCE_TEST_CLOSURE=PASS
REFERENCE_GATE_D_STATIC_REVIEW=PASS

PRODUCTION_TARGET=firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml
PRODUCTION_CORE=firmware/esphome_rc/components/greenhouse_n3w_product_core
PRODUCTION_TARGET_PRESENT_IN_PR516_BRANCH=false
PRODUCTION_CORE_CONVERGENCE_REQUIRED=true
PRODUCTION_SUCCESSOR_BASE_HEAD=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
PRODUCTION_SUCCESSOR_PR=474

LAB_REFERENCE_SOURCE_REPAIR_COMPLETE=true
PRODUCTION_SOURCE_REPAIR_COMPLETE=false
SOURCE_REPAIR_COMPLETE=false
PHYSICAL_ACCEPTANCE_COMPLETE=false
B3_CLOSED=false
MERGE=false
PR516_DRAFT=true

DIAGNOSTIC_WORKFLOW_REMOVED=true
DIAGNOSTIC_WORKFLOW_REMOVAL_COMMIT=b4f8183dbc9112c2b3c636d9f1160c4794d20744
BOARD_ACCESS=false
LIVE_T1_MUTATION=false
```

## 1. Gate C reference 实现完成内容

Gate C 已在 `greenhouse_n3w_core` reference/lab 路径中把 Gate B 的独立 discovery 能力接入现有 Direct recovery 状态机，没有创建第二套 Direct/Relay 状态机。

恢复顺序：

```text
原 durable broker_host 失败
-> 有界 discovery
-> 候选筛选
-> 运行时 MQTT 地址切换
-> 保留原 CA 与原 TLS 校验名称
-> 保留原 MQTT 账号、client_id 与其他身份
-> MQTT connected
-> 既有 Direct confirm
-> commit Direct
```

失败顺序：

```text
丢弃临时候选
-> 恢复本 boot 已验证的稳定运行时地址 / durable broker_host
-> 保留全部身份与配对状态
-> 返回既有 Relay / recovery backoff 路径
```

发现得到的新地址只存在 RAM；没有新增 Broker/NVS 持久写入，没有清配对，也没有重新走 ordinary pairing。

## 2. reference 路径已经固定的安全边界

- provisioned state、Wi-Fi IPv4、Direct recovery 调度和父 deadline 均满足时才允许进入地址恢复；
- discovery 非阻塞、有界收集；
- 最多解析 8 个 response、保留 3 个候选、最多尝试 2 个 Broker 地址；
- system_id、同子网、单播地址、source IP == advertised host、自身地址拒绝、TTL 上限均执行；
- Broker 端口继续来自 durable trusted broker record；
- 不修改 CA、TLS server name、MQTT username/password/client_id、NODE_ID、SYSTEM_ID、peer trust、credential generation 或 application keys；
- MQTT 旧事件通过运行时代际屏障隔离；
- 运行时恢复不调用阻塞 `esp_mqtt_client_stop()`，不引入 `portMAX_DELAY`；
- healthy Relay 30 秒绝对边界和无 Relay 120 秒绝对边界保持不变；
- MQTT 25 秒、Direct confirm 5 秒预算不被 discovery/cleanup 另开窗口；
- candidate 只有在既有 Direct commit 成功后才提升为本 boot 的稳定运行时地址；
- candidate 失败时恢复稳定运行时地址，不写 NVS。

## 3. MQTT generated-source overlay reference 修复

reference 路径 exact compile 暴露并关闭了两个 MQTT-enabled harness 幂等问题：

1. TLS generated-source patch 第二次执行时，无法识别已经同时叠加 MQTT barrier 的组合后镜像；
2. MQTT barrier patch 的“already applied”判断错误地要求旧前镜像消失，但旧前镜像本来就是新后镜像的前缀。

最终 reference 修复保持 fail-closed：

- TLS patch 只有在严格反向撤销 barrier 层和 TLS 层后能够恢复到固定 ESPHome 2026.4.3 上游 blob 时，才接受 `ALREADY_COMPOSED`；
- barrier patch 以完整后镜像恰好存在一次作为重复执行判据；
- 回归合同位于 `tests/n3w_phase4/test_broker_relocation_source_contract.py`。

临时诊断 workflow 已在验证完成后删除。

## 4. reference CI / exact compile 证据

```text
REFERENCE_VALIDATED_HEAD=ed399eebb2d6a614ffa97f6567ee9163d53b5262
GREENHOUSE_MANAGER_CI_RUN=37117976918
GREENHOUSE_MANAGER_CI=PASS
GATE_C_HARNESS_DIAGNOSTIC_RUN=37117976903
GATE_C_HARNESS_DIAGNOSTIC_CI=PASS
```

关键步骤全部 PASS：

- Gate A execution package contracts；
- Gate B discovery contracts / host test；
- Gate C recovery contracts / relocation budget host test；
- C++ cross-language vectors；
- Phase 4 simplified product runtime；
- generic ESP32-C6 Child compile；
- generic ESP32-C6 Relay compile；
- generic ESP32-C6 Phase 4 physical harness compile；
- auto safe fallback Gate A fixture compile。

这些证据证明 reference/lab 路径的设计和实现闭合，但不能替代正式 F1.0-RC2 production target 的编译与验收。

## 5. 生产路径纠偏证据

F1 准备阶段 fresh rebind 确认：

1. PR #516 分支中不存在正式生产目标 `firmware/esphome_rc/f1_0_rc2/f1_0_rc2_n3w_target.yml`；
2. 正式 production successor 仍在独立生产分支；
3. 当前最新 source-reviewed production successor 是 PR #474 head `d3c158b4376ca0577e4a3a45a18a6c5c6e994e75`；
4. 该正式 target 明确加载 `greenhouse_n3w_product_core`；
5. 该 product core 当前没有 `n3w_broker_relocation_policy.cpp`；
6. product-core `__init__.py` 只挂现有 TLS patch，没有 Gate C 的 MQTT event-generation barrier patch；
7. product-core `n3w_simple_product_component.h` 没有 Gate C broker-relocation/discovery-session 状态。

因此不能从 PR #516 直接构建“正式 production auto-fallback artifact”，也不能直接进入 Gate F。

## 6. 正确的下一阶段

下一阶段不是物理 Gate F，而是：

```text
NEXT_GATE=N3W_AUTO_SAFE_FALLBACK_PRODUCTION_CORE_CONVERGENCE_SOURCE_REPAIR_20261003_01
BASE_PR=474
BASE_HEAD=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
BASE_BRANCH=fix/n3w-production-relay-discovery-full-channel-fallback-v1-source-repair-20260924
```

目标：把已经在 reference 路径验证过的 Gate B/C 地址恢复能力**定向移植**到 `greenhouse_n3w_product_core`，同时保留 PR #474 已通过独立复核的 full-channel Relay discovery、multi-relay selection、radio ownership 和恢复顺序。

不得简单用 reference core 全目录覆盖 production core。必须逐文件/逐职责移植，并重新跑 production-specific contracts、F1.0-RC2 config/full compile、binary de-harness proof 和 exact artifact binding。

只有 production convergence 闭合后，才允许再次设置：

```text
SOURCE_REPAIR_COMPLETE=true
```

并进入 Gate F physical preparation/execution。

## 7. 当前 STOP 边界

```text
LAB_REFERENCE_SOURCE_REPAIR_COMPLETE=true
PRODUCTION_SOURCE_REPAIR_COMPLETE=false
SOURCE_REPAIR_COMPLETE=false
PHYSICAL_ACCEPTANCE_COMPLETE=false
B3_CLOSED=false
BOARD_ACCESS=false
LIVE_T1_MUTATION=false
MERGE=false
```

PR #516 保持 Draft，作为 reference/lab 实现与验证证据，不直接作为正式 production write candidate。
