# gh-t1-broker-identity-host-replica-adapters-v1

状态：M2.4g-5i Draft

## 目标

本协议定义 production adapter skeleton 之后的第一组可执行适配器。它们只能作用于系统临时目录中的**显式标记宿主机副本**，用于验证真实生产路径所需的原子文件替换、fsync、驱动调用顺序、强制回退与故障注入，不得连接或修改真实 T1。

## 输入

必须绑定：

1. 已验证的 production executor contract；
2. 已验证的 production adapter skeleton；
3. 与 contract material SHA-256 一致的 activation handoff；
4. 位于系统临时目录中的 replica root。

replica root 必须：

- 为 mode 0700 的普通目录；
- 不是符号链接；
- 位于 `tempfile.gettempdir()` 解析后的目录内；
- 包含 mode 0600 的 `.gh-m2-host-replica.json`；
- marker 声明 `replica_only=true`；
- marker 的 contract SHA-256 与 mount-binding SHA-256 与 skeleton 完全一致；
- 包含私有的 `mosquitto/config` 与 `mosquitto/data`；
- `mosquitto.conf` SHA-256 与 contract baseline 完全一致；
- 初始不存在 `dynamic-security.json`。

## 驱动边界

适配器不得自行运行 Docker、systemd、SSH 或真实 Broker 命令。运行期行为必须通过注入的 `ReplicaBrokerDriver` 完成：

- restart Mosquitto；
- 等待 Dynamic Security 状态；
- 应用精确请求；
- 验证 provisioning identity；
- 删除 bootstrap admin；
- 执行 postactivation audit；
- rollback 后重启副本 Broker；
- 验证匿名 retained 状态。

默认 CLI 只生成计划，不提供 execute/enable/apply/live 参数。

## 原子文件事务

副本 mutation 必须：

1. 在目标文件同一目录创建临时文件；
2. 完整写入并 `fsync(file)`；
3. 设置目标权限；
4. 使用 `os.replace` 替换；
5. `fsync(parent directory)`；
6. 仅修改副本的 `mosquitto.conf` 与 `dynsec-password-init`；
7. 使用 handoff 中精确绑定的 plugin material 与 Dynamic Security request。

## 强制回退

任何 mutation 开始后的故障必须触发 rollback。rollback 使用 mutation 前完整 `mosquitto` 目录副本恢复：

- 准备同文件系统 restore 目录；
- 将当前副本移入 quarantine；
- 将 restore 目录替换到正式副本路径；
- fsync replica root；
- 调用注入驱动重启；
- 验证匿名 retained 状态；
- 校验完整文件、目录、mode 与 SHA-256 inventory。

rollback 失败必须作为终止故障显式报告，不得返回成功。

## 故障注入

至少覆盖：

- `after_config_replace`；
- `after_secret_replace`；
- `after_restart`；
- `after_state_wait`；
- `after_request`；
- `after_provisioning`；
- `after_bootstrap_delete`；
- `postactivation`；
- `rollback_incomplete`。

除 `rollback_incomplete` 外，所有 mutation 后故障均必须恢复完整 baseline。

## 安全状态

无论副本测试是否成功，报告必须保持：

- `replica_only=true`；
- `real_t1_target_allowed=false`；
- `docker_commands_available=false`；
- `production_executor_available=false`；
- `execution_enabled=false`；
- `apply_enabled=false`；
- `operator_action_authorized=false`；
- `ready_for_live_activation=false`；
- `current_services_modified=false`；
- `preserve_anonymous=true`；
- `anonymous_closure_enabled=false`。

## 未覆盖范围

本阶段不验证：

- 真实 Mosquitto 容器重启；
- 真实 Dynamic Security plugin 初始化；
- Home Assistant UI/config-flow；
- greenhouse-manager 真实凭据切换；
- 实体 ESP32-C6 节点凭据交付；
- 匿名访问关闭。
