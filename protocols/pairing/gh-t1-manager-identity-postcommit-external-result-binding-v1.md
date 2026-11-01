# T1 Manager 提交后审计外部执行结果绑定 V1

状态：M2.4g-6x Draft

## 1. 修正目的

V70 真实生产执行结果位于独立私有文件，而不是 transaction workspace 内。提交后持续性审计必须显式接收该文件，不能假设执行结果与 journal 位于同一目录。

## 2. 强制输入

审计必须同时接收：

1. 已提交 transaction workspace；
2. 独立 production execution result 文件；
3. `system_id`、真实 `node_id` 和精确 Discovery topic。

Execution result 必须是 mode `0600` 的普通文件且不是 symlink，并与 journal 的 `transaction_id` 和 `authorization_id` 同时一致。

## 3. 成功绑定条件

Execution result 必须证明：

```text
authorization_claimed=true
authorization_consumed=true
production_execution_completed=true
postactivation_verified=true
manager_identity_migrated=true
greenhouse_manager_recreated=true
node_credentials_delivered=false
preserve_anonymous=true
anonymous_closure_enabled=false
```

同时必须继续证明 Manager runtime image preserved，且未完成 rollback。

## 4. 只读不变性

审计开始和结束时，必须分别计算独立 execution result 文件的 mode、UID、GID、大小和 SHA-256 指纹。任一字段变化均 fail closed。

该指纹仅用于进程内比较，不得写入普通输出。审计仍不得 claim 授权、执行生产事务、重启服务、发布 MQTT、修改 Home Assistant、下发节点凭据或关闭 anonymous。

## 5. 版本关系

本文件补充 `gh-t1-manager-identity-postcommit-continuity-audit-v1.md`。二者冲突时，以本文件的显式外部 execution result 绑定要求为准。
