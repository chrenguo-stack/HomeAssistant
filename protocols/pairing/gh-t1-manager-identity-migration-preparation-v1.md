# T1 Manager Identity Migration Preparation V1

状态：M2.4g-6b Draft

## 1. 目的

本协议在 Broker Dynamic Security 身份激活和 Home Assistant 认证迁移已经通过后，把 `greenhouse-manager` 独立 MQTT 身份迁移所需的现有证据、inactive Stage、实时容器身份、Compose 来源和凭据材料收敛为一个私有、不可执行的准备包。

本阶段只回答“是否具备进入 manager 一次性授权设计的条件”，不授权真实迁移，也不修改任何运行服务。

## 2. V0.5 阶段位置

本协议属于 H1/H3 与 N2 的交叉前置工作：

- Broker 身份与 Home Assistant 认证连接已经完成；
- manager 仍使用迁移前连接方式；
- 真实节点长期凭据尚未下发；
- 匿名兼容仍必须保留；
- H3 和 N2 均不得在本阶段标记完成。

因此成功结果只能输出：

```text
ready_for_manager_migration_authorization=true
ready_for_manager_migration_apply=false
manager_identity_migrated=false
node_credentials_delivered=false
```

## 3. 输入

必须同时绑定：

1. `gh.m2.t1-homeassistant-mqtt-postactivation-handoff/1` 私有交接包；
2. 已验证且未启用的 `gh.m2.t1-auth-migration-stage/1`；
3. Stage 中的 manager 环境、密码和 Compose overlay 材料；
4. 当前运行的 `greenhouse-manager` 容器身份；
5. 当前 Compose project、working directory 和有序配置文件清单；
6. 当前 `.env` 状态；
7. 预期 retained telemetry Topic；
8. 规划中的 active secret root。
9. 若本轮用于替代一次已人工复核的 legacy rollback，则必须额外输入并完整验证
   `gh.m2.t1-manager-identity-legacy-review-bridge/1` 私有桥接目录。

任何材料缺失、漂移、权限不安全或状态不一致均必须终止。

legacy review bridge 只允许解除旧事务的 manual-review 阻断。新准备包必须绑定
bridge manifest SHA-256、records 集合 SHA-256 和目录名短指纹，并继续固定：

```text
rollback_audit_passed=false
manual_review_resolved=true
future_baseline_waiver_enabled=false
ready_for_production_execution=false
```

它不得替代本轮实时 Manager/Compose 绑定，也不得豁免后续 fresh rollback。

## 4. 前置交接验证

postactivation handoff 必须保持：

```text
broker_identity_activated=true
homeassistant_authenticated=true
manager_identity_migrated=false
node_credentials_delivered=false
ready_for_manager_migration_preparation=true
ready_for_manager_migration_apply=false
preserve_anonymous=true
anonymous_closure_enabled=false
legacy_review_bridge_bound=true  # 仅 legacy rollback 替代链
future_baseline_waiver_enabled=false
```

其 records 必须全部使用 mode `0600`，并通过 size 与 SHA-256 校验。普通输出不得含密钥或输入路径。

## 5. inactive Stage 验证

Stage 必须通过完整 inventory、权限和 SHA-256 校验。`activation-plan.json` 必须固定：

```text
activation_enabled=false
current_services_modified=false
active_paths_modified=false
requires_explicit_gate=true
requires_fresh_backup_immediately_before_apply=true
preserve_anonymous=true
anonymous_closure_enabled=false
```

Stage retained Topic 与本次输入必须一致。

## 6. Manager 凭据材料

`payload/manager/manager.env` 只允许：

```text
GH_MQTT_USERNAME
GH_MQTT_PASSWORD_FILE=/run/secrets/gh_manager_mqtt_password
GH_MQTT_CLIENT_ID
```

禁止 inline `GH_MQTT_PASSWORD`。密码文件必须为 mode `0600`、非符号链接、UTF-8 单行非空内容。

Compose fragment 必须与环境材料完全一致，并固定只读挂载：

```text
source=/opt/greenhouse-secrets/mqtt/manager/password
target=/run/secrets/gh_manager_mqtt_password
read_only=true
```

## 7. 实时 Manager 与 Compose 绑定

只允许执行：

```text
docker inspect greenhouse-manager
```

必须验证：

- 容器状态为 running；
- restart count 为 0；
- 容器 ID、镜像 ID、镜像引用和启动时间完整；
- 当前尚未配置非空 `GH_MQTT_USERNAME`、`GH_MQTT_PASSWORD` 或 `GH_MQTT_PASSWORD_FILE`；
- 当前 Client ID 若存在，只能记录短指纹；
- Compose project、working directory 和 config files 标签完整；
- 当前配置文件与 Stage baseline 的路径、顺序和 SHA-256 一致；
- `.env` 若存在必须为 mode `0600`，并与 Stage baseline 一致。

准备工具不得调用 `docker exec`、restart、stop、create、Compose、systemd 或 SSH。

## 8. 输出准备包

输出目录必须为 mode `0700`，内部文件必须为 mode `0600`。至少包含：

- `material/manager/manager.env`；
- `material/manager/password`；
- `material/manager/compose-secret-fragment.yaml`；
- `manager-runtime-binding.json`；
- `transaction-plan.json`；
- `operator-runbook.txt`；
- `manifest.json`。

私有 runtime binding 可以记录后续事务所需的真实路径和完整本机绑定，但普通 JSON 报告只允许输出名称、状态、SHA-256 和短指纹，不得泄露用户名、密码、完整 Client ID 或宿主机路径。

## 9. 后续事务合同

本阶段只冻结后续顺序，不实现执行入口：

1. 刷新 postactivation 与 manager runtime 绑定；
2. 创建 fresh manager Compose/secret rollback；
3. 创建短时、单次、全指纹绑定的操作员授权；
4. 原子写入 manager password；
5. 应用精确 manager Compose overlay；
6. 只重建或重启 `greenhouse-manager`；
7. 验证认证 Client ID、ingress 订阅、canonical/Discovery 发布和重连；
8. 任一失败执行完整回退。

禁止在同一事务中修改 Mosquitto、Home Assistant、节点凭据或匿名模式。

## 10. 成功状态合同

```text
prepared=true
read_only_live_services=true
current_services_modified=false
apply_enabled=false
operator_action_authorized=false
broker_identity_activated=true
homeassistant_authenticated=true
manager_identity_migrated=false
node_credentials_delivered=false
ready_for_manager_migration_authorization=true
ready_for_manager_migration_apply=false
preserve_anonymous=true
anonymous_closure_enabled=false
```

阻断项至少包括：

```text
manager_operator_authorization_required
manager_live_execution_not_implemented
node_credentials_not_delivered
anonymous_closure_not_reviewed
```

## 11. 下一门

下一阶段 M2.4g-6c 应实现短时、单次、与 6b 准备包和实时状态重新绑定的 manager 操作员授权。授权模块仍不得修改服务。真实 manager 执行必须在之后的 adapter、故障注入和显式 live packet 完成后另行进入门禁。
