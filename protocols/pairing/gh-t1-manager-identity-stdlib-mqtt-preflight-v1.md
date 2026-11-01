# T1 manager identity stdlib MQTT preflight v1

状态：M2.4g-6p Draft

## 背景

6o production execution packet 在 T1 宿主机 Python 中运行，而 `greenhouse-manager` 服务容器拥有独立的 Python 依赖环境。真实首次执行在授权 claim 前因宿主机缺少 `paho-mqtt` 安全失败。该问题不应通过临时安装依赖或重放旧授权解决。

## 目标

本协议定义一个仅依赖 Python 3.11 标准库的 MQTT 3.1.1 retained-state reader，并将其固定为 T1 6o 工具的匿名兼容性读取实现。正式创建 6i/6j 短时材料前必须先运行 preflight。

## 允许的网络行为

1. 连接绑定的本机 MQTT 端口；
2. 发送匿名 MQTT CONNECT，Clean Session=true；
3. 对一个精确 Topic 发送 QoS 0 SUBSCRIBE；
4. 接收 CONNACK、SUBACK 和一条非空 retained PUBLISH；
5. 发送 DISCONNECT 并关闭 TCP 连接。

禁止行为：

- 发送任何 PUBLISH；
- 使用 `+` 或 `#` 通配符；
- 订阅 `gh/` 和 `homeassistant/` 之外的 Topic；
- 输出 retained payload；
- 修改 retained state、Broker 配置、容器或凭据。

## Preflight 输出

成功报告必须包含：

- `stdlib_mqtt_reader_ready=true`；
- `anonymous_connect_verified=true`；
- `exact_topic_subscribe_verified=true`；
- `retained_payload_verified=true`；
- `publish_performed=false`；
- `retained_state_modified=false`；
- `current_services_modified=false`；
- `payload_included=false`；
- `secret_values_included=false`；
- `preserve_anonymous=true`；
- `anonymous_closure_enabled=false`。

## 6o 绑定

T1 工具 `run_t1_manager_identity_migration_production_execution_packet.py` 必须显式向 6n runtime probe 注入本标准库 reader。工具不得依赖宿主机安装 paho。服务容器中的正式 manager MQTT client 仍可继续使用项目声明的 paho 依赖，两者互不替代。

## 失败语义

- CONNECT、CONNACK、SUBACK、retained PUBLISH、Topic、payload 或超时任一验证失败，preflight 必须非零退出；
- preflight 失败时不得生成新的短时授权材料；
- 6o 在 authorization claim 前失败时，不得复用旧授权或旧确认短语；
- 任何旧 6e/6f/6i/6j/6k 材料均视为作废，必须从新源码重新生成。

## 安全边界

本协议不授权真实迁移，不允许修改 Mosquitto、Home Assistant、节点或关闭匿名访问。真实 6o apply 仍必须经过新的 6e/6f/6i/6j、第一次操作员确认、6k 和第二次操作员确认。
