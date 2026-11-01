# ADR-0003：NODE_ID 不复用、硬件重新配对与可靠退役合同

- 状态：已接受；由本决策完成 Manager 0.4.97 运行时对齐
- 日期：2026-07-26；实现对齐日期：2026-07-30
- 决策来源：用户确认
- 实施决策：`D1-PROJECT-ROADMAP-V0.7-AND-C07-IDENTITY-SEMANTICS-CORRECTION-20260729-01`
- 关联：ADR-0002、C-07、技术路线 V0.7
- 替代范围：
  - 替代 ADR-0002 中 NODE_ID“可迁移”的定义；
  - 替代 V0.5/V0.6 中 NODE_ID 可跨主板迁移或进入 `reusable` 的条款；
  - 不替代 C-07 已实现的 outbox、凭据撤销、retained tombstone、持久化门禁、幂等重试和重启恢复机制。

## 1. 背景

HARDWARE_ID 代表具体 ESP32-C6 硬件；NODE_ID 由操作员在批准配对时指定，决定 MQTT 业务主题和
Home Assistant 设备身份。早期设计允许主板更换时迁移 NODE_ID，C-07 又把复用限制在清理完成、
逻辑位置一致、私有身份绑定且匿名兼容关闭之后。该规则把物理硬件、逻辑位置和历史连续性耦合，
增加审批、审计、恢复和售后解释成本。

产品采用更简单且失败关闭的规则：每次新的硬件归属使用新的 NODE_ID，系统内不拼接新旧硬件历史。
可靠退役链仍必须跨 SQLite、Dynamic Security、retained 状态、Discovery 和 Manager 内存安全恢复。

## 2. 术语

| 术语 | 含义 |
|---|---|
| HARDWARE_ID | 具体硬件的不可变工厂身份；不决定 Home Assistant 设备身份 |
| NODE_ID | 一次获批节点归属的逻辑身份；决定业务主题、Discovery identifiers 和历史归属 |
| assignment | 一次 HARDWARE_ID、pairing_id、NODE_ID 与凭据 generation 的获批归属 |
| 维修/轮换 | 同一当前归属内恢复连接、更新 Wi-Fi、轮换凭据或重新授权，不结束 NODE_ID |
| 退役 | 操作员显式结束当前归属，并执行凭据、retained 状态和运行时状态清理 |
| 重新配对 | 已退役 HARDWARE_ID 使用新的配对会话重新进入系统并取得全新 NODE_ID |

## 3. 决策

### 3.1 身份不变量

1. NODE_ID 一经分配，只属于当次 assignment。
2. NODE_ID 退役后永久封存，不再分配给任何 HARDWARE_ID，包括原 HARDWARE_ID。
3. 更换主板必须走完整新配对流程并分配全新 NODE_ID。
4. 不提供跨硬件复用开关、逻辑位置豁免、私有身份豁免或人工强制复用入口。
5. 同一未退役硬件的 Wi-Fi 重配、凭据轮换、主机恢复和经授权维修可以保留当前 NODE_ID。
6. 已退役 HARDWARE_ID 可以重新配对，但必须使用新的 pairing_id、严格递增 pairing_epoch、
   全新凭据、更高 generation 和从未使用过的新 NODE_ID。

### 3.2 可靠退役顺序

1. SQLite 事务记录退役意图，关闭当前历史归属，把 NODE_ID 置为 `retiring` 并创建 outbox。
2. 撤销 MQTT client、role、ACL 和凭据生命周期。
3. tombstone 两个 Discovery 配置。
4. tombstone canonical telemetry、availability、diagnostic。
5. 清除 last_seen、availability、去重键和 Discovery 摘要缓存。
6. 只有凭据撤销和全部运行时清理均完成后，才完成 outbox，并把 NODE_ID 置为永久 `retired`。

所有外部步骤必须可安全重试。Manager 启动后必须继续处理未完成 outbox。

### 3.3 持久化防复活

`retiring` 和 `retired` 均拒绝：

- 旧节点 ingress；
- 匿名兼容客户端冒用旧 NODE_ID；
- Manager 重启时由旧 retained canonical telemetry 恢复；
- 新配对审批重新声明已使用过的 NODE_ID。

取消 `reusable` 不等于取消 NODE_ID lease；lease 是永久历史索引和防复活门禁。

### 3.4 已退役 HARDWARE_ID 重新配对

1. 上一 retirement outbox 必须完成，未完成时失败关闭。
2. pairing_id 必须全新，pairing_epoch 必须严格递增。
3. registration 可以进入新 pending 会话，但历史 pairing session、event、assignment、outbox 和撤销证据必须保留。
4. 审批必须选择从未出现在 lease 或历史表中的新 NODE_ID。
5. 凭据生命周期必须创建新 assignment；generation 高于该硬件历史最大值，不能覆盖旧撤销证据。

### 3.5 Home Assistant 历史

退役不删除 Home Assistant 已保存历史、长期统计或审计记录。新 assignment 使用新 NODE_ID，
形成新的设备身份和曲线。系统内不自动合并、别名迁移或重写历史。

## 4. 数据库迁移

- `node_id_leases.state` 从 `active/retiring/reusable` 迁移为 `active/retiring/retired`。
- 所有已有 `reusable` 行在单一 SQLite 事务中映射为 `retired`。
- 迁移保留 node_id、hardware_id、logical_location_id、retirement_id 和 updated_at，不删除历史行。
- credential lifecycle 从每 HARDWARE_ID 单行迁移为多 assignment 历史；旧行成为第一条 assignment。
- 任何迁移失败必须整体回滚，不能把旧 NODE_ID 暴露为可分配。

## 5. 接口变化

- 删除 `reuse_retired_node_id`、`private_identity_bound` 和 anonymous 状态驱动的复用路径。
- `logical_location_id` 继续用于位置审计，但不授权身份复用。
- 操作员 CLI 不再暴露任何 NODE_ID 复用参数。
- `observe_hello()` 对 retired HARDWARE_ID 检查上一 outbox：未完成拒绝，完成后允许更高 epoch 的新 pending。

## 6. 验证

必须覆盖：旧 `reusable` 数据迁移、跨硬件和同硬件旧 ID 永久拒绝、outbox 未完成时重新配对拒绝、
outbox 完成后新会话和新 ID 成功、多代凭据 generation、崩溃恢复、五个 tombstone、旧 retained state 防复活和旧凭据拒绝。
