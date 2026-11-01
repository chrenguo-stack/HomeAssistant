# N3-W T1 Home Assistant clean-product bootstrap source

Status: `SOURCE_CANDIDATE_ONLY`.

本目录只定义 clean-product T1 的 Home Assistant MQTT 首次配置源码和部署合同，不构成 live T1 安装授权。

## Source-to-runtime mapping

工厂/正式部署阶段必须把：

```text
infra/n3w-t1/homeassistant/custom_components/n3w_mqtt_bootstrap/
```

安装到目标 Home Assistant `/config/custom_components/n3w_mqtt_bootstrap/`，并把 `configuration-snippet.yaml` 的配置合并进正式 `configuration.yaml`。

运行时只读挂载：

```text
host homeassistant/password
-> /run/secrets/gh_homeassistant_mqtt_password

host homeassistant/mqtt-bootstrap.json
-> /run/n3w/ha-mqtt-bootstrap.json
```

两者都必须为普通非符号链接私有文件；密码文件与 Home Assistant 实际运行 UID 必须一致。部署前由 clean-product deployment gate 检查两个 mount 均为 read-only。

## Bootstrap semantics

首次启动且没有 MQTT config entry 时，`n3w_mqtt_bootstrap` 调用 Home Assistant 自己的 MQTT config flow：

```text
source=user
broker=127.0.0.1
port=1883
protocol=5
username=<service identity>
password=<read from private password file>
client_id=<service identity>
CA=off
transport=tcp
```

它不直接编辑 `.storage`。

如果已存在恰好一个 MQTT entry，只有当 endpoint、username、client ID 和 password 都与当前 private material 精确一致时才 no-op PASS。任何不一致或存在多个 MQTT entry 时 fail closed，不自动重配、不覆盖现有用户配置。

密码轮换不是 bootstrap 的职责，必须继续走独立 rotation gate。

## Broker dependency

该 bootstrap 依赖生产 Broker 已经通过安全 gate 启动，并且宿主仅存在：

```text
127.0.0.1:1883 -> broker:1883/tcp
0.0.0.0:8883 -> broker:8883/tcp/TLS
```

1883 只允许 loopback publication，不能变成 LAN/wildcard listener。Broker 仍使用全局 Dynamic Security、`allow_anonymous false`，不重新引入 `per_listener_settings`。

Home Assistant 启动顺序必须在 Broker 1883 loopback authenticated endpoint ready 之后；源码单元测试不能替代 exact Home Assistant image 的隔离 runtime acceptance。

## Hard boundaries

```text
DIRECT_STORAGE_EDIT=false
BROKER_DYNSEC_MUTATION_BY_HA=false
ADMIN_SECRET_READ=false
NODE_CREDENTIAL_CREATION=false
BOARD_ACCESS=false
```
