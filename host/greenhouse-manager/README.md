# greenhouse-manager · M0/M1 MQTT 状态与 Home Assistant 发现

本目录是 V0.5 主机端的可运行服务。M0 负责把节点发布到 MQTT 入口 Topic 的 `gh.telemetry/1` 消息校验、去重并转换为 retained 规范化状态；M1 在此基础上生成 Home Assistant MQTT Discovery 配置。

## 当前职责

1. 订阅节点入口：

   ```text
   gh/v1/<system_id>/ingress/node/+/telemetry
   ```

2. 订阅 retained canonical telemetry，用于 manager 重启后恢复节点生命周期状态：

   ```text
   gh/v1/<system_id>/state/+/telemetry
   ```

3. 校验：
   - Topic 中的 `system_id`；
   - Topic 与载荷中的 `node_id` 是否一致；
   - `gh.telemetry/1` JSON Schema；
   - 节点不得填写 manager 专属的 `received_at`。

4. 去重：

   ```text
   node_id + boot_id + seq
   ```

5. 发布 retained 状态：

   ```text
   gh/v1/<system_id>/state/<node_id>/telemetry
   gh/v1/<system_id>/state/<node_id>/availability
   gh/v1/<system_id>/state/<node_id>/diagnostic
   ```

6. 超过 `GH_STALE_AFTER_S` 未收到新遥测时，将节点 availability 更新为 `unavailable`。

7. manager 或 T1 重启后，从 Broker 中保留的 canonical telemetry 恢复：
   - 每个节点最近一次 `received_at`；
   - 最近一个 `node_id + boot_id + seq` 去重键；
   - 后续 stale 超时判定基础。

8. 为每个节点发布 retained Home Assistant MQTT Discovery：

   ```text
   homeassistant/device/<node_id>/config
   homeassistant/binary_sensor/<node_id>_connectivity/config
   ```

   第一阶段发现实体包括：
   - 空气温度；
   - 空气湿度；
   - 二氧化碳；
   - 光照度；
   - 固件版本；
   - 节点标识；
   - 连接状态。

   设备 Discovery 使用 canonical telemetry 作为状态源，并使用 canonical availability 控制传感器可用性。连接状态单独使用 binary sensor Discovery，以便节点离线时明确显示为关闭，而不是把该实体本身标记为不可用。

恢复机制和 Discovery 均依赖 Mosquitto retained 消息，不在容器内建立数据库，因此仍保持只读根文件系统和无状态部署方式。相同 Discovery 内容不会在每个 60 秒遥测周期重复发布；只有 manager 重启、首次发现节点或设备信息变化时才重新发布。

## 暂未包含

- 注册和配对；
- 动态安全账号与 ACL 下发；
- 独立数据库持久化；
- 命令和配置下行；
- LoRa 网关帧解包；
- VPD、露点、绝对湿度、PPFD、DLI、土壤和电池等完整实体集。

这些能力将在后续 M1 扩展及 M2–M4 分阶段加入。

## 本地测试

Python 版本：3.11 或更高。

```bash
cd host/greenhouse-manager
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
ruff check .
```

## 本地运行

复制环境变量模板：

```bash
cp .env.example .env
set -a
source .env
set +a

greenhouse-manager
```

最小必填配置：

```text
GH_SYSTEM_ID
GH_MQTT_HOST
```

Home Assistant Discovery 配置：

```text
GH_HA_DISCOVERY_ENABLED=true
GH_HA_DISCOVERY_PREFIX=homeassistant
GH_HA_DEVICE_NAME_PREFIX=温室监测节点
```

`GH_HA_DISCOVERY_PREFIX` 必须与 Home Assistant MQTT 集成中的 Discovery Prefix 保持一致。

生产环境必须配置独立的 manager MQTT 账号、TLS 和 Mosquitto ACL；`.env` 不得提交到仓库。

## M0 验收标准

- 有效遥测被发布到 canonical telemetry Topic；
- 相同 `node_id + boot_id + seq` 的重复包不重复发布；
- 非法 JSON、Schema 错误、节点 ID 不匹配被拒绝；
- 非法包不会覆盖上一条有效 retained 状态；
- 节点超时后 availability 变为 `unavailable`；
- 新遥测到达后 availability 恢复为 `online`；
- manager 重启后能够从 retained canonical telemetry 恢复节点最近状态；
- 节点保持离线时，manager 重启后仍能在超时后发布 `unavailable`。

## M1 第一阶段验收标准

- 首次接收或恢复节点 telemetry 后发布 retained Device Discovery；
- 同一节点在 Home Assistant 中只生成一个设备；
- 空气温度、空气湿度、CO₂ 和光照度实体读取 canonical telemetry；
- 固件版本和节点标识归入诊断实体；
- 连接状态随 canonical availability 在在线与离线之间切换；
- manager 或 Home Assistant 重启后，Discovery 和 retained 状态能够自动恢复；
- 相同 Discovery 配置不在每次遥测时重复发布。
