# greenhouse-manager 生产驱动临时主机副本故障矩阵 V1

**Schema：** `gh.m2.t1-manager-identity-production-driver-replica-fault-matrix/1`  
**开发门：** M2.4g-6g  
**状态：** 临时副本验证；真实 T1 禁止；生产驱动未安装

## 1. 目的与路线位置

本阶段承接 M2.4g-6f 的 production manager driver contract，在系统临时目录中的标记主机副本上，对生产驱动的方法顺序、授权 claim、运行时重验证、fresh rollback、manager material 写入、manager-only recreate、发布验证、既有实体连续性、私有 journal 和完整回退进行故障注入。

该矩阵只证明事务编排与恢复语义能够在临时副本中闭环，不代表真实 T1 已具备执行条件，更不代表 `greenhouse-manager` 已完成身份迁移。

## 2. 输入绑定

矩阵必须绑定并重新验证：

- mode `0600` 的 production manager driver contract；
- driver contract、adapter contract 与 preparation manifest 的 SHA-256；
- manager runtime binding、username 与独立 Client ID 指纹；
- 6d 标记临时主机副本及其 baseline inventory；
- `replica_only=true`、`real_t1_target_allowed=false` 和 `docker_commands_available=false`。

临时副本必须位于系统临时目录，目录 mode 不得向 group/other 开放，且不得包含符号链接。

## 3. 覆盖的方法

矩阵覆盖 6f 冻结的全部 14 个方法：

```text
claim_authorization
revalidate_runtime
verify_fresh_rollback
install_manager_material
recreate_manager
verify_authenticated_identity
verify_ingress_subscription
verify_canonical_publication
verify_discovery_publication
verify_reconnect
verify_existing_entities
postactivation_audit
rollback
append_journal
```

其中核心 material 写入、manager recreate、身份和发布验证、完整 snapshot rollback 继续复用 6d 已验证的临时副本适配器；6g 在其外层增加 authorization、runtime、fresh rollback、existing entities 和 journal 驱动语义。

## 4. 合成授权 claim

6g 不使用 6c 的真实授权文件，也不产生可用于真实 T1 的授权。

临时副本内生成只与 driver contract SHA-256 绑定的合成授权材料，并验证：

- source 与 claim 位于同一文件系统；
- source 和 claim 均为 mode `0600`；
- 使用 hardlink 建立 claim；
- claim directory 执行 fsync；
- source unlink 后 source directory 执行 fsync；
- claim inode 与原 source inode 一致；
- claim 只存在于事务私有 workspace，事务结束即删除。

## 5. Fresh rollback 验证

在任何 manager material 写入前，矩阵必须确认：

- baseline snapshot 已存在；
- baseline inventory 非空；
- baseline snapshot inventory 与捕获记录完全一致；
- 当前 manager replica inventory 与 baseline 完全一致。

此处验证的是临时副本 snapshot，不是未来真实 T1 的 fresh rollback 包。

## 6. Journal 验证

临时 journal 必须：

- 位于事务 workspace；
- 目录 mode `0700`、文件 mode `0600`；
- 每阶段 JSON Lines append 后执行 file fsync；
- journal directory 执行 fsync；
- 只记录 schema、driver contract SHA-256、阶段、状态和 `replica_only`；
- 不记录密码、完整身份值或真实主机路径。

## 7. 故障矩阵

矩阵包含 16 个故障点。

### 7.1 写入前故障

```text
after_authorization_claim
after_runtime_revalidation
after_fresh_rollback_verification
```

验收要求：

- 尚未修改 manager replica；
- 不触发 rollback；
- 事务 workspace 被清除；
- replica inventory 与 baseline 精确一致。

### 7.2 写入后及验证阶段故障

```text
after_password_write
after_env_write
after_overlay_write
after_recreate
after_identity
after_subscription
after_canonical_publish
after_discovery_publish
after_reconnect
postactivation
after_existing_entities
after_journal_commit
```

验收要求：

- 自动执行完整 snapshot rollback；
- 新增 password、auth environment 与 Compose overlay 全部清除；
- 只调用 manager replica 的 rollback recreate；
- legacy anonymous path 验证通过；
- rollback 后 inventory 与 baseline 精确一致。

### 7.3 回退失败故障

```text
rollback_incomplete
```

验收要求：必须显式报告终止错误，不得误报事务成功或已完成回退。

## 8. 成功路径验收

成功路径必须同时满足：

- 合成授权 claim 完成；
- runtime 与 host replica plan 无漂移；
- fresh rollback baseline 验证完成；
- 三份 manager material 原子写入；
- manager replica recreate 请求完成；
- 认证身份、独立 Client ID、ingress、canonical、Discovery、reconnect 验证完成；
- postactivation audit 通过；
- 既有 Home Assistant 实体连续性验证完成；
- journal commit 完成；
- 除 rollback 外的 13 个方法均在成功路径执行。

完整矩阵还必须通过至少一个写入后故障验证 rollback 方法，因此最终 14 个方法覆盖率为 100%。

## 9. 强制安全状态

计划、单次事务和矩阵报告必须保持：

```text
replica_only=true
real_t1_target_allowed=false
docker_commands_available=false
production_manager_driver_installed=false
production_executor_available=false
execution_enabled=false
apply_enabled=false
operator_action_authorized=false
ready_for_manager_migration_apply=false
manager_identity_migrated=false
node_credentials_delivered=false
current_services_modified=false
preserve_anonymous=true
anonymous_closure_enabled=false
```

只有完整矩阵通过后，矩阵报告才允许：

```text
production_replica_fault_matrix_passed=true
ready_for_live_runtime_gate=true
```

这里的 `ready_for_live_runtime_gate` 只允许进入下一阶段的真实 T1 **只读** runtime/mount/Compose 检查，绝不授权写入或重建。

## 10. CLI 边界

公开 CLI 只生成并验证 replica plan。不得提供：

```text
--execute
--claim
--apply
--live
```

实际矩阵只能由测试代码注入明确的临时 replica driver factory 执行。

## 11. 下一门禁

M2.4g-6g 通过后进入 M2.4g-6h：真实 T1 只读 runtime、mount、Compose 与 active secret target gate。6h 仍不得写入文件、创建授权、重建容器或迁移 manager 身份。
