# N3-W T1 OTA V1.2 R8 Attempt 03 PASS → 既有事务架构续接交接

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：继续“温室环境监测系统（ESP32-C6）”项目 N3-W 的 T1 Core Stack OTA V1.2；当前目标是完成备用 T1 的 R8 单版本 Home Assistant 代表性验收。因本会话在 Attempt 03 PASS 后曾短暂偏离 V1.2，开始设计一套平行 predecessor-switch 状态机，现已复核并停止该路线。新会话从已证实的 Attempt 03 PASS 停点恢复，严格复用 V1.2 既有持久事务、T1_Core_Updater 和 HA U0–U13 / recovery primitives，不再创建第二套产品事务框架。
- 已完成到：
  - 备用 T1 当前 Home Assistant `2026.10.4` 健康基线已只读核对；
  - PR #822 的 isolated bound-USB Attempt 03 已实机 PASS；
  - 当前 `2026.10.4` 回退镜像归档和受保护 HA 数据备份已重新验真；
  - 宿主命名空间在验证前后均保持 U 盘未挂载，独立命名空间使用 `ro,norecovery`；
  - R8 容量判断仍冻结为“释放旧镜像后、下一次导入前重新实测”，当前约 4.75 GB 仅为释放前观察值；
  - 已复核正式 `2026.10.0 → 2026.10.4` compatibility review：`persistent_schema_compatible=true`、`rollback_compatible_source_review=true`，目标清单 `rollback_compatible=true`；
  - 已识别并停止错误 successor 路线：独立 `r8-predecessor-switch` 状态机不得作为 R8 产品执行权威。
- 当前状态：`可继续`。下一步只做源码/架构 rebind 与最小实现设计；不需要先访问 T1。任何实机写入、停服、Docker 镜像删除/导入、U 盘写入、断电测试前都必须重新核对对应明确授权。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - PR #821: `https://github.com/chrenguo-stack/HomeAssistant/pull/821`
  - PR #822: `https://github.com/chrenguo-stack/HomeAssistant/pull/822`
  - PR #822 branch: `review/t1-ota-r8-spare-preflight-20261122`
- 核对时 main／本任务源码：
  - `MAIN=4fde1b7c5cc0aa224fa3574b8b4cc638edd93647`
  - `PR821_HEAD=eac5794afbeef265dee0f5f60d5e5223de111e35`
  - `PR822_ATTEMPT03_SOURCE_HEAD=ba01d2d6d65d71cfbbb5cd54c397646dfee0cc63`
  - PR #822 base = PR #821 exact head。
  - 本交接为 docs-only advance；新会话必须 fresh rebind PR #822 current head，并确认除交接/归档外无新的产品源码漂移。
- 证据入口：
  - `docs/development/N3W_T1_OTA_V1_2_R8_SPARE_READONLY_PREFLIGHT_PHYSICAL_EVIDENCE_20261122.md`
    - 读取 “Isolated bound-USB verification Attempt 03”；
  - R8 focused CI run: `45031849491`，focused job / compile / tests 均 SUCCESS；
  - V1.2 产品架构：`docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md`
    - 重点读取第 3–7 节、第 9–10 节、附录 A R7/R8；
  - 兼容性权威：
    - `infra/n3w-t1/upgrades/homeassistant-2026.10.4-compatibility-review.json`
    - `infra/n3w-t1/upgrades/homeassistant-2026.10.4.json`
- 关键实机证据：
  - current HA: `local/n3w-homeassistant:2026.10.4-5881590f`
  - current version: `2026.10.4`
  - baseline: `RUNNING_BASELINE_PASS`
  - HA restart count: `0`
  - transactions stable: `true`
  - bound USB: `/dev/sda1`, ext4, transaction bound
  - USB host mount before/after Attempt 03: `false/false`
  - isolated mount: `ro,nosuid,nodev,noexec,relatime,norecovery`
  - current rollback image archive SHA-256: `31108a725e6b6530c68834218d9e41579055d7fe2718b3f42902b71237dc8e5f`
  - current rollback image archive size: `743051918`
  - protected backup SHA-256: `b6f7ad3803c1ae954d2d946562b5ae1db8725786e4c457db8a1deff7b10623e2`
  - protected backup manifest SHA-256: `1cf39dad34b36b8901c24151cc7d4b3ec6fa09b25264f6812c3a9e51569409ac`
  - pre-release internal available bytes at Attempt 03: `4754415616`
  - exact `2026.10.0` image currently resident on spare T1: `false`
- 精确 `2026.10.0` operator-side image authority：
  - image ref: `local/n3w-homeassistant:2026.10.0-0c73235a`
  - image ID: `sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879`
  - archive size: `2448553472`
  - archive SHA-256: `e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663`
  - platform: `linux/arm64`

## 3. 必须继承的结论

- 已证实：
  - Attempt 03 = `PASS`。当前绑定 U 盘包含经过重新验真的、事务绑定的 `2026.10.4` 回退镜像与受保护 HA 数据备份。
  - U 盘验证过程没有 T1 runtime、Docker、服务、USB 写入或格式化；宿主命名空间前后均未挂载该盘。
  - 释放前内部余量 `4754415616` bytes 不是 R8 容量 PASS/FAIL。容量 authority 仍是：
    `CAPACITY_DECISION_POINT=AFTER_RELEASE_BEFORE_NEXT_IMPORT`。
  - 正式 compatibility review 明确绑定 predecessor `2026.10.0` 与 candidate `2026.10.4`，三个核心 HA storage contract 版本一致，并给出 `persistent_schema_compatible=true`、`rollback_compatible_source_review=true`；目标清单给出 `rollback_compatible=true`。
  - 因此，“必须先找到一份历史 2026.10.0 数据备份”不再是这个 exact 10.0↔10.4 对的源码级硬前置。实际 10.0 前代基线如何由既有 V1.2 事务/恢复原语准备，仍需下一 gate 完成最小设计与实现复核。
  - V1.2 的本地主执行权威是既有 T1_Core_Updater / 持久事务 / HA U0–U13 + recovery primitives；T1_Core_Stack OTA 不替代 updater 作为执行器。
- 待确认：
  - 在不新增平行状态机的条件下，现有 V1.2 源码中哪一组既有原语最小组合即可把备用 T1 从当前 10.4 安全准备为 exact 10.0 R8 predecessor baseline；
  - 该准备步骤中“当前数据保护、当前 10.4 镜像释放、释放后容量判断、exact 10.0 导入、10.0 健康确认、失败恢复”的责任分别已由哪些现有模块承担，哪些只是小缺口需要 ADAPT；
  - 下一次实机写入前的 fresh 状态、授权、回滚入口和空间公式必须基于 V1.2 当前代码重新绑定，不继承 scratch successor 的实现。
- 已排除：
  - `review/t1-ota-r8-predecessor-switch-20261122`（当前 scratch head `16462a435e5f380bcfdb38b90a135677452f4eb9`）不得作为产品实现或实机执行权威。其独立 predecessor-switch 状态机、独立事务文件和专用介质布局违反 V1.2 “复用既有持久事务与恢复原语、不维护平行产品状态机”的架构原则。
  - 不得把旧 P5 的固定 `1.5 GiB` 余量常量直接重新定义为新的 R8 容量硬门槛；容量判断必须回到 V1.2/R8 的释放后实测与实际峰值模型。
  - 不得因为新会话或 R8 前代准备而新建第二套 updater、第二套 recovery engine、专用容器或平行状态机。
  - Attempt 01/02 的 `ha_usb_prepared_image_materials_invalid` / `recovery_material_records_unavailable` 已证明为历史 P3 记录格式兼容误判，并由 Attempt 03 实际材料验真 PASS 关闭；不得重新解释为 U 盘损坏。

## 4. 执行范围与授权

- 可继续：
  - fresh rebind repository / PR #821 / PR #822 / main；
  - 读取 V1.2 架构、现有 T1_Core_Updater、HA U0–U13、U9+ recovery、U13B rollback、Generic V2、compatibility review；
  - 源码复核、最小差距分析、局部源码修改、单元/模拟测试、focused CI、GitHub 归档；
  - 目标是在既有 V1.2 事务架构中形成“R8 前代 10.0 准备”的最小实现，不扩大产品架构。
- 暂停边界：
  - `T1_ACCESS`：新会话首先不需要；若后续需要新的只读实机状态，先按当前任务规则核对范围；
  - 以下操作必须在执行前重新核对 exact 授权：服务 stop/start/restart、Docker container/image mutation、删除当前 10.4、导入 10.0、U 盘写入、恢复数据写入、重启/断电、R8 正式 OTA、重要合并/发布；
  - 禁止使用 scratch predecessor-switch branch 作为实机执行包；
  - Broker OTA 仍不在本阶段，继续等 Home Assistant OTA 验收完成后再开发。
- 授权状态：
  - `LIVE_WRITE_AUTHORIZATION=NONE`
  - `T1_MUTATION_AUTHORIZATION=NONE`
  - `USB_WRITE_AUTHORIZATION=NONE`
  - `POWER_CYCLE_AUTHORIZATION=NONE`
  - `MERGE_AUTHORIZATION=NONE`
  - Attempt 03 为只读验证，不产生或消费新的 live-write authorization。
  - 本交接本身不授予任何新权限。

## 5. 下一步

- 行动：
  - `NEXT_ONE_GATE=N3W_T1_OTA_V1_2_R8_EXISTING_TRANSACTION_ARCHITECTURE_PREDECESSOR_PREP_REBIND`
  - 先 fresh rebind：
    1. `main`
    2. PR #821 exact head `eac5794afbeef265dee0f5f60d5e5223de111e35`
    3. PR #822 Attempt 03/source stop head `ba01d2d6d65d71cfbbb5cd54c397646dfee0cc63`；随后仅有本交接 docs-only advance，current head 在新会话 fresh rebind
    4. V1.2 architecture
    5. existing T1_Core_Updater transaction/recovery modules
    6. exact 10.0↔10.4 compatibility authority
  - 只回答一个问题：**如何用现有 V1.2 持久事务与 recovery primitives，以最小增量把备用 T1 准备成 exact 2026.10.0 R8 前代基线？**
  - 将相关现有能力逐项标为 `KEEP / ADAPT / MISSING`，优先复用；禁止创建独立 R8 状态机。
  - 若存在局部、明确、无架构取舍的小缺口，可直接开发、测试、CI、归档；到第一次实机写入边界停止并提交 exact 授权所需输入。
- 完成条件：
  - predecessor preparation 的每个破坏性边界都能映射到 V1.2 已有 transaction/recovery authority；
  - 没有新产品级状态机、没有新 recovery engine、没有新 U 盘产品布局；
  - 当前 10.4 回退 authority 与 exact 10.0 image authority 均被复用；
  - 容量判断仍发生在“旧 HA 镜像实际释放完成后、下一镜像导入前”，公式/峰值需求来自当前 V1.2 实现而非历史 P5 常量；
  - focused tests / CI 对正常路径、容量不足、导入失败、恢复成功/失败至少形成确定性证据；
  - 首次 live mutation 前输出 exact target、source head、rollback authority、fresh baseline、授权 scope；没有用户明确授权则停止。
- 失败／停点：
  - 如果 fresh rebind 发现 PR #821/#822、V1.2 authority 或既有 updater/recovery 源码发生实质漂移，先停止受影响开发并重新分类；
  - 如果最小前代准备必须修改产品级事务模型，停止并回到架构评审，不允许以 scratch branch 继续；
  - 如果 CI 暴露局部明确 bug，可按项目规则直接小修；涉及状态模型、恢复责任、容量策略或 live scope 扩大则暂停；
  - 任一 live-write 授权在未明确批准前，不得跨过实机写入边界。

## 6. 必读定位与归档

- 仓库规则：
  - `AGENTS.md`
  - `docs/skills/greenhouse-github-development-efficiency/SKILL.md`
  - `docs/development/local-ai-task-splitting-rules.md`
  - `docs/development/development-artifact-archive-rules.md`
  - `docs/development/TEAM_COLLABORATION_WORKSPACE_STANDARD.md`
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set`
- 任务资料：
  - `docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md`
    - 第 3–7 节：事务、恢复、验收与 checker 边界；
    - 第 9–10 节：实机代表性验收和发布回归；
    - 附录 A：R7/R8 工程定位；
  - `docs/development/N3W_T1_OTA_V1_2_R8_SPARE_READONLY_PREFLIGHT_PHYSICAL_EVIDENCE_20261122.md`
    - Attempt 03 为当前最新实机只读证据；
  - `infra/n3w-t1/upgrades/homeassistant-2026.10.4-compatibility-review.json`
    - exact 10.0↔10.4 persistent schema / rollback compatibility authority；
  - `infra/n3w-t1/upgrades/homeassistant-2026.10.4.json`
    - target / predecessor / rollback compatible binding；
  - `docs/development/N3W_CURRENT_STATE.md`
    - 只取 V1.2 当前 authority 和仍适用的 T1_Core_Stack 分层规则，历史执行授权不得继承；
  - `docs/development/N3W_CURRENT_STATE_INDEX.md`
    - 用于定位旧 U9/U10/U13B/Generic V2 证据；
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`
    - 重点复用 U7/KF-158、U9/U10/KF-167、KF-168 等“观察器误判不得阻断恢复”和旧记录兼容防护；
  - exact historical handoff process standard（只取仍适用的执行语义）：
    `4300890dff0ce63d5a547df21426e287d084d9ee:docs/development/NEW_CHAT_HANDOFF_STANDARD.md`
  - current formal handoff template：
    `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md`，`HANDOFF_TEMPLATE_VERSION=1.4`
- 已归档：
  - PR #822 Attempt 03/source stop head `ba01d2d6d65d71cfbbb5cd54c397646dfee0cc63`；
  - Attempt 03 physical evidence 已在该 stop head 的 evidence 文档中固定；
  - 本交接为后续 docs-only advance，不改变 Attempt 03 产品源码/实机事实；
  - 本交接文档本身归档到 PR #822 branch。
- 未归档重要资料：无。错误 scratch predecessor-switch 分支已保留为非产品历史材料，但已明确禁止作为后续 authority。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：

> 阅读本交接和适用仓库指令，继续“温室环境监测系统（ESP32-C6）”N3-W。先 fresh rebind main、PR #821、PR #822、V1.2 架构及 Attempt 03 evidence。当前有效停点是 Attempt 03 PASS；不要继续 `review/t1-ota-r8-predecessor-switch-20261122` 的平行状态机路线。下一步只按 V1.2 既有持久事务、T1_Core_Updater、HA U0–U13 / recovery primitives 复核并实现最小的 exact `2026.10.0` predecessor preparation。开发、测试、CI 和 GitHub 归档可连续推进；第一次 T1/USB/Docker/service 写入前停止并核对 exact 授权。
