# N3-W 新会话交接：T1 U13B P3 实机恢复至 U4，续接 U5

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 交接目标为续接同一笔 U13B P3 验收事务的 U5 安装意图。本轮于 2026-11-18 收口 U1→U4 恢复并归档。
- 实机最后一步为 `U4_RECOVERY_PASS / EXIT_CODE=0`。事务停在 `U4_READY_TO_INSTALL / ACTIVE`，新 USB 文件系统 UUID 和验收镜像已通过校验，服务维持恢复前的运行基线。
- 用户指定在新对话进入 U5 阶段。新对话先核对源码与 U4 现场，再开展针对当前 P3 事务的 U5 只读预检。

## 2. 代码与证据

- 仓库为 `chrenguo-stack/HomeAssistant`，分支为 `fix/kf147-u3-recovery-and-error-visibility-20261110`，[PR #807](https://github.com/chrenguo-stack/HomeAssistant/pull/807) 核对时为 open、draft、unmerged。
- 默认 `main` 为 `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`。PR base 为 `fix/kf147-post-destructive-stop-readonly-forensic-20261110` @ `ab277001dc9b31dcccb4d36b1507cec5f26d5a1d`。
- 本交接提交的父提交为 U4 结果归档 `bb3aba33a519fc9599cc7562fb98644a83835c16`。本交接提交只更新文档。新对话以远端 PR head 和实际文件差异重新确认来源。
- 原 P3 实机执行源码为 `cddadc5bff1a00d4392de33680a5b0ad0acace1e`。U1→U4 恢复执行源码为 `d54e2794a590208c7a9f57ac00bb6ee2017a94ff`，入口为 `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/executor.py`。[恢复源码 CI](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44233715143) 通过。
- 当前 U4 状态文件 SHA-256 为 `00167d489d785af6a458cd09826b9293dc29ec6c85b02ac75772017633d6f154`。[实机回执](https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6968950587)。
- 验收目标为 `local/n3w-homeassistant:2026.10.4-u13b-acceptance-v1`，归档字节数为 `835299595`，SHA-256 为 `be30c4778bf537258d9e3825524c79532f20e8eb7a82136f560110d8f44b418d`。产物源码 `d8446485557eb8e02bdb1460e84fe23984047f5b`，artifact ID `14381710716`。[冻结产物 run](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44199389702)。
- P3 HA 前任运行镜像由原执行 manifest 绑定为 `local/n3w-homeassistant:2026.10.4-5881590f`。当前生产定义参考 `infra/n3w-t1/production/t1-core-stack-current.json`，其仓库产品源码为 `5b32e1ae82104a42f9e4e6907fe44d9172e87615`。新对话按 P3 事务范围重新核对实际运行镜像及适用的回退依据。
- U4 归档提交的 Core Stack 和 updater CI 曾因 `state_authority_link_missing` 失败，原因是两个状态文档首段缺少原有 Core Stack 字段。本交接补回字段。[Core Stack 失败 run](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44241328591) · [updater 失败 run](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44241328635)。在新对话核对交接提交实际触发的 [PR checks](https://github.com/chrenguo-stack/HomeAssistant/pull/807/checks)。
- 本地 Core Stack authority checker 已通过，Core Stack 与 P3 恢复相关测试共 53 项通过。实机 U4 回执继续以恢复执行提交和上面的证据链接为准。

## 3. 必须继承的结论

- 原 P3 执行在 `U1_PREPARE_REQUESTED` 领取授权后停止。首次恢复又因 USB 独占读取返回 `EBUSY` 在领取恢复授权前停止。T1 取证定位到 Manager 容器挂载命名空间内残留的 U13A 只读挂载。按用户单独授权精确卸载后，整盘和分区独占读取均通过，签名为空，服务和 U1 状态未变化。随后独立恢复已真实通过 U4。[原 P3 停止记录](https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6968167263) · [卸载和 U4 回执](https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6968950587)。
- 原 P3 格式化步骤中失败的具体子命令仍未确定。KF-166 保持 OPEN。已定位的残留挂载解释了恢复预检的独占失败。
- U4 回执只证明恢复完成时的状态。当前 T1 的 USB UUID、挂载身份和选项、HA/Manager/Broker 容器基线、OTA daemon、实际部署源码与 IPC 仍需 fresh read-only rebind。应从当前事务和文件系统身份解析 USB，设备节点只作现场定位。
- 历史 R14 只读包和 R18 INSTALL 包均绑定此前的事务摘要、USB UUID 和验收归档。它们可以用于复核检查项和停止条件。当前 P3 必须重新绑定 U4 摘要、目标归档和实际部署的执行路径。

## 4. 执行范围与授权

- 本轮只归档和交接，现场停在 `U4_READY_TO_INSTALL`。新对话可完成仓库和执行包只读核对、检查项设计、源码复核、模拟测试与归档。在当前 P3 的只读入口核对通过后，先以只读方式复查实机。
- 原 P3 clean OTA 授权 `N3W_T1_U13B_P3_NEW_CLEAN_OTA_20261117_01` 已消费。恢复授权 `N3W_T1_U13B_P3_U1_TO_U4_USB_RECOVERY_20261118_01` 已消费。历史 Manager 挂载的单点卸载已结束。P3 原执行绑定的 U9 授权不迁移到当前续接。
- 用户本次指定在新对话推进 U5。当前 P3 对应的 U4→U5 实机 INSTALL 候选尚未绑定，新的 INSTALL 一次性授权尚未认领或消费。必须以当前 P3 的实机只读证据和通过验证的候选为依据，并在生产写入前确认该动作的适用授权。
- U5 的写入范围限于准确的安装意图和按适用合同进行的 Host/USB 事务元数据同步。USB 格式化、替换归档、服务重启、镜像切换、U6+、板卡和合并均在本次交接范围之外。不得重放旧 P3 或 U1→U4 恢复。

## 5. 下一步

1. 重新核对默认 `main`、PR #807 base、远端 head、当前状态首段和 fresh CI。用文件差异区分执行源码和文档变化。
2. 校验现有预检入口和 manifest 是否适配本笔 P3 U4。若沿用旧包的检查结构，先补齐本笔事务、目标与运行依赖绑定，再做只读模拟和实机复核。
3. 只读核对持久 U4 状态及摘要、USB 真实文件系统身份与 mountinfo、Host/USB 元数据一致性、归档字节数和 SHA-256、当前 HA/Manager/Broker 及 OTA daemon、部署源码和 IPC 只读响应。该步的完成条件是实机预检通过并归档，事务保持 U4。
4. 证据通过后，收敛只到 U5 的 INSTALL-intent 候选，验证实际部署的 IPC 能力、失败停点与授权账本。绑定适用的一次性授权后，以 Host/USB 同时到达 `U5_INSTALL_REQUESTED_REVALIDATING` 为实机完成条件，到 U5 即停并归档。
5. 源码、实机状态、挂载、证据或授权有漂移时停止受影响动作。INSTALL 前失败保留 U4；领取授权后失败先只读确认账本与 Host/USB 状态。SSH 断线时先查持久回执。

## 6. 必读定位与归档

- 仓库规则为根目录 `AGENTS.md` 与其引用的规范。按 [工作上下文第 12 节](N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set) 取最小读取集，模板以 [正式 V1.4](templates/NEW_CHAT_HANDOFF_TEMPLATE.md) 为准。
- 优先读取 [当前状态](N3W_CURRENT_STATE.md) 首段、[状态索引](N3W_CURRENT_STATE_INDEX.md) 首段及 [KF-166](KNOWN_FAILURES_AND_REGRESSION_GUARDS.md)。查看 `tools/execution_packages/n3w/r7a/u13b_p3_live_to_u11/manifest.json` 的候选绑定与历史执行边界，以及 `u13b_p3_u1_u4_recovery/executor.py` 的 U4 写后校验。
- 设计 U5 时按需查阅 `tools/execution_packages/n3w/r7a/kf147_official_u5_preflight_successor/` 和 `tools/execution_packages/n3w/r7a/kf152_r18_u4_to_u5_install_intent_successor/`。检查其 manifest 中的旧事务值和授权，再提取可复用的合同。
- 已归档 [U4 状态提交](https://github.com/chrenguo-stack/HomeAssistant/commit/bb3aba33a519fc9599cc7562fb98644a83835c16) 与 [实机回执](https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6968950587)。Mac 私有执行目录含 `evidence/recovery-result.json`。实际 SSH 连接参数、私有路径和原始设备身份沿用私有上下文。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接和适用仓库指令，重新核对默认 main、PR #807 及其 base/head、当前状态和 CI。从本笔 P3 的 U4 事务 `00167d489d785af6a458cd09826b9293dc29ec6c85b02ac75772017633d6f154` 开始，先核对并执行适配当前 P3 的 U5 只读预检。预检通过后准备并验证 U4→U5 INSTALL-intent 候选，按适用授权执行，实机到 U5 即停并归档。
