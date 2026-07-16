# T1 Home Assistant MQTT 迁移材料证据 V1

状态：M2.4i Draft

## 1. 目的

Broker Dynamic Security 已激活、Manager 已迁移认证身份并通过持续性审计后，Home Assistant 的专用 MQTT identity 已存在于 Broker，但运行中的 Home Assistant 尚未完成官方 MQTT UI/config-flow 重配置。

本合同在不读取 Home Assistant `.storage` 的前提下，定位并验证此前生成的私有 Home Assistant MQTT 迁移材料，证明这些材料仍与当前 Broker identity、client ID 约束、retained 状态和网络拓扑一致。

本阶段只建立“可准备官方重配置交接”的证据，不授权用户操作，也不自动修改 Home Assistant。

## 2. 输入材料

允许识别以下两种私有 JSON：

```text
gh.m2.homeassistant-mqtt-update/1
gh.m2.homeassistant-mqtt-reconfigure-values/1
```

材料必须满足：

- 普通文件、非符号链接；
- 单硬链接；
- mode `0600`；
- 直接父目录不允许 group/other 访问；
- username、password、client ID 和 port 完整；
- discovery 保持启用；
- operation 明确为官方 MQTT config entry 重配置；
- 所有重复副本必须归一到同一个 credential binding。

若发现多个互相冲突的 credential binding，必须失败闭锁，不得自行选择最新文件。

## 3. 在线验证

对唯一候选材料执行以下只读验证：

1. 当前 Broker 仍加载 Dynamic Security plugin；
2. anonymous 兼容仍开启；
3. Dynamic Security state 为 mode `0600`、单硬链接，UID/GID 与 Broker 进程运行身份一致；
4. state 中恰有一个 Home Assistant identity；
5. username、client ID、role 与冻结模型一致；
6. 候选 credential 使用正确 client ID 可订阅并读取既有 retained telemetry；
7. 使用相同 username/password 但错误 client ID 必须被拒绝；
8. 从 Home Assistant 容器到 Broker 的候选目标可达；
9. 三个受保护容器、Broker 配置和 Dynamic Security state 在验证前后完全不变。

验证只建立临时 `mosquitto_sub` 订阅连接，不发布 MQTT 消息。

## 4. Home Assistant 边界

严禁读取或写入 Home Assistant `.storage`，包括但不限于：

```text
/config/.storage/core.config_entries
```

不得通过文件编辑自动更新 MQTT config entry。后续只能由操作员在 Home Assistant 官方 MQTT Reconfigure/config-flow 中输入经验证的本地私有材料。

## 5. 输出脱敏

普通报告不得包含：

- username、password、client ID 原文；
- Broker host 原文；
- 候选文件路径；
- Docker container ID 或 image ID；
- 节点凭据；
- Home Assistant 存储内容。

允许输出固定长度指纹、计数和 SHA-256。

## 6. 成功边界

成功时：

```text
material_evidence_verified=true
ready_for_homeassistant_official_reconfigure_handoff=true
ready_for_live_apply=false
operator_action_authorized=false
```

并必须保留以下阻塞项：

```text
explicit_operator_decision_required
homeassistant_official_mqtt_ui_config_flow_pending
homeassistant_postchange_runtime_verification_pending
real_node_credential_delivery_unverified
authenticated_observation_window_pending
anonymous_closure_not_authorized
```

## 7. 永久安全约束

本工具不得：

- 修改、重启或重建任何容器；
- 修改 Broker 配置或 Dynamic Security state；
- 发布 MQTT 消息；
- 创建、认领、消费或复用生产授权；
- 调用生产执行器；
- 读取或写入 Home Assistant `.storage`；
- 下发节点凭据；
- 关闭 anonymous MQTT。
