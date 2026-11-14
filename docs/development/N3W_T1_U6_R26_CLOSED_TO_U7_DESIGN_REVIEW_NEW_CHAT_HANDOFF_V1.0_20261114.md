# N3-W T1 U6 R26 CLOSED → U7 设计/复核 新会话交接 V1.0（2026-11-14）

`HANDOFF_TEMPLATE_VERSION=1.4`

本文只记录本轮 U6/R26 closure 到下一阶段 U7 设计/复核的增量。长期规则以 `N3W_PROJECT_WORKING_CONTEXT.md` 为准。公开文档不包含私有 SSH 地址、known-hosts 路径、私有证据目录或其他运行时私密定位信息。

## 1. 目标与停点

- 任务／交接原因：R26 predecessor recovery 已完成并正式 CLOSED_PASS；本轮对话在完成 GitHub 对齐后结束。用户明确要求在本轮结束前自行对 T1 执行一次重启；新会话从 **U7 Home Assistant 停写／数据备份流程的设计和源码复核** 开始，不直接执行 U7 live mutation。
- 已完成到：
  - R26 durable remote result = `U6_R26_PREDECESSOR_RECOVERY_PASS`；
  - host transaction 与 bound USB transaction metadata 均已持久化到 `U6_PREDECESSOR_RECOVERY_PREPARING`；
  - predecessor recovery archive 已验证、fsync；
  - R26 one-shot authorization 已 claimed + consumed，永久 no-replay；
  - Mac 端 Attempt 03 的 `STOP_UNKNOWN` 已由后续 durable `success.json` 证明为 client transport timeout false-negative；
  - R26 closure、Current State、Current State Index、Working Context V7.7、KF-154 已归档到 GitHub。
- 当前状态：**U6 CLOSED_PASS / U7 未执行 / 可进入 U7 设计与复核**。交接生成时 T1 reboot 尚未由本交接验证完成；重启后的 live runtime、USB mount、boot ID、service PID/container ID 均标记为 `UNKNOWN_FRESH`。

```text
CURRENT_PHASE=U6_PREDECESSOR_RECOVERY_PREPARING
NEXT_PHASE=U7_HA_QUIESCED_DATA_BACKUP_PREPARING
R26_TERMINAL=CLOSED_PASS
R26_REPLAY_PERMITTED=false

T1_REBOOT_REQUESTED_BY_USER=true
T1_REBOOT_AUTHORIZED_ONCE=true
T1_REBOOT_EXECUTED_AT_HANDOFF_CREATION=false
POST_REBOOT_RUNTIME_BASELINE=UNKNOWN_FRESH

U7_LIVE_EXECUTION_AUTHORIZED=false
MERGE=false
```

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: `#807` — OPEN / DRAFT / UNMERGED；本轮写后 fresh mergeability=false，但 `MERGE=false`，mergeability 不作为下一阶段 authority
- 核对时 main／本任务源码：
  - repository main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - R26 live closure/docs alignment head: `562db4178f72f692bd612b76bc8029c0a4366227`
  - R26 execution authority head: `d95426b15fb718e60683f75ceef36becb8038b61`
  - current repository product source head: `5b32e1ae82104a42f9e4e6907fe44d9172e87615`
  - formal handoff template V1.4 blob: `885fd63131e80936e5e1fe907378be08a0060f12`
- 证据入口：
  - `docs/development/N3W_T1_U6_R26_LIVE_PREDECESSOR_RECOVERY_CLOSURE_20261114.md`
  - `docs/development/N3W_CURRENT_STATE.md`
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md` — V7.7
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` — KF-154
  - PR #807 R26 closure comment: `6871417084`

R26 durable U6 evidence:

```text
LIVE_TRANSACTION_PHASE=U6_PREDECESSOR_RECOVERY_PREPARING
LIVE_TRANSACTION_SHA256=7f406b5b88f7bd5c3161d7527a001ddcb3414a8ec64fb34cdad444c2c3e62ebe
USB_TRANSACTION_PHASE=U6_PREDECESSOR_RECOVERY_PREPARING

PREDECESSOR_ARCHIVE_SHA256=34cec37ab021e1081e236502bfd06760894f6bca93bd8d6bf99d8d90bb89848d
PREDECESSOR_ARCHIVE_SIZE_BYTES=743074537
PREDECESSOR_PORTABLE_IDENTITY_SHA256=8b4d4376e2ab339347abb4aa554d3a5cc6f93ea20b0ee3c22ca8e29ae14b16c3
PREDECESSOR_VERIFIED=true
PREDECESSOR_FSYNCED=true

PRODUCT_U9_AUTHORIZATION_CLAIMED=false
PRODUCT_U9_AUTHORIZATION_CONSUMED=false

SERVICE_RESTART=false
HA_QUIESCE=false
U7_PLUS=false
ROLLBACK_REQUIRED=false
```

下一阶段上位设计／源码定位：

- `docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_AND_DATA_ROLLBACK_ARCHITECTURE_V1.1_20261106.md`
  - blob: `c8a5af2123dcd53b5a1101cf9b737fe011622120`
  - 重点：Phase U7、HA_DATA_BACKUP semantics、power-loss/USB-removal behavior。
- `docs/development/N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_DESIGN_DELTA_20261106.md`
  - blob: `628c77b9a6476709c58d72d5b258a12f9e02d9bf`
  - 重点：U6→U7→U8 state-machine mapping、INSTALL contract、HA_DATA_BACKUP contract。
- `tools/n3w_t1_core_updater_ha_usb.py`
  - blob: `dc8218344061d93f524ca7cc786f7aacfa27e1db`
  - 重点：`record_predecessor_recovery_and_ha_quiesced()` 要求 current phase=U6、verified predecessor、`ha_quiesced=true` 才能进入 U7。
- `tools/n3w_t1_core_updater_ha_backup.py`
  - blob: `212fc5a0c2ce8c7c3375f65f3e8ead165299ab1b`
  - 重点：backup record 必须同时满足 verified/fsynced/consistent pre-upgrade point/完整 production config/storage integrity/ownership metadata/confidentiality/authenticity，并对 unsupported external state fail closed。
- `tools/n3w_t1_core_updater_ha_prepare_host.py`
  - live source SHA-256: `0d0c96d7ae2f26c2d2ae8388e6ee75ad0616081a6cdcb98727f2131dab31c30e`
  - repository blob: `59b06d3aa595a6c4801b96d6b992b174a700ca31`

## 3. 必须继承的结论

- 已证实：
  1. R26 已真实成功，不能因 Mac transport timeout 将其重新分类为失败；durable remote `success.json` 是后续裁决依据。
  2. R26 authorization 已 consumed/no-replay；Attempt 03 永久禁止重跑。
  3. 当前 durable host transaction 与 USB phase 都是 U6；predecessor archive 已 verified + fsynced。
  4. Home Assistant 在 R26 closure 时仍运行，未 quiesce；Manager/HA/Broker 容器均 running/restart0；owner units active/running/success/NRestarts=0。
  5. 产品 U9 authorization 仍未 claimed/consumed；没有 predecessor internal image deletion，没有 U7+。
  6. 冻结架构规定 U7 顺序为：verified target + verified predecessor → production-owner semantics quiesce HA → create consistent HA_DATA_BACKUP directly to USB → verify integrity → fsync data+metadata → persist U7 state；U8 之前不得进入 destructive U9。
  7. 当前仍在 U9 前；架构的 power-loss contract 要求 predecessor 仍为内部权威，不能把重启理解为已进入 destructive recovery。
- 待确认：
  1. 用户本轮结束后实际执行 T1 reboot 后的 `boot_id`、owner units、containers、IPC phase；
  2. `/run/n3w-t1-ota/... ` runtime mount 是否消失或被自动恢复；
  3. bound USB 是否仍在、是否需由 product resolver 重新 mount 同一 filesystem UUID；
  4. post-reboot host transaction 是否仍精确 U6、SHA 是否保持或因合法启动流程产生可解释变化。
  以上均为 `UNKNOWN_FRESH`；新会话进行 U7 **设计/复核** 可先继续，但任何未来 U7 live gate 在执行前必须重新只读核对这些状态。
- 已排除：
  - 不重跑 R26；
  - 不重新提交 INSTALL；
  - 不把 `/dev/sdb1` 或任何固定 `/dev/sdX` 当长期业务 authority；
  - 不因 reboot 自动 claim U9；
  - 不在 U7 设计阶段删除 predecessor image；
  - 不把未验证的 post-reboot mount/service 状态写成 PASS；
  - 不合并 PR #807。

## 4. 执行范围与授权

- 可继续：
  - 新会话可直接进行 U7 架构/源码独立复核、设计收敛、source-only 实现、测试、模拟、CI 和 GitHub 归档；
  - 可分析 reboot 后 U6→U7 所需的 same-USB reopen/remount/revalidation 机制；
  - 可按现有项目规则连续完成 source-only 小修和 fresh CI。
- 暂停边界：
  - **任何 U7 实机执行、HA quiesce、HA_DATA_BACKUP 真实创建、USB 写入、service stop/start、transaction U6→U7 mutation 均未授权**；
  - U8/U9+、image deletion、target install、rollback、board access、PR merge 均未授权；
  - 若 U7 设计需要改变已冻结 product phase semantics、backup security contract 或扩大到 U8/U9，先停止并说明设计影响。
- 授权状态：
  - R26：claimed=true / consumed=true / replay=false，terminal。
  - 本轮 T1 reboot：用户在当前对话明确授权 **一次** T1 reboot；该授权只覆盖正常重启本身，不覆盖 source/USB/transaction/service-config 修改。
  - U7 live execution：无。
  - PR merge：无。

## 5. 下一步

- 行动：
  1. 新会话读取本交接与最小必读集，fresh rebind main、PR #807、current branch head、Current State/Index/Working Context/KF-154；
  2. **从 U7 设计和源码复核开始**，不要先制造 live execution package；
  3. 独立复核当前 U7 相关 product source 与冻结架构，重点回答：
     - reboot 后处于 durable U6 时，如何重新解析并挂载 transaction-bound USB，而不依赖固定 device path；
     - quiesce 必须由哪个 production owner 执行，如何证明 HA 真正停止写入；
     - HA_DATA_BACKUP 的精确范围、SQLite consistency、ownership/mode、confidentiality/authenticity、external-state fail-closed；
     - U6→U7 transaction/USB metadata 的写入顺序与 fsync 边界；
     - backup 失败或进程/SSH 丢失时如何保持 predecessor running/recoverable，是否允许 restart HA；
     - 长任务 progress/heartbeat/timeout 设计，避免重复 KF-154；
     - U7 成功后如何停在 U7，且不自动进入 U8/U9。
  4. 形成 U7 SOURCE_DESIGN / source-review 结论；需要实现时再做 source-only repair + tests + fresh CI。
- 完成条件：
  - U7 设计明确满足 V1.1 architecture 与 source-design contract；
  - 对 post-reboot U6 same-media resolution 有明确、可测试、fail-closed 的方案；
  - HA quiesce 与 backup consistency、安全性、fsync、resume/failure semantics 都有测试；
  - 不出现 U8/U9 premature transition；
  - source-only CI/review closure 后再提出独立 live preflight/authorization gate。
- 失败／停点：
  - 若 fresh source 与冻结架构冲突，先在 source/design gate 内修复并重新 CI；
  - 若 post-reboot live 状态未来与 durable U6 authority 冲突，停止 U7 live preparation，先做 bounded read-only forensic；
  - 若需要新的 live mutation 或扩大 phase 范围，停止并取得明确授权。

## 6. 必读定位与归档

- 仓库规则：
  - 适用 repository `AGENTS.md`；
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md` 第 12 节 minimum new-chat read set；
  - formal template: `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4。
- 任务资料：
  - 本交接：恢复当前 stop point 和 next gate；
  - `N3W_CURRENT_STATE.md` / `N3W_CURRENT_STATE_INDEX.md`：当前 live phase / repo authority；
  - `N3W_T1_U6_R26_LIVE_PREDECESSOR_RECOVERY_CLOSURE_20261114.md`：U6 physical closure；
  - `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` KF-154：post-claim transport-timeout guard；
  - `N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_AND_DATA_ROLLBACK_ARCHITECTURE_V1.1_20261106.md` Phase U7 / §8 HA_DATA_BACKUP / power-loss semantics；
  - `N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_DESIGN_DELTA_20261106.md` state machine / INSTALL / backup contract；
  - U7 implementation review: `ha_usb.py`, `ha_backup.py`, `ha_prepare_host.py` 及相关 tests，按实际设计需要补读。
- 已归档：
  - R26 closure alignment head: `562db4178f72f692bd612b76bc8029c0a4366227`
  - PR #807 R26 closure comment: `6871417084`
  - 本交接提交后以其 Git commit 为正式新会话入口。
- 未归档重要资料：无。私有 SSH 地址、known-hosts 路径和本地 evidence root 按项目 public/private boundary 保留在私有上下文，不写入公开 GitHub。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：

> 阅读 `docs/development/N3W_T1_U6_R26_CLOSED_TO_U7_DESIGN_REVIEW_NEW_CHAT_HANDOFF_V1.0_20261114.md`，并按 V1.4 最小读取集 fresh rebind repository main、PR #807、current branch head、Current State、Current State Index、Working Context V7.7、KF-154 与 R26 closure。继续“温室环境监测系统（ESP32-C6）”项目 N3-W。R26 已 CLOSED_PASS 且 consumed/no-replay；当前 durable phase=U6_PREDECESSOR_RECOVERY_PREPARING。用户在上一会话结束后计划执行一次 T1 reboot，因此 post-reboot runtime/mount baseline 先视为 UNKNOWN_FRESH。**本会话从 U7 Home Assistant quiesce / HA_DATA_BACKUP 的架构设计和源码独立复核开始，不执行 U7 live mutation。**重点把 reboot 后 same-USB reopen、quiesce consistency、backup security/integrity、failure/resume、timeout/progress 与 U7 stop boundary 设计完整；source-only 开发、测试、CI 和 GitHub 归档可按项目规则连续推进。到达任何 U7 live execution / service stop / USB write / transaction mutation / U8+ / merge 边界时停止。
