# gh-h3-pairing-runtime-deployment-v1

## 1. 目的

定义 H3/N2 Stage 2B-3 的 Manager 端装配和隔离部署合同。该合同不启用生产功能，只把 Stage 2A、Stage 2B-1 和 Stage 2B-2 组合为一个默认关闭、可检查、可隔离启动的候选运行时。

## 2. 默认关闭

环境变量：

```text
GH_PAIRING_SERVICE_ENABLED=false
```

默认值必须为 `false`。未显式设置为真时：

- 不创建 RegistrationRegistry；
- 不读取 CA 文件；
- 不创建 HTTP 或 UDP socket；
- 不创建 Zeroconf 实例；
- 不发布 mDNS；
- 不连接 MQTT；
- 不改变现有 `greenhouse-manager` 入口和运行行为。

## 3. 双门限制

当前阶段只有以下组合允许启动：

```text
GH_PAIRING_SERVICE_ENABLED=true
GH_PAIRING_DEPLOYMENT_MODE=isolated-lab
```

其他 deployment mode 必须失败关闭。生产模式、M401A 模式和 T1 模式尚未定义。

## 4. 冻结监听合同

隔离候选只允许：

```text
47110/tcp  pairing HTTP endpoint
47111/udp  nonce-bound fallback discovery
```

环境变量不得把这两个端口改为其他值。Compose 不得发布宿主机端口，只能在 `internal: true` 网络中 `expose`。

## 5. mDNS 合同

- service type：`_greenhouse._tcp.local.`
- pairing path：`/v1/pairing`
- advertised host：必须为 `.local`
- advertised IPv4：必须为本地 IPv4
- mDNS 只用于候选发现，不代表 Manager 身份认证

## 6. CA 与节点 Broker 目标

启用时必须提供：

```text
GH_PAIRING_BROKER_HOST
GH_PAIRING_BROKER_PORT
GH_PAIRING_BROKER_TLS_SERVER_NAME
GH_PAIRING_BROKER_CA_FILE
```

CA 文件必须使用绝对路径、是普通非符号链接文件、不超过 64 KiB，并包含 PEM certificate 边界。配置检查报告不得输出 CA 路径或 PEM 内容。

## 7. 运行时装配

```text
RegistrationRegistry
→ PairingSessionManager
→ SecurePairingCoordinator
→ PendingOfferRegistry
→ PairingEndpointApp
→ HTTP server + UDP server + mDNS advertiser
→ PairingNetworkService
→ PairingRuntime
```

任何中间步骤失败时，已创建的 socket、advertiser 和数据库连接必须关闭。

## 8. Provisioner 边界

`PairingRuntime` 接收 `NodeIdentityProvisioner` 接口，不把生产 DynSec 管理凭据写入配置对象。

Stage 2B-3 的独立入口使用 `IsolatedLabProvisioner`：只在当前进程内记录 plan，不连接真实 Broker，不提供生产凭据持久化，也不声明节点可连接正式 MQTT。生产 `DynsecProvisioner` 绑定属于后续受保护工作包。

## 9. 隔离容器合同

隔离 Compose 必须具备：

- `GH_PAIRING_SERVICE_ENABLED=false` 默认值；
- 无 `ports:`；
- 只 `expose` 47110/tcp 和 47111/udp；
- `internal: true` 网络；
- `read_only: true`；
- `cap_drop: ALL`；
- `no-new-privileges:true`；
- 仅状态目录可写；
- 不挂载 Docker socket；
- 不挂载 Home Assistant、Mosquitto 或现有 Manager 数据目录。

## 10. 阶段限制

本合同不表示 M401A 或 T1 已部署、真实 DynSec 已绑定、本地扫码 UI 已完成、ESP32-C6 客户端已完成、内存会话可在主机重启后恢复，或生产端口、防火墙和 TLS 终止方案已批准。
