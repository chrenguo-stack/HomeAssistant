# T1 Broker Dynamic Security 预激活 Fresh Evidence V1

状态：M2.4h Draft

## 1. 目的

Manager MQTT 身份迁移已经提交并通过持续性审计后，Broker Dynamic Security 的预激活证据必须重新建立。旧证据链假设 Manager 尚未配置认证，也会读取 Home Assistant `.storage`，因此不能继续作为当前基线。

本合同定义一个新的只读证据重建步骤。它只证明当前环境满足进入后续预激活门的条件，不授权 Broker 激活，也不授权任何客户端迁移。

## 2. 当前基线

Fresh evidence 必须同时证明：

1. `greenhouse-manager`、`mosquitto`、`homeassistant` 均处于 running 且 restart count 为 0；
2. Manager 已使用独立 MQTT username、client ID 和只读 password-file；
3. Manager 密码文件为单硬链接、非空、mode `0600`，UID/GID 与 Manager 进程有效身份一致；
4. Manager 到 Broker 的 MQTT 连接稳定；
5. Broker 仍允许 anonymous；
6. Dynamic Security plugin 可用，但尚未写入 Broker 配置，state 文件尚不存在；
7. 既有 canonical telemetry、availability 与 Home Assistant Discovery retained 数据连续；
8. Home Assistant 到 Broker 的可达拓扑可通过容器元数据和 TCP probe 确认；
9. 节点最小权限 ACL 模型仍限制为仅发布自身 ingress topic。

## 3. Home Assistant 边界

本阶段禁止读取或写入：

```text
/config/.storage
/config/.storage/core.config_entries
```

Home Assistant 的 MQTT config entry 身份绑定延后到官方 MQTT UI/config-flow 操作阶段。Fresh evidence 仅确认网络拓扑、Broker 可达性和“必须使用官方配置流程”的约束。

## 4. 允许的输出写入

工具可以在显式 output root 下创建一个新的私有 evidence bundle：

- bundle 目录 mode `0700`；
- `evidence.json` 和 `manifest.json` mode `0600`；
- 先在同一文件系统的临时私有目录完成写入和 fsync，再原子重命名为最终目录；
- 失败时不得遗留最终目录或部分证据。

该写入仅用于审计证据，不得修改任何运行服务、Broker 配置、Compose 配置、凭据或 Home Assistant 数据。

## 5. 输出脱敏

普通输出和 evidence bundle 不得包含：

- 密码、username 或 client ID 原文；
- 密码文件源路径；
- Home Assistant `.storage` 内容或路径；
- Docker container ID、image ID；
- Broker candidate 原始 host；
- 节点凭据。

允许输出固定长度指纹和 SHA-256，以用于同一证据链中的完整性验证。

## 6. 强制阻塞项

即使 fresh evidence 全部通过，也必须继续输出以下阻塞项：

```text
explicit_operator_decision_required
production_driver_not_installed
single_use_authorization_not_created
homeassistant_official_mqtt_ui_config_flow_pending
real_node_credential_delivery_unverified
anonymous_closure_not_authorized
```

因此：

```text
ready_for_broker_preactivation_gate=true
ready_for_live_activation=false
apply_enabled=false
execution_enabled=false
operator_action_authorized=false
```

## 7. 永久安全约束

Fresh evidence 工具不得：

- 调用 Broker 或 Manager 生产执行器；
- 创建、认领、消费或复用生产授权；
- 重启、停止、删除或重建容器；
- 发布 MQTT 消息；
- 修改 Broker、Compose、Home Assistant 或节点；
- 下发节点凭据；
- 关闭 anonymous MQTT。

后续任何 Broker 激活仍需独立的 fresh rollback、runtime binding、生产驱动合同、短时单次授权和用户明确确认。
