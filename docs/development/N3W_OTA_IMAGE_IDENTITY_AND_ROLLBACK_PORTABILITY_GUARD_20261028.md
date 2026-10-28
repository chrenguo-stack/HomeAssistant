# N3-W OTA 镜像身份与回滚可移植性设计红线 — 2026-10-28

> **CRITICAL / OTA LONG-TERM GUARD**
>
> 本文来自 R10 T1 candidate R2 真实升级事故。该问题不是一次性的 R10 实现细节，
> 而是以后所有 T1/容器/主机 OTA 都必须遵守的通用设计约束。

## 1. 事故结论

R2 exact artifact 中同一个 `greenhouse-manager-arm64.tar` 同时具有：

- OCI config digest：
  `sha256:94db48b902c39f1ffa61cd9b5e91e683b18be4eefdd07d4a95a7dbfb5495ceef`
- OCI manifest digest：
  `sha256:9b5b3daf706b2bafc927426a26cf373d7f657a5d090948f6387906e5bc7973f2`

CI 构建机上的 `docker image inspect ... .Id` 返回 config digest，并被 R2 package
错误冻结为唯一 `manager.image_id`。

真实 T1 加载同一个 exact tar 后，Docker event 在 target tag 被 rollback 删除时报告的
Actor.ID 是 OCI manifest digest。

因此，**Docker runtime 暴露的 image ID 可能随 engine/image-store 实现而变化，
不能作为跨主机、跨 Docker 版本/存储实现的唯一 portable artifact identity。**

R2 executor 把 CI runtime `.Id` 强制等同于 T1 runtime `.Id`，导致 exact image 已成功
load 后仍被误判为 `target_image_binding_invalid`，随后进入 rollback。

## 2. OTA 核心设计规则

### 2.1 Artifact identity 与 runtime identity 必须分离

以后所有 OTA 必须分别记录：

1. **Artifact-native identity**
   - artifact 文件 SHA-256
   - OCI config digest
   - OCI manifest digest
   - platform / architecture
   - artifact 内 tag / reference
2. **Runtime engine identity**
   - 目标设备实际 `docker image inspect` / event / container Image 字段
   - 仅用于当前运行环境的映射与校验

禁止把某一台 CI/build host 的 runtime `.Id` 当成 portable artifact authority。

### 2.2 OTA package 必须可脱离 Docker daemon 自证身份

package builder 应直接从 image tar / OCI archive 中读取并验证 digest，而不是依赖：

`docker load -> docker inspect .Id -> 写进 manifest`

作为唯一绑定方式。

目标设备加载前，artifact 本身必须已经能证明：

- tar SHA-256
- OCI config digest
- OCI manifest digest
- tag/reference
- OS/architecture
- source/build provenance

### 2.3 Runtime 校验必须接受同一 exact artifact 的合法 engine 表示

如果目标 Docker engine 可能用 config digest 或 manifest digest 表示 image identity，
executor 必须将两者都绑定到同一个 frozen artifact authority，再判断 runtime 是否 exact。

不能为了兼容而“放宽到任意 ID”；允许集合必须来自 exact artifact 本身。

## 3. Rollback 设计红线

本次 R2 还暴露第二个 OTA 通用问题：

原始 apply failure 在 rollback 再失败时被覆盖，只剩：

`rollback_unproven`

以后 OTA transaction 必须在进入 rollback 前 durable 记录：

- apply_error_class
- apply_error_reason
- failure_phase
- mutation boundary
- rollback_started

rollback 自己再失败时，必须同时保留：

- original apply error
- rollback error
- rollback error class
- current recovery phase

**绝不允许 rollback 错误覆盖原始升级失败原因。**

## 4. Firewall / service 并发回滚规则

registration guard 使用自己的 firewall lock，但 R2 rollback cleanup 原先没有使用同一把锁；
同时 NetworkManager dispatcher 可能在 rollback 的 `stop + disable` 后再次
`reload-or-restart` registration unit。

以后 OTA 涉及 systemd/NetworkManager/firewall 等异步组件时：

- mutation path 与 rollback path 必须使用同一 ownership/lock contract；
- disabled unit 不得被 dispatcher/watchdog 自动重新拉起；
- rollback proof 应比较“规则语义”，不能把实时 packet/byte counters 和自动时间戳误当成规则漂移；
- 但 functional equality 与 transaction closure 必须分开记录，不能因为现场最终看起来健康就改写失败历史。

## 5. OTA 验收最低矩阵

任何后续 T1 OTA 至少需要覆盖：

- build host 与 target host Docker 版本/存储实现不同；
- config digest != manifest digest；
- runtime `.Id` 分别呈现 config/manifest digest 的 synthetic test；
- exact tar 在 target load 后身份仍可从 artifact-native authority 证明；
- apply failure before/after service stop；
- rollback 成功；
- rollback 部分失败；
- apply failure + rollback failure 时原始错误仍可追溯；
- dispatcher/watchdog/network event 与 rollback 并发；
- authorization claim 后永久禁止 replay；
- rollback 后 predecessor runtime、DB、F4、firewall、ports、Broker continuity 独立证明。

## 6. 当前 R3 修复映射

PR #720 当前 R3 repair：

- package manifest 增加 archive-native OCI config + manifest digest；
- CI `.Id` 标记为 non-portable authority；
- executor runtime identity 接受 exact artifact 派生的合法 digest 集；
- rollback 前保存 original apply error；
- firewall cleanup 与 registration guard 使用同一 lock；
- dispatcher 不再 restart disabled registration guard；
- focused regression tests 覆盖上述事故路径。

## 7. 长期规则

以后设计 OTA 时，首先检查本文，而不是从“Docker image ID 一定稳定”开始假设。

建议长期视为以下工程原则：

`ARTIFACT_IDENTITY != RUNTIME_ENGINE_IDENTITY`

`ROLLBACK_ERROR MUST NOT ERASE APPLY_ERROR`

`OTA_SUCCESS = EXACT_ARTIFACT + AUTHORIZED_MUTATION + POSTCHECK + PROVEN_ROLLBACK_PATH`

状态：

`OTA_DESIGN_GUARD=ACTIVE`
`R2_LIVE_AUTHORIZATION=CONSUMED_DO_NOT_REPLAY`
`R3_SOURCE_REPAIR=IN_PROGRESS`
