# N3-W T1 U7 R29 read-only preflight PASS → live source activation authorized
# 新会话交接文档 V1.0 — 2026-11-14

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：继续 N3-W T1 Home Assistant mandatory-USB OTA V1.2 路线。当前会话先完成 V1.2 路线/工程膨胀独立复核，再把 R29 read-only preflight Attempt03 与用户新的一次性授权对齐到 GitHub；新会话从 R29 grant-only successor 开始，最终执行一次 R29 live source activation。
- 已完成到：
  - V1.2 架构复核：产品路线、状态机和安全模型未偏移；工程执行/验证脚手架已达到中高程度膨胀，但不构成当前 R29 阻塞。
  - R29 source authority `acad3133d224ac9ae17c2ce45311c22db1e5ebe7` fresh CI 16/16 SUCCESS，final decoder/helper/source review PASS。
  - R29 real-T1 read-only preflight Attempt03 `U7-R29-READONLY-PREFLIGHT03-20261114T135007Z` CLOSED_PASS，RC=0 / wrapper RC=0。
  - 用户已明确授权下一会话执行 gate `N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_U7_SOURCE_ACTIVATION_R29_20261114_01`，确认语为 `EXECUTE U7 R29 SOURCE ACTIVATION: YES`。
- 当前状态：**可继续，但必须先做 grant-only successor + fresh CI + final exact review；本会话未执行 live source activation。** Reviewed source manifest 仍是 ungranted，authorization 尚未 claim/consume。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - candidate branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR #807: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR state at handoff preparation: OPEN / DRAFT / UNMERGED / MERGEABLE
- 核对时 main／本任务源码：
  - main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - exact reviewed R29 executable-source authority: `acad3133d224ac9ae17c2ce45311c22db1e5ebe7`
  - R29 executor blob: `f5427493f13b8fbccae55a9623036d41efa929d5`
  - R29 ungranted manifest blob: `5843be47fa3af87b431a97344b4ec2d6e097762d`
  - R29 focused test blob: `5f342bfad4e080a01b961f150aabfd138967c0cd`
  - HA target-binding workflow blob: `a7a3ce28b2cd28d565d61ce11036ed1591ceb83d`
  - frozen R25 helper blob: `f3e3ad25cda278f8ed5888bfee11573ac5fdd29e`
- 证据入口：
  - Attempt03 public closure comment: PR #807 comment `6878264504`
  - R29 exact pre-Attempt03 closure comment: `6878215851`
  - Attempt02 repair/CI comment: `6878155553`
  - HA target binding #935: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43601160554
  - Manager A-to-B #1111: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43601160565
  - fast source/exact closure #1464: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43601160638
  - public repository safety #7571: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43601160611
  - V1.2 route/bloat review: `docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_V1_2_ROUTE_AND_ENGINEERING_BLOAT_REVIEW_20261114.md`
  - R29 repair history: `docs/development/N3W_T1_U7_R28_IMPORT_FAILURE_TO_R29_SOURCE_REPAIR_20261114.md`

Production/runtime authority remains separate from repository tip:
- product source authority: `5b32e1ae82104a42f9e4e6907fe44d9172e87615`
- Manager: `local/greenhouse-manager:fresh-44e7d7472714` observed live in Attempt03
- Home Assistant: `local/n3w-homeassistant:2026.10.0-0c73235a`
- Broker: `local/n3w-mosquitto:2.1.2-3184566d`

## 3. 必须继承的结论

- 已证实：
  1. **V1.2 产品路线没有偏移。** Durable live phase 仍是 `U6_PREDECESSOR_RECOVERY_PREPARING`；R29 只是 U7 source activation，不是新产品 lifecycle phase。R29 success 之后下一 lifecycle action 仍是 V1.2 的 U6→U7 HA quiesce/data-backup。
  2. **工程膨胀存在且已产生自有故障面。** PR #807 在复核时为 389 commits / 139 changed files / +46985 / -760。R28 import-closure gap、R29 Attempt01 helper-indirection defect、Attempt02 embedded remote decoder defect均属于实现/执行脚手架问题，不是 V1.2 状态机缺陷。
  3. 当前不应在 R29 live activation 前重构 executor framework；这会破坏 exact review/preflight binding。应在当前 R29/U7 路径稳定后单独安排 convergence。
  4. R28 是 terminal consumed/no-replay；其 source activation 失败后 bounded rollback PASS，不能重放。
  5. R29 Attempt01：本地 wrapper STOP，`T1_ACCESS=false`，无 staging/claim/mutation。
  6. R29 Attempt02：仅建立 SSH，remote decoder 在 state read 前 STOP；无 staging/claim/mutation。
  7. R29 Attempt03：real-T1 read-only CLOSED_PASS，`source_activation_eligible=true`，`authorization_claimed=false`，`authorization_consumed=false`，所有 mutation=false。
  8. Attempt03 exact live state：
     - transaction SHA-256 `7f406b5b88f7bd5c3161d7527a001ddcb3414a8ec64fb34cdad444c2c3e62ebe`;
     - R26 predecessor authority exact、consumed/no-replay；
     - IPC phase `PREDECESSOR_RECOVERY_PREPARING`，installed version `2026.10.0`;
     - Manager / HA / Broker running，restart_count=0；
     - host / services-owner / broker-owner active/running/success，NRestarts=0；
     - backup/USB/install predecessor exact；
     - pre-U7 `n3w_t1_core_updater_host.py` = ABSENT；
     - common blob = `63a0377b7df509fd44194a1752a19c013ce55858`；
     - v2_state blob = `d89d4696409d7c451ec0b37a8be87e29092806b6`；
     - nine unchanged U6 dependency hashes exact。
  9. R29 activation set is exactly six modules:
     - `n3w_t1_core_updater_ha_backup.py`
     - `n3w_t1_core_updater_ha_usb.py`
     - `n3w_t1_core_updater_ha_install.py`
     - `n3w_t1_core_updater_host.py`
     - `n3w_t1_core_updater_common.py`
     - `n3w_t1_core_updater_v2_state.py`
- 待确认：
  - 新会话 fresh rebind 后 PR #807/head 是否仅有本轮 docs-only alignment drift；必须证明 R29 executable source 与 `acad3133...` byte authority 未变。
  - grant-only successor 的 fresh CI 必须全绿；final exact review 必须证明仅授权状态变化，不含 executable-source drift。
  - live execution 前必须 fresh 绑定私有 T1 locator / known-hosts / host-key authority；这些私有值不得写入 GitHub。
- 已排除：
  - 不需要再执行 Attempt01/02/03 read-only preflight，除非 fresh rebind 或 live baseline显示实质漂移。
  - 不允许重放 R28。
  - 不允许把 R29 source activation success 自动解释为 U7 lifecycle completion。
  - 不在 R29 前临时重构 transport/executor framework。
  - 不把 USB /dev node、UUID、fingerprint 恢复为 cross-session product authority。

## 4. 执行范围与授权

- 可继续：
  1. fresh rebind main、PR #807、current state、R29 source authority；
  2. 基于已审核 executable source 创建 **grant-only successor**；
  3. grant-only successor fresh CI；
  4. final exact source/manifest review；
  5. 条件满足后执行一次 R29 real-T1 live source activation；
  6. 归档 R29 result。
- 暂停边界：
  - R29 success 必须停在 `STOP_AFTER_R29_U7_SOURCE_ACTIVATION_BEFORE_U7_HA_QUIESCE_DATA_BACKUP_LIVE_EXECUTION`。
  - R29 不允许 service stop/restart、transaction mutation、USB mutation、U7 transition、HA quiesce、HA backup、U8+、board access、merge。
  - 如果 executable source 相对 `acad3133...` 有任何实质变化，不得继承本授权；停止并重新复核/授权。
  - 如果 live execution claim 后发生失败/transport uncertainty，authorization 永久 consumed/no-replay；不得自动第二次执行，只能读取 durable state 并按 executor rollback/reconciliation contract处理。
- 授权状态：
  - source: user message in current chat, 2026-11-14；
  - gate: `N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_U7_SOURCE_ACTIVATION_R29_20261114_01`
  - confirmation: `EXECUTE U7 R29 SOURCE ACTIVATION: YES`
  - `USER_AUTHORIZATION_GRANTED=true`
  - `AUTHORIZATION_CLAIMED=false`
  - `AUTHORIZATION_CONSUMED=false`
  - `REPLAY_PERMITTED=false`
  - `CURRENT_SOURCE_MANIFEST_GRANTED=false`
  - `GRANT_ONLY_SUCCESSOR_REQUIRED=true`

交接本身不新增权限；这里记录的是用户在交接前已经明确给出的 exact R29 gate authorization。

## 5. 下一步

- 行动：
  1. 阅读本 handoff 与适用仓库指令；
  2. fresh rebind `main`、PR #807/head、R29 source authority、Current State/Index；
  3. 确认从 `acad3133...` 到当前 docs-alignment head 不存在 executable-source drift；
  4. materialize grant-only successor：只把 R29 manifest 的 live execution authorization 设为 granted，保持 claimed=false / consumed=false / replay=false，不改变 executable source；
  5. fresh CI；若同一 HEAD 连续 3 次仍未终态，停止轮询并给出 run 链接；
  6. CI 全绿后立即做 final exact review；
  7. 使用私有 exact T1 binding 执行一次 R29 live source activation，不重复请求已授予的 R29 gate 权限；
  8. 归档结果并停止在 U7 HA quiesce/data-backup 之前。
- 完成条件：
  - expected result `U7_R29_SOURCE_ACTIVATION_PASS`；
  - authorization claimed=true / consumed=true / replay=false；
  - six target modules exact；
  - staged import + installed import PASS；
  - unit PIDs / container IDs / restart_count continuity PASS；
  - U6 transaction SHA unchanged；
  - IPC remains `PREDECESSOR_RECOVERY_PREPARING`；
  - service_stop=false / service_restart=false / transaction_mutation=false / usb_mutation=false / u7_transition=false / u8_plus=false；
  - durable success evidence + public-safe GitHub closure archived。
- 失败／停点：
  - preclaim failure：不消费授权；修复是否可继续取决于是否改变 executable source。任何 source drift 需要重新 review/authorization。
  - postclaim failure：authorization consumed/no-replay；最多执行 executor 定义的一次 bounded rollback；之后停止并从 durable remote state 取证。
  - rollback 不完整：视为 `ROLLBACK_INCOMPLETE`，禁止重试 live gate。
  - R29 PASS 后不自动执行 U7 HA quiesce/data-backup；它是独立 live lifecycle gate。

## 6. 必读定位与归档

- 仓库规则：
  - 读取适用 `AGENTS.md`；
  - 按 `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set` 执行最小读取集。
- 任务资料：
  - `docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_REMOVABLE_MEDIA_CONTENT_AUTHORITY_ARCHITECTURE_V1.2_20261112.md` — V1.2 冻结产品/恢复 authority；
  - `docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_V1_2_ROUTE_AND_ENGINEERING_BLOAT_REVIEW_20261114.md` — 本轮路线/膨胀复核；
  - `docs/development/N3W_T1_U7_HA_QUIESCE_DATA_BACKUP_SOURCE_DESIGN_AND_REVIEW_20261114.md` — R29 之后的 U7 设计边界；
  - `docs/development/N3W_T1_U7_R28_IMPORT_FAILURE_TO_R29_SOURCE_REPAIR_20261114.md` — R28→R29、Attempt01/02/03；
  - `docs/development/N3W_CURRENT_STATE.md` 与 `N3W_CURRENT_STATE_INDEX.md` — active route；
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` — 重点读取 KF-155 以及 post-claim uncertainty / executor fail-closed 相关 guards；
  - `tools/execution_packages/n3w/r7a/u7_source_activation_r29/{executor.py,manifest.json}` — 执行前必须重新核对 exact package。
- 已归档：
  - PR #807 comments `6878155553`, `6878215851`, `6878264504`；
  - architecture review/current-state alignment/R29 Attempt03 closure 与本 handoff 均在 PR #807 candidate branch。
- 未归档重要资料：
  - 私有 T1 SSH locator、known-hosts path、host-key binding 按项目规则只保存在 private context，不进入 GitHub；新会话执行前 fresh verify。
  - 无未归档的公开工程产物。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

### 新会话启动语

```text
阅读：
docs/development/N3W_T1_U7_R29_READONLY_PREFLIGHT_PASS_TO_LIVE_SOURCE_ACTIVATION_AUTHORIZED_NEW_CHAT_HANDOFF_V1.0_20261114.md

并按 handoff 的必读定位读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md 相关章节
- docs/development/N3W_CURRENT_STATE.md 顶部当前 authority
- docs/development/N3W_CURRENT_STATE_INDEX.md 顶部当前索引
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md 中 KF-155 与相关 executor guards
- docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_REMOVABLE_MEDIA_CONTENT_AUTHORITY_ARCHITECTURE_V1.2_20261112.md
- docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_V1_2_ROUTE_AND_ENGINEERING_BLOAT_REVIEW_20261114.md
- docs/development/N3W_T1_U7_R28_IMPORT_FAILURE_TO_R29_SOURCE_REPAIR_20261114.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

先 fresh rebind repository main、PR #807、candidate head 和 exact R29 executable-source authority，确认本轮 docs-only alignment 没有引入 executable-source drift。

然后进入：

N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_U7_SOURCE_ACTIVATION_R29_20261114_01
EXECUTE U7 R29 SOURCE ACTIVATION: YES

该 R29 gate 的用户授权已在上一会话明确授予，claimed=false、consumed=false。不要再次要求同一授权。

先 materialize grant-only successor，要求 fresh CI 全 SUCCESS + final exact review，再执行一次 live R29 source activation。

R29 PASS 后必须停止在 U7 HA quiesce/data-backup live execution 之前。
不要重放 R28，不要重新执行 Attempt01/02/03，不要自动进入 U7/U8+，不要 merge。
```
