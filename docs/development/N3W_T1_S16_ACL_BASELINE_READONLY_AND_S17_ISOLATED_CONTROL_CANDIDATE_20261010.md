# N3-W T1 S16 默认 ACL 只读验收及 S17 隔离修复预演（2026-10-10）

## S16 T1 现场依据

用户执行只读 gate 返回：

```text
S16_PRECHECK=PASS
IMAGE_ID_MATCH=True
CONFIG_SHA_MATCH=True
DYNSEC_STATE_SHA256=93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da
DYNSEC_CLIENT_COUNT=1
DYNSEC_ADMIN_ONLY=True
DYNSEC_ROLE_COUNT=1
DYNSEC_GROUP_COUNT=UNKNOWN
DEFAULT_publishClientSend=False
DEFAULT_publishClientReceive=True
DEFAULT_subscribe=False
DEFAULT_unsubscribe=True
S16_DEFAULT_ACL_BASELINE=REPAIR_REQUIRED
DYNSEC_STATE_UNCHANGED=True
DYNSEC_MUTATION=False
PASSWORD_CONTENT_READ=False
BROKER_STARTED=False
HOST_8883_PUBLICATION=False
BOARD_ACCESS=False
S16_READONLY_RESULT=PASS
SSH_OR_REMOTE_EXIT_CODE=0
```

结果定义：S16 只读取证门 `PASS`，但产品强制 ACL 四元组尚未通过。唯一异常是 `publishClientReceive=true`；`S14` 使用 `mosquitto_ctrl dynsec init` 创建此默认值是插件已知行为，不属于初始化失败，也不意味证书或 Broker 运行失败。未读明文密码、未修改真实 Dynamic Security JSON。

权威 `host/greenhouse-manager/src/greenhouse_manager/runtime/dynsec_plan.py` 中 `DynsecDefaultAccess` 定义为 publishClientSend=false、publishClientReceive=false、subscribe=false、unsubscribe=true。官方 Mosquitto Dynamic Security 文档也写明 `init` 默认 publishClientReceive=allow，正确在线命令为 `mosquitto_ctrl dynsec setDefaultACLAccess publishClientReceive deny`，该命令须连接运行中、已认证的 Broker，**初始化命令本身是例外，不能在停机状态把 setDefaultACLAccess 当离线变更器**。参考 `https://mosquitto.org/documentation/dynamic-security/` 及 `https://github.com/eclipse-mosquitto/mosquitto/blob/master/plugins/dynamic-security/README.md`。

## S17：使用一次性密码/数据库验证官方命令

1. 仅使用 T1 本地已存在精确 Mosquitto ARM64 image ID；不 pull、不 tag、不接触生产 TLS、DynSec JSON、管理员密码或业务凭据。
2. 在新的隐蔽私有临时目录生成**一次性** Dynamic Security JSON，且容器使用 `--network none` 并仅在其隔离网络命名空间监听 `127.0.0.1:18883`，无 `-p`，不会在宿主监听端口 18883/8883。临时容器以 UID 1883 运行、无权限提升、只读 rootfs，只有测试临时目录一个 RW 挂载，容器 `/tmp` 使用 tmpfs。
3. 在隔离容器内通过 stdin 初始化 throwaway admin password，放入 tmpfs 中 0600 `mosquitto_ctrl` 配置；不得通过 argv、Docker 环境变量、日志或 GitHub 输出。仅运行一次官方 `setDefaultACLAccess publishClientReceive deny` 命令，随后 `getDefaultACLAccess` 观察，最后读取 throwaway JSON 的四个默认 ACL 字段验证目标值。
4. 进出环境固定：45 个既有 Docker volumes 集合不变、两条项目网络无容器、输入与输出安全规则仍在、无宿主 8883 监听、仅临时测试容器出现并退出；临时数据包含一次性 secret，仅经显式校验后删除本阶段新建的私有临时目录，异常时 STOP、保留目录取证，不触碰生产数据。
5. S17 通过仅证明实际 T1 镜像对 ACL 修改命令的支持，**不是**生产默认 ACL 已修复。之后另设 exact-state snapshot/production update gate，首先检查 S16 已记录的 JSON SHA 和 S14 密码文件完整性，优先只修单一 `publishClientReceive` 值，不创建 service users 或覆盖 admin。
6. 生产 ACL 默认修复闭环后才可开始三个服务身份 provisioning、manager、homeassistant 的创建与正反例矩阵，节点账号按真实首次配对逐节点生成，不设共享节点账号。最终 Broker 启动门仍需单独审查并验收 Docker Compose /2 gate 与入口防护。

```text
S16_READONLY_RESULT=PASS
S16_DEFAULT_ACL_BASELINE=REPAIR_REQUIRED
NEXT_ONE_GATE=N3W_T1_S17_THROWAWAY_DYNSEC_DEFAULT_RECEIVE_DENY_ISOLATED_PROOF
S17_ONLY_THROWAWAY_ADMIN=true
S17_PRODUCTION_SECRET_MOUNT=false
S17_PRODUCTION_DYNSEC_MUTATION=false
S17_HOST_BROKER_START=false
S17_HOST_8883_PUBLICATION=false
S17_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```

终端命令仅在用户对话中给出；GitHub 仅保存脱敏设计、源码与验收证据。
