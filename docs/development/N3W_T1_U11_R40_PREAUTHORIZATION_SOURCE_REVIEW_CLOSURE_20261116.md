# N3-W T1 U11 R40 preauthorization source review closure — 2026-11-16

## Result

```text
PR=807
SOURCE_HEAD=a187e70f4c3aef4657be3d47983a404d61ea07e3
SOURCE_CI=16_OF_16_SUCCESS
HA_TARGET_BINDING_RUN=43812175507
HA_TARGET_BINDING_TESTS=777_PASSED

R40_EXECUTOR_BLOB=f3b42958bbffeeb1b49afc2ad6be9ad8e59c4425
R40_MANIFEST_BLOB=53348743072e6a868b98fa6abd85cf5870e464b0
R40_TEST_BLOB=3c72c533b1715aa50a2c0f2035614c6ca66a5e01
U11_CONTROLLER_BLOB=33bd5e486db17b2476674009a6c23eecf750c12a
U11_HOST_ADAPTER_BLOB=1ec5adaf63fe9ae5024be05922536cfe4f2168ba

FINAL_SOURCE_REVIEW=PASS
NEW_BLOCKER_COUNT=0
SOURCE_REPAIR_REQUIRED=false
REAL_T1_U11_AUTHORIZED=false
```

This closure is repository/source evidence only. It does not authorize or execute a real U11 mutation.

## Reviewed scope

The independent review covered:

- `tools/n3w_t1_core_updater_ha_u11.py`
- `tools/n3w_t1_core_updater_ha_u11_host.py`
- `tools/execution_packages/n3w/r7a/u11_target_install_r40/executor.py`
- `tools/execution_packages/n3w/r7a/u11_target_install_r40/manifest.json`
- `tests/tools/test_n3w_t1_u11_target_install_r40.py`
- `.github/workflows/n3w-t1-core-updater-homeassistant-target-binding-ci.yml`
- exact R39/R37 execution dependencies named by the R40 manifest.

## Exact-source binding

Every path listed by `package_source_authority` was re-read from exact head `a187e70f4c3aef4657be3d47983a404d61ea07e3` and matched the manifest-bound Git blob exactly.

```text
PACKAGE_SOURCE_AUTHORITY=PASS
SOURCE_DRIFT=false
```

R40 delivers the new U11 controller and host adapter as exact package-bound temporary modules. It does not replace live T1 source files.

## Authorization and no-replay review

The local executor checks the preauthorization manifest before creating the SSH transport:

```text
LIVE_EXECUTION_AUTHORIZED=false
AUTHORIZATION_GRANTED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_PERMITTED=false
```

The reviewed preauthorization head therefore cannot enter live execution.

For a future grant-state successor, the execution order is:

```text
manifest/grant validation
-> SSH transport
-> embedded R39 read-only preclaim
-> one-shot remote claim
-> exact U11 controller execution
```

The R39 preclaim precedes creation of the R40 claim ledger. After claim, replay is forbidden. Transport ambiguity is reconciled from durable remote state rather than by replay.

## U11 install sequence review

The controller preserves the frozen U11 order:

```text
exact U10 transaction
-> exact bound USB target reverify
-> target image must be absent
-> predecessor HA binding must be current
-> docker target load
-> portable/runtime image identity verify
-> HA target binding publish
-> production services owner start
-> exact Manager/Broker peer identity
-> exact target HA runtime identity
-> production /config mount proof
-> USB U11 metadata
-> host U11 transaction
```

USB U11 metadata is persisted before the host U11 transaction.

The host adapter starts the official `n3wfc4-services-activation.service`; it does not bypass production ownership with an unmanaged Compose start.

## U11 / U12 boundary

R40 proves only target installation/start identity and production `/config` continuity.

The reviewed source does not call:

- `wait_services()`
- `observe_v2()`
- listener health acceptance
- MQTT authentication acceptance
- Home Assistant HTTP acceptance
- `record_target_accepted()`
- the U12 transition.

```text
U11_TARGET_INSTALL_START=IN_SCOPE
U12_TARGET_ACCEPTANCE=OUT_OF_SCOPE
U12_PLUS=false
```

## Partial-failure and reconciliation review

Post-claim failures are fail-closed:

```text
STATUS=STOP_POSTCLAIM
RECOVERY_REQUIRED=true
REPLAY_PERMITTED=false
```

Failure evidence re-observes, and conservatively handles uncertainty for:

- target image presence;
- Home Assistant binding state;
- services-owner / Manager / Home Assistant runtime state;
- USB transaction phase;
- host transaction phase.

A success ledger is written only after controller completion and terminal U11 verification. Transport/result ambiguity uses the status reconciliation path and never authorizes replay.

## CI evidence

Exact head `a187e70f4c3aef4657be3d47983a404d61ea07e3` completed all 16 repository workflows successfully.

The HA target-binding source job for run `43812175507` explicitly included:

```text
tests/tools/test_n3w_t1_u11_target_install_r40.py
777 passed in 8.22s
```

Manager A-to-B, storage lifecycle, Core Stack current authority, public repository safety and the remaining repository workflows also completed SUCCESS.

## Live state preserved

The last physical authority remains R39:

```text
R39_RESULT=U11_R39_READONLY_PREFLIGHT_PASS
LIVE_TRANSACTION_PHASE=U10_INTERNAL_PREDECESSOR_CAPACITY_RELEASED
LIVE_TRANSACTION_SHA256=c0dc58ebcfcd2876aec5bfcf556723ae779106803e19df5541b1847fc494bba3
R38_REPLAY_PERMITTED=false
TARGET_INTERNAL_IMAGE_ABSENT=true
BROKER_RUNNING=true
MANAGER_QUIESCED=true
```

No T1 access or mutation occurred during this R40 source review.

## Closure boundary

```text
R40_SOURCE_STATUS=CLOSED_PASS
R40_PREAUTHORIZATION_STATUS=CLOSED_PASS
R40_LIVE_EXECUTION_AUTHORIZED=false
R40_DIRECT_EXECUTION_FROM_PREAUTH_HEAD=false

NEXT_ONE_GATE=R40_LIVE_ONE_SHOT_U11_TARGET_INSTALL_EXPLICIT_AUTHORIZATION
NEXT_GATE_MODE=EXPLICIT_AUTHORIZATION_THEN_GRANT_ONLY_SUCCESSOR
GRANT_SUCCESSOR_REQUIRES_FRESH_CI=true
GRANT_SUCCESSOR_REQUIRES_FINAL_EXACT_SOURCE_REVIEW=true

STOP_BOUNDARY=BEFORE_ANY_REAL_T1_U11_TARGET_LOAD_BINDING_MUTATION_SERVICE_START_USB_OR_HOST_U11_PERSISTENCE
```

A future user authorization does not retroactively make this preauthorization manifest executable. The repository must create a grant-only successor, run fresh exact-head CI, and perform a final exact-source review before any real T1 U11 execution.
