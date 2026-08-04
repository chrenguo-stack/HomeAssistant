# ADR-0006：C06-B2 真实 Home Assistant 历史投影适配器

- 状态：已接受（C06-B2A/C06-B2B）；C06-B2C 隔离验收实施中
- 阶段：C06-B2C
- C06-B2A 初始决策门：`D1-C06B2A-MQTT-RPC-PROTOCOL-HA-TARGET-LEDGER-AND-CUSTOM-INTEGRATION-STACKED-DRAFT-CREATION-20260803-01`
- C06-B2A 修复决策门：`D1-C06B2A-PR263-BLOCKER-REMEDIATION-EXACT-GITHUB-WRITE-CLOSURE-20260804-01`
- C06-B2B 实施决策门：`D1-C06B2B-REAL-MQTT-RPC-RECORDER-API-RUNTIME-WIRING-HOST-ONLY-STACKED-DRAFT-IMPLEMENTATION-20260804-01`
- C06-B2B 验收决策门：`D1-C06B2B-PR264-FINAL-READ-ONLY-REVIEW-AND-HOST-ONLY-ACCEPTANCE-20260804-01`
- C06-B2C 设计决策门：`D1-C06B2C-ISOLATED-REAL-MOSQUITTO-FULL-HOME-ASSISTANT-RECORDER-END-TO-END-DESIGN-DECISION-20260804-01`
- C06-B2C 实施决策门：`D1-C06B2C-ISOLATED-REAL-MOSQUITTO-FULL-HOME-ASSISTANT-RECORDER-END-TO-END-STACKED-DRAFT-IMPLEMENTATION-20260804-01`
- C06-B2C 精确堆叠基线：PR #264 HEAD `a55b59027cb58f471353983f092fede00ae85cd4`

## 背景

C06-B1 已冻结 Manager 侧小时统计投影合同、稳定 `idempotency_key`、单调 `revision` 和投影哈希。C06-B2A 建立了 Home Assistant 目标侧协议、单调账本、实体解析和 Recorder 抽象；C06-B2B 在默认关闭的前提下完成真实 MQTT RPC、Recorder 支持 API 和两端启动入口接线。

C06-B2C 只验证上述已接受代码在 GitHub Runner 的一次性隔离环境中能否形成真实闭环，不访问 T1，不修改生产 Broker、Home Assistant、Recorder 或 Manager 数据库，也不改变任何运行默认值。

## 决策

1. Manager 与 Home Assistant 自定义集成之间采用专用 MQTT RPC。
2. 请求主题固定为 `gh/v1/{SYSTEM_ID}/out/homeassistant/history/projection`。
3. 响应主题固定为 `gh/v1/{SYSTEM_ID}/ingress/homeassistant/history/projection/result`。
4. 请求和响应必须使用 QoS 1、`retain=false`。
5. Home Assistant 目标侧维护独立的版本化单调账本，不能只依赖 Recorder 数据判断 `revision` 与 `projection_hash`。
6. 目标统计必须回填到由 MQTT Discovery `unique_id` 解析出的现有实体统计，不得静默创建第二条 external-statistic 曲线。
7. 禁止 Manager 直接读写 Home Assistant 数据库。
8. Manager 和 Home Assistant 的 C06-B2 运行能力保持显式 opt-in，默认关闭。
9. C06-B2C 必须通过正式 Manager 程序入口、真实 Mosquitto、完整 Home Assistant Core、真实 MQTT Discovery 实体和临时 Recorder 验证闭环，不允许直接实例化两端 Adapter 冒充运行链。
10. C06-B2C 测试发现运行代码缺陷时，以失败证据终止；不得在同一实施授权中修改 C06-B2B 运行代码。

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

## C06-B2C 隔离验收合同

1. 每次运行生成唯一 Compose 项目名、随机临时 Broker 凭据、独立容器、卷和内部网络；不发布宿主机端口。
2. 测试顺序固定为：启动 Broker/HA → MQTT Discovery 创建目标实体 → 使用正式 Store API 初始化待执行投影 → 启动 MQTT 观察器 → 启动真实 Manager 入口 → 首次写入与精确读回 → 幂等和单调规则 → Home Assistant 重启持久性 → 删除容器、卷和网络。
3. Recorder 验证只通过 Home Assistant 支持的统计查询 API，不读取 SQLite，不将 Recorder 数据库放入证据包。
4. 证据必须记录镜像标签和运行时解析的镜像标识、请求/结果 QoS 与 retain、Manager 完成状态、目标账本状态、Recorder 精确读回、重启结果和清理结果。
5. Artifact 不得包含 Broker 密码、`.storage` 原文件、Recorder 数据库、Manager 数据库、完整目标账本、容器环境变量或生产配置。

## 本阶段明确排除

- 不修改 PR #260、PR #261、PR #262、PR #263 或 PR #264。
- 不修改 `host/greenhouse-manager/src/**` 或 `host/homeassistant/custom_components/greenhouse_history/**`。
- 不访问或修改 T1、生产 Broker、生产 Home Assistant、生产 Recorder、生产 Manager 数据库、凭据、匿名模式、挂载或容器。
- 不创建部署包、生产授权包、生产执行包或物理执行链。
- 不将任何 PR 标记 Ready，不合并、不发布、不打标签、不部署、不激活版本。

## 后续阶段

C06-B2C 通过后，仍需另行决策是否进入故障矩阵、候选集成验收或堆叠 PR 的合并规划；C06-B2C 本身不授予其中任何权限。
