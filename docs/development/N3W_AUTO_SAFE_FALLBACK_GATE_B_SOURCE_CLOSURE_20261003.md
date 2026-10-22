# N3-W auto 安全回退 Gate B 源码收口

日期：2026-10-03

```text
TASK=N3W_AUTO_SAFE_FALLBACK_GATE_B_DISCOVERY_PAIRING_DECOUPLING_SOURCE_REPAIR_20261002_01
BRANCH=fix/n3w-auto-safe-fallback-v1-20260929
PR=516
GATE_A=CLOSED_PASS
GATE_B_SOURCE_HEAD=a448af7a3c3db22de23b649d724fe1f97c8859a0
GATE_B_SOURCE_IMPLEMENTATION=COMPLETE
GATE_B_SOURCE_REVIEW=PASS
GATE_B_CI=PASS
GATE_B_CLOSED=CLOSED_PASS
GATE_C_ENTERED=false
AUTO_EXECUTE_GATE_C=false
LIVE_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

## 1. 收口结论

Gate B 已满足执行计划规定的停止条件：discovery 与 ordinary pairing 已完成源码职责解耦，纯协议、过滤、host C++ 行为测试和 ESP32-C6 编译链均通过。

本 Gate 仅完成可复用 discovery 能力、候选过滤和后续 recovery target 生成能力，不把 discovery 接入 Direct recovery 状态机。Gate C 未进入。

## 2. Gate B 已冻结的行为

当前源码在 Gate B source head 上满足：

1. provisioned node 不通过 `SimplePairingClient::run_once()` 做地址恢复；`run_once()` 对已配对状态仍直接返回 `ALREADY_PROVISIONED`；
2. 每轮独立 discovery 重新生成 request_id 随机材料和 nonce；
3. UDP discovery 单轮收集多个 response，而不是只接受第一个 response；
4. 最多解析 8 个报文；
5. 最多保留 3 个去重候选；
6. 后续 recovery target 最多生成 2 个候选地址；
7. 候选必须匹配 expected `system_id`；
8. advertised host 必须是合法 IPv4 单播；
9. advertised host 必须与节点本地 IPv4 位于同一子网；
10. UDP source IPv4 必须等于 advertised host；
11. 网络地址和广播地址拒绝；
12. Broker recovery target 只使用 durable trusted broker record 提供的 Broker port，不使用 discovery candidate 的 Manager/pairing port；
13. discovery 模块没有 CA、TLS server name、MQTT username/password/client_id、NODE_ID/SYSTEM_ID、peer trust、application key、credential generation 或 NVS 写入口；
14. discovered address 只存在于 RAM candidate / recovery target 中；
15. Gate B 没有调用 ordinary pairing / hello / begin 作为地址恢复路径；
16. Gate B 没有修改 Direct/Relay 状态机或恢复预算。

## 3. CI 证据

Gate B source head：

`a448af7a3c3db22de23b649d724fe1f97c8859a0`

该 head 的 pull-request workflow 共 13 个，全部 `completed/success`。

`greenhouse-manager CI` run：

- run id: `37082266384`
- `scope`: PASS
- `test`: PASS
- `n3w-phase3-cross-language`: PASS

Gate B 专用步骤：

- `Auto safe fallback Gate B discovery contracts`: PASS
- `Build and run Gate B discovery policy host test`: PASS

同一 job 中以下编译/回归步骤也通过：

- Phase 3 source safety contracts
- Phase 4 source-only activation contracts
- Phase 4 watchdog breadcrumb contracts
- Phase 4 relay unicast channel observability contracts
- Phase 4 single-radio ownership contracts
- Phase 4 recovery exit and Direct liveness contracts
- C++ cross-language vectors
- Phase 4 simplified product runtime
- generic ESP32-C6 Child compile
- generic ESP32-C6 Relay compile
- generic ESP32-C6 Phase 4 physical harness compile
- auto safe fallback Gate A fixture compile

## 4. closure 前最后修正

前一个 source head `61761d049c591bac3a4064a8253196bcb0bb0860` 的 CI 虽然全绿，但 Gate B 新增的专用测试没有被 workflow 明确执行，因此当时没有关闭 Gate B。

随后只修改 `.github/workflows/greenhouse-manager-ci.yml`，把 Gate B Python discovery contracts 和 discovery policy host C++ test 显式接入 CI，形成 `a448af7a3c3db22de23b649d724fe1f97c8859a0`。

`61761d... -> a448af7...` 只有 workflow 文件变化，没有产品源码变化。重新运行后 Gate B 专用测试及完整编译链全部 PASS。

## 5. Gate C 边界

根据 `N3W_AUTO_SAFE_FALLBACK_SOURCE_REPAIR_EXECUTION_PLAN_20260929.md`，Gate C 才负责把该 discovery 能力接入 Direct 恢复状态机。

Gate C 的恢复顺序仍保持：

```text
原 broker_host 失败
-> 有界 discovery
-> 候选筛选
-> 请求 MQTT 地址切换
-> 原 CA + 原 TLS 名称验证
-> 原账号登录
-> MQTT connected
-> 既有 Direct confirm
-> commit Direct
```

任何一步失败仍必须：

```text
丢弃临时候选
-> 保留 durable broker_host 和全部身份
-> 恢复 Relay 或进入既有退避
```

Gate B closure 不构成 Gate C 自动授权。

## 6. 当前停止点

```text
GATE_B=CLOSED_PASS
GATE_C_ENTERED=false
AUTO_EXECUTE_GATE_C=false
LIVE_MUTATION=false
BOARD_ACCESS=false
MERGE=false
PR516_DRAFT=true
```

下一阶段如继续，应单独 fresh rebind 后再进入 Gate C；不得因为 Gate B closure 自动执行 Gate C、板卡操作、T1 live mutation 或 merge。
