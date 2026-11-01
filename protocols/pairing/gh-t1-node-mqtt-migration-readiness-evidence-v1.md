# T1 节点 MQTT 运行时迁移前只读证据合同 V1

## 1. 目的与范围

本合同用于在真实节点 `gh-n1-a9f2f8` 尚未接收长期 MQTT 凭据、仍依赖 anonymous 兼容路径时，建立一次新的、不可替代的迁移前只读基线。它不执行凭据生成、密码轮换、节点配置、固件升级、retained 发布、Broker 重启或 anonymous 关闭。

固定范围：

```text
system_id=greenhouse
node_id=gh-n1-a9f2f8
discovery_topic=homeassistant/device/gh-n1-a9f2f8/config
```

## 2. 不可变安全边界

1. `allow_anonymous` 必须保持开启；`anonymous_closure_enabled=false`。
2. 不得访问、读取、写入或编辑 Home Assistant `.storage`。
3. 不得生成、读取、打印或下发节点明文密码。
4. 不得升级或替换生产 Manager、Mosquitto、Home Assistant 镜像。
5. 不得调用 Dynamic Security 控制主题，不得修改 Broker 配置或状态。
6. 不得发布 MQTT 消息；只允许对精确主题执行订阅读取。
7. 不得重放 V70、V84～V92、V69 authorization 或任何已领取/已消耗授权。
8. 证据前后必须重新读取受保护服务、Broker 配置和 Dynamic Security 状态；任何漂移均失败闭锁。
9. 真实 T1 包装脚本必须使用新的唯一文件名，并在执行前验证 SHA-256。

## 3. 证据输入绑定

真实 T1 执行必须绑定：

- 40 位仓库提交 SHA；
- Manager 源码合同版本；
- 交接基线 Broker 配置 SHA-256；
- 交接基线 Dynamic Security 状态 SHA-256；
- 精确 system、node、Discovery topic；
- 节点身份 generation；
- 有界 MQTT 等待窗口和 Broker 日志尾部范围。

已知 V1 基线：

```text
broker_config_sha256=8fbd8cd18259ac071d602ffaf85ecdb4033aed57bf4c0889801ccabf403c2c84
dynamic_security_state_sha256=0d21faa86f4d3f47d64a027de5d2bf524803f5a1d4ecd5d3b070996fcf416320
```

若执行前状态已合理变化，应先建立新的只读基线，不得通过放宽比较继续运行。

## 4. 必须验证的证据

### 4.1 受保护服务

证据前后分别读取 `greenhouse-manager`、`mosquitto`、`homeassistant` 的容器 ID、镜像 ID、启动时间、运行状态与重启次数。三者必须持续运行、重启次数为 0，且前后快照完全一致。

### 4.2 Broker 与 Dynamic Security

必须验证：

- anonymous 处于开启状态；
- Dynamic Security 插件和状态文件绑定唯一；
- 状态文件权限为 `0600`；
- 状态文件属主与 Broker 进程一致；
- 硬链接数为 1；
- 配置和状态 SHA 与绑定基线相同；
- 证据采集前后 SHA 不变。

### 4.3 预配置节点身份

根据正式 `dynsec_plan` 生成期望模型，并对 Dynamic Security 状态作语义比较：

```text
username=ghn_<node_id>
client_id=<node_id>
role=gh-node-<system_id>-<node_id>
```

必须确认：

- 客户端、角色均唯一；
- 固定 client ID 精确匹配；
- 客户端未禁用；
- 仅绑定期望角色；
- 凭据材料存在，但不得输出内容；
- 10 条节点 ACL 与正式计划逐条等价；
- 默认 ACL 访问策略未漂移。

### 4.4 运行时与数据连续性

通过 anonymous 观察连接读取以下精确主题：

```text
gh/v1/greenhouse/state/gh-n1-a9f2f8/telemetry
gh/v1/greenhouse/state/gh-n1-a9f2f8/availability
homeassistant/device/gh-n1-a9f2f8/config
gh/v1/greenhouse/ingress/node/gh-n1-a9f2f8/telemetry
```

必须确认：

- 规范 telemetry retained 可读，`node_id` 精确；
- availability retained 可读且绑定同一节点；
- Discovery retained 的设备标识、state topic、availability topic 均精确；
- 所有组件 `unique_id` 继续绑定同一节点；
- 在有界窗口内收到一条新的 ingress telemetry；
- 不发布测试报文，不改写 retained 状态。

Broker 连接日志必须出现精确 client ID 的最新连接记录，并确认未携带预配置节点 username。若日志无法归因，证据失败，不得把“未发现认证连接”等同于“已证明匿名连接”。原始日志不得写入报告。

## 5. 结果语义

成功结果只表示：

- 当前节点、Broker、Discovery 和实体身份连续；
- anonymous 兼容运行时仍可观察；
- 预配置认证身份与 ACL 未漂移；
- 现场尚未出现提前的认证节点连接；
- 可以进入节点迁移方案评审。

成功结果不表示：

- 节点具备安全保存凭据的固件能力；
- 已建立私有交付路径；
- 已生成或下发节点密码；
- 已获得写操作授权；
- 可以迁移节点或关闭 anonymous。

## 6. 固定阻塞项

只读证据成功后仍必须保留：

```text
node_firmware_authenticated_mqtt_capability_unverified
node_private_credential_delivery_path_unverified
node_anonymous_fallback_rollback_unverified
fresh_node_migration_authorization_not_created
authenticated_node_observation_window_pending
anonymous_closure_not_authorized
```

因此：

```text
ready_for_node_migration_design=true
ready_for_node_credential_generation=false
ready_for_live_apply=false
ready_for_anonymous_closure=false
```
