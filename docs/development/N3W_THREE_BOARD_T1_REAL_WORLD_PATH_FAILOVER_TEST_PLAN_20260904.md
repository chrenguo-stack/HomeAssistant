# N3-W 三板 / T1 真实场景路径切换实机验证方案

- 日期：2026-09-04
- 文档性质：public-safe / test-plan / documentation-only
- 仓库：`chrenguo-stack/HomeAssistant`
- 基线 `main`：`0f48ef18d371d0d5fe073a406d74a4d860614ed2`
- 基线 tree：`146c842e7756fba8d0efa5762312282754666ba3`

## 1. 测试定位

本方案用于完成 N3-W 三板 / T1 的下一阶段真实场景实机验证。

上一阶段已经冻结：

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
N3W_THREE_BOARD_REGRESSION_RETEST=FROZEN_PASS
REOPEN_PREVIOUS_ACCEPTANCE=false
```

本轮新 North Star：

```text
NORTH_STAR=
N3W_THREE_BOARD_T1_REAL_WORLD_PATH_FAILOVER_VALIDATION

TEST_SCENARIO=
PHYSICAL_WIFI_COVERAGE_LOSS_AND_AUTOMATIC_RELAY_RECOVERY
```

本轮验证的核心不是再次证明单板可以通信，而是证明三个节点在真实空间覆盖条件变化下，可以完成：

```text
Direct
→ Wi-Fi 真实覆盖丢失
→ 自动 Relay
→ Relay 稳态
→ Wi-Fi 真实恢复
→ 自动回 Direct
→ Relay 自动退出
```

并且整个过程中保持节点身份、配对、凭据、应用密钥和 peer trust 生命周期稳定。

## 2. 节点角色与目标拓扑

本轮建议固定三块物理板的角色，避免测试中途交换职责：

| 角色 | 物理板 | Wi-Fi 条件 | 预期职责 |
|---|---|---|---|
| Node-1 | Board A | 始终处于 Wi-Fi 有效覆盖范围 | 自身 Direct，同时在需要时转发 Node-2 / Node-3 |
| Node-2 | Board B | 覆盖内 → 移出覆盖 → 移回覆盖 | Direct → Relay → Direct |
| Node-3 | Board C | 覆盖内 → 移出覆盖 → 移回覆盖 | Direct → Relay → Direct |
| T1 | 测试 T1 | 始终正常运行 | Broker + Manager + Home Assistant |
| AP | 测试 Wi-Fi AP | 配置固定、信道固定 | 提供真实 Wi-Fi 覆盖环境 |

正常基线：

```text
Node-1 ──WiFi──► T1
Node-2 ──WiFi──► T1
Node-3 ──WiFi──► T1
```

Node-2 / Node-3 离开 Wi-Fi 覆盖后的目标状态：

```text
Node-1 ──WiFi────────► T1
  ▲
  │ ESP-NOW / Relay
  ├──── Node-2
  │
  └──── Node-3
```

恢复后的目标状态：

```text
Node-1 ──WiFi──► T1
Node-2 ──WiFi──► T1
Node-3 ──WiFi──► T1

Relay path 自动退出
```

本轮验证的是单跳 Relay，不引入 mesh。

## 3. 故障注入原则：必须采用真实空间覆盖丢失

本轮明确取消 AP 侧阻断节点数据、MAC filter、association deny 等人工网络策略作为主要故障注入方式。

原因：

```text
AP_BLOCKS_DATA
!=
NODE_OUT_OF_WIFI_COVERAGE
```

AP 侧阻断可能让节点仍保持 Wi-Fi 射频关联或链路可见，这不能等价模拟真实温室中节点已经离开 Wi-Fi 覆盖范围的场景。

本轮故障注入必须采用：

```text
Node-1:
始终位于 Wi-Fi 有效覆盖范围

Node-2 / Node-3:
物理移动出 Wi-Fi 有效覆盖范围
但仍处于 Node-1 的 ESP-NOW 单跳可达范围
```

整个测试中保持：

```text
AP_CONFIG_MUTATION=false
AP_MAC_FILTER=false
AP_ASSOCIATION_DENY=false
AP_TRAFFIC_BLOCK=false
AP_CHANNEL_CHANGE=false

BOARD_FIRMWARE_MUTATION=false
PAIRING_MUTATION=false
CREDENTIAL_MUTATION=false
```

不得通过关闭 Node-2 / Node-3 Wi-Fi radio、修改 Wi-Fi 密码、修改固件、阻断 T1 地址、切换 AP 信道、关闭整个 AP 等方式替代真实覆盖丢失。

## 4. 真实 RF 条件模型

测试场地应形成至少三个可区分的区域。

### 4.1 Zone A — Wi-Fi Good

要求：

```text
Node-1 WiFi stable
Node-2 WiFi stable
Node-3 WiFi stable
```

用于 T0 正常 Direct 基线和最终恢复状态。

### 4.2 Zone B — Transition

该区域可能出现：

```text
RSSI 很低
Wi-Fi 反复 disconnect / reconnect
偶发 association
Direct / Relay 边界抖动
```

Zone B 不作为 Relay 稳态测试位置。

原因是它容易制造路径 flapping，使产品状态机问题和正常 RF 边界抖动难以区分。

### 4.3 Zone C — Wi-Fi Unavailable / Relay Reachable

Node-2 / Node-3 正式 Relay 稳态位置必须满足：

```text
NODE_WIFI_USABLE=false
NODE_DIRECT_MQTT_USABLE=false
ESP_NOW_TO_NODE1_USABLE=true
```

换言之，本轮真正要验证的是：

```text
Wi-Fi direct unavailable
AND
ESP-NOW relay reachable
```

该区域正是未来温室现场 Relay 功能要解决的实际覆盖空洞。

## 5. 不以固定米数作为 Gate

本轮不得预先规定“距离 AP 30 米 / 50 米”作为通过条件。

Wi-Fi 和 ESP-NOW 覆盖受以下因素显著影响：

- 墙体；
- 温室金属骨架；
- 作物与含水量；
- 节点与 AP 天线方向；
- 安装高度；
- 地面和结构反射；
- 同频干扰；
- 天气和现场环境。

因此正式 Gate 使用通信事实定义：

```text
ZONE_C_VALID =
WiFi direct unavailable
AND
ESP-NOW relay reachable
```

距离只作为测试环境记录，不作为产品判定门槛。

## 6. 总体测试路线

正式路线：

```text
P0  RF coverage survey
 ↓
T0  Three-board Direct baseline
 ↓
T1  Physically move Node-2 / Node-3 out of Wi-Fi coverage
 ↓
T2  Automatic Direct → Relay takeover
 ↓
T3  Two-node Relay steady-state
 ↓
T4  Move Node-2 back into Wi-Fi coverage
 ↓
     Node-1 Direct
     Node-2 Direct
     Node-3 Relay
 ↓
T5  Move Node-3 back into Wi-Fi coverage
 ↓
T6  Three-board Direct steady-state + Relay quiescence
 ↓
FINAL CLOSEOUT
```

不在当前规划文档中写死切换秒数。正式时间门槛应在执行前通过只读源码 / T1 runtime preclaim，从当前 frozen firmware 和 Manager 语义中读取真实 retry / fallback / hysteresis 参数后制定。

## 7. P0 — RF Coverage Survey

P0 不是产品 PASS/FAIL Gate，而是为正式测试找到可重复的位置。

需要固定：

```text
POSITION_NODE1_WIFI_GOOD
POSITION_NODE2_WIFI_GOOD
POSITION_NODE3_WIFI_GOOD

POSITION_NODE2_WIFI_DEAD_RELAY_OK
POSITION_NODE3_WIFI_DEAD_RELAY_OK
```

测试中 Node-1 固定不动；Node-2 / Node-3 在已确认位置之间移动，不在正式 Gate 中临时寻找 RF 边界。

P0 目标：

```text
NODE1_WIFI_STABLE=true
NODE2_ZONE_C_WIFI_UNAVAILABLE=true
NODE2_ZONE_C_RELAY_REACHABLE=true
NODE3_ZONE_C_WIFI_UNAVAILABLE=true
NODE3_ZONE_C_RELAY_REACHABLE=true
```

如果找不到同时满足 Wi-Fi 不可用、Relay 可达的 Zone C，则停止正式 T0～T6，不以修改产品配置来“制造”测试环境。

## 8. T0 — 三板全 Direct 基线

三个节点全部放在 Wi-Fi Good 区域。

目标：

```text
NODE_1_PATH=direct
NODE_2_PATH=direct
NODE_3_PATH=direct

NODE_1_TELEMETRY_FLOWING=true
NODE_2_TELEMETRY_FLOWING=true
NODE_3_TELEMETRY_FLOWING=true

NODE_1_SEQ_MONOTONIC=true
NODE_2_SEQ_MONOTONIC=true
NODE_3_SEQ_MONOTONIC=true
```

同时证明 T1 当前 runtime authority 健康：

```text
MANAGER_RUNNING=true
BROKER_RUNNING=true
HOMEASSISTANT_RUNNING=true
```

在路径变化前保存每个节点的当前只读基线：

```text
last_seq
last_source
canonical_cursor
replay_cursor
```

安全 / 生命周期不变量：

```text
PAIRING_STATE_STABLE=true
CREDENTIAL_STATE_STABLE=true
APPLICATION_KEY_STATE_STABLE=true
PEER_TRUST_STATE_STABLE=true
```

## 9. T1 — 真实移动 Node-2 / Node-3 离开 Wi-Fi 覆盖

保持：

```text
Node-1 = 固定
AP = 固定
T1 = 固定
```

仅执行物理位置变化：

```text
MOVE Node-2:
WiFi GOOD
→ WiFi UNAVAILABLE / Relay Reachable

MOVE Node-3:
WiFi GOOD
→ WiFi UNAVAILABLE / Relay Reachable
```

禁止伴随：

```text
RESET
BOOT
POWER_CYCLE
FLASH
PAIRING
CREDENTIAL_RECOVERY
CONFIG_CHANGE
AP_CHANGE
FORCE_PATH
```

### T1 首先证明“真实 Direct 路径不可用”

不能仅根据 Manager 暂时没收到 Direct telemetry 就宣布 Wi-Fi 已丢失。

应通过多个独立事实交叉确认：

```text
Wi-Fi association / usable link lost
Direct MQTT unusable
Direct telemetry ceased
Relay telemetry subsequently begins
```

目标输出：

```text
NODE_2_WIFI_DIRECT_PATH_UNAVAILABLE=true
NODE_3_WIFI_DIRECT_PATH_UNAVAILABLE=true
```

具体使用哪个 firmware / Manager / AP oracle，在执行前 readonly preclaim 冻结。

## 10. T2 — 自动 Direct → Relay Takeover

不允许人工发送任何路径控制指令。

禁止：

```text
PATH=relay
FORCE_RELAY
MANUAL_RELAY_SELECT
RESET
PAIR
```

产品必须自行完成：

```text
Node-2:
WiFi failure detected
→ Direct unavailable
→ Relay eligible
→ select Node-1
→ telemetry via Relay

Node-3:
WiFi failure detected
→ Direct unavailable
→ Relay eligible
→ select Node-1
→ telemetry via Relay
```

目标状态：

```text
NODE_1_ACTIVE_PATH=direct
NODE_2_ACTIVE_PATH=relay
NODE_3_ACTIVE_PATH=relay
```

Relay peer 必须为当前固定 Node-1，但 public-safe 归档不得输出 raw node identity。

## 11. T2 核心验收：Node-1 同时承担三项工作

Node-1 必须同时：

```text
1. 自己的 telemetry 持续 Direct
2. 转发 Node-2 telemetry
3. 转发 Node-3 telemetry
```

目标：

```text
NODE_1_OWN_DIRECT_HEALTHY=true
NODE_1_RELAY_NODE2_HEALTHY=true
NODE_1_RELAY_NODE3_HEALTHY=true
```

同时不允许：

```text
NODE_1_TELEMETRY_STARVATION=true
NODE_1_WIFI_DROP=true
NODE_1_RESET=true
NODE_1_QUEUE_RUNAWAY=true
```

Node-1 成为 Relay 后，自己的 Direct 业务不能退化为“只负责转发”。

## 12. Relay 只改变 transport path，不改变稳定节点身份

Manager / Broker / HA 必须仍然区分三个逻辑节点：

```text
Node-1 telemetry → Node-1
Node-2 telemetry → Node-2
Node-3 telemetry → Node-3
```

不得出现：

```text
Node-2 telemetry 被归入 Node-1
Node-3 telemetry 被归入 Node-1
```

因此：

```text
TRANSPORT_PATH_CHANGED=true
NODE_IDENTITY_CHANGED=false
```

HA 中三个节点实体应保持原身份和历史连续性。

## 13. T3 — Two-node Relay Steady-State

Node-2 / Node-3 在 Zone C 固定位置保持 Relay，不做持续移动。

建议每个 Relay 节点至少观察：

```text
>=10 complete telemetry cycles
```

正式窗口长度在 preclaim 后根据真实 telemetry cadence 确认。

分别验证：

```text
SEQ_STRICTLY_INCREASING=true
RELAY_ACCEPTED_COUNT>=10
RELAY_REJECTED_COUNT=0
WRONG_NODE_IDENTITY_COUNT=0
DUPLICATE_CANONICAL_COUNT=0
```

Node-1 自身 Direct telemetry 也必须保持连续。

### 重复数据检查

Direct→Relay 和 Relay→Direct 切换窗口最容易同时出现两个副本：

```text
Direct copy
+
Relay copy
```

必须证明 Manager replay / canonical pipeline 没有产生重复计数或 HA 双更新。

## 14. T4 — 仅将 Node-2 移回 Wi-Fi 覆盖范围

执行：

```text
MOVE Node-2:
WiFi UNAVAILABLE
→ WiFi GOOD

Node-3:
保持在 WiFi UNAVAILABLE / Relay Reachable 区域
```

目标混合状态：

```text
Node-1 = direct
Node-2 = direct
Node-3 = relay via Node-1
```

这是本轮最重要的状态之一，用于证明路径管理是：

```text
PER_NODE=true
GLOBAL_RELAY_MODE=false
```

## 15. Node-2 Relay → Direct 自动恢复链

Node-2 进入 Wi-Fi Good 区域后必须自行完成：

```text
WiFi detected
↓
WiFi association
↓
IP / network usable
↓
MQTT / TLS usable
↓
Direct telemetry accepted
↓
Direct becomes preferred
↓
Relay path released
```

禁止人工发送：

```text
STOP_RELAY
FORCE_DIRECT
PATH_DIRECT
```

目标：

```text
NODE_2_PHYSICAL_WIFI_RETURN=PROVEN
NODE_2_RELAY_TO_DIRECT_AUTOMATIC=PASS
```

## 16. T4 并发要求：Node-3 必须继续 Relay

Node-2 回 Direct 的过程中，Node-3 仍然保持 Zone C。

必须同时证明：

```text
NODE_2_RELAY_TO_DIRECT=PASS
NODE_3_RELAY_CONTINUITY=PASS
```

如果 Node-2 恢复 Direct 导致 Node-3 Relay 同时异常退出，则说明 Relay path state 存在跨节点全局耦合，应判定失败并停止后续自动推进。

## 17. T5 — 将 Node-3 移回 Wi-Fi 覆盖范围

执行：

```text
MOVE Node-3:
WiFi UNAVAILABLE
→ WiFi GOOD
```

目标最终路径：

```text
NODE_1_PATH=direct
NODE_2_PATH=direct
NODE_3_PATH=direct
```

Node-3 同样必须自行完成 Relay → Direct 状态机，不允许人工强制路径切换。

## 18. Relay 恢复后必须真正静默

恢复 Direct 不能只证明“Direct resumed”。

还必须证明：

```text
NODE_2_RELAY_TRAFFIC_QUIESCENT=true
NODE_3_RELAY_TRAFFIC_QUIESCENT=true
```

防止出现：

```text
Direct 已恢复
但 Relay 仍后台持续发送
```

否则可能导致：

- 不必要的电池消耗；
- ESP-NOW 空口占用；
- duplicate telemetry；
- replay churn；
- Node-1 长期承担无意义 forwarding。

## 19. T6 — 全 Direct 恢复后的稳定观察

Node-1 / Node-2 / Node-3 全部位于 Wi-Fi Good 区域后继续观察。

目标：

```text
NODE_1_PATH=direct
NODE_2_PATH=direct
NODE_3_PATH=direct

NO_RELAY_RESIDUAL_TRAFFIC=true
NO_PATH_FLAPPING=true
NO_DUPLICATE_TELEMETRY=true
```

特别检查恢复后是否发生：

```text
Direct
→ Relay
→ Direct
→ Relay
```

若 Wi-Fi 已稳定可用但 path 仍持续震荡，不得判 PASS。

## 20. 观测 authority 优先级

本轮不要求三块板同时 USB 连接 Mac。

优先采用真实运行态数据：

```text
1. AP / Wi-Fi association or usable-link state
2. Manager ingress source: direct / relay
3. Manager replay / canonical cursor
4. Broker authorization / rejection state
5. Home Assistant entity continuity
6. Board serial: 仅作为失败诊断辅助
```

不应为方便观测而让三块板长期通过 USB 供电或同时打开串口，因为 USB、DTR/RTS、供电条件可能改变真实现场行为。

三块板优先使用正常现场供电方式运行。

## 21. 建议记录的 KPI

每个节点至少记录：

| 指标 | Node-1 | Node-2 | Node-3 |
|---|---|---|---|
| Initial path | direct | direct | direct |
| Physical Wi-Fi loss detected | — | timestamp | timestamp |
| First Relay accepted telemetry | — | timestamp | timestamp |
| Direct→Relay transition latency | — | Δt | Δt |
| Relay telemetry count | own direct | N | N |
| Relay rejected count | — | 0 | 0 |
| Physical Wi-Fi return | — | timestamp | timestamp |
| First Direct accepted telemetry | — | timestamp | timestamp |
| Relay→Direct transition latency | — | Δt | Δt |
| duplicate sequence | 0 | 0 | 0 |
| reset count | 0 | 0 | 0 |
| pairing restart | 0 | 0 | 0 |

切换延迟正式门槛不在本文件中人为写死。

执行前应读取当前 frozen source 的：

```text
WiFi retry
WiFi loss / unusable determination
relay activation threshold
relay peer selection policy
direct recovery preference
direct recovery hysteresis
telemetry cadence
```

再以：

```text
configured threshold + bounded observation margin
```

定义 T1～T6 的 acceptance window。

## 22. 空间 / RF 环境记录

建议记录：

```text
AP_LOCATION_CLASS
NODE1_LOCATION_CLASS
NODE2_OUTAGE_LOCATION_CLASS
NODE3_OUTAGE_LOCATION_CLASS

AP_TO_NODE1_DISTANCE_APPROX
NODE1_TO_NODE2_DISTANCE_APPROX
NODE1_TO_NODE3_DISTANCE_APPROX

OBSTRUCTION_CLASS
```

`OBSTRUCTION_CLASS` 可使用：

```text
line_of_sight
one_wall
greenhouse_frame
outdoor_to_indoor
other
```

这些数据用于未来部署经验积累，但不作为固定米数 Gate。

## 23. RSSI 记录

如果当前 frozen firmware / runtime 已经提供相应只读字段，可以记录：

```text
WiFi RSSI
ESP-NOW / relay peer RSSI
```

用于后续分析：

```text
WiFi RSSI ↓
     Direct good
     transition
     Direct unavailable
           ↓
     Relay still healthy
```

本轮不新增代码只为采集 RSSI，也不提前人为制定 RSSI threshold。

## 24. 生命周期不变量

仅 transport path 变化时，下列 authority 不应变化：

```text
NODE_ID
hardware identity
pairing approval
MQTT credential generation
application-key epoch
peer-trust generation
DynSec role / ACL
SYSTEM_ID
```

必须保持：

```text
transport path change
!= pairing lifecycle change
!= credential recovery
!= application-key rotation
!= peer-trust rotation
```

若仅因 Wi-Fi 覆盖临时丢失就发生 pairing reopen、credential rotation、NODE_ID reassignment 或 DynSec mutation，应立即 fail-closed。

## 25. 安全边界

正式测试除物理移动节点外，默认不允许：

```text
BOARD_RESET
BOOT_BUTTON_ACTION
POWER_CYCLE
FLASH_WRITE
NVS_ERASE
NVS_MUTATION
PAIRING_RECOVERY
CREDENTIAL_RECOVERY
APPLICATION_KEY_MUTATION
PEER_TRUST_MUTATION
DYNSEC_MUTATION
BROKER_ACL_MUTATION
MANAGER_MUTATION
HOMEASSISTANT_MUTATION
T1_SERVICE_RESTART
AP_CONFIG_MUTATION
```

任何超出上述边界的诊断或恢复动作必须单独设计、单独授权，不得在 T0～T6 executor 中自动扩权。

## 26. 总体 PASS 判据

只有以下链路全部成立，才判定本轮 North Star PASS：

```text
PHYSICAL_WIFI_COVERAGE_LOSS_PROVEN=true

NODE_1_WIFI_CONTINUITY=PASS

NODE_2_WIFI_LOSS=PROVEN
NODE_3_WIFI_LOSS=PROVEN

NODE_2_DIRECT_TO_RELAY_AUTOMATIC=PASS
NODE_3_DIRECT_TO_RELAY_AUTOMATIC=PASS

NODE_1_TWO_NODE_RELAY_FORWARDING=PASS

NODE_2_RELAY_RUNTIME_STABLE=PASS
NODE_3_RELAY_RUNTIME_STABLE=PASS

NODE_2_PHYSICAL_WIFI_RETURN=PROVEN
NODE_2_RELAY_TO_DIRECT_AUTOMATIC=PASS

NODE_3_RELAY_CONTINUITY_DURING_NODE2_RECOVERY=PASS

NODE_3_PHYSICAL_WIFI_RETURN=PROVEN
NODE_3_RELAY_TO_DIRECT_AUTOMATIC=PASS

THREE_NODE_FINAL_DIRECT_STATE=PASS

RELAY_QUIESCENCE_AFTER_RECOVERY=PASS
NO_PATH_FLAPPING=true
NO_DUPLICATE_TELEMETRY=true

NODE_IDENTITY_CONTINUITY=true

PAIRING_MUTATION=false
CREDENTIAL_MUTATION=false
APPLICATION_KEY_MUTATION=false
PEER_TRUST_MUTATION=false
DYNSEC_MUTATION=false

BOARD_RESET=false
FLASH=false
NVS_MUTATION=false

T1_SERVICE_RESTART_REQUIRED=false
```

最终 North Star：

```text
N3W_THREE_BOARD_T1_REAL_WORLD_PATH_FAILOVER_VALIDATION=PASS

REAL_WIFI_COVERAGE_LOSS_PROVEN=true
TWO_NODE_RELAY_FAILOVER_PROVEN=true
MIXED_DIRECT_RELAY_OPERATION_PROVEN=true
AUTOMATIC_DIRECT_RECOVERY_PROVEN=true
RELAY_RELEASE_AFTER_WIFI_RECOVERY_PROVEN=true
```

## 27. Fail-closed 规则

以下任一情况应停止当前 Gate，不得自动“修好再继续”：

```text
Node identity ambiguity
Manager / Broker authority drift
unexpected pairing or credential lifecycle change
unexpected application-key / peer-trust change
unexpected DynSec mutation
Board reset / reboot not part of authorized scenario
wrong-node telemetry attribution
duplicate canonical telemetry not explained by replay protection
Node-1 loses own Direct path while relaying without environmental cause
Node-2 recovery disrupts Node-3 relay
path flapping persists after stable Wi-Fi return
```

普通的边界 RF 抖动应与产品状态机失败区分；如果测试位置处于 Zone B，应返回 P0 重新选择位置，而不是修改产品状态机以适应一次不稳定测试位置。

## 28. 下一逻辑 Gate

本规划文档本身不授权任何物理执行。

建议下一逻辑 Gate：

```text
CURRENT_GATE=
N3W_THREE_BOARD_T1_PATH_FAILOVER_READONLY_PRECLAIM
```

该 Gate 只读复核：

```text
1. 当前 exact firmware / Manager source authority
2. Wi-Fi loss / retry state machine
3. Relay activation条件与 peer selection
4. Direct recovery priority / hysteresis
5. telemetry cadence
6. 当前三板 identity / security baseline
7. T1 current Manager / Broker runtime authority
```

随后再根据当前源码中的真实参数生成一次完整的 P0 + T0～T6 物理执行计划。

```text
BOARD_ACCESS=false
LIVE_MUTATION=false
AUTO_EXECUTE_NEXT=false
```

## 29. 归档边界

本文只记录 public-safe 方案，不包含：

- raw NODE_ID；
- raw SYSTEM_ID；
- MQTT credential；
- Setup Secret；
- private keys；
- raw hardware identity；
- private T1 locator；
- raw Broker / Manager logs。

文档提交不改变 deployed product-source authority。