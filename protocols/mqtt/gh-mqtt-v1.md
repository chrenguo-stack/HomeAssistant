# gh-mqtt-v1 最小协议

状态：Draft / V0.5 Sprint 0

## 1. 目标

`gh-mqtt-v1` 是温室环境监测系统中节点、网关、`greenhouse-manager` 和 Home Assistant 之间的最小稳定消息契约。

原则：

- 节点只发布原始入口消息，不直接发布 Home Assistant Discovery；
- `greenhouse-manager` 是规范化状态和 Home Assistant Discovery 的唯一发布者；
- Wi-Fi 直连节点与 LoRa 子节点使用同一业务数据模型；
- 网关只封装和转发子节点业务帧，不修改业务内容；
- 所有数值单位写入字段名；
- 缺失数据使用 `null` 和质量字段，不使用 `-999` 等哨兵值；
- 遥测去重键为 `node_id + boot_id + seq`。

## 2. Topic 根路径

```text
gh/v1/<system_id>/
```

`system_id` 在设备配对时由 manager 下发，设备不得自行生成新的系统 ID。

## 3. 节点入口 Topic

```text
gh/v1/<sid>/ingress/node/<node_id>/register
gh/v1/<sid>/ingress/node/<node_id>/telemetry
gh/v1/<sid>/ingress/node/<node_id>/status
gh/v1/<sid>/ingress/node/<node_id>/event
gh/v1/<sid>/ingress/node/<node_id>/ack
```

## 4. 网关入口 Topic

```text
gh/v1/<sid>/ingress/gateway/<gateway_id>/<node_id>/frame
gh/v1/<sid>/ingress/gateway/<gateway_id>/status
gh/v1/<sid>/ingress/gateway/<gateway_id>/event
```

`frame` 载荷使用 `gh.relay/1` 包装，内部业务帧保持端到端完整。

## 5. Manager 下行 Topic

```text
gh/v1/<sid>/out/node/<node_id>/command
gh/v1/<sid>/out/node/<node_id>/config
gh/v1/<sid>/out/node/<node_id>/confirm
```

## 6. Manager 规范化状态 Topic

```text
gh/v1/<sid>/state/<node_id>/telemetry
gh/v1/<sid>/state/<node_id>/availability
gh/v1/<sid>/state/<node_id>/diagnostic
gh/v1/<sid>/state/<node_id>/meta
```

## 7. 遥测载荷 `gh.telemetry/1`

必填字段：

- `schema`：固定为 `gh.telemetry/1`；
- `node_id`：稳定节点 ID；
- `boot_id`：每次启动生成的新 ID；
- `seq`：本次启动周期内单调递增序号；
- `uptime_ms`：设备启动后的毫秒数；
- `cap_hash`：当前能力集合哈希；
- `measurements`：测量值对象；
- `quality`：每个测量值的质量对象；
- `power`：供电状态。

可选字段：

- `sampled_at`：设备有可信时间时使用 RFC3339；
- `fw_version`：固件版本；
- `hardware_id`：仅注册或诊断阶段使用，常规遥测可省略。

### 7.1 标准测量字段

```text
air_temperature_c
air_humidity_pct
co2_ppm
illuminance_lx
soil_temperature_c
soil_moisture_pct
soil_ec_us_cm
vpd_kpa
dew_point_c
absolute_humidity_g_m3
ppfd_umol_m2_s
dli_today_mol_m2_d
dli_yesterday_mol_m2_d
battery_v
battery_pct
```

节点可省略未配置的能力字段，但不能用无效数字代替缺失值。

### 7.2 质量枚举

```text
ok
warming
stale
fault
not_present
```

示例：传感器启动预热期间，测量值为 `null`，质量为 `warming`。

## 8. Manager 增补字段

manager 接收入口遥测后：

1. 校验节点身份和载荷结构；
2. 按 `node_id + boot_id + seq` 去重；
3. 增加 `received_at`；
4. 计算在线状态和陈旧状态；
5. 发布规范化 retained 状态；
6. 更新 Home Assistant Discovery。

节点不得自行填写 `received_at`。

## 9. QoS 与 Retain

| 消息 | QoS | Retain |
|---|---:|---:|
| 节点 telemetry/frame | 1 | 否 |
| register/status/event/ack | 1 | 否 |
| command/config/confirm | 1 | 否 |
| canonical telemetry | 1 | 是 |
| availability/meta/diagnostic | 1 | 是 |
| Home Assistant Discovery | 1 | 是 |

规范化遥测超过 manager 配置的陈旧时间后，实体应标记 unavailable，不能仅依赖旧 retained 数值继续显示为在线。

## 10. ACL 最小规则

节点：

- 可写自身 `ingress/node/<node_id>/#`；
- 可读自身 `out/node/<node_id>/#`；
- 不可写 `state/#` 和 `homeassistant/#`。

网关：

- 可写自身 gateway 入口命名空间；
- 可读自身下行命名空间；
- 不可写规范化状态和 Discovery。

manager：

- 可读全部 `ingress/#`；
- 可写 `state/#`、`out/#` 和 `homeassistant/#`。

## 11. 兼容性规则

- `schema` 主版本变化代表不兼容变更；
- V1 内允许增加可选字段；
- 已发布字段不得改变含义或单位；
- 未识别字段应忽略，不得导致整包拒绝；
- 缺失必填字段或类型错误必须拒绝并记录诊断事件。

## 12. 当前冻结范围

本轮冻结：

- Topic 层级；
- `gh.telemetry/1` 基本字段；
- 质量枚举；
- QoS/retain 规则；
- 去重键；
- manager 唯一规范化发布者原则。

后续单独冻结：

- `gh.register/1`；
- `gh.command/1`；
- `gh.relay/1` 二进制网关封装；
- 配对和密钥轮换协议。
