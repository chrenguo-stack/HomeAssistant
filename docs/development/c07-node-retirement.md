# C-07：节点退役与配对记录保留策略

## 已接受决策

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
- 只有凭据撤销与运行时清理均完成后，NODE_ID 才进入
  `reusable`；分配给不同 hardware_id 时还必须显式声明复用、提交与
  旧租约完全一致的 `logical_location_id`，并确认新硬件已绑定可强制
  执行的私有身份。逻辑位置同时写入 registration、NODE_ID lease、
  历史映射、retirement outbox 和无秘密审计事件。
- 缺少历史逻辑位置证据的旧 NODE_ID 一律失败关闭，不得推断或补猜。
- 匿名兼容入口仍可冒充 NODE_ID 时，代码硬门禁止跨 hardware_id
  复用；`greenhouse-manager-registration` 不提供关闭该门的命令行参数，
  即使同时传入 `--reuse-retired-node-id` 与
  `--private-identity-bound` 也会拒绝。未来只有能够以实际 Broker
  隔离证据建立可信调用上下文的管理入口，才可在匿名入口已关闭后调用
  底层复用事务。

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
记录逻辑监测位置。该值不是地址文本或用户显示名称，而是稳定、可审计的
位置标识；主板更换时必须原值匹配。

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
