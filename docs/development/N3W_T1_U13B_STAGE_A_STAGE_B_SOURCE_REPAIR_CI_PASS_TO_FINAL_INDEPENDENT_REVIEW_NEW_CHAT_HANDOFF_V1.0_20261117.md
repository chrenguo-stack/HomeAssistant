# N3-W T1 U13B Stage A/B Source Repair CI PASS → Final Independent Review New Chat Handoff V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：U13B Stage A / Stage B 曾被描述为已完成，但后续独立复核发现真实正确性与 fail-closed 缺口。本轮已完成对应 source repair 并取得 exact-head 16/16 CI SUCCESS。用户要求切换新会话，并要求新会话**先重新独立复核 Stage A / Stage B，不得盲信本轮修复结论；确认无问题后才向前推进**。
- 已完成到：exact source-repair head `6475c06e831cd597d6680502b41ea6fde6642837`；16/16 workflow SUCCESS。修复覆盖 generic U13B transition bypass、rollback branch phase semantics、exact predecessor runtime identity、HA restart-loop guard、Broker owner guard、backup verify read-only semantics，以及 rollback origin / interruption regression coverage。
- 当前状态：`SOURCE_REPAIR_CI_CLOSED_PASS / FINAL_INDEPENDENT_REVIEW_REQUIRED`。Stage A / Stage B 暂不标最终 CLOSED_PASS；Stage C 未开始。

## 2. 代码与证据

- 仓库／分支／PR：`chrenguo-stack/HomeAssistant`；分支 `fix/kf147-u3-recovery-and-error-visibility-20261110`；PR #807，`OPEN / DRAFT / MERGEABLE / UNMERGED`。
- 核对时 main／本任务源码：
  - default main：`3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - PR base：`ab277001dc9b31dcccb4d36b1507cec5f26d5a1d`
  - source-repair authority：`6475c06e831cd597d6680502b41ea6fde6642837`
  - repair commits：`0a97aea20b4ec542940e29bd470ab228784eab04` → `921102ba444e655ebd6c4cbee2233ecbae65aab6` → `6475c06e831cd597d6680502b41ea6fde6642837`
- 证据入口：
  - Stage A/B design：`docs/development/N3W_T1_U13B_AUTOMATIC_ROLLBACK_SOURCE_DESIGN_V1_20261117.md`
  - state machine：`tools/n3w_t1_core_updater_ha_usb_state.py`
  - rollback domain helpers：`tools/n3w_t1_core_updater_ha_usb.py`
  - command-free controller：`tools/n3w_t1_core_updater_ha_u13b.py`
  - production runtime/media adapter：`tools/n3w_t1_core_updater_ha_u13b_host.py`
  - protected HA backup/restore：`tools/n3w_t1_core_updater_ha_backup.py`
  - regression tests：`tests/tools/test_n3w_t1_core_updater_ha_usb_r2.py`, `tests/tools/test_n3w_t1_u13b_controller.py`, `tests/tools/test_n3w_t1_u13b_host.py`, `tests/tools/test_n3w_t1_core_updater_ha_backup_u7.py`
  - CI：exact head `6475c06e...` = 16/16 SUCCESS；HA target-binding run `44011716167` SUCCESS；Manager A-to-B run `44011716095` SUCCESS。
  - PR checkpoint comment：`6937475479` records the repair-pending state before final CI closure.

## 3. 必须继承的结论

- 已证实：
  - U13A real-T1 success remains terminal at `U13A_COMMITTED`; prior U13A authorization is claimed + consumed + no-replay. This source work did not alter live T1 state.
  - Earlier Stage A/Stage B closure claims were insufficient and must not be treated as authority.
  - Generic `transition()` now rejects every U13B edge; matching forged rollback evidence passed through generic transition is not accepted.
  - Internal rollback progression has rollback-edge exact update-key contracts.
  - U13B prerequisite semantics no longer rely on treating rollback subphases as linearly later than U12/U13A.
  - Stage B predecessor runtime authority now requires durable `current_image_identity.runtime_image_id`, exact HA runtime image ID, HA `RestartCount==0`, active Broker owner, exact Manager/Broker peers and production config mount.
  - Backup verification requires an already-existing private recovery directory; missing recovery backup directory fails without creating it.
  - Tests exercise rollback entry from U9/U10/U11/U12 and interruption/resume at cleanup, predecessor image, data quiesce, data restore, predecessor runtime and terminal health.
  - Exact source head `6475c06e...` completed 16/16 CI SUCCESS.
- 待确认：
  - 新会话必须重新独立检查 Stage A / Stage B design + source + tests，重点寻找仍可能产生 false `ROLLED_BACK`、错误 authority、rollback replay、recovery-media mutation 或 runtime-health false PASS 的路径。
  - USB-ahead / host-behind durable split-write reconciliation remains unresolved and is intentionally outside Stage A/B source repair. It is the next Stage C problem only after review PASS.
  - Stage A / Stage B final closure status therefore remains pending fresh independent review.
- 已排除：
  - 不得以 “CI green” 替代独立源码复核。
  - 不得恢复到“generic transition + boolean evidence 即可证明 rollback”的旧路线。
  - 不得依赖 Docker tag 单独证明 predecessor runtime identity。
  - 不得把 session-scoped USB public fingerprint 升格为跨 session recovery authority。
  - 不得 blind replay 解决 USB/host split-write。

## 4. 执行范围与授权

- 可继续：
  - fresh rebind repository main / PR #807 / source head / CI；
  - repository-only Stage A/B independent design/source/test review；
  - 若发现局部、明确、无歧义且不扩大范围的问题，可修复源码/测试、执行必要 CI 并归档；
  - **只有 Stage A/B fresh review 无新 blocker 时**，才可继续进入 repository-only Stage C USB/host split-write read-only reconciliation source design/development。
- 暂停边界：
  - `T1_ACCESS=false`
  - `T1_MUTATION=false`
  - `U13B_LIVE_EXECUTION_AUTHORIZED=false`
  - `BOARD_ACCESS=false`
  - `MERGE=false`
  - 不生成或执行 live U13B authorization package；
  - Stage A/B fresh review 若发现 blocker，立即停止 Stage C 前进，先完成 repair + verification。
- 授权状态：本交接无新的 live/physical authorization。U13A 历史授权已消费，`replay_permitted=false`；不得复用。

## 5. 下一步

- 行动：
  1. fresh rebind default main、PR #807 base/head、source-repair authority `6475c06e...` 和 16/16 CI；
  2. 按 Section 6 必读定位重新读取适用规则和 Stage A/B design/source/tests；
  3. 独立复核，不接受本 handoff 中“已修复”描述作为充分证据；
  4. 输出至少：
     ```text
     STAGE_A_REVIEW=
     STAGE_B_REVIEW=
     NEW_BLOCKER_COUNT=
     SOURCE_REPAIR_REQUIRED=
     STAGE_A_CLOSED_PASS=
     STAGE_B_CLOSED_PASS=
     STAGE_C_ENTRY_ALLOWED=
     ```
  5. 若 `NEW_BLOCKER_COUNT=0` 且 Stage A/B 均 PASS，则进入下一 repository-only gate：
     `U13B_STAGE_C_USB_HOST_SPLIT_WRITE_READONLY_RECONCILIATION_SOURCE_DESIGN_AND_DEVELOPMENT`。
- 完成条件：Stage A/B fresh independent review 有源码与测试证据支撑；若发现 blocker，完成 repair + applicable CI；若无 blocker，明确记录 Stage C entry allowed，并把结果归档到 GitHub。
- 失败／停点：任何 false-PASS path、authority drift、rollback replay ambiguity、recovery media mutation、runtime-health proof 缺口或 source/CI drift 都使 `STAGE_C_ENTRY_ALLOWED=false`，先修复并重新复核。

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/local-ai-task-splitting-rules.md`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set`
- 任务资料：
  - `docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_AND_DATA_ROLLBACK_ARCHITECTURE_V1.1_20261106.md`：上位 U13A/U13B architecture 与 rollback acceptance boundary；
  - `docs/development/N3W_T1_U13B_AUTOMATIC_ROLLBACK_SOURCE_DESIGN_V1_20261117.md`：Stage A/B 当前设计及 independent-review repair；
  - `docs/development/N3W_CURRENT_STATE.md` / `N3W_CURRENT_STATE_INDEX.md`：当前 authority 和历史定位；
  - 上述 Stage A/B source/test 文件：必须独立读源码，不只接受设计文档结论；
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：若发现新的 false oracle / failure class，再核是否需要新增或更新 KF。
- 已归档：
  - source/test/design repair 全部已进入 PR #807，exact source authority `6475c06e831cd597d6680502b41ea6fde6642837`；
  - exact-head CI 16/16 SUCCESS；
  - 本交接路径：`docs/development/N3W_T1_U13B_STAGE_A_STAGE_B_SOURCE_REPAIR_CI_PASS_TO_FINAL_INDEPENDENT_REVIEW_NEW_CHAT_HANDOFF_V1.0_20261117.md`；
  - 状态同步：`docs/development/N3W_CURRENT_STATE.md`、`docs/development/N3W_CURRENT_STATE_INDEX.md`。
- 未归档重要资料：无。本轮没有新的私有 raw evidence、实机日志或 live artifact。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：阅读本交接和适用仓库指令，fresh rebind default main、PR #807、source-repair authority `6475c06e831cd597d6680502b41ea6fde6642837` 及其 16/16 CI。先独立复核 U13B Stage A / Stage B 的设计、源码和测试，不要默认接受本轮修复结论；只有确认无新 blocker 后，才进入 Stage C USB/host split-write read-only reconciliation 的下一步 source design/development。