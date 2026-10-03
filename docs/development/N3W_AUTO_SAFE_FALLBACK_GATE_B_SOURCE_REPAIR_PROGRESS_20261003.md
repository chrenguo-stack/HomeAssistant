# N3-W auto 安全回退 Gate B 源码修复进度

日期：2026-10-03

```text
TASK=N3W_AUTO_SAFE_FALLBACK_GATE_B_DISCOVERY_PAIRING_DECOUPLING_SOURCE_REPAIR_20261002_01
BRANCH=fix/n3w-auto-safe-fallback-v1-20260929
PR=516
SOURCE_HEAD_BEFORE_PROGRESS_DOC=0e7053286794979878fe07687f60151d10937ddc
MAIN_REBIND=d423211b6196c2f2f0f01dff072c4f877fbe58ee
MERGE_BASE=a363962a118e823f97022a6c398383e9e43fc830
PRODUCT_SOURCE_DRIFT_ON_MAIN_SINCE_MERGE_BASE=false
GATE_A=CLOSED_PASS
GATE_A_REENTRY=false
LIVE_MUTATION=false
BOARD_ACCESS=false
MERGE=false
AUTO_EXECUTE_GATE_C=false
GATE_B_SOURCE_IMPLEMENTATION=COMPLETE
GATE_B_CI=WAITING_FINAL_CONFIRMATION
GATE_B_CLOSED=false
GATE_C_ENTERED=false
```

## 1. fresh rebind 结论

本轮开始时重新核对 current main、Draft PR #516、修复分支以及 `greenhouse_n3w_core` 相关源码。

从 PR merge-base `a363962a118e823f97022a6c398383e9e43fc830` 到 current main `d423211b6196c2f2f0f01dff072c4f877fbe58ee` 的 39 个提交没有修改 `firmware/esphome_rc/components/greenhouse_n3w_core/` 产品源码，因此 Gate B 不需要重做设计，可以继续既有修复路线。

Gate A 保持 `CLOSED_PASS`，本轮没有重进 Gate A，没有重复物理测试，没有复用任何 consumed authorization。

## 2. Gate B 已完成的源码工作

新增公共 discovery 协议与过滤模块：

- `n3w_manager_discovery.h`
- `n3w_manager_discovery.cpp`
- `n3w_manager_discovery_policy.cpp`

新增 ESP32 多响应 UDP discovery 适配器：

- `n3w_esp32_manager_discovery.h`
- `n3w_esp32_manager_discovery.cpp`

普通首次配对继续保留原有 `SimplePairingClient::run_once()` 流程，但 discovery query 构造和 response 解析已经改为复用公共模块。已配对节点仍在 `run_once()` 入口直接返回 `ALREADY_PROVISIONED`，Gate B 没有建立任何让已配对节点重新进入 ordinary pairing / hello / begin 的路径。

## 3. Gate B 已冻结的安全边界

当前源码实现固定：

1. 每轮 discovery 重新生成 request_id 随机材料与 nonce；
2. UDP 适配器在单轮收集窗口内收集多个 response，而不是只取第一个；
3. 最多解析 8 个报文；
4. 最多保留 3 个去重候选地址；
5. 后续 recovery target 最多生成 2 个候选地址；
6. 候选必须满足 expected system_id；
7. advertised host 必须是合法 IPv4 单播；
8. advertised host 必须与节点本地 IPv4 位于同一子网；
9. UDP source IPv4 必须等于 advertised host；
10. 网络地址和广播地址拒绝；
11. Broker recovery target 的端口只接受调用方传入的 durable trusted broker port，不采用 discovery candidate 中的 Manager/pairing port；
12. discovery 模块没有 CA、TLS server name、MQTT username/password/client_id、NODE_ID/SYSTEM_ID、peer trust、application key、credential generation 或 NVS 写入口；
13. discovered address 只存在于返回候选对象和后续 RAM recovery target 中；
14. Gate B 没有接入 Direct recovery 状态机。

## 4. 新增测试

新增：

- `tests/n3w_phase4/n3w_manager_discovery_policy_host_test.cpp`
- `tests/n3w_phase4/test_manager_discovery_policy_behavior.py`
- `tests/n3w_phase4/test_manager_discovery_source_contract.py`

覆盖范围包括：

- 8 / 3 / 2 上限；
- system_id 错误拒绝；
- 跨子网拒绝；
- source IP 与 advertised host 不一致拒绝；
- multicast、network address、broadcast address 拒绝；
- 候选地址去重；
- durable Broker port 继续生效；
- discovery 与 pairing 状态机解耦；
- 已配对节点不进入 `run_once()`；
- 每轮 fresh request_id / nonce 材料；
- UDP 多响应收集和 source IP 捕获；
- discovery 源码不得出现 trust、credential 或 NVS mutation。

## 5. CI 当前状态

本轮第一次 CI 暴露 `tracked-content-safety`：host test 使用了私网示例地址，被仓库公开内容扫描器拦截。该问题不属于产品逻辑失败，测试地址随后改为 RFC 文档示例网段。

按本项目长链路规则，本轮 GitHub workflow 已进行三次状态检查，之后停止继续轮询。最后一次检查时，没有观察到当前代码 head 的明确失败，但主测试、cross-language 和若干 contract/scope job 仍处于 queued / in-progress，因此本文件不得把 Gate B 标记为 `CLOSED_PASS`。

当前 PR：

https://github.com/chrenguo-stack/HomeAssistant/pull/516

## 6. 当前停止点

```text
GATE_B_SOURCE_IMPLEMENTATION=COMPLETE
GATE_B_SOURCE_REVIEW=PASS_WITH_CI_PENDING
GATE_B_CI=WAITING_FINAL_CONFIRMATION
GATE_B_CLOSED=false
GATE_C_ENTERED=false
LIVE_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

下一次继续时先 fresh rebind PR #516 最新 head 和 CI 结果。如果最终 CI 全部通过，再做 Gate B closure 记录；不要自动进入 Gate C。
