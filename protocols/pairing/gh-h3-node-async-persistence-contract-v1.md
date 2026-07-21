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

快照只允许包含：operation ID、state version、阶段、结果、节点状态码、错误码、候选数量、generation 和布尔标志。禁止包含任何秘密或凭据正文。

## 3. 调度合同

- mDNS、UDP、HTTP 和密码学闭环只能在独立 worker task 中执行；
- ESPHome 主循环只轮询状态快照；
- worker 活跃时不得并发 prune、候选选择或 reset；
- 队列满或 worker 活跃时，新请求失败关闭；
- 取消为协作式，并受底层单次网络调用超时约束；
- 已成功完成的安全闭环优先于同时到达的迟到取消请求。

## 4. 凭据 journal

槽位：`A`、`B`。记录状态：`EMPTY`、`PREPARED`、`COMMITTED`、`INVALID`。

记录元数据：

- `schema_version = 1`；
- slot；
- state；
- 非零 generation；
- 64 位小写十六进制 payload digest。

提交规则：

1. candidate generation 严格大于 active generation；
2. candidate 写入非活动槽；
3. candidate 先进入 `PREPARED`；
4. MQTT profile 验证成功后才能进入 `COMMITTED`；
5. active marker 最后切换；
6. rollback 不改变旧 active marker；
7. 恢复时 marker、slot、state、generation 必须精确一致；
8. 歧义或更高 generation 冲突一律失败关闭。

## 5. MQTT profile 激活

顺序：

```text
unchanged
candidate_staged
probing
verified
activated
```

验证必须同时具备认证成功、订阅准备完成和受控 telemetry round trip。验证失败只能 rollback，不能覆盖旧 active generation。

## 6. Stage 2C-3 限制

本合同的 C++ 实现只运行内存模型，不调用正式存储或 MQTT mutation API。`ram_staged` 和模型中的 `committed` 均不得解释为真实 flash 持久化或生产 Broker 激活证据。
