# gh-h3-node-async-persistence-contract-v1

## 1. 定位

本合同冻结 H3/N2 Stage 2C-3 节点侧异步执行、凭据 journal 和 MQTT profile 激活前置语义。它不授权实际持久化或生产 MQTT 切换。

## 2. 异步 operation

每次请求包含本地单调递增的非零 `operation_id`。同一时刻最多存在一个活动 operation。

阶段：

```text
idle
queued
discovering
waiting_selection
secure_pairing
ram_staged
persistence_prepared
mqtt_probing
completed
cancelled
failed
```

结果：

```text
none
success
busy
selection_required
cancelled
invalid_transition
discovery_failed
pairing_failed
persistence_failed
mqtt_probe_failed
```

快照只允许包含：operation ID、饱和递增的 state version、阶段、结果、节点状态码、错误码、候选数量、generation 和布尔标志。禁止包含任何秘密或凭据正文。

## 3. 调度合同

- mDNS、UDP、HTTP 和密码学闭环只能在独立 worker task 中执行；
- ESPHome 主循环只轮询状态快照；
- `active` 从请求成功入队开始，覆盖 queued 与 executing；
- 请求入队使用原子 compare-and-exchange，关闭 queue-to-task 状态竞争；
- worker 活跃时不得并发 prune、候选选择或 reset；
- worker 活跃时，公开状态读取只能访问主循环持有的固定快照，不得读取 worker 正在修改的客户端对象；
- worker 活跃时，网络结果只能暴露脱敏的 `in_progress` 状态；
- 队列满或 worker 活跃时，新请求失败关闭；
- STOP 必须能覆盖一个尚未消费的 RUN 命令；
- task 生命周期和 operation 生命周期必须使用独立状态；
- 取消为协作式，并受底层单次网络调用超时约束；
- 已成功完成的安全闭环优先于同时到达的迟到取消请求；
- `discovering` phase 必须与节点核心已经进入 DISCOVERING 的快照同时发布。

## 4. 凭据 journal

槽位：`A`、`B`。记录状态：`EMPTY`、`PREPARED`、`COMMITTED`、`INVALID`。

记录元数据：

- `schema_version = 1`；
- 与物理槽一致的 slot；
- state；
- 非零 generation；
- 64 位小写十六进制 payload digest。

提交规则：

1. candidate generation 严格大于 active generation；
2. candidate 写入非活动槽；
3. candidate 先进入 `PREPARED`；
4. MQTT profile 验证成功后才能进入 `COMMITTED`；
5. active marker 最后切换；
6. rollback 只允许在尚未 commit 的 prepared 状态，且不改变旧 active marker；
7. commit 后不得在同一合同实例 rollback 或再次 prepare；
8. 恢复时 marker、物理 slot、记录 slot、schema、state、generation 和 digest 必须精确一致；
9. marker 缺失时不得存在任何 COMMITTED 记录；
10. marker 缺失时最多允许一个 PREPARED 孤儿记录；
11. marker 有效时，另一槽的较低 COMMITTED generation 可视为旧基线；
12. 相同或更高 COMMITTED generation、双 PREPARED、过期 PREPARED 或其他歧义一律失败关闭；
13. generation 更高的单个 PREPARED 记录必须在恢复快照中显式暴露，供正式实现决定清理或继续验证。

## 5. MQTT profile 激活

顺序：

```text
unchanged
candidate_staged
probing
verified
activated
```

验证必须同时具备认证成功、订阅准备完成和受控 telemetry round trip。三项条件共有 8 种组合，只有全部为真可进入 `verified`。

验证失败只能 rollback，不能覆盖旧 active generation。rollback 只允许在 candidate staged、probing、verified 或 failed 阶段；进入 `activated` 后拒绝 rollback 和再次 stage。

## 6. Stage 2C-3 限制

本合同的 C++ 实现只运行内存模型，不调用正式存储或 MQTT mutation API。`ram_staged`、模型中的 `committed` 和 `activated` 均不得解释为真实 flash 持久化或生产 Broker 激活证据。
