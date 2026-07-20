# H3/N2 Stage 2B-3 Manager 装配与隔离部署说明

**基线：** `main = 0e5d51b9164889e35e1847ed4c537b9120b07d05`  
**开发分支：** `feature/h3-n2-stage2b3-manager-assembly-20260720-v40`

## 1. 目标

把已合并的配对会话、安全传输、mDNS/UDP 发现和 HTTP 端点组合成一个默认关闭的 Manager 候选运行时，同时保证现有 `greenhouse-manager` 入口、M401A、T1、Home Assistant 和 Broker 完全不变。

## 2. 代码范围

- `pairing_runtime_config.py`
- `pairing_runtime.py`
- `pairing_lab_cli.py`
- `Dockerfile.pairing-lab`
- `infra/compose/h3-pairing-lab/compose.yaml`
- 配置、运行时、CLI 和部署合同测试
- `gh-h3-pairing-runtime-deployment-v1.md`

## 3. 默认关闭保证

默认配置执行 `greenhouse-manager-pairing-lab --check-config` 时应报告：

```json
{
  "pairing_service_enabled": false,
  "network_attempted": false,
  "listener_count": 0,
  "secret_values_included": false
}
```

默认 `greenhouse-manager` 应用不导入新 runtime，不启动新线程，不打开新端口。

## 4. 隔离运行模式

当前只支持：

```text
GH_PAIRING_DEPLOYMENT_MODE=isolated-lab
```

隔离入口使用进程内 provisioner，不调用真实 DynSec。它用于验证 Manager 端装配和为 Stage 2C 准备协议端点，避免提前触碰生产 Broker。

## 5. 固定端口

- 47110/tcp：配对 HTTP
- 47111/udp：回退发现

Compose 不做宿主机端口映射，网络为 internal。

## 6. 退出门

- 默认关闭配置无网络；
- 启用必须经过双门；
- 配置漂移失败关闭；
- CA 文件校验和报告脱敏；
- HTTP/UDP/mDNS 组装成功；
- `/healthz` 通过；
- close 幂等；
- Compose 无宿主机 ports；
- 全 Manager、M0、M2 和板级编译 CI 通过。

## 7. 后续

Stage 2C 从该 runtime contract 开发 ESP32-C6 客户端。真实 DynSec provisioner、M401A/T1 隔离部署和生产启用仍需单独授权和实机证据。
