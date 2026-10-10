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
