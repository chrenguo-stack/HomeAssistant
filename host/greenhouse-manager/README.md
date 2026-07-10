# greenhouse-manager · M0 遥测入口

本目录是 V0.5 主机端的第一个可运行服务骨架。M0 只完成一件事：把节点发布到 MQTT 入口 Topic 的 `gh.telemetry/1` 消息校验、去重并转换为 retained 规范化状态。

## 当前职责

1. 订阅：

   ```text
   gh/v1/<system_id>/ingress/node/+/telemetry
   ```

2. 校验：
   - Topic 中的 `system_id`；
   - Topic 与载荷中的 `node_id` 是否一致；
   - `gh.telemetry/1` JSON Schema；
   - 节点不得填写 manager 专属的 `received_at`。

3. 去重：

   ```text
   node_id + boot_id + seq
   ```

4. 发布 retained 状态：

   ```text
   gh/v1/<system_id>/state/<node_id>/telemetry
   gh/v1/<system_id>/state/<node_id>/availability
   gh/v1/<system_id>/state/<node_id>/diagnostic
   ```

5. 超过 `GH_STALE_AFTER_S` 未收到新遥测时，将节点 availability 更新为 `unavailable`。

## 暂未包含

- 注册和配对；
- 动态安全账号与 ACL 下发；
- Home Assistant Discovery；
- 数据持久化；
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
- 新遥测到达后 availability 恢复为 `online`。
