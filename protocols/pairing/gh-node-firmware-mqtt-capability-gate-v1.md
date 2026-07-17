# 节点固件 MQTT 认证能力门 V1

## 1. 目的

本合同将真实节点 `gh-n1-a9f2f8` 的 V96 同步重连只读证据转化为候选固件设计门。当前只允许设计、静态实现与隔离测试准备，不生成节点密码，不下发凭据，不升级生产节点或 T1 镜像，不关闭 anonymous。

## 2. V96 已确认事实

```text
system_id=greenhouse
node_id=gh-n1-a9f2f8
generation=1
repository_sha=9b70576bcac47c9e3f95cedfd467652b517c1b11
manager_source_version=0.4.87
```

现场证据确认：

- anonymous 仍开启；
- Dynamic Security 中目标节点身份、角色及 10 条 ACL 精确；
- 节点当前连接确属 anonymous；
- 同步重连与 fresh ingress 均被观察到；
- retained telemetry、availability、Discovery 及 19 个组件身份连续；
- 当前运行时 Client ID 与预配置目标 Client ID 不同；
- Manager、Mosquitto、Home Assistant 及 Broker 状态前后稳定；
- 未访问 Home Assistant `.storage`，未下发节点凭据，未升级生产镜像。

当前 anonymous 运行时 Client ID 只保留指纹，不记录或公开原值：

```text
observed_client_id_fingerprint=97b32e78cb7b4ad3
target_client_id=gh-n1-a9f2f8
```

因此候选固件必须主动把 MQTT Client ID 切换为固定目标值；不能把当前历史 Client ID 当作认证身份。

## 3. 固定候选身份

```text
username=ghn_gh-n1-a9f2f8
client_id=gh-n1-a9f2f8
role=gh-node-greenhouse-gh-n1-a9f2f8
generation=1
```

密码不属于源码合同输入，不得进入 Git、Issue、聊天、构建日志、串口日志、API 日志、诊断实体或公开固件。

## 4. 八项固件能力

候选固件必须同时实现并验证：

1. **显式认证身份**：支持固定 username、password 和固定 Client ID；认证连接必须使用上述目标 Client ID。
2. **candidate/fallback 双槽**：认证候选配置与 anonymous 回退配置相互独立，私有材料不得进入公开 YAML 或公共编译产物。
3. **有界失败回退**：candidate 连续认证失败达到冻结阈值后自动切回 anonymous，不得无限重连阻塞。
4. **候选保留**：回退后不擦除 candidate，只允许输出代际与不可逆指纹。
5. **本地功能独立**：MQTT 认证、Broker、Wi-Fi 故障均不得影响传感器、LCD 五页、RS485、电源保护和本地告警。
6. **秘密脱敏**：密码不得出现在串口、API、崩溃输出、诊断实体、日志或公开制品。
7. **电源与网络故障恢复**：断电、重启、Wi-Fi 丢失、Broker 不可达后仍能恢复本地功能和 anonymous fallback。
8. **退役代际擦除**：迁移提交后可安全擦除退役凭据代际，且不得误删当前代际或 fallback。

每一项均必须先通过隔离测试，再通过真实 ESP32-C6 实板测试。

## 5. 状态机冻结

```text
LEGACY_ANONYMOUS
  -> CANDIDATE_STAGED
  -> CANDIDATE_CONNECTING
  -> AUTHENTICATED_OBSERVATION
  -> COMMITTED

CANDIDATE_CONNECTING
  -> AUTH_FAILURE_THRESHOLD
  -> FALLBACK_ANONYMOUS

AUTHENTICATED_OBSERVATION
  -> CONTINUITY_OR_ACL_FAILURE
  -> FALLBACK_ANONYMOUS
```

约束：

- `LEGACY_ANONYMOUS` 和 `FALLBACK_ANONYMOUS` 均使用现有兼容路径；
- `CANDIDATE_STAGED` 不得自动激活；
- candidate 激活必须受一次性事务控制；
- fallback 不修改 retained topic，不改变 HA device/entity identity；
- anonymous 在整个试点及观察期继续开启。

## 6. 隔离测试矩阵

候选实现进入实板前必须覆盖：

- 正确 username/password/Client ID 认证成功；
- 正确密码但错误 Client ID 被拒绝；
- 错误密码达到阈值后回退；
- Broker 不可达、连接超时和连接被踢后的回退；
- candidate 与 fallback 跨重启保存；
- fallback 后 candidate 仍存在但秘密不输出；
- 日志、诊断和崩溃输出秘密扫描；
- ACL：只能发布自身 ingress，只能订阅自身 out；
- 禁止发布 `$CONTROL/#`、`homeassistant/#`、`gh/v1/greenhouse/state/#`；
- 本地采集、LCD、RS485 在所有故障注入下持续。

隔离测试不得连接生产 T1，不得使用生产节点凭据。

## 7. 实板测试门

仅当候选实现和隔离矩阵通过后，才允许请求真实 ESP32-C6 实板测试。实板测试仍使用非生产秘密，至少验证：

- 断电、重启、Wi-Fi 丢失和 Broker 暂停；
- candidate 失败后 anonymous 自动恢复；
- LCD 五页和所有传感器持续运行；
- 固定 Client ID 精确；
- 串口和 ESPHome 日志无秘密；
- 现有约 20 个 HA 实体身份无变化。

## 8. 当前门状态

```text
ready_for_candidate_firmware_design=true
ready_for_candidate_firmware_build=false
ready_for_isolated_capability_test=false
ready_for_real_board_capability_test=false
ready_for_node_credential_generation=false
ready_for_live_apply=false
ready_for_anonymous_closure=false
```

当前阻塞项：

```text
candidate_firmware_implementation_missing
candidate_firmware_isolated_validation_pending
candidate_firmware_real_board_validation_pending
node_private_credential_delivery_path_unverified
node_anonymous_fallback_rollback_unverified
fresh_node_migration_authorization_not_created
authenticated_node_observation_window_pending
anonymous_closure_not_authorized
```

## 9. 安全边界

- 不重放 V70、V84～V92、V93～V96 或任何已消耗授权；
- 不访问 Home Assistant `.storage`；
- 不生成、读取、输出或下发节点明文密码；
- 不调用生产 Dynamic Security 控制命令；
- 不升级生产 Manager、Mosquitto、Home Assistant 或节点固件；
- 不关闭 anonymous；
- 后续任何真实 T1 或节点写操作必须建立新的只读证据、独立回滚和短时精确授权。
