# N3-W T1 Mac 本地 exact artifact cache V1 源码修补闭环
# 2026-10-15

## 0. 结论

```text
TASK=N3W_T1_MAC_LOCAL_EXACT_ARTIFACT_CACHE_V1_SOURCE_DESIGN_AND_REPAIR_20261015_01
RESULT=CLOSED_SOURCE_PASS

BASE_PR=544
BASE_HEAD=35564490ed3f41e7c27efff3a0df3a1867e3832b
PR=545
PR_STATE=OPEN_DRAFT_UNMERGED
SOURCE_HEAD=d1a7847c1e0612ac80b31b85262011110f329794

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
EXPLICIT_DEVICE_PROVISIONING=false
F4=false
BOARD_ACCESS=false
MERGE=false
```

本 Gate 已把 R4 后延期的 `LOCAL_ARTIFACT_CACHE_OPTIMIZATION` 实现为 Mac 侧持久 exact artifact store。
它只改变 Mac 获取 exact GitHub artifact 的方式，不改变 T1 public product、远端 staging、一次一镜像传输、
authorization claim、provisioning 或 F4 语义。

## 1. 冻结后的路径

默认持久目录：

```text
~/Documents/N3W/exact-artifacts/
  <artifact_id>/
    <artifact_zip_sha256>/
      artifact.zip
      binding.json
```

操作者可通过：

```text
--artifact-cache-root <path>
```

指定其他固定目录，例如外置磁盘或专用项目目录。显式路径优先于默认目录。

V1 明确不再使用 `~/.cache`。

## 2. Cache hit contract

exact entry 必须同时满足：

- entry 目录安全且不是 symlink；
- file-set 恰好为 `artifact.zip` + `binding.json`；
- binding 精确匹配 repository / run ID / artifact name / artifact ID / artifact ZIP SHA256；
- 每次命中都重新计算 cached ZIP SHA256；
- ZIP member/file-set 安全检查继续执行；
- 解包后继续执行现有 runtime payload、manifest、capacity、host wrapper、host baseline、三镜像 tar
  size/SHA256 与 cross-binding 校验。

全部 PASS 后才使用本地副本。

```text
CACHE_HIT_VERIFIED
→ GitHub artifact metadata lookup=false
→ GitHub large artifact download=false
→ Mac verified artifact -> existing T1 transport path
```

cache 只是 transport optimization，不成为新的 release authority。

## 3. Cache miss contract

miss 时：

1. GitHub artifact metadata 绑定检查；
2. GitHub REST artifact redirect 下载 exact ZIP；
3. 在同一 artifact-ID 目录创建 transaction-owned 临时目录；
4. 验证 outer ZIP SHA256；
5. 验证 exact/safe outer file-set；
6. 写 public-safe `binding.json`；
7. 同 filesystem 原子 rename 到最终 exact entry；
8. 使用已验证内容继续现有 inner binding。

失败时仅删除本次临时 cache 目录；不得覆盖已有 exact entry。

如果 exact entry 已存在但损坏或 binding 不匹配，V1 fail closed；不把 corruption 静默当成 miss，也不自动覆盖后重新下载。

## 4. Source delta

相对 PR #544 R4 closure base，源码相关 delta：

```text
tools/n3w_t1_fresh_product_staging_host.py
tests/tools/test_n3w_t1_fresh_product_staging_host.py
tools/execution_packages/n3w/f2/t1_fresh_readonly_preflight/executor.py
docs/development/N3W_T1_MAC_LOCAL_EXACT_ARTIFACT_CACHE_V1_SOURCE_DESIGN_20261015.md
```

F2 executor 的 exact host-wrapper blob authority 已随 wrapper 修改同步更新。

## 5. Regression coverage

新增/冻结：

- valid exact cache hit 不调用 GitHub metadata、不下载大 artifact；
- cached ZIP SHA mismatch fail closed；
- cache binding mismatch fail closed；
- miss -> exact download -> SHA PASS -> atomic publish；
- 第一次 miss 成功后第二次 exact use 命中本地；
- 默认持久路径固定为 `~/Documents/N3W/exact-artifacts`；
- `--artifact-cache-root` 允许人工覆盖；
- existing inner verification 保持；
- cache acquisition 位于 T1 payload transfer / authorization claim 之前。

## 6. Exact-head CI closure

```text
SOURCE_HEAD=d1a7847c1e0612ac80b31b85262011110f329794
CI_TOTAL=14
CI_SUCCESS=14
CI_FAILURE=0
CI_PENDING=0
```

高相关检查：

```text
N3W_T1_F2_READONLY_PREFLIGHT_SOURCE_CI=SUCCESS
RUN_ID=38694709149
FOCUSED_TESTS=64_PASSED

N3W_T1_FRESH_BOOTSTRAP_DEPLOYABLE_PAYLOAD_CI=SUCCESS
RUN_ID=38694709028
ARTIFACT_ID=11953163662
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-d1a7847c1e0612ac80b31b85262011110f329794
ARTIFACT_DIGEST=sha256:6f0ec341494bc6ba2a9b9d03a2c3968b708241dd069408a3dc72f63f3e79a89c
FRESH_BOOTSTRAP_INNER_BINDING=PASS
FRESH_TRANSPORT_V2_POST_UPLOAD_BINDING=PASS
FRESH_BOOTSTRAP_DEPLOYABLE_POST_UPLOAD_BINDING=PASS

N3W_T1_PRODUCTION_STACK_STAGING_PAYLOAD_CI=SUCCESS
RUN_ID=38694709222
ARTIFACT_ID=11953318563
ARTIFACT_DIGEST=sha256:cc1f64f95c1d5c9da3b3ac93879342f76427114bcda061c3eaa2d27a83aa51d5
RUN_EXACT_ARTIFACT_BINDING=PASS
PAYLOAD_SIDECAR_BINDING=PASS
OFFLINE_RUNTIME_CONTRACT_EXACT=PASS
```

其余 11 个 PR checks 同样全部 SUCCESS，包括 public repository safety。

早一轮 CI 因新增默认路径断言测试中遗漏 `tool = load_tool()` 而失败；
该问题只在 test code，已在 same Gate 修复。最终 exact source head 上无 CI failure。

## 7. Artifact / authorization 边界

CI 生成的 fresh deployable artifact 仍包含 workflow 的 R4 authorization identity。
R4 live authorization 已在前序 Gate consumed/no-replay。

因此：

```text
NEW_CI_ARTIFACT_IS_SOURCE_AND_BINDING_EVIDENCE=true
NEW_CI_ARTIFACT_IS_NEW_R4_LIVE_AUTHORIZATION=false
R4_REPLAY_PERMITTED=false
```

不得因为本 Gate 生成了新 artifact 就重放 R4。

## 8. 当前边界

```text
MAC_EXACT_ARTIFACT_CACHE_V1_SOURCE=CLOSED_PASS
DEFAULT_DURABLE_STORE=~/Documents/N3W/exact-artifacts
CUSTOM_STORE_SUPPORTED=true

REAL_MAC_CACHE_POPULATION=NOT_EXECUTED
REAL_MAC_CACHE_HIT_ACCEPTANCE=NOT_EXECUTED

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
EXPLICIT_DEVICE_PROVISIONING=false
F4=false
BOARD_ACCESS=false
PR545_MERGE=false
```

源码层已经闭环，但尚未在操作者 Mac 上创建真实持久 store，也尚未用真实 2.5 GiB exact artifact
证明“第一次写入 / 第二次 cache hit / 第二次不下载 GitHub 大文件”。

## 9. Next ONE Gate

```text
NEXT_ONE_GATE=N3W_T1_MAC_LOCAL_EXACT_ARTIFACT_CACHE_V1_MAC_ACCEPTANCE_20261015_01
AUTO_EXECUTE_NEXT_GATE=false
```

下一 Gate 只在 Mac 本地做 exact artifact 持久化与 cache-hit 验收；默认不访问 T1，不进入 provisioning/F4，
不重放 R4，不触碰 board。

完成 Mac acceptance 后再回到 explicit per-device provisioning 的独立授权决策。
