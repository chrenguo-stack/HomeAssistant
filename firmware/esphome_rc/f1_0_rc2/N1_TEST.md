# F1.0-RC2-N1.0 实板联调清单

N1 只写入第二块完整 PCB。稳定运行的 N0.3 节点不改动。

## 1. 准备 Broker 地址

在 T1 上获取局域网 IPv4：

```bash
hostname -I
```

在本目录创建本地 secrets：

```bash
cp secrets.n1.example.yaml secrets.yaml
```

将 `n1_mqtt_broker` 改为 T1 的局域网 IPv4，端口保持 1883。

## 2. 编译与写入

```bash
cd firmware/esphome_rc/f1_0_rc2
bash tools/n1.sh config
bash tools/n1.sh compile
bash tools/n1.sh run --device <N1测试板IP或串口>
```

## 3. 节点本地回归

确认：

- LCD 五页界面和方向正确；
- SCD30、SHT30、BH1750 正常；
- RS485 手动读取至少 5 次成功；
- 土壤传感器断电后 VCC 为 0 V；
- GPIO6 正常运行时稳定常亮；
- 无 Home Assistant API 客户端时节点不重启。

## 4. MQTT 垂直链路

T1 部署 manager 后执行：

```bash
docker exec mosquitto mosquitto_sub \
  -h 127.0.0.1 \
  -t 'gh/v1/greenhouse/state/#' \
  -v
```

等待约 60 秒，应看到：

```text
gh/v1/greenhouse/state/<node_id>/telemetry {...}
gh/v1/greenhouse/state/<node_id>/availability online
```

载荷必须包含：

- `schema=gh.telemetry/1`；
- 稳定 `node_id`；
- 每次启动变化的 `boot_id`；
- 单调递增的 `seq`；
- 传感器、质量和电源字段；
- manager 添加的 `received_at`。

## 5. Broker 断线恢复

只停止 Mosquitto 容器会影响现有 Home Assistant MQTT，因此测试窗口内执行：

```bash
docker stop mosquitto
```

观察 3–5 分钟：

- 节点不重启；
- LCD 和本地传感器继续运行；
- RS485 仍能手动读取；
- GPIO6 不因 MQTT 离线闪烁。

恢复：

```bash
docker start mosquitto
```

恢复后 90 秒内应重新出现 canonical telemetry，且 `seq` 继续递增。

## 6. 回退

N1 测试异常时，通过当前 OTA 路径写回 `f1_0_rc2.yml` 的 N0.3 固件。不要修改稳定节点。
