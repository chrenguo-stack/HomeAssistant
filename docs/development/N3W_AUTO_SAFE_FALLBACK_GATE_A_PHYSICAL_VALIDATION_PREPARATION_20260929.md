# N3-W auto 安全回退 Gate A 实板验证准备

日期：2026-09-29  
状态：准备中，尚未写板  
PR：#516  
目标分支：`fix/n3w-auto-safe-fallback-v1-20260929`

```text
TASK=N3W_AUTO_SAFE_FALLBACK_V1_GATE_A_PHYSICAL_VALIDATION_PREPARATION_20260929
BOARD_TARGET=BOARD_B
BOARD_ACCESS=true
BOARD_READONLY_PREFLIGHT=PASS
BOARD_FLASH=false
T1_READONLY_PREFLIGHT=PASS
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

## 1.1 2026-09-29 只读预检结果

本轮已经完成 T1 + Board B 只读预检。公共仓库只记录脱敏结论，不记录局域网实际地址。

```text
T1_DEFAULT_ROUTE_INTERFACE_PRESENT=true
T1_IPV4_PREFIX_BOUND=true
T1_TWO_UNUSED_SAME_SUBNET_CANDIDATES=PASS
BROKER_IPV4_WILDCARD_8883=true
MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0

BOARD_B_ROM_IDENTITY_MATCH=PASS
BOARD_B_FLASH_SIZE_8MB=PASS
BOARD_B_SECURE_BOOT_DISABLED=PASS
BOARD_B_FLASH_ENCRYPTION_DISABLED=PASS
BOARD_B_PARTITION_TABLE_BINDING=PASS

BOARD_FLASH=false
T1_MUTATION=false
```

KF-099 的实板闭环同时证明 Board B 当前走的是未完成 provision 的 pairing WAIT 路径，而不是已加载 durable Broker profile 的正常 Direct MQTT 路径。因此 Gate A 不能再把“Board B 已有可用产品 MQTT NVS”作为前提；否则测试固件可能永远停在等待 `runtime_ready()`，这不是 MQTT retarget 能力本身的结果。

为隔离这个无关变量，Gate A fixture 已调整为：

```text
phase4_product_runtime=false
production_pairing_state_not_required=true
mqtt_profile_source=ephemeral_lab_only
durable_broker_nvs_write=false
production_broker_credentials_used=false
production_dynsec_mutation=false
```

实板 timing gate 后续改用独立的临时 TLS MQTT lab profile。临时 profile 只存在于测试固件应用镜像和私有本地/T1 临时目录；测试结束后连同测试固件一起清除，不写入 product NVS，也不修改生产 Broker / Manager / DynSec。

## 2. 为什么使用临时 T1 地址别名

Gate A 不需要真的改 DHCP。

更安全的办法是在 T1 当前网卡上临时增加一个同网段 IPv4 地址别名：

```text
当前 T1 IPv4 = restore host
临时第二地址 = live alias
同网段确认未占用地址 = blackhole address
```

生产 Broker 的 IPv4 wildcard 8883 预检已通过，但 Gate A 不再复用生产账号。后续使用独立的临时 TLS MQTT lab broker/profile，并让同一个临时 Broker 同时可通过 restore host 与 live alias 访问。这样仍然能验证“TCP 目标改变、TLS 身份不变”的核心行为，同时不要求 Board B 已经完成产品 provisioning。

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
-> 构建 private exact Gate A firmware + isolated TLS lab bundle
-> private artifact binding
-> Board B write
-> 启动临时 isolated TLS lab broker
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
