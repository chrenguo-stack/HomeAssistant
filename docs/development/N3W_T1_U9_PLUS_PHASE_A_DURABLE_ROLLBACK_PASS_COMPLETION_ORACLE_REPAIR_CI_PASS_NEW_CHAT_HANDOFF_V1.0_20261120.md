# N3-W T1 U9+ Phase-A durable rollback PASS / completion-oracle repair CI PASS
# 新会话交接文档 V1.0 — 2026-11-20

`HANDOFF_TEMPLATE_VERSION=1.4`

## 1. 目标与停点

- 任务／交接原因：完成 T1_Core_Stack OTA Phase-A 自动回滚验收。本轮已证明真实 T1 从 U9+ 故障注入路径自动恢复到 durable U13B 并恢复业务；随后定位并修复 customer-completion oracle 的 1883 socket 唯一性假失败。因本轮上下文较长，用户要求在 CI 全绿后切换新会话。
- 已完成到：Host 与绑定 USB 都已进入 `U13B_ROLLED_BACK / ROLLED_BACK`，Host/USB transaction exact；业务 runtime 健康；completion-oracle source repair、回归测试、P3 manifest rebind、Phase-A manifest rebind 已提交，source head `93610f23472759cf1601d2ad82b9b59b7225f4d6` 的 22/22 workflow 全部 SUCCESS。
- 当前状态：可继续源码/只读核对，但**真实 T1 的新 completion-oracle repair 尚未部署**。当前 Phase-A 不能正式标 PASS，因为 live IPC 最后仍是旧 candidate 产生的 `ERROR / u9_plus_completion_ha_mqtt_socket_ambiguous`。

## 2. 代码与证据

- 仓库／分支／PR：
  - repository: `chrenguo-stack/HomeAssistant`
  - branch: `fix/kf147-u3-recovery-and-error-visibility-20261110`
  - PR: https://github.com/chrenguo-stack/HomeAssistant/pull/807
  - PR state: OPEN / DRAFT / unmerged
- 核对时 main／本任务源码：
  - main: `3e7faf258d670c9eaf3be6ede9bbb02df2ac009d`
  - Phase-A source/authority head: `93610f23472759cf1601d2ad82b9b59b7225f4d6`
  - source repair: `ecb2b789c25a7fe2369da74f08c0b7fe2bbce5c3`
  - repaired U13B host blob: `a103a2633aaea5a34efbfed35449b2eb5bace61b`
  - regression test commit: `9c1b257b2024fbafb30ed634e107d17128fe7b96`
  - P3 authority rebind: `14ac4308db81ddf3259027d899a3bd2ae811d651`
  - P3 manifest blob: `8b7f67e7c29dd1b276f4c2dd35218c77c2ee5f54`
  - Phase-A authority rebind: `93610f23472759cf1601d2ad82b9b59b7225f4d6`
- 证据入口：
  - Phase-A plan: `docs/development/N3W_T1_U9_PLUS_BOUNDED_RECOVERY_REAL_T1_FAULT_INJECTION_ACCEPTANCE_PHASE_A_PLAN_20261119.md`
  - completion oracle source: `tools/n3w_t1_core_updater_ha_u13b_host.py`
  - regression tests: `tests/tools/test_n3w_t1_u13b_host.py`
  - Phase-A manifest: `tools/execution_packages/n3w/r7a/u13b_p3_u1_u4_recovery/u9plus_fault_acceptance_manifest.json`
  - key PR evidence comments: #7030304657 readonly preflight PASS; #7030367311 exact U13B-host repair + one OTA restart PASS; #7030673182 strict-health PASS; #7030962534 durable U13B terminal evidence; #7031068237 completion-oracle root cause; #7031091948 source repair/rebind; #7031100834 CI progress.
  - final CI aggregate: 22 SUCCESS / 0 FAILURE / 0 PENDING.
  - key runs:
    - https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44679435059 — fast source/exact closure — SUCCESS
    - https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44679435074 — P3 acceptance clean OTA source — SUCCESS
    - https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44679435028 — P3 live/read-only source — SUCCESS
    - https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44679434989 — HA 2026.10.3 target binding — SUCCESS
    - https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44679435130 — HA 2026.10.4 target binding — SUCCESS
    - https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44679434940 — HA 2026.10.4 same-version artifact — SUCCESS
    - https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44679435008 — Manager A-to-B — SUCCESS
    - https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44679435015 — Core Stack current authority — SUCCESS
  - CI polling record: active polling stopped after 3 checks at 18/22 SUCCESS; user later reported CI SUCCESS and one fresh rebind confirmed 22/22 SUCCESS.

## 3. 必须继承的结论

- 已证实：
  - real T1 durable Host transaction = `U13B_ROLLED_BACK / ROLLED_BACK`;
  - bound USB host transaction and phase document = `U13B_ROLLED_BACK`;
  - Host/USB transaction equality = true;
  - `rollback_recovery_content_verified`, `rollback_predecessor_image_restored`, `rollback_ha_data_restored`, `rollback_predecessor_runtime_started`, `rollback_health_verified` are all true;
  - consumed U9 authorization tuple unchanged; replay not permitted;
  - services owner active, broker owner active, Manager/Home Assistant/Broker counts = 1/1/1;
  - predecessor image present; target image absent;
  - strict predecessor-health predicates passed: listener contract exact, Manager MQTT authenticated, Home Assistant MQTT authenticated, HA HTTP=401;
  - automatic durable rollback and business recovery therefore PASS.
- 已证实的最终 blocker：
  - live IPC remained `ERROR / u9_plus_completion_ha_mqtt_socket_ambiguous`;
  - old oracle ran host-wide `ss ... dport=:1883` then required exactly one counter record;
  - this did not bind the record to a HA-owned socket and conflicted with existing production HA acceptance, which permits one or more HA-owned established 1883 sockets;
  - product MQTT failure is **not** proven; this is a completion-oracle false failure.
- 源码修复已证实：
  - keep fresh simplified-N3-W Manager acceptance event;
  - keep same-window MQTT `bytes_received` + `data_segs_in` progress;
  - aggregate complete established-1883 counter records;
  - missing/incomplete evidence still fails closed;
  - regression coverage and 22/22 CI PASS.
- 待确认：
  - fresh live T1 still binds the Phase-A candidate daemon override after the pause;
  - live candidate U13B-host file is still the previous exact content and has not already moved to blob `a103a263...`;
  - current durable Host/USB U13B terminal and runtime remain exact;
  - after installing the repaired candidate source and one authorized OTA-daemon restart, IPC can complete to `ROLLED_BACK`.
- 已排除：
  - U13B supervision-contract false failure — repaired and strict health now PASS;
  - Host/USB split-brain — absent at durable terminal;
  - predecessor business runtime failure — absent;
  - target image residue — absent;
  - U9 authorization replay — absent;
  - destructive U10 needs no replay for the next live-revalidation attempt.

Secondary source observations that are **not** current root cause:
- the IPC status ordering can theoretically expose a stale projected `ROLLING_BACK` before checking recovery-worker liveness; this was not proven to be the cause of this live run and no repair was made for it;
- official `verify-recovered` is labelled read-only but writes `recovered.json`; it was intentionally not run. `OFFICIAL_RECOVERED_RECEIPT_PRESENT=false`.

## 4. 执行范围与授权

- 可继续：
  - fresh repository/main/PR/source/CI rebind;
  - source review and focused tests;
  - GitHub archival;
  - **read-only** T1 preflight for the next gate.
- 暂停边界:
  - do not replace the live candidate source yet;
  - do not restart `n3w-t1-ha-ota.service` again without explicit live-revalidation authorization;
  - do not write transaction or USB state;
  - do not replay U9 authorization;
  - do not rerun destructive U10;
  - do not enter U11+;
  - do not overwrite production `/opt/HomeAssistant` source;
  - do not merge PR #807.
- 授权状态:
  - original Phase-A U9 authorization: claimed + consumed + no replay;
  - previous candidate U13B-host single-file repair + one OTA restart: completed;
  - next candidate source replacement/restart for blob `a103a263...`: **NOT_GRANTED**;
  - handoff itself grants no new live permission.

T1 locator, SSH/known-host data and other private access details remain in private conversation context and must not be copied into public GitHub.

## 5. 下一步

- 行动：
  1. fresh rebind main, PR #807, branch HEAD and source/manifest authority;
  2. confirm final CI remains green for source head `93610f23472759cf1601d2ad82b9b59b7225f4d6`;
  3. run only `N3W_T1_U9_PLUS_PHASE_A_COMPLETION_ORACLE_REPAIR_LIVE_REVALIDATION_PREFLIGHT` as a true read-only T1 check;
  4. require exact durable Host/USB U13B terminal, healthy runtime, active candidate override, and exact currently installed candidate U13B-host source;
  5. if preflight PASS, stop and request/confirm explicit authorization for **one** exact candidate-file replacement to blob `a103a263...` plus **one** OTA-daemon restart;
  6. after an authorized restart, observe IPC and durable state read-only. The expected terminal is `IPC_PHASE=ROLLED_BACK`, `error_code=null`.
- 完成条件：
  - IPC `ROLLED_BACK` with no error under repaired candidate;
  - durable Host/USB terminal remains exact U13B;
  - customer completion oracle passes without U9 replay or destructive U10 replay;
  - business runtime remains healthy;
  - then Phase-A may be recorded `PASS`;
  - do **not** claim the <=15 minute SLA from this cross-pause transaction.
- 失败／停点：
  - any source/authority/runtime drift => stop affected operation and diagnose read-only;
  - preflight PASS does not itself authorize candidate replacement/restart;
  - new IPC error after repaired source => no blind second restart;
  - after Phase-A PASS, stop before Phase B. Phase B fresh continuous downtime acceptance is a separate decision/authorization.

## 6. 必读定位与归档

- 仓库规则：
  - applicable repository `AGENTS.md`, if present;
  - `docs/development/N3W_PROJECT_WORKING_CONTEXT.md` relevant updater/current-authority sections and §12 minimum new-chat read set;
  - formal template authority: `docs/development/templates/NEW_CHAT_HANDOFF_TEMPLATE.md` V1.4.
- 任务资料：
  - this handoff;
  - `docs/development/N3W_CURRENT_STATE.md` latest 2026-11-20 entry;
  - `docs/development/N3W_CURRENT_STATE_INDEX.md` latest 2026-11-20 entry;
  - `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` KF-168 latest update;
  - Phase-A plan named above;
  - exact source, tests and manifests named in §2.
- 已归档：
  - PR #807 comments listed in §2;
  - Current State / State Index / KF-168 / Working Context updated together with this handoff.
- 未归档重要资料：无。Private T1 locators remain intentionally outside public GitHub.

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

新会话启动语：

```text
阅读《docs/development/N3W_T1_U9_PLUS_PHASE_A_DURABLE_ROLLBACK_PASS_COMPLETION_ORACLE_REPAIR_CI_PASS_NEW_CHAT_HANDOFF_V1.0_20261120.md》。

同时按交接中的“必读定位与归档”读取适用仓库规则、N3W_CURRENT_STATE、N3W_CURRENT_STATE_INDEX、KF-168、Phase-A plan，以及 exact source/test/manifests。

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

先 fresh rebind：
- main
- PR #807
- branch fix/kf147-u3-recovery-and-error-visibility-20261110
- PHASE_A_SOURCE_HEAD=93610f23472759cf1601d2ad82b9b59b7225f4d6
- repaired U13B host blob a103a2633aaea5a34efbfed35449b2eb5bace61b
- final CI status

然后只进入：
NEXT_ONE_GATE=N3W_T1_U9_PLUS_PHASE_A_COMPLETION_ORACLE_REPAIR_LIVE_REVALIDATION_PREFLIGHT

本 gate 只读。先确认 durable Host/USB U13B terminal、runtime health、candidate override 和当前 candidate source exact binding。

禁止：
- U9 replay
- destructive U10 replay
- candidate source replacement
- OTA restart
- transaction/USB mutation
- U11+
- production source overwrite
- merge

如果只读 preflight PASS，停止在新的 live-revalidation authorization boundary，再决定是否执行 exact candidate single-file replacement + one OTA restart。
```
