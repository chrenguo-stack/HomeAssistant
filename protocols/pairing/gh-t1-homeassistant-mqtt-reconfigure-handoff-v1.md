# gh-t1-homeassistant-mqtt-reconfigure-handoff-v1

## 1. 状态与目的

状态：Draft / M2.4g-4  
关联：Issue #17、`gh-t1-homeassistant-mqtt-target-gate-v1`、`gh-node-credential-delivery-v1`

本协议定义 Home Assistant MQTT integration 从匿名 Broker 连接迁移到独立认证身份之前的人工交接包、即时回退材料、官方 UI 操作边界和后置校验。

该阶段不自动调用 Home Assistant config-flow，不编辑 `.storage`，不重启 Home Assistant，不修改 Broker、manager 或节点。

## 2. 已验证的真实 T1 目标模型

M2.4g 真实 T1 只读审计结果：

```text
Home Assistant network mode = host
Mosquitto network mode       = ha_docker_default
shared Docker networks       = 0
Docker alias mosquitto       = unresolved / unreachable from Home Assistant
loopback 127.0.0.1:1883      = reachable and topology eligible
T1 host address              = reachable but fallback not authorized
selected target kind         = loopback
selected target fingerprint  = 12ca17b49af22894
```

因此当前 Home Assistant MQTT 目标必须使用经审计的 host-network loopback 模型。不得把迁移包中历史占位值 `mosquitto` 直接填入 Home Assistant。

## 3. 官方重配置路径

Home Assistant MQTT Broker 设置只能通过官方 UI/config-flow 修改：

```text
Settings
  → Devices & services
  → MQTT
  → Reconfigure
```

迁移值包括：

- Broker host；
- port；
- username；
- password；
- Advanced options 中的自定义 client ID。

MQTT discovery 必须继续启用。不得删除并重新添加 integration，不得直接修改：

```text
/config/.storage/core.config_entries
```

## 4. 执行顺序

正式人工操作必须满足以下顺序：

1. Broker Dynamic Security 候选已经安装；
2. Home Assistant 独立身份已经创建；
3. 该身份通过独立 MQTT v5 连接和 ACL 校验；
4. 匿名访问仍保持；
5. 重新运行 target gate，确认 loopback、entry 指纹和 storage SHA 未漂移；
6. 立即生成新的 reconfigure handoff；
7. operator authorization gate 明确通过；
8. 用户只在 Home Assistant UI 中提交一次；
9. 立即运行 postcheck；
10. 失败时优先使用官方 UI 回退旧值。

当前 `broker_identity_not_activated` 尚未解除，因此本协议实现固定输出：

```text
operator_action_authorized = false
ready_for_operator_reconfigure = false
```

不得仅因为 handoff 文件已经生成就执行 UI 操作。

## 5. 私有交接目录

`prepare` 创建模式为 `0700` 的本地目录：

```text
greenhouse-ha-mqtt-handoff-<UTC>-<token>/
├── manifest.json
├── operator-runbook.txt
├── homeassistant/
│   ├── core.config_entries.before.json
│   ├── reconfigure-values.json
│   └── rollback-values.json
└── rollback/
    └── greenhouse-t1-rollback-<UTC>-<token>.tar.gz
```

目录及其内容不得提交 Git、上传 Issue、复制到 Home Assistant 状态或输出到普通日志。

所有文件模式必须为 `0600`。

## 6. 前置绑定

交接包必须绑定以下真实 T1 证据：

```text
target kind                 = loopback
target fingerprint          = 12ca17b49af22894
MQTT entry fingerprint      = 9dda2c31088e933e
core.config_entries SHA-256 = ea9a9dd59e308a85a5bbf32dceb54629b9674f7fa4af162ca03bb60ce4315b15
```

上述值只代表 2026-07-12 的审计基线。正式迁移前必须重新审计；任何变化都不得沿用旧指纹。

## 7. 回退材料

### 7.1 通用 T1 回退包

现有 `greenhouse-t1-rollback` 包保存 Mosquitto 配置、Mosquitto 数据和 greenhouse-manager 数据，用于 Broker/manager 侧恢复。

### 7.2 Home Assistant 专用检查点

通用回退包不包含 Home Assistant `.storage`。因此 handoff 必须另外保存：

```text
homeassistant/core.config_entries.before.json
```

该文件是完整原始快照，仅供紧急恢复设计使用。当前：

```text
emergency_storage_restore_authorized = false
```

不得在 Home Assistant 运行期间覆盖该文件。紧急文件级恢复需要独立的停机、校验、恢复和启动门禁，尚未授权。

### 7.3 官方 UI 回退值

`rollback-values.json` 保存原 MQTT entry 的 `data` 和 `options`，用于首选回退方法：

```text
MQTT → Reconfigure → 填回旧值
```

该文件可能包含秘密，必须保持本机私有。

## 8. 迁移值

`reconfigure-values.json` 保存：

```text
schema
official_config_flow_only
broker
port
username
password
client_id
generation
preserve_discovery
advanced_options_required
```

对当前真实 T1，Broker host 由审计结果映射为 `127.0.0.1`，而不是迁移包内历史占位值。

工具的普通 JSON 报告不得输出：

- Broker 原值；
- username；
- password；
- client ID；
- MQTT entry ID 原值；
- `.storage` 原文。

## 9. 后置校验

`postcheck` 只读验证：

- MQTT entry ID 指纹未改变；
- `.storage` SHA 已改变；
- broker、port、username、password、client ID 与交接值一致；
- discovery 未关闭；
- Home Assistant 容器保持 running；
- restart count 为 0。

通过时：

```text
reconfigure_verified = true
rollback_required = false
ready_for_live_apply = false
```

即使 Home Assistant 重配置成功，节点交付和匿名关闭仍然没有自动授权。

任何字段不一致、entry 被替换、discovery 被关闭、容器异常或 storage 未变化时：

```text
reconfigure_verified = false
rollback_required = true
```

此时不得继续 manager、节点或匿名关闭步骤。

## 10. 明确禁止

本阶段不得：

- 通过脚本调用 Home Assistant config-flow 写接口；
- 直接编辑 `.storage`；
- 自动提交 MQTT UI 表单；
- 在 Broker 身份未验证时使用新凭据；
- 在正常回退中复制原始 `.storage` 快照；
- 将 handoff 目录上传到 GitHub；
- 输出任何密码或完整 entry ID；
- 关闭匿名访问；
- 向真实节点下发凭据。

## 11. 下一门

下一开发门是 Broker 身份候选的可回退激活与只读验证。该门必须保持匿名兼容，先验证 Home Assistant 独立身份能够完成 MQTT v5 CONNECT 和规定 ACL，再允许重新生成 fresh handoff 和人工 UI 操作授权。
