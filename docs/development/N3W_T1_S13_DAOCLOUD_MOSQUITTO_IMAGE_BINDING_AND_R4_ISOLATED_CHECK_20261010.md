# N3-W T1 S13-R3 DaoCloud 镜像下载完成与 S13-R4 隔离能力验证（2026-10-10）

## S13-R3 用户实测证据

用户于 T1 执行了已授权的一次 DaoCloud 镜像下载，并提供以下截取完整的预检、下载和停止结果：

```text
FREE_DISK_GIB_BEFORE=6.02
S13_R3_PRECHECK=PASS
DAOCLOUD_PULL_EXIT_CODE=0
DAOCLOUD_PULL=PASS
IMAGE_REFERENCE=m.daocloud.io/docker.io/library/eclipse-mosquitto:2.1.2-alpine
IMAGE_ID=sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408
IMAGE_ARCHITECTURE=arm64
IMAGE_OS=linux
IMAGE_REPO_DIGESTS=["m.daocloud.io/docker.io/library/eclipse-mosquitto@sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408"]
UPSTREAM_DIGEST_INDEPENDENTLY_VERIFIED=false
FREE_DISK_GIB_AFTER=5.98
S13_R3_RESULT=PASS
CONTAINER_CREATED=false
BROKER_STARTED=false
TLS_PRIVATE_KEY_ACCESSED=false
BOARD_ACCESS=false
STOP=true
SSH_OR_REMOTE_EXIT_CODE=0
```

**证据范围：**成功从已连通的 DaoCloud 代理下载一个 linux/arm64 镜像，并核对本地 image metadata；未启动容器、未访问 TLS 私钥和 MQTT 凭据。镜像 ID 是 Docker 本地镜像 configuration digest，DaoCloud 返回的同样字符串不构成独立的 Docker Hub multiarch manifest / platform-specific digest 确认。镜像尚不能晋升为 `UPSTREAM_VERIFIED` 生产供应链 authority。

与 S13-R1 Docker Hub 无法联网的缺陷分类应当分开：这次镜像下载已经绕过直连障碍，未修改 NetworkManager、SSH、防火墙、Docker daemon 或既存服务。

## S13-R4 有界隔离测试准入

下一步测试在 T1 本机以已下载的**精确 image ID** 创建一次短命容器，固定 `--pull never`、`--network none`、`--read-only`、`--cap-drop ALL`、`--security-opt no-new-privileges`、`--user 1883:1883`、不提供宿主挂载或生产私钥、无 `-p`。只执行 shell 基础读取、`mosquitto -h` 非监听版本自述、Mosquitto Ctrl 命令存在性、动态权限插件路径 `/usr/lib/mosquitto_dynamic_security.so` 的可读性、实际 uid/gid 校验。

前后都要断言：精确镜像 ID、无其它 Docker 容器、45 个已保护 volume 名称集合未改变、两个项目网络仍无容器、守护规则仍在和 TCP 8883 未监听。若临时容器未自动清理，STOP，不能尝试执行 Broker / DynSec 后续步骤。异常失败与镜像能力缺失分别分类，避免未捕获 stderr 重复拖慢。

```text
S13_R3=PASS
S13_R4_NEXT_ONE_GATE=MOSQUITTO_IMAGE_EXACT_ID_ISOLATED_NO_NETWORK_NO_SECRET_PROBE
S13_R4_EPHEMERAL_CONTAINER_ONLY=true
S13_R4_TLS_MOUNT=false
S13_R4_DYNSEC_INITIALIZATION=false
S13_R4_PRODUCTION_BROKER_START=false
S13_R4_HOST_8883_PUBLICATION=false
S13_R4_NETWORK_MUTATION=false
S13_R4_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```

S13-R4 PASS 后须独立验证 TLS 单文件只读 bind/uid1883 实际可读性，再创建全新 DynSec 及 production Compose。真实 Broker 启动前还需通过 existing `n3w_pairing_deployment_gate.py` /2 和入口防护验收。终端命令仅在对话发布，仓库不得包含生产私钥、Docker token 和私人网络地址。


## S13-R4 用户实机结果：PASS

```text
S13_R4_PRECHECK=PASS
EXACT_IMAGE_ID_MATCH=True
ISOLATED_TEST_EXIT_CODE=0
PROBE_MOSQUITTO_VERSION=2.1.2
PROBE_UID_GID=1883:1883
PROBE_DYNSEC_PLUGIN_READABLE=true
PROBE_MOSQUITTO_CTRL_PRESENT=true
ISOLATED_CONTAINER_REMOVED=True
DOCKER_VOLUMES_PRESERVED=True
INGRESS_GUARD_PRESERVED=True
HOST_8883_LISTENER=0
PRODUCTION_TLS_PRIVATE_KEY_MOUNTED=False
PRODUCTION_BROKER_STARTED=False
S13_R4_RESULT=PASS
BOARD_ACCESS=False
STOP=True
SSH_OR_REMOTE_EXIT_CODE=0
```

本轮真正验证了 Mosquitto 版本 2.1.2、普通 UID/GID 1883、动态安全插件和 mosquitto_ctrl，并证明无网络临时容器已删除。未读取或挂载生产私钥，不将此测试误表述为 Broker 运行时 TLS 校验。

Docker Hub 官方 image layer 公布的 `eclipse-mosquitto:2.1.2-alpine` **多平台索引摘要**为 `sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408`，与本次由 DaoCloud 返回的 `RepoDigests` 中 sha256 值一致。这里比较的是 **registry 索引摘要**，不是对本地 Docker image configuration `Id` 的独立证明：同一字串碰巧还出现在现场 `IMAGE_ID` 字段，需在下一门实际检查 `docker image inspect`、镜像来源和单文件只读挂载，且不能混用二者的语义。官方 Docker Library `official-images/library/eclipse-mosquitto` 列明对应 tag、GitCommit 和 arm64v8 平台。

## S13-R5 下一门：单文件 TLS 绑定安全验证

1. 仅使用本次已下载的精确 image ID（不得联网 pull）；复验 tag、RepoDigest、image ID 和 linux/arm64。
2. 保留原有 45 volumes、两条空网络、原 ingress guard 和无 8883 监听；仅一次 `--rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --user 1883:1883` 的临时容器。
3. 以 **三个单文件 readonly bind** 映射宿主 `ca.pem`、`server.pem`、`server.key` 至容器**已有目录**的不同文件名，绝不把私有 CA signing key、整个 `/etc/n3wfc4` 目录或宿主 socket 挂载。
4. 容器只执行 `test -r` 等访问判定，不展示、复制、签名、打印密钥，不启动 Mosquitto Broker。
5. CA 私钥仍仅存在 T1 root 的私有目录；server.key 对候选镜像的读取必须以来源摘要复核、隔离条件和正确 UID/GID 三重条件为前提。若要在将来的生产配置使用 `/mosquitto/tls`，需独立确保容器实际路径安全存在，不能用已存在的 `/mosquitto/config` 检测结果冒充此路径通过。
6. 真正的证书服务端验证和 DynSec 隔离初始化仍另设后续门；不上线 Broker、不发布端口。

```text
S13_R4_RESULT=PASS
UPSTREAM_PUBLIC_INDEX_DIGEST_MATCHES_MIRROR=PASS
LOCAL_IMAGE_CONFIGURATION_ID_IS_NOT_MANIFEST_DIGEST=true
NEXT_ONE_GATE=S13_R5_EXACT_IMAGE_READONLY_CERT_FILE_BIND_PROBE
S13_R5_CONTAINER_NETWORK=NONE
S13_R5_CA_PRIVATE_KEY_MOUNT=false
S13_R5_BROKER_STARTED=false
S13_R5_TLS_HOST_PORT_PUBLICATION=false
S13_R5_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```
