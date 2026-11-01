# F1.0-RC2 N0 首轮实板测试

## 已完成的构建验证

- ESPHome：2026.4.3
- Python：3.11.9（PlatformIO ESP-IDF 环境）
- ESP-IDF：5.5.4
- 本地完整编译：通过
- 编译时间：2026-07-10 12:55:55 +0800
- 配置哈希：`0x21c5baf6`

## 烧录前检查

1. 传感器和 LCD 按当前 PCB 接线；
2. EWM22M 天线已连接，虽然本版不启用 LoRa 业务；
3. 使用稳定的 USB 烧录供电；
4. 首轮测试保留串口日志；
5. 确认开发分支为 `feature/f1-0-rc2-n0`。

## 烧录命令

```bash
cd firmware/esphome_rc/f1_0_rc2
ls /dev/cu.usbmodem*
bash tools/rc2.sh run --device /dev/cu.usbmodemXXXX
```

## 首轮观察顺序

### 1. 启动与本地初始化

确认日志包含：

```text
[boot] Local initialization complete; starting first soil read cycle.
[soil] Sensor power ON; warm-up started.
```

### 2. I²C 设备

预期扫描地址：

- `0x23`：BH1750
- `0x44`：SHT30
- `0x61`：SCD30

### 3. RS485 土壤读取

确认：

1. GPIO15 上电；
2. 等待 15 秒预热；
3. 发起 Modbus 请求；
4. 如存在硬件回显，日志可出现 `Discarded exact TX echo`；
5. 土壤湿度、温度、电导率更新；
6. 完成后 GPIO15 关闭。

### 4. LCD12864

确认：

- 屏幕方向和坐标正常；
- 五页每 8 秒切换；
- 字体无乱码或缺字；
- 未联网时显示配网二维码；
- 联网后显示 IP 和 Wi-Fi 信号；
- 数值不越界、不重叠。

### 5. 电源与电池

确认：

- GPIO0 主电源状态与实际供电路径一致；
- Home Assistant/日志中的电池电压与万用表对比；
- 记录实测电池电压和显示电压，用于计算校准系数；
- 首轮不主动把电池放至低电阈值。

### 6. 离线运行

关闭路由器或不进行配网，确认：

- MCU 不重启；
- 传感器继续采集；
- LCD 继续刷新；
- 周期性 RS485 读取仍执行。

## 需要回传的资料

- 从上电开始至少 2 分钟的完整日志；
- LCD 五个页面的照片；
- 万用表电池电压和 LCD/日志电压；
- 主电源接入与断开时 GPIO0 状态；
- 土壤传感器是否成功读取及是否出现回显过滤日志。
