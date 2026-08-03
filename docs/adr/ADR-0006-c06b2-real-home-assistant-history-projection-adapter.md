# ADR-0006：C06-B2 真实 Home Assistant 历史投影适配器

- 状态：提议
- 阶段：C06-B2A
- 决策门：`D1-C06B2A-MQTT-RPC-PROTOCOL-HA-TARGET-LEDGER-AND-CUSTOM-INTEGRATION-STACKED-DRAFT-CREATION-20260803-01`
- 堆叠基线：PR #262 精确 HEAD `0ec7bb3d17f08f6e26d475ce6f2a55e5bea39434`

## 背景

C06-B1 已冻结 Manager 侧小时统计投影合同、稳定 `idempotency_key`、单调 `revision` 和投影哈希。本阶段只建立真实 Home Assistant 目标侧的协议、单调账本与自定义集成骨架，不接入生产运行链，不访问 T1，不修改 Home Assistant 生产数据，也不激活任何新功能。

## 决策

1. Manager 与 Home Assistant 自定义集成之间采用专用 MQTT RPC。
2. 请求主题固定为：
   `gh/v1/{SYSTEM_ID}/out/homeassistant/history/projection`
3. 响应主题固定为：
   `gh/v1/{SYSTEM_ID}/ingress/homeassistant/history/projection/result`
4. 请求和响应必须使用 QoS 1、`retain=false`。
5. Home Assistant 目标侧维护独立的版本化单调账本，不能只依赖 Recorder 数据判断 `revision` 与 `projection_hash`。
6. 目标统计必须回填到由 MQTT Discovery `unique_id` 解析出的现有实体统计，不得静默创建第二条 external-statistic 曲线。
7. 禁止 Manager 直接写 Home Assistant 数据库。
8. C06-B2A 只提供纯 Python 协议、账本、实体解析和 Recorder 抽象；不连接真实 MQTT，不调用真实 Recorder，不修改 Manager 启动入口。
9. 所有新能力默认未激活。

## 目标账本单调规则

- 目标不存在：接受并保存 `pending`，完成写后读回后转为 `verified`。
- 同 revision、同 hash：若已 verified 且读回一致，则幂等成功；若 pending，则继续 reconciliation。
- 同 revision、不同 hash：`blocked/target_same_revision_hash_conflict`。
- 请求 revision 低于目标：`blocked/target_newer_revision`。
- 请求 revision 高于目标：仅当旧目标 verified 时可接受；旧目标 pending 时返回 `retry/prior_revision_pending`。

## 本阶段明确排除

- 不修改 PR #260、PR #261、PR #262。
- 不访问或修改 T1、生产 Broker、生产 Home Assistant、生产 Manager 数据库、凭据、匿名模式、挂载或容器。
- 不创建部署包、授权包、生产执行包或物理执行链。
- 不将任何 PR 标记 Ready，不合并、不发布、不打标签、不部署。

## 后续阶段

- C06-B2B：真实 MQTT bridge、Manager adapter、response router、有界 worker，仍默认关闭。
- C06-B2C：隔离 Mosquitto + 真实 Home Assistant Core + 临时 Recorder 的端到端验证。
