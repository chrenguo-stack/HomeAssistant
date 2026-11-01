# M0 MQTT 垂直链路

该目录将 V0.5 当前三个已完成模块连成第一条可运行链路：

```text
模拟监测节点 → Mosquitto → greenhouse-manager → retained canonical state
```

## 包含的服务

- `mosquitto`：仅用于本地开发的匿名 Broker；
- `manager`：校验、去重并发布规范化状态；
- `simulator`：持续发布 `gh.telemetry/1`；
- `observer`：可选的 Topic 实时观察器。

模拟器默认每 5 条制造一个重复包、每 7 条制造一个湿度越界包，用于持续验证 manager 的去重和错误隔离。非法包不得覆盖上一条有效 canonical telemetry。

## 启动

```bash
cd infra/compose/m0
docker compose up --build
```

另开终端观察 manager 发布的状态：

```bash
docker compose --profile observe up observer
```

也可以直接使用本机 MQTT 客户端：

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -t 'gh/v1/devsystem/state/#' -v
```

## 自动验收

```bash
bash verify.sh
```

脚本会构建并启动三个核心服务，然后验证：

1. 有效入口遥测被转换为 retained canonical telemetry；
2. canonical 消息包含 manager 生成的 `received_at`；
3. availability 为 `online`；
4. 模拟器制造的非法遥测被拒绝并生成 diagnostic；
5. diagnostic 不会破坏上一条有效遥测。

验收结束后脚本自动删除容器和测试数据卷。

## 停止与清理

```bash
docker compose down --volumes --remove-orphans
```

## 安全边界

`infra/mosquitto/dev/mosquitto.conf` 开启匿名访问，只允许用于开发机和 CI。正式主机必须使用：

- 独立 manager、节点和网关账号；
- Dynamic Security/ACL；
- TLS 服务端证书校验；
- 不对公网暴露 1883 端口。
