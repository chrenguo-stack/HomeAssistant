# M2-ADR-001：本地 + 云端混合开发及项目私有 Mosquitto 冻结决策

- **状态：** 已冻结
- **批准日期：** 2026-07-17
- **批准方：** 产品负责人
- **适用范围：** M2 节点 MQTT 认证迁移、ESP32-C6 实板故障矩阵及后续同类研发工作

## 1. 决策

项目冻结采用以下开发和验证模式：

```text
本地 Mac：快速测试、缓存编译、USB 烧录、串口和实板验证
GitHub / 隔离 Linux：干净环境、Docker、完整 CI、安全与回归门禁
真实板卡 / T1：阶段末实机或生产阶段门
```

不采用纯云端开发模式。纯云端不能替代 USB 首次烧录、LCD、传感器、RS485、Wi-Fi、断电、NVS、GPIO 回滚及真实串口证据。

## 2. 本地 Broker 决策

本地 ESP32-C6 节点认证实验室使用项目私有固定版本 Mosquitto，不再把 Homebrew `mosquitto` 公式作为必要依赖，也不注册 Homebrew 后台服务。

冻结参数：

| 项目 | 冻结值 |
|---|---|
| Mosquitto 版本 | `2.0.21` |
| 官方源码 | `https://mosquitto.org/files/source/mosquitto-2.0.21.tar.gz` |
| SHA-256 | `7ad5e84caeb8d2bb6ed0c04614b2a7042def961af82d87f688ba33db857b899d` |
| 构建系统 | CMake，最低 `3.18` |
| WebSocket | 关闭 |
| MQTT 客户端工具 | 不构建 |
| 插件 | 不构建 |
| 文档 | 不构建 |
| TLS | 保留 |
| 产物 | 仅 `mosquitto`、`mosquitto_passwd` |
| 默认缓存根 | `$HOME/.cache/greenhouse-mosquitto` |
| 系统服务 | 不创建、不启动 |

固定源码版本经过 SHA-256 验证后，在仓库外的私有缓存目录构建。构建过程不得覆盖未知既有安装；既有目录必须先通过 manifest、版本和二进制哈希复核才能复用。

## 3. 选择理由

1. 当前 Intel macOS 12 本地环境已验证 Python、Ruff、pytest、ESPHome 和 ESP32-C6 编译能力，满足主要开发需求。
2. Homebrew 当前环境属于旧系统和镜像元数据组合，完整 `mosquitto` 公式会引入本项目不需要的 `libwebsockets` 依赖链。
3. 节点认证板级实验仅需要普通 MQTT/TCP、用户名密码文件和受控 Broker 生命周期，不需要 WebSocket。
4. 项目私有固定版本能够控制源码来源、哈希、构建选项、产物位置和进程边界，减少本地环境漂移。
5. GitHub CI 继续提供干净 Linux、Docker 和完整回归，避免本地成功被误认为跨平台或生产验收。

## 4. 环境职责冻结

### 4.1 本地 Mac

负责：

- `gh-local status`、`gh-local fast`；
- Ruff、pytest 和局部合同测试；
- ESPHome `config` 及缓存 ESP32-C6 编译；
- 项目私有 Mosquitto 构建、验证和本地非生产 Broker 生命周期；
- 专用测试板 USB 烧录、串口、LCD、传感器、RS485、Wi-Fi、断电和 GPIO 操作。

不得承担：

- 以本地结果替代 GitHub required checks；
- 生产 T1 修改；
- 生产凭据生成或读取；
- anonymous MQTT 关闭。

### 4.2 GitHub / 隔离 Linux

负责：

- 公共仓库安全扫描；
- Manager、M0/M1/M2 回归；
- 原生 Linux Mosquitto 和 Docker Mosquitto 集成；
- 固件完整编译；
- 固定源码哈希及最小构建配方复核；
- 合并前门禁。

### 4.3 实板 / T1 阶段门

负责：

- 真实 ESP32-C6 运行时故障矩阵；
- 真实 T1 只读探测、授权、执行、回滚和提交后审计；
- 任何生产服务或生产凭据变化。

编译、模拟、本地 Broker 或 CI 通过均不得表述为实板或生产验收完成。

## 5. 安全边界

项目私有 Mosquitto 工具必须保持：

- 只使用官方 HTTPS 源码和冻结 SHA-256；
- 安装目录和构建目录位于 Git 仓库外；
- manifest 为私有文件，绑定平台、版本、构建配方、绝对产物路径及二进制哈希；
- 公共输出不包含本地绝对路径；
- 不执行 `brew services start mosquitto`；
- 不连接生产 T1、生产 Broker 或 Home Assistant `.storage`；
- 不生成、交付或提交生产节点凭据；
- 不改变 anonymous MQTT 状态；
- `ready_for_live_apply=false`；
- `ready_for_anonymous_closure=false`。

## 6. 变更控制

以下变化必须形成新的明确决策，不能静默更新：

- Mosquitto 版本或源码 SHA-256；
- 开启 WebSocket、插件、客户端或其他额外组件；
- 改为系统级或 Homebrew 服务安装；
- 改变本地、云端、实板或 T1 的职责边界；
- 改为纯云端模式；
- 将本地或 CI 结果视为生产验收。

版本升级至少需要：官方发布审查、源码哈希更新、构建配方回归、GitHub 干净环境测试和本地 Mac 重新验证。

## 7. 当前阶段状态

```text
hybrid_development_mode_frozen=true
pure_cloud_mode_selected=false
private_mosquitto_version=2.0.21
homebrew_mosquitto_required=false
homebrew_service_required=false
production_system_modified=false
node_credentials_generated=false
anonymous_closure_enabled=false
local_mac_private_build_pending=true
real_board_runtime_fault_matrix_pending=true
ready_for_live_apply=false
ready_for_anonymous_closure=false
```
