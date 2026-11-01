# greenhouse-manager 身份迁移生产运行时探针 V1

- 阶段：M2.4g-6n
- 状态：Draft
- 范围：6l 编排器、6m 宿主机 adapters 与真实 `greenhouse-manager` 运行时之间的只读业务验证
- 关联：Issue #17、#94、#96、#98；6e～6m

## 1. 目的

本协议定义在 manager-only 身份迁移中，如何在不发布测试消息、不修改 Broker retained state、不编辑 Home Assistant `.storage` 的前提下，证明新容器实际使用独立 MQTT 身份连接，并继续接收真实节点入口、发布规范状态、availability 和 Discovery。

6n 同时定义受限 integration factory。该 factory 只把 6l 编排器连接到 6m adapters/driver，不安装 execute CLI，也不授权真实 T1 apply。

## 2. 探针输入

必须由调用方显式提供并验证：

- `SYSTEM_ID`；
- 一个当前持续上报的真实 `NODE_ID`；
- 该节点的一个精确 Home Assistant Discovery topic；
- manager production host binding；
- 6m 已绑定的 manager username、Client ID、password source 和容器内 password target；
- MQTT 端口，研发 T1 当前为 1883；
- MQTT socket/即时启动日志等待窗口 `timeout_s`，研发 T1 当前为 35 秒；
- 被动等待真实节点下一轮遥测的独立窗口 `telemetry_timeout_s`，研发 T1 当前为 90 秒；
- 只读 retained reader；
- 只允许执行 `docker inspect greenhouse-manager` 的 command runner。

不得使用通配 Discovery topic，不得把密码或完整身份写入普通报告。

## 3. 迁移前连续性基线

在授权 claim 和任何文件写入之前，探针必须匿名只读获取：

1. `gh/v1/<sid>/state/<node_id>/telemetry`；
2. `gh/v1/<sid>/state/<node_id>/availability`；
3. 精确 Discovery config topic。

基线至少冻结：

- canonical payload 中的 `node_id`；
- Discovery `device.identifiers`；
- 所有 component 或顶层 `unique_id`；
- `state_topic`；
- availability 配置。

传感器数值、时间戳、manager 版本和节点 firmware 允许自然变化，不作为身份连续性摘要。

## 4. 认证运行时验证

迁移后只通过 `docker inspect greenhouse-manager` 获取：

- container ID；
- `State.Pid`、`StartedAt`、running 状态和 restart count；
- Config.Env；
- Mounts；
- Docker JSON `LogPath`。

必须满足：

```text
GH_MQTT_USERNAME == bound manager username
GH_MQTT_CLIENT_ID == bound manager Client ID
GH_MQTT_PASSWORD_FILE == bound container password target
GH_MQTT_PASSWORD is empty
```

且 password source 必须是已绑定 host target、普通私有文件，并以只读 bind mount 映射到容器目标。

## 5. 稳定 MQTT 会话

探针读取 `/proc/<manager-pid>/net/tcp` 和 `tcp6`，要求：

- 在 `timeout_s` 有界窗口内等待连接到绑定 MQTT 端口的 `ESTABLISHED` socket 出现，首次采样为空不得立即失败；
- 每次使用 `time.monotonic()` 计算剩余时间，并按 `poll_interval_s` 休眠，不得忙等或依赖固定 shell sleep；
- socket 出现后，两次间隔采样中至少一个 socket inode 保持一致；
- socket 出现后消失或 inode 改变时，只要尚未超时就继续轮询，直到新的会话稳定；
- 错误远端端口、非 `ESTABLISHED` 状态或超时后才出现的 socket 不得通过；
- `/proc` 路径必须由本次 `docker inspect` 的正整数 PID 构造；
- 只读，不执行 namespace、shell、`docker exec` 或网络注入。

认证环境、私有 password mount 和稳定 MQTT socket 三者共同作为 authenticated session 证据。超时仍必须 fail closed，并由既有事务执行标准回滚。

### 5.1 脱敏失败枚举

运行时探针异常必须携带固定 `failure_code`，普通输出只能使用下列枚举，不得复制异常自由文本、用户名、Client ID、密码或路径：

- `runtime_ownership_binding_failed`
- `authentication_environment_binding_failed`
- `password_mount_binding_failed`
- `password_source_safety_failed`
- `docker_log_binding_failed`
- `mqtt_socket_appearance_timed_out`
- `mqtt_socket_never_stabilized`
- `passive_telemetry_timed_out`
- `runtime_probe_failed`（未细分的保守兜底）

环境、mount、secret owner 或日志绑定失败必须发生在 socket 验证之前；socket 失败不得覆盖更早、更具体的绑定错误。

阶段诊断继续保留兼容的顶层 `failure_code`，并将上述白名单枚举写入可选的 `probe_failure_code`；不得持久化异常 message 或未列入白名单的任意属性。

## 6. Docker JSON log 绑定

允许直接读取 `docker inspect` 返回的 JSON log file，但必须验证：

- container ID 为 64 位十六进制；
- log filename 精确为 `<container-id>-json.log`；
- parent directory 名称精确为 container ID；
- 文件存在、不是符号链接；
- 只接受 `time >= State.StartedAt` 的日志记录；
- 最大读取尾部窗口受限，禁止无界加载历史日志。

必须观察到本次启动后的：

```text
Subscribed to gh/v1/<sid>/ingress/node/+/telemetry
Subscribed to gh/v1/<sid>/state/+/telemetry
Accepted telemetry node=<node_id> ...
Published Home Assistant discovery node=<node_id> topic=<exact-topic>
```

无法在超时窗口内被动观察到真实节点下一轮遥测时必须 fail closed，不得发布合成遥测代替。

socket/启动日志窗口与被动遥测窗口必须分离。研发 T1 的 N1 固件遥测周期为 60 秒，
因此 `telemetry_timeout_s` 必须至少覆盖一个完整上报周期及调度余量，当前固定为 90 秒；
不得沿用 35 秒 socket 窗口等待 60 秒周期遥测。所有等待必须使用同一可注入的 monotonic clock，
并按剩余时间截断 sleep，禁止忙等。

## 7. 业务验证

### 7.1 ingress

本次启动日志出现精确 ingress subscription，且随后出现真实节点 `Accepted telemetry`。

### 7.2 canonical state

在 `Accepted telemetry` 后匿名只读获取 exact canonical topic，要求 `node_id` 一致且 payload 为有效 JSON object。

### 7.3 availability

exact availability topic 必须为该节点的 `online` 状态。

### 7.4 Discovery

本次启动日志必须出现 exact Discovery topic 发布，迁移后 Discovery 身份摘要必须与迁移前一致。

### 7.5 reconnect

本次启动后的 ingress 和 canonical subscription 日志均存在，且 MQTT socket 在间隔采样中稳定。

### 7.6 匿名兼容

迁移后仍能匿名只读 exact canonical retained state。该检查只证明兼容路径保留，不授权匿名控制或凭据关闭。

## 8. Integration factory

6l transaction workspace 已包含 `journal.json`。factory 必须创建：

```text
<transaction-workspace>/host-adapters
```

并要求：

- 目标此前不存在；
- mode 精确为 `0700`；
- 作为 6m adapters 的空 workspace；
- baseline capture 在 adapters prepare、授权 claim 和 mutation 之前完成；
- 任何 baseline/binding/probe 初始化失败均发生在 claim 前。

## 9. 当前状态

6n 合并后仍保持：

```text
execution_entrypoint_installed=false
authorization_claimed=false
production_executor_available=false
execution_enabled=false
apply_enabled=false
ready_for_manager_migration_apply=false
manager_identity_migrated=false
node_credentials_delivered=false
current_services_modified=false
preserve_anonymous=true
anonymous_closure_enabled=false
```

## 10. 后续门

下一阶段才可实现唯一 production execution packet/CLI，并必须：

1. 显式传入真实节点与精确 Discovery topic；
2. 重新生成 6e/6f/6i/6j；
3. 完成第一次操作员确认并创建短时单次授权；
4. 通过 6k 第二次事务门；
5. 要求精确 `EXECUTE-M2-MANAGER-MIGRATION:*` 与显式 enable flag；
6. 在真实写操作前再次核对三个容器和非目标服务身份；
7. 任一 post-claim 失败自动回滚。

本协议不构成真实 T1 写授权。
