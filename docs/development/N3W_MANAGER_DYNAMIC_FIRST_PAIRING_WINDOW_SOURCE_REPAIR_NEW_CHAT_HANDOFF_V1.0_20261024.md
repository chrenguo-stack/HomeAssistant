# N3-W Manager Dynamic First-Pairing Window — Source Repair New-Chat Handoff V1.0 — 2026-10-24

## 1. Handoff identity

```text
PROJECT=温室环境监测系统（ESP32-C6）
WORKSTREAM=N3-W / T1 first-pair onboarding
HANDOFF_TYPE=STAGE_DELTA
HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.1
TEAM_SHARED_WORKSPACE=GITHUB
```

This handoff transfers the project from the failed Manager-recreate onboarding design to the frozen Manager in-process dynamic pairing-window design.

## 2. Product north star

First-pair onboarding must allow a new node to be added without restarting Broker, Manager or Home Assistant in the normal path.

Pairing exposure must be temporary and fail-closed:

- UDP 47111 and TCP 47112 are closed in normal production state;
- one bounded dynamic pairing window may open inside the already-running Manager process;
- Manager itself owns the deadline and closes the window;
- no durable Compose/env pairing mutation is used;
- a Manager restart must return to pairing closed, never automatically reopen a previous window.

## 3. Frozen authorities

Read these first:

1. this handoff;
2. `docs/development/N3W_PROJECT_WORKING_CONTEXT.md`;
3. `docs/development/N3W_CURRENT_STATE.md`;
4. `docs/development/N3W_CURRENT_STATE_INDEX.md`;
5. `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`;
6. `docs/development/N3W_MANAGER_DYNAMIC_FIRST_PAIRING_WINDOW_SOURCE_DESIGN_AND_ACCEPTANCE_PLAN_20261024.md`;
7. PR #664 Conversation, especially the live root-cause closure comments.

Repository/PR authority at handoff creation:

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=664
PR_STATE=OPEN_DRAFT
PR_BRANCH=fix/n3w-t1-first-pairing-onboarding-activation-20261024
PR_BASE=dc596ad50eb2ea80ba55aa3af2413236321f1465
PRE_FREEZE_EXECUTABLE_SOURCE_HEAD=85706d7507b8ce90b3447c18ab62d9c0a37afcce
DOCS_FREEZE_HEAD_BEFORE_HANDOFF=3a383cbec2ea9b58c2a557f90547e2093b82f8e4
HANDOFF_TEMPLATE_BLOB=b9ef40acdaa8fae37feb5ffe5662afd0e89462a0
```

The next chat must fresh-rebind main and PR #664 before source editing. Docs-only freeze commits after the executable source head do not themselves authorize source assumptions if new drift is found.

## 4. Proven facts from the failed live attempt

The failed first live `open` attempt consumed its one-shot authorization. It is permanently non-replayable.

Board D was not paired.

The live failure root cause is proven:

1. PR #664 used out-of-band `docker compose ... --force-recreate manager` to open pairing.
2. The deployed `n3wfc4-services-activation.service` owns Manager and Home Assistant in one foreground Compose lifecycle:
   `docker compose ... --abort-on-container-exit manager homeassistant`.
3. Stopping/recreating the old Manager caused that foreground Compose owner to log `Aborting on container exit...`.
4. Home Assistant was then actively stopped by Docker/Compose and exited 137.
5. Docker reported `OOMKilled=false`; kernel OOM evidence was absent.
6. Broker remained running.
7. Manager later returned to factory pairing-disabled / factory Broker-placeholder values and pairing ports were closed.

Do not reclassify this as a Board D failure or Home Assistant self-crash.

## 5. Separate parser defect already repaired

The failed live attempt also exposed a separate source defect:

the staged onboarding parser rejected `OPEN_RESTORE_PENDING` / `TIMEOUT_RESTORE_PENDING` even though the expiry/recovery path expected them.

PR #664 repaired that parser/watchdog binding defect at:

`85706d7507b8ce90b3447c18ab62d9c0a37afcce`

Related CI was 12/12 PASS.

Do not confuse this closed source bug with the still-open lifecycle architecture blocker.

## 6. Current public-safe live baseline

At the end of the evidence collection:

- Manager was running;
- Manager factory pairing was disabled;
- the factory Broker placeholder was restored;
- UDP 47111 had no listener;
- TCP 47112 had no listener;
- Broker was running with restart count 0 in the captured evidence;
- Home Assistant was stopped by the proven Compose supervision abort path;
- the old watchdog timer was inactive;
- the old staged watchdog service was observed auto-restarting against the old parser;
- failed transaction/evidence still exists and must be preserved;
- no Setup Secret was imported;
- Board D remains unpaired.

This is not a full healthy production baseline. Do not claim recovery PASS until a later explicitly authorized live recovery gate proves it.

## 7. Authorization ledger

Consumed and non-replayable for this route:

`N3W_T1_FIRST_PAIRING_ONBOARDING_LIVE_ACTIVATION_AND_BOARD_D_FIRST_PAIR_20261024_01`

It cannot authorize:

- another `open`;
- manual watchdog/service cleanup;
- Home Assistant restart;
- new Manager deployment;
- Board D pairing;
- any second live attempt.

The next source gate requires no live authorization because it is repository-only.

Any later T1 recovery, production image deployment, or Board D pairing requires its own new explicit live authorization.

## 8. Frozen design decision

The replacement design is Manager-owned in-process dynamic pairing.

Normal production configuration remains:

- `GH_N3W_PRODUCT_PAIRING_ENABLED=false`;
- `GH_N3W_NODE_BROKER_HOST=gate-f-unbound.invalid`;
- `GH_N3W_PAIRING_ADVERTISED_HOST=auto`;
- Manager host network;
- no Manager Docker ports.

Do not split the production Manager/Home Assistant systemd lifecycle in this task.

Do not use Compose override or Manager recreate in the normal pairing path.

## 9. Required runtime shape

Add a Manager-owned pairing-window controller that:

- creates the existing pairing composition on demand;
- starts the existing UDP/HTTP pairing runtime and existing `pairing.sock`;
- accepts only one open window;
- enforces 180–600 seconds, default 300;
- derives the runtime Broker locator from the requesting local peer;
- keeps that locator in memory only;
- owns automatic deadline close;
- exposes local-only open/status/close control through a private Unix socket under `/run/greenhouse-manager`;
- destroys pairing-specific resources on close;
- never reopens after Manager restart.

The control socket and the existing Setup Secret `pairing.sock` must remain separate authorities.

## 10. Expected source scope

Expected files/modules include:

- `host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_manager_runtime_wiring.py`;
- `host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_simplified_product_runtime.py`;
- a new Manager dynamic pairing-window/control module;
- `host/greenhouse-manager/src/greenhouse_manager/ops/n3w_pairing_cli.py`;
- `tools/n3w_t1_first_pairing_onboarding.py`;
- Manager runtime tests;
- PR #664 onboarding tests;
- applicable CI workflow updates.

The exact file set is not frozen if source review proves a smaller/safer implementation.

## 11. Required removal from normal onboarding behavior

The normal first-pair path must no longer depend on:

- Compose pairing override;
- `--force-recreate manager`;
- factory Manager recreate on close;
- Manager container identity changing to prove open;
- durable mutation of pairing enable or node Broker host;
- watchdog recovery whose ordinary action is Manager recreate.

Historical commits/evidence remain intact.

## 12. Source test contract

Source repair is not complete until tests prove:

- pairing closed by default;
- one dynamic open;
- duplicate/concurrent open rejected;
- local-peer validation;
- bounded duration validation;
- manual close;
- automatic deadline close;
- Manager shutdown closes pairing;
- Manager restart does not reopen pairing;
- no raw Setup Secret / Broker locator leakage;
- real UDP/TCP/Unix sockets appear during open and disappear after close/timeout;
- the normal Manager MQTT service is not reconstructed;
- Direct/Relay normal runtime ownership is not closed by pairing cleanup;
- pairing resource handles close cleanly;
- real transaction parser/state transitions are exercised instead of monkeypatching away the parser.

## 13. CI continuation rules

Do not enter live work until:

- focused Manager dynamic-pair tests PASS;
- greenhouse-manager CI PASS;
- existing N3-W pairing/recovery regressions PASS;
- PR #664 onboarding CI PASS;
- public repository safety PASS;
- relevant F4/F5 production/release checks show no new source regression;
- an independent source review finds no new false-PASS path.

If CI remains pending after a small bounded number of checks, give the GitHub Actions link and STOP polling. Do not loop indefinitely.

## 14. Production artifact boundary

Source PASS does not authorize T1 deployment.

Because Manager code changes, later live work requires a new exact Manager production image and exact source/image/release binding.

Broker and Home Assistant images should remain unchanged unless an independent blocker proves otherwise.

## 15. Current-live recovery remains separate

Before deploying/testing the new dynamic Manager on T1, the existing failed-attempt state must be recovered under a separate explicit live gate.

That recovery gate must preserve the old transaction/evidence, keep its authorization consumed, eliminate the obsolete watchdog loop safely, restore/verify Home Assistant and normal product runtime, and prove 47111/47112 closed.

Do not mix that recovery into the source-repair gate.

## 16. Later live acceptance order

After source/CI/artifact closure:

1. explicitly authorized failed-attempt recovery;
2. exact new Manager deployment/verification;
3. no-Board dynamic open/close test;
4. no-Board automatic-timeout test;
5. only then a completely new one-shot Board D first-pair authorization;
6. durable registration/credential/application-key/peer-trust proof;
7. dynamic close;
8. zero-interruption proof for Broker, Manager and Home Assistant;
9. GitHub evidence closure;
10. STOP before Direct/Relay successor work.

## 17. Hard STOP conditions

Stop before advancing if any of these is observed:

- normal dynamic open/close restarts Manager or Home Assistant;
- Broker changes unexpectedly;
- 47111/47112 remain exposed after close/deadline;
- control state disagrees with actual listener state;
- runtime Broker locator is persisted;
- a pairing window can be silently extended/replayed;
- Manager restart reopens pairing;
- Setup Secret/private locator leaks into public evidence;
- deployed Manager image is not the exact reviewed artifact;
- old failed transaction is deleted/overwritten;
- old consumed authorization is reused;
- first-pair credential/trust commit becomes partial and unreconciled.

## 18. Closed routes

Do not reopen in the next source gate:

- Manager-only Compose recreate as normal onboarding;
- automatic replay of the consumed first-pair authorization;
- systemd Manager/Home Assistant split;
- Board firmware/OTA/NVS work;
- Direct/Relay or multi-relay acceptance;
- PR #664 merge.

## 19. Known failure

```text
KF_ID=KF-129
SYMPTOM=Manager-only onboarding recreate caused production Compose supervision to stop Home Assistant
ROOT_CAUSE=PR #664 assumed Manager could be recreated outside the existing combined Manager/Home Assistant foreground Compose ownership
FIX_OR_GUARD=frozen in-process dynamic pairing-window design; no normal Manager/HA restart; Manager-owned deadline; local-only control; exact source/image/live acceptance required
STATUS=OPEN
```

The separate recovery-pending parser defect is already repaired and covered by PR #664 tests.

## 20. NEXT_ONE_GATE

```text
NEXT_ONE_GATE=N3W_MANAGER_DYNAMIC_FIRST_PAIRING_WINDOW_SOURCE_REPAIR_20261024_01

REPOSITORY_MUTATION=true
SOURCE_MUTATION=true
TEST_MUTATION=true
DOC_MUTATION=true

T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
FIRMWARE_OTA_NVS=false
PRODUCTION_ARTIFACT_DEPLOYMENT=false
MERGE=false
AUTO_EXECUTE_NEXT_GATE=false
```

### Execution contract

1. fresh-rebind repository main and PR #664;
2. confirm no executable-source drift invalidates this design;
3. read the frozen design;
4. implement the smallest safe Manager in-process pairing-window controller;
5. replace the PR #664 Manager-recreate normal path;
6. add focused real-parser/real-resource tests;
7. run focused tests, then applicable full CI;
8. independently review the exact source head for lifecycle, timeout, resource cleanup and false-PASS paths;
9. update GitHub progress/evidence;
10. STOP before production image build/deployment unless a later gate explicitly authorizes it.

### Expected closure

PASS only if the exact source proves:

- no normal Compose/Manager/HA restart;
- bounded in-process pairing window;
- Manager-owned automatic timeout;
- local-only control;
- runtime-only locator;
- deterministic close;
- preserved one-shot transaction/security evidence;
- applicable CI green;
- no new source blocker.

FAIL/STOP on any substantive mismatch. Do not paper over the mismatch with mocks or by weakening invariants.

## 21. New Chat Start Prompt

```text
阅读《docs/development/N3W_MANAGER_DYNAMIC_FIRST_PAIRING_WINDOW_SOURCE_REPAIR_NEW_CHAT_HANDOFF_V1.0_20261024.md》。

同时读取：
- docs/development/N3W_PROJECT_WORKING_CONTEXT.md
- docs/development/N3W_CURRENT_STATE.md
- docs/development/N3W_CURRENT_STATE_INDEX.md
- docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
- docs/development/N3W_MANAGER_DYNAMIC_FIRST_PAIRING_WINDOW_SOURCE_DESIGN_AND_ACCEPTANCE_PLAN_20261024.md

继续“温室环境监测系统（ESP32-C6）”项目 N3-W。

先 fresh rebind repository main、PR #664、candidate branch 和 current state，确认本轮 docs-only 设计冻结后没有新的 executable-source drift。

只进入：

NEXT_ONE_GATE=N3W_MANAGER_DYNAMIC_FIRST_PAIRING_WINDOW_SOURCE_REPAIR_20261024_01

本轮源代码目标是用 Manager 进程内动态 pairing window 替换 PR #664 的 Compose override / Manager force-recreate 正常路径。

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_ARTIFACT_DEPLOYMENT=false
MERGE=false

必须保留：
- 旧 live pairing authorization 已 consumed/non-replayable；
- Board D 尚未配对；
- 当前 T1 失败现场恢复属于后续独立 live gate；
- 不拆 Manager/Home Assistant systemd 生命周期；
- 不自动进入下一阶段。

完成源码、测试、CI 和独立源码复核后 STOP。
```

## 22. Final frozen state

```text
CURRENT_STAGE=DYNAMIC_FIRST_PAIRING_DESIGN_FROZEN
CURRENT_STOP_POINT=BEFORE_DYNAMIC_PAIRING_SOURCE_REPAIR
CURRENT_BLOCKER=KF-129 / old Manager-recreate onboarding path incompatible with production supervision
LIVE_SYSTEM_STATE=PAIRING_EXPOSURE_CLOSED_BUT_FULL_PRODUCT_BASELINE_NOT_RECOVERED
NEXT_ONE_GATE=N3W_MANAGER_DYNAMIC_FIRST_PAIRING_WINDOW_SOURCE_REPAIR_20261024_01

TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS

PROJECT_WORKING_CONTEXT_VERSION=1.1
HANDOFF_TEMPLATE_VERSION=1.3

LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

## 23. Handoff compliance audit

```text
=== HANDOFF COMPLIANCE AUDIT ===

HANDOFF_TEMPLATE_VERSION=1.3
PROJECT_WORKING_CONTEXT_VERSION=1.1

PROJECT_WORKING_CONTEXT_REFERENCED=PASS
LONG_TERM_RULE_DUPLICATION_MINIMIZED=PASS
STAGE_SPECIFIC_OVERRIDES_EXPLICIT=PASS
PRIVATE_CONTEXT_EXCLUDED_FROM_PUBLIC_HANDOFF=PASS

PRODUCT_NORTH_STAR_PRESENT=PASS
FROZEN_AUTHORITIES_COMPLETE=PASS
CURRENT_LIVE_BASELINE_COMPLETE=PASS
PROVEN_FACTS_SEPARATED_FROM_INFERENCE=PASS
CURRENT_BLOCKERS_EXPLICIT=PASS
CLOSED_ROUTES_EXPLICIT=PASS

AUTHORIZATION_LEDGER_COMPLETE=PASS
CONSUMED_AUTH_REPLAY_GUARD=PASS
ROLLBACK_AUTHORITY_EXPLICIT=PASS

NEXT_ONE_GATE_EXPLICIT=PASS
NEXT_GATE_SCOPE_BOUNDED=PASS
ALLOWED_FORBIDDEN_SCOPE_EXPLICIT=PASS
EXECUTION_CONTRACT_SELF_CONTAINED=PASS
CI_CONTINUATION_HARD_RULES_PRESENT=PASS
EXPECTED_CLOSURE_PRESENT=PASS
AFTER_PASS_DOES_NOT_AUTO_EXECUTE=PASS

KNOWN_FAILURES_UPDATE_CLASSIFIED=PASS
NEW_CHAT_START_PROMPT_PRESENT=PASS
TEAM_WORKSPACE_STATUS_PRESENT=PASS
FINAL_FROZEN_STATE_PRESENT=PASS

HANDOFF_STATE_COMPLETENESS=PASS
HANDOFF_READY_FOR_NEW_CHAT=true

=== END ===
```
