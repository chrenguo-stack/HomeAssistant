# H0/H1 源码基线状态（2026-08-02）

- 源码决策：`D1-H0H1-V07-IDENTITY-ALIGNMENT-GREENHOUSE-INIT-PORTABLE-RESTORE-CONTRACT-AND-HOST-ONLY-HARNESS-CREATION-20260802-01`
- 零净历史漂移接受与重建决策：`D1-H0H1-ACCIDENTAL-MAIN-ZERO-NET-HISTORY-DRIFT-ACCEPTANCE-AND-PR260-CURRENT-MAIN-REBUILD-REVALIDATION-20260802-01`
- 当前接受 main：`ba6255cb3cb4067efd72b23f81f1a799c2c0026e`
- 原始内容等价基线：`1a5f08d31de837f09cd921205f540ba6f3f568dc`
- V0.7 来源：PR #211 精确 HEAD `1947a9e7c3d1e5d158a7987a0b02baba71f0c730`
- 状态：源码开发与 host-only 验证阶段
- H0：`PARTIAL_IMPLEMENTATION_NOT_ACCEPTED`
- H1：`SOURCE_CONTRACT_IMPLEMENTED_NOT_LIVE_ACCEPTED`

## main 历史处置

三次空文件误创建及其三次立即删除已作为零净文件变化的公开历史接受；未执行 force rewrite。
PR #260 已使接受后的 current main 成为源码 HEAD 的祖先。当前审查 Artifact 必须从
`origin/main` 解析并记录实际 BASE_SHA，同时记录精确 SOURCE_SHA；旧 Artifact 仅保留为历史证据。

## 本阶段包含

- 当前 main 上重新落地 V0.7 和 C-07 永久 NODE_ID 封存语义；
- Manager 版本推进至 0.4.98；
- 正式 `bootstrap/` 生命周期；
- marker-last 系统初始化；
- 完整角色清单的 AES-GCM 可移植备份；
- 原子恢复；
- 双主机 SYSTEM_ID claim 冲突模型；
- 匿名关闭 secret-free 隔离 policy；
- focused tests、CLI 集成和 host-only harness；
- secret-free GitHub review Artifact。

## 未执行

```text
t1_operation=false
docker_operation=false
broker_operation=false
home_assistant_operation=false
board_operation=false
network_operation=false
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
