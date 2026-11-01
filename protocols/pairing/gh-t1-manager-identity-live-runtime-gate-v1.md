# greenhouse-manager 身份迁移真实 T1 只读运行时门禁 V1

**Schema：** `gh.m2.t1-manager-identity-live-runtime-gate/1`  
**开发门：** M2.4g-6h  
**状态：** 只读检查；不创建授权；不写入文件；不重建容器

## 1. 目的与路线位置

本门禁承接 M2.4g-6g 已通过的 production driver 临时主机副本故障矩阵，在真实 T1 上确认当前 `greenhouse-manager` 的运行时身份、Compose 来源、文件元数据、安全配置和 inactive manager secret target 仍与 migration preparation 绑定一致。

本门禁通过后，只允许进入 fresh rollback 与 execution preparation 的下一阶段。它不代表 manager 身份已经迁移，也不授权任何写入或容器重建。

## 2. 输入

必须提供：

1. mode `0600` 的 M2.4g-6f production manager driver contract；
2. mode `0700` 的 manager migration preparation package。

门禁重新验证：

- driver contract 自身 SHA-256；
- 从 preparation package 重建的 M2.4g-6e adapter contract；
- preparation 内 `manager-runtime-binding.json` 的 SHA-256；
- manager runtime、Compose、secret root 和 password target 指纹；
- manager material、postactivation 与 migration stage 的既有绑定。

## 3. 唯一允许的运行时命令

```text
docker inspect greenhouse-manager
```

不得执行：

- `docker exec`；
- `docker cp`；
- `docker restart`；
- `docker compose up`；
- 任何 shell、SSH 或 systemd 命令；
- 任何 Mosquitto、Home Assistant 或节点操作。

## 4. 运行时身份检查

真实容器必须满足：

- 只有一个名为 `greenhouse-manager` 的容器；
- 状态为 `running`；
- `restart_count=0`；
- container ID、image ID、image ref、started time 与 preparation 完全一致；
- 旧 Client ID 指纹与 preparation 一致；
- `GH_MQTT_USERNAME`、`GH_MQTT_PASSWORD`、`GH_MQTT_PASSWORD_FILE` 均未激活。

任何漂移都要求重新生成 preparation 与后续契约，不能继续沿用旧材料。

## 5. Compose 检查

门禁从 Docker Compose labels 重新解析：

- project；
- working directory；
- config file set；
- `.env`。

每个文件必须：

- 位于绑定的 working directory 内；
- 是普通文件而非符号链接；
- device、inode、mode、uid、gid、size 和 SHA-256 与 preparation 完全一致。

重建后的 Compose binding 必须与 preparation 记录逐字段相同，并通过 driver contract 中的 project、working directory 和 config set 指纹。

## 6. 容器安全配置检查

必须保持：

```text
ReadonlyRootfs=true
Privileged=false
CapDrop includes ALL
SecurityOpt includes no-new-privileges
```

该检查避免身份迁移准备过程意外削弱现有 manager 容器隔离。

## 7. Inactive manager secret target 检查

门禁只检查 preparation 已绑定的 active secret root 和 manager password target：

- 路径必须为绝对路径且不能是符号链接；
- secret root 若已存在，必须是私有目录；
- password target 的父目录若已存在，必须是私有目录；
- manager password target 必须不存在；
- 当前容器不得挂载 `/run/secrets/gh_manager_mqtt_password`；
- 当前容器不得挂载 active secret root 或其子路径。

已有其他服务凭据不要求删除；本门禁只防止 manager 凭据提前激活。

## 8. 输出与脱敏

普通输出只包含：

- SHA-256；
- 16 位短指纹；
- 布尔检查结果；
- 强制安全状态。

不得输出密码、完整 username、完整 Client ID 或真实主机路径。

## 9. 强制安全状态

```text
read_only=true
live_runtime_gate_ready=true
ready_for_fresh_rollback_preparation=true
production_manager_driver_installed=false
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

其中 `ready_for_fresh_rollback_preparation=true` 仅表示可以开发和执行下一阶段的 fresh rollback 准备，不表示可以迁移 manager。

## 10. CLI 边界

CLI 只接受：

```text
<driver_contract_file> <preparation_directory>
```

不得提供：

```text
--execute
--claim
--apply
--live
```

## 11. 下一门禁

M2.4g-6h 通过后进入 M2.4g-6i：

1. 捕获真实 T1 fresh Compose + manager secret rollback；
2. 绑定 rollback inventory、archive、runtime、Compose 和 secret target；
3. 完成恢复演练；
4. 生成仍不可执行的 execution preparation packet。

6i 完成后仍需第二次精确确认和维护窗口决策，才能讨论 manager-only live transaction。
