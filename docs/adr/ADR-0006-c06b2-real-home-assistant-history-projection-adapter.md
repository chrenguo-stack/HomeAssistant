# ADR-0006：C06-B2 真实 Home Assistant 历史投影适配器

- 状态：提议
- 阶段：C06-B2A
- 初始决策门：`D1-C06B2A-MQTT-RPC-PROTOCOL-HA-TARGET-LEDGER-AND-CUSTOM-INTEGRATION-STACKED-DRAFT-CREATION-20260803-01`
- 修复决策门：`D1-C06B2A-PR263-BLOCKER-REMEDIATION-EXACT-GITHUB-WRITE-CLOSURE-20260804-01`
- 堆叠基线：PR #262 精确 HEAD `0ec7bb3d17f08f6e26d475ce6f2a55e5bea39434`

## 背景

C06-B1 已冻结 Manager 侧小时统计投影合同、稳定 `idempotency_key`、单调 `revision` 和投影哈希。本阶段只建立真实 Home Assistant 目标侧的协议、单调账本与自定义集成骨架，不接入生产运行链，不访问 T1，不修改 Home Assistant 生产数据，也不激活任何新功能。

## 决策

1. Manager 与 Home Assistant 自定义集成之间采用专用 MQTT RPC。
2. 请求主题固定为 `gh/v1/{SYSTEM_ID}/out/homeassistant/history/projection`。
3. 响应主题固定为 `gh/v1/{SYSTEM_ID}/ingress/homeassistant/history/projection/result`。
4. 请求和响应必须使用 QoS 1、`retain=false`。
5. Home Assistant 目标侧维护独立的版本化单调账本，不能只依赖 Recorder 数据判断 `revision` 与 `projection_hash`。
6. 目标统计必须回填到由 MQTT Discovery `unique_id` 解析出的现有实体统计，不得静默创建第二条 external-statistic 曲线。
7. 禁止 Manager 直接写 Home Assistant 数据库。
8. C06-B2A 只提供纯 Python 协议、账本、实体解析和 Recorder 抽象；不连接真实 MQTT，不调用真实 Recorder，不修改 Manager 启动入口。
9. 所有新能力默认未激活。

## 只读复核后的强化约束

1. Home Assistant 侧必须携带并执行与 Manager 逐字节相同的完整小时投影 JSON Schema，不允许以部分手写校验替代。
2. 账本完整文档写入使用单一事务锁和 copy-on-write：持久化成功前不得发布新内存状态；保存失败时内存和 Store 都保持旧状态。
3. Store 根固定绑定 `storage_schema_version=2` 和配置的 `system_id`。加载时重新验证投影 Schema、键、revision、hash、UTC 时间戳、有限数值和已解析实体数据。
4. Manager 接受响应前必须同时绑定固定结果主题、SYSTEM_ID、`request_id`、`idempotency_key`、revision 和投影 hash。
5. 账本默认只保留 14 天前已经 verified 的记录，pending 永不自动清理；最大 20,000 条、最大序列化 128 MiB，超过边界时失败关闭。
6. `read()` 和 `snapshot()` 返回深拷贝，不得向调用者暴露内部可变投影对象。

## 目标账本单调规则

- 目标不存在：接受并原子保存 `pending`，完成写后读回后转为 `verified`。
- 同 revision、同 hash：若已 verified 则幂等成功；若 pending 则继续 reconciliation。
- 同 revision、不同 hash：`blocked/target_same_revision_hash_conflict`。
- 请求 revision 低于目标：`blocked/target_newer_revision`。
- 请求 revision 高于目标：仅当旧目标 verified 时可接受；旧目标 pending 时返回 `retry/prior_revision_pending`。
- 安全清理后仍超过容量：`blocked/target_ledger_capacity_exceeded`。

## 本阶段明确排除

- 不修改 PR #260、PR #261、PR #262。
- 不访问或修改 T1、生产 Broker、生产 Home Assistant、生产 Manager 数据库、凭据、匿名模式、挂载或容器。
- 不创建部署包、授权包、生产执行包或物理执行链。
- 不将任何 PR 标记 Ready，不合并、不发布、不打标签、不部署。

## 后续阶段

- C06-B2B：真实 MQTT bridge、Manager adapter、response router、有界 worker，仍默认关闭。
- C06-B2C：隔离 Mosquitto、真实 Home Assistant Core 和临时 Recorder 的端到端验证。
