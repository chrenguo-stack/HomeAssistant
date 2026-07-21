# H3/N2 Stage 2C-3 异步执行与持久化前置设计

**基线：** `main = 7ea896b66ba4669f1baabbd8f622167142111d99`  
**开发分支：** `feature/h3-n2-stage2c3-async-persistence-contract-20260721-v48`  
**范围：** ESP32-C6 非生产异步配对执行、凭据双槽合同、MQTT 原子激活合同

## 1. 本阶段目标

Stage 2C-3 在 Stage 2C-2 同步网络与安全通道之上增加：

- 独立 FreeRTOS 配对 worker；
- 长度为 1 的命令队列与最新快照队列；
- 单次 operation ID、明确 phase/outcome、繁忙拒绝和协作取消；
- ESPHome 主循环只轮询脱敏快照，不直接执行 mDNS、UDP、HTTP 或密码学闭环；
- 双槽凭据 journal 的纯合同模型；
- 候选 MQTT profile 的探测、验证、激活和回滚纯合同模型；
- 最小板与完整产品板非生产编译目标。

## 2. 异步 worker 边界

`PairingAsyncWorker` 具备以下限制：

- 一个 worker task；
- 一个待执行命令；
- 一个最新状态快照；
- operation ID 必须单调递增且非零；
- `active` 从请求成功入队开始，覆盖排队和执行两个阶段；
- 使用原子 compare-and-exchange 拒绝并发请求，关闭“已入队但 task 尚未接收”窗口；
- worker 活跃时拒绝新的配对请求、候选选择和 reset；
- 多 Manager 仍返回 `selection_required`，选择动作只能在 worker 空闲时执行；
- STOP 使用队列覆盖写入，避免待执行 RUN 阻塞关闭命令；
- worker 运行状态与请求活动状态分别维护，避免 task handle 跨任务竞争；
- 状态版本递增采用饱和语义，不允许整数回绕；
- 状态快照不包含 pairing secret、方向密钥、MQTT 密码或凭据正文。

当前取消为协作式：在发现阶段和安全闭环边界检查取消标志；正在执行的单个底层网络调用依靠 Stage 2C-2 的超时上限返回。默认关闭等待预算为 45 秒，覆盖 mDNS、UDP 重试和四次 HTTP 上限的保守组合。成功完成的闭环不因最后时刻到达的取消请求被错误回滚。

## 3. ESPHome 调度模型

Stage 2C-3 使用独立的 `greenhouse_pairing_async_lab` 组件包装 Stage 2C-2 客户端：

- 内部客户端只在 worker task 中执行发现与安全闭环；
- worker 活跃时不从 ESPHome `loop()` 调用内部客户端；
- 主循环只接收固定结构的脱敏快照；
- `discovering` phase 仅在内部客户端已进入 DISCOVERING 状态后发布；
- 配对不会在开机时自动发起；
- 实验按钮仅为后续隔离实板验收准备，默认不触发。

现有生产 RC2 YAML 和 Stage 2C-2 组件显式配置接口保持不变。底层组件新增的空配置路径只用于 Stage 2C-3 作为 C++ 库自动加载，非空实例仍执行原有严格校验。

## 4. 双槽凭据 journal 合同

`CredentialPersistenceContract` 只定义元数据，不调用任何 flash 或 NVS API。

冻结规则：

1. active slot 为 `A`、`B` 或空，非法枚举失败关闭；
2. 新 generation 必须严格大于 active generation；
3. 候选写入非活动槽并标记 `PREPARED`；
4. payload 仅以 64 位小写十六进制摘要进入合同；
5. MQTT profile 验证成功前不得提交；
6. 提交后才允许切换 active marker；
7. commit 后不得执行合同 rollback，也不得在同一合同实例继续 prepare；
8. 恢复时物理槽位与记录内 slot、schema、state、generation、digest 必须一致；
9. active marker 必须与一个有效 `COMMITTED` 槽精确匹配；
10. 另一槽存在相同或更高 committed generation 时失败关闭；
11. 另一槽存在更低 committed generation 时视为旧基线，可恢复当前 active；
12. 最多允许一个 generation 更高的 `PREPARED` 孤儿记录，并在恢复快照中显式暴露以供后续清理；
13. 双 PREPARED、过期 PREPARED、无 marker 的 COMMITTED 或其他歧义状态均失败关闭；
14. rollback 仅清除尚未 commit 的候选元数据，不改变现有 active generation。

正式实现仍需补充加密存储、CRC/认证标签、原子 marker 写入、掉电测试和擦写寿命策略。

## 5. MQTT 原子激活合同

`MqttActivationContract` 只建模状态，不调用正式 MQTT setter 或连接器。

状态顺序：

```text
UNCHANGED
→ CANDIDATE_STAGED
→ PROBING
→ VERIFIED
→ ACTIVATED
```

候选 profile 只有同时满足以下条件才可验证：

- 认证成功；
- 订阅准备完成；
- 至少一次受控 telemetry round trip 成功。

任一条件失败进入 `FAILED`，随后只能 rollback；旧 active generation 在激活前始终保持不变。rollback 仅允许在 candidate staged、probing、verified 或 failed 阶段；进入 `ACTIVATED` 后拒绝 rollback 和再次 stage，避免把已激活 generation 伪装成未变更状态。

## 6. 明确禁止范围

本阶段不得：

- 调用正式 NVS 写入或 commit API；
- 写 Preferences、文件系统或 flash；
- 调用正式 MQTT username/password setter；
- 替换当前 MQTT profile；
- 自动发起真实配对；
- 使用真实 Wi-Fi、Broker、Manager 或节点凭据；
- 修改生产 RC2 YAML；
- 修改 M401A、T1、Home Assistant 或真实 Broker；
- 将模拟、合同测试或编译结果表述为实板验收。

## 7. 验收门

- host C++ async、journal、MQTT activation 基础合同测试；
- 独立 fail-closed 故障矩阵，覆盖 async 非法迁移、journal 恢复歧义及 MQTT 探测的全部 8 种布尔组合；
- FreeRTOS worker 和异步 wrapper 的 ESP32-C6 编译；
- 最小目标 ESPHome config/compile；
- 完整 RC2 产品板非生产目标 config/compile；
- 临时 secrets 不出现在日志；
- 源码扫描确认不存在正式持久化和 MQTT mutation；
- 公共仓库安全门和既有 Stage 2B/2C 回归通过。

达到这些门后，Stage 2C-3 仍只代表异步执行与持久化前置合同完成。正式 NVS 与 MQTT profile 切换必须在后续阶段单独授权和验收。
