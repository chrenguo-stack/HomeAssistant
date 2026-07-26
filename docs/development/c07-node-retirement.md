# C-07：节点退役与配对记录保留策略

## 2026-07-26 架构更新

ADR-0003 已接受新的产品身份规则：

- NODE_ID 只属于一次 `hardware_id -> node_id` 归属，退役后永久封存；
- 不再允许 NODE_ID 跨 hardware_id 复用，logical_location_id 和私有身份
  证明都不能形成例外；
- 已退役 hardware_id 在上一退役 outbox 完成后可以重新配对，但必须使用
  新 pairing_id、严格递增 epoch、新凭据和全新 NODE_ID；
- C-07 已实现并验收的 outbox、凭据撤销、五个 retained tombstone、
  持久化 ingress 门禁、内存清理和重启恢复全部保留。

截至 Manager 0.4.96，代码仍以 `reusable` 表示退役清理后的 NODE_ID，并在
严格条件下保留跨硬件复用底层路径，同时拒绝 retired hardware 重新配对。
这是明确的实现对齐待办，不能把 ADR-0003 的目标规则表述为当前已实现。

## 已实现并继续保留的可靠性决策

- 配对会话和注册事件不设自动过期或清理策略；历史 pairing session
  保持原事件状态，当前 registration 通过持久化 retired_at 表示 retired 终态。
- 长时间离线只影响 availability，不会自动触发退役。
- 退役只能由操作员显式发起，并通过 SQLite 事务写入：
  `retired` 终态、历史 `hardware_id -> node_id` 映射、NODE_ID
  `retiring` 租约以及可恢复的 retirement outbox。
- 外部清理通过 outbox 重试：先取得节点 Dynamic Security
  client/role 撤销证据，再清除两个 HA Discovery retained 配置和 canonical
  telemetry、availability、diagnostic retained 状态，并清理 Manager
  的 last_seen、availability、dedup 和 Discovery 缓存。
- Manager 仅处理已有凭据撤销证据的运行时清理任务；即使配对 intake
  已关闭，只要注册数据库存在，未完成 outbox 仍会在启动后继续处理。
- retained canonical 恢复同样受 NODE_ID lease 门禁约束，退役节点不能在
  Manager 重启后通过旧 retained 状态重新创建 HA Discovery。
- 当前 0.4.96 只有在凭据撤销与运行时清理均完成后才把租约推进到
  `reusable`。ADR-0003 要求实现迁移时把该终态改为永久
  `retired`/`non_reusable`，但仍保留持久化租约作为 ingress 和 retained
  恢复门禁。

## CLI

- `greenhouse-manager-node-retirement retire <hardware_id> --system-id <id>`
- `greenhouse-manager-node-retirement revoke-credentials <retirement_id>`
- `greenhouse-manager-node-retirement status <retirement_id>`
- `greenhouse-manager-node-retirement list`

`retire` 默认尝试撤销凭据；无法访问 provisioning 身份时操作安全地
停留在 outbox 中，NODE_ID 保持不可复用。Manager 会幂等重试 retained
tombstone 和内存清理。

新的注册审批必须通过
`greenhouse-manager-registration approve ... --logical-location-id <id>`
记录逻辑监测位置。该值可以继续作为稳定、可审计的位置标识，但 ADR-0003
禁止使用它授权 NODE_ID 复用。

## 验证边界

自动化测试覆盖退役事务、审计历史、NODE_ID 租约状态机、凭据撤销失败恢复、
Dynamic Security 幂等清理、五个 retained tombstone、内存状态清理，以及
Manager 重启时阻止退役节点由旧 retained canonical telemetry 重新出现。

正式收口还由隔离集成门验证真实 Mosquitto Dynamic Security 撤销、
五个 retained tombstone、真实 Home Assistant MQTT Discovery 实体删除，
以及 Manager 重启后旧 retained canonical telemetry 不会复活实体。该门
只使用临时非生产凭据，不连接 T1、实板或生产服务。

退役核心合同自 `greenhouse-manager` 0.4.95 起实现；逻辑位置与匿名兼容
硬门及隔离闭环自 0.4.96 起实现。

ADR-0003 的 NODE_ID 永久封存和 retired hardware 新身份重配尚未实现；
后续代码变更必须继续通过本节既有的真实隔离退役闭环。
