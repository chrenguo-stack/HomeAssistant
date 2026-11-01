# T1 Broker 身份生产 Broker Driver 协议 V1

状态：M2.4g-5t Draft

## 1. 目的

本协议实现生产事务 adapter 所需的最小 Broker driver。driver 只提供已冻结的容器运行时控制和进程内 MQTT Dynamic Security 控制，不提供 CLI、授权 claim、事务编排或 live apply 入口。

## 2. 运行时绑定

driver 必须从 mode-0600 private runtime binding manifest 读取并验证：

- Mosquitto container ID；
- Mosquitto image ID；
- `mosquitto.conf` 宿主机路径；
- `dynamic-security.json` 宿主机路径；
- baseline config SHA-256。

每次重启前后都必须重新执行 `docker inspect mosquitto` 并拒绝容器 ID、镜像或运行状态漂移。

## 3. Docker 命令白名单

唯一允许的 Docker 命令为：

```text
docker inspect mosquitto
docker restart mosquitto
```

禁止 `docker exec`、`docker cp`、`docker create`、`docker rm`、Compose、systemd、SSH 和其他服务重启。

## 4. MQTT 控制

Dynamic Security 控制必须使用进程内 paho-mqtt MQTT v5 会话：

- 控制 Topic：`$CONTROL/dynamic-security/v1`；
- 响应 Topic：`$CONTROL/dynamic-security/v1/response`；
- 密码不得进入 argv、环境变量或 stdout；
- client config 只允许 `-h`、`-p`、`-u`、`-P`、`-i`、`-V`；
- request 必须由 SHA-256 绑定的 handoff JSON 提供；
- 禁止外部 `mosquitto_pub`、`mosquitto_sub` 或 `mosquitto_rr` 进程执行生产控制。

## 5. 身份生命周期

固定顺序为：

1. bootstrap 身份提交精确 request；
2. provisioning 身份执行 `listClients`；
3. provisioning 身份删除 `admin`；
4. bootstrap 身份必须被拒绝；
5. provisioning 身份必须继续可用。

## 6. Postactivation 审计

审计必须同时验证：

- 绑定 Mosquitto 容器运行正常；
- config 已偏离 baseline 且包含规范 plugin 行；
- Dynamic Security state 存在且 mode 为 0600；
- 匿名兼容仍启用；
- 匿名 retained state 可读；
- Home Assistant 新身份可读取 retained state；
- 错误 Home Assistant client ID 被拒绝；
- provisioning 身份可访问控制 Topic；
- bootstrap admin 被拒绝；
- 匿名客户端无法访问控制 Topic。

任一检查失败必须返回 `rollback_required=true`。

## 7. 当前边界

本阶段：

- 无 CLI 或 live apply 入口；
- 不创建、claim 或消费授权；
- 不修改 Home Assistant；
- 不向实体节点交付凭据；
- 不关闭匿名访问；
- 只有生产事务 adapter 显式注入后才可调用 driver。
