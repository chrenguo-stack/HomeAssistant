# C-07：节点退役、永久身份封存与重新配对策略

## 已接受决策

- 配对会话、注册事件、assignment、NODE_ID 历史和 retirement outbox 不自动清理。
- 长时间离线只影响 availability，不自动触发退役。
- 退役只能由操作员显式发起，并通过 SQLite 事务写入 retired registration、历史映射、
  NODE_ID `retiring` lease 和可恢复 outbox。
- 外部清理按 outbox 幂等重试：先取得 Dynamic Security 撤销证据，再清除两个 Discovery retained 配置、
  canonical telemetry、availability、diagnostic，并清理 Manager 的 last_seen、availability、dedup 和 Discovery 缓存。
- Manager 启动后继续处理未完成 outbox；retained canonical 恢复受同一 lease 门禁约束。
- 凭据撤销和运行时清理全部完成后，NODE_ID 进入永久 `retired`，不再分配给任何 HARDWARE_ID。
- `retiring` 与 `retired` 均拒绝 ingress、匿名冒用和 retained canonical 恢复。
- 删除跨硬件复用、同位置复用、私有身份豁免和人工强制复用路径；`logical_location_id` 只用于审计。
- 已退役 HARDWARE_ID 只有在上一 outbox 完成后，才可使用新 pairing_id、严格递增 pairing_epoch、
  新凭据、更高 generation 和全新 NODE_ID 进入新 assignment。
- 历史 pairing session、registration event、旧 assignment、outbox 和撤销证据全部保留。
- Home Assistant 已保存历史不删除；新 NODE_ID 形成新设备和新曲线。

## 数据库状态

`node_id_leases.state`：

```text
active -> retiring -> retired
```

从旧数据库升级时，所有 `reusable` 原子迁移为 `retired`。不得删除 lease 或把旧 NODE_ID 恢复为未使用。

credential lifecycle 使用多 assignment 历史。同一 HARDWARE_ID 的旧 assignment 必须先 revoked，
随后才能以更高 generation 和新 NODE_ID 创建新 assignment；旧撤销记录保留。

## CLI

- `greenhouse-manager-node-retirement retire <hardware_id> --system-id <id>`
- `greenhouse-manager-node-retirement revoke-credentials <retirement_id>`
- `greenhouse-manager-node-retirement status <retirement_id>`
- `greenhouse-manager-node-retirement list`
- `greenhouse-manager-registration approve <hardware_id> <pairing_id> --node-id <new_id> --logical-location-id <id>`

registration CLI 不提供任何 NODE_ID 复用参数。

## 验证边界

自动化测试覆盖退役事务、永久 lease、数据库迁移、凭据撤销失败恢复、五个 retained tombstone、
内存状态清理、重启防复活、outbox 完成前重新配对拒绝、完成后同硬件新 assignment，以及旧 NODE_ID 永久拒绝。

隔离集成门继续验证真实 Mosquitto Dynamic Security 撤销、五个 retained tombstone、真实 Home Assistant
MQTT Discovery 实体删除和 Manager 重启防复活。该门只使用临时非生产凭据，不连接 T1、实板或生产服务。

退役可靠性机制自 0.4.95/0.4.96 起形成；永久身份封存和 retired HARDWARE_ID 新 assignment 自 0.4.97 起对齐。
