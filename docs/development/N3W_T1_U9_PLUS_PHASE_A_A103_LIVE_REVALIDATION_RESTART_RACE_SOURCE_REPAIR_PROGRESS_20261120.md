# N3-W T1 U9+ Phase-A a103 live revalidation restart-race source repair progress

DATE=2026-11-20
PR=807
STATUS=SOURCE_REPAIR_AND_EXACT_REBIND_IN_CI
MERGE=false

## 1. Live authorization actually consumed

The user explicitly authorized exactly one live candidate U13B-host source replacement to repaired blob `a103a2633aaea5a34efbfed35449b2eb5bace61b` plus exactly one `n3w-t1-ha-ota.service` restart.

The live executor reported:

```text
candidate_source_replaced=true
ota_restart_invoked=true
ota_restart_invocation_count=1
u9_replay=false
destructive_u10_replay=false
transaction_mutation_requested=false
usb_mutation_requested=false
u11_plus=false
production_source_overwrite=false
```

That authorization is consumed and must not be replayed.

## 2. Live result

The post-restart completion query stopped with:

```text
post_restart_ipc_error:u13b_predecessor_runtime_not_running
```

A subsequent strictly read-only forensic returned:

```text
HOST_PHASE=U13B_ROLLED_BACK
HOST_STATUS=ROLLED_BACK
HOST_TRANSACTION_SHA256=4548f591d972576ea4d3f1f078cb55b483d1f63f2244b03c3413da1891e09d3f
CANDIDATE_U13B_HOST_BLOB=a103a2633aaea5a34efbfed35449b2eb5bace61b
CANDIDATE_DAEMON_BLOB=941baffc8423a10cfa1436323d109caae17be473
SERVICES_OWNER=active
BROKER_OWNER=active
MANAGER_COUNT=1
HOMEASSISTANT_COUNT=1
BROKER_COUNT=1
LISTENERS_EXACT=true
MANAGER_MQTT_AUTHENTICATED=true
HOMEASSISTANT_MQTT_AUTHENTICATED=true
HOMEASSISTANT_HTTP_STATUS=401
IPC_PHASE=ERROR
IPC_ERROR_CODE=u13b_predecessor_runtime_not_running
```

Runtime timing:

```text
OTA_DAEMON_STARTED=2026-11-20 15:08:48 CST
SERVICES_OWNER_STARTED=2026-11-20 15:08:50 CST
HOMEASSISTANT_CONTAINER_STARTED=2026-11-20T07:08:51.267665196Z
MANAGER_CONTAINER_STARTED=2026-11-20T07:08:51.270049435Z
```

This proves the daemon evaluated completion before the application runtime had converged. The settled business runtime is healthy.

The journal also contained an older `u9_plus_broker_runtime_not_running` daemon-start failure. The filtered evidence did not retain timestamps for that line, so it is not used as the root-cause authority for this gate.

## 3. Exact root cause

In `U13BProductionRuntime.verify_predecessor_health()`, the pre-repair code did this before entering the existing readiness loop:

```python
runtime = self._running_predecessor_evidence(
    transaction,
    predecessor,
)
if runtime is None:
    raise UpdaterV2Error("u13b_predecessor_runtime_not_running")
```

The readiness loop below already handles a missing runtime as a soft state and waits/retries. The pre-loop hard failure therefore made the bounded convergence design unreachable during normal restart ordering.

## 4. Minimal repair

Repair commit:

```text
f8fc67cff39a0b2831a3005ae00d0556fce8351a
```

New source blob:

```text
437f3e6c4cae53f7d94e244cd312ac454768f8e1
```

The repair removes only the premature pre-loop runtime check. It does not add a fixed sleep and does not weaken the final strict runtime, identity, overlay, listener, MQTT or HTTP validation.

Regression commit:

```text
1ea43b4ac467ca99b83ecf9edc8d3502675fd0b1
```

The new regression starts with the services owner inactive, converges it on the first readiness-loop sleep, and requires predecessor health PASS.

## 5. Exact manifest rebind

```text
P3_REBIND_COMMIT=3569d385c9f774991af6a528c9c6dff0dcc232f4
P3_MANIFEST_BLOB=fcb8ecd4dd4f68a7fef5c64abe627cedc32dbca7
PHASE_A_REBIND_COMMIT=b1f3d5ca6564f38e5bf7638d7781110b878beaf6
PHASE_A_MANIFEST_BLOB=2ba6e96aec0f41f7916c852cef37c3fce9ecb966
```

## 6. CI status at the three-poll boundary for b1f3d5c

At the third and final active poll:

```text
15 SUCCESS
2 FAILURE
5 PENDING
```

Relevant PASS:
- N3W CI fast source and exact closure contract;
- N3W U13B P3 acceptance clean OTA source CI.

The two failures are not product-source test failures:
- Core Stack current authority: `state_authority_link_missing`;
- Manager A-to-B: the same Current State authority-link failure caused 4 tests to fail while 319 passed.

The newest Current State top section had dropped the long-lived Core Stack authority reference. The state/index archive update following this document restores that authority contract.

Active polling for commit `b1f3d5ca6564f38e5bf7638d7781110b878beaf6` is stopped by the three-check rule. No rerun was dispatched.

## 7. Stop boundary

```text
LIVE_T1_WRITE=false
LIVE_OTA_RESTART=false
U9_REPLAY=false
DESTRUCTIVE_U10_REPLAY=false
TRANSACTION_MUTATION=false
USB_MUTATION=false
U11_PLUS=false
PRODUCTION_SOURCE_OVERWRITE=false
MERGE=false
LIVE_437F_RETRY_AUTHORIZATION_GRANTED=false
```

NEXT_ONE_GATE=N3W_T1_U9_PLUS_PHASE_A_RESTART_CONVERGENCE_SOURCE_CI_CLOSURE

A later live retry with blob `437f3e6c...` requires a fresh read-only preflight and a separate explicit live mutation authorization.
