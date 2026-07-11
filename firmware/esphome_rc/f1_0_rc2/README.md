# F1.0-RC2 · N0.3 离线整机基线

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

## N0.3 修复

N0.3 处理 N0.2 实板回归发现的两项问题。

### RS485 断电倒灌

N0.2 关闭 GPIO15 后，实测：

```text
传感器 VCC：2.03 V
GPIO21 / UART TX：2.93 V
RXD0 / 芯片 GPIO17：1.47 V
```

这表明 UART TX 空闲高电平会经未上电的 RS485 收发电路形成幻象供电。N0.3 的时序调整为：

```text
等待 UART TX 排空
→ GPIO21 与 RXD0/GPIO17 切换为浮空输入
→ GPIO15 关闭传感器电源
```

再次读取时：

```text
GPIO15 开启电源
→ 等待 500 ms 电源稳定
→ 调用 UART load_settings(false) 恢复引脚与驱动
→ 继续原 15 秒传感器预热
→ 执行 Modbus 读取
```

UART `flush_timeout` 固定为 500 ms，避免异常情况下无限等待。OTA、低电保护和正常读取结束都使用同一安全断电流程。

### GPIO6 产品状态灯

N0.2 误将 GPIO6 配置为 ESPHome 全局 `status_led`，导致任一组件 warning 都会控制绿色 LED 闪烁。N0.3 删除 `status_led`，将 GPIO6 改为普通 GPIO 输出：

- 上电与本地初始化阶段：熄灭；
- 本地初始化完成：稳定常亮；
- 无 Wi-Fi、无 Home Assistant：仍保持常亮；
- 进入低电保护或 OTA：熄灭。

网络与配对状态继续由 LCD 第 5 页表达，不再复用绿色运行灯。

## LCD 界面

N0.2 已恢复 14.8 经过实板调整的产品界面，并在 N0.3 保持不变：

- 顶部设备后缀、电池图标和 Wi-Fi 信号；
- 气温/湿度页；
- 二氧化碳/DLI 页；
- 土壤温度/湿度/盐度页；
- VPD/露点/绝对湿度页；
- 配网二维码/已联网状态页；
- 底部分页指示和时间；
- 大号数值双绘制加粗；
- 低电保护专用画面。

14.8 的显示旋转角为 `270°`。当前 PCB 安装方向要求在此基础上再调转 `180°`，因此配置使用 `rotation: 90`，逻辑画布仍为 `64×128`。页面每 4 秒切换一次。

## 固定 GPIO

| 功能 | ESP32-C6 芯片 GPIO | WROOM-1 模组标识 |
|---|---:|---|
| TPS2116.ST 主电源状态 | 0 | IO0 |
| 电池 ADC | 1 | IO1 |
| LCD SPI CLK | 2 | IO2 |
| LCD SPI MOSI | 3 | IO3 |
| 绿色状态 LED（高电平点亮） | 6 | IO6 |
| RS485 土壤传感器电源 | 15 | IO15 |
| LCD CS（反相） | 16 | TXD0 |
| RS485 RX | 17 | RXD0 |
| RS485 TX | 21 | IO21 |
| I²C SDA | 22 | IO22 |
| I²C SCL | 23 | IO23 |

LoRa 模块引脚在本版不启用。

## RS485 首次读取规则

`on_boot priority: -100` 表示 ESPHome 本地组件初始化完成后立即启动首次读取流水线：

1. 先确保 GPIO21 与 RXD0/GPIO17 为高阻、GPIO15 关闭；
2. 打开 GPIO15；
3. 等待 500 ms 后恢复 UART；
4. 传感器继续预热 15 秒；
5. 读取连续三个寄存器；
6. 官方 Modbus 最多重试两次，总发送机会三次；
7. 完成或超时后再次将 UART 切换为高阻并关闭 GPIO15。

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
- N0.2 14.8 界面迁移、180° 方向修正、OTA 和实板运行：通过；
- N0.3 配置与完整编译：待验证；
- N0.3 RS485 断电残压、高阻恢复和 GPIO6 状态灯：待实板验证。
