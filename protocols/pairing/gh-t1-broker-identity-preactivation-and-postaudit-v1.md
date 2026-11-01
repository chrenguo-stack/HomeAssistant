# gh-t1-broker-identity-preactivation-and-postaudit-v1

## 1. 状态与范围

状态：Draft / M2.4g-5b（仓库侧门禁模型）  
关联：Issue #17、`gh-t1-broker-identity-activation-handoff-v1`、`gh-t1-homeassistant-mqtt-reconfigure-handoff-v1`

本协议定义真实 T1 Broker 身份激活前的最后只读门，以及一次独立、显式授权的 Broker 激活完成后必须立即执行的只读审计。

本阶段代码不执行以下动作：

- 不复制 Dynamic Security 文件到活动 Mosquitto 路径；
- 不修改 `mosquitto.conf`；
- 不重启 Mosquitto、Home Assistant 或 greenhouse-manager；
- 不修改 Home Assistant MQTT config entry；
- 不向节点交付凭据；
- 不关闭匿名兼容。

真实 Broker 写入仍必须由后续单独的严格实机门禁授权。

## 2. Preactivation gate

preactivation gate 必须重新绑定并验证：

1. activation handoff 完整且通过正式 verifier；
2. fresh rollback 仍可验证；
3. migration stage 名称与 stage manifest SHA-256 未漂移；
4. live Broker config SHA-256 与 stage、handoff plan 一致；
5. M2.4f client migration audit 仍完整通过；
6. Dynamic Security 尚未启用且 state 文件仍不存在；
7. anonymous legacy path 仍启用；
8. retained baseline 仍可读取；
9. 没有遗留候选容器；
10. Home Assistant 目标仍为经实机审计的 loopback；
11. Broker target、MQTT entry 与 `.storage` 指纹未漂移；
12. Mosquitto、Home Assistant、greenhouse-manager 均运行且 restart count 为 0。

当前真实 T1 的绑定基线为：

```text
target_kind = loopback
target_fingerprint = 12ca17b49af22894
mqtt_entry_fingerprint = 9dda2c31088e933e
```

`.storage` SHA-256 必须在执行门禁时由调用者显式提供，禁止在文档或日志中以可变默认值代替。

preactivation gate 即使全部通过，也必须输出：

```text
preconditions_ready = true
apply_enabled = false
operator_action_authorized = false
ready_for_live_activation = false
current_services_modified = false
preserve_anonymous = true
anonymous_closure_enabled = false
```

`preconditions_ready=true` 只表示具备申请下一道显式实机授权的条件，不代表已授权写入。

## 3. 独立 live activation 的边界

未来 live activation 必须是单独脚本、单次执行、失败即停，并满足：

- 执行前再次验证 preactivation gate；
- 仅启用 Dynamic Security 和既定身份；
- 保留 anonymous legacy role/group；
- 仅允许 Mosquitto 发生预期重启；
- Home Assistant、manager 和节点在该步保持旧连接；
- bootstrap admin 必须在 provisioning identity 验证成功后删除；
- 任一检查失败立即进入 fresh rollback；
- 不得在本步骤关闭 anonymous access。

本协议不实现该写入脚本。

## 4. Postactivation audit

live activation 返回后必须立即执行 postactivation audit。审计为只读，但允许在 Mosquitto 容器 `/tmp` 创建仅存续于单条命令期间的 `0600` 客户端配置文件，并通过 shell trap 删除。不得写入活动配置或数据目录。

必须验证：

1. Mosquitto、Home Assistant、greenhouse-manager 均运行且 restart count 为 0；
2. live Broker config 已从 preactivation baseline 发生预期变化；
3. Dynamic Security plugin 已配置；
4. `/mosquitto/data/dynamic-security.json` 存在且模式为 `0600`；
5. anonymous compatibility 仍启用；
6. 匿名客户端仍可读取既有 retained telemetry；
7. Home Assistant 独立身份可使用 MQTT v5 和规定 client ID 读取 retained telemetry；
8. 同一凭据使用错误 client ID 必须被拒绝；
9. provisioning identity 可读取 Dynamic Security control response；
10. bootstrap admin 已被拒绝；
11. anonymous client 不得访问 `$CONTROL/dynamic-security/v1`。

## 5. 审计结果

全部检查通过：

```text
activation_verified = true
rollback_required = false
broker_identity_activated = true
ready_for_homeassistant_reconfigure_handoff = true
operator_action_authorized = false
ready_for_live_apply = false
preserve_anonymous = true
```

此结果仅解除 `broker_identity_not_activated`。它不自动授权 Home Assistant UI 操作；必须重新生成 Home Assistant MQTT reconfigure handoff，并执行独立 UI 门禁。

任一检查失败：

```text
activation_verified = false
rollback_required = true
broker_identity_activated = false
ready_for_homeassistant_reconfigure_handoff = false
```

此时禁止迁移 Home Assistant、greenhouse-manager 或节点。

## 6. 回退要求

postactivation audit 失败时必须使用 activation handoff 中的 fresh rollback：

1. 停止后续迁移；
2. 恢复 Mosquitto 配置与数据；
3. 重启 Mosquitto；
4. 验证 anonymous legacy path；
5. 验证 retained state；
6. 确认 Home Assistant、manager 与节点仍使用旧连接；
7. 重新生成 migration package、stage 和 activation handoff。

不得通过保留失败的 Dynamic Security 状态继续尝试 Home Assistant 重配置。

## 7. 日志与秘密

preactivation 和 postactivation 普通报告不得包含：

- Broker、Home Assistant、provisioning 或 bootstrap 密码；
- Home Assistant 用户名或 client ID 原值；
- provisioning 配置原文；
- Dynamic Security request/response 原文；
- retained payload；
- rollback archive 内容。

允许输出：

- 指纹和 SHA-256；
- 布尔检查结果；
- 容器 state、restart count 与 image ID；
- `rollback_required`；
- 已脱敏的阶段状态。

## 8. 下一阶段

完成仓库侧 preactivation/postactivation 模型后，下一步才是：

1. 在真实 T1 生成并验证新的 Broker activation handoff；
2. 执行 disabled preactivation gate；
3. 由用户明确授权一次 Broker live activation；
4. 立即执行 postactivation audit；
5. 审计通过后重新生成 Home Assistant MQTT reconfigure handoff；
6. 最后才进入 Home Assistant 官方 UI 重配置。

节点凭据交付仍保持独立阻断，不得与 Broker 或 Home Assistant 迁移合并执行。
