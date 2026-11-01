# N3-W T1 Mac 本地 exact artifact cache V1 源码设计
# 2026-10-15

## 0. Gate

```text
TASK=N3W_T1_MAC_LOCAL_EXACT_ARTIFACT_CACHE_V1_SOURCE_DESIGN_AND_REPAIR_20261015_01
BASE_PR=544
BASE_HEAD=35564490ed3f41e7c27efff3a0df3a1867e3832b
BASE_R4_RESULT=CLOSED_PASS
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
EXPLICIT_DEVICE_PROVISIONING_ENTERED=false
F4_ENTERED=false
```

本 Gate 只优化 Mac 侧 exact artifact 获取路径，不改变 T1 产品安装内容、镜像顺序、授权语义、
远端 staging、一次一镜像传输、5 GiB 容量保护、provisioning 或 F4 activation 语义。

## 1. 目标

冻结默认路径：

```text
check Mac local exact cache
        |
        +-- exact entry exists
        |     |
        |     +-- exact binding + outer ZIP SHA256 PASS
        |     +-- extract safely
        |     +-- existing inner SHA256 / manifest / image binding PASS
        |     |
        |     +--> use Mac cache -> T1
        |          GitHub large artifact download = false
        |
        +-- cache miss
              |
              +-- verify lightweight GitHub artifact metadata
              +-- download exact artifact ZIP
              +-- verify outer ZIP SHA256
              +-- verify safe outer file set
              +-- atomically publish cache entry
              +-- existing inner SHA256 / manifest / image binding PASS
              |
              +--> use newly verified Mac cache -> T1
```

## 2. Cache authority

Cache 只是 transport optimization，不是新的 release authority。

每次使用仍必须由调用方提供并绑定：

```text
repository
run_id
artifact_name
artifact_id
artifact_zip_sha256
runtime_payload_sha256
payload_manifest_sha256
```

cache entry 以 artifact ID + exact ZIP SHA256 隔离，不允许只按文件名命中。

缓存命中时不需要重新下载 GitHub 大文件；exact outer ZIP SHA256 必须重新计算。
解包后仍沿用现有严格校验：

- exact outer file set；
- runtime payload SHA256 + sidecar；
- payload manifest SHA256；
- capacity contract SHA256；
- host wrapper SHA256；
- host baseline SHA256；
- 三个 image tar 的 size + SHA256；
- payload manifest / transport / capacity cross-binding；
- running host wrapper == artifact host wrapper。

因此 local cache 不能绕过任何已有 binding。

## 3. 持久目录

V1 不再使用 `~/.cache`。这些 exact artifact 是后续重复部署可长期复用的生产输入，不应放在
可能被系统或清理工具当作临时缓存处理的目录。

默认使用用户可见、长期保留的目录：

```text
~/Documents/N3W/exact-artifacts/
  <artifact_id>/
    <artifact_zip_sha256>/
      artifact.zip
      binding.json
```

操作者也可以通过 `--artifact-cache-root <path>` 人工指定其他固定目录，例如外置磁盘、
专用项目目录或 `~/Downloads/N3W-exact-artifacts`。显式参数优先于默认目录。

选择 `~/Documents/N3W/exact-artifacts` 而不是 Downloads 作为默认值，是因为 Downloads
仍常被人工或清理工具定期整理；Documents 更符合“长期 artifact store”的产品语义。

`binding.json` 只允许公开安全字段：

```text
schema
repository
run_id
artifact_name
artifact_id
artifact_zip_sha256
```

不得写入 T1 locator、密码、token、credential、TLS private key 或任何实例秘密。

## 4. Fail-closed 规则

存在 cache entry 时，以下任一情况均禁止使用，也禁止静默把损坏 cache 当成 miss：

- entry/root 是 symlink 或类型异常；
- entry file-set 不精确；
- binding.json 无法解析；
- repository/run/name/id/ZIP SHA 任一不匹配；
- cached artifact.zip SHA256 不匹配；
- ZIP outer file-set 不匹配或 member 不安全；
- 任一后续 inner SHA256/cross-binding 失败。

V1 对“存在但损坏/不匹配”的 cache 采取 fail-closed STOP，不自动删除、不自动覆盖，
避免把本地 corruption 隐藏成一次新的网络下载。

## 5. Cache miss 下载与发布

cache miss 时：

1. 只先读取 GitHub artifact metadata，确认 artifact ID/name/run/digest/expired 绑定；
2. 通过现有 GitHub REST artifact redirect 获取 exact ZIP；
3. 在 cache 同一 artifact-ID 目录下创建私有临时目录；
4. 下载完成后验证 outer ZIP SHA256；
5. 验证 safe outer file-set；
6. 写 exact `binding.json`；
7. 临时目录原子 rename 为最终 exact entry；
8. 后续只从最终 cache entry 解包到本次临时 workdir。

失败时删除 transaction-owned 临时 cache 目录，不破坏已存在 exact cache。

## 6. GitHub 网络边界

```text
CACHE_HIT_VERIFIED:
GitHub large artifact download=false
GitHub artifact metadata lookup=false

CACHE_MISS:
GitHub artifact metadata lookup=true
GitHub large artifact download=true
cache populated only after exact verification
```

本 Gate 不要求完全离线运行；它只保证 exact cache hit 不再重复下载 GitHub 大 artifact。

## 7. 与 T1 / authorization 的关系

cache 检查、SHA256 验证和 cache miss 下载全部发生在：

```text
remote payload transfer BEFORE
authorization claim BEFORE
Docker mutation BEFORE
production service start BEFORE
```

因此 local cache 故障必须保持：

```text
authorization_claimed=false
authorization_consumed=false
T1 product mutation=false
```

本 Gate 不执行真实 T1 apply。

## 8. Source scope

预计只修改：

```text
tools/n3w_t1_fresh_product_staging_host.py
tests/tools/test_n3w_t1_fresh_product_staging_host.py
docs/development/*
```

现有 workflow 已覆盖 host-wrapper source/test 路径；先不扩大 workflow scope，CI 结果再判断是否需要补充。

## 9. Required regression tests

至少覆盖：

1. valid exact cache hit -> 不调用 GitHub metadata、不调用大文件下载；
2. cache hit outer ZIP SHA mismatch -> fail closed；
3. cache hit binding mismatch -> fail closed；
4. cache miss -> metadata PASS -> download -> SHA PASS -> atomic cache publish；
5. cache miss 首次成功后第二次运行 -> cache hit；
6. 默认路径固定为 `~/Documents/N3W/exact-artifacts`，CLI 暴露 `--artifact-cache-root` 人工覆盖；
7. existing inner artifact/image verification remains after cache acquisition；
8. authorization claim ordering仍在完整 local exact verification之后。

## 10. Stop boundary

```text
SOURCE_DESIGN=true
SOURCE_REPAIR=AUTHORIZED
CI_ALLOWED=true
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
EXPLICIT_DEVICE_PROVISIONING=false
F4=false
BOARD_ACCESS=false
MERGE=false
AUTO_EXECUTE_NEXT_GATE=false
```
