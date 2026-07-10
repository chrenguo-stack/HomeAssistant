# F1.0-RC2 · N0.2 离线整机基线

本目录是按照 V0.5 路线新建的 F1.0-RC2。它不是旧版文件改名，而是从当前 PCB、14.x 成熟功能和 15.1.2 回显过滤 Modbus 基线重新整合。

## 本版目标

先完成 N0：即使没有 Wi-Fi、Home Assistant 或 MQTT，节点也能持续采集、显示并执行低电保护。

已包含：

- ESP32-C6-WROOM-1，8 MB Flash，ESP-IDF；
- SCD30、SHT30、BH1750；
- RS485 土壤湿度、温度、电导率；
- `echo_filtered_modbus` + 官方 `modbus_controller`；
- TPS2116.ST 主电源状态；
- 475 kΩ / 475 kΩ 电池 ADC，理论换算 `ADC × 2.0`，预留校准系数；
- 低电防抖、恢复滞回和 RS485 断电保护；
- Captive Portal、ESPHome API、mDNS、本地 OTA 与 HTTP Pull OTA；
- 14.8 LCD12864 五页产品界面、配网二维码和联网状态页。

暂不包含正式 MQTT、greenhouse-manager 配对、ESP-NOW 和 LoRa 业务通信。

## N0.2 LCD 变更

N0.2 恢复 14.8 经过实板调整的产品界面：

- 顶部设备后缀、电池图标和 Wi-Fi 信号；
- 气温/湿度页；
- 二氧化碳/DLI 页；
- 土壤温度/湿度/盐度页；
- VPD/露点/绝对湿度页；
- 配网二维码/已联网状态页；
- 底部分页指示和时间；
- 大号数值双绘制加粗；
- 低电保护专用画面。

14.8 的显示旋转角为 `270°`。当前 PCB 安装方向要求在此基础上再调转 `180°`，因此配置使用 `rotation: 90`，逻辑画布仍为 `64×128`。

页面沿用 14.8 的节奏，每 4 秒切换一次。

## 固定 GPIO

| 功能 | GPIO |
|---|---:|
| TPS2116.ST 主电源状态 | 0 |
| 电池 ADC | 1 |
| LCD SPI CLK | 2 |
| LCD SPI MOSI | 3 |
| 绿色状态 LED（高电平点亮） | 6 |
| RS485 土壤传感器电源 | 15 |
| LCD CS（反相） | 16 |
| RS485 RX | 17 |
| RS485 TX | 21 |
| I²C SDA | 22 |
| I²C SCL | 23 |

LoRa 模块引脚在本版不启用。

## RS485 首次读取规则

`on_boot priority: -100` 表示 ESPHome 本地组件初始化完成后立即启动首次读取流水线：

1. 打开 GPIO15；
2. 传感器预热 15 秒；
3. 读取连续三个寄存器；
4. 官方 Modbus 最多重试两次，总发送机会三次；
5. 完成或超时后关闭 GPIO15。

这里没有旧版额外固定 30 秒等待。

## 字体

延续 14.8 已验证的 LCD12864 点阵字体组合：

- 10 px：Fusion Pixel Font 等宽 BDF；
- 12 px：Fusion Pixel Font 等宽 BDF；
- 16 px：Ark Pixel Font 等宽 BDF，仅用于大号数字。

字体不直接提交到本仓库。下载脚本固定使用上游 `2026.07.01` Release，避免浮动的 `latest` 版本造成构建结果变化。

`tools/rc2.sh` 会在运行 ESPHome 前检查字体，缺失时自动下载并生成：

```text
fonts/fusion-pixel-10px-monospaced-zh_hans.bdf
fonts/fusion-pixel-12px-monospaced-zh_hans.bdf
fonts/ark-pixel-16px-monospaced-zh_cn.bdf
```

## 构建与安装

```bash
cd firmware/esphome_rc/f1_0_rc2
bash tools/rc2.sh config
bash tools/rc2.sh compile
bash tools/rc2.sh run --device 设备IP或串口
```

## 当前验证状态

- N0.1 ESPHome 2026.4.3 完整编译：通过；
- N0.1 OTA：通过；
- N0.1 整机运行及全部传感器数据：通过；
- N0.2 14.8 界面迁移和 180° 方向修正：待编译、OTA 与照片回归。
