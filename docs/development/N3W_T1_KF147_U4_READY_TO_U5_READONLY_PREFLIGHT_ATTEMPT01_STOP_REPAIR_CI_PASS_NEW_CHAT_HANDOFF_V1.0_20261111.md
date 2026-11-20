# N3-W T1 KF-147 U4 Ready → U5 Read-only Preflight Attempt 01 Stop / Repair CI Pass
# 新会话交接文档 V1.0 — 2026-11-11

`HANDOFF_TEMPLATE_VERSION=1.4`

> 本交接按 main 上正式 V1.4 模板生成。PR #807 分支内的模板副本仍为旧版本，禁止用于新的 formal handoff。
> V1.4 authority: main commit `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`, template blob `885fd63131e80936e5e1fe907378be08a0060f12`.

## 1. 目标与停点

- 任务／交接原因：继续“温室环境监测系统（ESP32-C6）”N3-W 的 KF-147 Mandatory USB Home Assistant OTA 收口。本轮完成 R5/R6 恢复、Home Assistant 2026.10.4 USB 目标下载与 U4 验证、U5 bounded install-intent 产品源码、独立只读资格预检包、Attempt 01 失败定位与修复、以及修复后 exact CI 闭环。用户明确要求停止继续推进并生成交接。
- 已完成到：
  - R5 已完成精确 `n3w-update` 权限修复；R5 一次性授权已消费且不可重放；
  - R6 已激活 mounted-root resume 产品修复并重启 OTA service；R6 本地 executor 因重启后的 Docker IPC readiness race 终止，但后台 OTA worker 随后成功继续；R6 一次性授权已消费且不可重放；
  - 实机最后一次成功核对已到 `U4_READY_TO_INSTALL / ACTIVE`，目标归档已验证；
  - U5 产品源码已实现 bounded install intent：重新验证同一绑定 USB、精确目标归档和当前 admission，只允许 U4→U5，停止在 U6 之前，不认领 U9 destructive authorization；
  - 独立 U5 read-only eligibility preflight 已实现并 fail-closed；
  - U5 preflight Attempt 01 已执行，因内嵌远端脚本缺少 `base64` 导入而 `STOP / RC=2`；未发生远端暂存、源码、USB 或 Home Assistant 修改，未认领或消费授权；
  - 缺失导入已修复，已加入真实运行时回归测试；本地干净验证和修复后 CI 全部通过；
  - 修复后的 Attempt 02 **未执行**。
- 当前状态：`STOPPED_BY_USER_BEFORE_U5_READONLY_PREFLIGHT_ATTEMPT02`。只有收到新的用户恢复指令后，才可先做 fresh rebind，再考虑执行修复后的独立只读 Attempt 02。当前尚未到达 `FRESH_EXPLICIT_U5_INSTALL_AUTHORIZATION_REQUIRED`，因为修复后的 U5 eligibility preflight 尚未 PASS。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR state at source handoff: OPEN / DRAFT / MERGEABLE / not merged
  - PR base: `fix/kf147-post-destructive-stop-readonly-forensic-20261110`
- 核对时 main／本任务源码：
  - main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - U5 product source commit: `15b9d50ea2cbf98eeec220d0f1844fe68485d3c0`
  - U5 read-only preflight package commit: `33786bc17e4fdd702201473daec3238b90feccb9`
  - retired Host-A1 authority alignment: `8162c31a7d72327cedfbe976cb3d8c72c06473f9`
  - Attempt 01 repair and exact source authority head: `7a641462f321fd5d738eff78624d675839c0a63d`
  - 本交接文档允许作为 `7a641462...` 之后的 docs-only advance；新会话必须 fresh rebind PR HEAD，并确认从 source authority head 到新 HEAD 只有交接／归档类变更，不能把 docs-only HEAD 误当成新的产品源码 authority。
- U5 exact source blobs：
  - `tools/n3w_t1_core_updater_ha_prepare.py` = `9ca7f0411a9e45d488e6cba4a3526bfaa7c77e20`
  - `tools/n3w_t1_core_updater_ha_prepare_host.py` = `85f0765050c025f3d68a5667fda0d4772b4f15a6`
  - `tools/n3w_t1_core_updater_ha_ipc.py` = `ebd71331eaef4ef5a9fb76a130a66c714370d92e`
  - `tools/execution_packages/n3w/r7a/kf147_u4_to_u5_install_intent_preflight/executor.py` = `948621386d869b28a7fad072cb3b857205465d44`
  - `tools/execution_packages/n3w/r7a/kf147_u4_to_u5_install_intent_preflight/manifest.json` = `8e29f1c64489104dfe94866b7a8a6a364552c490`
  - `tests/tools/test_n3w_t1_kf147_u4_to_u5_install_intent_preflight.py` = `9c353c4166c420a15314e7a7887822a597fd939d`
- 证据入口：
  - R6 failure/activation archive: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6784810427
  - R6 successor diagnosis archive: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6784842194
  - U4 download closure: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6785491869
  - U5 source/CI boundary archive: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6785700473
  - U5 preflight Attempt 01 failure and repair: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6795599418
  - final local/GitHub alignment and explicit stop: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6795870643
- 修复后 CI authority：
  - Target-binding run `43019235001`: SUCCESS
    - `source` = SUCCESS
    - `exact-binding` = SUCCESS
    - https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43019235001
  - Manager A-to-B run `43019234910`: SUCCESS
    - `source` = SUCCESS
    - `exact-manager-slice` = SUCCESS
    - `pre-u1-v2-simulation` = SUCCESS
    - https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43019234910
  - fast source/exact closure、public repository safety、storage headroom 及 applicable scoped CI 均为 SUCCESS。

## 3. 必须继承的结论

- 已证实：
  - 实机最后一次成功 U4 观察为 `U4_READY_TO_INSTALL / ACTIVE`，`target_artifact_verified=true`，`usb_capacity_verified=true`；
  - U4 transaction file SHA256 为 `dc6252c231269582233065558bdd21f7b52307a6e06b7d0104e594689853f259`；
  - 目标归档 `homeassistant-arm64.tar.gz` 大小为 `835309535` bytes，SHA256 为 `eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973`；
  - 实机最后一次成功 IPC 观察为 `READY_TO_INSTALL`，`error_code=null`，installed version 为 `2026.10.0`；
  - 最后一次成功 U4 观察时 OTA service active/running，Manager、Home Assistant、Broker 均 running 且 restart count 为 0；
  - R5、R6 及更早已消费的一次性授权不可重放；
  - U5 产品源码只存在于 PR 分支，尚未部署到 T1；实机仍运行 U4 predecessor source；
  - Attempt 01 已建立 T1 SSH session 并调用只读远端脚本，但脚本在读取状态前因 `NameError:name 'base64' is not defined` fail-closed；
  - Attempt 01 的结果明确为 remote staging=false、host source mutation=false、USB mutation=false、Home Assistant mutation=false、authorization claimed=false、authorization consumed=false；
  - `base64` 导入修复、exact executor blob 更新和运行时回归测试均已在 `7a641462...` 完成；本地干净结果 `31 passed`，修复后 source/exact CI 全部 SUCCESS。
- 待确认：
  - U4 transaction、目标归档、USB 绑定、service、containers 和 IPC 必须由 Attempt 02 fresh revalidate；Attempt 01 没有完成这些远端状态读取，不能把历史 U4 观察当成 Attempt 02 PASS；
  - operator-local T1 网络 locator 在本轮因临时路由器发生变化；未来不得假定历史私网地址，必须从用户私有上下文重新取得并使用严格 known-hosts 绑定；
  - 修复后的 preflight 是否在实机返回 `u5_intent_eligible=true` 仍为 UNKNOWN，直到 Attempt 02 实际 PASS。
- 已排除：
  - Attempt 01 消费 U5 live authorization；
  - Attempt 01 修改源码、USB、目标归档或 Home Assistant；
  - Attempt 01 已建立 U5 eligibility；
  - CI 失败或制品绑定漂移作为当前阻塞原因；
  - 任何 R5/R6/旧 authorization replay；
  - 把“CI SUCCESS”解释为 U5 实机安装授权。

## 4. 执行范围与授权

- 可继续：
  - 当前已按用户要求停止；没有自动继续权限；
  - 未来收到新的用户恢复指令后，可做 repository/PR/CI/source read-only fresh rebind；
  - fresh rebind 无漂移后，可执行修复后的独立 **U5 read-only eligibility preflight Attempt 02**；
  - 可归档 Attempt 02 的 public-safe 结果。
- 暂停边界：
  - 不得在本交接后自动执行 Attempt 02；
  - 不得部署 U5 product source；
  - 不得重启 OTA service；
  - 不得执行 U4→U5 transition；
  - 不得修改、卸载、格式化、重分区或清理 USB；
  - 不得修改 Home Assistant、Manager 或 Broker；
  - 不得进入 U6+ 或 U9 destructive phase；
  - 不得访问板卡；
  - 不得合并 PR #807。
- 授权状态：
  - R5/R6：CLAIMED=true / CONSUMED=true / REPLAY_PERMITTED=false，均已退役；
  - U5 read-only Attempt 01：已执行并 STOP，不涉及 live authorization claim/consume；
  - U5 live execution authorization：NOT GRANTED；
  - U5 authorization claimed=false / consumed=false / replay_permitted=false；
  - U5 manifest 仍为 fail-closed：`live_execution_authorized=false`、authorization granted/claimed/consumed 均为 false；
  - 本 handoff 不授予 Attempt 02、U5 live mutation、U6+、destructive action、merge 或 deployment 权限。

## 5. 下一步

- 行动：
  1. 等待用户新的明确恢复指令；在此之前不做任何执行；
  2. fresh rebind main、PR #807、source authority head `7a641462f321fd5d738eff78624d675839c0a63d` 和当前 PR HEAD；
  3. 确认 run `43019235001`、`43019234910` 仍为 SUCCESS，且 docs-only advance 没有改变 U5 source/package authority；
  4. 从用户私有上下文 fresh bind 当前 T1 SSH locator、严格 known-hosts 和既有可信 host key；不要把私网地址或原始设备身份写入公共 GitHub；
  5. 独立复核 U5 executor/manifest/test，确认仍为 preflight-only、read-only、ungranted；
  6. 只有用户恢复后，执行 Attempt 02，并 fresh verify exact U4 transaction、同一 USB、精确 target、predecessor source、service、containers 和 IPC；
  7. 将 Attempt 02 public-safe 结果归档到 PR #807。
- 完成条件：
  - `status=PASS`；
  - `read_only_preflight=true`；
  - `u5_intent_eligible=true`；
  - U4 transaction、target size/SHA、USB binding、predecessor source、service、containers 和 IPC 全部匹配；
  - authorization claimed/consumed=false/false；
  - remote staging、source/USB/HA/Manager/Broker mutation 均为 false；
  - U6+=false；
  - 证据归档完成。
- 失败／停点：
  - 任一 fresh drift 或 Attempt 02 非 PASS => STOP，只读分类并归档，不修复实机；
  - Attempt 02 PASS => STOP at `FRESH_EXPLICIT_U5_INSTALL_AUTHORIZATION_REQUIRED`；不得自动部署源码、重启服务或执行 U4→U5；
  - 只有未来独立、明确、fresh 的 U5 live authorization 才可能进入后续设计／执行；该授权不能从本交接、CI SUCCESS 或 read-only PASS 推导。

## 6. 必读定位与归档

- 仓库规则：
  - repository applicable instructions；
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`；
  - [工作上下文的 minimum new-chat read set](N3W_PROJECT_WORKING_CONTEXT.md#12-minimum-new-chat-read-set)；
  - 使用 main commit `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d` 的 V1.4 template authority，不使用 PR #807 分支中的旧模板副本。
- 任务资料：
  - 本交接；
  - `docs/development/N3W_T1_KF147_R4_TERMINAL_TO_R5_READONLY_PREFLIGHT_NEW_CHAT_HANDOFF_V1.0_20261111.md` — R4→R5 前置链路；
  - `docs/development/N3W_T1_KF147_U3_BOUND_MEDIA_RECOVERY_AND_ERROR_VISIBILITY_SOURCE_DESIGN_20261110.md` — R5/R6 根因与产品修复依据；
  - `tools/n3w_t1_core_updater_ha_prepare.py`、`tools/n3w_t1_core_updater_ha_prepare_host.py`、`tools/n3w_t1_core_updater_ha_ipc.py` — bounded U5 product source；
  - `tools/execution_packages/n3w/r7a/kf147_u4_to_u5_install_intent_preflight/executor.py` — Attempt 02 read-only execution contract；
  - `tools/execution_packages/n3w/r7a/kf147_u4_to_u5_install_intent_preflight/manifest.json` — exact U4/U5 eligibility and authorization boundary；
  - `tests/tools/test_n3w_t1_kf147_u4_to_u5_install_intent_preflight.py` — preflight regression guards；
  - `docs/development/N3W_CURRENT_STATE.md`、`docs/development/N3W_CURRENT_STATE_INDEX.md`、`docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` — 仅按 KF-147/U5 相关条目补读，不得让历史状态覆盖 fresh PR #807 evidence。
- 已归档：
  - PR #807 comments 和 CI runs 已在第 2 节列出；
  - U4 exact target evidence、Attempt 01 failure、repair、CI closure 和 explicit stop 均已 public-safe 归档。
- 未归档重要资料：
  - 无。operator-local SSH locator、known-hosts、host key binding 和临时 evidence directory 属于私有操作上下文，故意不进入公共 GitHub；未来必须 fresh 获取，不视为可继承的公共执行 authority。

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：

```text
阅读：
docs/development/N3W_T1_KF147_U4_READY_TO_U5_READONLY_PREFLIGHT_ATTEMPT01_STOP_REPAIR_CI_PASS_NEW_CHAT_HANDOFF_V1.0_20261111.md

同时按需读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_T1_KF147_U3_BOUND_MEDIA_RECOVERY_AND_ERROR_VISIBILITY_SOURCE_DESIGN_20261110.md

交接模板 authority 使用 main commit：
3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
中的 V1.4；不要使用 PR #807 分支上的旧模板副本。

fresh rebind：
- repository main
- PR #807
- U5_SOURCE_AUTHORITY_HEAD=7a641462f321fd5d738eff78624d675839c0a63d
- target-binding CI run 43019235001
- Manager A-to-B CI run 43019234910

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

当前状态：
STOPPED_BY_USER_BEFORE_U5_READONLY_PREFLIGHT_ATTEMPT02

只有收到新的用户恢复指令后，才可进入：
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_KF147_U4_TO_U5_INSTALL_INTENT_R7_READONLY_PREFLIGHT_ATTEMPT02

本轮边界：
LIVE_EXECUTION_AUTHORIZED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
SOURCE_DEPLOYMENT=false
SERVICE_RESTART=false
U4_TO_U5_TRANSITION=false
USB_MUTATION=false
HOMEASSISTANT_MUTATION=false
MANAGER_MUTATION=false
BROKER_MUTATION=false
U6_PLUS=false
BOARD_ACCESS=false
MERGE=false

先 fresh rebind exact U5 executor/manifest/test、CI 和 operator-local SSH identity，再执行 preflight-only。
Attempt 02 PASS 后停止在 FRESH_EXPLICIT_U5_INSTALL_AUTHORIZATION_REQUIRED，不自动进入 U5 live。
R5、R6 及所有已消费 authorization 均不得 replay。
```
