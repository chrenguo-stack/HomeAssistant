# N3-W T1 U9+ Phase-A restart-convergence repair CI PASS → live revalidation preflight
# 新会话交接文档 V1.0 — 2026-11-20

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：继续 T1_Core_Stack OTA Phase-A 自动回滚验收。本轮完成了 `a103...` 实机再验证、发现并证明 restart-convergence completion-oracle 假失败、实施最小源码修复、补回归测试、exact manifest rebind，并将最终源码/CI 闭合。因当前对话链路已较长，切换新会话继续下一次只读实机预检。
- 已完成到：真实 T1 仍 durable `U13B_ROLLED_BACK / ROLLED_BACK`，业务 runtime 健康；restart-convergence repair source/test/manifests exact；CI-closed head `3d74881e3bfadbecd23721f8c9d500f95ef69696` 为 22/22 workflow SUCCESS；Current State / Index / KF-168 / closure archive 已对齐 GitHub。
- 当前状态：**可继续只读 preflight**。Phase-A overall 仍为 `NOT_YET_PASS`，因为 repaired blob `437f3e6c...` 尚未安装到 live candidate；任何新的 candidate replacement / OTA restart 仍需 separate explicit authorization。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR state: OPEN / DRAFT / unmerged
- 核对时 main／本任务源码：
  - default main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - final source-CI authority head: `3d74881e3bfadbecd23721f8c9d500f95ef69696`
  - source repair commit: `f8fc67cff39a0b2831a3005ae00d0556fce8351a`
  - repaired U13B-host blob: `437f3e6c4cae53f7d94e244cd312ac454768f8e1`
  - regression test blob: `9ca455c79204632e396530c0e40f654957da2caf`
  - P3 manifest blob: `fcb8ecd4dd4f68a7fef5c64abe627cedc32dbca7`
  - Phase-A manifest blob: `2ba6e96aec0f41f7916c852cef37c3fce9ecb966`
  - post-CI docs alignment commits: `d5b9891d...`, `88cd2a41...`, `4ac60992...`, `67b92010...`; these are documentation/state alignment only and do not redefine the product-source authority.
- 证据入口：
  - source/CI closure: `docs/development/N3W_T1_U9_PLUS_PHASE_A_RESTART_CONVERGENCE_SOURCE_CI_CLOSURE_20261120.md`
  - previous live progress archive: `docs/development/N3W_T1_U9_PLUS_PHASE_A_A103_LIVE_REVALIDATION_RESTART_RACE_SOURCE_REPAIR_PROGRESS_20261120.md`
  - current state: `docs/development/N3W_CURRENT_STATE.md`
  - current index: `docs/development/N3W_CURRENT_STATE_INDEX.md`
  - KF-168: `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`
  - product source: `tools/n3w_t1_core_updater_ha_u13b_host.py`
  - regression: `tests/tools/test_n3w_t1_u13b_host.py`
  - P3 manifest: `tools/execution_packages/n3w/r7a/u13b_p3_live_to_u11/manifest.json`
  - Phase-A manifest: `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/u9plus_fault_acceptance_manifest.json`
- Final CI on `3d74881e...`: `22 SUCCESS / 0 FAILURE / 0 PENDING`.
  - fast source/exact: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694858559
  - P3 acceptance source: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694858598
  - P3 live/read-only source: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694858532
  - Core Stack authority: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694858575
  - Manager A-to-B: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694858647
  - HA 2026.10.4 target binding: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694858704
  - same-version acceptance artifact: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694859200
  - public repository safety: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694858521

## 3. 必须继承的结论

- 已证实：
  - durable Host = `U13B_ROLLED_BACK / ROLLED_BACK`;
  - business runtime settled healthy: services owner active, Broker owner active, Manager/Home Assistant/Broker = 1/1/1, exact listeners, Manager + HA MQTT authenticated, HA HTTP=401;
  - live Home Assistant remains bound to predecessor `local/n3w-homeassistant:2026.10.4-5881590f`;
  - current live candidate U13B-host blob = `a103a2633aaea5a34efbfed35449b2eb5bace61b`;
  - current live IPC = `ERROR / u13b_predecessor_runtime_not_running`;
  - this is a restart-ordering false failure, not business recovery failure: OTA daemon started at 15:08:48 CST, services owner at 15:08:50, Manager/HA at 15:08:51;
  - root cause: `verify_predecessor_health()` raised before entering its existing readiness loop;
  - minimal repair `437f3e6c...` removes only the premature pre-loop runtime hard failure; final strict runtime/identity/overlay/listener/MQTT/HTTP checks remain;
  - source, regression, exact manifest rebind and 22/22 CI all PASS.
- 待确认：
  - fresh live T1 still has durable Host U13B terminal and healthy settled runtime;
  - candidate daemon override remains active;
  - live U13B-host file is still exact `a103a263...` and has not already moved to `437f3e6c...`;
  - IPC still reports the known old-candidate terminal `u13b_predecessor_runtime_not_running`;
  - only after a later separately authorized `437f...` replacement + one restart can live completion be expected to reach `ROLLED_BACK`.
- 已排除：
  - previous manual preflight `services_supervision_contract_drift` was probe error from using generic `LocalHost.inspect_v2()` instead of the U13B/U11 overlay supervision contract;
  - previous `ota_status_rejected` was probe error from root UID=0 accessing an IPC socket that requires Manager UID/GID 999;
  - original socket-uniqueness blocker `u9_plus_completion_ha_mqtt_socket_ambiguous` was repaired by `a103...` and did not recur after its live installation;
  - current blocker is not T1 business-runtime outage.

## 4. 执行范围与授权

- 可继续：
  - fresh repository/main/PR/source/manifest/CI rebind;
  - source review and read-only checks;
  - GitHub archival;
  - exactly one read-only next gate: `N3W_T1_U9_PLUS_PHASE_A_RESTART_CONVERGENCE_REPAIR_LIVE_REVALIDATION_PREFLIGHT`.
- 暂停边界：
  - do not replace the live candidate file with `437f3e6c...`;
  - do not restart `n3w-t1-ha-ota.service`;
  - do not mutate Host/USB transaction;
  - do not replay U9;
  - do not rerun destructive U10;
  - do not enter U11+;
  - do not overwrite production `/opt/HomeAssistant` source;
  - do not merge PR #807.
- 授权状态：
  - original Phase-A U9 authorization: consumed / no replay;
  - `a103...` single-file replacement + one OTA restart authorization: consumed / no replay;
  - `437f3e6c...` live retry authorization: **NOT_GRANTED**;
  - handoff itself grants no new live mutation permission.

Private T1 locator / SSH / host-key material remains outside public GitHub. The next session should recover it only from private context when needed.

## 5. 下一步

- 行动：
  1. read this handoff and the minimum project read set;
  2. fresh-rebind main, PR #807, branch head, exact `437f...` source/test/P3/Phase-A manifest blobs and CI-closed head;
  3. execute only `N3W_T1_U9_PLUS_PHASE_A_RESTART_CONVERGENCE_REPAIR_LIVE_REVALIDATION_PREFLIGHT` as a true read-only T1 gate;
  4. use the U13B/U11 overlay supervision contract, not generic `LocalHost.inspect_v2()`;
  5. query OTA IPC as Manager UID/GID 999, not root UID 0;
  6. require durable Host U13B, healthy runtime, active candidate override, exact live `a103...` binding and expected IPC error;
  7. if preflight PASS, **stop** and request explicit authorization before any exact `437f...` single-file replacement + one OTA restart.
- 完成条件：
  - next gate itself completes read-only with no T1 mutation;
  - fresh live baseline is exact and no new drift/blocker is found;
  - after a later separately authorized live retry, expected completion is `IPC_PHASE=ROLLED_BACK`, `error_code=null`, while durable U13B and business runtime remain healthy;
  - only then may Phase-A overall be recorded PASS.
- 失败／停点：
  - any source/manifest/runtime drift => stop affected operation and diagnose read-only;
  - do not convert observer/probe mistakes into product failures;
  - no blind second restart after any future live error;
  - after Phase-A PASS, stop before Phase B; continuous downtime/SLA acceptance remains a separate stage.

## 6. 必读定位与归档

- 仓库规则：
  - applicable repository `AGENTS.md`;
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md` and §12 minimum new-chat read set;
  - formal handoff template authority: `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4, blob `885fd63131e80936e5e1fe907378be08a0060f12`.
- 任务资料：
  - this handoff;
  - `docs/development/N3W_CURRENT_STATE.md` latest 2026-11-20 entry;
  - `docs/development/N3W_CURRENT_STATE_INDEX.md` latest 2026-11-20 entry;
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` latest KF-168 update;
  - closure/progress archives in §2;
  - exact source/test/manifests in §2.
- 已归档：
  - restart-convergence live false-failure evidence;
  - source repair and regression;
  - P3 + Phase-A exact rebind;
  - final 22/22 CI;
  - Current State / Index / KF-168 closure state;
  - this formal handoff.
- 未归档重要资料：无。Private runtime locators/credentials intentionally remain outside public GitHub.

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：

```text
阅读《docs/development/N3W_T1_U9_PLUS_PHASE_A_RESTART_CONVERGENCE_REPAIR_CI_PASS_TO_LIVE_REVALIDATION_PREFLIGHT_NEW_CHAT_HANDOFF_V1.0_20261120.md》。

同时按交接“必读定位与归档”读取适用仓库规则、N3W_PROJECT_WORKING_CONTEXT、N3W_CURRENT_STATE、N3W_CURRENT_STATE_INDEX、KF-168，以及 exact source/test/manifests。

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

先 fresh rebind：
- main
- PR #807
- branch fix/kf147-u3-recovery-and-error-visibility-20261110
- CI_CLOSED_HEAD=3d74881e3bfadbecd23721f8c9d500f95ef69696
- repaired U13B-host blob=437f3e6c4cae53f7d94e244cd312ac454768f8e1
- test blob=9ca455c79204632e396530c0e40f654957da2caf
- P3 manifest=fcb8ecd4dd4f68a7fef5c64abe627cedc32dbca7
- Phase-A manifest=2ba6e96aec0f41f7916c852cef37c3fce9ecb966
- final CI=22/22 SUCCESS

然后只进入：
NEXT_ONE_GATE=N3W_T1_U9_PLUS_PHASE_A_RESTART_CONVERGENCE_REPAIR_LIVE_REVALIDATION_PREFLIGHT

本 gate 只读。
U13B supervision 必须使用 U11 overlay contract。
IPC status 必须以 Manager UID/GID 999 查询。

禁止：
- candidate source replacement
- OTA restart
- U9 replay
- destructive U10 replay
- Host/USB transaction mutation
- U11+
- production source overwrite
- merge

如果 read-only preflight PASS，停止在新的 live retry authorization boundary，再决定是否执行 exact 437f 单文件替换 + one OTA restart。
```
