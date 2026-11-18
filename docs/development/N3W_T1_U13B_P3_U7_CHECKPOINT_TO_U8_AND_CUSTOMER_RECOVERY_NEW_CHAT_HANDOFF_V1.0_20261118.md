# N3-W T1 P3 U7 停点 → U8 与客户升级恢复验收
# 新会话交接文档 V1.0 — 2026-11-18

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- **目标与交接原因。** 接续本笔 P3 恢复材料验收，并在继续切换前把故障恢复纳入客户交付验收。本对话收口归档，实机步骤转入新对话。
- **最后实机停点。** `U7_HA_QUIESCED_DATA_BACKUP_PREPARING`。事务 SHA-256 为 `2f45f6eee5fa59d0dafe53cedc23c11d62de35e949fb645ea8fd74b3d8d861a2`。最后一次只读补验确认主机及 USB 一致，Home Assistant 和温室管理容器已停止，MQTT Broker 由原容器运行。 [U7 实机停点](./N3W_T1_U13B_P3_U7_READONLY_PREFLIGHT_20261118.md#u7-实机停点确认)
- **当前状态。** U8 候选 CI 已通过，可接续源码复核和只读预检。U8 写入待候选专属授权。按已讨论顺序，当前 T1 进入 U9 前先在备用 T1 证明切换前恢复。

## 2. 代码与证据

| 绑定项 | 已核对值 |
| --- | --- |
| 仓库及 PR | `chrenguo-stack/HomeAssistant`，[PR #807](https://github.com/chrenguo-stack/HomeAssistant/pull/807)，OPEN / DRAFT / UNMERGED |
| PR head 分支 | `fix/kf147-u3-recovery-and-error-visibility-20261110` |
| PR base | `fix/kf147-post-destructive-stop-readonly-forensic-20261110`，`ab277001dc9b31dcccb4d36b1507cec5f26d5a1d` |
| 默认 main 和 V1.4 模板来源 | `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`，[模板](https://github.com/chrenguo-stack/HomeAssistant/blob/3e7faf258d670c9eaf3be6ede9bbb02df2ac009d/docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md) |
| 现场与计划对齐提交 | `f174429f766310cdd344a3f3646026a9f639e09c` |
| U8 执行候选 | `e78b80642f7e71a88ae086f3d7b6c54c34defb99` |
| P3 冻结产品源码 | `cddadc5bff1a00d4392de33680a5b0ad0acace1e` |
| U7 授权提交 | `cb7f0fb5757b2d744dd272895e4923242ead2191`，已消费 |
| U7 只读补验提交 | `f0fbe73c6944388cd8420308eb08733872274548` |
| U7 只读补验回执 SHA-256 | `27739cf29a883c4ee58d8cc6094099f4fd4e36a056dd94acfeb28d29bb203e73` |
| P3 目标归档 SHA-256 | `be30c4778bf537258d9e3825524c79532f20e8eb7a82136f560110d8f44b418d` |
| 旧镜像归档 SHA-256 | `31108a725e6b6530c68834218d9e41579055d7fe2718b3f42902b71237dc8e5f` |
| 加密数据备份 SHA-256 | `b6f7ad3803c1ae954d2d946562b5ae1db8725786e4c457db8a1deff7b10623e2`，2,090,112 字节 |

U8 三项检查均在精确候选提交通过。交接和状态对齐提交只归档文档，执行和授权仍绑定 U8 候选。 [P3 源码 CI](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44302218987) · [Core Stack CI](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44302219133) · [仓库安全 CI](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44302218652)

当前现场仍以已归档的旧镜像 `local/n3w-homeassistant:2026.10.4-5881590f` 作为 P3 恢复基线。P3 目标为同版本独立镜像 `local/n3w-homeassistant:2026.10.4-u13b-acceptance-v1`。当前 Core Stack 仓库权威与 P3 现场单独记录。 [当前状态首节](./N3W_CURRENT_STATE.md)

## 3. 必须继承的结论

- **已证实。** U7 正式执行在备份完成后的外层停机检查返回 `STOP_POSTCLAIM`。独立只读补验以 `P3_U7_POSTCLAIM_EVIDENCE_VERIFIED / EXIT_CODE=0` 确认备份已落盘、通过完整性及认证验证并与静止源数据一致。原失败记录保留，原执行成功回执不存在。KF-158 的误判是执行器只接受 `inactive`，实机实际为 `failed/exit-code`，退出码 130，主进程为 0，两个应用容器确已停止。 [U7 执行和补验](./N3W_T1_U13B_P3_U7_READONLY_PREFLIGHT_20261118.md)
- **待现查。** 新对话的 USB 挂载、U7 当前事务和服务状态、备用 T1 基线均为 `UNKNOWN_FRESH`。用 U8 只读预检作最小复核。KF-159 已验证设备枚举会话指纹可能改变，跨会话按绑定文件系统 UUID、准确归档和事务记录核对。 [故障防回归记录](./KNOWN_FAILURES_AND_REGRESSION_GUARDS.md)
- **交付缺口。** U8 通过只证明恢复材料齐备。用户版仍需在实际产品入口证明切换前可以自动恢复旧服务、切换后可回滚，断电后可续接。5 分钟和 15 分钟是试验目标，客户承诺以实测为准。 [恢复验收计划](./N3W_T1_CUSTOMER_OTA_FAILURE_RECOVERY_ACCEPTANCE_PLAN_20261118.md)

## 4. 执行范围与授权

- **可继续。** 新对话先核对 GitHub、精确候选及私有 SSH 绑定，从 Mac 对当前 T1 执行 U8 只读预检。可以并行准备备用 T1 的切换前恢复设计、源码验证、模拟和归档。
- **暂停边界。** U8 写入待绑定 `e78b8064` 的独立一次性授权。备用 T1 实机故障注入和服务恢复需单独明确目标与范围。当前 T1 的 U9+、镜像删除/加载、服务启动或重启，以及 PR 合并均未获本次交接授权。
- **授权状态。** U7 已认领、已消费、禁止重放。U8 授权编号 `N3W_T1_U13B_P3_U8_RECOVERY_ADMISSION_20261118_01`，当前无授予、无执行。获得授权后，以精确候选为父提交，在独立执行引用上只新增 `recovery_admission_grant.json`，绑定候选、U7 事务、补验回执、目标归档、有效期和 U8 上限。保留 PR 归档历史。U9 另行决定并授权。

## 5. 下一步

1. 核对默认 main、PR #807 的 base/head、精确 U8 候选和其三项 CI。核对私有 T1 目标及主机密钥后，以精确候选和冻结产品源码运行 `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/recovery_admission.py`。先 `--mode source-check`，再 `--mode preflight`，均传候选的 `--expected-commit`。预期 `P3_U8_READONLY_PREFLIGHT_PASS / EXIT_CODE=0`，事务仍在 U7。保留 JSON、回执 SHA-256 和退出码。
2. 取得精确授权且只读条件通过后，使用授权提交运行一次 `--mode execute`。预期 `P3_U8_RECOVERY_ADMISSION_PASS / EXIT_CODE=0`，主机和 USB 达到 `U8_RECOVERY_ADMISSION_COMPLETE`，恢复内容清单摘要一致，`u9_plus=false`。核对服务状态，归档后停在 U8。
3. 当前 T1 做 U9 前，先在备用 T1 实测 U7 最终检查报错、进程中断及主机和 USB 分步落盘故障。判定条件为安全续接或自动恢复旧版，页面可访问、历史可读、新监测数据恢复更新。之后推进 U9–U11，并以最终交付版本从客户入口验收正常升级、切换后回滚、掉电续接和原盘拔插。 [验收顺序](./N3W_T1_CUSTOMER_OTA_FAILURE_RECOVERY_ACCEPTANCE_PLAN_20261118.md#下一阶段顺序)

如果预检失败，按原因只读定位并保持当前现场。如果执行断线、超时或返回 `STOP_POSTCLAIM`，从同一执行包运行 `--mode status`，核对授权账本、主机和 USB 的实际阶段。已消费授权不重试，主机与 USB 分裂时先取证。原始回执仅留在私有 Mac，公开归档记录摘要和结论。

## 6. 必读定位与归档

- 仓库规则：根目录 `AGENTS.md` 和其中引用的协作与归档规则。 [工作上下文最小读取范围](./N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set)
- 任务资料：`N3W_CURRENT_STATE.md` 和 `N3W_CURRENT_STATE_INDEX.md` 首节、U7 实机停点确认、U8 候选说明、客户恢复验收计划。故障清单只读 KF-158 与 KF-159 相关条目，掉电合同沿用现有 P5 设计第 15 节。 [U8 候选说明](./N3W_T1_U13B_P3_U8_RECOVERY_ADMISSION_20261118.md)
- 已归档：U7 原执行和独立补验、KF-158 防回归、U8 候选与测试、恢复设计和顺序、现场状态及索引。 [现场与计划对齐提交](https://github.com/chrenguo-stack/HomeAssistant/commit/f174429f766310cdd344a3f3646026a9f639e09c)
- 未归档重要资料：无。原始终端回执在私有 Mac，已用 SHA-256 绑定。恢复后的本地旧草稿保留为临时材料，其中有已被 GitHub 候选修正的导入顺序，后续使用 GitHub 精确提交。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
LAST_VERIFIED_LIVE_STAGE=U7
NEXT_ONE_GATE=P3_U8_FRESH_READONLY_PREFLIGHT
U8_LIVE_AUTHORIZATION_GRANTED=false
```

新会话启动语：阅读本交接与适用仓库指令，按 V1.4 最小读取范围核对 GitHub 和私有 T1 绑定。从本笔已证实的 U7 事务执行 U8 只读预检，按文中的授权和验收顺序继续。当前 T1 进入 U9 前先在备用 T1 验证切换前恢复。原 U7 授权已消费。
