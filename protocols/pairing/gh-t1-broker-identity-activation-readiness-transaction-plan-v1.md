# gh-t1-broker-identity-activation-readiness-transaction-plan-v1

状态：M2.4g-5p Draft

## 1. 目的

在任何授权 claim、production adapter 安装或真实 Broker 变更之前，将有效的 bundle-bound authorization 与 activation readiness bundle 再次绑定为一份不可执行的私有事务计划。

本阶段只证明未来事务的输入、顺序、回退和后续人工步骤已经冻结，不提供 live apply。

## 2. 输入

输入必须包括：

1. mode `0600` 的 bundle-bound authorization；
2. mode `0600` 的 activation readiness bundle；
3. 独立的 `greenhouse-m2-activation-plans*` mode `0700` 输出目录。

authorization 与 bundle 必须重新验证，authorization 必须仍处于有效期内、尚未消费，并完整绑定以下值：

- bundle SHA-256；
- production driver contract SHA-256；
- production executor contract SHA-256；
- mount binding SHA-256；
- runtime binding manifest SHA-256；
- production driver preflight SHA-256；
- Home Assistant target gate SHA-256；
- Broker runtime 指纹；
- Home Assistant target/config-entry/storage 指纹；
- activation scope。

## 3. 事务合同

事务计划必须冻结：

- 授权必须在未来执行入口中通过同文件系统 hardlink 后 unlink 原名称的方式原子 claim；
- 必须建立 mode `0600` 私有事务日志；
- mutation 后必须执行 postactivation audit；
- 任意失败都必须强制 rollback；
- 成功路径只允许一次 Mosquitto 重启；
- rollback 可能额外触发一次 Mosquitto 重启；
- Home Assistant 官方 MQTT 重配置只能发生在 Broker 身份激活成功后；
- 真实节点凭据交付只能发生在 Broker 身份激活成功后；
- 本事务禁止关闭匿名访问。

## 4. 输出

完整事务计划必须：

- 原子写入；
- 文件权限为 `0600`；
- 包含 authorization 全文 canonical JSON SHA-256，但不复制 token；
- 包含自身 canonical JSON SHA-256；
- 不包含完整宿主机路径；
- 不包含任何密码、bootstrap secret 或 authorization token。

stdout 只允许输出文件名、SHA-256、authorization ID、过期时间和安全状态。

## 5. 固定状态

计划生成和验证后必须保持：

- `transaction_plan_ready=true`；
- `authorization_valid=true`；
- `authorization_claimed=false`；
- `claim_enabled=false`；
- `production_transaction_adapters_installed=false`；
- `production_executor_available=false`；
- `execution_enabled=false`；
- `apply_enabled=false`；
- `operator_action_authorized=true`；
- `ready_for_live_activation=false`；
- `current_services_modified=false`；
- `preserve_anonymous=true`；
- `anonymous_closure_enabled=false`。

固定 blockers：

1. `production_transaction_adapters_not_installed`；
2. `authorization_not_claimed`；
3. `production_executor_disabled`；
4. `homeassistant_official_mqtt_ui_config_flow_pending`；
5. `real_node_credential_delivery_unverified`。

## 6. 禁止行为

本阶段禁止：

- claim 或消费 authorization；
- 安装或调用 production transaction adapters；
- 修改 Mosquitto 配置、数据或 Dynamic Security 状态；
- 重启任何容器；
- 修改 Home Assistant；
- 向真实 ESP32-C6 节点写入凭据；
- 提供 `--claim`、`--execute`、`--apply` 或 `--live` CLI 入口。
