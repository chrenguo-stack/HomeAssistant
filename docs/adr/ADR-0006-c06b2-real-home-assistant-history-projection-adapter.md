# ADR-0006：C06-B2 真实 Home Assistant 历史投影适配器

- 状态：已接受（C06-B2A/C06-B2B）；C06-B2C 真实隔离验收升版替换读回后继修复中
- 阶段：C06-B2B Recorder 升版替换预期值读回修复 / C06-B2C 重新验收
- C06-B2A 初始决策门：`D1-C06B2A-MQTT-RPC-PROTOCOL-HA-TARGET-LEDGER-AND-CUSTOM-INTEGRATION-STACKED-DRAFT-CREATION-20260803-01`
- C06-B2A 修复决策门：`D1-C06B2A-PR263-BLOCKER-REMEDIATION-EXACT-GITHUB-WRITE-CLOSURE-20260804-01`
- C06-B2B 实施决策门：`D1-C06B2B-REAL-MQTT-RPC-RECORDER-API-RUNTIME-WIRING-HOST-ONLY-STACKED-DRAFT-IMPLEMENTATION-20260804-01`
- C06-B2B 验收决策门：`D1-C06B2B-PR264-FINAL-READ-ONLY-REVIEW-AND-HOST-ONLY-ACCEPTANCE-20260804-01`
- C06-B2C 设计决策门：`D1-C06B2C-ISOLATED-REAL-MOSQUITTO-FULL-HOME-ASSISTANT-RECORDER-END-TO-END-DESIGN-DECISION-20260804-01`
- C06-B2C 实施决策门：`D1-C06B2C-ISOLATED-REAL-MOSQUITTO-FULL-HOME-ASSISTANT-RECORDER-END-TO-END-STACKED-DRAFT-IMPLEMENTATION-20260804-01`
- C06-B2C 初始精确堆叠基线：PR #264 HEAD `a55b59027cb58f471353983f092fede00ae85cd4`
- C06-B2B Recorder 屏障修复决策门：`D1-C06B2B-PR265-RECORDER-IMPORT-QUEUE-COMMIT-BARRIER-REAL-E2E-BLOCKER-SUCCESSOR-REPAIR-STACKED-DRAFT-IMPLEMENTATION-20260804-01`
- Recorder 屏障修复精确堆叠基线：PR #265 HEAD `8f7c8603c92eba4246cb3b0f7b15c914b19b0ff3`
- C06-B2B UTC 时间点读回修复决策门：`D1-C06B2B-PR266-RECORDER-READBACK-UTC-INSTANT-CANONICALIZATION-AND-FALSE-COMMIT-BARRIER-REMOVAL-REAL-E2E-SUCCESSOR-REPAIR-STACKED-DRAFT-IMPLEMENTATION-20260804-01`
- UTC 时间点读回修复精确堆叠基线：PR #266 HEAD `21f288c1c47f7801e21e77ada460c6353e371e14`
- C06-B2B 升版替换预期值读回修复决策门：`D1-C06B2B-PR267-RECORDER-REPLACEMENT-EXPECTED-VALUE-READBACK-POLLING-AND-MONOTONIC-FAILURE-EVIDENCE-REAL-E2E-SUCCESSOR-REPAIR-STACKED-DRAFT-IMPLEMENTATION-20260804-01`
- 升版替换预期值读回修复精确堆叠基线：PR #267 HEAD `4c29fced18e8d45cac78f71ec82112bcf65a8cef`

## 背景

C06-B1 已冻结 Manager 侧小时统计投影合同、稳定 `idempotency_key`、单调 `revision` 和投影哈希。C06-B2A 建立 Home Assistant 目标侧协议、单调账本、实体解析和 Recorder 抽象；C06-B2B 在默认关闭的前提下完成真实 MQTT RPC、Recorder 支持 API 和两端启动入口接线。

C06-B2C 仅验证上述代码能否在 GitHub Runner 的一次性隔离环境中形成真实闭环，不访问 T1，不修改生产 Broker、Home Assistant、Recorder 或 Manager 数据库，也不改变任何运行默认值。

PR #265 的真实隔离运行证明 Broker、完整 Home Assistant、临时 Recorder、正式 Manager 入口、MQTT Discovery、QoS 1 非保留请求和结果绑定均已实际工作，但 Recorder 导入后的读回返回 `retry/target_readback_incomplete`。该失败证据绑定运行 `30913737925`、Artifact `8894210396` 和 PR #265 精确 HEAD。

PR #266 按独立授权加入 `async_block_till_done()` 后，Host-Only 测试通过，但真实隔离运行 `30916480533` 仍返回相同 `retry/target_readback_incomplete`。失败 Artifact `8895322947` 绑定 PR #266 精确 HEAD `21f288c1c47f7801e21e77ada460c6353e371e14`，摘要为 `sha256:20aa46e06e5c16151a57b96fccf16c639a0cd530dbb3b34c4cd93ba8ba92ece7`；隔离容器、卷、网络和宿主端口仍完全清理。

进一步只读核验得到两个结论：

1. 请求 `sample_hour` 可使用 `2026-08-03T04:00:00.000Z`，而 Recorder 返回时间被旧适配器格式化为 `2026-08-03T04:00:00Z`。旧代码直接比较字符串，导致同一 UTC 时间点因小数秒表示不同而被错误过滤。
2. Home Assistant 2026.7.1 的 `async_block_till_done()` 在 Recorder 队列为空且事件 session 无待提交写入时可以立即返回；这不能对已被 Recorder 线程取走、由独立 session 处理的导入任务提供严格提交证明。因此不得继续把该调用描述为持久化提交屏障。

PR #267 移除虚假提交屏障并改用 UTC 时间点比较后，Host-Only 运行 `30919045360` 通过，真实隔离运行 `30919045339` 的首次写入、目标账本和 Recorder 精确读回均已 `verified`，证明原 `target_readback_incomplete` 阻塞已经消除。随后高 revision 替换返回非 `verified`，运行在 `phase_monotonic` 终止；失败 Artifact `8896337266` 绑定 PR #267 精确 HEAD `4c29fced18e8d45cac78f71ec82112bcf65a8cef`，摘要为 `sha256:c6627f39569a5adb5b15715db0af1ec6c3c086e50d41e93fb7d580d422bbd9be`，隔离资源仍完全清理。

根因是现有轮询只以目标键数量齐全为完成条件。升版替换时，旧 revision 的 statistic ID 和 UTC 小时仍完整存在，首次查询会返回键齐全但数值陈旧的旧行；旧代码因此提前停止轮询，随后外层 `verify_readback()` 才报告 `target_readback_mismatch`。持久化确认必须绑定本次导入的完整 `StatisticWrite` 预期值，而不能只绑定键和小时。

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
10. C06-B2C 测试发现运行代码缺陷时，以失败证据终止；不得在同一实施授权中继续修改 C06-B2B 运行代码。
11. 移除 PR #266 引入的 `async_block_till_done()` 调用及其超时、异常分类，不再将其声明为 Recorder 导入提交屏障。
12. 请求时间和 Recorder 返回时间必须分别解析成时区明确的 UTC `datetime`，随后按同一时间点比较；不得比较 RFC 3339 文本形式。
13. `Z`、`.000Z` 和 `+00:00` 等表示同一 UTC 时间点的合法形式必须匹配；相邻小时必须严格拒绝。
14. `StatisticReadback.start` 继续保留请求合同中的原始字符串，避免改变 MQTT RPC 和账本键合同；时间点判定只在适配器内部使用规范化 `datetime`。
15. 导入后的持久化确认以现有有限支持 API 读回轮询为准：只有目标 statistic ID、UTC 小时和 `mean/min/max` 全部精确读回，才允许目标账本转为 `verified`。
16. 保持统计 ID、`source="recorder"`、现有实体目标和支持的读回接口不变；不得改用 external statistics，也不得直接访问 Home Assistant 数据库。
17. 每次成功调用 `async_import_statistics()` 后，适配器必须保存该批完整 `StatisticWrite` 作为紧随其后的读回期望；读回请求的 statistic ID 与 UTC 小时必须和该批期望严格一致。
18. 每轮 Recorder 查询必须同时核对键、UTC 时间点、单位、`mean`、`min` 和 `max`。键齐全但值仍属于旧 revision 时必须继续轮询，不得提前返回。
19. 超时分类保持可诊断：从未得到完整键集时返回 `retry/target_readback_incomplete`；曾得到完整键集但数值持续陈旧时返回 `retry/target_readback_mismatch`。
20. 单调测试每个请求的实际响应或异常必须在断言前写入 `monotonic-attempt.json`；真实 E2E 失败时不得只留下通用 `AssertionError`。

## 只读复核后的强化约束

1. Home Assistant 侧必须携带并执行与 Manager 逐字节相同的完整小时投影 JSON Schema，不允许以部分手写校验替代。
2. 账本完整文档写入使用单一事务锁和 copy-on-write：持久化成功前不得发布新内存状态；保存失败时内存和 Store 都保持旧状态。
3. Store 根固定绑定 `storage_schema_version=2` 和配置的 `system_id`。加载时重新验证投影 Schema、键、revision、hash、UTC 时间戳、有限数值和已解析实体数据。
4. Manager 接受响应前必须同时绑定固定结果主题、SYSTEM_ID、`request_id`、`idempotency_key`、revision 和投影 hash。
5. 账本默认只保留 14 天前已经 verified 的记录，pending 永不自动清理；最大 20,000 条、最大序列化 128 MiB，超过边界时失败关闭。
6. `read()` 和 `snapshot()` 返回深拷贝，不得向调用者暴露内部可变投影对象。

## 目标账本单调规则

- 目标不存在：接受并原子保存 `pending`，完成写后精确读回后转为 `verified`。
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
6. 修复后重新运行同一真实隔离生命周期；只有首次写入、精确读回、幂等、升版、降版拒绝、同版冲突、HA 重启持久性和彻底清理全部通过，才能提出新的 C06-B2C 验收门。

## 升版替换预期值读回后继修复边界

后继 Draft 必须精确堆叠于 PR #267 HEAD `4c29fced18e8d45cac78f71ec82112bcf65a8cef`。相对该基线只允许修改：

- `host/homeassistant/custom_components/greenhouse_history/recorder_adapter.py`
- `host/greenhouse-manager/tests/runtime/test_c06b2b_runtime_wiring.py`
- `infra/compose/c06b2c-history-projection-e2e/verify.py`
- `tools/c06b2b_runtime_wiring_host_only_harness.py`
- `tools/c06b2c_isolated_e2e_evidence.py`
- `docs/adr/ADR-0006-c06b2-real-home-assistant-history-projection-adapter.md`
- `.github/workflows/c06b2b-runtime-wiring-ci.yml`
- `.github/workflows/c06b2c-isolated-e2e-ci.yml`
- `.github/workflows/c06b2a-ha-target-ledger-ci.yml`
- `.github/workflows/c06-history-replay-ci.yml`

Host-Only 测试必须验证：

- 首次查询返回旧 revision 完整键和值时不会结束轮询；
- 后续查询返回新 revision 预期值后才成功；
- 完整键但持续陈旧在超时后分类为 `target_readback_mismatch`；
- 持续缺键在超时后分类为 `target_readback_incomplete`；
- UTC 等价形式与相邻小时约束继续保持。

C06-B2C 必须在断言前持久化幂等、升版、降版和同版冲突的逐请求响应证据，并重新执行真实 Mosquitto、完整 Home Assistant、临时 Recorder、正式 Manager 入口、HA 重启持久性和彻底清理。

## 本阶段明确排除

- 不修改 PR #260 至 PR #267；既有失败证据保持不可改写。
- 除上述十文件后继修复边界外，不修改 Manager 或 Home Assistant 运行代码。
- 不访问或修改 T1、生产 Broker、生产 Home Assistant、生产 Recorder、生产 Manager 数据库、凭据、匿名模式、挂载或容器。
- 不创建部署包、生产授权包、生产执行包或物理执行链。
- 不将任何 PR 标记 Ready，不合并、不发布、不打标签、不部署、不激活版本。

## 后续阶段

升版替换预期值读回修复和 C06-B2C 重新验收通过后，仍需另行决策是否进入故障矩阵、候选集成验收或堆叠 PR 的合并规划；本修复授权本身不授予其中任何权限。
