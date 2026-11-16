# N3-W T1 U9 R36 CLOSED_PASS → U10 新会话交接 V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：本轮已完成 Home Assistant mandatory-USB OTA 的 U9 live-authorization claim，并完成 R36 实机、GitHub 归档和 closure CI。当前对话在 U10 前结束；新对话从 U10 阶段恢复。
- 已完成到：R36 real-T1 `U8_RECOVERY_ADMISSION_COMPLETE -> U9_LIVE_AUTHORIZATION_CLAIMED` CLOSED_PASS；U9 host transaction 与 USB mirror 均 exact；KF-161 物理关闭；U9 closure archive CI 16/16 SUCCESS。
- 当前状态：`U9_STATUS=CLOSED_PASS`。可进入 U10 的设计复核、源码准备、模拟/测试和只读预检准备；**real-T1 U10 destructive predecessor-capacity release 尚未授权**。

```text
HANDOFF_SOURCE_AUTHORITY=e841ede79abe9ca4b014adc9d2729c61a9cfbda1
R36_GRANT_HEAD=f78dc7da7998ce2d3d275dc05e09d173d84f200b
R36_EXECUTION_ID=r36-live01-20261116T003710Z
R36_RESULT=U9_R36_LIVE_AUTHORIZATION_CLAIM_PASS
R36_RC=0
LIVE_TRANSACTION_PHASE=U9_LIVE_AUTHORIZATION_CLAIMED
LIVE_TRANSACTION_SHA256=69f5a8c2190dac0a12df3aac1bdc9c9f3b02050e9541e7a202907204d280f7c3
U9_STATUS=CLOSED_PASS
STOP_BOUNDARY=BEFORE_U10_REAL_T1_DESTRUCTIVE_MUTATION
```

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR #807: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR 状态：OPEN / DRAFT / UNMERGED
  - PR base: `fix/kf147-post-destructive-stop-readonly-forensic-20261110`
- 核对时 main／本任务源码：
  - main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - R36 exact grant/execution authority: `f78dc7da7998ce2d3d275dc05e09d173d84f200b`
  - U9 closure archive authority: `e841ede79abe9ca4b014adc9d2729c61a9cfbda1`
  - R36 executor blob: `528fa2c7f6b46cd1fafa046e19db1719b70b7fd4`
  - R36 granted manifest blob: `42a4c322f9b1ca84d019a74c1f54d2d7d5ae199e`
  - R36 focused-test blob: `21b6230447a3bdceddb253c63f643c7d0bfe8405`
- 证据入口：
  - U9 closure archive: https://github.com/chrenguo-stack/HomeAssistant/commit/e841ede79abe9ca4b014adc9d2729c61a9cfbda1
  - R36 grant authority: https://github.com/chrenguo-stack/HomeAssistant/commit/f78dc7da7998ce2d3d275dc05e09d173d84f200b
  - HA target-binding closure CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43781713508
  - Manager A-to-B closure CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43781713556
  - Core Stack authority closure CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43781713487
  - fast source/exact closure CI: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43781713555
  - closure archive CI: 16/16 SUCCESS。
  - 私有 raw evidence 存在于用户本地私有 evidence root；公开交接不记录其真实路径或原始内容。

## 3. 必须继承的结论

- 已证实：
  - R36 real-T1 返回 `RC=0`，状态 `U9_R36_LIVE_AUTHORIZATION_CLAIM_PASS`。
  - R36 authorization 与 product U9 authorization 均已 claimed + consumed；`R36_REPLAY_PERMITTED=false`。
  - durable transaction 已从 U8 精确进入 `U9_LIVE_AUTHORIZATION_CLAIMED`，SHA-256 为 `69f5a8c2190dac0a12df3aac1bdc9c9f3b02050e9541e7a202907204d280f7c3`。
  - recovery-content manifest 仍为 `18698bcded28d0497ae3dcd3363ace68f54a3cbc1c42a1fd5710173a24d900f3`；USB mirror at U9 exact；bound filesystem UUID continuity PASS。
  - predecessor internal image 仍存在；target internal image 仍不存在。
  - Broker running / restart_count=0；Manager 与 Home Assistant exited / restart_count=0；host 与 broker owner active/running；services owner failed/quiesced。
  - `u10_destructive_successor_eligible=true`，但 eligibility 不是 authorization。
  - KF-161 已由 R36 物理验证 CLOSED_PASS；R35 与 R36 都永久 no-replay。
  - R36 执行后的 shell session-save warning 出现在 executor RC=0、SSH cleanup 完成之后，不改变 R36 PASS 结论。
- 待确认：
  - 新会话开始时 fresh rebind main、PR #807/current head、CURRENT_STATE、INDEX、KF-161 和冻结 U10 设计，确认无 source/authority drift。
  - U10 尚无独立 execution package、grant、real-T1 baseline 或 live authorization；这些必须在新会话中建立。
- 已排除：
  - 不重放 R35 或 R36。
  - U10 不等于 target load；冻结阶段定义是 `U10=INTERNAL_PREDECESSOR_CAPACITY_RELEASED`，`U11=TARGET_INSTALLED_STARTED`。
  - 不使用 `docker system prune`、`docker image prune -a`、wildcard 删除或 Manager/Broker 无关删除。
  - 不把 U10 eligibility、用户要求“新对话进入 U10”、源码/CI PASS 解释成 real-T1 destructive authorization。

## 4. 执行范围与授权

- 可继续：
  - fresh read-only rebind；
  - 阅读冻结 U10 设计与当前产品源码；
  - 独立源码复核；
  - 设计并实现 U10 successor package；
  - focused test、模拟测试、GitHub CI、public-safe 归档；
  - 设计 U10 read-only preflight，并在不触及 real-T1 写入的范围内准备执行合同。
- 暂停边界：
  - **任何 real-T1 U10 phase advancement、predecessor runtime/image 删除或其他 destructive mutation 前必须停止并获得新的明确授权。**
  - U11 target load/start、服务恢复/启动、U12 acceptance、U13 commit/rollback 不属于当前交接授权。
  - board access、merge 仍未授权。
- 授权状态：
  - R35：claimed=true / consumed=true / replay=false。
  - R36：claimed=true / consumed=true / replay=false。
  - U10 real-T1 destructive execution：**无授权**。
  - 用户本轮仅指定“在新对话中进入 U10”；这授权阶段切换和开发/只读准备，不自动授予 destructive live execution。

## 5. 下一步

- 行动：
  1. 按 Minimum New Chat Read Set 读取本交接、工作上下文、CURRENT_STATE、INDEX、KNOWN_FAILURES。
  2. fresh rebind repository main、PR #807/current head 与 U9 closure authority。
  3. 读取 `docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_DESIGN_DELTA_20261106.md` 的 U10/INSTALL 合同。
  4. 独立复核当前产品源码中 U9→U10 transition、`destructive_cutover_allowed()`、transaction/USB durable ordering 和 predecessor 精确删除边界。
  5. 设计新的 U10 successor gate：从 exact U9 起步，只允许释放 exact predecessor HA runtime/image objects required for capacity；不得加载 target，不得进入 U11。
  6. 增加 focused regression、模拟/CI 与 public-safe authority 归档。
  7. source/CI 完成后，若下一步需要 real-T1 U10 mutation，停在授权边界并申请新的明确授权。
- 完成条件：
  - U10 source contract 与 frozen architecture 一致；
  - exact U9 authority、same USB、recovery assets、backup、transaction、runtime/predecessor identity 均有 fail-closed guard；
  - destructive deletion allowlist 精确且无 wildcard/prune；
  - durable host transaction 与 USB phase 的顺序/失败处理可证明；
  - focused tests + required CI 通过；
  - public-safe source/test/docs/KF（如新增故障）均归档；
  - real-T1 U10 执行前具有新的明确 one-shot authorization。
- 失败／停点：
  - source/authority drift、U9 transaction/USB mismatch、predecessor identity 不精确、recovery/backup 不可验证、容量/运行时状态不满足、或删除范围不能精确限定时 fail closed。
  - 任何 post-claim/destructive failure 不得自动 replay；先读 durable ledger 并建立 successor/reconciliation gate。
  - 未获得 U10 live authorization 时，不得进入真实 predecessor 删除。

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/local-ai-task-splitting-rules.md`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set`
- 任务资料：
  - 本交接文件；
  - `docs/development/N3W_CURRENT_STATE.md`：当前 U9 authority 与 stop boundary；
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`：最近阶段索引；
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：KF-159/KF-160/KF-161 与 no-replay guards；
  - `docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_DESIGN_DELTA_20261106.md`：冻结 U10/INSTALL state machine 与 destructive contract；
  - `tools/n3w_t1_core_updater_ha_usb.py`、`tools/n3w_t1_core_updater_ha_usb_state.py`：U9/U10 product transition authority；
  - `tools/execution_packages/n3w/r7a/u9_live_authorization_r36_successor/`：R36 exact predecessor execution package，**只读参考，不得重放**。
- 已归档：
  - U9 closure archive：`e841ede79abe9ca4b014adc9d2729c61a9cfbda1`
  - KF-161 closure：已在 `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` 持久化。
  - V1.4 template blob：`885fd63131e80936e5e1fe907378be08a0060f12`
- 未归档重要资料：
  - R36 raw execution evidence 保留于用户本地私有 evidence root；由于属于 private raw evidence 不上传 GitHub。公开可恢复事实、hash、phase、CI 与 runtime summary 已归档。
  - 其余 continuation-critical artifact：无。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
PRIVATE_RAW_EVIDENCE_PRESENT=true
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
UNARCHIVED_CRITICAL_RESULT_COUNT=0
```

新会话启动语：

> 阅读 `docs/development/N3W_T1_U9_R36_CLOSED_PASS_TO_U10_NEW_CHAT_HANDOFF_V1.0_20261116.md`，并按 `N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set` 恢复“温室环境监测系统（ESP32-C6）”N3-W。fresh rebind main、PR #807/current head、CURRENT_STATE、INDEX、KNOWN_FAILURES 和 U9 closure authority。U9 已 CLOSED_PASS；R35/R36 永久 no-replay。进入 U10 阶段，先复核冻结 U10 设计和现有产品源码，准备 U9→U10 source/read-only gate。U10 real-T1 predecessor-capacity release 属 destructive mutation，当前未授权；在任何真实 U10 写入前停止并申请新的明确授权。不得提前进入 U11 target load/start。
