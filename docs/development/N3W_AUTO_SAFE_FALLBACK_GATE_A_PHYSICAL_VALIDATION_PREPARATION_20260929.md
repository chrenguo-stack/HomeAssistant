# N3-W auto 安全回退 Gate A 实板验证准备

日期：2026-09-29  
状态：准备中，尚未写板  
PR：#516  
目标分支：`fix/n3w-auto-safe-fallback-v1-20260929`

```text
TASK=N3W_AUTO_SAFE_FALLBACK_V1_GATE_A_PHYSICAL_VALIDATION_PREPARATION_20260929
BOARD_TARGET=BOARD_B
BOARD_ACCESS=false
BOARD_FLASH=false
T1_MUTATION=false
BROKER_MUTATION=false
PAIRING_MUTATION=false
NVS_MUTATION=false
MERGE=false
```

## 1. 目的

本轮不测试完整 auto discovery，只验证 MQTT 客户端最关键的三个运行期行为：

1. 已连接时从当前 Broker 地址切到同一台 T1 的第二个可达地址；
2. 旧地址正处于连接超时时，能否在预算内改回可达地址；
3. 旧地址已经进入重连等待时，能否在预算内改回可达地址。

这三项通过以后，才允许把自动发现接进 Direct/Relay 恢复状态机。

## 2. 为什么使用临时 T1 地址别名

Gate A 不需要真的改 DHCP。

更安全的办法是在 T1 当前网卡上临时增加一个同网段 IPv4 地址别名：

```text
当前 T1 IPv4 = restore host
临时第二地址 = live alias
同网段确认未占用地址 = blackhole address
```

Broker 当前应继续使用单一 IPv4 wildcard 监听 8883。这样同一份证书、同一账号、同一 Broker 进程同时可通过两个地址访问。

测试结束后删除临时地址别名即可，不修改：

- Broker 配置；
- Manager 配置；
- 证书；
- MQTT 账号；
- Board durable broker record；
- pairing state。

## 3. Board 选择与回滚权威

优先使用 Board B，因为当前 GitHub authority 已记录 Board B 的最近一次 exact firmware 和物理验收。

```text
CURRENT_BOARD_B_AUTHORITY=KF099
KF099_ARTIFACT_RUN_ID=36399176674
KF099_ARTIFACT_ID=10959875986
KF099_ARTIFACT_NAME=n3w-kf099-c578bcb-boardb-exact-source
KF099_ARTIFACT_ZIP_SHA256=56abb5267ee1786f77930837d6a660745ee64f320d1c6ad64aac7c852aa115cb
KF099_APPLICATION_SHA256=d0875ca692f7bd4349fd7d8bcdab69318e6c8b737b69a48f667b6e72cb89cb60
KF099_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
BOARD_B_ROM_IDENTITY_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee
```

Gate A 测试固件只允许覆盖：

- otadata；
- application。

禁止覆盖：

- bootloader；
- partition table；
- product NVS；
- full chip。

测试结束后必须用上述 KF099 exact artifact 恢复 Board B，并重新做 Direct baseline。

## 4. 新增 Gate A fixture

测试目标：

`firmware/esphome_rc/board_lab/n3w_auto_safe_fallback_gate_a/generic.yml`

它不会写新的永久 Broker 地址。

运行顺序：

```text
baseline connected
-> live alias retarget
-> disconnect
-> reconnect live alias
-> blackhole retarget
-> 在连接尝试中改回 restore host
-> reconnect
-> 再次 blackhole retarget
-> 在重连等待窗口改回 restore host
-> reconnect
-> PASS
```

关键日志：

```text
GATE_A_BASELINE_CONNECTED
GATE_A_LIVE_RETARGET_REQUEST
GATE_A_LIVE_RECONNECTED
GATE_A_BLACKHOLE_ACTIVE_RETARGET
GATE_A_BLACKHOLE_ACTIVE_RECOVERED
GATE_A_BLACKHOLE_WAIT_RETARGET
GATE_A_BLACKHOLE_WAIT_RECOVERED
GATE_A_PHYSICAL_SEQUENCE_PASS
```

任何 `GATE_A_FAIL` 都停止。

## 5. 时间门槛

当前 Direct recovery MQTT 阶段预算为 25 秒。

因此两条黑洞恢复路径都要求：

```text
BLACKHOLE_START -> RESTORED_MQTT_CONNECTED <= 25000 ms
```

同时记录 `n3w_runtime_retarget_server()` 自身调用耗时。

如果调用因为 MQTT 内部锁阻塞太久，导致整条路径超过 25 秒：

```text
GATE_A=FAIL
FULL_AUTO_FALLBACK_IMPLEMENTATION_ALLOWED=false
```

不得通过增加 healthy Relay 的 30 秒总上限来绕过。

## 6. 进入实板前的只读预检

必须先得到：

- T1 当前主 IPv4；
- 对应网卡名和前缀长度；
- 8883 wildcard listener 仍成立；
- 一个确认未占用的同网段 live alias；
- 一个确认未占用且不添加到 T1 的 blackhole IP；
- Board B 当前 ROM identity、8MB Flash、安全状态和 partition table 仍匹配；
- KF099 回滚 artifact 仍可取得并通过 SHA 校验。

这些预检全部完成以前：

```text
BOARD_FLASH=false
T1_ADDRESS_ALIAS_ADD=false
```

## 7. 后续执行顺序

```text
fixture CI PASS
-> T1/Board B read-only preflight
-> 冻结 live alias / blackhole / restore host
-> 构建 exact Gate A firmware
-> artifact binding
-> Board B write
-> live alias temporary add
-> Gate A physical sequence
-> live alias remove
-> KF099 exact rollback
-> Direct baseline
-> Gate A adjudication
```

若 Gate A PASS，下一步才进入：

`N3W_AUTO_SAFE_FALLBACK_V1_DISCOVERY_AND_RECOVERY_SOURCE_REPAIR`

若 Gate A FAIL，停止完整 auto fallback 接线，先修 MQTT 连接所有权和有界退出问题。
