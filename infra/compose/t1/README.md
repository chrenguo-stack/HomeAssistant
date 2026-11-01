# 斐讯 T1 · N1 greenhouse-manager 部署

本目录只增加 `greenhouse-manager`，复用 T1 上已经运行的 Mosquitto，不启动第二个 Broker，也不修改现有 Home Assistant、ESPHome、InfluxDB、Grafana 或 Node-RED 容器。

## 已确认环境

- 主机：aarch64 / Armbian Ubuntu；
- Docker 29.4.2；
- Docker Compose v5.1.3；
- 现有 Mosquitto 服务位于外部网络 `ha_docker_default`；
- Broker 容器名和网络 DNS 名均为 `mosquitto`；
- 当前实验 listener 为 1883，允许匿名访问；
- 主机内存和磁盘余量有限，因此 manager 限制为 96 MiB、64 PID，日志最多约 10 MiB。

## 部署

在仓库根目录执行：

```bash
cd infra/compose/t1
cp .env.example .env

docker compose --env-file .env \
  -f docker-compose.manager.yml config

docker compose --env-file .env \
  -f docker-compose.manager.yml up -d --build
```

查看状态：

```bash
docker ps --filter name=greenhouse-manager
docker logs --tail 100 greenhouse-manager
```

预期日志应包含连接 `mosquitto:1883` 和订阅：

```text
gh/v1/greenhouse/ingress/node/+/telemetry
```

## 观察规范化状态

在 N1 实板开始发布后执行：

```bash
docker exec mosquitto mosquitto_sub \
  -h 127.0.0.1 \
  -t 'gh/v1/greenhouse/state/#' \
  -v
```

停止观察使用 `Ctrl+C`。

## 更新

```bash
git pull --ff-only
cd infra/compose/t1
docker compose --env-file .env \
  -f docker-compose.manager.yml up -d --build
```

## 回退和删除

```bash
cd infra/compose/t1
docker compose --env-file .env \
  -f docker-compose.manager.yml down
```

该命令只删除 manager 容器和本项目构建的网络附件，不会停止现有 Mosquitto 或 Home Assistant。

## 当前安全边界

当前 Mosquitto 配置 `allow_anonymous true` 仅用于 N1 局域网联调。不要通过 FRP 或路由器端口映射公开 1883。进入产品化阶段前必须启用每设备账号、ACL 和 TLS。
