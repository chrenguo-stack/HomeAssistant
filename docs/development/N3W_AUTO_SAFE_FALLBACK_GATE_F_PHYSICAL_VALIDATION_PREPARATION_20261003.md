# N3-W auto 安全回退 Gate F 物理验收准备

日期：2026-10-03  
分支：`fix/n3w-auto-safe-fallback-v1-20260929`  
PR：#516（Draft）

```text
TASK=N3W_AUTO_SAFE_FALLBACK_GATE_F_PHYSICAL_VALIDATION_PREPARATION_20261003_01
GATE_A=CLOSED_PASS
GATE_B=CLOSED_PASS
GATE_C_TO_E_SOURCE_SIDE=CLOSED_PASS
SOURCE_REPAIR_COMPLETE=true
PHYSICAL_ACCEPTANCE_COMPLETE=false
B3_CLOSED=false
MERGE=false

VALIDATED_SOURCE_TEST_HEAD=ed399eebb2d6a614ffa97f6567ee9163d53b5262
SOURCE_TO_CLOSURE_HEAD=d8219fd9d3a37456cc08d1131b386e14029bd4ed
PRODUCT_SOURCE_DRIFT_AFTER_VALIDATION=false
BOARD_ACCESS=false
LIVE_T1_MUTATION=false
WRITE_AUTHORIZATION=false
```

## 1. 目的

Gate F 只验证真实 ESP32-C6 + 可控 T1/Broker 下的最小物理闭环，不再扩展源码设计。

Gate F 必须证明：

1. 旧 Broker/T1 地址正常 Direct；
2. T1 IPv4 改变，但 T1 身份、CA、TLS server name、MQTT 账号/client_id 不变；
3. 旧地址连接失败；
4. 节点在同一 boot 中通过独立 discovery 找到新地址；
5. 新地址使用原 CA、原 TLS 名称、原账号完成 MQTT；
6. Manager-visible telemetry 恢复；
7. healthy Relay 场景整轮 Direct probe 不超过 30 秒；
8. 候选不可达时能按父 deadline 退出并回到 Relay/既有退避；
9. 断电后 RAM-only 地址丢失，下一 boot 能再次 discovery；
10. durable pairing、Broker record、credential generation 前后不变。

## 2. 不允许通过的手段

整个 Gate F 禁止：

- 清配对；
- 恢复出厂；
- 修改 NODE_ID / SYSTEM_ID / peer trust；
- 刷新 MQTT 用户名、密码或 client_id；
- 修改 CA 或 TLS server name；
- 把 discovery response 当认证；
- 为通过测试写入新的 durable Broker 地址；
- 通过重启节点掩盖同 boot recovery 失败；
- 用反复重启 T1 或 Manager 掩盖退出/回滚错误；
- 把“有 Relay 链路”误报成 Manager 已接纳数据；
- 复用 Gate A 已消费的现场授权。

## 3. Gate F 分步执行

### F0：fresh rebind 与 exact-source 冻结（只读）

执行：

- fresh rebind PR #516、修复分支、current main；
- 再次确认 `ed399eeb...` 之后无产品源码/测试漂移；
- 读取 Gate C–E closure、开发测试计划、执行计划；
- 固定 ESPHome 2026.4.3 / ESP-IDF 5.5.4 / ESP32-C6；
- 固定本轮 physical source head。

停止条件：出现产品源码漂移则先回源码复核，不进入板端。

### F1：exact artifact 构建与绑定（非现场）

分别构建并记录：

- 正式生产目标；
- physical harness / 必要诊断目标。

记录：

- exact source SHA/tree；
- 构建配置摘要；
- firmware/application SHA-256；
- artifact ID；
- production / harness 明确区分。

停止条件：任一 exact compile / artifact binding 失败，不刷板。

### F2：Board / T1 只读预检

在任何写入、换网、重启前只读确认：

- 选中的 Board 是当前身份和业务正常的已配对节点；
- 硬件/flash/分区/当前应用身份与预期一致；
- secure boot / flash encryption 状态已知；
- NVS 必须保留；
- T1 Broker / Manager 当前稳定；
- T1 当前 LAN 地址、目标换址方式和恢复管理通道可控；
- Manager restart count / container identity 建立基线；
- 当前 node_id / system_id / credential generation / durable Broker record 建立脱敏前态。

停止条件：身份不完整、NVS 保护不明确、T1 无可靠回滚通道、当前业务不健康时，不写板。

### F3：独立写板授权

只有用户明确授权后才允许：

- 写入已绑定 exact artifact；
- 仅修改批准的应用分区/OTA 入口；
- 不擦 NVS；
- 不生成新身份；
- 写后重新核对 application SHA-256 / 分区 / boot 状态。

当前：

```text
WRITE_AUTHORIZATION=false
BOARD_MUTATION=false
```

### F4：90 秒 Direct baseline

同一 boot 记录：

- boot/session；
- source=direct；
- seq 前进；
- Manager accepted telemetry；
- node/system identity；
- T1 Manager restart count；
- durable pairing/Broker/credential generation 前态。

必须通过 90 秒基线后才换地址。

### F5：T1 IPv4 受控变化

前提：有可靠恢复管理通道。

操作：

- 只改变 T1 LAN IPv4 / DHCP 结果；
- T1 身份、证书、TLS server name、MQTT 凭据不变；
- 板保持同一 boot；
- 不插 USB、不重启板、不人工改板端 Broker 地址；
- 如需移动板，必须先进入明确 MOVE arming 点。

### F6：同 boot 自动恢复验证

必须同时看到：

```text
OLD_TARGET_FAIL=true
DISCOVERY_NEW_TARGET=true
ORIGINAL_TLS_IDENTITY_USED=true
ORIGINAL_MQTT_ACCOUNT_USED=true
MQTT_NEW_TARGET_CONNECTED=true
DIRECT_CONFIRM=true
MANAGER_VISIBLE_TELEMETRY_RECOVERED=true
SAME_BOOT=true
IDENTITY_UNCHANGED=true
```

Manager 第一条新数据出现后，至少再观察两次 seq / updated_at 前进。

### F7：600 秒稳态观察

记录：

- seq 连续前进；
- 最大业务间隔；
- duplicate / missing；
- Manager restart count；
- 板复位 / watchdog；
- MQTT client/task/socket 是否异常增长；
- 堆趋势；
- 采样/LCD/本地功能是否保持原周期。

Option B 仍允许既有语义下的数据损失，不把本验收改写成“每 5 秒一条绝不能丢”。

### F8：失败路径验证

至少注入：

- discovery 无候选；
- 候选不可达 / TCP 黑洞；
- 候选失败后回滚。

必须证明：

- 不写 NVS；
- 不清身份；
- 不出现双 MQTT client；
- 不出现旧回调污染新 attempt；
- healthy Relay 的 Direct probe 整轮不超过 30 秒；
- 无 Relay 的 recovery 不突破 120 秒父边界；
- 回到 Relay 或既有 backoff，而不是整板重启。

### F9：断电 / RAM-only 地址验证

仅在同 boot 地址恢复已通过后单独执行，不能与前一轮混算。

验证：

- 断电前后 durable Broker record 不变；
- 重启后 RAM override 消失；
- durable identity / credential generation 不变；
- 在旧 durable 地址仍失效时，下一 boot 仍可重新 discovery 新 T1 地址并恢复。

### F10：现场清理与 closure

恢复受控网络环境，确认：

- T1 管理访问正常；
- Broker / Manager 稳定；
- 板端身份和 NVS 无意外变化；
- 无测试凭据/临时地址写入生产持久状态；
- 证据脱敏归档到 GitHub；
- exact source / artifact / Board / test result 一一绑定。

全部通过后才允许：

```text
PHYSICAL_ACCEPTANCE_COMPLETE=true
B3_CLOSED=true
```

是否合并 PR #516 仍需在 Gate F closure 后单独决定。

## 4. 首轮物理样本选择原则

不预设必须使用 Board A 或 Board B。首轮选择必须以 F2 fresh read-only 结果为准：

- 当前身份正常；
- 当前业务 Direct 正常；
- NVS / 配对状态完整；
- 可安全刷入 exact artifact；
- 可提供可靠回滚。

若某板仍有其他未闭合身份/配置问题，排除出首轮，不把该问题误判成 auto fallback 失败。

## 5. 当前 STOP

当前已完成的是 Gate F 准备文件，不构成现场授权。

```text
GATE_F_PREPARATION=COMPLETE
BOARD_ACCESS=false
LIVE_T1_MUTATION=false
WRITE_AUTHORIZATION=false
T1_ADDRESS_CHANGE_AUTHORIZATION=false
MERGE=false
```

下一安全动作：只读 F0/F1 可以继续；F2 若涉及读取真实 Board/T1 状态，需要明确进入现场预检；F3 及之后必须获得对应 live mutation 授权。
