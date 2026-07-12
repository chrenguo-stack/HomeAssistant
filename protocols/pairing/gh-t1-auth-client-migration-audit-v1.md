# gh-t1-auth-client-migration-audit-v1

## 1. 目的

M2.4f 在真实激活之前，只读审计三类客户端的迁移能力：

- greenhouse-manager；
- Home Assistant MQTT integration；
- 环境监测节点。

该阶段不得应用任何凭据，也不得修改 Home Assistant `.storage`、节点固件、Compose、`.env`、Broker 或活动秘密目录。

## 2. 前置条件

必须使用已通过 M2.4d 与 M2.4e 的私有非激活暂存目录。

暂存目录必须再次通过完整性验证，且 `activation-plan.json` 必须保持：

```text
activation_enabled = false
current_services_modified = false
active_paths_modified = false
preserve_anonymous = true
anonymous_closure_enabled = false
requires_explicit_gate = true
requires_fresh_backup_immediately_before_apply = true
```

工具必须重新运行 M2.4c live readiness。任何门禁漂移都必须在客户端审计前阻断。

## 3. Home Assistant 审计

### 3.1 容器发现

通过 Docker 运行清单发现唯一 Home Assistant 容器，并只读检查：

- 容器状态；
- restart count；
- image reference 与 image ID；
- `/config` mount 类型和来源；
- Compose project、working directory 及 config-files label 是否存在；
- Home Assistant 版本（可读取时）。

若发现零个或多个候选容器，必须阻断。

### 3.2 MQTT config entry

只允许通过以下只读方式读取：

```text
docker exec <homeassistant> cat /config/.storage/core.config_entries
```

工具在内存中解析 MQTT config entry，不得输出原始 JSON。报告只能包含：

- storage version；
- MQTT entry 数量；
- 启用的 MQTT entry 数量；
- 是否唯一存在；
- entry ID 的截断 SHA-256 指纹；
- source；
- title、broker、port、username、password、client ID 是否存在；
- discovery 是否显式关闭；
- broker 是否与预期目标匹配。

不得输出：

- entry ID 原值；
- broker 实际值；
- username；
- password；
- client ID；
- 任何 Home Assistant access token。

### 3.3 迁移路径

Home Assistant MQTT config entry 必须通过 Home Assistant 官方 UI/config-flow 重新配置。

```text
direct_storage_edit_forbidden = true
automatic_update_supported = false
migration_method = homeassistant_ui_reconfigure
operator_action_required = true
```

本阶段不得写入 `/config/.storage/core.config_entries`，不得直接重启 Home Assistant。

## 4. greenhouse-manager 审计

暂存目录必须包含：

- `payload/manager/manager.env`；
- `payload/manager/password`；
- `payload/manager/compose-secret-fragment.yaml`。

仅验证：

- username 与 client ID 字段存在；
- password-file contract 为 `/run/secrets/gh_manager_mqtt_password`；
- password 文件模式为 `0600`；
- Compose fragment 存在。

报告不得包含字段值或秘密内容。

## 5. 节点审计

暂存目录必须包含：

```text
payload/node/<node_id>/mqtt-credentials.json
```

仅验证 schema、node ID、username/password/client ID 存在，以及：

```text
automatic_apply = false
migration_method = firmware_or_provisioning_update_required
live_delivery_path_verified = false
```

在节点凭据安全交付与回退路径经过独立开发、测试和实机验证之前，真实激活必须保持阻断。

## 6. 输出与阻断项

报告 schema：

```text
gh.m2.t1-auth-client-migration-audit/1
```

固定安全字段：

```text
read_only = true
apply_enabled = false
current_services_modified = false
ready_for_live_apply = false
```

当前预期阻断项至少包括：

```text
homeassistant_operator_reconfigure_required
node_credential_delivery_path_unverified
```

若 MQTT entry 缺失或不唯一，增加：

```text
homeassistant_mqtt_entry_not_ready
```

若当前 Broker 与预期目标不匹配，增加：

```text
homeassistant_broker_target_mismatch
```

## 7. 明确禁止

本阶段不得：

- 修改 Home Assistant `.storage`；
- 调用 Home Assistant config-flow 写接口；
- 写入 manager Compose 或 `.env`；
- 写入 `/opt/greenhouse-secrets/mqtt`；
- 修改或下发节点凭据；
- 创建、停止、重启或重建真实容器；
- 配置真实 Broker Dynamic Security；
- 关闭匿名访问；
- 输出任何密码或完整 config-entry 标识。

审计完成只用于确定后续开发阻断项，不构成真实迁移授权。
