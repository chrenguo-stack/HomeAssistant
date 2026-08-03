# 温室环境监测系统分阶段技术开发路线 V0.6

**副标题：双产品线、身份不复用与可靠生命周期后继版**

| 项目 | 内容 |
|---|---|
| 文档版本 | V0.6 |
| 文档状态 | 后继架构基线；实现状态与验收证据分离 |
| 编制日期 | 2026-07-26 |
| 适用阶段 | 研发、样机验证、小规模试点与产品化准备 |
| 主机平台 | 64 位 Linux + Docker；当前参考硬件为斐讯 T1 |
| 节点平台 | ESP32-C6-WROOM-1；Wi-Fi 版 / LoRa 版 |
| 前序基线 | 《分阶段技术开发路线 V0.5｜双产品线与接口冻结版》 |
| 替代关系 | V0.5 原文件保持冻结；冲突内容由 ADR-0003 和本文件替代 |
| 审计基点 | `main@43aa37b0cc343efdd2024f369517e55c5b6461f1`；Manager 0.4.96 |

核心方向：**离线优先｜双产品线｜统一协议｜安全配对｜NODE_ID 不复用｜
集中状态｜可靠退役｜历史补发隔离**

## 0. 文档定位与使用规则

V0.6 是长期产品与技术路线，不是当前 PR、CI、实板或生产环境状态报告。
实时进度统一记录在 `docs/status/`，对话和阶段交接记录在
`docs/handoffs/`，验收证据记录在 `docs/acceptance/`。本文件不因每次
提交或测试结果而重写。

内容分为三类：

- **冻结决策**：后续设计和编码必须遵守；变更必须形成新的 ADR。
- **接口基线**：可以进入开发，但仍需通过模拟、隔离 Broker、实板、T1
  或现场测试。
- **待验证决策门**：尚未达到产品承诺条件，不得在销售、量产或宣传材料中
  表述为已完成能力。

V0.6 的主要修订：

1. NODE_ID 不再跨硬件迁移或复用；退役后永久封存。
2. 已退役 HARDWARE_ID 可以重新配对，但必须取得全新 NODE_ID。
3. 完整保留 C-07 的 outbox、凭据撤销、五个 retained tombstone、持久化
   ingress 门禁和重启恢复。
4. 明确 canonical 实时状态与历史补发是两条独立通道。
5. 明确 Manager 默认保存 7 天原始历史，Home Assistant 只导入小时统计投影。
6. 将 `state/<node_id>/meta` 标为保留接口；当前 Manager 实际状态主题只有
   telemetry、availability、diagnostic。
7. 明确 `greenhouse_manager/runtime/` 与 `ops/` 的模块分层。
8. 将阶段进度从架构路线中移出，只保留阶段依赖和验收门。

## 1. 总体目标与架构原则

### 1.1 产品目标

系统面向不熟悉 Linux、Docker、MQTT 和 Home Assistant 配置的温室与水产
养殖使用者。安装者只应完成供电、Wi-Fi 配网和一次明确的节点确认；新增
节点随后自动进入 Home Assistant，不要求固定路由器、固定 IP 或手工编辑
MQTT Discovery。

### 1.2 离线优先

- 节点在无 Wi-Fi、无 MQTT、无主机时继续采集传感器并使用固定五页 LCD
  显示。
- 网络、配对、凭据轮换和 OTA 不得阻塞传感器任务。
- LCD 背光保持关闭，页面内容和离线能力不因通信产品线改变。
- 离线只影响上报和 availability，绝不自动触发退役。

### 1.3 统一身份但不迁移

- SYSTEM_ID 标识一套温室系统。
- MANAGER_ID 标识主机管理实例。
- HARDWARE_ID 标识具体 ESP32-C6 硬件。
- NODE_ID 标识一次获批节点归属和 Home Assistant 设备身份。
- GATEWAY_ID 标识 Wi-Fi 中继或 LoRa 网关。
- 更换硬件、退役后重新配对都必须使用新 NODE_ID。
- 传输路径变化、网关切换、Wi-Fi 重配和同一当前归属内的凭据轮换不得改变
  NODE_ID。

### 1.4 集中规范状态

节点和网关只发布受限 ingress。只有 greenhouse-manager 可以校验、去重、
确定可用性、形成 canonical state 并发布 Home Assistant Discovery。无线
网关不得直接为子节点创建 HA 实体。

### 1.5 本地优先与安全渐进

系统默认在用户局域网内运行，数据不依赖厂商云。研发阶段允许受控兼容路径，
但生产安全必须逐步达到独立凭据、最小 ACL、TLS、可撤销身份、备份恢复和
受控密钥存储；任何阶段都不得把匿名实验状态描述为销售安全能力。

## 2. 产品线与硬件基线

### 2.1 Wi-Fi 版

- ESP32-C6 板载天线；
- Wi-Fi 直连为默认路径；
- 弱覆盖环境可使用 ESP-NOW 单跳子节点到 Wi-Fi 中继；
- 不在首版实现 ESP-NOW Mesh 或任意多跳路由。

### 2.2 LoRa 版

- ESP32-C6 + EWM22M-400T22S；
- 普通 LoRa 子节点到 LoRa 网关节点；
- LoRa 网关通过 Wi-Fi/TLS/MQTT 上传；
- 普通传感器节点不转发其他 LoRa 子节点；
- 只有单跳现场验证不足且新增网关不经济时，才评估独立供电的专用射频
  中继器。

### 2.3 共同硬件与功能

- 传感器：SCD30、SHT30、GY30、RS485 土壤温度/水分/电导率；
- 显示：LCD12864 五页；
- 主控：ESP32-C6-WROOM-1，8 MB Flash；
- 当前监测节点电源、RS485、LCD 和传感器接口保持共同基线；
- LoRa 版额外启用 EWM22M 引脚和无线配置。

### 2.4 产品线共同合同

两款产品共享：

- SYSTEM_ID、HARDWARE_ID、NODE_ID 和凭据模型；
- pairing、MQTT、canonical telemetry、availability 和 diagnostic；
- Home Assistant Device Discovery；
- 退役、凭据撤销、备份恢复和 OTA 原则；
- 同一传感器质量码、BOOT_ID、SEQ 和数据时间语义。

## 3. 系统角色与职责

| 角色 | 主要职责 | 明确限制 |
|---|---|---|
| 普通监测节点 | 采集、LCD、本地保护、Wi-Fi 直连或对应无线子链路 | 不发布 canonical state；不拥有 Manager 高权限 |
| ESP-NOW 子节点 | 单跳发送自身数据 | 不转发其他节点；不形成 Mesh |
| Wi-Fi 中继 | 终止 ESP-NOW 链路并上传 gateway ingress | 不直接创建子节点 HA 实体 |
| LoRa 子节点 | 通过 EWM22M 发送自身业务帧 | 不承担其他子节点转发 |
| LoRa 网关 | 终止 LoRa 应用会话、ACK、诊断并上传 | 不改变子节点 NODE_ID；不发布 canonical state |
| 专用 LoRa 中继 | 固定供电，仅转发两个无线段 | 后续决策门；不采集环境数据 |
| Mosquitto | TLS、Dynamic Security、客户端/角色/ACL | 不理解业务身份和退役策略 |
| greenhouse-manager | 配对、注册、入口校验、去重、状态、Discovery、退役 | 不依赖手工 YAML 才能接入节点 |
| Home Assistant | 设备/实体、历史、统计、自动化和界面 | 不签发节点凭据；不解析无线帧 |
| greenhouse-init | 首次生成系统身份、CA 和初始化资料 | 初始化后退出，不作为长期服务 |

greenhouse-manager 代码分层：

- `greenhouse_manager/runtime/` 保存生产运行时与核心状态逻辑；
- `greenhouse_manager/ops/` 保存操作员 CLI、迁移和运维入口；
- `ops/` 可以依赖 `runtime/`，`runtime/` 不得反向依赖 `ops/`；
- 冻结跨组件接口放在 `protocols/`，阶段状态和授权记录不得放入
  `protocols/`。

## 4. 双产品线通信路径

### 4.1 Wi-Fi 直连

1. 节点采集并在本地 LCD 显示。
2. 节点以独立凭据写入自身 `ingress/node/<node_id>/...`。
3. Manager 校验身份、payload、BOOT_ID、SEQ、质量和新鲜度。
4. Manager 发布 retained canonical state 与 Discovery。
5. Home Assistant 通过 MQTT 集成创建或更新设备和实体。

### 4.2 ESP-NOW 单跳补盲

1. 子节点使用应用层认证和 AEAD 帧发送数据。
2. Wi-Fi 中继验证无线会话并封装 gateway ingress。
3. Manager 恢复原 NODE_ID，执行与直连路径相同的校验和去重。
4. 路径切换不能创建第二套 HA 设备或回滚状态。

### 4.3 LoRa 星形单跳

1. LoRa 子节点使用独立会话材料发送业务帧。
2. 网关执行接收、ACK、重试统计和射频诊断。
3. 网关以自身 GATEWAY_MQTT 凭据上传带原 NODE_ID 的 gateway ingress。
4. Manager 是唯一 canonical state 和 Discovery 发布者。

### 4.4 网关切换

网关是传输角色，不是子节点业务身份所有者。网关切换只改变当前路径租约和
诊断；`SYSTEM_ID + NODE_ID` 保持不变。旧路径仅允许有限的已发送早期帧，
不得覆盖较新的 canonical state。

## 5. LoRa 中继冻结结论

F1.0 采用网关星形单跳，不让普通 LoRa 子节点承担转发。专用射频中继只有
满足以下条件才进入 N4-L：

- 现场单跳无法达到目标，增加网关不经济；
- 固定供电，不使用普通传感器节点电池；
- 首轮只验证一个中继跳数；
- 拓扑静态、无环；
- 中继不进入 Home Assistant 传感器设备模型；
- 端到端 NODE_ID、BOOT_ID、SEQ、认证、ACK 和去重仍由端点与 Manager
  负责。

## 6. 主机组件与恢复边界

### 6.1 Home Assistant

使用官方 MQTT 集成消费 Manager 发布的 Discovery 和状态。产品集成可以
提供 Config Flow、节点审批、修复提示和诊断，但不得绕过 Manager 签发
凭据或直接创建正式环境传感器实体。

### 6.2 Mosquitto

使用 Dynamic Security 管理 service、node 和 gateway 身份。ACL 默认拒绝：

- 普通节点只写自身 node ingress，只读自身 out；
- 网关只写自身 gateway ingress，只读自身 out；
- Manager 可读 ingress，写 state/out/Discovery；
- provisioning 身份只用于创建、轮换和撤销身份；
- Home Assistant 使用独立客户端。

### 6.3 greenhouse-manager

Manager 负责：

- pending/approve/reject 与配对会话；
- NODE_ID 分配和永久历史索引；
- Dynamic Security provisioning plan；
- canonical telemetry、availability、diagnostic；
- Home Assistant Device Discovery；
- C-06 历史补发；
- C-07 可靠退役；
- 重启恢复、审计和兼容边界。

### 6.4 备份恢复

主机备份必须成对覆盖 SYSTEM_ID、MANAGER_ID、CA、Dynamic Security、
registration、NODE_ID 历史、credential lifecycle 和未完成 outbox。无有效
备份时不得静默创建新系统并接管旧节点。

## 7. 身份、凭据与安全模型

| 标识/凭据 | 用途 | 规则 |
|---|---|---|
| SYSTEM_ID | 隔离一套温室系统 | 由初始化生成，可从受保护备份恢复 |
| MANAGER_ID | 标识主机管理实例 | 用于多主机冲突和配对归属 |
| HARDWARE_ID | 追踪具体硬件 | 不可变，不决定 HA 身份 |
| NODE_ID | 一次获批归属和 HA 身份 | Manager/操作员审批分配；退役后永久封存 |
| GATEWAY_ID | 网关逻辑身份 | 独立于子节点 NODE_ID |
| NODE_MQTT | 节点 MQTT client/username/password | 每节点、每代独立；可撤销 |
| NODE_AUTH_KEY | 无线或应用层认证材料 | 每节点独立；不作为共享系统万能密钥 |
| MANAGER_MQTT | Manager 服务身份 | 只保存在主机安全存储 |
| SYSTEM_ROOT_KEY | 签发/派生材料 | 不下发到所有节点，不进入日志或 Git |

### 7.1 NODE_ID 不复用

冻结规则以 ADR-0003 为准：

- 新硬件必须新 NODE_ID；
- 旧 NODE_ID 退役后永久不可分配；
- retired hardware_id 可在清理完成后以新 pairing_id、递增 epoch 和新
  NODE_ID 重新配对；
- 系统不拼接新旧节点的 HA 历史；
- logical_location_id 可以保留为位置审计字段，但不能授权 NODE_ID 复用。

### 7.2 一次性配对材料

节点在未配对状态使用硬件随机数生成至少 128 位 pairing PoP，并与
pairing_epoch 写入 NVS。LCD 只显示当前一次性二维码和由 transcript 派生的
短码；二维码成功消费、过期、恢复出厂或明确重新配对后必须失效。

PoP 不通过 MQTT、mDNS、UDP、日志或 Home Assistant 明文传播。6 位短码只
用于人眼核对，不能独立承担密钥功能。

### 7.3 安全会话

配对安全会话使用成熟原语：

1. 节点与 Manager 生成临时密钥；
2. PoP 认证 hardware_id、manager_id、pairing_id、nonce 和双方公钥的完整
   transcript；
3. ECDH shared secret 经 HKDF 派生方向隔离会话密钥；
4. AEAD 加密 credential bundle；
5. 节点验证 transcript、有效期、序列和 tag 后写入 pending 槽；
6. pending 测试成功后 commit，失败回滚 active。

具体原语和线格式以 `protocols/pairing/` 已冻结协议为准。

### 7.4 凭据签发合同

批准 registration 不等于已经签发 Broker 凭据。生产签发必须把
Dynamic Security provision 与 credential lifecycle activation 绑定到同一
assignment/generation，失败时留下无秘密、可重试证据。退役通过相同
provisioning plan 规则调用幂等 deprovision。

### 7.5 安全阶段

| 阶段 | 允许方案 | 必须说明 |
|---|---|---|
| 研发样机 | 受控 LAN、普通 NVS、临时匿名兼容 | 不是销售安全能力 |
| 小规模试点 | 独立凭据、最小 ACL、TLS、PoP、撤销和恢复演练 | 记录备份与密钥恢复 |
| 销售版本 | Secure Boot v2、Flash Encryption、NVS Encryption 按量产方案启用 | 必须验证烧录、维修、回滚和恢复 |

## 8. Manager 发现协议

发现只提供可配对候选，不建立信任。

1. mDNS/DNS-SD 为首选；
2. 局域网 UDP nonce 请求/响应为回退；
3. 二维码和用户确认完成所有权证明与目标系统选择。

发现响应只能包含协议版本、system hint、规范主机名、端口和 CA 摘要；不得
包含 MQTT 密码、NODE_AUTH_KEY、PoP 或系统根密钥。

发现多个 Manager 时节点不得按 RSSI、响应速度或 ID 自动选择。已绑定节点
不会因网络中出现新的 Manager 而自动开放配对或被接管。

## 9. 首次绑定、维修与 TLS 信任

### 9.1 首次绑定

1. 节点发现候选 Manager；
2. 用户扫描当前一次性二维码并选择目标系统；
3. Manager 验证 PoP 和安全 transcript；
4. 操作员批准并指定全新 NODE_ID；
5. Manager 创建独立 MQTT 身份和最小 ACL；
6. 加密下发 SYSTEM_ID、NODE_ID、CA、Broker endpoint、凭据和版本；
7. 节点写 pending、测试连接并发 claim；
8. Manager 验证后 commit；
9. Manager 发布 Discovery，LCD 短暂显示添加成功。

### 9.2 同一归属维修

同一未退役硬件的 Wi-Fi 更新、凭据轮换或经授权 repair 可以保留 NODE_ID。
维修必须使用新 pairing_id/epoch 和安全会话，不得把旧 PoP 或旧授权当成
长期后门。

### 9.3 恢复出厂

恢复出厂清除节点上的系统身份、长期凭据、Wi-Fi 和配对缓存，使节点回到
未绑定状态。服务器端当前归属不会仅因设备本地恢复出厂自动退役；操作员
仍需显式退役旧归属。重新批准时必须使用新 NODE_ID。

### 9.4 主机恢复

恢复 SYSTEM_ID、CA、Dynamic Security、registration 和 credential lifecycle
后，未退役节点无需重新配对。没有有效备份时不得静默生成新 CA 接管。

## 10. MQTT 主题、状态与 ACL 基线

统一前缀：

```text
gh/v1/<system_id>/
```

### 10.1 当前直连入口

```text
gh/v1/<sid>/ingress/node/<node_id>/telemetry
```

其他 register/status/event/ack 与 gateway ingress 必须在对应 schema 和
producer/consumer 同时冻结后启用，不能只因 V0.5 曾列出就视为已实现。

### 10.2 当前 canonical 状态

截至审计基点，Manager 实际使用：

```text
gh/v1/<sid>/state/<node_id>/telemetry
gh/v1/<sid>/state/<node_id>/availability
gh/v1/<sid>/state/<node_id>/diagnostic
```

三者 QoS 1、retain=true，由 Manager 唯一发布。`telemetry` 回答当前规范
状态，`availability` 回答节点可用性，`diagnostic` 回答可诊断状态。

### 10.3 保留的 meta 接口

```text
gh/v1/<sid>/state/<node_id>/meta
```

`meta` 是目标接口，不是当前已实现的第四个 Manager 状态主题。正式启用前
必须冻结 schema、发布触发条件、retain 语义、Discovery 依赖和退役
tombstone，并同步实现生产者、消费者和测试。

### 10.4 Discovery

当前每节点存在两个 retained 配置主题：

- device config；
- connectivity binary_sensor config。

Discovery 由 Manager 唯一发布和删除。退役时必须同时 tombstone。

### 10.5 ACL

| 客户端 | 允许发布 | 允许订阅 |
|---|---|---|
| 普通节点 | 自身 `ingress/node/<node_id>/#` | 自身 `out/node/<node_id>/#` |
| 网关 | 自身 `ingress/gateway/<gateway_id>/#` | 自身 `out/gateway/<gateway_id>/#` |
| Manager | ingress；state/out/Discovery | ingress、HA status 和必要恢复主题 |
| Home Assistant | 按集成需要读取 state/Discovery | 不写节点 ingress |

## 11. Canonical 实时状态、历史补发与去重

### 11.1 实时 canonical

- 每个 boot_id 内 seq 严格单调递增；
- Manager 拒绝旧 seq、重复和状态回退；
- canonical telemetry retain=true，只回答“当前状态”；
- Home Assistant 面板和 Discovery 只消费 canonical 当前状态；
- Manager 重启恢复 retained canonical 时仍需通过 NODE_ID lease 门禁。

### 11.2 C-06 历史补发

历史补发是独立数据通道：

- 使用独立 topic 和 schema；
- retain=false；
- 表示过去时间段的记录；
- 不参与 canonical seq 比较；
- 不覆盖 telemetry/availability/diagnostic；
- Manager 默认保存最近 7 天的原始采集分辨率；
- Home Assistant 只导入小时统计投影，用于补全曲线和事后分析；
- 原始历史仍由 Manager 保存，不把全部分钟级记录灌入 HA；
- 重复补发必须依据稳定记录键幂等；
- 精确 topic、schema、分页、确认和存储格式在 C-06 protocol ADR 中冻结后
  才进入实现。

### 11.3 可用性

区分：

- transport_available；
- node_alive；
- data_fresh；
- sensor_health；
- gateway_available；
- manager_registered。

长期离线只更新 availability 和 data_fresh，不删除 registration、Discovery
历史或触发退役。

### 11.4 路径租约和去重

同一 NODE_ID 同时只允许一个有效入口路径。路径切换需稳定确认、旧路径有限
接受窗口和 BOOT_ID+SEQ 去重；任何无线中继或网关都不能通过重发较旧帧回滚
canonical state。

## 12. C-07 可靠退役

### 12.1 操作员动作

退役是唯一触发完整状态清理的生命周期动作，必须由操作员显式发起。命令
必须幂等，允许低频使用，但执行链必须支持部分失败和进程崩溃恢复。

### 12.2 持久化流程

1. SQLite 事务记录 retired registration、历史映射、NODE_ID `retiring`
   租约和 retirement outbox。
2. 撤销 MQTT client、role、ACL 和凭据生命周期。
3. tombstone 两个 Discovery 配置。
4. tombstone telemetry、availability、diagnostic。
5. 清理 last_seen、availability、去重键和 Discovery 摘要缓存。
6. 取得全部完成证据后完成 outbox，并把旧 NODE_ID 置为永久不可复用。

### 12.3 防复活

- `retiring` 和永久 retired NODE_ID 都拒绝 ingress；
- retained canonical 恢复受同一门禁约束；
- Manager 重启继续未完成 outbox；
- 旧凭据和匿名兼容入口都不能让节点重新发布 Discovery；
- HA 已保存历史不删除。

### 12.4 重新配对

已退役 hardware_id 只有在上一 outbox 完成后才能进入新的 pending 会话。
新会话必须有新 pairing_id、递增 epoch、新凭据和全新 NODE_ID。历史 pairing
session、registration event、旧归属和撤销证据全部保留。

## 13. LCD 第 5 页与连接状态机

LCD 保持五页，不新增第 6 页。第 5 页承担配网、发现、配对和短暂成功状态：

| 状态 | LCD 内容 | 行为 |
|---|---|---|
| 未配置 Wi-Fi | 配网二维码、热点名和说明 | 进入 Captive Portal |
| Wi-Fi 已连，未发现主机 | 正在查找主机 | mDNS/UDP；继续本地监测 |
| 发现一个主机，未绑定 | 新增节点二维码和倒计时 | 等待用户确认 |
| 发现多个主机 | 提示在主机中选择 | 不自动绑定 |
| 配对中 | 握手、审批和凭据进度 | 防止重复配对 |
| 等待 HA 注册 | 正在创建设备 | 发布 ingress，等待 Discovery |
| 注册完成 | 短暂显示添加成功 | 转回长期状态页 |
| 已绑定离线 | 本地采集正常，显示网络/主机故障 | 退避重连，不开放配对 |

Wi-Fi 使用普通阶梯图标；涉及 LoRa 或 Wi-Fi+LoRa 时使用深色背景反白阶梯，
网关选举状态可闪烁。显示变化不得破坏固定五页内容和背光关闭约束。

## 14. 分阶段开发顺序

本章只冻结依赖顺序，不声明当前完成度。

| 阶段 | 侧别 | 核心目标 | 进入下一阶段条件 |
|---|---|---|---|
| D0 | 架构 | 双产品线、角色和单跳原则 | ADR-0001 与 V0.5 基线 |
| D1 | 架构 | 身份不复用、C-06/C-07 生命周期 | ADR、协议和迁移计划冻结 |
| H0 | 主机 | T1/64 位 Linux、恢复镜像、断电基线 | 连续运行和恢复测试 |
| H1 | 主机 | Compose、系统身份、Broker 与持久卷 | 可重复初始化和备份 |
| H2 | 主机 | MQTT V1、canonical state、Discovery、模拟节点 | 模拟节点完整进入 HA |
| H3 | 主机 | 发现、配对、凭据、退役和恢复 | 隔离闭环与故障矩阵 |
| N0 | 节点 | RC2 完整编译和离线实板基线 | 无网络长期稳定 |
| N1 | 节点 | Wi-Fi 配网和 Manager 发现 | 多主机和恢复通过 |
| N2 | 节点 | 安全配对、双槽凭据、TLS/MQTT、LCD | 实板端到端闭环 |
| N3-W | Wi-Fi 版 | ESP-NOW 单跳、路径租约与切换 | 不重复设备、不回滚 |
| N3-L | LoRa 版 | 星形单跳、ACK、重试和诊断 | 现场可达率达标 |
| N4-L | 可选 | 专用 LoRa 中继 | 仅在单跳不足时启动 |
| S1 | 系统 | OTA、备份恢复、老化、试点和售后工具 | 可复制、可恢复、可维护 |

每个阶段的当前 SHA、PR、CI、Artifact、授权和实机状态只在
`docs/status/`、`docs/acceptance/` 和 `docs/handoffs/` 中记录。

## 15. 验证矩阵与风险

### 15.1 验证矩阵

| 类别 | 关键场景 | 通过标准 |
|---|---|---|
| 离线运行 | 无 Wi-Fi/T1/MQTT | 采集和 LCD 持续，无重启风暴 |
| 发现 | mDNS 失败、UDP 回退、多主机 | 不自动接管，可恢复 |
| 配对 | 过期、重放、断电、重复审批 | 失败关闭，可安全重试 |
| 凭据 | 错误凭据、轮换、Broker 重启 | active 可回退，秘密不泄漏 |
| 退役 | 各外部步骤失败、Manager 崩溃 | outbox 恢复，旧节点不复活 |
| 身份 | 换硬件、retired hardware 重配 | 必须新 NODE_ID，旧 ID 永久拒绝 |
| 状态 | 重复、乱序、旧路径、重启恢复 | canonical 不回滚 |
| 历史 | 重复补发、跨窗口、HA 导入 | 不覆盖实时状态，小时投影幂等 |
| ESP-NOW | 中继掉线、信道变化、并发 | 单跳恢复，容量实测 |
| LoRa | 干扰、重试、网关切换 | 指标可诊断，可达率实测达标 |
| 主机 | 断电、容器异常、备份恢复 | 系统身份和未退役节点连续 |
| OTA | 中断、不兼容、低电、回滚 | 不使设备永久失联 |

### 15.2 主要风险

| 风险 | 影响 | 控制 |
|---|---|---|
| 二手主机硬件差异 | 稳定性和售后不一致 | 入库检测、统一镜像、备份和替换方案 |
| mDNS 路由器兼容 | 节点找不到主机 | UDP 回退、规范主机名、用户确认 |
| CA/密钥丢失 | 无法信任恢复主机 | 加密备份、恢复演练、访问控制 |
| 无线共享信道拥塞 | 延迟和掉线 | 单跳、调度、退避和容量实测 |
| 历史补发挤占实时链路 | 当前状态延迟 | 独立通道、限速、批次和优先级 |
| 永久 NODE_ID 增长 | 索引持续增长 | 大命名空间、索引和归档审计 |
| Home Assistant 版本变化 | Discovery/统计兼容 | 隔离集成门和版本适配 |
| 协议过早扩展 | 维护负担 | 先冻结 V1，兼容评审后扩展 |

## 附录 A：ESP32-C6 固定 GPIO 基线

| GPIO | 固定用途 |
|---|---|
| GPIO0 | TPS2116.ST 主电源状态，高电平表示主 5V |
| GPIO1 | 电池 ADC；475kΩ/475kΩ 分压；理论电池电压为 ADC×2，预留实板校准 |
| GPIO2 / GPIO3 | LCD12864 SPI CLK / MOSI |
| GPIO6 | 绿色状态 LED，高电平点亮 |
| GPIO10 / GPIO11 | EWM22M M0 / M1，仅 LoRa 版启用 |
| GPIO15 | RS485 土壤传感器电源，高电平开启；strapping 风险已知 |
| GPIO16 | LCD CS，`inverted=true` |
| GPIO17 / GPIO21 | RS485 RX / TX |
| GPIO18 / GPIO19 / GPIO20 | EWM22M RX / TX / AUX |
| GPIO22 / GPIO23 | I²C SDA / SCL |

## 附录 B：canonical telemetry 最小字段

```json
{
  "schema": "gh.telemetry/1",
  "node_id": "n_01JABCDEF",
  "boot_id": "boot_01J2A6Q9T8W4",
  "seq": 1284,
  "uptime_ms": 4285000,
  "sampled_at": null,
  "cap_hash": "sha256:8e91...",
  "fw_version": "F1.0-RC2-N2.0",
  "measurements": {
    "air_temperature_c": 26.4,
    "air_humidity_pct": 71.2,
    "co2_ppm": 684
  },
  "quality": {
    "co2_ppm": "ok"
  },
  "power": {
    "source": "main",
    "battery_v": 4.06,
    "battery_pct": null,
    "low": false
  }
}
```

字段规则：

- node_id 必须与主题一致；
- boot_id 每次启动变化；
- seq 在同一 boot_id 内严格递增；
- 无可信时间时 sampled_at 允许为 null，Manager 增加 received_at；
- 无效读数使用 null，不使用魔数；
- quality 使用冻结枚举；
- cap_hash 变化触发能力和 Discovery 复核。

## 附录 C：操作与状态边界

| 动作 | NODE_ID | 服务器 registration | 设备本地状态 |
|---|---|---|---|
| Wi-Fi 重配 | 保留 | 不退役 | 只更新网络 |
| 凭据轮换 | 保留 | 保留当前归属 | active/pending 双槽切换 |
| 同一硬件维修 | 保留 | 需明确 repair 授权 | 新会话，不重放旧 PoP |
| 恢复出厂 | 服务器不自动释放 | 仍需操作员退役 | 清除本地系统和凭据 |
| 显式退役 | 永久封存 | outbox 完成后终态 | 旧凭据失效 |
| retired hardware 重配 | 必须全新 | 新 assignment/generation | 新 PoP、新凭据 |
| 更换主板 | 必须全新 | 新 hardware_id 新归属 | 完整新配对 |
| 主机恢复 | 保留未退役 ID | 从备份恢复 | 节点无需重配 |

## 附录 D：术语

| 术语 | 定义 |
|---|---|
| canonical state | Manager 验证后发布、供 HA 使用的唯一当前可信状态 |
| ingress | 节点或网关只能写入的受限原始数据命名空间 |
| HARDWARE_ID | 具体硬件的工厂身份 |
| NODE_ID | 一次获批归属的逻辑身份；不跨硬件复用 |
| assignment | hardware_id 与 node_id 的一次有时间边界的归属 |
| pairing PoP | 一次性所有权证明 |
| BOOT_ID | 一次节点启动的随机会话标识 |
| path lease | Manager 对 NODE_ID 当前入口路径的临时所有权 |
| node lease | NODE_ID 的 active/retiring/永久 retired 持久化状态 |
| retirement outbox | 跨数据库、Broker、retained 状态和内存清理的可恢复任务 |
| historical replay | 独立于 canonical 当前状态的历史记录补发 |

## 附录 E：V0.5 到 V0.6 的替代矩阵

| V0.5 条款 | V0.6 处理 |
|---|---|
| NODE_ID 可迁移、主板更换沿用原 ID | 由 ADR-0003 替代；新硬件必须新 ID |
| 撤销只描述禁用凭据、结束租约 | 补齐 C-07 outbox、五个 tombstone、内存清理和重启恢复 |
| `state/<node_id>/meta` 与三个状态并列 | 标为保留接口，当前未实现 |
| canonical telemetry 同时承担所有历史语义 | 增加独立 C-06 历史补发通道 |
| 路线正文包含“下一步”进度 | 实时状态移到 status/acceptance/handoffs |
| greenhouse_manager 包结构未说明 | 明确 runtime/ops 分层 |

## 附录 F：架构决策与参考

- ADR-0001：Wi-Fi 版与 LoRa 版双产品通信架构；
- ADR-0002：M2 零配置配对、运行时凭据与 MQTT 安全边界；
- ADR-0003：NODE_ID 不复用、硬件重新配对与可靠退役合同；
- C-07：`docs/development/c07-node-retirement.md`；
- 模块生命周期：`docs/development/module-lifecycle-rules.md`；
- Home Assistant MQTT：<https://www.home-assistant.io/integrations/mqtt/>；
- Mosquitto Dynamic Security：
  <https://mosquitto.org/documentation/dynamic-security/>；
- ESP-IDF ESP-NOW：
  <https://docs.espressif.com/projects/esp-idf/zh_CN/stable/esp32c6/api-reference/network/esp_now.html>；
- ESP-IDF NVS Encryption：
  <https://docs.espressif.com/projects/esp-idf/en/stable/esp32c6/api-reference/storage/nvs_encryption.html>。

## 版本结束语

V0.6 保留 V0.5 的双产品线、离线优先、集中规范状态和单跳补盲原则，并以
ADR-0003 简化身份生命周期。后续实现应先对齐 NODE_ID 永久封存、retired
hardware 新身份重配和凭据生命周期，再继续扩展历史补发和无线能力；任何
完成度必须由独立状态与验收证据确认。
