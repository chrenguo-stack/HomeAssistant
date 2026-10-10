# N3-W T1 S13 官方 Mosquitto 镜像下载失败取证（2026-10-10）

## 现场输出与可支持的判断

用户提供的 S13 Mac→T1 执行结果：

```text
S13_STAGE=OFFICIAL_IMAGE_BINDING
FREE_DISK_GIB=6.02
S13_PRECHECK=PASS
STOP_COMMAND_FAILED=docker pull --platform
RETURN_CODE=1
SSH_OR_REMOTE_EXIT_CODE=2
```

- S13 前置检查 PASS；`docker pull --platform linux/arm64 eclipse-mosquitto:2.1.2-alpine` 失败（Docker 命令退出码 1）。
- 整段 T1 SSH 脚本退出码 2 是执行包装器抛出的状态，不能替代原 Docker stderr。
- 原脚本捕获了 Docker stderr 但未输出，因此**尚不能得出具体失败根因**；不能说是产品缺陷，也不能把前置检查的 PASS 当作镜像部署 PASS。
- 脚本在镜像下载处提前 STOP。后续镜像 inspect、无网络临时测试容器、动态权限初始化、证书容器内可读性与 Broker 启动均未执行。
- S13 未进行正式容器创建、宿主 8883 发布、Broker 私钥读取或节点操作。Docker daemon 在下载前可能已经创建部分缓存层，不能把失败等价为零磁盘变化。
- 官方 Docker Library supported tags 已确认 `2.1.2-alpine` 及 linux/arm64v8 受支持；这是来源验证，不等于 T1 可以访问镜像仓库。

## 失败范围及下门

仅执行 T1 只读网络取证：Docker daemon active、Docker Hub 域名 DNS、registry HTTPS /v2/（401 为匿名仓库正常挑战响应）、auth token endpoint（绝不输出 token）、只读 manifest inspect 并输出有限删敏错误。必须保留 Docker stderr，确认失败类型后才决定是否原位重试一次最小镜像下载。

```text
S13_PRECHECK=PASS
S13_OFFICIAL_IMAGE_PULL=FAIL
S13_IMAGE_DIGEST_BINDING=PENDING
S13_ISOLATED_CONTAINER_TEST=NOT_EXECUTED
S13_PRODUCTION_BROKER_START=false
S13_RESULT=STOP
NEXT_ONE_GATE=S13_R1_DOCKER_REGISTRY_FAILURE_READONLY_FORENSIC
S13_R1_T1_MUTATION=false
S13_R1_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```

本文件只保存脱敏状态与决策，不向 GitHub 提交执行脚本、私有主机地址、Docker auth token、私钥或终端原始日志。
