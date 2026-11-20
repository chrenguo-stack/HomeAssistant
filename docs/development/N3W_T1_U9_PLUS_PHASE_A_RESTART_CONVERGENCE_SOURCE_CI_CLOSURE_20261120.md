# N3-W T1 U9+ Phase-A restart-convergence source/CI closure

DATE=2026-11-20
PR=807
PR_STATE=OPEN_DRAFT_UNMERGED
DEFAULT_MAIN_HEAD=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
CI_CLOSED_HEAD=3d74881e3bfadbecd23721f8c9d500f95ef69696
STATUS=CLOSED_PASS_SOURCE_TEST_CI
MERGE=false

## 1. Live evidence carried into this closure

The previously authorized real-T1 revalidation installed exact live candidate U13B-host blob:

```text
a103a2633aaea5a34efbfed35449b2eb5bace61b
```

and invoked exactly one `n3w-t1-ha-ota.service` restart. That authorization is consumed and must not be replayed.

The restart reached:

```text
candidate_source_replaced=true
ota_restart_invoked=true
ota_restart_invocation_count=1
post_restart_ipc_error=u13b_predecessor_runtime_not_running
```

A subsequent strictly read-only forensic proved the settled business runtime healthy:

```text
HOST_PHASE=U13B_ROLLED_BACK
HOST_STATUS=ROLLED_BACK
HOST_TRANSACTION_SHA256=4548f591d972576ea4d3f1f078cb55b483d1f63f2244b03c3413da1891e09d3f
SERVICES_OWNER=active
BROKER_OWNER=active
MANAGER_COUNT=1
HOMEASSISTANT_COUNT=1
BROKER_COUNT=1
LISTENERS_EXACT=true
MANAGER_MQTT_AUTHENTICATED=true
HOMEASSISTANT_MQTT_AUTHENTICATED=true
HOMEASSISTANT_HTTP_STATUS=401
HOMEASSISTANT_BINDING=local/n3w-homeassistant:2026.10.4-5881590f
IPC_PHASE=ERROR
IPC_ERROR_CODE=u13b_predecessor_runtime_not_running
```

Observed startup order:

```text
OTA_DAEMON_STARTED=2026-11-20 15:08:48 CST
SERVICES_OWNER_STARTED=2026-11-20 15:08:50 CST
HOMEASSISTANT_CONTAINER_STARTED=2026-11-20T07:08:51.267665196Z
MANAGER_CONTAINER_STARTED=2026-11-20T07:08:51.270049435Z
```

This is a completion-oracle false failure caused by restart ordering, not failed business recovery.

## 2. Root cause and minimal repair

Pre-repair `U13BProductionRuntime.verify_predecessor_health()` performed an immediate `_running_predecessor_evidence()` call and raised `u13b_predecessor_runtime_not_running` before entering the already-existing bounded readiness loop.

The repair removes only that premature pre-loop hard failure. It does not introduce a fixed sleep and does not weaken the strict final runtime identity, overlay supervision, listener, MQTT or HTTP verification.

```text
SOURCE_REPAIR_COMMIT=f8fc67cff39a0b2831a3005ae00d0556fce8351a
REPAIRED_U13B_HOST_BLOB=437f3e6c4cae53f7d94e244cd312ac454768f8e1
REGRESSION_COMMIT=1ea43b4ac467ca99b83ecf9edc8d3502675fd0b1
REGRESSION_TEST_BLOB=9ca455c79204632e396530c0e40f654957da2caf
```

The regression starts with the services owner unavailable, converges it during the first readiness-loop sleep, then requires predecessor-health PASS.

## 3. Exact manifest binding

Final exact bindings at CI-closed head:

```text
U13B_HOST_BLOB=437f3e6c4cae53f7d94e244cd312ac454768f8e1
U13B_HOST_TEST_BLOB=9ca455c79204632e396530c0e40f654957da2caf
P3_MANIFEST_BLOB=fcb8ecd4dd4f68a7fef5c64abe627cedc32dbca7
PHASE_A_MANIFEST_BLOB=2ba6e96aec0f41f7916c852cef37c3fce9ecb966
P3_REBIND_COMMIT=3569d385c9f774991af6a528c9c6dff0dcc232f4
PHASE_A_REBIND_COMMIT=b1f3d5ca6564f38e5bf7638d7781110b878beaf6
INDEX_COMPATIBILITY_FIX_COMMIT=3d74881e3bfadbecd23721f8c9d500f95ef69696
```

The final index-only repair restores the exact `Live upgrade accepted.` compatibility marker required by the existing Core Stack pending-state regression. It does not change product source behavior.

## 4. Final CI

Exact CI authority:

```text
CI_HEAD=3d74881e3bfadbecd23721f8c9d500f95ef69696
CI_FINAL=22_SUCCESS_0_FAILURE_0_PENDING
```

Key SUCCESS runs:

- fast source/exact closure: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694858559
- P3 acceptance clean OTA source: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694858598
- P3 live/read-only source: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694858532
- Core Stack current authority: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694858575
- Manager A-to-B: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694858647
- HA 2026.10.3 target binding: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694858527
- HA 2026.10.4 target binding: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694858704
- HA 2026.10.4 same-version acceptance artifact: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694859200
- public repository safety: https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44694858521

## 5. Closure result

```text
PHASE_A_DURABLE_AUTOMATIC_ROLLBACK=PASS
PHASE_A_BUSINESS_RECOVERY=PASS
RESTART_CONVERGENCE_SOURCE_REPAIR=PASS
RESTART_CONVERGENCE_REGRESSION=PASS
RESTART_CONVERGENCE_EXACT_BINDING=PASS
RESTART_CONVERGENCE_CI=22_OF_22_SUCCESS
PHASE_A_OVERALL=NOT_YET_PASS
```

Phase-A overall remains open because the repaired `437f3e6c...` candidate has not yet been installed/revalidated on the real T1.

## 6. Stop boundary and next gate

Current live T1 still has:

```text
LIVE_CANDIDATE_U13B_HOST_BLOB=a103a2633aaea5a34efbfed35449b2eb5bace61b
LIVE_IPC_PHASE=ERROR
LIVE_IPC_ERROR_CODE=u13b_predecessor_runtime_not_running
LIVE_BUSINESS_RUNTIME_HEALTH=PASS
LIVE_A103_RESTART_AUTHORIZATION=CONSUMED_NO_REPLAY
```

No new live mutation is authorized.

```text
NEXT_ONE_GATE=N3W_T1_U9_PLUS_PHASE_A_RESTART_CONVERGENCE_REPAIR_LIVE_REVALIDATION_PREFLIGHT
NEXT_GATE_SCOPE=READ_ONLY
LIVE_437F_RETRY_AUTHORIZATION_GRANTED=false
U9_REPLAY=false
DESTRUCTIVE_U10_REPLAY=false
TRANSACTION_MUTATION=false
USB_MUTATION=false
U11_PLUS=false
PRODUCTION_SOURCE_OVERWRITE=false
MERGE=false
```

The next session must first fresh-rebind repository/PR/source/manifest/CI and perform only a read-only T1 preflight. If that preflight is exact, stop at a new explicit authorization boundary before any live replacement to blob `437f3e6c...` and before any OTA-daemon restart.
