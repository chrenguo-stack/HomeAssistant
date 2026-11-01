# T1 Manager Identity Migration Host Replica V1

状态：M2.4g-6d Draft

## 1. 目的

本协议在 6b 准备包和 6c 授权合同已经冻结后，仅在系统临时目录中的标记副本上实现并演练 `greenhouse-manager` 身份迁移所需的文件事务、manager 重建、身份/订阅/发布验证与完整回退。

本阶段不使用真实操作员授权，不 claim 或 consume 授权，也不提供真实 T1 执行入口。

## 2. V0.5 阶段边界

本阶段仍属于 H1/H3 与 N2 的交叉前置建设。成功演练只能证明 manager 迁移事务模型具备继续产品化的基础，不得标记：

- H3 完成；
- N2 完成；
- manager 真实身份已经迁移；
- 节点凭据已经下发；
- 匿名访问可以关闭。

所有报告必须保持：

```text
replica_only=true
real_t1_target_allowed=false
production_executor_available=false
execution_enabled=false
apply_enabled=false
operator_action_authorized=false
ready_for_manager_migration_apply=false
manager_identity_migrated=false
node_credentials_delivered=false
current_services_modified=false
preserve_anonymous=true
anonymous_closure_enabled=false
```

## 3. 输入

### 3.1 6b preparation

必须验证：

- `gh.m2.t1-manager-identity-migration-preparation/1`；
- 全部 records 的 mode、size、SHA-256 与 secret classification；
- manager environment、password、Compose fragment；
- manager runtime binding；
- preparation 中的用户名、Client ID 与 runtime binding 指纹。

### 3.2 临时副本

副本必须：

- 位于系统临时目录；
- 根目录及子目录为私有目录；
- 不含符号链接；
- 包含 mode `0600` 的 `.gh-m2-manager-host-replica.json`；
- marker 与 preparation manifest、manager runtime、Compose binding 全指纹绑定；
- `manager/compose` 中的 baseline Compose 文件和 `.env` 与 runtime binding 的 mode、size、SHA-256 一致；
- `manager/secrets` 初始不含 manager password；
- 初始不含 `manager-auth.env` 或 `docker-compose.manager-auth.yml`。

真实 `/opt/...`、Docker bind mount 或 active secret 目录均不得作为 replica root。

## 4. 注入式 Driver

host replica adapters 只调用注入式 driver 接口：

1. `recreate_manager`；
2. `verify_authenticated_identity`；
3. `verify_ingress_subscription`；
4. `verify_canonical_publication`；
5. `verify_discovery_publication`；
6. `verify_reconnect`；
7. `postactivation_audit`；
8. `recreate_after_rollback`；
9. `verify_legacy_anonymous_path`。

模块自身不得包含 Docker、Compose、systemd、SSH 或真实 MQTT 命令。

## 5. 原子事务顺序

在副本上必须按以下顺序执行：

1. 建立完整 `manager` tree baseline 快照；
2. 原子写入 `manager/secrets/manager/password`；
3. 原子写入 `manager/compose/manager-auth.env`；
4. 原子写入 `manager/compose/docker-compose.manager-auth.yml`；
5. 请求注入式 driver 重建 manager；
6. 验证独立 username 与 Client ID；
7. 验证 ingress 订阅；
8. 验证 canonical state 发布；
9. 验证 Home Assistant Discovery 发布；
10. 验证断线重连；
11. 执行 postactivation audit。

所有文件写入必须使用同目录临时文件、`fsync`、mode `0600` 和原子替换。

## 6. Postactivation 合同

注入式审计至少必须返回：

```text
manager_identity_verified=true
ingress_subscription_verified=true
canonical_publication_verified=true
discovery_publication_verified=true
reconnect_verified=true
rollback_required=false
replica_only=true
preserve_anonymous=true
anonymous_closure_enabled=false
```

任一字段失败均必须进入回退。

## 7. 回退

回退必须：

- 以完整 baseline tree 替换已变更的 `manager` tree；
- 对 replica root 执行目录 `fsync`；
- 调用注入式 driver 恢复旧 manager；
- 验证 legacy anonymous path；
- 比较完整路径、mode 和 SHA-256 inventory；
- 确认 manager auth material 已消失。

回退不完整必须作为终止错误显式上报，禁止伪装为成功。

## 8. 故障注入矩阵

至少覆盖：

```text
after_password_write
after_env_write
after_overlay_write
after_recreate
after_identity
after_subscription
after_canonical_publish
after_discovery_publish
after_reconnect
postactivation
rollback_incomplete
```

除 `rollback_incomplete` 外，每个故障都必须恢复完整 baseline inventory。`rollback_incomplete` 必须明确报告“事务失败且回退失败”。

每个阶段使用独立临时副本；输入 template 必须在整个矩阵后保持不可变。

## 9. 成功报告

成功副本演练可以输出：

```text
mutation_completed=true
postactivation_verified=true
rollback_completed=false
manager_identity_migrated_in_replica=true
```

但全局状态必须继续输出：

```text
manager_identity_migrated=false
ready_for_manager_migration_apply=false
```

## 10. 下一门

M2.4g-6e 应冻结 production manager transaction adapter contract：

- 精确输入和路径绑定；
- fresh rollback；
- 允许的 Compose 与 Docker 命令集合；
- manager-only recreate/restart；
- postactivation 与强制回退；
- 禁止修改 Mosquitto、Home Assistant、节点或匿名模式。

6e 仍应默认禁用真实执行；在生产 driver、fault matrix、执行准备包和第二次精确确认完成前，不得创建真实 T1 live packet。
