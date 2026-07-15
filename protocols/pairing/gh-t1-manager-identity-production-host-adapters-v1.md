# greenhouse-manager 身份迁移生产宿主机适配器 V1

- 阶段：M2.4g-6m
- 状态：Draft
- 范围：真实 T1 上 `greenhouse-manager` 独立 MQTT 身份迁移的受限宿主机适配器与运行时 driver
- 关联：Issue #17、#94、#96；6e～6l

## 1. 目的

本协议把 6l 库级事务编排器连接到真实主机所需的最小文件系统与 Docker 能力收敛为受限接口。6m 只交付可注入的 adapters 与 driver，不交付 execute CLI，不领取授权，也不执行真实 T1 apply。

## 2. 输入绑定

适配器必须完整验证：

- mode `0600` 的 6f production driver contract；
- 仍在有效期内的 6i execution preparation；
- 6b manager migration preparation 及其全部记录；
- driver、adapter、runtime、live binding 和 preparation manifest 的 SHA-256；
- Compose project、working directory、config file set 和可选 `.env`；
- manager secret root、password target、认证环境和 overlay 目标；
- fresh rollback archive 的 scope、inventory、路径和摘要。

任何文件、路径、绑定、mode、owner、size 或 SHA-256 漂移都必须 fail closed。

## 3. 写入能力边界

仅允许以下四类写入：

1. manager password target；
2. Compose working directory 下的 `manager-auth.env`；
3. Compose working directory下的 `docker-compose.manager-auth.yml`。
4. fresh rollback 精确绑定、且仅位于 manager secret provisioning anchor 下的缺失私有目录链。

写入必须采用：

- 同目录临时文件；
- file `fsync`；
- mode `0600`；
- 原子 `replace`；
- 父目录 `fsync`；
- 路径必须处于已绑定 root 内；
- 目标或现存祖先不得为符号链接。
- 目录 provisioning 的 trusted parent 必须预先存在且不是符号链接；新建目录必须逐级创建为
  mode `0700`，每级执行 parent `fsync`，并由 fresh rollback 记录精确的逆序清理清单；
- password 原子写入必须在标准 host adapter 内触发该目录 provisioning，生产包装器不得依赖
  外置或可遗漏的目录创建步骤。

不得创建、覆盖或删除上述四类目标以外的认证状态。

## 4. Docker 命令白名单

允许的运行时命令只有：

```text
docker inspect greenhouse-manager
```

以及基于已绑定 project、working directory、原始 Compose 文件集合和 manager auth overlay 的：

```text
docker compose \
  --project-directory <bound-working-directory> \
  --project-name <bound-project> \
  -f <bound-config-1> ... \
  -f <bound-manager-auth-overlay> \
  up -d --no-deps --force-recreate greenhouse-manager
```

回滚重建使用相同已绑定 project/config set，但不得包含 auth overlay。

明确禁止：

- `docker exec`、`docker cp`、任意 shell 或 SSH；
- 修改、重启或重建 Mosquitto；
- 修改、重启或重建 Home Assistant；
- 修改节点或下发节点凭据；
- 将任何其他 service 加入 Compose target。

## 5. Snapshot 与 rollback

`prepare()` 必须在授权 claim 前：

1. 验证 fresh rollback archive；
2. 将 archive 成员逐个读取到事务私有子目录；
3. 禁止 `extractall`、绝对路径、`..`、符号链接和未登记成员；
4. 要求 source path 精确属于已绑定 Compose config set 或 `.env`；
5. 生成 path-redacted、secret-free 的 snapshot inventory；
6. 不修改任何当前服务或目标文件。

rollback 必须：

- 原子恢复全部 Compose config 和可选 `.env`；
- 删除 manager auth overlay、auth environment 和 password target；
- 仅按 fresh rollback 清单由深到浅删除本事务创建的私有目录；已有目录不得删除；
- 只重建 `greenhouse-manager`；
- 验证旧匿名路径和原有 Home Assistant 实体；
- 对恢复后的 mode 与 SHA-256 逐项复核；
- 任何残留认证 mutation state 都视为失败。

## 6. 运行时探针接口

实际业务验证通过注入式 probe 完成，必须覆盖：

- manager 独立 username 与 Client ID；
- ingress subscription；
- canonical state 发布；
- availability 发布；
- Home Assistant Discovery 发布；
- MQTT 断线重连；
- 原有设备和实体连续刷新；
- legacy anonymous path；
- 完整 postactivation audit。

普通报告只返回布尔状态、摘要和短指纹，不返回密码、完整身份、Compose/.env 内容或真实路径。

## 7. 与 6l 的集成约束

6l 在事务 root 写入 `journal.json`。6m 的 factory 必须使用独立的：

```text
<transaction-workspace>/host-adapters
```

作为 adapters workspace，并确保其为新建 mode `0700` 空目录。不得把已有 journal 的事务 root 直接传给要求空目录的 `prepare()`。

## 8. 当前强制状态

本阶段合并后仍必须保持：

```text
execution_entrypoint_installed=false
authorization_claimed=false
production_executor_available=false
execution_enabled=false
apply_enabled=false
ready_for_manager_migration_apply=false
manager_identity_migrated=false
node_credentials_delivered=false
current_services_modified=false
preserve_anonymous=true
anonymous_closure_enabled=false
```

## 9. 后续门

下一阶段才允许：

1. 将 6l orchestrator 与 6m adapters/driver 通过受限 factory 连接；
2. 实现真实 runtime probe；
3. 覆盖完整故障注入矩阵；
4. 形成唯一 execute packet/CLI；
5. 重新走真实 T1 的 6e/6f/6i/6j、第一次确认、6k 和第二次精确确认。

本协议不构成真实 T1 写授权。
