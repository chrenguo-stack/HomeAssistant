# N3-W T1 U8 R33 false-STOP → R34 read-only reconciliation
# 新会话交接文档 V1.0 — 2026-11-15

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：继续 N3-W T1 mandatory-USB Home Assistant OTA。R33 已消费一次性授权并把 durable transaction 推进到 U8，但终态校验因 session public fingerprint 被错误当成跨会话 authority 而返回 `STOP_POSTCLAIM`。本次交接在 KF-159 根因证明、R34 只读 successor source/CI 闭合后切换会话；新会话只需执行一次 R34 read-only reconciliation。
- 已完成到：
  - R33 real-T1 执行已结束，`authorization_claimed=true`、`authorization_consumed=true`、`replay_permitted=false`，禁止任何 R33 replay。
  - durable transaction 已为 `U8_RECOVERY_ADMISSION_COMPLETE`，SHA-256 `b483236e9439e3e8bc5d6c3cce51bed6649c3feaecdef09cf8fa66a0afab5a3f`。
  - recovery-content manifest 为 `18698bcded28d0497ae3dcd3363ace68f54a3cbc1c42a1fd5710173a24d900f3`，只读取证已重算一致。
  - 只读取证证明 USB mirror 唯一 mismatch 是 `manifest.public_fingerprint`；filesystem UUID、transaction id、phase、target/predecessor/backup identities、target checksum/size、recovery-content manifest 全部一致。
  - KF-159 根因已归档；R34 strictly-read-only successor 已实现并完成 16/16 CI SUCCESS。
- 当前状态：**可继续**。没有剩余 source/CI blocker。下一步只运行一次 R34 read-only reconciliation；R34 之前不需要再做开发或授权操作。

## 2. 代码与证据

- 仓库／分支／PR：
  - Repository: `chrenguo-stack/HomeAssistant`
  - Branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR state at handoff: OPEN / DRAFT / MERGEABLE / UNMERGED
- 核对时 main／本任务源码：
  - `MAIN=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - `R34_SOURCE_HEAD=1de3b11f0dafa717e3199767e868b9f52ba7c2c3`
  - `R34_SOURCE_CI=16_OF_16_SUCCESS`
  - `R34_EXECUTOR_BLOB=a26ecf36936da9d8d9f2aed9de6ae9cf8c72a403`
  - `R34_MANIFEST_BLOB=4831e46e7e2cf072c8df684b910974d0bcbf9f00`
  - `R34_FOCUSED_TEST_BLOB=870368d2998340fde96bf5fe2e3aeb17bdadec8b`
  - `R34_WORKFLOW_BLOB=75813b24574fa82d30ef97686496ea72ca73deb3`
- 证据入口：
  - R34 executor: https://github.com/chrenguo-stack/HomeAssistant/blob/1de3b11f0dafa717e3199767e868b9f52ba7c2c3/tools/execution_packages/n3w/r7a/u8_post_r33_readonly_reconciliation_r34/executor.py
  - R34 manifest: https://github.com/chrenguo-stack/HomeAssistant/blob/1de3b11f0dafa717e3199767e868b9f52ba7c2c3/tools/execution_packages/n3w/r7a/u8_post_r33_readonly_reconciliation_r34/manifest.json
  - R34 focused tests: https://github.com/chrenguo-stack/HomeAssistant/blob/1de3b11f0dafa717e3199767e868b9f52ba7c2c3/tests/tools/test_n3w_t1_u8_post_r33_readonly_reconciliation_r34.py
  - KF-159: `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` 顶部条目。
  - R34 source/CI archive comment: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6896475506
  - R34 bounded-poll archive comment: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6896480985
  - Final HA target-binding CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43727199876
  - Final Manager A-to-B CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43727199822
- 实际部署/运行版本仍是现有生产基线：Manager `local/greenhouse-manager:fresh-44e7d7472714`，Home Assistant predecessor `local/n3w-homeassistant:2026.10.0-0c73235a`，Broker `local/n3w-mosquitto:2.1.2-3184566d`。R34 不部署任何新产品源码。

## 3. 必须继承的结论

- 已证实：
  - **R33 不可重放。** R33 execution id `r33-live01-20261115T144821Z` 已 claimed + consumed；结果 `STOP_POSTCLAIM`，RC=2，`replay_permitted=false`。
  - **产品 transaction 已 durable 到 U8。** 当前 phase `U8_RECOVERY_ADMISSION_COMPLETE`；transaction 文档合法，recovery-content manifest 可从 transaction 重算完全一致。
  - **R33 是 false-STOP，不是 recovery content 损坏。** 只读取证的 mismatch count=1，唯一项 `manifest.public_fingerprint`。其余 durable mirror fields 全 PASS。
  - `SubprocessPrepareBackend._stable_fingerprint()` 明确将 fingerprint 定义为 session observation，并注明不可作为 cross-session recovery authority；它包含 path/major:minor 等可能跨会话变化的字段。
  - 冻结架构在 U9 前要求的是 same bound USB filesystem UUID + exact recovery content。当前 filesystem UUID 与 durable mirror authority 一致。
  - 最近只读取证：Broker owner active/running、NRestarts=0；services owner failed/failed、MainPID=0、NRestarts=0；predecessor internal image 存在且 exact；target image 不存在。
  - R34 source head `1de3b11...` 已 16/16 CI SUCCESS；R34 不包含 transaction/USB/service mutation，也不进入 U9。
- 待确认：
  - `MANAGER_CONTAINER_STATE=UNKNOWN_FRESH`
  - `HOMEASSISTANT_CONTAINER_STATE=UNKNOWN_FRESH`
  - R34 会重新验证 exact container identities、Manager/HA quiesced、Broker continuity、USB mirror file SHA256、U8 transaction SHA 和 R33 failure ledger；无需额外手工基线。
- 已排除：
  - 重新运行 R33：**禁止**，因为 consumed/no-replay。
  - 为“修一致”而重写 USB public fingerprint：**禁止**；session fingerprint 不是 durable cross-session authority。
  - U9 / destructive cutover / predecessor delete / target load / service restart：**本交接范围外且未授权**。
  - Board access / merge：**未授权**。

## 4. 执行范围与授权

- 可继续：
  - 用户在本会话明确要求“新对话从只需运行一次 R34 read-only reconciliation 开始”。因此下一会话可以直接执行 **一次** R34 real-T1 read-only reconciliation。
  - 可进行 fresh repository rebind、读取 R34 exact package、建立私有 SSH epoch、执行 R34 只读取证、保存 private raw evidence、把 public-safe closure 归档到 GitHub。
- 暂停边界：
  - R34 PASS 后停止在 U9 前；不得自动 claim U9、不得删除 predecessor、不得 load target、不得启动/重启业务服务、不得 merge PR #807。
  - R34 FAIL 时停止并按失败字段做只读/源码复核；不得重跑 R33，不得用 USB 写入“修复”fingerprint。
- 授权状态：
  - R33 authorization：`CLAIMED=true / CONSUMED=true / REPLAY_PERMITTED=false / RESULT=STOP_POSTCLAIM`；永久不可复用。
  - R34：只读检查，不使用 live-mutation authorization；用户已明确允许下一会话直接执行一次。
  - U9 authorization：**无**。

## 5. 下一步

- 行动：
  1. fresh rebind `main`、PR #807 和 exact R34 source head `1de3b11f0dafa717e3199767e868b9f52ba7c2c3`；确认 R34 package blobs 未漂移且 source CI 仍为 16/16 SUCCESS。
  2. 使用现有**私有** T1 SSH/known-hosts 绑定运行一次：
     `tools/execution_packages/n3w/r7a/u8_post_r33_readonly_reconciliation_r34/executor.py`
     并把 `--expected-package-commit` 固定为 `1de3b11f0dafa717e3199767e868b9f52ba7c2c3`。公开 GitHub 不写私有地址、known-hosts 路径或 host key。
  3. 保存 private evidence；把 public-safe R34 closure、current-state/index 和 KF-159 status 对齐到 GitHub。
- 完成条件：
  - `status=U8_R34_POST_R33_READONLY_RECONCILIATION_PASS`
  - `read_only=true`
  - `r33_false_stop_confirmed=true`
  - `u8_durable=true`
  - `usb_durable_mirror_exact=true`
  - `same_bound_usb_filesystem_uuid=true`
  - `session_public_fingerprint_non_authoritative=true`
  - `authorization_claimed=true` / `authorization_consumed=true` / `replay_permitted=false` 仅表示继承的 R33 ledger；
  - `product_u9_authorization_claimed=false`
  - `product_u9_authorization_consumed=false`
  - `destructive_cutover=false`
  - `target_image_load=false`
  - `predecessor_image_delete=false`
  - `service_mutation=false`
  - `u9_plus=false`
  - predecessor image exact-preserved，target image absent，Manager/HA quiesced，Broker continuity PASS。
- 失败／停点：
  - 任一 R34 exact hash、ledger、transaction、durable mirror、runtime 或 image boundary 不符：STOP。
  - R34 不做修复写入，不改变 transaction/USB/service。
  - PASS 后可把 U8 标为 `CLOSED_PASS_RECONCILED`，但仍停在 U9 前；U9 需要新的独立设计/授权判断。

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/local-ai-task-splitting-rules.md`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
  - [工作上下文的读取规则](../N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set)
- 任务资料：
  - `docs/development/N3W_CURRENT_STATE.md`：只读顶部 latest authority。
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`：只读顶部 R33/R34 条目。
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：只读顶部 **KF-159**，按需补读 KF-158。
  - `tools/execution_packages/n3w/r7a/u8_post_r33_readonly_reconciliation_r34/manifest.json`：R34 exact contract。
  - `tools/execution_packages/n3w/r7a/u8_post_r33_readonly_reconciliation_r34/executor.py`：R34 执行器。
  - `docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_DESIGN_DELTA_20261106.md`：按需复核 U7→U8→U9 frozen architecture。
- 已归档：
  - R34 source/CI closure、KF-159、current-state/index 均已进入 PR #807 分支。
  - R34 source authority 固定为 `1de3b11f0dafa717e3199767e868b9f52ba7c2c3`。
- 未归档重要资料：
  - 无 public-safe 关键知识缺口。
  - R33 与只读诊断的 raw evidence 保留在用户私有 evidence root，**不上传 GitHub**；必要事实已用 sanitized hashes/status/KF-159 归档。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
PRIVATE_RAW_EVIDENCE_PRESENT=true
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_U8_POST_R33_READONLY_RECONCILIATION_R34_20261115_01
STOP_BOUNDARY=AFTER_R34_READONLY_RECONCILIATION_BEFORE_U9
```

新会话启动语：阅读本交接和适用仓库指令，按必读定位恢复任务；fresh rebind exact R34 source authority 后，直接运行一次 R34 real-T1 read-only reconciliation，归档结果，并在 U9 前停止。
