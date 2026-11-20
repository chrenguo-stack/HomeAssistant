# N3-W T1 KF-168 IPC 迁移中止与回退 → 执行器就绪修复

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：继续 Home Assistant 强制 USB OTA 的 U9+ Phase‑A。目标是修复 KF‑168 的 Manager IPC 目录递归绑定问题，并完成真实 T1 的自动回滚验收。本次交接停在五文件迁移中止、原文件和业务恢复之后。
- 已完成到：已复现实机 USB `device_busy` 根因，已清理确切的残留挂载。永久 IPC 隔离候选实现、源码复核及适用 CI 通过。五文件迁移曾执行一次，实机启动检查抢跑后回退；独立只读复核确认 5/5 文件与部署前逐字节相同，业务恢复。
- 当前状态：可继续**迁移执行器的源码修复及离线验证**。Phase‑A 持久回滚和业务恢复已证实，产品完成检查尚未通过，`PHASE_A_OVERALL=NOT_YET_PASS`；永久隔离候选未留在现场。
- 产品范围：`T1_Core_Stack OTA` V1.0 已冻结产品级架构。它的详细设计和 SOTA‑R1–R7 整栈实现／验收另行推进，不能用此处 HA Phase‑A 的证据代替。Phase‑B 连续停机时间及 SLA 也仍为独立阶段。

## 2. 代码与证据

- 仓库：`chrenguo-stack/HomeAssistant`；核对时 `main=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`。交接分支为 `docs/n3w-u9plus-phase-a-restart-live-preflight-20261120`，交接前证据 head 为 `3532dd9877bdb4454415068ce52c6290bb743bd1`。
- 三个源码 PR 均为 OPEN / DRAFT / UNMERGED，交接记录不改变其 head：

  | PR | 用途 | 核对时完整 head |
  | --- | --- | --- |
  | [#807](https://github.com/chrenguo-stack/HomeAssistant/pull/807) | U9+ Phase‑A 及 restart-convergence 修复 | `7811b6bc2fc3cdc5b1cecb45549cb81b6d80784c` |
  | [#809](https://github.com/chrenguo-stack/HomeAssistant/pull/809) | 脱敏 USB 子命令诊断 | `06332c58de850c590da83e0971d7576291f371b2` |
  | [#810](https://github.com/chrenguo-stack/HomeAssistant/pull/810) | 永久隔离 Manager OTA IPC 导出和 USB 挂载树 | `4abebaa61c1db0be41a724c45263e26ac15eb06e` |

- #810 源码 tree：`b34b33ebd7bd477c7f10692c001b8da45768a645`。确认 16 SUCCESS / 4 草稿门控 SKIP / 0 FAILURE / 0 PENDING；关键 [Linux ext4 与 socket 回归](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44724148347)、[HA 目标绑定](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44724148316)、[Manager A→B](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44724148419) 均成功。本地 228 项测试、13 项执行包绑定检查通过；两项 Linux 专用检查由 CI 执行。
- #810 绑定：P3 manifest blob `33a8ccdcccf4c02c36e51139e357260f0813ce62`，Phase‑A manifest blob `67ca34f0d2b9d223474a325fcd51ed733d7bf593`，Linux 回归所在测试 blob `77023d9552781b09064cd7d851bd58b94a46f7a1`。五文件的线上前态与候选后态精确哈希见[迁移预检](https://github.com/chrenguo-stack/HomeAssistant/blob/b7f7d2dd70ae00deead70c30f23551fc8c1645e6/docs/development/N3W_T1_KF168_MANAGER_OTA_IPC_MIGRATION_PREFLIGHT_20261120.md)。
- 线上最近审核时仍为旧布局，活跃候选 daemon blob `941baffc8423a10cfa1436323d109caae17be473`，U13B Host blob `437f3e6c4cae53f7d94e244cd312ac454768f8e1`；不要把 #810 或其 CI 结果当成已部署事实。该 HA 回滚实验和仓库已验收的 Core Stack 产品基线由 [Current State](./N3W_CURRENT_STATE.md) 分别记录。

## 3. 必须继承的结论

- **已证实，USB 根因。** Manager 对旧 OTA 根目录的只读递归 bind 保留了绑定 USB 的读写 ext4 超级块。私有挂载命名空间中的 `ro,noload` 实测退出 32 / `device_busy`。单次受权卸载清理成功。永久方案拆分 IPC 导出和 USB 挂载树，保留 Manager 容器内 socket、清单路径和 UID 999 校验。旧故障和新布局均有 Linux 回归证据。见[根因归档](https://github.com/chrenguo-stack/HomeAssistant/blob/b726c7d14732e4a73568ada4c0ad29a59a2f8e27/docs/development/N3W_T1_KF168_MANAGER_RECURSIVE_BIND_USB_EBUSY_ROOT_CAUSE_20261120.md)及[清理归档](https://github.com/chrenguo-stack/HomeAssistant/blob/b828ccab36416d3152e3a5eff85236d7810bb793/docs/development/N3W_T1_KF168_EXACT_MANAGER_RETAINED_USB_UNMOUNT_PASS_20261120.md)。
- **已证实，迁移停点。** 5 个候选文件按计划写入，最后成功步骤包含预创建停止态 Manager、启动 OTA 并验证新导出端点与宿主机兼容别名，随后应用 owner 启动命令返回。即时运行中容器断言报 `container_not_unique`，触发回退。回退中的同一断言也曾抢跑；后续独立审计证实 5/5 原文件恢复。回退时 systemd 11:17:55.315Z 标记 Started，Docker 直到 11:17:56.576Z/11:17:56.578Z 才启动 HA/Manager。部署时的失败和回退时的观测都不能用作新布局已经收敛后的失败证据。见[执行与回退归档](https://github.com/chrenguo-stack/HomeAssistant/blob/3532dd9877bdb4454415068ce52c6290bb743bd1/docs/development/N3W_T1_KF168_IPC_MIGRATION_READYNESS_STOP_AND_ROLLBACK_20261120.md)。
- **已证实，最后实机观测。** 脱敏目标为同一 T1 故障注入实验实例。2026‑11‑20T11:22:13Z，Host `U13B_ROLLED_BACK / ROLLED_BACK`，事务 SHA‑256 `4548f591d972576ea4d3f1f078cb55b483d1f63f2244b03c3413da1891e09d3f`；业务 1/1/1、监听匹配、两路 MQTT 已认证、HA HTTP 401。Broker 未重启。回退窗口绑定 ext4 正常挂载及卸载各一次，11 个已检查命名空间无残留。既有 Host/USB 元数据比对证据为 `HOST_USB_EXACT`；最近回退审计验证了 Host 原字节与 USB 挂载路径，未在该审计中重新比对 USB 的五份元数据。
- **已证实，完成检查仍开。** 回退后的 IPC（Manager UID/GID 999:999）终态为 `ERROR / u9_plus_recovery_customer_oracle_incomplete`。11:17:51–11:22:13 UTC 的窗口内，接受的简化 N3‑W 遥测事件为 0，缺少必须的新遥测与同窗口 HA MQTT 传输证据；聚合错误不会逐项列出所有失败断言。
- **待确认。** 上述时间之后的现场标为 `UNKNOWN_FRESH`。下一次验收前需要重新核对现场及可控的真实 N3‑W 遥测来源。执行器就绪屏障尚未实现；即使原有源码和 CI 成功，也仍需该修复与新的实机迁移证据。
- **已排除的误判。** systemd `Type=simple` 的 Started 不是容器 readiness；单次即时查询为零不能直接当成重复或错误容器。回退窗口的 USB 已正常挂载，不能把这次聚合完成错误直接归为旧 `device_busy`。当前数据也不能证明 Phase‑B 的用户停机时间指标。

## 4. 执行范围与授权

- 可继续：在隔离 worktree 审查已归档的执行器，修复部署／回退就绪检查；写离线回归、运行适用 CI、核验精确哈希并归档审查候选。可以提前定义后续真实遥测的可用性验收和最小观测合同。
- 暂停边界：停在源码门。任何新的 T1 部署、文件写入、服务停启、迁移试跑、挂载／卸载、容器重建、Host/USB 事务操作及发布合并均需各自的边界。不进入 U11+、Phase‑B 或 SOTA 整栈验收。
- 已消费／禁止重放：产品 U9、先前 U10 故障注入、`a103...` 和 `437f...` 单文件替换＋各一次 OTA 重启、隔离挂载诊断、残留挂载清理、#810 五文件迁移及该次回退。
- 上次回退入口：已归档的五文件前态和哈希，以及 T1 受保护的同次执行收据与备份。私有备份字节不公开；候选模块旧 blob 和已安装 unit/overlay 的旧 SHA‑256 在迁移预检中绑定。交接本身不授予权限。

## 5. 下一步

```text
NEXT_ONE_GATE=N3W_T1_KF168_IPC_MIGRATION_EXECUTOR_READINESS_SOURCE_REPAIR
SCOPE=SOURCE_OFFLINE_TEST_CI_ARCHIVE_ONLY
PHASE_A_OVERALL=NOT_YET_PASS
```

1. Fresh rebind `main`、#807/#809/#810、GitHub 归档分支及最新停点。将 #810 精确源码和历史执行器区分绑定。复核迁移 install/rollback 共同的即时容器查询及 systemd/Docker 时间线。
2. 给部署与回退共用一个基于单调时钟、有期限的就绪屏障。预创建的 Manager 必须在 OTA 启动前固定 ID。应用 owner 启动后，在唯一期望容器身份仍可证明、单元未失败的情况下允许短暂 0 running；待 Manager 和 HA 实际运行，再做原有身份、镜像、绑定、业务和事务校验。
3. 回归至少覆盖：初始停止后收敛、部署及回退两条路径、容器重复／意外替换、镜像或挂载漂移、owner 失败、Broker/Host 漂移以及超时。禁止固定睡眠代替就绪证明；禁止自动重启或重试来通过校验。先离线、再适用 CI、再 exact remote binding。
4. 完成条件：修复与回归都已归档，保留 #810 的 IPC 隔离合同和稳定容器身份契约，形成一份新的可审查迁移候选。另行列出真实 N3‑W 遥测源的可用性及 HA MQTT 同窗证明要求。**本门通过后停在新的只读部署预检入口**；旧迁移执行器和授权均不得复用。

## 6. 必读定位与归档

- 仓库规则：适用 `AGENTS.md`、[项目工作上下文 §12](./N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set)、[归档规则](./development-artifact-archive-rules.md)及开发规范。交接模板 [V1.4](./templates/NEW_CHAT_HANDOFF_TEMPLATE.md)，精确 blob `885fd63131e80936e5e1fe907378be08a0060f12`。
- 任务资料：[Current State](./N3W_CURRENT_STATE.md)、[Current State Index](./N3W_CURRENT_STATE_INDEX.md)、[KF‑168 最新条目](./KNOWN_FAILURES_AND_REGRESSION_GUARDS.md)；[Phase‑A 验收合同](./N3W_T1_U9_PLUS_BOUNDED_RECOVERY_REAL_T1_FAULT_INJECTION_ACCEPTANCE_PHASE_A_PLAN_20261119.md)；[V1.0 架构 §§28–31](./N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.0_20261106.md#28-acceptance-gates-for-future-implementation)。
- 已归档关键结果：[根因与实际复现](https://github.com/chrenguo-stack/HomeAssistant/blob/b726c7d14732e4a73568ada4c0ad29a59a2f8e27/docs/development/N3W_T1_KF168_MANAGER_RECURSIVE_BIND_USB_EBUSY_ROOT_CAUSE_20261120.md)、[残留挂载清理](https://github.com/chrenguo-stack/HomeAssistant/blob/b828ccab36416d3152e3a5eff85236d7810bb793/docs/development/N3W_T1_KF168_EXACT_MANAGER_RETAINED_USB_UNMOUNT_PASS_20261120.md)、[#810 永久方案](https://github.com/chrenguo-stack/HomeAssistant/blob/4abebaa61c1db0be41a724c45263e26ac15eb06e/docs/development/N3W_T1_KF168_MANAGER_OTA_IPC_EXPORT_ISOLATION_DESIGN_20261120.md)、[五文件预检与哈希](https://github.com/chrenguo-stack/HomeAssistant/blob/b7f7d2dd70ae00deead70c30f23551fc8c1645e6/docs/development/N3W_T1_KF168_MANAGER_OTA_IPC_MIGRATION_PREFLIGHT_20261120.md)、[最新停点、回退和已消费执行器](https://github.com/chrenguo-stack/HomeAssistant/blob/3532dd9877bdb4454415068ce52c6290bb743bd1/docs/development/N3W_T1_KF168_IPC_MIGRATION_READYNESS_STOP_AND_ROLLBACK_20261120.md)。
- 未归档重要资料：无。T1 连接和认证材料、恢复备份原始字节保留在私有环境；公开归档提供所需的脱敏定位、哈希和重建依据。下一门的执行器修复尚未开始，不能记为未归档实现。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
UNARCHIVED_CRITICAL_RESULT_COUNT=0
SECRET_VALUES_INCLUDED=false
```

新会话启动语：

> 阅读本交接及 §6 的必读资料，fresh rebind `main`、PR #807、#809、#810 和最新 GitHub 归档。只进入 `N3W_T1_KF168_IPC_MIGRATION_EXECUTOR_READINESS_SOURCE_REPAIR`，修复部署／回退就绪屏障并交付离线验证、适用 CI 与精确归档。达到新的只读部署预检入口即停。不得重放已消费授权或将 Phase‑A 记为 PASS。
