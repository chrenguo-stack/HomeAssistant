# gh-t1-manager-identity-failure-diagnostic-v1

状态：M2.4g-6q Draft

## 目标

真实 T1 的 greenhouse-manager 身份迁移在授权领取后发生失败时，事务必须自动回滚，同时留下足以定位失败子阶段、但不包含凭据或敏感路径的诊断材料。

## 诊断文件

每个私有 production transaction workspace 可包含：

- `stage-progress.json`：当前或最后完成的 allowlisted 子阶段；
- `failure-diagnostic.json`：首次主迁移失败；
- `rollback-failure-diagnostic.json`：回滚过程失败，和主失败分开保存。

文件必须为普通文件、mode 0600，所在 transaction workspace 必须为私有目录。

## 允许的失败阶段

主迁移阶段：

- `adapter_prepare`
- `mutation_pipeline`
- `manager_recreate`
- `authenticated_identity`
- `ingress_subscription`
- `canonical_publication`
- `availability_publication`
- `discovery_publication`
- `reconnect`
- `existing_entities`
- `postactivation_pipeline`
- `postactivation_audit`

回滚阶段：

- `rollback_pipeline`
- `rollback_manager_recreate`
- `rollback_anonymous_path`
- `rollback_existing_entities`

不得写入任意自由文本阶段名。

## 允许的诊断字段

`failure-diagnostic.json` 和 `rollback-failure-diagnostic.json` 仅允许保存：

- schema；
- allowlisted `failed_stage`；
-固定 `failure_code`；
-异常类名称；
-是否为 rollback failure；
- UTC 时间；
- `exception_message_included=false`；
- `secret_values_included=false`；
- `path_values_redacted=true`。

不得保存异常 message、traceback、用户名、client ID、token、密码、密码文件内容、Compose/.env 内容、容器完整 ID或绝对敏感路径。

## 保留规则

1. 主迁移第一次失败写入后不得被外层 `mutation_pipeline` 或后续 rollback 覆盖；
2. rollback failure 必须写入独立文件；
3. journal 最终 phase 可以是 `rollback_completed`，但诊断文件必须继续保留原始失败子阶段；
4. 已消费授权不得因回滚成功而恢复或重放；
5. transaction、claimed authorization、rollback 与诊断材料在审计完成前不得删除。

## 只读诊断

只读 CLI 只能输出：

- journal 终态；
- 是否存在主失败/回滚失败诊断；
- allowlisted failure stage 与固定错误码；
- rollback 是否完成或 terminal；
- `secret_values_included=false` 与 `path_values_redacted=true`。

CLI 不得修改容器、Broker、Home Assistant、节点、retained state 或授权材料。

## 当前真实事务兼容

在本协议合入前生成的 legacy transaction 可能只有 `phase=rollback_completed`，没有 `failure-diagnostic.json`。CLI 必须明确返回 `failure_stage_available=false`，不得猜测失败原因。

## 安全边界

- 不关闭匿名；
- 不下发节点凭据；
- 不修改或重启 Mosquitto、Home Assistant 或节点；
- 本协议和实现合入本身不授权新的真实迁移；
- 下一次真实 6o 仍需要全新的 6e/6f/6i/6j/6k、两次精确操作员确认和 fresh rollback。
