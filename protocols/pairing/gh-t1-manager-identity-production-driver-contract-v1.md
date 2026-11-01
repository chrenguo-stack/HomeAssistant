# greenhouse-manager 身份迁移生产驱动契约 V1

**Schema：** `gh.m2.t1-manager-identity-production-driver-contract/1`  
**开发门：** M2.4g-6f  
**状态：** 驱动接口冻结；实现未安装；真实执行禁用

## 1. 目的

本契约承接 M2.4g-6e 的 production transaction adapter contract，将后续生产驱动必须提供的方法、命令构造、文件写入、验证、回退和日志接口冻结为不可调用的静态协议。

本阶段只定义能力边界，不安装真实驱动，不解析真实主机路径，不创建或消费授权，不操作 T1。

## 2. 输入与绑定

输入必须是 mode `0600` 的 6e adapter contract。驱动契约绑定：

- adapter contract SHA-256；
- preparation、runtime binding、transaction plan 和三份 manager material 的 SHA-256；
- postactivation 与 migration stage SHA-256；
- manager runtime、Compose、project、working directory、config set 指纹；
- active secret root、password target、manager username 与 Client ID 指纹。

输出不得包含密码、完整身份值或真实主机路径。

## 3. 冻结方法清单

后续驱动实现只能提供以下方法：

```text
claim_authorization
revalidate_runtime
verify_fresh_rollback
install_manager_material
recreate_manager
verify_authenticated_identity
verify_ingress_subscription
verify_canonical_publication
verify_discovery_publication
verify_reconnect
verify_existing_entities
postactivation_audit
rollback
append_journal
```

6f 中所有方法均保持：

```text
installed=false
callable=false
host_path_access=false
host_write_capability=false
docker_mutation_capability=false
mqtt_probe_capability=false
authorization_claim_capability=false
```

## 4. Runtime 驱动边界

命令构造只能来自已绑定的 Compose project、working directory、config file set 和事务私有 overlay。

允许的命令模型：

```text
docker inspect greenhouse-manager

docker compose \
  --project-name <bound-project> \
  --project-directory <bound-working-directory> \
  --file <each-bound-config-file> \
  --file <bound-manager-auth-overlay> \
  up -d --no-deps --force-recreate greenhouse-manager
```

必须使用 argv 数组，不允许 shell 字符串。服务目标只能是 `greenhouse-manager`。Mosquitto、Home Assistant 和节点均不得成为命令目标。

## 5. 文件系统驱动边界

只允许：

- manager password 原子写入；
- manager auth environment 原子写入；
- manager Compose overlay 原子写入。

要求同目录临时文件、file fsync、原子替换、父目录 fsync、mode `0600`，并拒绝符号链接。6f 不解析任何真实主机路径。

## 6. Fresh rollback 驱动边界

驱动必须在后续门禁中验证：

- 最大新鲜度 900 秒；
- 完整 Compose 与 manager secret snapshot；
- inventory 与 archive SHA-256；
- 恢复演练已经通过；
- rollback 后精确 inventory 匹配。

6f 不捕获、不绑定、不恢复真实 rollback。

## 7. 验证驱动边界

后续实现必须能够验证：

- manager 认证身份与独立 Client ID；
- ingress subscription；
- canonical state 与 Discovery 发布；
- 断线重连；
- 原有 Home Assistant 实体继续刷新；
- manager restart count 为零；
- Broker 和 Home Assistant 认证状态保持；
- 匿名兼容保持；
- 节点凭据未变化。

MQTT probe 和 host runtime probe 的具体实现仍未选择。

## 8. 回退与日志边界

任一授权 claim 后的失败必须回退完整 snapshot，只能重建 `greenhouse-manager`，并验证旧路径、实体刷新与 inventory 精确恢复。回退失败是终止状态。

journal 必须 mode `0600`，每阶段 append + fsync，不得记录秘密值或真实主机路径。

## 9. 强制安全状态

```text
production_manager_driver_installed=false
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

公开 CLI 只能生成和验证契约，不得提供 execute、claim、apply 或 live 入口。

## 10. 后续门禁

下一步为 production driver 的临时主机副本实现与故障注入。只有在副本恢复矩阵全部通过后，才进入真实 T1 只读 runtime/mount/Compose gate。
