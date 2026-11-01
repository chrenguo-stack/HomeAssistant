# T1 S13-R5 TLS 文件绑定验收与 S14 全新 DynSec 初始化（2026-10-10）

## S13-R5 实机证据

用户从 Mac Terminal 连接 T1 取得：

```text
S13_R5_PRECHECK=PASS
EXACT_IMAGE_BINDING=PASS
CERT_FINGERPRINTS=PASS
TLS_PROBE_EXIT_CODE=0
TLS_SINGLE_FILE_MOUNTS=PASS
TLS_UID1883_READ=PASS
ISOLATED_CONTAINER_REMOVED=True
DOCKER_VOLUMES_PRESERVED=True
CA_SIGNING_PRIVATE_KEY_MOUNTED=False
TLS_FILE_CONTENT_PRINTED=False
PRODUCTION_BROKER_STARTED=False
HOST_8883_PUBLICATION=False
BOARD_ACCESS=False
S13_R5_RESULT=PASS
SSH_OR_REMOTE_EXIT_CODE=0
```

镜像使用本地精确 ID `sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408`（linux/arm64，Mosquitto 2.1.2），证书指纹仍绑定：

- CA DER SHA256: `ce1fa7cbe9918f2a926fbfa91747c34d71543c519fe38795082b5b1f938b0322`
- Server DER SHA256: `87c2783264bb29dad9a457ba5c80d21809f041309fef0d9f85b551cfe2db5c88`

本证据证明三个单文件只读挂载以 UID/GID 1883 能被读取，不表示生产服务端 TLS/MQTT 已启动，也不证明正式 `/mosquitto/tls` 的路径布局。CA 签发私钥未进入容器。

## S14 准备：隔离生成全新 Dynamic Security 初始化状态

复用已验证的 Mosquitto 2.1.2 `mosquitto_ctrl dynsec init` 原始初始化合同；**禁止**复用旧历史 DynSec JSON、旧账号密码、匿名 1883 实验配置或旧 Home Assistant/Broker/MQTT 持久状态。

S14 有且只有一个新的状态所有权范围：

- 私有持久数据目录候选 `/var/lib/n3wfc4-broker`（必须确证不存在）；以 UID 1883 独占写入 `dynamic-security.json`，最终 0600；后续 Broker data mount `/mosquitto/data`。
- 管理员随机初始密码只储存在已创建的 root 专有 `/etc/n3wfc4/private/dynsec-admin-password`，0600，禁止输出到终端/GitHub、命令参数、容器环境变量或镜像层。使用 stdin 两次交给初始化工具。
- Docker 创建仅一次隔离短命容器，`--network none --pull never --read-only --user 1883:1883 --cap-drop ALL --security-opt no-new-privileges`，仅允许挂载空白、专用 DynSec staging 数据目录为 RW；**不可挂载** CA 签发私钥、TLS 服务器私钥、宿主 Docker socket、普通 Manager 状态或其它业务卷；不启动 Broker listener。
- 如果初始化失败或中断，root-only 密码文件或 staging 数据目录可能残留；标记 PARTIAL 并 STOP，不用相同命令重试覆盖，不进行通用清理。
- 初始化后检查 JSON 结构、管理员凭据条目、非明文口令、0600 权限和 Docker 45 个存量 volumes、空项目网络、入口防护和无端口监听。
- 已批准的官方 image tag 在 T1 不可直连；DaoCloud 代理镜像的本地 digest 已固定，但 **manifest/image-configuration 摘要的独立来源一致性仍需在正式启动前复核**。S14 容器 `network none` 限制凭据离线泄漏；此阶段不是生产供应链最终批准。
- 实际 Broker 启动前，必须具备独立 Manager/HA/Node ACL 和 account policy、Mosquitto 2.1.2 全局插件 `global_plugin`、匿名禁止、显式单一 `0.0.0.0:8883`、双 Docker bridge、host-mode Manager、`GH_N3W_PAIRING_ADVERTISED_HOST=auto`、已启用入口防护及 `tools/n3w_pairing_deployment_gate.py`/2 PASS。
- 终端脚本仅在对话中发布。GitHub 仅保留脱敏里程碑和设计证据，不记录私钥、账号凭据、完整 JSON 或包含私有地址的日志。

```text
S13_R5_RESULT=PASS
NEXT_ONE_GATE=N3W_T1_S14_FRESH_DYNSEC_ADMIN_INITIAL_STATE_MATERIALIZATION
S14_PERMITTED_NEW_SECRET=true
S14_NEW_DYNSEC_ADMIN_PASSWORD_ROOT_ONLY=true
S14_NEW_BUSINESS_ROOT_ONLY=true
S14_EPHEMERAL_INIT_CONTAINER=NETWORK_NONE
S14_MQTT_LISTENER_START=false
S14_BROKER_PUBLICATION=false
S14_MANAGER_HA_MUTATION=false
S14_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```
