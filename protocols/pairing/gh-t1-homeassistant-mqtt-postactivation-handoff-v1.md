# T1 Home Assistant MQTT Postactivation Handoff V1

状态：M2.4g-6a Draft

## 1. 目的

本协议把已经完成的 Broker Dynamic Security 身份激活、Home Assistant 官方 MQTT 重配置、自动后置检查和当前只读复核，收敛为一个可长期审计的私有交接包。

该交接包只证明：

- Broker 身份激活事务已经提交且未回退；
- Broker 当前身份、ACL、匿名兼容和 retained 状态复核通过；
- Home Assistant 仍使用同一 MQTT config entry，并已经切换到预期认证字段；
- discovery 保持开启，Home Assistant 容器运行正常；
- 当前只允许进入 manager 身份迁移的“准备阶段”。

它不授权 manager 迁移、节点凭据下发、服务重启、Home Assistant `.storage` 编辑或匿名关闭。

## 2. V0.5 阶段位置

本协议属于 H1/H3 与 N2 的交叉前置收口：

1. H1 已验证 Broker Dynamic Security 与系统身份；
2. Home Assistant 认证连接已完成，但不等同于 H3 凭据生命周期闭环；
3. manager 独立身份仍未迁移；
4. 真实节点长期凭据仍未下发；
5. 匿名兼容必须保留，匿名关闭仍是后续独立决策门。

因此交接包只能输出 `ready_for_manager_migration_preparation=true`，必须保持 `ready_for_manager_migration_apply=false`。

## 3. 输入材料

实现必须同时绑定以下材料：

- Broker 生产事务目录中唯一 `phase=committed` 的私有 journal；
- 原 Broker activation handoff 的私有 manifest；
- Home Assistant MQTT reconfigure handoff 的私有 manifest；
- 已保存的 Home Assistant postcheck 结果；
- 当前重新运行的 Home Assistant postcheck；
- 当前重新运行的 Broker postactivation audit；
- 预期 retained telemetry topic。

任何输入缺失、漂移、回退、权限不安全或复核失败都必须终止，不得生成成功交接包。

## 4. 必须通过的 Broker 证明

Broker 事务 journal 必须满足：

- schema 为 `gh.m2.t1-broker-identity-production-activation-journal/1`；
- `phase=committed`；
- `preserve_anonymous=true`；
- `anonymous_closure_enabled=false`；
- 普通输出不包含密钥或宿主机路径。

当前 Broker postactivation audit 必须满足：

- Dynamic Security plugin 和私有 state 文件存在；
- Home Assistant 正确身份可以读取 retained telemetry；
- 错误 Client ID 被拒绝；
- provisioning control 可用；
- bootstrap admin 已失效；
- 匿名 retained telemetry 仍可读；
- 匿名 control 被拒绝；
- 相关服务运行且 restart count 为零；
- 所有 checks 均为 true，`rollback_required=false`。

## 5. 必须通过的 Home Assistant 证明

Home Assistant handoff 必须继续保持：

- 官方 config-flow/UI 路径；
- `apply_enabled=false`；
- `operator_action_authorized=false`；
- 不允许直接编辑 `.storage`；
- expected retained topic 与本次交接一致。

保存的 postcheck 与当前重新运行的 postcheck 都必须满足：

- Broker、端口、用户名、密码和 Client ID 字段全部匹配；
- MQTT config entry 指纹不变；
- storage 已通过官方流程发生预期变化；
- discovery 未关闭；
- Home Assistant 容器运行正常且 restart count 为零；
- `reconfigure_verified=true`；
- `rollback_required=false`。

保存结果与当前结果的安全语义投影必须一致，不能只接受旧的成功文件而跳过实时复核。

## 6. 输出交接包

输出目录必须为 mode `0700`，文件必须为 mode `0600`。交接包至少包含：

- `broker-postactivation-audit.json`；
- `homeassistant-postcheck-supplied.json`；
- `homeassistant-postcheck-live.json`；
- `operator-runbook.txt`；
- `manifest.json`。

manifest 只记录 SHA-256、短指纹、相对文件名和安全状态，不记录 MQTT 密码、完整 Client ID、授权口令或输入绝对路径。

## 7. 状态合同

成功交接包必须固定输出：

```text
broker_identity_activated=true
homeassistant_authenticated=true
manager_identity_migrated=false
node_credentials_delivered=false
ready_for_manager_migration_preparation=true
ready_for_manager_migration_apply=false
operator_action_authorized=false
apply_enabled=false
current_services_modified=false
preserve_anonymous=true
anonymous_closure_enabled=false
direct_storage_edit_forbidden=true
```

阻断项必须至少包含：

```text
manager_identity_not_migrated
node_credentials_not_delivered
anonymous_closure_not_reviewed
```

## 8. 写入与运行边界

本工具只允许：

- 读取现有事务、handoff 和 postcheck 材料；
- 对当前 Broker 与 Home Assistant 执行既有只读审计；
- 在新的私有输出目录写入审计交接包。

本工具禁止：

- 修改或重启 Mosquitto、Home Assistant、greenhouse-manager 或节点；
- 创建、消费或复用生产授权；
- 修改 `.storage`；
- 写入 manager 或节点凭据；
- 删除任何历史事务、Stage、handoff、rollback、authorization 或 postcheck；
- 关闭匿名兼容。

## 9. 下一门

成功生成本交接包后，下一项工作是单独设计 manager 身份迁移的准备、一次性授权、执行、后置验证和回退状态机。manager 迁移不得与真实节点凭据下发或匿名关闭合并为同一次写操作。
