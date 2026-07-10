# greenhouse-simulator

用于 V0.5 主机端开发的 MQTT 监测节点模拟器。它生成符合 `gh.telemetry/1` 的遥测数据，不依赖 ESP32 实板即可测试 Mosquitto 和 `greenhouse-manager`。

## 默认行为

- 每 10 秒发布一条遥测；
- 启动时生成新的 `boot_id`；
- `seq` 从 0 单调递增；
- QoS 1，入口消息不 retain；
- 默认持续运行。

入口 Topic：

```text
gh/v1/<system_id>/ingress/node/<node_id>/telemetry
```

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `GH_SYSTEM_ID` | `devsystem` | 系统 ID |
| `GH_NODE_ID` | `node_01HZX7AQ5FJ3` | 稳定节点 ID |
| `GH_MQTT_HOST` | `mosquitto` | Broker 主机 |
| `GH_MQTT_PORT` | `1883` | Broker 端口 |
| `GH_SIM_INTERVAL_S` | `10` | 发布间隔 |
| `GH_SIM_INITIAL_DELAY_S` | `2` | 首次发布前等待 |
| `GH_SIM_COUNT` | `0` | 主消息数量，0 表示持续运行 |
| `GH_SIM_DUPLICATE_EVERY` | `0` | 每 N 条追加一次完全相同的重复包 |
| `GH_SIM_INVALID_EVERY` | `0` | 每 N 条生成一次湿度越界的非法包 |

## 本地测试

```bash
cd host/simulator
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
ruff check .
```

通常不需要单独运行本服务，使用 `infra/compose/m0` 可以同时启动 Mosquitto、manager、模拟节点和状态观察器。
