# ADR-0003：NODE_ID 不复用、硬件重新配对与可靠退役合同

- 状态：已接受；实现对齐待完成
- 日期：2026-07-26
- 决策来源：用户确认
- 关联：ADR-0002、C-07、技术路线 V0.5、技术路线 V0.6
- 替代范围：
  - 替代 ADR-0002 §3.1 中 `node_id`“可迁移”的定义；
  - 替代技术路线 V0.5 中 NODE_ID 可跨主板迁移的条款；
  - 替代 C-07 中退役 NODE_ID 进入 `reusable` 并可跨 hardware_id
    复用的产品策略；
  - 不替代 C-07 已实现的 outbox、凭据撤销、retained tombstone、
    持久化门禁、幂等重试和重启恢复机制。

## 1. 背景

`HARDWARE_ID` 代表具体 ESP32-C6 硬件，`NODE_ID` 由操作员在批准配对时
指定，决定 MQTT 业务主题和 Home Assistant 设备身份。V0.5 和 ADR-0002
曾允许在更换主板时把原 NODE_ID 迁移到新 HARDWARE_ID；C-07 当前实现又把
这种复用限制在退役清理完成、逻辑位置一致、私有身份已绑定且匿名兼容关闭
之后。

进一步产品评审认为，这套迁移规则会把“逻辑位置连续性”“物理硬件身份”
和“Home Assistant 历史连续性”耦合在一起，增加审批、审计、恢复和售后
解释成本。产品选择更简单且失败关闭的规则：每次新的硬件归属都使用新的
NODE_ID，系统内不拼接新旧硬件的历史。

同时，节点退役跨越 SQLite、Mosquitto Dynamic Security、MQTT retained
状态、Home Assistant Discovery 和 Manager 内存缓存。操作低频或由人工
触发，并不能消除中途失败和进程崩溃，因此可靠退役链必须保留。

## 2. 术语

| 术语 | 含义 |
|---|---|
| `HARDWARE_ID` | 具体硬件的不可变工厂身份；不决定 Home Assistant 设备身份。 |
| `NODE_ID` | 一次获批节点归属的逻辑身份；决定业务主题、Discovery identifiers 和历史归属。 |
| 当前归属 | 一个 hardware_id 与一个 node_id 之间尚未退役的有效绑定。 |
| 维修/轮换 | 同一当前归属内恢复连接、更新 Wi-Fi、轮换凭据或重新授权，不结束 NODE_ID。 |
| 退役 | 操作员显式结束当前归属，并执行凭据、retained 状态和运行时状态清理。 |
| 重新配对 | 已退役 hardware_id 使用新的配对会话重新进入系统，并取得全新 NODE_ID。 |

## 3. 决策

### 3.1 身份不变量

1. NODE_ID 一经分配，只属于当次 `hardware_id -> node_id` 归属。
2. NODE_ID 退役后永久封存，不再分配给任何 hardware_id，包括原
   hardware_id。
3. 更换主板必须走完整的新配对流程，并分配全新 NODE_ID。
4. 不支持 NODE_ID 跨硬件复用，不提供例外开关、逻辑位置豁免或人工强制
   复用入口。
5. 同一未退役硬件的 Wi-Fi 重配、凭据轮换、主机恢复和经授权维修不属于
   硬件更换，可以保留当前 NODE_ID。
6. 已退役 hardware_id 可以重新配对，但必须使用新的 pairing_id、严格递增
   的 pairing_epoch、全新凭据和从未使用过的新 NODE_ID。

### 3.2 退役触发

1. 退役只能由操作员显式触发。
2. 长期离线、availability 超时、传感器故障、Broker 暂时不可达或节点重启
   都不得自动触发退役。
3. 重复提交同一退役操作必须幂等，不得重复释放身份、删除其他节点状态或
   生成不同结果。

### 3.3 可靠退役顺序

退役保持以下持久化、可恢复顺序：

1. 在 SQLite 事务内记录退役意图，关闭当前 `hardware_id -> node_id`
   历史归属，把 NODE_ID 置为 `retiring`，并创建 retirement outbox。
2. 撤销该归属的 MQTT client、role、ACL 和相关凭据生命周期。
3. 向两个 Home Assistant Discovery 配置主题发布 retained 空 payload。
4. 向 canonical telemetry、availability、diagnostic 三个状态主题发布
   retained 空 payload。
5. 在同一 Manager 生命周期临界区内清除该 node_id 的 last_seen、
   availability、去重键和 Discovery 发布摘要缓存。
6. 只有凭据撤销和全部运行时清理均获得完成证据后，才完成 outbox，并把
   NODE_ID 租约置为永久 `retired`/`non_reusable` 终态。

所有外部步骤必须可安全重试。Manager 启动后必须继续处理未完成 outbox；
不得因为配对入口关闭或上次进程崩溃而放弃清理。

### 3.4 持久化 ingress 拒绝

五个 retained tombstone 不是唯一防线。退役和已完成退役的 NODE_ID 都必须
由持久化租约门禁拒绝：

- 拒绝旧节点继续发布的 ingress；
- 拒绝匿名兼容客户端冒用旧 NODE_ID；
- 拒绝 Manager 重启时由旧 retained canonical telemetry 恢复该节点；
- 拒绝任何新配对审批重新声明已使用过的 NODE_ID。

取消 `reusable` 产品语义不等于取消 NODE_ID lease；租约仍是防止旧节点
复活的核心持久化状态。

### 3.5 已退役硬件重新配对

已退役 hardware_id 重新发起配对时：

1. 上一退役 outbox 必须已经完成；清理未完成时失败关闭。
2. pairing_id 必须全新，pairing_epoch 必须严格递增，旧会话不得重放。
3. 当前 registration 可以进入新的 pending 会话，但历史 pairing session、
   registration event 和旧 `hardware_id -> node_id` 映射必须保留。
4. 审批必须选择未在 NODE_ID 历史或租约表中出现过的新 NODE_ID。
5. 新凭据生命周期必须形成新的 assignment/generation 记录，不能因
   hardware_id 已存在一条 revoked 记录而冲突，也不能覆盖旧撤销证据。

具体数据库可以采用 assignment_id、复合主键或历史表，但必须满足上述行为，
不得通过删除旧行来实现重新配对。

### 3.6 Home Assistant 历史

退役不删除 Home Assistant 中已经保存的历史、长期统计或审计记录。新硬件或
重新配对后的同一硬件使用新 NODE_ID，因此在 Home Assistant 中形成新的设备
身份和新曲线。

如使用者确需拼接新旧硬件曲线，只能通过系统外离线工具处理。Manager、
Home Assistant 集成和配对流程不提供自动合并、别名迁移或历史重写。

### 3.7 凭据签发与生命周期

生产凭据签发成功必须与凭据生命周期持久化形成一个明确合同：

- Dynamic Security provision 成功后记录对应 assignment、hardware_id、
  node_id 和 generation；
- 退役撤销通过同一 provisioning plan 计算规则和
  `DynsecProvisioner.deprovision()` 底层机制执行；
- 签发、生命周期记录和撤销之间不得依赖测试代码手工补写状态；
- 任何中间失败必须留下可重试、无秘密的证据，不得把凭据写入日志、Git 或
  retained 主题。

## 4. 与当前实现的差异

截至 `main@43aa37b0cc343efdd2024f369517e55c5b6461f1`
（greenhouse-manager `0.4.96`）：

- C-07 的 outbox、五个 tombstone、内存清理、持久化 ingress 门禁和重启
  恢复已经实现并通过隔离闭环；这些机制继续保留。
- `node_id_leases` 当前仍包含 `reusable`，审批底层仍存在跨 hardware_id
  复用参数；需要改为永久不可复用终态并移除相关入口。
- `observe_hello()` 当前拒绝所有 retired hardware_id；需要允许满足 §3.5
  的新会话。
- `credential_lifecycle` 当前以 hardware_id 的单条记录为中心；需要支持
  同一硬件退役后新的 assignment/generation，同时保留旧撤销证据。
- 生产凭据签发路径与 `CredentialLifecycleStore.activate()` 尚未形成统一
  端到端入口；需要在生产配对接入时补齐。

本 ADR 接受的是目标架构，不把上述实现差异表述为已经完成。

## 5. 必须修改的合同与测试

实现对齐时至少需要：

1. 将 NODE_ID lease 终态从可复用语义改为永久封存语义，并迁移已有
   `reusable` 记录。
2. 删除或禁用 `reuse_retired_node_id`、`private_identity_bound` 和
   logical_location_id 驱动的跨硬件复用路径；logical_location_id 可以继续
   用于位置审计，但不再授权身份复用。
3. 调整 retired hardware_id 的 hello、pending、approve 和凭据生命周期
   分支。
4. 增加“退役未完成时拒绝重新配对”“退役完成后新 NODE_ID 可配对”
   “旧 NODE_ID 永久拒绝”“跨硬件复用无任何例外”的测试。
5. 保留 C-07 的真实 Mosquitto Dynamic Security、真实 Home Assistant
   Discovery、五个 tombstone 和重启不复活隔离门。
6. 更新 ADR-0002、C-07、协议说明、操作员 CLI 帮助和技术路线，不再把
   NODE_ID 描述为可迁移。

## 6. 后果

优点：

- 用户和售后规则简单：换硬件就是新设备、新 NODE_ID；
- 不需要证明逻辑位置、私有身份绑定或匿名关闭后再开放复用；
- 降低旧硬件冒用、新旧实体混淆和历史错误拼接风险；
- 审计可以直接按不可变归属和事件时间线解释。

代价：

- 主板更换后 Home Assistant 会出现新设备，历史曲线不自动连续；
- NODE_ID 数量只增不减，需要足够大的命名空间和永久历史索引；
- 现有 C-07 身份复用代码和测试需要迁移；
- 同一硬件退役后重新配对需要支持多代凭据生命周期。

## 7. 不采用的方案

- **NODE_ID 随硬件迁移**：身份连续性收益不足以抵消授权、审计和复活风险。
- **仅同逻辑位置允许复用**：仍需可信位置证明和例外路径，产品规则复杂。
- **删除 outbox、两阶段租约和崩溃恢复**：无法处理跨数据库、Broker、
  retained 状态和内存的部分失败。
- **离线超时自动退役**：会把正常网络故障误判为不可逆生命周期动作。
- **退役时删除 HA 历史**：破坏审计与用户历史数据，不符合低频人工退役
  的产品预期。
