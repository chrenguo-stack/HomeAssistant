# gh-t1-broker-identity-activation-transaction-v1

## 1. 状态与范围

状态：Draft / M2.4g-5d（禁用的事务协调器）  
关联：Issue #17、M2.4g-5a handoff、M2.4g-5b preactivation/postaudit、M2.4g-5c authorization

本协议定义 Broker 身份激活的事务状态机、一次性授权消费、后置审计和强制回退契约。当前版本只提供可测试的协调器和只读 plan CLI；生产 mutation、postactivation adapter 与 rollback adapter 均未接入，因此真实 T1 执行仍被硬性禁用。

当前 CLI 只能验证 transaction plan，并必须输出：

```text
production_executor_available = false
execution_enabled = false
apply_enabled = false
ready_for_live_activation = false
current_services_modified = false
preserve_anonymous = true
anonymous_closure_enabled = false
```

本阶段不得向操作员提供 live apply 命令。

## 2. 事务前置条件

协调器在任何授权消费和活动路径写入前必须同时验证：

1. M2.4g-5c authorization 当前有效、未消费、单次使用且已明确授权；
2. authorization 与 handoff、stage、Broker target、MQTT entry、Home Assistant `.storage` 和 retained topic 指纹完全匹配；
3. disabled preactivation gate 再次通过；
4. 匿名兼容仍存在；
5. Dynamic Security 尚未激活；
6. handoff fresh rollback 与指纹绑定仍有效；
7. mutation、postactivation 和 rollback 三个 executor 全部显式安装；
8. 调用者显式传入 `execution_enabled=true`。

缺少任一 executor 或 execution flag 时，必须在授权 claim 之前失败。

## 3. 一次性授权 claim

授权消费采用同目录、确定名称的原子 claim：

```text
broker-activation-authorization-<id>.json
→ claimed-<id>.json
```

要求：

- 原授权文件与 claim 文件均为 `0600`；
- 使用硬链接排他创建 claim，claim 已存在即拒绝；
- claim 成功后删除未消费文件名；
- 对 claim 文件重新执行完整授权验证；
- 之后原子写入 `consumed=true`、`consumed_at` 和 `transaction_id`；
- 授权一经 claim，不因事务成功、失败或回退而恢复为未消费；
- 并发调用最多只能有一个成功取得确定 claim 名称。

若进程在 claim 中断，系统必须失败关闭，并保留 claim 材料供人工审计，不得自动重放。

## 4. 私有事务日志

每次事务创建 `0600` 私有 JSON journal，不记录密码、token、MQTT payload 或 Dynamic Security 请求原文。

最小阶段：

1. `authorization_claimed`
2. `mutation_requested`
3. `mutation_completed`
4. `completed`

失败阶段：

- `failed_before_mutation`
- `rollback_requested`
- `rolled_back`
- `rollback_failed`

日志必须记录：transaction ID、authorization ID、handoff 名称、授权 claim 文件名、mutation 是否已开始、postactivation 是否通过、rollback 是否尝试和完成。

## 5. Executor 契约

### 5.1 Mutation executor

一旦进入 mutation executor，协调器按“可能已经修改活动系统”处理；任何异常都必须触发 rollback，不允许依赖异常类型判断是否已经写入。

成功报告必须包含：

```text
mutation_started = true
mosquitto_restarted = true
bootstrap_admin_removed = true
provisioning_identity_verified = true
preserve_anonymous = true
anonymous_closure_enabled = false
```

### 5.2 Postactivation auditor

Mutation 成功后必须立即执行 M2.4g-5b postactivation audit。成功报告必须包含：

```text
activation_verified = true
rollback_required = false
broker_identity_activated = true
ready_for_homeassistant_reconfigure_handoff = true
preserve_anonymous = true
anonymous_closure_enabled = false
```

所有 `checks` 必须为 true，否则进入 rollback。

### 5.3 Rollback executor

任何 mutation 异常、mutation 契约不完整、postactivation 失败或 postactivation 契约不完整，都必须执行 fresh rollback。成功报告必须包含：

```text
rollback_completed = true
baseline_config_restored = true
dynamic_security_state_absent = true
anonymous_retained_state_readable = true
```

回退报告不完整视为 rollback failure，不得伪装为已恢复。

## 6. 当前实现边界

当前协调器的生产执行入口故意缺失：

- CLI 仅构建 plan；
- `execute_activation_transaction()` 默认 `execution_enabled=false`；
- mutation、postactivation 和 rollback executor 默认均为 `None`；
- 只有单元测试通过显式注入模拟 executor 才能覆盖成功和故障状态机；
- 代码合并不等于允许真实 T1 执行。

## 7. 进入下一门的条件

在提供真实 T1 live gate 前，至少还需完成：

1. 独立 production mutation adapter；
2. crash-safe fresh rollback adapter；
3. 与既有 postactivation audit 的正式适配；
4. 隔离 Docker 快照中的成功演练；
5. mutation 中断、Mosquitto 重启失败、Dynamic Security 初始化失败、bootstrap 删除失败、postaudit 失败和 rollback 失败的故障注入；
6. 确认 Home Assistant 与 greenhouse-manager 未被重启或修改；
7. 新的精确 main、handoff、stage、entry 和 `.storage` 指纹门禁。

在上述条件完成前，真实 T1 继续保持禁止直接应用迁移。
