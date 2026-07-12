# gh-t1-broker-identity-production-driver-preflight-v1

状态：M2.4g-5m Draft

## 目的

定义 production Broker driver 安装前的最终只读预检。预检重新绑定 driver contract、executor contract、私有 runtime binding manifest、当前 live mount gate 与当前 preactivation gate，但不安装或调用 production driver。

## 输入

必须提供 mode 0600 的 driver contract、executor contract、runtime binding manifest，以及 activation handoff、inactive stage、retained telemetry Topic 和 Home Assistant 官方 MQTT config entry 的目标指纹、entry 指纹与 storage SHA-256。

## 重新验证

本次运行必须重新完成：

1. driver contract 验证；
2. executor contract 验证，并从当前 handoff 和 stage 重建后精确比较；
3. runtime binding manifest 完整性与时效性验证；
4. live mount gate；
5. Broker identity preactivation gate；
6. Mosquitto 容器 ID、镜像、启动时间和 restart count 绑定；
7. Compose 文件及 Mosquitto config/data 路径的 device、inode、mode、uid、gid 与 SHA-256 绑定；
8. mosquitto.conf 基线 SHA-256 验证；
9. dynamic-security.json 在激活前仍不存在。

runtime binding manifest 默认最长有效期为 900 秒，可配置范围为 60 至 3600 秒。容器、路径、Compose、权限或配置发生变化时必须失败。

## 操作边界

预检只允许既有只读门所需查询和 `docker inspect mosquitto`。禁止重启或修改服务，禁止 Docker exec、cp、create、start、stop、rm，禁止消费操作员授权，禁止生成 execute、enable、apply 或 live 入口，禁止把真实宿主机路径写入标准输出。

## 成功状态

```text
preflight_ready=true
read_only=true
path_values_redacted=true
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

预检通过仍不等于允许激活。production driver 安装、新的单次授权、Home Assistant 官方 MQTT UI/config-flow、实体节点凭据交付以及匿名关闭稳定性门仍是后续独立条件。
