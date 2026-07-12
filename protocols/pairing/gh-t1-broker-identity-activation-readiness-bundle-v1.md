# gh-t1-broker-identity-activation-readiness-bundle-v1

状态：M2.4g-5n Draft

## 1. 目的

在创建单次操作员授权或安装生产执行器之前，将已经通过的真实 T1 只读验证结果冻结为一个私有、不可执行、无密钥的 readiness bundle。

该 bundle 仅用于回答：当前 Broker、Compose、bind mount、Home Assistant MQTT 目标和迁移材料是否仍属于同一组已验证输入。

## 2. 输入

所有输入文件必须：

- 位于同一个 `greenhouse-m2-runtime-bindings-*` 私有目录；
- 为普通文件且权限精确为 `0600`；
- 不得为符号链接；
- 分别通过已有 verifier。

输入包括：

1. production driver contract；
2. production executor contract；
3. runtime binding manifest；
4. production driver preflight；
5. Home Assistant MQTT target gate。

## 3. 绑定字段

bundle 必须绑定：

- production driver contract SHA-256；
- production executor contract SHA-256；
- mount binding SHA-256；
- runtime binding manifest SHA-256；
- production driver preflight SHA-256；
- Home Assistant target gate SHA-256；
- Broker runtime 指纹；
- Home Assistant 目标类型、目标指纹、config entry 指纹和 storage SHA-256。

runtime binding manifest 必须仍在允许的新鲜度窗口内。

## 4. 激活范围

bundle 只能声明以下范围：

- 仅激活 Broker 身份层；
- 保持匿名兼容；
- 成功路径最多预期一次 Mosquitto 重启；
- 回退路径可能增加一次重启；
- 不在同一事务中关闭匿名访问；
- 不在同一事务中修改 Home Assistant；
- 不在同一事务中向真实节点交付凭据。

## 5. 输出与权限

完整 bundle 必须：

- 原子写入；
- 文件权限为 `0600`；
- 位于输入所在私有目录；
- 包含自身 canonical JSON SHA-256；
- 不包含真实宿主机路径或任何密码、token、bootstrap secret。

stdout 只允许输出文件名、SHA-256 和脱敏指纹。

## 6. 强制阻塞条件

bundle 生成后仍必须保持：

- `operator_decision_required=true`；
- `single_use_authorization_created=false`；
- `production_driver_installed=false`；
- `production_executor_available=false`；
- `execution_enabled=false`；
- `apply_enabled=false`；
- `operator_action_authorized=false`；
- `ready_for_live_activation=false`；
- `current_services_modified=false`；
- `preserve_anonymous=true`；
- `anonymous_closure_enabled=false`。

固定 blockers：

1. `explicit_operator_decision_required`；
2. `production_driver_not_installed`；
3. `single_use_authorization_not_created`；
4. `homeassistant_official_mqtt_ui_config_flow_pending`；
5. `real_node_credential_delivery_unverified`。

## 7. 禁止行为

本阶段禁止：

- 创建或 claim 操作员授权；
- 安装或调用 production driver；
- 修改 Mosquitto 配置或 Dynamic Security 状态；
- 重启任何服务；
- 修改 Home Assistant `.storage`；
- 写入 ESP32-C6 节点凭据；
- 提供 `--authorize`、`--execute`、`--apply` 或 `--live` CLI 入口。
