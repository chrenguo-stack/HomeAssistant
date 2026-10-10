# N3-W T1 S16 全新动态权限默认拒绝与业务服务身份计划（2026-10-10）

## S15 入门事实

T1 新 `/etc/n3wfc4/mosquitto.conf` 已以精确 SHA-256 `3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6` 成功创建，Mosquitto 2.1.2 `--test-config` 返回 0；仅使用新 Broker CA/server 证书/动态权限数据库，无对外监听。S15 = PASS，不能推导业务账号或端到端 TLS 已完成。

## 当前主线代码真值

根据现有 `host/greenhouse-manager/src/greenhouse_manager/runtime/dynsec_plan.py`、`service_identity_plan.py`、`dynsec_api.py` 与 `protocols/pairing/gh-dynsec-profile-v1.md`：

- `system_id=greenhouse`；provisioning、manager、homeassistant 三类服务需分别使用 `ghs_greenhouse_<service>` 用户名、`gh-<service>-greenhouse` 唯一 MQTT client id、`gh-service-greenhouse-<service>` 专用 role，generation=1，独立的至少 256-bit 随机密码。
- 节点账号严格在真正的首次配对过程中产生，每台独立的 `ghn_<node_id>`、client ID `<node_id>`、`gh-node-greenhouse-<node_id>`、随机密码与 generation；不得把服务账号、管理员账号或一个共用“node”帐号冒充真实节点。
- 默认 ACL 必须为 `publishClientSend=false`、`publishClientReceive=false`、`subscribe=false`、`unsubscribe=true`。管理员初始 `mosquitto_ctrl dynsec init` 成功 **并不证明**初始默认 ACL 完全匹配上述值，必须现场读取取证，只有后续受控权限初始化可修补。
- `provisioning`：仅可写 `$CONTROL/dynamic-security/v1`，读取相应 `.../response`，明确禁止应用 `gh/#` 和 `homeassistant/#`。
- `manager`：接收 `gh/v1/greenhouse/ingress/node/+/telemetry`、`.../ingress/gateway/+/+/frame` 等限定 ingest；允许发布 `gh/v1/greenhouse/state/#` 以及 `homeassistant/device/+/config`、`homeassistant/binary_sensor/+/config`；禁止直接写 `$CONTROL/#`、节点 ingress 和 `homeassistant/status`。
- `homeassistant`：接收 `homeassistant/#`、`gh/v1/greenhouse/state/#`，只能发布 `homeassistant/status`；禁止写节点 ingress、canonical state 或 `$CONTROL/#`。
- 权限需区分 `subscribePattern` 和 `publishClientReceive`，防止客户端无权订阅但仍可接收消息。`+` 和 `#` 必须按 MQTT 标准占完整层级。服务的用户名和绑定的 MQTT client id 都要通过实测；不能只检测一个。
- ACL 及账号变更采用隔离 Broker 同机无外部网络、真实 DynSec JSON 的复制候选进行整套测试，不手工猜测 JSON 密码哈希格式，不在主 Broker 上直接凭明文命令行批量初始化。后续权限确认与 promote 的执行门需 separate gate，失败不覆盖 S14 原始持久数据。

## S16 现场只读证据要求

1. 镜像、配置 SHA、证书指纹、S14 admin-only 状态与 root 密码文件权限仍匹配；只报告 JSON 的安全结构、客户端数/角色数/组数、`defaultACLAccess` 的四项布尔值、状态 SHA-256，绝不打印 DynSec JSON 内容、password/salt/hashes。
2. `n3wfc4-private` 和 `n3wfc4-services` 无容器，原 45 volumes 完整、入口防护 active / enabled、INPUT 和 DOCKER-USER 跳转规则第一条、守护链最终 DROP、8883 无监听。
3. 不对 `/etc/n3wfc4/private/dynsec-admin-password` 执行读取，只查 root/0600 元信息。
4. 与 S15 一样原样 STOP；即使发现默认 `publishClientReceive=true` 也只报告 `BASELINE_REPAIR_REQUIRED`，不得悄悄修改 JSON 或默认 ACL；不将未符合源计划的默认值宣称为 PASS。

```text
S15=PASS
S16_GATE=FRESH_DYNSEC_DEFAULTS_AND_SERVICE_PLAN_READONLY
S16_EXTERNAL_PORTS=ZERO
S16_RUNTIME_MUTATION=false
S16_DYNSEC_MUTATION=false
S16_SECRET_OUTPUT=false
S16_BOARD_ACCESS=false
NEXT_AFTER_S16=ISOLATED_CANDIDATE_DEFAULT_DENY_PLUS_SERVICE_ACLS
PR541=OPEN_DRAFT
```

源文件描述已有正式身份规划；新 T1 实际身份/权限尚未创建，不得误标为产品业务认证 PASS。
