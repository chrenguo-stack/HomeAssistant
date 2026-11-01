# 固件工作区

## 构建目标

- `wifi_node`：Wi-Fi 版环境监测节点。
- `wifi_gateway`：Wi-Fi 版 ESP-NOW 单跳中继节点。
- `lora_node`：LoRa 版环境监测子节点。
- `lora_gateway`：LoRa 网关节点，LoRa 收发并通过 Wi-Fi/MQTT 回传。
- `lora_repeater`：专用射频中继试验，首版不量产。
- `esphome_rc`：现阶段 ESPHome RC 固件及 external components。

## 共用模块

`common/` 后续应按职责拆分为：

- `board`：GPIO、硬件版本和产品 SKU；
- `sensors`：SCD30、SHT30、BH1750、RS485 土壤传感器；
- `display`：LCD12864 五页显示和配对二维码状态机；
- `power`：TPS2116 状态、电池 ADC、低电保护；
- `identity`：HARDWARE_ID、NODE_ID、BOOT_ID；
- `provisioning`：Wi-Fi 配网、manager 发现和安全绑定；
- `telemetry`：统一采样模型和协议编码；
- `storage`：NVS、凭据和配置迁移；
- `diagnostics`：运行、通信和传感器诊断。

正式 ESP-IDF 迁移前，ESPHome RC 不得被删除，需保留为硬件回归基线。
