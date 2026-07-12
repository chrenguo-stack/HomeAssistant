# gh-dynsec-profile-v1 每节点与服务最小权限配置

状态：Draft / M2.3k  
关联：ADR-0002、`gh-pairing-v1`、Issue #17

## 1. 范围

本配置冻结 Mosquitto Dynamic Security 的每节点和服务身份计划，并在独立临时 Broker 中执行 ACL、身份绑定、失败回滚、轮换和 legacy anonymous 兼容性验证。真实 T1 Broker、运行中 manager、Home Assistant 和节点凭据不在本阶段修改范围内。

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

1. 创建专属 role 并一次性写入确定性 ACL；
2. 创建绑定唯一 client ID、role 和高熵密码的 client；
3. 任一步失败时按 client → role 顺序尽力回滚；
4. 只有连接与 ACL 矩阵验证通过后，才允许把该 generation 标记为 active；
5. 失败不得修改上一代 active identity。

Dynamic Security 管理账号不得兼任 manager 遥测账号。真实环境的控制链路最终必须使用 TLS；明文 1883 只允许隔离实验。

## 7. 秘密处理

- 密码不得进入 repr、日志、异常、审计事件、Home Assistant 或 Git；
- 命令行参数不得携带节点或服务密码；
- 隔离测试凭据只存在于测试进程内存和临时 Dynamic Security 状态；
- 后续真实迁移必须使用受保护的 secret file、stdin 或等价秘密挂载；
- 生成失败不得复用部分随机值。

## 8. M2.2a 验收

- 两节点计划的身份和允许 Topic 完全隔离；
- 默认 send/receive/subscribe 均为 deny；
- `$CONTROL`、Discovery 和 canonical state 显式拒绝；
- 密码至少 256 位且 repr 脱敏；
- 本阶段没有 Broker、T1 或真实节点副作用。

## 10. M2.2c 凭据轮换与回滚

1. 新 generation 必须严格大于当前 generation；
2. Broker 先写入候选密码；
3. manager 使用候选 username、client ID 和密码执行一次独立连接探测；
4. 探测成功后，旧密码必须无法重新连接；
5. 探测失败时立即恢复上一代密码；
6. 若恢复也失败，返回不含密码的明确错误并停止自动推进，禁止把未知状态报告为成功。

隔离测试必须覆盖成功轮换和失败回滚。T1 影子部署前仍不向真实 Broker 写入任何账号或 ACL。

## 11. M2.3g 服务身份

真实迁移不得复用节点账号或初始 admin，必须建立三个独立服务身份：

| 身份 | client ID | 允许范围 |
|---|---|---|
| provisioning | `gh-provisioning-<sid>` | Dynamic Security 请求及响应 Topic |
| manager | `gh-manager-<sid>` | 节点 ingress、canonical state、两类现用 Discovery、配对 hello |
| Home Assistant | `gh-homeassistant-<sid>` | 读取 Discovery 与 canonical state；发布 `homeassistant/status` |

所有身份使用独立 256 位随机密码、唯一 username/client ID/role 和单调 generation。provisioning 明确拒绝 `gh/#` 与 `homeassistant/#`；manager 和 Home Assistant 明确拒绝 `$CONTROL/#`。Home Assistant 当前不得向 `gh/#` 发布，控制下行必须在后续协议冻结后单独授权。

## 12. M2.3h 统一事务下发

节点与服务身份共用同一 Dynamic Security 事务适配器：先创建 role，再创建绑定唯一 client ID 和 role 的 client；任一步失败均按 client → role 顺序尽力回滚。凭据对象的 username、client ID 和 generation 必须与计划完全一致，否则在连接 Broker 前拒绝。

服务身份接入不得改变全局默认拒绝基线，也不得复用 legacy anonymous role。

## 13. M2.3i 隔离 Broker 服务身份执行矩阵

独立 `infra/compose/m2-dynsec` Broker 必须实际创建 provisioning、manager、Home Assistant 和节点 `gh-n1-a9f2f8`，并执行以下 gate：

1. 节点只能发布自身 ingress；manager 必须能接收，其他节点 ingress 必须拒绝；
2. manager 可以发布 canonical state 和当前两类 Discovery；Home Assistant 必须能接收；
3. manager 不得发布 `homeassistant/status`、任意未授权 Discovery、节点 ingress 或 `$CONTROL/#`；
4. Home Assistant 只能发布 `homeassistant/status`，不得写 canonical state、ingress 或 `$CONTROL/#`；
5. provisioning 必须能执行 Dynamic Security 请求并接收响应，但不得订阅或发布 `gh/#`、`homeassistant/#`；
6. 四类 username 必须分别绑定冻结的唯一 client ID，错误 client ID 必须拒绝连接；
7. 注入 client 已创建后的失败，必须在真实隔离 Broker 上观察到 `deleteClient` → `deleteRole`，且两个对象均消失；
8. 回滚后 legacy anonymous 应用 Topic 发送和接收仍正常，匿名 `$CONTROL/#` 仍被拒绝；
9. 原有节点轮换、失败恢复、撤销和跨节点隔离测试必须继续通过；
10. 测试密码不得写入仓库、测试输出或 Broker 失败日志，Compose 结束必须删除临时卷。

该 gate 通过后，下一步才允许把同一四身份矩阵扩展到 `--network none` 的真实 T1 快照候选；仍不得修改真实 Broker 或关闭匿名访问。

## 14. M2.3k MQTT ACL 过滤器可移植性

真实 T1 快照候选首次执行发现，`homeassistant/binary_sensor/+_connectivity/config` 在目标 Mosquitto 中不会匹配 `homeassistant/binary_sensor/<object_id>_connectivity/config`。MQTT 通配符必须遵守标准层级规则：

- `+` 必须独占一个完整 Topic 层级；
- `#` 必须独占最后一个 Topic 层级；
- Dynamic Security 的 `%c`、`%u` 替换符必须独占一个完整层级。

manager 的现用二进制传感器 Discovery 权限固定为：

```text
allow publishClientSend homeassistant/binary_sensor/+/config
```

代码必须在生成 role 前拒绝任何不符合上述规则的 ACL。隔离 Broker CI 通过不能替代真实快照所记录 Mosquitto 镜像的兼容性 gate。
