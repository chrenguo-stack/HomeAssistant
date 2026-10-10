# N3-W T1：S14 全新动态权限初始化 PASS 与 S15 Broker 生产配置候选（2026-10-10）

## S14 现场证据

用户于 T1 完成一次隔离、无网络的 `mosquitto_ctrl dynsec init` 初始化：

```text
S14_PRECHECK=PASS
DYNSEC_INIT_EXIT_CODE=0
DYNSEC_STATE_CREATED=True
DYNSEC_INITIAL_ADMIN_COUNT=1
DYNSEC_STATE_MODE=0600_UID1883
DYNSEC_ADMIN_PASSWORD_MODE=0600_ROOT
DYNSEC_PASSWORD_PRINTED=False
DYNSEC_ADMIN_PASSWORD_IN_CONTAINER_ENV=False
DYNSEC_JSON_PLAINTEXT_PASSWORD=False
ISOLATED_CONTAINER_REMOVED=True
DOCKER_VOLUMES_PRESERVED=True
INGRESS_GUARD_PRESERVED=True
BROKER_STARTED=False
HOST_8883_PUBLICATION=False
BOARD_ACCESS=False
S14_RESULT=PASS
SSH_OR_REMOTE_EXIT_CODE=0
```

现场新建 `/var/lib/n3wfc4-broker/dynamic-security.json` 与 `/etc/n3wfc4/private/dynsec-admin-password`；不复用旧 CA/身份/数据。用户本机原始日志私有留存，仓库仅归档脱敏结果。管理员初始密码不会通过容器环境变量、命令参数或 GitHub 传递。

## S15 源码冻结

新配置源码：
`infra/n3w-t1/broker/mosquitto.conf`

静态回归测试：
`tests/tools/test_n3w_t1_fresh_mosquitto_config_contract.py`

冻结配置精确 SHA256：

```text
SOURCE_MOSQUITTO_CONFIG_SHA256=3708c6cea415ae6c0a4f35d71a116fff8571921b5a3774dbb55d0a9cb42845a6
LOCAL_BASIC_STATIC_CHECK=PASS
GITHUB_CI=NOT_CLAIMED
T1_REAL_MOSQUITTO_CONFIG_TEST=NOT_YET_EXECUTED
```

该候选只允许 `listener 8883 0.0.0.0`、`allow_anonymous false`、单一 `global_plugin /usr/lib/mosquitto_dynamic_security.so`、数据文件 `/mosquitto/data/dynamic-security.json`、持久状态目录 `/mosquitto/data/`。证书使用经 S13-R5 实测可用的单文件只读挂载目标：

```text
/mosquitto/config/n3w-ca.pem
/mosquitto/config/n3w-server.pem
/mosquitto/config/n3w-server.key
```

不以历史旧的 `plugin` / `per_listener_settings false` 方式复用配置，不启动 1883 非加密端口，不挂载 CA signing private key，不包含账号密码。

## S15 T1 staging + `--test-config` 边界

1. 前置核对原 45 个 Docker 卷名称集合不变、两条项目网络无容器、入口防护有效、无 TCP/8883 监听；精确镜像 ID、既有 CA/Server 证书指纹与 S14 的单一管理员/权限状态完整性不漂移。
2. 仅在不存在 `/etc/n3wfc4/mosquitto.conf` 的前提下，准备候选配置到同目录私有临时文件并核对上述精确 SHA256；使用已经下载镜像 `sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408`，`--pull never --network none --read-only --user 1883:1883 --cap-drop ALL --security-opt no-new-privileges`，仅运行 `mosquitto --test-config` 静态配置校验，不启动常驻 MQTT listener。
3. 运行单文件 readonly cert/key bind；Dynamic Security 状态以整个新业务数据目录 readonly bind，不挂载 root-only admin password；不修改 DynSec 状态、凭据、Manager/HA、Docker 网络/守护规则。
4. 只有 `--test-config` 返回码 0、精确 SHA256 未变化、宿主状态未漂移时，才将候选配置原子 rename 到 `/etc/n3wfc4/mosquitto.conf`，文件 0644 root-owned；保留当前上级私有目录权限。
5. 若失败，候选临时配置可能仍在 /etc/n3wfc4 并应 STOP 取证，不得循环重试。任何终端执行命令都仅在聊天对话下发，不以 GitHub 文档充当命令执行包。
6. S15 PASS **不是** Broker 启动授权。Broker 生产运行还需要单独的 Manager/HA/Provisioning/Node 权限矩阵、身份和凭据初始化、真实 TLS/DynSec 端到端验收、Source/Compose v2 gate 及 ingress guard live gate，保持 `GH_N3W_PAIRING_ADVERTISED_HOST=auto` + PR #522 Broker 地址 RAM-only 安全回退。

```text
S14_RESULT=PASS
NEXT_ONE_GATE=N3W_T1_S15_FRESH_MOSQUITTO_CONFIG_STAGE_AND_TEST_ONLY
S15_T1_CONFIG_WRITE=SCOPED_NEW_FILE_ONLY
S15_ALLOW_EPHEMERAL_NETWORK_NONE_CONTAINER=true
S15_DYNSEC_MUTATION=false
S15_BROKER_SERVICE_START=false
S15_PORT_8883_PUBLICATION=false
S15_MANAGER_HA_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```
