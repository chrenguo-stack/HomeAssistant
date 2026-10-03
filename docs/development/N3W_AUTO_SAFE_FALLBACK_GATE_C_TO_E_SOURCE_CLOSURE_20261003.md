# N3-W auto 安全回退 Gate C–E 源码侧收口

日期：2026-10-03  
分支：`fix/n3w-auto-safe-fallback-v1-20260929`  
PR：#516（Draft）

```text
TASK=N3W_AUTO_SAFE_FALLBACK_GATE_C_TO_E_SOURCE_CLOSURE_20261003_01
GATE_A=CLOSED_PASS
GATE_B=CLOSED_PASS

GATE_C_VALIDATED_HEAD=ed399eebb2d6a614ffa97f6567ee9163d53b5262
GATE_C_SOURCE_IMPLEMENTATION=COMPLETE
GATE_C_SOURCE_REVIEW=PASS
GATE_C_AUTOMATED_TESTS=PASS
GATE_C_EXACT_COMPILE=PASS

GATE_D_SOURCE_TEST_CLOSURE=PASS
GATE_D_STATIC_REVIEW=PASS
GATE_D_ACTUAL_BACKEND_AND_PHYSICAL_ITEMS=PENDING_GATE_F

GATE_E_SOURCE_REVIEW=PASS
PR516_DRAFT=true
SOURCE_REPAIR_COMPLETE=true
PHYSICAL_ACCEPTANCE_COMPLETE=false
B3_CLOSED=false
MERGE=false

BOARD_ACCESS=false
LIVE_T1_MUTATION=false
```

## 1. 本轮完成内容

Gate C 已把 Gate B 的独立发现能力接入现有 Direct recovery 状态机，没有创建第二套 Direct/Relay 状态机。

恢复顺序保持为：

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

失败顺序保持为：

```text
丢弃临时候选
-> 恢复本 boot 已验证的稳定运行时地址 / durable broker_host
-> 保留全部身份与配对状态
-> 返回既有 Relay / recovery backoff 路径
```

第一版发现得到的新地址仍然只存在 RAM；没有新增 Broker/NVS 持久写入，也没有清配对或重新走 ordinary pairing。

## 2. Gate C 关键安全边界

源码和测试已经固定以下约束：

- provisioned state、Wi-Fi IPv4、Direct recovery 调度和父 deadline 均满足时才允许进入地址恢复；
- discovery 非阻塞，有界收集；
- 最多解析 8 个 response、保留 3 个候选、最多尝试 2 个 Broker 地址；
- system_id、同子网、单播地址、source IP == advertised host、自身地址拒绝、TTL 上限均执行；
- Broker 端口继续来自 durable trusted broker record；
- 不修改 CA、TLS server name、MQTT username/password/client_id、NODE_ID、SYSTEM_ID、peer trust、credential generation 或 application keys；
- MQTT 旧事件通过运行时代际屏障隔离，旧连接迟到事件不能提交新候选结果；
- 运行时恢复不调用阻塞 `esp_mqtt_client_stop()`，不引入 `portMAX_DELAY`；
- healthy Relay 的 30 秒绝对边界和无 Relay 的 120 秒绝对边界保持不变；
- MQTT 25 秒、Direct confirm 5 秒预算不被 discovery/cleanup 另开窗口；
- candidate 只有在既有 Direct commit 成功后才提升为本 boot 的稳定运行时地址；
- candidate 失败时恢复稳定运行时地址，不写 NVS。

## 3. MQTT generated-source overlay 修复

本轮 exact compile 暴露了两个只在 MQTT-enabled physical harness 中出现的幂等问题：

1. TLS generated-source patch 第二次执行时，无法识别已经同时叠加 MQTT barrier 的组合后镜像；
2. MQTT barrier patch 的“already applied”判断错误地要求旧前镜像消失，但旧前镜像本来就是新后镜像的前缀。

最终修复保持 fail-closed：

- TLS patch 只有在严格反向撤销 barrier 层和 TLS 层后能够恢复到固定 ESPHome 2026.4.3 上游 blob 时，才接受 `ALREADY_COMPOSED`；
- barrier patch 以完整后镜像恰好存在一次作为重复执行判据；
- 对应回归合同已经加入 `tests/n3w_phase4/test_broker_relocation_source_contract.py`。

临时诊断 workflow 已在验证完成后删除，不保留为长期产品 CI。

## 4. CI / exact compile 证据

验证绑定到：

```text
GATE_C_VALIDATED_HEAD=ed399eebb2d6a614ffa97f6567ee9163d53b5262
GREENHOUSE_MANAGER_CI_RUN=37117976918
GREENHOUSE_MANAGER_CI=PASS
GATE_C_HARNESS_DIAGNOSTIC_RUN=37117976903
GATE_C_HARNESS_DIAGNOSTIC_CI=PASS
```

`greenhouse-manager CI` 的关键步骤全部 PASS：

- Phase 3 source safety contracts；
- Phase 4 source-only activation contracts；
- Phase 4 watchdog breadcrumb contracts；
- Phase 4 relay unicast channel observability contracts；
- Phase 4 single-radio ownership contracts；
- Phase 4 recovery exit and Direct liveness contracts；
- Gate A execution package contracts；
- Gate B discovery contracts；
- Gate B discovery policy host test；
- Gate C recovery contracts；
- Gate C relocation budget host test；
- C++ cross-language vectors；
- Phase 4 simplified product runtime；
- generic ESP32-C6 Child compile；
- generic ESP32-C6 Relay compile；
- generic ESP32-C6 Phase 4 physical harness compile；
- auto safe fallback Gate A fixture compile。

在该 validation head 上，其余 PR 工作流也均成功。

## 5. Gate D / Gate E 结论

Gate D 的源码侧四层测试与静态审查已经闭合：纯函数/协议、MQTT 地址切换适配合同、Direct/Relay 状态机与截止时间、ESP32-C6 exact compile 均有自动化证据。

重点阻断项在源码侧均已关闭或受合同保护：

- 旧回调污染新 attempt；
- 自动重连返回旧目标的代际污染；
- TLS 名称被新 IP 覆盖；
- candidate 失败写 NVS；
- healthy Relay 30 秒被延长；
- discovery/cleanup 另开预算；
- ordinary pairing / KF-099 回归；
- Option-B telemetry ownership 回归。

Gate E 的独立源码复核与仓库 CI 条件满足，但 PR #516 必须继续保持 Draft，直到 Gate F 物理验收完成。

## 6. 不能提前宣称的项目

Astra 48 项矩阵中要求实际 MQTT 后端、隔离服务端或真实 ESP32-C6 的项目仍未由本轮源码 CI 证明，例如：

- 同一 Broker 换 IP 后用原 CA / TLS 名称 / 账号真实连接；
- 错误 CA、错误证书名称、证书有效期/时间问题的服务端行为；
- 旧 IP TCP/TLS 黑洞与迟到回调的实际底层行为；
- healthy Relay 30 秒、无 Relay 120 秒在真实单射频环境中的时间边界；
- Manager-visible telemetry 恢复；
- 断电后 RAM 地址消失并重新 discovery；
- 多板、Relay Child、双 T1、重复换址和长稳资源行为。

因此：

```text
SOURCE_REPAIR_COMPLETE=true
PHYSICAL_ACCEPTANCE_COMPLETE=false
B3_CLOSED=false
MERGE=false
```

## 7. 下一安全入口

下一阶段为 Gate F 物理最小验证。进入 Gate F 前必须重新 fresh rebind，并单独确认：

- exact source / exact artifact；
- 可用且身份正常的已配对 ESP32-C6；
- T1/Broker 可控换址与可靠回滚通道；
- NVS 保留与刷写边界；
- Board/T1 live mutation 明确授权。

Gate F 不得复用 Gate A 已消费的现场授权，也不得用重启、清配置或重新配对掩盖换址失败。

STOP：本文件只关闭 Gate C–E 的源码侧开发与复核；没有进入 Gate F，没有访问开发板，没有修改 T1，没有合并 PR #516。
