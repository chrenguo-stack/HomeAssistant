# N3-W T1 minimal-host fresh bootstrap R4 source repair progress（2026-10-11）

R4 解决的是“安装包怎么安全送到 T1”，不碰真实 T1。

本轮新增新的 fresh host wrapper。它在传输大文件之前先做三件事：

1. 下载并核对 GitHub exact artifact；
2. 直接从压缩包读取 transport metadata，不先解压；
3. 只读查询 T1 的 /var/tmp 和 Docker 存储空间，算出最坏情况下需要多少空间。

容量判断不再只看“当前还有没有 5 GiB”。现在会同时考虑：

- 压缩包 + 解压后的 payload；
- 三个 Docker 镜像逐个 load 时增加的磁盘占用；
- 每个镜像 load 成功后立即删除对应 tar；
- 最坏峰值以后仍必须至少剩 5 GiB。

新的 read-only preflight 不创建 T1 临时目录、不传 payload、不执行 docker load。

同时保留了后续 apply 会使用的顺序加载函数，固定顺序为：

```text
Home Assistant
→ Manager
→ Broker
```

每个 tar 都是：

```text
docker load 成功
→ 立刻删除该 tar
→ 再处理下一个
```

不允许 docker pull。

artifact manifest 现在额外记录每个镜像：

- tar 大小；
- Docker load 后镜像大小；
- 镜像名；
- 固定加载顺序。

上传后重新下载的 exact binding 检查会再次验证这些 metadata，并重新计算容量峰值。

当前 wrapper CLI 只开放 read-only `preflight`，还没有开放 live apply，因此本 R4 不可能误触真实部署。

```text
R4_SOURCE_COMMITTED=true\nR4_STATUS=CLOSED_PASS\nR4_EXACT_ARTIFACT_RUN=38156268697\nR4_EXACT_ARTIFACT_ID=11709005237\nR4_EXACT_ARTIFACT_BINDING=PASS
R4_CI=PASS
T1_ACCESS=false
LIVE_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false

NEXT_ONE_GATE=
N3W_T1_MINIMAL_HOST_BASELINE_BOOTSTRAP_SOURCE_REPAIR_R5_20261011_01

R5_SCOPE=HOST_ONLY_ISOLATED_FULL_FRESH_CI
```
