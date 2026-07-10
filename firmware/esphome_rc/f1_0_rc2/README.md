# F1.0-RC2 · N0.1 离线整机基线

本目录是按照 V0.5 路线新建的第一版 F1.0-RC2。它不是旧版文件改名，而是从当前 PCB、14.x 成熟功能和 15.1.2 回显过滤 Modbus 基线重新整合。

## 本版目标

先完成 N0：即使没有 Wi-Fi、Home Assistant 或 MQTT，节点也能持续采集、显示并执行低电保护。

已包含：

- ESP32-C6-WROOM-1，8 MB Flash，ESP-IDF；
- SCD30、SHT30、BH1750；
- RS485 土壤湿度、温度、电导率；
- `echo_filtered_modbus` + 官方 `modbus_controller`；
- LCD12864 五页轮播及 Captive Portal 二维码/联网状态页；
- TPS2116.ST 主电源状态；
- 475 kΩ / 475 kΩ 电池 ADC，理论换算 `ADC × 2.0`，预留校准系数；
- 低电防抖、恢复滞回和 RS485 断电保护；
- Captive Portal、ESPHome API、mDNS、本地 OTA 与 HTTP Pull OTA。

暂不包含正式 MQTT、greenhouse-manager 配对、ESP-NOW 和 LoRa 业务通信。

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

字体不直接提交到本仓库。构建前运行下载脚本，脚本固定使用上游 `2026.07.01` Release，避免浮动的 `latest` 版本造成构建结果变化：

```bash
bash tools/fetch_fonts.sh
```

下载后会生成：

```text
fonts/fusion-pixel-10px-monospaced-zh_hans.bdf
fonts/fusion-pixel-12px-monospaced-zh_hans.bdf
fonts/ark-pixel-16px-monospaced-zh_cn.bdf
```

## 构建

```bash
cd firmware/esphome_rc/f1_0_rc2
bash tools/fetch_fonts.sh
esphome config f1_0_rc2.yml
esphome compile f1_0_rc2.yml
esphome run f1_0_rc2.yml --device /dev/cu.usbmodemXXXX
```

首次准备字体和 PlatformIO 依赖时，编译电脑需要能够访问 GitHub。

## 当前验证状态

- ESPHome 2026.4.3 配置校验：通过；
- C++ 代码生成：通过；
- 当前自动环境因无法解析 GitHub 域名，未能下载 PlatformIO 的 ESP32 平台包，因此尚未完成最终链接；
- 实板烧录和传感器验证：待进行。

## 首轮实板验收

1. 上电后 LED、LCD 和 Captive Portal 正常；
2. LCD 每 8 秒切换一页，共五页；
3. SCD30、SHT30、BH1750 数据有效；
4. 本地初始化完成后 GPIO15 立即进入“上电—15 秒预热—读取—断电”流程；
5. 日志出现 `Discarded exact TX echo` 时，土壤数据仍能正常发布；
6. GPIO0 在主电源/电池路径切换时状态正确；
7. ADC 电压与万用表读数对比，用于确定 `battery_calibration_factor`；
8. 无 Wi-Fi 时本地采集和 LCD 不受影响。
