# ADR-0001：Wi-Fi 版与 LoRa 版双产品通信架构

- 状态：已接受
- 日期：2026-07-10
- 基线：技术路线 V0.5

## 决策

产品分为两个硬件版本：

1. **Wi-Fi 版**：ESP32-C6 板载天线；Wi-Fi 直连优先，复杂环境弱覆盖使用 ESP-NOW 单跳子节点到中继节点。
2. **LoRa 版**：ESP32-C6 + EWM22M-400T22S；子节点以 LoRa 到网关节点，网关以 Wi-Fi 接入 greenhouse-manager。

普通 LoRa 子节点不承担其他子节点的转发。需要进一步扩距时，单独验证固定供电的专用射频中继器，不在首版中实现自组织 Mesh。

## 原因

- 避免 ESP-NOW 与 LoRa 在同一 SKU 内形成重复业务链路；
- 保持两款产品共同的身份、安全、MQTT 和 Home Assistant 模型；
- 控制低功耗子节点的复杂度、故障传播和无线信道占用；
- 适合个人开发者分阶段验证和维护。

## 后果

- 固件形成独立构建目标，但共享 `firmware/common`；
- N3 分为 N3-W（ESP-NOW）与 N3-L（LoRa 网关）；
- 专用 LoRa 中继列为后续 N4-L 决策门；
- Home Assistant 只识别 NODE_ID，不感知底层传输路径。
