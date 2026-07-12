# gh-t1-broker-identity-host-replica-fault-matrix-v1

状态：M2.4g-5j Draft

## 目标

本协议定义宿主机副本适配器的完整故障矩阵。每个故障场景必须在独立的系统临时目录副本中执行，使用内存 Broker 驱动，不得复用真实 T1、真实 Docker 容器或上一场景留下的工作目录。

## 输入

矩阵必须先通过 M2.4g-5i host replica plan，并确认：

- `replica_transaction_ready=true`；
- `replica_only=true`；
- `real_t1_target_allowed=false`；
- `docker_commands_available=false`；
- `current_services_modified=false`。

输入 replica template 只能被读取和复制，矩阵前后必须使用完整 tree inventory 证明模板未变化。

## 场景隔离

每个故障阶段必须：

1. 新建独立的系统临时目录；
2. 使用 `copy2` 复制完整 replica template；
3. 在复制品上执行一次事务；
4. 验证回退或终止故障；
5. 删除整个场景目录；
6. 不向报告写入真实路径或凭据。

## 内存驱动

矩阵默认使用 `InMemoryReplicaBrokerDriver`。该驱动：

- 不连接 Broker；
- 不运行 Docker、systemd、SSH 或网络命令；
- 只记录无秘密事件名；
- 对 Dynamic Security 请求只保留 canonical JSON SHA-256；
- 不保留用户名、密码或请求正文。

## 必须覆盖的故障

矩阵必须精确覆盖：

- `after_config_replace`；
- `after_secret_replace`；
- `after_restart`；
- `after_state_wait`；
- `after_request`；
- `after_provisioning`；
- `after_bootstrap_delete`；
- `postactivation`；
- `rollback_incomplete`。

前八项必须同时满足：

- `fault_injected=true`；
- `rollback_completed=true`；
- 完整 replica inventory 与模板相同；
- `scenario_isolated=true`。

`rollback_incomplete` 必须显式报告 rollback failure，不得返回成功。

## 输出

完整矩阵成功时必须报告：

- `all_faults_exercised=true`；
- `forced_rollback_verified=true`；
- `rollback_failure_explicit=true`；
- `template_immutable=true`；
- `scenario_isolation_verified=true`。

同时继续保持：

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

本阶段仍不验证真实 Mosquitto 重启、真实 Dynamic Security API、Home Assistant 官方 UI/config-flow、greenhouse-manager 真实凭据切换或实体节点凭据交付。
