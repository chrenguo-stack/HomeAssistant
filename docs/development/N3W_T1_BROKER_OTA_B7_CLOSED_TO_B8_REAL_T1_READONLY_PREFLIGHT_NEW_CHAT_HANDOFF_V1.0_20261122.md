# N3-W T1 Broker OTA — B7 CLOSED → B8 Real T1 Read-only Preflight 新会话交接

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：继续 T1 Core Stack OTA V1.2 的 Broker OTA 路线。B1–B7 已完成源码、Recovery Point、宿主接管、exact package、Mosquitto 2.1.4 target freeze、隔离 A→B 与独立源码复核。本次切换新会话，下一唯一执行 gate 为 `N3W_T1_BROKER_OTA_B8_REAL_T1_READONLY_PREFLIGHT_20261121_01`。
- 已完成到：B6 `CLOSED_PASS`；B7 `CLOSED_PASS`；B8 exact candidate set 已冻结；PR #820 交接前已验证 docs-head `ad37f39c108631d252fe1972f16c8602d00cafa7` 的 18 个 workflow 全部 SUCCESS；本 handoff 归档会产生新的 docs-only head，新会话必须 fresh rebind，不把 handoff 内的 pre-handoff SHA 当作当前 PR head。
- 当前状态：`READY_TO_ENTER_B8_READONLY_PREFLIGHT`。用户在本次交接请求中明确要求“在新对话进入 NEXT_ONE_GATE”，因此 B8 gate-entry / T1 read-only preflight 已授权；尚未执行任何真实 T1 访问。本授权不包含任何写入、安装、服务启停、Broker apply、重启/断电、merge 或 release。

```text
NEXT_ONE_GATE=N3W_T1_BROKER_OTA_B8_REAL_T1_READONLY_PREFLIGHT_20261121_01
B8_GATE_ENTRY_AUTHORIZED=true
B8_T1_READONLY_AUTHORIZED=true
B8_T1_READONLY_AUTHORIZATION_SOURCE=USER_DIRECTIVE_IN_HANDOFF_REQUEST
B8_T1_READONLY_AUTHORIZATION_CLAIMED=false
B8_T1_READONLY_AUTHORIZATION_CONSUMED=false
B8_T1_READONLY_AUTHORIZATION_NON_CONSUMPTIVE=true
B8_T1_MUTATION_AUTHORIZED=false
AUTO_EXECUTE_AFTER_B8=false
```

## 2. 代码与证据

- 仓库／分支／PR：`chrenguo-stack/HomeAssistant`；`feat/t1-broker-ota-b6-target-simulation-20261121`；Draft PR #820：https://github.com/chrenguo-stack/HomeAssistant/pull/820
- 核对时 main／本任务源码：`main=4fde1b7c5cc0aa224fa3574b8b4cc638edd93647`；PR #820 **pre-handoff validated docs-head**=`ad37f39c108631d252fe1972f16c8602d00cafa7`；B7 executable source authority=`dbc4f1ca5ce90f39e64887fb361d074ec51a7130`。交接归档之后的 PR #820 current head 必须由新会话 fresh rebind。
- 证据入口：
  - B6/B7 current authority：`docs/development/N3W_CURRENT_STATE.md` 顶部 2026-11-21 B6/B7 section。
  - B7 closure：`docs/development/N3W_T1_BROKER_OTA_V1_0_B7_INDEPENDENT_SOURCE_REVIEW_AND_B8_CANDIDATE_CLOSURE_20261121.md`。
  - B6 design/closure：`docs/development/N3W_T1_BROKER_OTA_V1_0_B6_TARGET_IMAGE_AND_ISOLATED_SIMULATION_20261121.md`。
  - V1.2 product authority：`docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md`，重点第 1、3、5、6、9、10、11 节。
  - Frozen target manifest：`infra/n3w-t1/upgrades/broker-2.1.4.json`。
  - Production predecessor authority：`infra/n3w-t1/production/image-lock.json` 与 `infra/n3w-t1/production/t1-core-stack-current.json`；真实 T1 当前运行态仍必须在 B8 fresh read-only 复核。
  - B6 Phase 1 exact target run：`44921739065`；artifact `14713718457`。
  - B6 frozen Phase 2 run：`44922182784`；`source=SUCCESS`、`exact-binding=SUCCESS`、`isolated-a-to-b=SUCCESS`、freeze 后 `exact-artifact=SKIPPED`。
  - B7 Recovery Support exact run：`44922182840`；artifact `14714301747`。
  - PR #820 docs-head final validation：Broker target run `44922688478=SUCCESS`；18/18 workflow SUCCESS。

### Frozen B8 candidate set

```text
BROKER_PREDECESSOR_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
BROKER_TARGET_IMAGE=local/n3w-mosquitto:2.1.4-5d96ab48
BROKER_TARGET_ARTIFACT_ID=14713718457
BROKER_TARGET_ARTIFACT_DIGEST=sha256:36d2d820b1d793f64014d910d08eace4d7ef90375adb2e43b1ba8e46a5195cf3
BROKER_TARGET_ARCHIVE_SHA256=35630ff4b3ba710d26f1b44ac022b806c3ad53c2f1a015195e48c79690d26f3e
BROKER_TARGET_ARCHIVE_SIZE_BYTES=13799035
BROKER_TARGET_ARM64_MANIFEST=sha256:5d96ab48dab65f1198659af538139d999ab474dd78ee1c231ffff0f4d52552e0

BROKER_RECOVERY_SUPPORT_SOURCE_HEAD=dbc4f1ca5ce90f39e64887fb361d074ec51a7130
BROKER_RECOVERY_SUPPORT_ARTIFACT_ID=14714301747
BROKER_RECOVERY_SUPPORT_ARTIFACT_DIGEST=sha256:ca2d4ffdce131b2916d2a4d8ccf3d38d5a9c28781a65af51fdbb0cbac0068f09
BROKER_RECOVERY_SUPPORT_MANIFEST_SHA256=29be11a66e3bf53c4073120340064fab9f56fbe2c0c6e4a55e0dfb299ddf652f
BROKER_RECOVERY_SUPPORT_UPDATER_SHA256=1daed02060fe51b64d0ee648fd5855926e5759770a6634fccddc7c2804d2371d
BROKER_RECOVERY_SUPPORT_UNIT_SHA256=d5bea0c625edfcf46729170eac30872ae8a11c59fce14c89c6c585d46438ce19
```

PR #820 docs-only head later重新生成的 Recovery Support artifact `14714610810`（digest `sha256:a8c20a911549efd6adeb39a886581acc1120755c3b5867a12fc1e00b62c3315a`）不是自动替换 B8 candidate 的 authority。没有 executable source 变更时，B8 继续绑定 `dbc4f1ca... / 14714301747`；如新会话发现 executable blob drift，必须 STOP 并重新绑定候选。

## 3. 必须继承的结论

- 已证实：
  - B6 Phase 2 frozen exact-binding PASS；target manifest、GitHub artifact、archive SHA256、portable identity、upstream linux/arm64 manifest 已精确绑定。
  - 隔离 Mosquitto 2.1.2 → 2.1.4 → predecessor rollback 全链路 PASS：Recovery Point create/restore、旧 retained 读取、target 写入、restore hash、2.1.2 rollback 读取、DynSec application auth compatibility 均成立。
  - B7 独立源码复核 `NEW_SOURCE_BLOCKER_COUNT=0`。Recovery Point create/restore/retire、Generic V2 automatic rollback / host restart takeover、`rollback_source_phase`、certificate lifecycle exclusive lock、writer quiescence、terminal cleanup、retirement crash-resume 均有直接源码和回归测试覆盖。
  - Broker OTA profile 固定为 `IMAGE_ONLY_V1`；TLS/CA、`mosquitto.conf`、DynSec schema 不迁移；Broker-only 更新按 V1.2 采用本机恢复策略，不自动引入 HA USB 路线。
- 待确认（B8 fresh T1 只读）：
  - 当前真实 T1 是否仍健康运行 predecessor `local/n3w-mosquitto:2.1.2-3184566d`，且 production Broker 实例/8883 listener 唯一、Manager/HA 同步健康。
  - 当前 Broker binding mode、Compose/env 实际 authority、arm64 平台、前代 image identity 是否与仓库 authority 一致。
  - `/var/lib/n3wfc4-broker` root 及 `dynamic-security.json` / `mosquitto.db` 的存在、owner/mode/shape、容量预算是否满足 Recovery Point preflight；不得输出文件明文或凭据。
  - `/var/lib/n3w-t1-core-updater` 是否不存在未完成 V2 transaction、陈旧 Broker recovery point 或需要先处理的 terminal cleanup。
  - certificate lifecycle lock / owner unit / timer 当前是否无冲突，Recovery Support 安装父目录和 systemd 环境是否满足后续安装前提。
  - frozen GitHub artifacts 在 B8 开始时仍可取得且未过期。
- 已排除：
  - Attempt 01–05 的失败均为隔离 CI fixture 问题，未证明 Mosquitto 2.1.4、Generic V2 或 Recovery Point 产品缺陷。
  - KF-102 guard：DynSec `admin` 不能被当作普通 application publisher。B8/B9/B11 的业务验收不得通过扩大 admin 权限来制造 PASS，必须使用合法 application/node identity。
  - KF-100 guard：Broker OTA quiesce / rollback 必须尊重 certificate lifecycle exclusive lock，不得绕过或停用该生命周期机制。
  - 历史 B5 artifact `14711625754` 已被 B7 hardening 后的 `14714301747` 替代，不得用于 B8。

## 4. 执行范围与授权

- 可继续：
  - fresh rebind GitHub exact head / artifacts / current state；
  - 执行 B8 所需的真实 T1 **只读**检查；若模型不能直接访问 T1，则生成最小、可直接复制执行的 Mac Terminal 命令，由用户执行并回传结果；
  - 在不接触 live T1 的情况下补充源码复核、确定性模拟、GitHub 文档/证据归档；
  - B8 PASS 后可以准备 B9 preauthorization 设计/执行包，但不得执行任何 live mutation。
- 暂停边界：
  - B8 内禁止：向 T1 写文件、上传 artifact、安装 Recovery Support、`daemon-reload`/`enable`、Docker load/tag/remove、Compose/env 改写、Broker/Manager/HA stop/start/restart、证书动作、DynSec mutation、Broker target apply、reboot/power-loss、merge/release。
  - 任一 live authority、服务健康、transaction、Broker state root metadata、capacity、artifact binding 与冻结输入不一致时，B8 `STOP`；不得现场修复以换取 PASS。
  - B9 live mutation、B10 reboot/power-loss、B11 live acceptance/rollback mutation、B12 merge/release 都需要各自适用的新授权或用户决定。
- 授权状态：

```text
AUTHORIZATION=N3W_T1_BROKER_OTA_B8_REAL_T1_READONLY_PREFLIGHT_20261121_01
GRANTED=true
CLAIMED=false
CONSUMED=false
REPLAY_PERMITTED=true_WITHIN_B8_READONLY_SCOPE_UNTIL_GATE_CLOSE_OR_AUTHORITY_DRIFT
TARGET=REAL_T1_PRODUCTION_HOST_READONLY_PRECHECK
CANDIDATE_TARGET_ARTIFACT_ID=14713718457
CANDIDATE_RECOVERY_SUPPORT_ARTIFACT_ID=14714301747
LIVE_MUTATION_AUTHORIZED=false
REBOOT_AUTHORIZED=false
MERGE_AUTHORIZED=false
RELEASE_AUTHORIZED=false
```

## 5. 下一步

- 行动：
  1. 新会话 fresh rebind `main`、PR #820、current state/index、B7 closure、frozen target manifest 与两个 B8 candidate artifacts；确认 executable source blobs 相对 `dbc4f1ca...` 无漂移。
  2. 进入 `N3W_T1_BROKER_OTA_B8_REAL_T1_READONLY_PREFLIGHT_20261121_01`。只读核对真实 T1：系统/平台、三服务健康、Broker exact predecessor/image/listener、binding mode、transaction state、Broker writable state root metadata/required files/size、free-space capacity、certificate lifecycle guard/owner、后续安装父路径与 systemd 前提。
  3. 将 B8 结果归档到 GitHub；只在全部 PASS 后输出 B9 live-mutation preauthorization proposal。B8 不安装、不 staging、不 stop service。
- B8 完成条件：
  - exact repository/candidate rebind PASS；
  - real T1 predecessor/runtime/binding/platform PASS；
  - Broker/Manager/HA healthy + production identity/listener uniqueness PASS；
  - no active/unresolved upgrade transaction PASS；
  - Broker state root/required state metadata PASS，capacity preflight PASS；
  - certificate lifecycle conflict check PASS；
  - both frozen candidate artifacts available/exact/non-expired PASS；
  - `T1_MUTATION=false`、`SERVICE_RESTART=false`、`BROKER_LIVE_APPLY=false`。
- 失败／停点：任一 mismatch 均 `STOP_B8_READONLY_PREFLIGHT`，保存脱敏证据并回到高层判断；不得自动进入 B9。

### 后续任务链路（仅规划，不等于授权，也不改变 NEXT_ONE_GATE 唯一性）

```text
B8  REAL_T1_READONLY_PREFLIGHT
 -> PASS
B9  LIVE_MUTATION_PREAUTH + Recovery Support install/enable + exact Broker 2.1.4 apply
     （实际执行前必须冻结 fresh rollback authority，并取得明确 live-mutation 授权）
 -> PASS
B10 CONTROLLED_REBOOT / HOST-RESTART / POWER-LOSS_RECOVERY_ACCEPTANCE
     （单独 reboot/power-loss 授权；证明主机自动接管同一 durable transaction）
 -> PASS
B11 POST_UPGRADE_BUSINESS_CONTINUITY_AND_FAILURE_RECOVERY_ACCEPTANCE
     （按 V1.2 第 6/9/10 节：实际运行身份、受影响收数链路、合法 DynSec application identity、真实 rollback/恢复样本；需要 mutation 时另授权）
 -> PASS
B12 FINAL_BROKER_OTA_CLOSURE + STACK_INTEGRATION / MERGE / RELEASE_DECISION
     （只做最终复核与候选收敛；merge/release 必须用户另行明确批准）
```

如果 B9–B11 过程中出现 executable source change，必须重新生成并绑定 Recovery Support exact package；如果 target image/manifest identity 改变，则必须重新走 B6 exact target freeze，不得继承旧 B8/B9 授权。

## 6. 必读定位与归档

- 仓库规则：先读根 `AGENTS.md`；按其要求读 `docs/skills/greenhouse-github-development-efficiency/SKILL.md`、`docs/development/local-ai-task-splitting-rules.md`、`docs/development/development-artifact-archive-rules.md`、`docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`。按 `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set` 恢复最小读取集；本任务同时关注 §14 T1_Core_Stack authority layering 与 §15 dual-T1 roles。
- 任务资料：
  - `docs/development/N3W_CURRENT_STATE.md` 顶部 B6/B7 authority；
  - `docs/development/N3W_CURRENT_STATE_INDEX.md` 顶部 B6/B7/B8 索引；
  - `docs/development/N3W_T1_BROKER_OTA_V1_0_B7_INDEPENDENT_SOURCE_REVIEW_AND_B8_CANDIDATE_CLOSURE_20261121.md`；
  - `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md` §1/3/5/6/9/10/11；
  - `infra/n3w-t1/upgrades/broker-2.1.4.json`；
  - `tools/n3w_t1_core_updater_v2.py`、`tools/n3w_t1_core_updater_broker_recovery.py`、`tools/n3w_t1_core_updater_broker_support.py`；
  - `infra/n3w-t1/systemd/n3wfc4-core-updater-broker-recovery.service`；
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` 中 KF-100、KF-102。
- 已归档：PR #820 以及上述 B6/B7 closure、current state/index、CI runs 和 artifacts；本 handoff 提交后即为新对话入口。
- 未归档重要资料：无。私有 T1 地址、凭据、原始 DynSec 内容、证书私钥等从未进入公开 handoff。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：

> 阅读本交接和适用仓库指令，fresh rebind `main`、PR #820、`N3W_CURRENT_STATE.md` / `N3W_CURRENT_STATE_INDEX.md`、B7 closure 与 frozen B8 artifacts。继续“温室环境监测系统（ESP32-C6）”N3-W T1 Core Stack OTA V1.2。当前唯一 gate 是 `N3W_T1_BROKER_OTA_B8_REAL_T1_READONLY_PREFLIGHT_20261121_01`；本交接已记录用户对 B8 真实 T1 只读预检的明确 gate-entry 授权。先执行 B8 fresh read-only preflight，严禁任何 T1 写入、Recovery Support 安装/enable、Docker load、服务启停、Broker apply、reboot/power-loss、merge/release。若需要访问 T1，请给出可直接复制的 Mac Terminal 只读命令，由用户执行并回传。B8 PASS 后只归档并准备 B9 preauthorization，不得自动进入 B9。
