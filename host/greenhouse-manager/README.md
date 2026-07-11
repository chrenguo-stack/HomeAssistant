# greenhouse-manager · M0 遥测入口

本目录是 V0.5 主机端的第一个可运行服务骨架。M0 只完成一件事：把节点发布到 MQTT 入口 Topic 的 `gh.telemetry/1` 消息校验、去重并转换为 retained 规范化状态。

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

该恢复机制依赖 Mosquitto retained 消息，不在容器内建立数据库，因此仍保持只读根文件系统和无状态部署方式。

## 暂未包含

- 注册和配对；
- 动态安全账号与 ACL 下发；
- Home Assistant Discovery；
- 独立数据库持久化；
- 命令和配置下行；
- LoRa 网关帧解包。

这些能力在 M1–M4 分阶段加入，不会阻塞 M0 的入口链路测试。

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
