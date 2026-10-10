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


## S13-R1 现场追加：DNS 正常但 HTTPS unreachable

用户于 S13-R1 提供真实 T1 只读取证：

```text
DNS_registry-1.docker.io=PASS
DNS_auth.docker.io=PASS
REGISTRY_V2=FAIL
REGISTRY_V2_ERROR=Network is unreachable (errno 101)
REGISTRY_AUTH=FAIL
REGISTRY_AUTH_ERROR=Network is unreachable (errno 101)
MANIFEST_READ=TIMEOUT
DOCKER_CONTAINER_COUNT_ZERO=True
S13_R1_READONLY_COMPLETE=true
IMAGE_PULL_EXECUTED=false
T1_MUTATION=false
BOARD_ACCESS=false
SSH_OR_REMOTE_EXIT_CODE=0
```

此证据支持：域名查询可用，但 T1 运行环境无法成功通过 HTTPS 访问 Docker Hub registry/auth；镜像清单请求超时。**不能仅凭 errno 101 区分无 IPv4 默认路由、IPv6 unreachable、代理误配或出站阻断**。S13 首个 pull 的真实 stderr 仍未捕获，不回填猜测作为原始错误。

下一门只做定向只读路由、IPv4/IPv6 分栈 TCP 到 registry/auth、已知公共 IPv4:443 TCP 与 Docker daemon/system proxy 是否启用的布尔检查；不吐出代理 URL/口令。诊断前不得修改 NetworkManager、默认路由、DNS、guard、防火墙、Docker daemon/proxy 或 SSH。

```text
S13_R1_DNS=PASS
S13_R1_REGISTRY_HTTPS=FAIL
S13_R1_MANIFEST=TIMEOUT
S13_R1_ROOT_CAUSE=UNRESOLVED
NEXT_ONE_GATE=S13_R2_IPV4_IPV6_ROUTE_AND_EGRESS_READONLY_FORENSIC
S13_R2_T1_MUTATION=false
S13_R2_IMAGE_PULL=false
S13_R2_BOARD_ACCESS=false
S13_BROKER_START=false
```


## S13 国内镜像代理入口实测（2026-10-10）

在用户 Mac→T1 只读 HTTPS 探测中，`m.daocloud.io` 和 `docker.m.daocloud.io` 均完成 IPv4 DNS 查询并返回 HTTP `401`，且 curl 退出码为 0。这支持镜像 Registry 的 TLS/HTTP 入口已从 T1 成功到达，HTTP 401 是 registry 认证挑战；**尚不等于目标 Mosquitto tag、manifest、blob 下载或完整镜像供应链身份已验证**。

DaoCloud 官方 `public-image-mirror` 使用文档说明推荐添加 `m.daocloud.io/docker.io/library/...` 前缀形式，可依据指定 tag 请求 Docker Hub 镜像代理，并注明白名单、限流、缓存时效及 SHA256 保持性。前述 T1 访问 Docker Hub 直连失败并未要求修改 NetworkManager/SSH/Docker daemon 或现存防火墙。

下一门 S13-R3：仅重新确认无容器、现存 45 个 volumes、`n3wfc4-private` 和 `n3wfc4-services` 无连接、入口防护 active、8883 未监听、磁盘空间达到下限；允许 **一个 bounded** 的 `m.daocloud.io/docker.io/library/eclipse-mosquitto:2.1.2-alpine` / linux/arm64 镜像 pull，然后仅 Docker image metadata inspect，记录 `Image ID`、`RepoDigests`、`Architecture` 和 `Os`。要保留失败 stderr 的有限且脱敏摘录。此门不启动任何容器、不挂载 TLS 私钥、不创建 DynSec 数据或账号，不重试其它不受控站点。

镜像来源绑定：通过镜像代理拉到的镜像保持为 `CANDIDATE`，只以镜像 tag 或自引用 mirror digest 不足以宣称独立上游供应链一致性；需在后续隔离测试及上游摘要比对后再晋升为生产 deployment authority。

```text
S13_DAOCLOUD_REGISTRY_ENTRY=PASS_HTTP_401
S13_TARGET_IMAGE_AVAILABILITY=NOT_YET_PROVEN
S13_R3_ALLOWED=ONE_MIRROR_IMAGE_PULL_PLUS_METADATA_INSPECT
S13_R3_CONTAINER_CREATE=false
S13_R3_PRODUCTION_BROKER_START=false
S13_R3_HOST_8883_PUBLICATION=false
S13_R3_TLS_PRIVATE_KEY_ACCESS=false
S13_R3_BOARD_ACCESS=false
NEXT_ONE_GATE=S13_R3_DAOCLOUD_MOSQUITTO_ARM64_IMAGE_PULL
```
