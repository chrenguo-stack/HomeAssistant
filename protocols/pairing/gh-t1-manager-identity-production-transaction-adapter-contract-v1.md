# greenhouse-manager 身份迁移生产事务适配器契约 V1

**Schema：** `gh.m2.t1-manager-identity-production-transaction-adapter-contract/1`  
**开发门：** M2.4g-6e  
**状态：** 接口冻结；适配器未安装；真实执行禁用

## 1. 目的与路线位置

本契约将已通过隔离副本验证的 `greenhouse-manager` 身份迁移流程，收敛为后续生产适配器必须遵守的最小能力边界。

本阶段仍属于开发路线 V0.5 中 H1/H3 与 N2 的迁移前置工程，不代表：

- `greenhouse-manager` 已完成真实身份迁移；
- 真实节点已获得长期凭据；
- 匿名 MQTT 兼容可以关闭；
- H3 主机维护、备份与恢复闭环已经完成。

## 2. 输入绑定

契约只能从 mode `0600` 的私有 manager migration preparation package 构建，并完整验证：

- preparation manifest 及其全部记录清单；
- manager runtime binding；
- manager transaction plan；
- manager environment、password 和 Compose fragment 的 SHA-256；
- manager runtime 与 Compose 指纹；
- postactivation handoff 与 migration stage 的 SHA-256；
- Compose project、working directory、config file set；
- active secret root 与 manager password target；
- manager username 与独立 Client ID 指纹。

普通输出只包含 SHA-256 和短指纹，不得包含密码、完整身份值或真实主机路径。

## 3. 冻结事务顺序

后续真实事务必须按以下顺序执行，不得跳步或并行：

1. claim 单次短时授权；
2. 重新验证 manager runtime、Compose 和 mount 绑定；
3. 验证 fresh rollback；
4. 原子写入 manager password；
5. 原子写入 manager auth environment；
6. 原子写入 manager Compose overlay；
7. 仅重建 `greenhouse-manager`；
8. 验证认证 username 与独立 Client ID；
9. 验证 ingress subscribe；
10. 验证 canonical state 发布；
11. 验证 Home Assistant Discovery 发布；
12. 验证 manager 断线重连；
13. 验证原有 Home Assistant 实体继续刷新；
14. 执行完整 postactivation audit；
15. 提交私有事务 journal。

任一授权 claim 后的失败都必须进入 rollback；rollback 失败是终止状态。

## 4. 文件系统能力边界

后续适配器只允许三类写入：

- manager password；
- manager auth environment；
- manager Compose overlay。

每次写入必须使用同目录临时文件、file `fsync`、mode `0600`、原子替换和父目录 `fsync`。禁止符号链接目标，禁止越过 preparation 绑定的目标路径。

## 5. 运行时命令边界

允许的命令模型只有：

```text
docker inspect greenhouse-manager
```

以及使用已绑定 project、working directory、Compose 文件集合和 auth overlay 的：

```text
docker compose ... up -d --no-deps --force-recreate greenhouse-manager
```

明确禁止：

- 操作、重启或重建 Mosquitto；
- 操作、重启或重建 Home Assistant；
- 操作节点或下发节点凭据；
- shell、SSH、systemd、`docker exec`、`docker cp`、任意容器创建/删除；
- 将 `greenhouse-manager` 以外的服务加入 Compose target。

## 6. Fresh rollback 契约

真实事务前必须另行捕获 fresh rollback，并满足：

- 在授权创建前完成；
- 最大新鲜度 900 秒；
- 完整覆盖 Compose tree 与 manager secret tree；
- 包含文件类型、mode、owner、inventory SHA-256 与 archive SHA-256；
- 绑定 preparation、runtime、Compose、secret root 和 password target；
- 已通过恢复演练；
- rollback 后 inventory 必须精确一致。

本 6e 契约不捕获、绑定或执行真实 rollback。

## 7. Postactivation 验收

必须同时满足：

- manager 以独立认证身份连接且 Client ID 匹配；
- ingress subscribe 正常；
- canonical state 和 Discovery 正常发布；
- 断线重连正常；
- 原有 Home Assistant 设备和实体继续刷新；
- manager `restart_count=0`；
- Broker 身份激活和 Home Assistant 认证状态保持正常；
- 匿名兼容继续保留；
- 节点凭据保持不变。

## 8. Rollback 验收

rollback 必须：

- 恢复完整 Compose 与 manager secret snapshot；
- 清除新写入的 manager auth mutation state；
- 仅重建 `greenhouse-manager`；
- 验证旧 manager 兼容路径恢复；
- 验证原有 Home Assistant 实体继续刷新；
- 验证恢复后的 inventory 精确匹配；
- 写入私有 rollback journal。

不得回退 Mosquitto、Home Assistant 或节点凭据。

## 9. 本阶段强制安全状态

```text
production_transaction_adapters_installed=false
authorization_claimed=false
claim_enabled=false
fresh_rollback_bound=false
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

公开 CLI 只能生成和校验契约，不得提供 `claim`、`execute`、`apply` 或 `live` 入口。

## 10. 后续门禁

进入真实 manager 迁移前，至少还需独立完成：

1. production manager driver contract；
2. production adapter 临时副本故障注入；
3. 真实 T1 只读 runtime/mount/Compose gate；
4. fresh rollback 与 execution preparation packet；
5. 第二次精确确认与用户维护窗口决策；
6. manager-only live transaction 与自动回退。
