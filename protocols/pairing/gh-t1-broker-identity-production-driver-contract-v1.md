# gh-t1-broker-identity-production-driver-contract-v1

状态：M2.4g-5k Draft

## 目的

本协议冻结未来真实 T1 Broker 身份激活所需的生产 Broker driver 边界，但不安装、启用或调用该 driver。输入必须同时绑定：

- 已验证的 production executor contract；
- 已验证的 production adapter skeleton；
- 已通过的真实 T1 live mount gate；
- contract、skeleton 与 mount-binding 的 SHA-256。

## 运行时控制命令白名单

未来 runtime controller 只允许以下两个精确命令模板：

```text
docker inspect mosquitto
docker restart mosquitto
```

其中仅 `docker restart mosquitto` 属于变更命令。禁止：

- `docker exec`、`docker cp`、`docker create/run/start/stop/rm/kill`；
- Docker Compose；
- systemd；
- SSH；
- shell 或 `sh -c`；
- 重启 Home Assistant、greenhouse-manager 或其他容器；
- 在 argv、环境变量或标准输出中携带密码。

## Dynamic Security 传输

Dynamic Security 控制必须由同进程 `paho-mqtt` 客户端完成：

- Broker 目标来自重新验证的 preactivation target；
- 凭据只从 mode `0600` 且已绑定的交接文件读取；
- 请求只从 SHA-256 绑定的 `dynsec-request.json` 读取；
- 密码不得进入 argv、环境变量、日志或标准输出；
- 不允许依赖外部 `mosquitto_pub/sub/rr` CLI；
- 控制与响应 Topic 固定为 Dynamic Security 官方 Topic。

## 文件事务边界

未来文件适配器必须：

1. 仅解析 production executor contract 中冻结的 `/mosquitto/...` 目标；
2. 通过私有 runtime binding manifest 解析真实宿主机 bind-mount 路径；
3. 拒绝符号链接、越界路径及任何 Home Assistant、Compose、manager 或节点路径；
4. 使用同目录临时文件、文件 `fsync`、原子替换和父目录 `fsync`；
5. 任一 mutation 入口后的失败必须执行完整快照回退；
6. rollback 失败必须作为终止故障明确上报。

## 当前不可执行状态

本阶段必须保持：

```text
production_driver_contract_available=true
production_driver_installed=false
production_executor_available=false
execution_enabled=false
apply_enabled=false
operator_action_authorized=false
ready_for_live_activation=false
current_services_modified=false
preserve_anonymous=true
anonymous_closure_enabled=false
```

CLI 只允许生成和验证契约，不得包含 `execute`、`enable`、`apply` 或 `live` 入口。

## 后续阻塞条件

真实执行前仍必须完成：

- 私有 runtime binding manifest；
- production driver 实现与独立审查；
- 新鲜 preactivation 与单次操作员授权；
- Home Assistant 官方 MQTT UI/config-flow 重配置；
- 实体节点凭据交付验证；
- 匿名关闭独立稳定性门。
