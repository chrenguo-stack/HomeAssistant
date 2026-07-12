# gh-t1-broker-identity-activation-handoff-v1

## 1. 状态与目的

状态：Draft / M2.4g-5a  
关联：Issue #17、`gh-t1-homeassistant-mqtt-reconfigure-handoff-v1`、`gh-node-credential-delivery-v1`

本协议定义真实 T1 启用 Mosquitto Dynamic Security、创建独立服务与节点身份之前的私有交接包。

本阶段只完成：

- 复核既有 inactive migration stage；
- 重新执行精确 staged package 的隔离候选演练；
- 验证匿名兼容、Home Assistant 身份 ACL、client ID 绑定、bootstrap admin 移除和 retained state 恢复；
- 立即生成新的本机回退包；
- 固化后续 live activation 与 rollback 顺序。

本阶段不修改真实 Mosquitto、Home Assistant、greenhouse-manager 或节点。

## 2. 当前安全边界

交接包必须固定输出：

```text
apply_enabled = false
operator_action_authorized = false
ready_for_live_activation = false
current_services_modified = false
preserve_anonymous = true
anonymous_closure_enabled = false
```

交接目录存在不代表允许将材料复制到活动路径，也不代表允许重启 Mosquitto。

## 3. 前置条件

准备交接包前必须同时满足：

1. migration stage 通过 `verify_migration_stage`；
2. `activation-plan.json` 仍为 disabled；
3. stage manifest 指纹未漂移；
4. M2.4f client migration audit 仍完整通过；
5. retained baseline 可读；
6. exact stage rehearsal 使用 `--network none`；
7. 演练候选和故障注入候选均已清理；
8. live source、stage 和 source package 均未发生变化。

## 4. 候选演练验收

交接包只在以下演练证据全部为真时生成：

```text
exact_package_request_applied
exact_package_identity_matrix
client_id_binding
provisioning_control_only
bootstrap_admin_removed
provisioning_after_admin_removal
legacy_anonymous_after_admin_removal
anonymous_control_denied
retained_state_recovered
```

其中：

- Home Assistant 身份必须能够使用规定 client ID 完成 MQTT v5 权限矩阵；
- 错误 client ID 必须拒绝；
- Home Assistant 不得写入 canonical 或 ingress；
- 非 provisioning 身份不得访问 `$CONTROL`；
- anonymous 仍可使用既有业务 Topic，但不得访问 Dynamic Security 控制面；
- bootstrap admin 删除后 provisioning 身份仍可管理候选；
- retained state 必须从回退快照恢复。

## 5. 私有交接目录

`prepare` 生成模式为 `0700` 的目录：

```text
greenhouse-broker-identity-handoff-<UTC>-<token>/
├── manifest.json
├── activation-plan.json
├── operator-runbook.txt
├── material/
│   ├── broker/
│   │   ├── dynsec-request.json
│   │   └── mosquitto-plugin.conf
│   ├── bootstrap/
│   │   ├── dynsec-password-init
│   │   └── admin-client.conf
│   ├── provisioning/
│   │   ├── mosquitto-client.conf
│   │   └── identity.json
│   └── homeassistant/
│       ├── mqtt-update.json
│       └── identity.json
└── rollback/
    └── greenhouse-t1-rollback-<UTC>-<token>.tar.gz
```

所有文件必须为 `0600`。目录不得提交 Git、上传 Issue、复制到普通日志或离开 T1。

## 6. Fresh rollback

交接包必须在准备时调用真实 T1 backup 工具，生成并校验新的 rollback archive。

该回退包用于后续 Broker live activation 失败时恢复：

- Mosquitto 配置；
- Mosquitto 数据；
- greenhouse-manager 数据。

Fresh rollback 只是必要条件，不构成 live apply 授权。

## 7. Live binding

交接包必须记录：

- stage 名称；
- stage manifest SHA-256；
- stage readiness 中的 live Broker config SHA-256；
- fresh rollback 文件名、大小和 SHA-256；
- exact candidate rehearsal 的布尔证据。

live activation 前必须重新读取真实文件并与这些指纹比较。任一漂移都要求废弃交接包并重新准备。

## 8. 后续 live activation 顺序

未来独立授权门必须严格按以下顺序执行：

1. 重新验证 live config、容器状态和交接包；
2. 重新验证 fresh rollback；
3. 在保持 anonymous group 的条件下安装 Dynamic Security；
4. 只重启 Mosquitto；
5. 验证原匿名节点 telemetry、availability 和 retained state；
6. 验证 Home Assistant 独立身份 MQTT v5 CONNECT 与 ACL；
7. 验证 provisioning 身份后删除 bootstrap admin；
8. 运行只读 post-activation audit；
9. 通过后才允许生成新的 Home Assistant reconfigure handoff。

本协议没有实现上述 live 写入动作。

## 9. 回退顺序

任一 live activation 检查失败时必须：

1. 停止继续迁移 manager、Home Assistant 或节点；
2. 使用 fresh rollback 恢复 Mosquitto 配置和数据；
3. 重启 Mosquitto；
4. 验证 anonymous legacy path；
5. 验证 retained state；
6. 保持 Home Assistant 使用旧匿名连接；
7. 记录失败原因后重新生成 migration package/stage。

不得在失败状态下关闭匿名访问。

## 10. 报告脱敏

普通 JSON 报告不得包含：

- dynsec request 原文；
- bootstrap password；
- provisioning password；
- Home Assistant username、password 或 client ID；
- Dynamic Security 控制请求；
- rollback archive 内容。

允许报告：

- 文件相对路径；
- SHA-256；
- 布尔验收结果；
- stage 和 handoff 目录名称；
- `apply_enabled=false` 等安全状态。

## 11. verify

`verify` 必须检查：

- 根目录模式为 `0700`；
- manifest、plan 和所有 inventory 文件为 `0600`；
- 相对路径无目录穿越；
- 文件大小与 SHA-256 匹配；
- fresh rollback 可通过正式 backup verifier；
- preserve-anonymous 和 disabled flags 未改变。

verify 只验证本地交接材料，不检查或修改 live Broker。

## 12. 下一门

下一开发门是 M2.4g-5b：显式授权的真实 Broker activation 与 post-activation audit。

在用户再次明确许可真实 T1 写入前，必须保持：

```text
broker_identity_not_activated
homeassistant_operator_reconfigure_required
node_credential_delivery_path_unverified
```
