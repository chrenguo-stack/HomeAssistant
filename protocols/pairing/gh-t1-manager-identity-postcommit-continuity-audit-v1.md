# T1 Manager 身份迁移提交后持续性只读审计 V1

状态：M2.4g-6w Draft

## 1. 目的

本协议定义 `greenhouse-manager` 独立 MQTT 身份迁移已经提交后，如何在不修改任何服务、不复用旧授权、不重新执行生产事务的前提下，验证迁移结果仍然连续有效。

该审计位于 Manager 身份迁移终态与 Broker Dynamic Security 预激活 fresh evidence 之间。审计通过只表示可以进入新的 Broker 只读证据重建，不表示允许激活 Dynamic Security、重配置 Home Assistant、下发节点凭据或关闭 anonymous。

## 2. 不可变边界

审计必须满足：

- 只允许读取私有 transaction workspace、Docker 运行时元数据、`/proc` 网络状态、Manager 日志和精确 retained topic；
- 不创建、claim、consume 或复用任何 authorization；
- 不调用 Manager production executor；
- 不写入 transaction、Compose、secret、Mosquitto、Home Assistant 或节点文件；
- 不重启、重建或停止任何容器；
- 不执行 MQTT PUBLISH；
- 保持 `preserve_anonymous=true`、`anonymous_closure_enabled=false`；
- 保持 `node_credentials_delivered=false`；
- 不读取或编辑 Home Assistant `.storage`；
- 输出不得包含密码、完整凭据、私有路径、container ID 或 image ID。

## 3. 输入绑定

审计输入为：

1. 已提交的 Manager production transaction workspace；
2. `system_id`；
3. 一个已知真实 `node_id`；
4. 该节点的精确 Home Assistant Discovery topic；
5. MQTT 端口和有界超时参数。

Transaction workspace 必须是私有目录，`journal.json` 必须为 mode `0600`，并满足：

- schema 为 `gh.m2.t1-manager-identity-production-journal/1`；
- `phase=committed`；
- target 仅为 `greenhouse-manager`；
- Mosquitto、Home Assistant 和节点均不在允许修改范围；
- anonymous 保留且 anonymous closure 禁用。

审计还必须在 workspace 中唯一找到与 journal 的 transaction ID 和 authorization ID 同时绑定的成功 execution result。

## 4. 持续性检查

### 4.1 Transaction 连续性

- journal 仍为 committed 终态；
- execution result 仍证明 production execution、postactivation 和 Manager identity migration 成功；
- execution result 仍证明 Manager runtime image preserved；
- 未记录 rollback completed；
- 审计前后 transaction workspace 全量内容摘要不变。

### 4.2 容器连续性

- `greenhouse-manager`、`mosquitto`、`homeassistant` 均运行；
- 三者 restart count 均为 0；
- Manager 当前启动时间必须处于 transaction created 与 committed 时间之间，证明仍是提交事务创建的容器；
- Mosquitto 和 Home Assistant 当前启动时间不得晚于 transaction created 时间；
- 审计前后三个容器的 ID、image、started-at、restart count 和运行状态必须完全一致；
- ID 和 image 只在进程内比较，不得输出。

### 4.3 Manager 认证身份连续性

- MQTT username 和 Client ID 非空；
- `GH_MQTT_PASSWORD_FILE` 精确指向 `/run/secrets/gh_manager_mqtt_password`；
- inline `GH_MQTT_PASSWORD` 为空或不存在；
- password mount 唯一且只读；
- mount source 是 mode `0600` 的普通文件且不是 symlink；
- password source UID/GID 与 Manager 进程有效 UID/GID 一致；
- Manager 到 MQTT 端口的 established socket 在两次采样中保持相同 inode。

### 4.4 数据路径连续性

审计只允许匿名订阅以下精确 retained topic：

- canonical telemetry；
- availability；
- Home Assistant Discovery。

必须验证：

- canonical `node_id` 未变化；
- availability 属于 `online` 或 `unavailable`；
- Discovery 的 device identifier、component unique ID、state topic 与 availability topic 仍绑定同一节点；
- Manager 日志仍包含 ingress subscription、canonical subscription 和该节点 Discovery publication；
- retained 读取成功同时证明 anonymous compatibility 仍存在。

## 5. 成功输出

成功输出 schema：

```text
gh.m2.t1-manager-identity-postcommit-continuity-audit/1
```

必须包含：

```text
read_only=true
continuity_audit_passed=true
transaction_phase=committed
manager_identity_migrated=true
runtime_manager_image_preserved=true
runtime_manager_upgrade_performed=false
mosquitto_modified=false
homeassistant_modified=false
nodes_modified=false
node_credentials_delivered=false
preserve_anonymous=true
anonymous_closure_enabled=false
current_services_modified=false
transaction_files_modified=false
authorization_reused=false
production_execution_invoked=false
manual_recovery_required=false
ready_for_broker_preactivation_fresh_evidence=true
```

## 6. 失败语义

任何输入缺失、绑定漂移、运行状态变化、认证环境异常、mount/ownership 异常、socket 不稳定、retained/topic 身份变化、日志证据缺失或审计期间文件/容器变化，都必须 fail closed，返回非零退出码。

失败不得触发自动修复、回滚、容器重启或重新执行旧事务。后续处理必须先进行人工只读诊断。
