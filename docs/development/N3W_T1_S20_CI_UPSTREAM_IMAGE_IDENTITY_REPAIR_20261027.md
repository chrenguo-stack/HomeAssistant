# N3W T1 S20 CI 镜像身份验证修复（2026-10-27）

```text
TASK=N3W_T1_S20_CI_UPSTREAM_IMAGE_IDENTITY_REPAIR_20261027_01
BASE_MAIN=be4b422d7fafd9fe47f4cf1b65bafc04454e76b5
R2B_PR=683
R2B_SOURCE_MUTATION=false
PRODUCTION_IMAGE_LOCK_MUTATION=false
T1_ACCESS=false
BOARD_ACCESS=false
LIVE_RUNTIME_MUTATION=false
MERGE=false
```

## 1. 问题

PR #683 的 `N3W T1 S20 real service handoff CI` 中：

- source job PASS；
- volume-lifecycle 与 tls-readiness 在真正的 S20 runtime 断言之前失败；
- workflow 从 DaoCloud 镜像地址按 tag 拉取；
- 随后要求该镜像地址的 `RepoDigests` 必须包含 Docker Hub 历史 index digest
  `sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408`；
- 当前 DaoCloud 拉取结果报告
  `sha256:860aeb5d63ce509508f6dcfb2bc8a1c1dd2bc60555b562b45ce90e52d8dabb0f`，
  因此在 runtime 测试之前退出。

旧检查隐含了一个不成立的长期假设：

> 镜像代理/镜像站在自己的 registry 命名空间下返回的 RepoDigest，必须永远与上游 Docker Hub index digest 相同。

registry 地址是镜像身份的一部分。镜像站自己的 RepoDigest 不能被当成 Docker Hub 上游 index digest 的稳定别名。

## 2. 修复原则

S20 real-service CI 是 GitHub runner 上的行为验证，不是生产 ARM64 镜像生成 authority。

因此修复为：

```text
docker.io/library/eclipse-mosquitto:2.1.2-alpine@
sha256:38c0da4f2ef84284d47b3b3eeea1cb3bdeabe81ee10caf0cd5c5ff61ee3ea408
```

CI 直接使用上游 content-addressed immutable reference。

不再：

- 先按 DaoCloud tag 拉取；
- 再把 DaoCloud `RepoDigests` 与 Docker Hub index digest 比较。

这不是接受新的镜像内容，而是消除 registry-local digest 与 upstream digest 的语义混用。

## 3. 生产 authority 不变

本修复不修改：

`infra/n3w-t1/production/image-lock.json`

生产 Broker 仍由现有 ARM64 锁定记录约束：

```text
source_ref=m.daocloud.io/docker.io/library/eclipse-mosquitto:2.1.2-alpine
platform=linux/arm64
manifest_digest=sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549
image_id=sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b
```

CI fixture identity与生产 ARM64 artifact authority继续分离。

## 4. CI policy 对齐

本次还为 `n3w-t1-s20-real-service-handoff-ci.yml` 增加 PR-scoped：

- `concurrency`
- `cancel-in-progress`

因此删除 manifest 中原来的：

`missing_pr_cancel`

技术债例外。

## 5. 回归保护

新增：

`tests/tools/test_n3w_t1_s20_real_service_handoff_ci_contract.py`

固定验证：

1. S20 CI 使用上游不可变 digest；
2. S20 CI 不再引用生产 DaoCloud tag；
3. S20 CI 不再使用 `RepoDigests` 做错误的跨 registry 等值比较；
4. production image-lock 仍保持 DaoCloud + ARM64 manifest 锁；
5. 已修复的 policy exception 必须删除。

```text
R2B_SOURCE_CHANGED=false
PRODUCTION_IMAGE_AUTHORITY_CHANGED=false
CI_IDENTITY_SEMANTICS_REPAIRED=true
```
