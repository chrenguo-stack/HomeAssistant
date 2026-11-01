# 温室环境监测系统

面向中小型温室的本地优先、可离线运行、可扩展环境监测与安全控制系统。

本仓库采用单体仓库（monorepo）管理以下内容：

- ESP32-C6 节点固件；
- Wi-Fi 版 ESP-NOW 单跳补盲；
- LoRa 环境监测节点及由普通节点承担的网关角色；
- 斐讯 T1 Docker 主机端服务；
- Home Assistant 配套集成；
- MQTT、配对、发现和路径租约协议；
- 硬件资料、测试用例、部署和恢复工具。

## 当前架构基线

- **Wi-Fi 版**：ESP32-C6 板载天线，Wi-Fi 直连优先；弱覆盖区域使用 ESP-NOW 单跳子节点到中继节点。
- **LoRa 版**：所有产品均为完整环境监测节点。满足正式绑定、稳定 Wi-Fi/TLS/MQTT 回传、电源、资源和 LoRa 健康条件的普通节点，可由 Manager 签发有限期 `GATEWAY_ID` 租约并承担网关角色。
- **无专用 LoRa 中继器**：首版保持“子节点 → 普通 LoRa 网关节点 → Wi-Fi/MQTT → Manager”的星形单跳；不设计独立无传感器中继硬件，不实现 LoRa-to-LoRa 多跳或 Mesh。
- **本地优先**：没有 Home Assistant、Wi-Fi 或 MQTT 时，节点仍持续采集传感器并通过 LCD 显示。
- **统一上层模型**：greenhouse-manager 是 canonical state 和 MQTT Discovery 的唯一发布者。
- **身份不复用**：HARDWARE_ID 标识具体硬件，NODE_ID 标识一次获批的节点归属和 Home Assistant 设备身份；更换硬件或退役后重新配对必须分配全新 NODE_ID，旧 NODE_ID 永久封存。
- **可靠生命周期**：节点退役由操作员显式发起，通过持久化 outbox 完成凭据撤销、状态清理和 Discovery 删除；部分失败或 Manager 重启后必须能够安全恢复。
- **退役硬件可重新配对**：上一 outbox 完成后，同一 HARDWARE_ID 可使用全新 `pairing_id`、严格递增 `pairing_epoch`、新凭据和从未使用过的新 NODE_ID 进入新归属。
- **实时与历史隔离**：canonical state 只表示当前可信状态；历史补发使用独立通道，不参与实时序列比较，也不得覆盖当前状态。
- **安全接入**：节点通过一次性配对获得系统 CA、MQTT 凭据和最小权限 ACL。

## 仓库导航

- `firmware/`：节点固件与共用组件
- `host/`：T1 主机端服务和 Home Assistant 配套集成
- `protocols/`：跨固件、主机和网关的冻结接口
- `docs/`：架构、路线、ADR 和研发文档
- `hardware/`：GPIO、PCB 和器件资料
- `tests/`：协议、集成、硬件和现场测试
- `infra/`：部署、备份、恢复和运维
- `tools/`：开发辅助工具

## 开发原则

1. 先稳定离线采集，再完成联网闭环，最后增加无线补盲和控制。
2. 两个硬件版本共享协议、身份、安全和数据模型，但分别构建固件目标。
3. LoRa 网关是普通环境监测节点的附加角色；自身 NODE_ID、传感器、LCD 和 Home Assistant 设备身份保持有效。
4. 所有协议变更先更新 `protocols/` 和 ADR，再修改代码。
5. `main` 始终保持可构建或仅包含明确标注的骨架代码。

当前后继架构基线：**V0.7 双产品线、身份不复用、普通 LoRa 节点网关化与可靠生命周期后继版**。
V0.5 与 V0.6 作为前序历史基线保持不变。

架构基线不代表对应能力已经完成开发或验收。实时进度以 `docs/status/`、`docs/acceptance/` 和 `docs/handoffs/` 中的记录与证据为准。
