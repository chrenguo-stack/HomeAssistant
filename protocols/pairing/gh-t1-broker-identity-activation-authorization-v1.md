# gh-t1-broker-identity-activation-authorization-v1

## 1. 状态与范围

状态：Draft / M2.4g-5c（一次性授权材料）  
关联：Issue #17、`gh-t1-broker-identity-activation-handoff-v1`、`gh-t1-broker-identity-preactivation-and-postaudit-v1`

本协议定义真实 T1 Broker 身份激活前的独立操作员授权材料。授权材料只证明：指定 activation handoff、migration stage、Home Assistant MQTT 目标与当前配置指纹已经由操作员明确确认，可提交给后续 live activation executor 再次验证。

本阶段不实现 live activation executor，并且不执行以下动作：

- 不修改活动 `mosquitto.conf`；
- 不创建或替换活动 Dynamic Security state；
- 不停止、重建或重启任何容器；
- 不修改 Home Assistant MQTT config entry；
- 不迁移 greenhouse-manager；
- 不向节点交付凭据；
- 不关闭匿名兼容；
- 不消费或删除授权文件。

因此，即使授权文件创建成功，普通结果仍必须保持：

```text
apply_enabled = false
ready_for_live_activation = false
current_services_modified = false
preserve_anonymous = true
anonymous_closure_enabled = false
```

## 2. 三步接口

### 2.1 request

`request` 必须重新运行并验证 disabled preactivation gate。只有以下条件全部成立时，才可输出授权请求：

1. activation handoff 仍完整且 fresh rollback 可验证；
2. migration stage 与 handoff 绑定未漂移；
3. live Broker 配置、匿名兼容、retained state 与容器运行状态仍符合 preactivation 基线；
4. Home Assistant 目标仍为经审计的 loopback；
5. MQTT entry 指纹与 `.storage` SHA-256 未漂移；
6. preactivation gate 仍输出 `preconditions_ready=true`；
7. preactivation gate 仍输出所有写入与授权标志为 false。

请求返回一个与 handoff manifest SHA-256 绑定的精确确认字符串：

```text
AUTHORIZE-M2-BROKER:<handoff-name>:<manifest-sha256-prefix>
```

请求本身不创建授权文件，且必须输出：

```text
operator_action_authorized = false
apply_enabled = false
ready_for_live_activation = false
current_services_modified = false
```

### 2.2 authorize

`authorize` 仅在调用者逐字提供当前 request 返回的确认字符串后运行。它必须再次执行完整 request/preactivation 验证，随后在私有目录中生成一个短时、单次授权文件。

授权文件必须：

- 所在目录模式为 `0700`；
- 文件模式为 `0600`；
- 不得为符号链接；
- 使用原子替换写入；
- 具有 60 至 3600 秒的有效期，默认 900 秒；
- 标记 `single_use=true`、`consumed=false`；
- 包含高熵随机 token，但普通 stdout 报告不得输出 token；
- 以 token 的 SHA-256 派生公开 authorization ID；
- 明确 `operator_action_authorized=true`；
- 同时保持 `apply_enabled=false` 和 `ready_for_live_activation=false`。

`operator_action_authorized=true` 只说明操作员已签发一次性授权材料，不代表本模块可以执行 Broker 写入。

### 2.3 verify

`verify` 必须拒绝过期、已消费、公开权限、符号链接、内容篡改或绑定漂移的授权文件。验证必须绑定以下全部值：

- activation handoff 目录名；
- handoff manifest SHA-256；
- migration stage manifest SHA-256；
- Home Assistant Broker target kind；
- Broker target fingerprint；
- MQTT config-entry fingerprint；
- Home Assistant `.storage` SHA-256；
- expected retained topic 的 SHA-256 指纹；
- authorization token 与 authorization ID；
- 创建时间、失效时间、单次使用状态；
- `preserve_anonymous=true`；
- `anonymous_closure_enabled=false`。

验证成功也必须保持：

```text
apply_enabled = false
ready_for_live_activation = false
current_services_modified = false
```

## 3. 后续 live activation executor 的强制要求

未来的 live activation executor 必须是不同模块和不同命令，不得复用本授权模块承担写入。executor 在任何活动路径写入前必须：

1. 重新验证 handoff、fresh rollback 与授权文件；
2. 重新运行 disabled preactivation gate；
3. 确认授权未过期、未消费且全部指纹未漂移；
4. 在活动文件写入前原子标记或原子占用授权，防止重复执行；
5. 只安装既定 Dynamic Security plugin 配置、state 与身份；
6. 保留 `allow_anonymous true` 及 legacy anonymous 权限；
7. 只允许 Mosquitto 发生预期重启；
8. 验证 provisioning identity 后删除 bootstrap admin；
9. 立即运行正式 postactivation audit；
10. 任一阶段失败时自动使用 handoff 中的 fresh rollback，恢复 Broker 配置与数据并验证匿名 retained 链路。

在 executor、自动回退和故障注入测试全部合入且再次通过真实 T1 门禁之前，不得向操作员提供 live activation 命令。

## 4. 秘密与日志

普通请求、创建和验证报告不得包含：

- authorization token；
- Broker、Home Assistant、provisioning、bootstrap 或节点密码；
- MQTT 用户名与 client ID 原值；
- Dynamic Security request 原文；
- retained payload；
- handoff 或 rollback 文件内容。

允许输出：

- authorization ID；
- handoff 名称；
- SHA-256 与截断指纹；
- 到期时间；
- 布尔安全状态；
- 授权文件本机路径。

授权文件属于 T1 本机敏感材料，不得复制到 Git、聊天、Home Assistant 实体或普通日志。

## 5. 当前阶段结论

M2.4g-5c 只建立“操作员明确确认”与未来 live executor 之间的可验证边界。它不解除以下阻断：

- `live_activation_executor_not_available`；
- `automatic_rollback_not_verified`；
- `homeassistant_operator_reconfigure_required`；
- `node_credential_delivery_path_unverified`。

下一步是实现完全独立、默认拒绝执行的 live activation transaction，并在隔离快照中完成成功、写入中断、重启失败、postactivation 失败和 rollback 失败等故障注入；随后才允许申请新的真实 T1 显式门禁。
