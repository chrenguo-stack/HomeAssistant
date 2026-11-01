# gh-t1-homeassistant-mqtt-target-gate-v1

## 1. 目的

M2.4g-1 与 M2.4g-2 在真实认证迁移之前完成两项只读工作：

1. 从 Home Assistant 容器内部验证候选 MQTT Broker 地址的 DNS 与 TCP 可达性，并结合 Docker 网络拓扑确定稳定地址模型；
2. 为 Home Assistant 官方 MQTT config-flow 重新配置建立前置指纹、后置复核和回退约束。

本门不应用凭据，不修改 Home Assistant `.storage`，不配置真实 Broker Dynamic Security，不重启任何真实服务，也不授权操作员在 UI 中执行迁移。

## 2. 前置条件

必须重新执行并通过 M2.4f 客户端迁移能力审计，且结果保持：

```text
schema = gh.m2.t1-auth-client-migration-audit/1
read_only = true
apply_enabled = false
current_services_modified = false
audit_complete = true
ready_for_live_apply = false
```

M2.4f 的以下阻断项必须继续保留：

```text
homeassistant_operator_reconfigure_required
node_credential_delivery_path_unverified
```

## 3. 候选地址模型

候选地址必须由调用者显式给出，不得从当前 Home Assistant MQTT entry 的 Broker 原值推断或复制。工具不得在报告中输出候选主机原值，只能输出候选类型、截断 SHA-256 指纹和布尔结果。

支持三种候选类型：

### 3.1 Docker service alias

```text
docker_service_alias
```

只有同时满足下列条件时才可选：

- Home Assistant 与 Mosquitto 共享至少一个 Docker 网络；
- 候选名称出现在 Mosquitto 于共享网络声明的 aliases 中；
- Home Assistant 容器内 DNS 解析成功；
- Home Assistant 容器内 TCP 连接目标端口成功。

### 3.2 Loopback

```text
loopback
```

只有 Home Assistant 容器使用 `network_mode=host`，且容器内部对 loopback 的 TCP 探测成功时才可选。普通 bridge 网络中的 `127.0.0.1` 仅指向 Home Assistant 容器自身，必须拒绝。

### 3.3 T1 host address

```text
host_address
```

主机地址仅作为显式授权的后备方案。即使 DNS/TCP 可达，未提供 `--allow-host-address-fallback` 时也不得自动选择。该路径依赖主机地址稳定性，后续真实门必须确认 DHCP 保留或等效的稳定地址机制。

## 4. 只读可达性探测

每个候选只允许在 Home Assistant 容器内执行：

- `socket.getaddrinfo()`；
- 最长 2 秒的 TCP connect；
- 输出 `dns_resolved`、`tcp_connectable` 和地址计数。

禁止：

- MQTT CONNECT；
- 发布或订阅；
- 使用暂存用户名或密码；
- 读取、输出或记录当前 MQTT Broker 原值；
- 修改网络、容器或防火墙。

## 5. 选择优先级

若多个候选同时满足拓扑和可达性条件，按以下稳定性优先级选择：

```text
docker_service_alias > loopback > host_address
```

若没有候选满足条件，增加阻断项：

```text
homeassistant_broker_target_unresolved
```

目标地址确定只表示 `target_model_ready=true`，不表示 Broker 身份已经激活，也不表示 Home Assistant 可以立即重新配置。

## 6. Home Assistant 官方重新配置门

Home Assistant MQTT 迁移只能通过官方 UI/config-flow：

```text
设置 → 设备与服务 → MQTT → 重新配置
```

本阶段只生成门禁元数据：

- MQTT entry ID 的脱敏指纹；
- `/config/.storage/core.config_entries` 的 SHA-256；
- 暂存 Home Assistant 凭据材料是否完整；
- discovery 是否保持启用；
- retained 基线是否可读；
- 目标地址模型是否已确定；
- 后置重新审计是否强制；
- 回退是否必须继续使用官方重新配置或新鲜回退包。

固定字段：

```text
official_config_flow_only = true
direct_storage_edit_forbidden = true
automatic_apply = false
operator_action_required = true
operator_action_authorized = false
post_change_reaudit_required = true
rollback_via_official_reconfigure_or_fresh_backup = true
```

## 7. 后置验证要求

未来真实 UI 门执行后，必须立即重新采集并比较：

- MQTT entry 指纹；
- `core.config_entries` SHA-256；
- MQTT entry 唯一性和启用状态；
- Broker 是否与已选目标指纹一致；
- username/password/client ID 是否存在；
- discovery 是否保持启用；
- Home Assistant 容器状态和 restart count；
- retained state 与既有 Discovery 实体是否继续可用；
- manager、Mosquitto 和 Home Assistant 是否仍 `running/restarts=0`。

任何失败都不得通过直接编辑 `.storage` 修复。

## 8. 回退边界

真实 UI 迁移前必须立即生成新的 T1 回退包，并重新校验 live baseline、镜像 ID、配置哈希和 retained 数据。

回退顺序：

1. 匿名兼容仍开启时，通过 Home Assistant 官方重新配置恢复迁移前连接参数；
2. 若 Home Assistant 无法通过官方 config-flow 恢复，停止继续迁移并使用新鲜回退包恢复；
3. 回退后重新运行 M2.4c、M2.4f 和本门；
4. 未恢复到完整基线前，不得迁移 manager 或节点，也不得关闭匿名访问。

本门不生成、保存或输出迁移前 Broker 原值或凭据正文。

## 9. 输出与阻断项

报告 schema：

```text
gh.m2.t1-homeassistant-mqtt-target-gate/1
```

固定安全字段：

```text
read_only = true
apply_enabled = false
current_services_modified = false
ready_for_operator_reconfigure = false
ready_for_live_apply = false
```

当前固定阻断项：

```text
broker_identity_not_activated
homeassistant_operator_reconfigure_required
node_credential_delivery_path_unverified
```

## 10. 明确禁止

本阶段不得：

- 写入 Home Assistant `.storage`；
- 调用 Home Assistant config-flow 写接口；
- 使用暂存凭据连接真实 Broker；
- 修改 Mosquitto、Home Assistant、greenhouse-manager 或节点；
- 创建、停止、重启或重建真实容器；
- 创建活动秘密目录；
- 下发节点凭据；
- 关闭匿名访问；
- 输出当前 MQTT entry 的 Broker、username、password、client ID 或完整 entry ID；
- 输出候选主机原值。

该门通过后，下一步仍是节点凭据交付与双槽回退机制的独立开发，不构成任何真实 apply 授权。
