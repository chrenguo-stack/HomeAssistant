# H0/H1 源码基线状态（2026-08-02）

- 源码决策：`D1-H0H1-V07-IDENTITY-ALIGNMENT-GREENHOUSE-INIT-PORTABLE-RESTORE-CONTRACT-AND-HOST-ONLY-HARNESS-CREATION-20260802-01`
- 零净历史漂移接受与重建决策：`D1-H0H1-ACCIDENTAL-MAIN-ZERO-NET-HISTORY-DRIFT-ACCEPTANCE-AND-PR260-CURRENT-MAIN-REBUILD-REVALIDATION-20260802-01`
- T1 只读基线审计：`D1-H0H1-PR260-EXACT-HEAD-T1-READ-ONLY-BASELINE-AUDIT-AUTHORIZATION-20260802-01`
- 基线缺口纠偏源码决策：`D1-H0H1-PR260-T1-BASELINE-GAP-REMEDIATION-DESIGN-AND-HOST-ONLY-PERSISTENCE-MIGRATION-CONTRACT-CREATION-20260802-01`
- 当前接受 main：`ba6255cb3cb4067efd72b23f81f1a799c2c0026e`
- 原始内容等价基线：`1a5f08d31de837f09cd921205f540ba6f3f568dc`
- V0.7 来源：PR #211 精确 HEAD `1947a9e7c3d1e5d158a7987a0b02baba71f0c730`
- T1 基线文件 SHA-256：`8408e29885fdce1efb0500c0b2a1783b0ea9751fdf156b1c177dd2695cf46d85`
- 状态：源码开发、host-only 验证和真实 T1 只读基线阶段
- H0：`PARTIAL_IMPLEMENTATION_NOT_ACCEPTED`
- H1：`SOURCE_CONTRACT_IMPLEMENTED_NOT_LIVE_ACCEPTED`

## main 历史处置

三次空文件误创建及其三次立即删除已作为零净文件变化的公开历史接受；未执行 force rewrite。
PR #260 已使接受后的 current main 成为源码 HEAD 的祖先。当前审查 Artifact 必须从
`origin/main` 解析并记录实际 BASE_SHA，同时记录精确 SOURCE_SHA；旧 Artifact 仅保留为历史证据。

## T1 只读基线结论

```text
t1_read_only_audit=PASS
manager_running_version=0.4.64
manager_target_source_version=0.4.98
manager_data_mount_present=false
broker_dynamic_security_state_present=true
broker_persistence_state_present=true
anonymous_compatibility_active=true
portable_restore_role_inventory_complete=false
real_backup_ready=false
restore_ready=false
anonymous_closure_ready=false
```

缺少 `/var/lib/greenhouse-manager` 持久化挂载是当前主要缺口。缺少挂载不能证明容器内部或其他
旧路径不存在身份和业务状态，因此后续必须先完成隐藏运行状态分类。

## 本阶段包含

- 当前 main 上重新落地 V0.7 和 C-07 永久 NODE_ID 封存语义；
- Manager 目标版本推进至 0.4.98；
- 正式 `bootstrap/` 生命周期；
- marker-last 系统初始化；
- 完整角色清单的 AES-GCM 可移植备份；
- 原子恢复；
- 双主机 SYSTEM_ID claim 冲突模型；
- 匿名关闭 secret-free 隔离 policy；
- 真实 T1 secret-free 只读基线；
- Manager 持久化迁移计划合同；
- `/var/lib/greenhouse-manager` 0700/0600 目标布局；
- 十角色逻辑映射、迁移分支和回滚合同；
- focused tests、CLI 集成和两个 host-only harness；
- secret-free GitHub review Artifact。

## 当前阻塞

```text
runtime_hidden_state_classified=false
candidate_root_prepared=false
manager_state_materialized=false
portable_backup_verified=false
execution_authorized=false
real_backup_creation=false
real_restore=false
anonymous_closure=false
deployment=false
```

## 本阶段未执行

```text
t1_write_operation=false
container_change=false
broker_change=false
home_assistant_change=false
board_operation=false
production_credential_generation=false
real_backup_creation=false
real_restore=false
anonymous_closure=false
ready=false
merge=false
release=false
tag=false
deployment=false
```

本文件不构成真实 H0/H1 验收。
