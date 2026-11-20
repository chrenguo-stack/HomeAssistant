# N3-W T1 KF-168 executor readiness source repair → read-only deployment preflight

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：KF-168 IPC 迁移执行器在应用 owner 启动后存在 readiness 抢跑。源码修复、离线验证、适用 CI 和精确归档现已闭环。
- 已完成到：部署与回退共用 bounded monotonic readiness barrier；Draft PR #811 精确源码 CI 与公共安全 CI 首次运行均成功；review package 明确禁止 live execution。
- 当前状态：**源码门 CLOSED_PASS**。停在新的只读部署预检入口。Phase-A 整体仍为 `NOT_YET_PASS`，#810 永久 IPC 隔离仍未留在现场。

## 2. 代码与证据

- 仓库：`chrenguo-stack/HomeAssistant`。
- Fresh-rebind main：`3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`。
- PR #807 head：`7811b6bc2fc3cdc5b1cecb45549cb81b6d80784c`。
- PR #809 head：`06332c58de850c590da83e0971d7576291f371b2`。
- PR #810 head：`4abebaa61c1db0be41a724c45263e26ac15eb06e`，tree `b34b33ebd7bd477c7f10692c001b8da45768a645`。
- PR [#811](https://github.com/chrenguo-stack/HomeAssistant/pull/811) source repair head：`6611c3bcac644e34d81077428fd454f3c8b9d557`，tree `795eb8f1f7e3dcbfa8b34cc236fd5139a30f10e7`。
- Exact blobs：executor `c0a05384dff5b44537a48e9a0dab048e2df7e1ee`；manifest `2076b667b7d171f84c26e6ac1b8cf62d8089cf49`；test `f1399027ed65ec9324481a91b84c3c4b0db9fff8`；workflow `5bd948932f6a3dd150d1a54c8e30a47c8e5cd043`。
- [Source CI 44742034850](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44742034850)：SUCCESS / attempt 1；focused committed successor tests 12 PASS；disposable ext4 regression PASS。
- [Public safety 44742034856](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44742034856)：SUCCESS / attempt 1。
- 源码闭环：[N3W_T1_KF168_IPC_MIGRATION_EXECUTOR_READINESS_SOURCE_REPAIR_CLOSURE_20261120.md](./N3W_T1_KF168_IPC_MIGRATION_EXECUTOR_READINESS_SOURCE_REPAIR_CLOSURE_20261120.md)。

## 3. 必须继承的结论

- 已证实：旧执行器将 Type=simple owner 的 Started 错当 Docker readiness；本次修复允许在 exact pre-created Manager 身份仍成立且 owner 未失败时短暂 0 running，随后要求 exact Manager + HA 真实 running。
- 已证实：部署与回退调用同一个 barrier；Manager 重复／替换、image/bind 漂移、owner/OTA 失败、Host/Broker 漂移和 deadline 均 fail closed；没有 fixed sleep、自动 restart 或 retry。
- 已证实：successor 为 review-only，`LIVE_EXECUTION_AUTHORIZED=false`；旧 wrapper SHA-256 `519539f6f67d8a5f37bd9cd28cd90cb7ac61ece35ba7135c4a494c697a220785` 与所有旧授权均不可重放。
- 已证实：源码/测试/CI 闭环不改变现场。最后实机仍是 2026-11-20T11:22:13Z 的 `U13B_ROLLED_BACK / ROLLED_BACK`，业务健康；#810 新 IPC 布局未部署。
- 待确认：下一次 read-only preflight 时的现场标记为 `UNKNOWN_FRESH`；必须重新验证 T1、候选五文件 baseline、无残留挂载、稳定 Manager/HA/Broker，以及真实 N3-W telemetry source 可用性。
- 待确认：未来 Phase-A completion 仍需新的 fresh simplified N3-W telemetry 与同窗口 HA MQTT transport 证据。此前窗口事件数为 0，不能把 Phase-A 标为 PASS。
- 已排除：不再把 systemd Started 或一次即时 0 running 当作容器失败；不得重新归因到已修复的旧 device_busy，除非新证据重新出现。

## 4. 执行范围与授权

- 可继续：**只读 T1 部署预检**，fresh rebind 现场、候选、五文件旧值、Manager pre-create 可行性、owner/Compose 绑定、USB 无挂载状态，以及真实 telemetry/HA MQTT 观测能力；可形成新的只读证据和未来执行候选绑定。
- 暂停边界：不得写入五文件；不得 stop/start/restart OTA/APP/Broker；不得 mount/unmount；不得 recreate 容器；不得修改 Host/USB transaction；不得部署 #810/#811；不得 claim/replay 旧授权；不得进入 U11+、Phase-B、merge/release。
- 授权状态：`NEW_LIVE_AUTHORIZATION=NOT_GRANTED`。交接不授予任何 live mutation。此前 #810 五文件迁移、回退、残留挂载清理及其他一次性授权全部 consumed/no-replay。

## 5. 下一步

```text
NEXT_ONE_GATE=N3W_T1_KF168_IPC_MIGRATION_EXECUTOR_READONLY_DEPLOYMENT_PREFLIGHT
SCOPE=READONLY_T1_PREFLIGHT_ONLY
PHASE_A_OVERALL=NOT_YET_PASS
```

1. Fresh rebind main、PR #807/#809/#810/#811、Current State、Known Failures 与本 closure。
2. 只读核对当前 T1，不使用旧 wrapper；确认现场仍与已归档 rollback baseline 相容。
3. 只读验证未来迁移的 Manager pre-created ID/Compose/owner readiness 前提，以及五文件新旧 exact binding。
4. 只读证明至少一个可控真实 N3-W telemetry source 当前可产生 fresh accepted event，并确认同窗口 HA MQTT 传输可观测。
5. 预检 PASS 也只说明“可进入新的 live authorization 设计/申请边界”；它不自动授权部署。

完成条件：形成新的 exact read-only preflight archive，明确 PASS/STOP、现场时间、candidate binding、telemetry availability 和下一授权边界。任何写操作前停止。

## 6. 必读定位与归档

- 仓库规则：`AGENTS.md`、`docs/development/N3W_PROJECT_WORKING_CONTEXT.md` §12、`docs/development/development-artifact-archive-rules.md`、V1.4 handoff template。
- 任务资料：`N3W_CURRENT_STATE.md`、`N3W_CURRENT_STATE_INDEX.md`、`KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`；本 source-repair closure；上一轮 [migration STOP/rollback archive](https://github.com/chrenguo-stack/HomeAssistant/blob/3532dd9877bdb4454415068ce52c6290bb743bd1/docs/development/N3W_T1_KF168_IPC_MIGRATION_READYNESS_STOP_AND_ROLLBACK_20261120.md)；#810 IPC isolation design。
- 已归档：PR #811 exact source/test/manifest/workflow blobs、两项 SUCCESS CI、source repair closure、Current State/Index/KF guard 更新。
- 未归档重要资料：无。本轮无新私有 T1 证据或凭据。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
UNARCHIVED_CRITICAL_RESULT_COUNT=0
SECRET_VALUES_INCLUDED=false
```

新会话启动语：

> 阅读本交接及 §6 必读资料，fresh rebind `main`、PR #807/#809/#810/#811 和最新 GitHub 归档。只进入 `N3W_T1_KF168_IPC_MIGRATION_EXECUTOR_READONLY_DEPLOYMENT_PREFLIGHT`，严格只读核对当前 T1、五文件/Compose/Manager readiness 前提及真实 N3-W telemetry + 同窗口 HA MQTT 观测能力。达到新的 live authorization 边界即停；不得重放旧执行器或已消费授权，不得将 Phase-A 记为 PASS。
