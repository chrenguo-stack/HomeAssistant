# N3-W T1 S20 Home Assistant 自动 MQTT 凭据消费 source design（2026-10-10）

## 1. 目的

S20 fresh source preflight 已确认 Manager 与 Provisioning 的文件读取接口存在，但 Home Assistant clean-product 自动消费路径缺失。产品目标不接受“Broker 账号创建后再让用户手工抄一遍密码进 Home Assistant”。

本设计只解决源码与部署合同，不执行 T1、Broker、Home Assistant 或板卡 mutation。

```text
LIVE_RUNTIME_MUTATION=false
PRODUCTION_CLIENT_CREATION=false
PRODUCTION_BROKER_START=false
HOST_8883_PUBLICATION=false
HOMEASSISTANT_STORAGE_DIRECT_EDIT=false
BOARD_ACCESS=false
```

## 2. 上游事实

2026-10-10 Home Assistant stable authority 已 fresh 核对为 `2026.10.0`。本轮 source feasibility 绑定：

```text
HOMEASSISTANT_CANDIDATE_IMAGE_REF=ghcr.io/home-assistant/home-assistant:2026.10.0
HOMEASSISTANT_UPSTREAM_SOURCE_TAG=2026.10.0
MQTT_CONFIG_FLOW_BLOB=9181013edc6686b6ac482b4061b3f5e48ba4ff77
HOMEASSISTANT_OCI_DIGEST=UNBOUND_PENDING_EXACT_IMAGE_PREFLIGHT
```


Home Assistant 当前 MQTT 官方文档仍把 Broker host/port/username/password/custom client ID 作为 MQTT integration 的 config-flow 配置。项目已有迁移协议也冻结：

```text
official_config_flow_only=true
direct_storage_edit_forbidden=true
```

对 exact `2026.10.0` upstream `homeassistant/components/mqtt/config_flow.py` 的 source feasibility review 观察到：

- MQTT `async_step_user()` 进入 broker setup；
- broker step 能根据输入验证真实 MQTT 连接并创建 config entry；
- reconfigure 也复用 broker step；
- 当前源码没有 MQTT `async_step_import()`；
- custom CA 的初次配置走 file-upload 路径，因此如果强行自动配置私有 CA/TLS，会把 source repair 与 Home Assistant 内部上传实现深度耦合。

这只是 upstream feasibility evidence，不是本项目 exact production image binding。正式 runtime 仍须绑定 exact HA image/version 后重验。

## 3. 选定的低复杂度路线

不直接编辑 `.storage`，也不自动操纵浏览器 UI。新增一个很小的 T1 专用 Home Assistant custom integration：

```text
custom_components/n3w_mqtt_bootstrap
```

它运行在 Home Assistant 进程内部，只在没有 MQTT config entry 时调用 Home Assistant 自己的 config-flow manager 完成第一次 MQTT integration 创建。

凭据来源：

```text
host private service credential root
  -> homeassistant/password
  -> read-only bind
  -> /run/secrets/gh_homeassistant_mqtt_password

host private bootstrap metadata
  -> homeassistant/mqtt-bootstrap.json
  -> read-only bind
  -> /run/n3w/ha-mqtt-bootstrap.json
```

metadata 只包含 broker endpoint、username、client ID、password-file target，不包含密码正文。

custom integration 只允许三种结果：

```text
0 MQTT entry
  -> run one official config flow
  -> verify create_entry
  -> PASS

1 MQTT entry and exact non-secret identity + password match
  -> no-op
  -> PASS

multiple entries or any mismatch
  -> FAIL_CLOSED
  -> no automatic reconfigure
```

密码轮换仍是单独 gate；bootstrap 不负责“看见不一致就自动改”。

## 4. 为什么增加一个 loopback-only MQTT listener

当前 fresh Broker source 只有 TLS/8883。Home Assistant 的 custom-CA 首次 config-flow 需要 upload semantics。为避免把产品安装绑死到 HA file-upload 内部细节，新增一个仅宿主 loopback 可见的 authenticated MQTT listener：

```text
127.0.0.1:1883 -> Broker 1883/tcp
allow_anonymous=false
Dynamic Security=enabled

0.0.0.0:8883 -> Broker 8883/tcp/TLS
allow_anonymous=false
Dynamic Security=enabled
```

外部节点和 Manager 的现有 TLS/8883 路线不变；1883 不得绑定 LAN wildcard，不得从客户网络访问。该 listener 只服务同一 T1 的 Home Assistant 初始/持续 MQTT 连接。

```text
KF097_PUBLIC_TLS_8883_GUARD=UNCHANGED
MANAGER_LOOPBACK_TLS_8883=UNCHANGED
NODE_TLS_8883=UNCHANGED
HA_LOOPBACK_1883_AUTH_ONLY=NEW
```

不得重新引入 Mosquitto 2.1 已关闭的 `per_listener_settings` 旧写法；继续使用一个 `global_plugin` Dynamic Security authority。

## 5. source guard

clean-product deployment gate 必须新增以下机器可查条件：

```text
BROKER_TLS_PUBLICATION=0.0.0.0:8883->8883/tcp
BROKER_HA_LOOPBACK_PUBLICATION=127.0.0.1:1883->1883/tcp
HOST_8883_OWNER=broker_only
HOST_1883_OWNER=broker_only
HOST_1883_NON_LOOPBACK_PUBLICATION_COUNT=0
MANAGER_NETWORK_MODE=host
MANAGER_PORTS=[]
HOMEASSISTANT_NETWORK_MODE=host
HOMEASSISTANT_PORTS=[]
HA_PASSWORD_MOUNT_READONLY=true
HA_BOOTSTRAP_METADATA_MOUNT_READONLY=true
```

任何 `0.0.0.0:1883`、LAN-IP:1883、额外 1883 owner 均 fail closed。

## 6. custom integration 安全规则

- password file：绝对路径、regular、非 symlink、mode 0600、owner 与 HA runtime UID 一致；
- metadata file：绝对路径、regular、非 symlink、group/other 不可读；
- 不输出 password、config-entry ID、完整 metadata；
- flow failure 只记录固定错误类；
- existing entry 不匹配时禁止自动 reconfigure；
- 不直接读写 `.storage`；
- 不创建/修改 Broker DynSec；
- 不读取管理员密码；
- 不生成 node credential；
- 不访问板卡。

## 7. source repair 分段

R1：clean three-service credential bundle；Manager + Provisioning separate file bindings；Home Assistant password + bootstrap metadata staging；zero node credentials。

R2：`n3w_mqtt_bootstrap` custom integration source；使用 fake HA config-flow manager 做纯源码/单元测试；仓库 CI 不安装 Home Assistant。

R3：fresh Broker config 新增 authenticated listener 1883；clean-product deployment gate 强制 loopback-only publication；既有 wildcard TLS/8883 guard 保持。

R4：绑定 exact Home Assistant image 后，用隔离容器执行真实 config-flow bootstrap acceptance，并证明：

```text
DIRECT_STORAGE_EDIT=false
PLAINTEXT_PASSWORD_OUTPUT=false
MQTT_ENTRY_COUNT=1
MQTT_ENTRY_CREATED_BY_CONFIG_FLOW=true
HA_AUTHENTICATED_MQTT_CONNECT=PASS
CONTAINER_RECREATE_PERSISTENCE=PASS
BOOTSTRAP_SECOND_RUN=NOOP_PASS
```

R4 之前不得声称 HA runtime consumer 已闭环。

## 8. 当前授权边界

本设计与 source repair 不构成生产部署授权。

```text
READY_FOR_REAL_SERVICE_IDENTITY_AUTHORIZATION=false
T1_RUNTIME_MUTATION=false
HOMEASSISTANT_RUNTIME_MUTATION=false
BROKER_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PR_MERGE=false
```
