# 15.1.2 RS485 Modbus 回显过滤基线

## 定位

本目录保存 2026-06-19 形成的 `15.1.2-rs485-modbus-echo-filter` 专项验证工程。

它是 **F1.0-RC2 开发的输入基线之一**，不是 F1.0-RC2，也不是当前整机固件。F1.0-RC2 尚未创建，将由后续开发把本目录中的 RS485 回显过滤能力与当前硬件、LCD、传感器、电源、联网和诊断需求进行整合。

## 文件结构

```text
15_1_2_rs485_modbus_echo_filter/
├── 15_1_2_rs485_modbus_echo_filter.yml
└── my_components/
    └── echo_filtered_modbus/
        ├── __init__.py
        ├── echo_filtered_modbus.h
        └── echo_filtered_modbus.cpp
```

## 已知条件

- 目标 MCU：ESP32-C6-WROOM-1；
- ESPHome 版本目标：2026.4.3；
- RS485 传感器电源：GPIO15，持续开启；
- RS485 UART TX：GPIO21；
- RS485 UART RX：GPIO17；
- 波特率：4800，8N1；
- Modbus 地址：`0x01`；
- 读取寄存器：`0x0000`～`0x0002`；
- 当前回显过滤只针对功能码 `0x03`；
- 当前启动流程仍包含 30 秒稳定等待和 15 秒预热，后续 F1.0-RC2 将按已确认规则改为本地初始化完成后立即启动首轮读取，不再固定等待 30 秒。

## 本地检查

```bash
cd firmware/esphome_rc/15_1_2_rs485_modbus_echo_filter
esphome config 15_1_2_rs485_modbus_echo_filter.yml
esphome compile 15_1_2_rs485_modbus_echo_filter.yml
```

## 预期日志

正常情况下应出现：

```text
[echo_filtered_modbus] Discarded exact TX echo ...
[soil_modbus] Soil moisture: ...
[soil_modbus] Soil temperature: ...
[soil_modbus] Soil conductivity: ...
```

不应再反复出现由请求回显拼接真实响应导致的 CRC 错误。

## 版本管理说明

本目录首先按用户提供的完整工程原样归档。后续修复不得覆盖此历史基线，应在新的 F1.0-RC2 目录或开发分支中完成。