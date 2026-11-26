# N3-W T1 OTA V1.3 U4 identity patch execution — 新会话交接 V1.0

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：继续“温室环境监测系统（ESP32-C6）”N3-W T1 Core Stack OTA V1.3 R8 验收。当前需要先把已 exact-CI/package 闭合的 KF-143 U4 predecessor identity 修复部署到 spare T1 updater。用户已明确指令：**在新对话中执行 `N3W_T1_V1_3_U4_IDENTITY_PATCH_20261123_01`**。
- 已完成到：live updater takeover PASS；legacy-U3 compatibility patch PASS；现有 HA transaction 保持同一个 ACTIVE `U3_TARGET_DOWNLOADING_VERIFYING`；schema-v2 Attempt 01/02 均 STOP 且未进入 U4/U5，Attempt 02 新签发的 v2 prepare authority 已退役；KF-143 source fix / regression / exact CI/package 已闭合。
- 当前状态：**可继续，等待新会话 fresh rebind 后执行 updater-only patch**。本交接不要求也不允许在 patch 内签发 schema-v2 prepare authority 或恢复 U3。

```text
LIVE_STATE=ACTIVE/U3_TARGET_DOWNLOADING_VERIFYING
LIVE_UPDATER_SOURCE=9093bf6ca13b27b850ee28d4508135c385b4b6ce
LIVE_UPDATER_PYZ_SHA256=9cf539cb7c7facd15a9729a2472601e5fce4f9c9b27750007e8924f73a8211b2

NEXT_PATCH_SOURCE_TEST_HEAD=c702dda43780892d477bc1a10141d98abc0d8229
NEXT_PATCH_EXECUTABLE_HEAD=a758239642f7cd54296548ae8b07a0d8cdc5f479
NEXT_PATCH_ARTIFACT_ID=14795440698
NEXT_PATCH_PYZ_SHA256=ae7c74a260f6023e19a0d63f2542f7c1bbc2693c032763270047771e435d3e5c

NEXT_AUTHORIZATION_ID=N3W_T1_V1_3_U4_IDENTITY_PATCH_20261123_01
NEXT_TERMINAL_STOP=ACTIVE_U3_WITH_c702dda4_UPDATER
SCHEMA_V2_AUTHORITY_IN_PATCH=false
U3_TO_U4_IN_PATCH=false
U5_IN_PATCH=false
```

## 2. 代码与证据

- 仓库／分支／PR：`chrenguo-stack/HomeAssistant` / `review/t1-ota-r8-existing-tx-predecessor-prep-20261123` / PR #824 <https://github.com/chrenguo-stack/HomeAssistant/pull/824>；PR 保持 OPEN / DRAFT / 未合并。
- 核对时 main／本任务源码：
  - repository main：`4fde1b7c5cc0aa224fa3574b8b4cc638edd93647`
  - live updater source：`9093bf6ca13b27b850ee28d4508135c385b4b6ce`
  - KF-143 executable source fix：`a758239642f7cd54296548ae8b07a0d8cdc5f479`
  - exact source/test CI head：`c702dda43780892d477bc1a10141d98abc0d8229`
- exact CI/package：
  - applicable workflows：19 SUCCESS；0 FAILURE；0 CANCELLED；0 RUNNING；2 expected path-gated SKIPPED
  - HA target-binding run：`45124757720` SUCCESS
  - recovery artifact ID：`14795440698`
  - artifact ZIP SHA256：`3bd2f94d2bd64fc35106f299fef08559d0a55c42852ce736d1e5a931cd09459e`
  - install manifest SHA256：`6fdaa8a5c8b8c2a2f388bd536e276238edd0ae05f0a7ad23948409953ee16dd4`
  - `ha-recovery.pyz`：479591 bytes；SHA256 `ae7c74a260f6023e19a0d63f2542f7c1bbc2693c032763270047771e435d3e5c`
  - 与 live `9093bf6c...` artifact 比较：只变化 `ha-recovery.pyz`；10 个非 pyz 安装负载逐字节一致。
- live transaction / USB public-safe evidence：
  - transaction id SHA256：`760dc8bdab1c9ceee2b0d3dfb2797111f24e69a9e7569efb6907bc64325d71fe`
  - transaction file SHA256：`9e663188098c6d4795115da42bd2acd4b31abb05aeb9f48ab8dfabac620988c7`
  - target archive：2448553472 bytes；SHA256 `e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663`
  - predecessor archive：2447090176 bytes；SHA256 `6502b8cdbf706d746e32311fdaa39ffc5ca703d76f766806bbb21d3c71278d1f`
  - 两个 partial 文件均不存在；internal target spool 已不存在；target 2026.10.0 尚未加载。
- 证据入口：
  - PR #824 comment `7093009644`：legacy-U3 compatibility live patch PASS
  - `7093054823`：schema-v2 U3→U4 authorization
  - `7093088176` / `7093099117`：Attempt 01 STOP / timer sequencing root cause
  - `7093400041`：Attempt 02 STOP；v2 authority 已退役
  - `7093431574`：KF-143 root cause / source repair
  - `7093590977`：`c702dda4...` exact CI/package closure
  - `docs/development/N3W_CURRENT_STATE.md`
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`，KF-143

## 3. 必须继承的结论

- 已证实：
  - live T1 当前运行 HA `2026.10.4-5881590f`、Manager `fresh-44e7d7472714`、Broker `2.1.2-3184566d`；最近 live 验证三者 running 且 restart_count=0。
  - live updater 已从 ea68 接管到 V1.3，并进一步部署 legacy-U3 compatibility pyz；当前 live source 为 `9093bf6c...`，pyz 为 `9cf539cb...`。
  - HA transaction 仍为同一个 ACTIVE U3；Attempt 01 未签发 authority，Attempt 02 authority 成功签发但 resume 失败，随后仅在确认仍为同一 U3 后将该 v2 authority 原子退役。
  - 当前没有 active prepare authority。旧 schema-v1 authority 已退役；Attempt 02 schema-v2 authority SHA256 `4fd417c97820a45c397dd4462d3ec86741ac6c7037fdac7302814a3916476edf` 也已退役。
  - Attempt 02 的 `RECOVERY_STARTUP_NEEDS_REVIEW` 根因是 KF-143：production admission 的 `current_image_identity` 只有 `runtime_image_id + platform`，而旧 U4 validator 无条件要求未保存的 `portable_identity_sha256`。
  - KF-143 修复保持 fail-closed：若 `portable_identity_sha256` 明确存在则仍必须精确匹配；仅当 production admission 从未提供该可选字段时，使用本次完整解析并与 live predecessor 验证后的 portable identity。
  - `c702dda4...` 已通过 exact CI/package；下一 live 修复只需替换 pyz。
- 待确认：
  - 新会话执行前必须 fresh read-only rebind：live pyz 仍应为 `9cf539cb...`；transaction file SHA256 仍应为 `9e663188...` / ACTIVE U3；active prepare authority 必须不存在；runtime 必须仍健康；target 10.0 必须仍未加载。
  - patch PASS 之后，下一道 schema-v2 U3→U4 live acceptance 仍未执行，KF-143 保持 OPEN。
- 已排除：
  - 不再使用旧 U1 假设；历史 U1 handoff 已被 live forensic 证明陈旧。
  - 不再使用 retired static-reserve U1→U4 命令。
  - 不得重放旧 schema-v1 authority 或已退役的 Attempt 02 v2 authority。
  - 不得在当前 live `9093bf6c...` updater 上再次尝试 U3→U4；必须先部署 `c702dda4...` patch。

## 4. 执行范围与授权

- 可继续：用户在当前会话明确要求“在新对话中执行 `N3W_T1_V1_3_U4_IDENTITY_PATCH_20261123_01`”。该一次性授权目标为 spare T1，候选精确绑定：
  - source/test head `c702dda43780892d477bc1a10141d98abc0d8229`
  - artifact `14795440698`
  - ZIP SHA256 `3bd2f94d...`
  - manifest SHA256 `6fdaa8a5...`
  - new pyz SHA256 `ae7c74a2...`
  - expected live old pyz SHA256 `9cf539cb...`
  - expected transaction file SHA256 `9e663188...`
- 授权允许：上传/暂存 exact artifact；本地与远端精确校验；静止 updater retry timer/service 与 OTA IPC socket/service；原子替换唯一变化的 `ha-recovery.pyz`；fsync/readback；验证 10 个非 pyz 文件无漂移；验证 transaction 无变化；失败时恢复 exact old pyz；成功后重新启用 updater socket/timer并只读验证 runtime/transaction/authority。
- 暂停边界：patch PASS 后立即停止，终态仍为 ACTIVE U3。**禁止** schema-v2 prepare authority、U3→U4、U5/install authority、authorization claim/consume、HA/Manager stop、target image load、current image release、USB payload 写入/删除/格式化、reboot/power-cycle、Broker OTA/mutation、PR merge、production release。
- 授权状态：

```text
AUTHORIZATION_ID=N3W_T1_V1_3_U4_IDENTITY_PATCH_20261123_01
AUTHORIZATION_SOURCE=USER_DIRECTIVE_IN_HANDOFF_ORIGIN_CHAT
AUTHORIZATION_STATUS=APPROVED_FOR_NEXT_CHAT_EXECUTION
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
AUTHORIZATION_REPLACED=false
FRESH_REBIND_REQUIRED=true
```

交接本身不扩大该授权。任何目标、transaction、old/new pyz、artifact、authority 或 runtime 漂移均使受影响写操作 STOP。

## 5. 下一步

- 行动：
  1. fresh rebind PR #824、branch head、main、current state、KF-143；确认没有 source drift。
  2. 对 spare T1 做最小只读 preflight，确认 old live pyz / transaction / authority / runtime / target-image absence 精确匹配本交接。
  3. 下载 artifact `14795440698`，独立验证 ZIP / manifest / source head / pyz。
  4. 执行 `N3W_T1_V1_3_U4_IDENTITY_PATCH_20261123_01` updater-only atomic patch。
  5. PASS 后立刻只读审计并归档 GitHub；停止，不进入 schema-v2 U3→U4。
- 完成条件：

```text
PATCH_STATUS=PASS
INSTALLED_PYZ_SHA256=ae7c74a260f6023e19a0d63f2542f7c1bbc2693c032763270047771e435d3e5c
NON_PYZ_VERIFIED_COUNT=10
TRANSACTION_STATUS=ACTIVE
TRANSACTION_PHASE=U3_TARGET_DOWNLOADING_VERIFYING
TRANSACTION_FILE_SHA256=9e663188098c6d4795115da42bd2acd4b31abb05aeb9f48ab8dfabac620988c7
ACTIVE_PREPARE_AUTHORITY=false
TARGET_2026_10_0_LOADED=false
HA_MANAGER_BROKER_HEALTH=PASS
UPDATER_SOCKET_REARMED=true
UPDATER_TIMER_REARMED=true
STOP_BEFORE_SCHEMA_V2_AUTHORITY=true
```

- 失败／停点：
  - mutation 前任一 preflight 漂移：STOP，不写。
  - 已静止控制面但 patch 未提交：保持 transaction 不变，恢复/重启仅在 old pyz exact 可证明时进行。
  - patch 已提交后验证失败：优先原子恢复 exact old pyz `9cf539cb...`；只有 old pyz readback、transaction non-drift、authority absence 均确认后才可 rearm。
  - 若 exact rollback 不能证明，**不要 rearm 不确定 updater**；保持 updater 控制面停止，保留 HA/Manager/Broker 当前运行，输出结构化 STOP，进入只读恢复诊断。
  - 不得把失败后的同一授权静默重放；先归档 STOP 并重新 fresh rebind。

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/local-ai-task-splitting-rules.md`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
  - [工作上下文的最小读取规则](N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set)
- 任务资料：
  - `docs/development/N3W_CURRENT_STATE.md`：当前 live/source/artifact/authorization 唯一 volatile authority。
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`：定位当前 handoff。
  - `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md`：产品设计 authority。
  - `docs/development/N3W_T1_OTA_V1_3_DYNAMIC_USB_CAPACITY_SOURCE_ALIGNMENT_20261123.md`：V1.3 动态容量 source alignment。
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`：读取 KF-143；KF-143 在 live U3→U4 验收前保持 OPEN。
- 已归档：PR #824、source fix `a7582396...`、test/CI head `c702dda4...`、artifact `14795440698`、上述 PR comments、current state、KF-143 和本交接文档。
- 未归档重要资料：无。真实 LAN 地址、原始 USB UUID/私有 locator 等继续留在私有执行上下文；GitHub 只保存脱敏 target class、hash 和 public-safe evidence。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

ARCHIVE_AUDIT=PASS
PUBLIC_SOURCE_ARCHIVED=true
PUBLIC_TESTS_ARCHIVED=true
PUBLIC_DOCS_ARCHIVED=true
KNOWN_FAILURES_UPDATED=true
PRIVATE_RAW_EVIDENCE_PRESENT=true
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
PRIVATE_EVIDENCE_BINDING_ARCHIVED=true
IMPORTANT_ENVIRONMENT_FACTS_ARCHIVED=true
REGRESSION_GUARD_ARCHIVED=true
UNTRACKED_CRITICAL_ARTIFACTS=0
UNARCHIVED_CRITICAL_KNOWLEDGE=0
UNARCHIVED_CRITICAL_RESULT_COUNT=0

NEXT_SAFE_ENTRY_POINT=FRESH_REBIND_THEN_N3W_T1_V1_3_U4_IDENTITY_PATCH_20261123_01
```

新会话启动语：阅读本交接和适用仓库指令，fresh rebind main / PR #824 / current state / KF-143，先核对 live U3 与 exact old/new updater identity；匹配后在现有用户授权范围内执行 `N3W_T1_V1_3_U4_IDENTITY_PATCH_20261123_01`。PASS 后归档并停止，不进入 schema-v2 authority 或 U3→U4。
