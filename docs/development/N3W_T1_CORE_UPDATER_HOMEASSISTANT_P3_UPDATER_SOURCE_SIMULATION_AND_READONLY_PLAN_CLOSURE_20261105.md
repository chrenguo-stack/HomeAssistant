# 温室环境监测系统（ESP32-C6） / N3-W / T1 Core Stack
# Home Assistant P3 updater source simulation and read-only plan CLOSED_PASS
# Closure — 2026-11-05

## 1. Closure

~~~text
=== N3W_T1_CORE_UPDATER_HOMEASSISTANT_P3_UPDATER_SOURCE_SIMULATION_AND_READONLY_PLAN_20261105_01 CLOSURE ===

EXECUTION_ID=N3W_T1_CORE_UPDATER_HOMEASSISTANT_P3_UPDATER_SOURCE_SIMULATION_AND_READONLY_PLAN_20261105_01
AUTHORIZATION=NOT_APPLICABLE:READONLY_SOURCE_GATE
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

P2B_EXECUTABLE_SOURCE_HEAD=f43e3600a017af04cb253d10ec0c86b47d24b5e3
P2_FINAL_DOCS_ALIGNMENT_HEAD=74ce1940c7ee0df14e0d7635a6a47f6900f0c2c0
P3_EXECUTABLE_SOURCE_HEAD=b4409c11beda99f2aef43353b8129003760634b7
PR785=OPEN_DRAFT
PR785_MERGEABLE=true
MERGE=false

TARGET_MANIFEST=infra/n3w-t1/upgrades/homeassistant-2026.10.4.json
TARGET_MANIFEST_BLOB_SHA=6966b4fe4d7620ccc436643cc840da9ae95e6010
TARGET_ARTIFACT_ID=13391983948
TARGET_ARCHIVE_SHA256=eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973
TARGET_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
PREDECESSOR_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a

HA_READONLY_INSPECT_PLAN=PASS
HA_SIMULATED_APPLY=PASS
HA_SIMULATED_ROLLBACK=PASS
HA_TEMPLATE_BINDING_ATOMICITY=PASS
MANAGER_CONTINUITY=PASS
BROKER_CONTINUITY=PASS
INTERRUPTED_BINDING_TRANSITION_RECOVERY=PASS
ACTIVATION_FAILURE_AUTO_ROLLBACK=PASS
FALSE_PASS_BLOCKER_COUNT=0

LATEST_HEAD_CI_TOTAL=14
LATEST_HEAD_CI_SUCCESS=14
LATEST_HEAD_CI_FAILURE=0
HA_TARGET_BINDING_CI_RUN=41981502824
HA_TARGET_BINDING_CI=SUCCESS
GENERIC_MANAGER_UPDATER_CI_RUN=41981502882
GENERIC_MANAGER_UPDATER_CI=SUCCESS
FAST_SOURCE_CI_RUN=41981502737
FAST_SOURCE_CI=SUCCESS

T1_ACCESS=false
T1_MUTATION=false
SERVICE_RESTART=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
STACK_1_1_0_PUBLICATION=false

P3_RESULT=CLOSED_PASS
NEXT_ROUTE=HA_P4_FRESH_READONLY_PREMUTATION_BASELINE
AUTO_EXECUTE_NEXT_GATE=false
STOP=true

=== END ===
~~~

## 2. Fresh rebind result

Fresh rebind confirmed that the P2 executable source authority remained
`f43e3600a017af04cb253d10ec0c86b47d24b5e3` and the final P2 documentation
alignment head remained
`74ce1940c7ee0df14e0d7635a6a47f6900f0c2c0`.

The delta between those two authorities was documentation-only. No unreviewed
executable source drift was present before P3 started.

The frozen Home Assistant target manifest remained byte-identical throughout
P3. P3 did not reproduce the P2A artifact and did not modify the frozen target
identity.

## 3. Source finding

Independent source review found one bounded product-path defect in the existing
generic V2 updater.

The generic V2 target model already accepted the frozen Home Assistant
`gh.n3w-t1-core-updater-target/2` target, but the real predecessor state from
P1 is `legacy_static`. The pre-P3 host path rejected that state before apply
because component upgrades required a `dynamic` binding.

A second transaction-integrity gap followed from the same condition: rollback
authority recorded the predecessor image but did not make the predecessor
binding mode part of transaction authority. Therefore a Home Assistant upgrade
could not prove that rollback restored both the predecessor image and the
predecessor template-binding mode.

## 4. P3 repair

P3 retained the existing generic V2 updater and did not create a second upgrade
engine.

The bounded repair does the following:

- allows Home Assistant `legacy_static` as the accepted predecessor mode;
- records `predecessor_binding_mode` in the V2 transaction;
- makes the updater own Home Assistant runtime-template convergence and image
  replacement in the same transaction;
- requires the committed target state to use `dynamic` binding;
- restores both predecessor image and predecessor binding mode on automatic and
  explicit rollback;
- keeps Manager and Broker as peer runtime authorities and rejects peer drift;
- classifies an interrupted binding transition separately from a valid
  predecessor or committed target state.

The conversion order is intentionally recoverable:

~~~text
legacy_static predecessor
-> env binds predecessor image
-> Compose switches to dynamic Home Assistant image variable
-> env advances to target image
-> target runtime starts and is verified
~~~

This means the intermediate state is still identifiable and recoverable instead
of becoming a false committed state.

## 5. Simulation evidence

P3 added source simulations using the frozen Home Assistant target rather than a
replacement target.

The simulation covers:

- read-only inspect and plan with no transaction-state creation;
- predecessor `legacy_static` to target `dynamic` apply;
- explicit rollback to predecessor image plus `legacy_static`;
- automatic rollback after injected activation failure;
- interrupted binding-transition classification and recovery;
- Manager continuity;
- Broker continuity;
- target binding-mode postcondition;
- false-PASS rejection.

File-level LocalHost tests additionally prove:

- static -> dynamic -> static round-trip restores exact product-file bytes;
- an interrupted template-convergence state can restore the legacy binding;
- failure on the second product-file write restores both files to the original
  bytes.

## 6. CI closure

Latest reviewed executable head:

~~~text
P3_EXECUTABLE_SOURCE_HEAD=b4409c11beda99f2aef43353b8129003760634b7
~~~

All 14 workflows observed on that exact head reached `SUCCESS`.

Critical P3 runs:

~~~text
HA_TARGET_BINDING_CI_RUN=41981502824
HA_TARGET_BINDING_CI=SUCCESS

GENERIC_MANAGER_UPDATER_CI_RUN=41981502882
GENERIC_MANAGER_UPDATER_CI=SUCCESS

FAST_SOURCE_CI_RUN=41981502737
FAST_SOURCE_CI=SUCCESS

PUBLIC_REPOSITORY_SAFETY_CI_RUN=41981502823
PUBLIC_REPOSITORY_SAFETY_CI=SUCCESS
~~~

No failed or pending workflow remains on the executable P3 head.

## 7. Scope and boundary

P3 performed repository source/test/CI work only.

~~~text
T1_ACCESS=false
T1_MUTATION=false
SERVICE_RESTART=false
BOARD_ACCESS=false
MERGE=false
STACK_1_1_0_PUBLICATION=false
P4_ENTERED=false
~~~

P0/P1/P2 remain closed and are not reopened.

## 8. Next route

P3 is closed.

The next route is:

~~~text
HA_P4_FRESH_READONLY_PREMUTATION_BASELINE
~~~

P4 is not entered by this closure. A fresh P4 read-only baseline must be treated
as the next gate and must not be inferred from P3 simulation evidence.

No live Home Assistant apply or rollback is authorized by this document.
