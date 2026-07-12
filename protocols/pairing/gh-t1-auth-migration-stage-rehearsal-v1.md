# gh-t1-auth-migration-stage-rehearsal-v1

## 1. 目的

M2.4e 验证 M2.4d 生成的真实 T1 私有非激活暂存目录可以作为唯一迁移材料来源，在隔离的 Mosquitto 快照候选中完成认证迁移演练，并在故障场景下可靠清理。

本阶段仍不授权真实迁移。

## 2. 输入

唯一显式输入为 M2.4d 暂存目录及预期 retained topic。

暂存目录必须先通过：

```text
verify_migration_stage
```

随后必须校验：

- `activation-plan.json` 仍处于禁用状态；
- 暂存迁移包副本 SHA-256 与 manifest 一致；
- 暂存迁移包自身完整性有效；
- 原回退包、原迁移包和全部真实 Compose/.env 源文件仍与暂存时 SHA-256 一致。

## 3. 禁用状态要求

演练前必须满足：

```text
activation_enabled = false
current_services_modified = false
active_paths_modified = false
preserve_anonymous = true
anonymous_closure_enabled = false
```

任一标志不满足时，不得创建候选容器。

## 4. 故障注入演练

第一轮候选必须：

1. 从暂存 manifest 指向的回退包恢复临时快照；
2. 使用暂存目录内的迁移包副本；
3. 使用回退包记录的精确 Mosquitto image ID；
4. 以 `--network none` 创建候选；
5. 应用迁移包中的精确 Dynamic Security 请求；
6. 在请求完成后、身份矩阵验证前注入预期故障；
7. 无论故障如何，删除候选容器和临时目录。

故障候选仍存在时，整道门必须失败。

## 5. 完整演练

故障清理验证后，必须从同一暂存目录重新执行完整隔离演练：

- provisioning 身份可管理候选；
- bootstrap admin 删除成功且不可继续使用；
- 删除 admin 后 provisioning 仍可工作；
- node、manager、Home Assistant、provisioning 四身份 ACL 矩阵通过；
- client ID 强绑定通过；
- provisioning 只能访问 Dynamic Security control；
- node、manager、Home Assistant 不能访问 control；
- retained 状态恢复；
- legacy anonymous 应用主题仍可用；
- anonymous `$CONTROL/#` 被拒绝；
- 完整候选结束后被删除。

## 6. 不变性检查

故障演练与完整演练前后必须重新验证：

- 暂存目录全部文件、权限、大小和 SHA-256；
- `stage-manifest.json` SHA-256；
- 原回退包 SHA-256；
- 原迁移包 SHA-256；
- 真实 Compose 文件 SHA-256 与模式；
- 真实 `.env` SHA-256 与模式。

任何差异必须阻断并报告，不得自动修复。

## 7. 成功报告

成功报告 schema：

```text
gh.m2.t1-auth-migration-stage-rehearsal/1
```

报告必须包含以下布尔证据：

```text
stage_verified = true
staged_package_verified = true
fault_after_exact_request_injected = true
fault_candidate_cleanup = true
success_candidate_cleanup = true
stage_immutable = true
live_sources_unchanged = true
exact_package_request_applied = true
exact_package_identity_matrix = true
client_id_binding = true
provisioning_control_only = true
bootstrap_admin_removed = true
provisioning_after_admin_removal = true
legacy_anonymous_after_admin_removal = true
anonymous_control_denied = true
retained_state_recovered = true
activation_enabled = false
active_paths_modified = false
current_services_modified = false
```

报告不得包含任何密码、`.env` 内容或完整客户端配置。

## 8. 安全边界

本阶段允许的 Docker 写操作仅限两个临时候选容器：

- 故障注入候选；
- 完整演练候选。

两个候选均必须：

```text
network = none
```

本阶段不得：

- 修改真实 Mosquitto 配置或数据；
- 修改真实 Compose 文件或 `.env`；
- 写入 `/opt/greenhouse-secrets/mqtt`；
- 重启、停止或重建真实容器；
- 修改 Home Assistant 或节点凭据；
- 关闭匿名访问；
- 修改或重新生成暂存内容；
- 将暂存内容复制离开 T1。

M2.4e 通过后，任何真实 apply 仍必须在执行前立即生成新的回退包，并进入独立、显式、可回退的事务门。
