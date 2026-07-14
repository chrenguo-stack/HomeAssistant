# T1 Manager Identity Fresh Chain Preparation V1

状态：M2.4g-6b replacement-chain gate

## 1. 目的

本协议把已经人工复核的 legacy rollback bridge、当前 Home Assistant MQTT
postactivation handoff、当前 inactive migration Stage 和新的 Manager/Compose 实时捕获，
收敛为一份全新的 `greenhouse-manager` 身份迁移 preparation。

该工具只允许发现和验证私有来源，或创建不可执行的 preparation。它不得创建或领取
authorization，不得生成 production execution packet，不得修改或重建任何运行服务。

## 2. 代码基线

运行时必须显式传入并验证：

- 精确仓库提交 SHA；
- 精确 `greenhouse-manager` 版本；
- 精确 retained telemetry Topic；
- 精确 legacy review bridge 名称和 manifest SHA-256。

工具必须从自身所在 Git worktree 验证 `HEAD` 和 `pyproject.toml`，不允许以其他提交的
源码生成新证据链。若通过安装后的入口运行，必须用 `--source-root` 显式指向相同的目标
Git worktree。运行中的 coordinator 源文件还必须与该提交中的同路径 blob 逐字一致。

## 3. 安全发现

工具在指定私有搜索根中只识别以下目录前缀：

- `greenhouse-manager-legacy-review-bridge-`；
- `greenhouse-ha-postactivation-handoff-`；
- `greenhouse-t1-auth-stage-`；
- `greenhouse-manager-migration-preparation-`。

每个候选必须重新验证 mode、inventory、SHA-256、schema 和 retained Topic 绑定。普通报告
只允许输出候选目录名称、名称短指纹、manifest SHA-256、时间和候选数量；不得输出完整路径、
Topic、用户名、Client ID 或秘密值。

若 postactivation handoff 或 Stage 不唯一，生产准备必须失败关闭。历史 preparation 可能分散在
多个归档工作区；默认输出根只能选择与已验证 legacy review bridge 输出目录共享同一工作区
父目录的唯一 preparation 输出根。discover-only 必须同时报告全部合法输出根数量和符合该
bridge-adjacent 拓扑规则的数量，不得报告路径。

若 bridge-adjacent 输出根仍不唯一，生产准备必须失败关闭。允许先使用 `--discover-only` 获取
脱敏候选名称，再显式选择已审核的 handoff/Stage 名称。显式 `--output-root` 必须精确属于本轮
扫描并通过 schema、mode 和 manifest 验证的候选集合；仅为私有目录但未被验证的路径不得接受。

## 4. Legacy review 边界

bridge 必须保持：

```text
rollback_audit_passed=false
manual_review_resolved=true
future_baseline_waiver_enabled=false
ready_for_fresh_evidence_chain=true
ready_for_production_execution=false
```

bridge 只解除旧事务的人工复核阻断，不能替代本轮 live Manager/Compose 捕获、fresh rollback、
两次操作员确认或后续 transaction gate。

## 5. Discover-only

`--discover-only` 只读文件和 Git 元数据，不调用 preparation builder，不写秘密材料，也不调用
Docker。成功报告必须保持：

```text
read_only_live_services=true
current_services_modified=false
authorization_created=false
authorization_claimed=false
ready_for_production_execution=false
manager_identity_migrated=false
node_credentials_delivered=false
preserve_anonymous=true
anonymous_closure_enabled=false
```

## 6. Fresh preparation

非 discover 模式调用正式 `prepare_manager_identity_migration` 实现，重新验证：

- postactivation handoff；
- inactive Stage 及 Manager 凭据材料；
- legacy review bridge；
- 当前运行 Manager 身份；
- 当前 Compose 配置、`.env` 和目标 secret root。

它只在既有 mode-0700 preparation 输出根下创建新的私有 preparation。成功结果必须固定：

```text
legacy_review_bridge_bound=true
future_baseline_waiver_enabled=false
ready_for_manager_migration_authorization=true
ready_for_manager_migration_apply=false
authorization_created=false
authorization_claimed=false
ready_for_production_execution=false
current_services_modified=false
```

## 7. 下一门

fresh preparation 成功后，仍需从该新 preparation 重新生成 contracts、live runtime gate、
directory contract、preclaim probe、fresh rollback 和短时 execution preparation。只有整条 fresh
evidence chain 全部通过，才允许请求第一次新的精确操作员确认。
