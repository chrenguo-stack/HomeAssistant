# gh-dynsec-profile-v1 每节点最小权限配置

状态：Draft / M2.2a  
关联：ADR-0002、`gh-pairing-v1`、Issue #17

## 1. 范围

本阶段只冻结并生成 Mosquitto Dynamic Security 的每节点计划，不连接真实 Broker。账号创建、密码设置、启用和回滚由后续隔离集成阶段实现。

## 2. 身份

```text
username = ghn_<node_id>
client_id = <node_id>
role = gh-node-<system_id>-<node_id>
password = 32 random bytes, unpadded base64url
generation = monotonic uint32
```

用户名必须绑定唯一 client ID。不同节点不得共享账号、角色或密码。

## 3. 默认访问

| 事件 | 默认 |
|---|---|
| publishClientSend | deny |
| publishClientReceive | deny |
| subscribe | deny |
| unsubscribe | allow |

必须显式把 `publishClientReceive` 改为 deny；Mosquitto Dynamic Security 初始配置的该项可能为 allow，不能依赖 subscribe ACL 单独完成数据隔离。

## 4. 节点允许项

```text
allow publishClientSend    gh/v1/<sid>/ingress/node/<node_id>/#
allow subscribePattern     gh/v1/<sid>/out/node/<node_id>/#
allow publishClientReceive gh/v1/<sid>/out/node/<node_id>/#
allow unsubscribePattern   gh/v1/<sid>/out/node/<node_id>/#
```

## 5. 防御性拒绝

高优先级拒绝：

```text
$CONTROL/#
homeassistant/#
gh/v1/<sid>/state/#
```

默认拒绝还应覆盖其他 node_id、`$SYS/#` 和未声明的应用 Topic。

## 6. 安全创建顺序

1. 创建无密码 client，并绑定 client ID；
2. client 此时无法连接；
3. 创建/校验专属 role；
4. 添加 ACL；
5. 绑定 role；
6. 设置高熵密码；
7. 仅在完整验证后启用 client；
8. 失败时删除新 client/role，不修改旧 generation。

Dynamic Security 管理账号不得兼任 manager 遥测账号。真实环境的控制链路最终必须使用 TLS；明文 1883 只允许隔离实验。

## 7. 秘密处理

- 密码不得进入 repr、日志、异常、审计事件、Home Assistant 或 Git；
- 命令行参数不得携带密码；
- 后续控制适配器应使用受保护的 MQTT 控制载荷或 stdin/secret file；
- 生成失败不得复用部分随机值。

## 8. M2.2a 验收

- 两节点计划的身份和允许 Topic 完全隔离；
- 默认 send/receive/subscribe 均为 deny；
- `$CONTROL`、Discovery 和 canonical state 显式拒绝；
- 密码至少 256 位且 repr 脱敏；
- 本阶段没有 Broker、T1 或真实节点副作用。
