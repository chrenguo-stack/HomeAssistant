# 温室环境监测系统分阶段技术开发路线 V0.7

**副标题：双产品线、身份不复用、普通 LoRa 节点网关化与可靠生命周期后继版**

| 项目 | 内容 |
|---|---|
| 文档版本 | V0.7 |
| 文档状态 | 后继架构基线；普通 LoRa 节点网关角色冻结；实现状态与验收证据分离 |
| 编制日期 | 2026-07-28 |
| 适用阶段 | 研发、样机验证、小规模试点与产品化准备 |
| 主机平台 | 64 位 Linux + Docker；当前参考硬件为斐讯 T1 |
| 节点平台 | ESP32-C6-WROOM-1；Wi-Fi 版 / LoRa 版 |
| 前序基线 | V0.6 身份不复用与可靠生命周期后继版 |
| 替代关系 | V0.5 与 V0.6 原文件保持冻结；冲突内容由 ADR-0003 和本文件替代 |
| 实施决策 | `D1-PROJECT-ROADMAP-V0.7-AND-C07-IDENTITY-SEMANTICS-CORRECTION-20260729-01` |

核心方向：**离线优先｜双产品线｜NODE_ID 不复用｜普通节点网关化｜可靠退役｜历史补发隔离**

## 0. 文档定位与使用规则

V0.7 是长期产品与技术路线，不是当前 PR、CI、实板或生产环境状态报告。
实时进度统一记录在 `docs/status/`，对话和阶段交接记录在 `docs/handoffs/`，
验收证据记录在 `docs/acceptance/`。本文件不因每次提交或测试结果而重写。

内容分为三类：

- **冻结决策**：后续设计和编码必须遵守；变更必须形成新的 ADR。
- **接口基线**：可以进入开发，但仍需通过模拟、隔离 Broker、实板、T1 或现场测试。
- **待验证决策门**：尚未达到产品承诺条件，不得在销售、量产或宣传材料中表述为已完成能力。

V0.7 的主要修订：

1. 删除专用 LoRa 中继器产品方向及对应独立硬件阶段。
2. 冻结“普通 LoRa 环境监测节点承担网关角色”的产品模型。
3. 冻结网关候选资格、Manager 集中选举、GATEWAY_ID 有限期租约、双入口隔离和切换门禁。
4. NODE_ID 不跨硬件迁移或复用；退役后永久封存。
5. 已退役 HARDWARE_ID 在上一 outbox 完成后，可以使用新会话、新凭据和全新 NODE_ID 重新配对。
6. 完整保留 C-07 的 outbox、凭据撤销、五个 retained tombstone、持久化 ingress 门禁和重启恢复。
7. canonical 实时状态与历史补发保持两条独立通道；Manager 默认保存 7 天原始历史，Home Assistant 只导入小时统计投影。
8. 阶段进度从架构路线中移出，只保留阶段依赖和验收门。

## 1. 总体目标与架构原则

### 1.1 产品目标

系统面向不熟悉 Linux、Docker、MQTT 和 Home Assistant 配置的温室与水产养殖使用者。
安装者只应完成供电、Wi-Fi 配网和一次明确的节点确认；新增节点随后自动进入 Home Assistant，
不要求固定路由器、固定 IP 或手工编辑 MQTT Discovery。

### 1.2 离线优先

- 节点在无 Wi-Fi、无 MQTT、无主机时继续采集传感器并使用固定五页 LCD 显示。
- 网络、配对、凭据轮换和 OTA 不得阻塞传感器任务。
- LCD 背光保持关闭，页面内容和离线能力不因通信产品线改变。
- 离线只影响上报和 availability，绝不自动触发退役。

### 1.3 统一身份但不迁移

- SYSTEM_ID 标识一套温室系统。
- MANAGER_ID 标识主机管理实例。
- HARDWARE_ID 标识具体 ESP32-C6 硬件。
- NODE_ID 标识一次获批节点归属和 Home Assistant 设备身份。
- GATEWAY_ID 标识 Wi-Fi 中继或由普通 LoRa 环境监测节点承担的网关角色；不替代设备自身 NODE_ID。
- 更换硬件、退役后重新配对都必须使用新 NODE_ID。
- 传输路径变化、网关角色启停、Wi-Fi 重配和同一当前归属内的凭据轮换不得改变 NODE_ID。

### 1.4 集中规范状态

节点和网关角色只发布受限 ingress。只有 greenhouse-manager 可以校验、去重、确定可用性、
形成 canonical state 并发布 Home Assistant Discovery。承担网关角色的监测节点不得直接为子节点创建 HA 实体。

## 2. 产品线与硬件基线

### 2.1 Wi-Fi 版

- ESP32-C6 板载天线；
- Wi-Fi 直连为默认路径；
- 弱覆盖环境可使用 ESP-NOW 单跳子节点到 Wi-Fi 中继；
- 不在首版实现 ESP-NOW Mesh 或任意多跳路由。

### 2.2 LoRa 版

- 所有 LoRa 产品均为完整环境监测节点：ESP32-C6 + EWM22M-400T22S，并保留共同传感器、LCD 和离线采集能力；
- 普通状态下节点发送自身业务帧；具备稳定回传、电源、资源和 LoRa 健康条件的节点可由 Manager 授权承担网关角色；
- 网关节点通过 Wi-Fi/TLS/MQTT 上传自身数据和其他 LoRa 子节点数据；
- 自身遥测继续使用 node ingress，代子节点转发的数据使用独立 gateway ingress；
- 不设计专用 LoRa 中继器，也不在首版实现 LoRa-to-LoRa 多跳或 Mesh；覆盖不足时增加普通 LoRa 环境监测节点并将其部署为网关。

### 2.3 共同硬件与功能

- 传感器：SCD30、SHT30、GY30、RS485 土壤温度/水分/电导率；
- 显示：LCD12864 五页；
- 主控：ESP32-C6-WROOM-1，8 MB Flash；
- LoRa 版额外启用 EWM22M 引脚、无线配置、GATEWAY_ID 租约和网关转发任务。

## 3. 系统角色与职责

| 角色 | 主要职责 | 明确限制 |
|---|---|---|
| 普通监测节点 | 采集、LCD、本地保护、Wi-Fi 直连或对应无线子链路 | 不发布 canonical state；不拥有 Manager 高权限 |
| ESP-NOW 子节点 | 单跳发送自身数据 | 不转发其他节点；不形成 Mesh |
| Wi-Fi 中继 | 终止 ESP-NOW 链路并上传 gateway ingress | 不直接创建子节点 HA 实体 |
| LoRa 环境监测节点 | 采集、LCD、本地保护并发送自身业务帧；具备条件时成为网关候选 | 未取得 GATEWAY_ID 租约时不转发其他节点；不形成 Mesh |
| LoRa 网关角色 | 保持自身监测，同时终止 LoRa 应用会话、ACK、诊断并上传 gateway ingress | 不改变本机或子节点 NODE_ID；不直接发布 canonical state |
| Mosquitto | TLS、Dynamic Security、客户端/角色/ACL | 不理解业务身份和退役策略 |
| greenhouse-manager | 配对、注册、入口校验、去重、状态、Discovery、退役 | 不依赖手工 YAML 才能接入节点 |
| Home Assistant | 设备/实体、历史、统计、自动化和界面 | 不签发节点凭据；不解析无线帧 |

代码分层：

- `greenhouse_manager/runtime/` 保存生产运行时与核心状态逻辑；
- `greenhouse_manager/ops/` 保存操作员 CLI、迁移和运维入口；
- `ops/` 可以依赖 `runtime/`，`runtime/` 不得反向依赖 `ops/`；
- 冻结跨组件接口放在 `protocols/`，阶段状态和授权记录不得放入 `protocols/`。

## 4. 双产品线通信路径

### 4.1 Wi-Fi 直连

节点以独立凭据写自身 node ingress；Manager 校验身份、payload、BOOT_ID、SEQ、质量和新鲜度，
再发布 retained canonical state 与 Discovery。

### 4.2 ESP-NOW 单跳补盲

子节点使用应用层认证和 AEAD 帧单跳发送；Wi-Fi 中继封装 gateway ingress；Manager 恢复原 NODE_ID，
路径切换不得创建第二套 HA 设备或回滚状态。

### 4.3 LoRa 星形单跳

未承担网关角色的 LoRa 节点发送自身业务帧。承担网关角色的普通 LoRa 节点保持自身采集和 LCD，
同时执行子节点接收、ACK、重试统计和射频诊断。本机数据走 node ingress，转发数据走 gateway ingress。

## 5. LoRa 网关角色与准入冻结结论

V0.7 删除“专用 LoRa 中继器”产品方向。“中继”仅指普通 LoRa 环境监测节点承担网关转发，
不指 LoRa-to-LoRa 透明转发、多跳路由或 Mesh。

网关候选必须：

- 已完成正式绑定且当前归属为 active；
- EWM22M 配置、AUX/UART 和无线会话健康；
- Wi-Fi/TLS/MQTT 回传经过稳定窗口验证；
- 主电源、电池余量、内存、队列、任务看门狗和重启频率合格；
- 取得 Manager 签发的 GATEWAY_ID、最小 ACL 和有限期租约。

Manager 综合回传稳定性、电源、部署位置、LoRa 覆盖、当前负载和运行健康度集中选举，
不得只按 Wi-Fi RSSI 决定。切换只改变路径租约和诊断，NODE_ID 不变。

## 6. 主机组件与恢复边界

主机备份必须成对覆盖 SYSTEM_ID、MANAGER_ID、CA、Dynamic Security、registration、NODE_ID 历史、
credential lifecycle 和未完成 outbox。无有效备份时不得静默创建新系统并接管旧节点。

## 7. 身份、凭据与安全模型

| 标识/凭据 | 用途 | 规则 |
|---|---|---|
| HARDWARE_ID | 追踪具体硬件 | 不可变，不决定 HA 身份 |
| NODE_ID | 一次获批归属与 HA 身份 | 当前归属内稳定；退役后永久封存 |
| GATEWAY_ID | 当前网关角色 | 有限期租约；不替代 NODE_ID |
| pairing_id | 配对会话 | 每次新生命周期必须全新 |
| pairing_epoch | 防回退代次 | 对同一 HARDWARE_ID 严格递增 |
| NODE_MQTT | 节点自身入口凭据 | 每归属独立、可轮换、可撤销 |
| GATEWAY_MQTT | 网关入口凭据 | 与 GATEWAY_ID 租约绑定、最小 ACL |

NODE_ID 一经出现于当前租约或历史索引即永久保留。不得通过逻辑位置、匿名关闭、私有身份绑定、
人工开关或删除历史行恢复可分配状态。

## 8. Manager 发现协议

优先 mDNS，UDP 作为回退。发现报文不得包含 PoP、长期凭据或可用于接管的秘密。发现多个 Manager 时，
节点不得自动按 RSSI、响应速度或 ID 选择。

## 9. 首次绑定、维修与 TLS 信任

首次绑定使用一次性 PoP 和临时安全会话建立系统 CA、Broker 规范主机名和每节点凭据。
同一未退役归属内的 Wi-Fi 重配、凭据轮换和经授权维修可以保留 NODE_ID；显式退役结束当前归属。

## 10. MQTT 主题、状态与 ACL 基线

- 节点：`gh/v1/<system_id>/ingress/node/<node_id>/...`
- 网关：`gh/v1/<system_id>/ingress/gateway/<gateway_id>/...`
- canonical：`gh/v1/<system_id>/state/<node_id>/{telemetry,availability,diagnostic}`
- `state/<node_id>/meta` 为保留接口，当前不表述为已实现。
- 节点与网关默认拒绝，只获得自身入口和自身下行所需最小权限。

## 11. Canonical 实时状态、历史补发与去重

canonical telemetry 只表示当前可信状态。历史补发使用独立 topic/schema、`retain=false`、独立分页和确认，
不参与 canonical SEQ 比较，也不得覆盖当前状态。Manager 默认保存 7 天原始分辨率记录，Home Assistant 只导入小时统计投影。

## 12. C-07 可靠退役

### 12.1 触发

退役只能由操作员显式触发。长期离线、availability 超时、传感器故障、Broker 暂时不可达或节点重启
均不得自动触发退役。

### 12.2 持久化顺序

1. SQLite 事务记录 retired registration、历史映射、NODE_ID `retiring` 租约和 retirement outbox。
2. 撤销 MQTT client、role、ACL 和凭据生命周期。
3. tombstone 两个 Discovery 配置。
4. tombstone telemetry、availability、diagnostic。
5. 清理 last_seen、availability、去重键和 Discovery 摘要缓存。
6. 取得全部完成证据后完成 outbox，并把旧 NODE_ID 置为永久 `retired`。

### 12.3 防复活

- `retiring` 和永久 `retired` NODE_ID 都拒绝 ingress；
- retained canonical 恢复受同一门禁约束；
- Manager 重启继续未完成 outbox；
- 旧凭据和匿名兼容入口都不能让节点重新发布 Discovery；
- Home Assistant 已保存历史不删除。

### 12.4 已退役 HARDWARE_ID 重新配对

上一 outbox 未完成时失败关闭。完成后，同一 HARDWARE_ID 可以进入新 pending 会话，但必须：

- 使用全新 pairing_id；
- pairing_epoch 严格大于历史最大值；
- 签发全新凭据和更高 generation；
- 分配从未出现在 NODE_ID 租约或历史表中的全新 NODE_ID；
- 保留历史 pairing session、registration event、旧归属、outbox 和撤销证据。

## 13. LCD 第 5 页与连接状态机

LCD 保持固定五页和背光关闭。第 5 页承担配网、发现、配对、等待 HA 注册和短暂成功状态。
涉及 LoRa 或 Wi-Fi+LoRa 时使用深色背景反白阶梯，网关选举状态可闪烁。

## 14. 分阶段开发顺序

1. **N0/M0/M1**：离线采集、LCD、canonical state 和 Discovery 基线。
2. **M2/N2**：正式配对、每节点凭据、TLS、轮换、撤销与 C-07 身份语义。
3. **H0/H1**：可重复初始化、成对备份恢复、第二台主机恢复、断电和容器故障恢复。
4. **C-06**：独立历史补发协议、7 天原始存储、小时统计投影和断点续传。
5. **N3-W**：ESP-NOW 单跳补盲。
6. **N3-L**：普通 LoRa 节点网关候选、GATEWAY_ID 租约、资源隔离和星形单跳。
7. **控制节点**：在监测、通信和恢复闭环稳定后进入低压安全控制。

进入 N3-W/N3-L 前，N2、H0/H1 和 C-06 必须达到各自验收门；不得用新无线功能分散当前收口工作。

## 15. 验证矩阵与风险

至少覆盖：

- 数据库从 `reusable` 到永久 `retired` 的 fail-closed 迁移；
- 跨硬件和同硬件旧 NODE_ID 复用永久拒绝；
- outbox 未完成时重新配对拒绝；
- outbox 完成后新 pairing_id、递增 epoch、新 NODE_ID 和新凭据成功；
- Manager 崩溃、重启和重复处理 outbox 的幂等性；
- 五个 retained tombstone、旧 retained canonical 防复活和旧凭据拒绝；
- 网关租约到期、回传抖动、低电、资源不足和切换滞回；
- canonical 与历史补发乱序、重复和断点续传隔离。

## 附录 A：固定硬件边界

ESP32-C6-WROOM-1、8 MB Flash、SCD30、SHT30、GY30、RS485 土壤三合一、LCD12864 五页及背光关闭保持基线。

## 附录 B：canonical telemetry 最小字段

`schema`、`node_id`、`boot_id`、`seq`、`uptime_ms`、`sampled_at`、`cap_hash`、`fw_version`、
`measurements`、`quality`、`power`；Manager 增加 `received_at`。

## 附录 C：操作与状态边界

架构基线不构成物理授权、生产变更、Ready、merge、release、tag 或 deployment 授权。

## 附录 D：术语

- canonical state：Manager 验证后供 Home Assistant 使用的唯一当前可信状态。
- assignment：一次 HARDWARE_ID 与 NODE_ID 的获批归属及其凭据生命周期。
- retirement outbox：跨 SQLite、Broker、retained 状态和 Manager 内存清理的持久化工作队列。
- gateway role：普通环境监测节点承担的附加传输角色。

## 附录 E：V0.5/V0.6 到 V0.7 的替代矩阵

| 前序条款 | V0.7 处理 |
|---|---|
| NODE_ID 可迁移、主板更换沿用原 ID | 由 ADR-0003 替代；新硬件必须新 ID |
| NODE_ID 清理完成后可复用 | 改为永久 `retired`，任何硬件均不可复用 |
| retired HARDWARE_ID 一律拒绝 | outbox 完成后允许新会话、新凭据和新 NODE_ID |
| 专用 LoRa 中继器作为可选产品方向 | 删除；增加普通 LoRa 环境监测节点并授权其承担网关角色 |
| LoRa 网关是否具有传感器不明确 | 冻结为普通节点附加角色，保留自身 NODE_ID、采集和 LCD |
| canonical telemetry 同时承担历史语义 | 增加独立 C-06 历史补发通道 |

## 附录 F：架构决策

- ADR-0001：Wi-Fi 版与 LoRa 版双产品通信架构；
- ADR-0002：M2 零配置配对、运行时凭据与 MQTT 安全边界；
- ADR-0003：NODE_ID 不复用、硬件重新配对与可靠退役合同；
- C-07：`docs/development/c07-node-retirement.md`。

V0.7 保留双产品线、离线优先、集中规范状态、身份不复用、可靠退役和历史补发隔离原则，
并删除专用 LoRa 中继器产品方向，冻结普通 LoRa 环境监测节点承担网关角色的准入、选举、租约和切换边界。
