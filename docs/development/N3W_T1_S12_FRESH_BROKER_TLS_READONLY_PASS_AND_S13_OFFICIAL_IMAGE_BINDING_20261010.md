# N3-W T1：S12 Broker 证书只读校验与 S13 官方镜像绑定（2026-10-10）

## S12 现场事实

本记录依据用户在 T1 终端返回的 S12 日志摘要，全部只读：

```text
S12_TLS_IDENTITY=PASS
TLS_DIRECTORY_ROOT_MODE=0700
TLS_DIRECTORY_TLS_MODE=0700
TLS_DIRECTORY_PRIVATE_MODE=0700
CA_PEM_SHA256_DER=ce1fa7cbe9918f2a926fbfa91747c34d71543c519fe38795082b5b1f938b0322
SERVER_PEM_SHA256_DER=87c2783264bb29dad9a457ba5c80d21809f041309fef0d9f85b551cfe2db5c88
CA_KEY_OWNER=root:root_MODE=0600
SERVER_KEY_OWNER=1883:1883_MODE=0600
NETWORKS=n3wfc4-private,n3wfc4-services
HOST_8883_LISTENER=0
MOSQUITTO_IMAGE_COUNT=1
S12_READONLY_RESULT=PASS
PRODUCTION_BROKER_START=false
T1_MUTATION=false
BOARD_ACCESS=false
SSH_OR_REMOTE_EXIT_CODE=0
```

唯一检测到的本地候选镜像是 `local/mosquitto:pr260-source-exact`（linux/arm64，历史 PR260 镜像，镜像 ID `sha256:a908c65cc8e67ec9d292ef27c2c0360dbaaee7eb1b935cdd194e67697f15dea1`）。本地标签及自引用 RepoDigest 不构成现代生产供应链审核依据；**不得仅凭缓存复用或把新 Broker 私钥挂载到该旧镜像中**。

在 T1 宿主机，证书位于非公开的 `/etc/n3wfc4` 树内，其子目录 `tls` 0700。host-owned cert/key 权限校验不等于运行 UID 1883 的容器可以顺利 traverse 已 bind-mounted 的目录。应通过单文件只读 bind 以及确切容器目录权限进行后续隔离实验；在正式 Broker Compose 内不能挂载 CA 私钥。

## S13 镜像选择

- 根据 Docker 官方库公开 supported tags（2026-10-10 查证），`eclipse-mosquitto:2.1.2-alpine` 由 Eclipse Mosquitto 维护，提供 linux/arm64 v8；历史 T1 实测曾使用 Mosquitto 2.1.2。
- S13 阶段只准在网络和 guard preflight 后下载官方 version-specific tag；必须记录 remote RepoDigest、local immutable Image ID、OS/architecture、metadata，再进入独立 no-network/no-secrets 测试容器验证 CLI 和 `/usr/lib/mosquitto_dynamic_security.so` 插件文件及普通 UID1883 运行能力。
- S13 阶段不得启动 Mosquitto listener、不得配置 port publication、不得挂载证书/任何私钥、不得创建 DynSec 状态或账号；隔离测试容器必须 `--rm`、无网络、只读 rootfs、CAP drop all、no-new-privileges、user 1883。目标 Docker 容器结果仍为 0。
- 当前 T1 系统可用磁盘空间约 6.02 GiB；镜像大小需在实际 pull 前再次核实保留合理空间，不允许 prune 现有 45 个未归属卷或删除其它镜像。
- 2.1 配置必须使用 `global_plugin /usr/lib/mosquitto_dynamic_security.so`，不恢复过时 `per_listener_settings false`，且 `allow_anonymous false`。S13 验证文件存在不等于 DynSec 已安全初始化。
- 生产 Compose 仍须通过官方现存 v2 `n3w_pairing_deployment_gate.py` 与真实 guard、双网络、single explicit 0.0.0.0:8883/host-network Manager 合同。
- auto 恢复采用 PR #522 已实现的生产源码；目前 Gate F clean-board full acceptance 仍 open。T1 新系统身份/CA 凭据将重新初始化并首次配对。

```text
S12_CLOSED=PASS
NEXT_ONE_GATE=N3W_T1_S13_OFFICIAL_MOSQUITTO_IMAGE_PULL_AND_ISOLATED_NO_SECRET_CHECK
S13_IMAGE_DOWNLOAD=ALLOWED_AFTER_FRESH_PRECHECK
S13_EPHEMERAL_CONTAINER=NO_NETWORK_NO_PRIVILEGES_NO_SECRETS
S13_BROKER_LISTENER=false
S13_HOST_8883_PUBLICATION=false
S13_T1_TLS_MUTATION=false
S13_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```

本文件不包含给用户的执行脚本或运行明文。终端指令仅通过会话发送；GitHub 保存脱敏设计、源码和证据。
