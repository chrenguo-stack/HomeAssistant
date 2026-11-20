# N3W T1 U12 read-only preflight + performance instrumentation source design — 2026-11-17

## 1. Gate and authority

```text
NEXT_ONE_GATE=N3W_T1_U12_READONLY_PREFLIGHT_AND_PERFORMANCE_INSTRUMENTATION_SOURCE_DESIGN
PR=807
BASE_HEAD=14fffb6ce46cc92bcba1358a9d7eba78e77e3fb9
MAIN_HEAD=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
U11_PHYSICAL_COMPLETE=true
LIVE_TRANSACTION_PHASE=U11_TARGET_INSTALLED_STARTED
LIVE_TRANSACTION_SHA256=33350ba47e0af43b4f0e11fac990e24924f22057da60d980b26453b4e80e0471
R42_AUTHORIZATION_CONSUMED=true
R42_REPLAY_PERMITTED=false
U12_ACCEPTANCE=false
U12_LIVE_EXECUTION=false
U13_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

The handoff exact head has 16/16 workflows SUCCESS. This gate is source/read-only only. It does not authorize U12 persistence, U13+, board work, R42 replay, service restart, downgrade/re-upgrade, or merge.

## 2. Source decision

Do not add a new production U12 module in this gate.

The read-only preflight is implemented as a bounded execution package under `tools/execution_packages/n3w/r7a/`. This avoids creating an orphan production module before the U12 live controller is authorized and preserves the module-lifecycle rule that production code must be reachable from a real product entry point.

The package reuses the existing SSH/evidence transport and installed transaction validator, but independently observes the post-R42 runtime. It never loads an image, rewrites Compose, starts/stops/restarts services, writes the transaction, writes the USB mirror, or calls `record_target_accepted()`.

## 3. U12 fresh read-only preflight contract

The preflight must prove all of the following from the real T1 before a later U12 live gate can be authorized:

```text
EXACT_U11_HOST_TRANSACTION=true
EXACT_U11_USB_PHASE_MIRROR=true
ALL_FOUR_USB_MIRROR_DOCUMENTS_CONSISTENT=true
R42_SUCCESS_LEDGER_PRESENT=true
R42_FAILURE_LEDGER_ABSENT=true
R42_CLAIMED_CONSUMED_NO_REPLAY=true
TARGET_HOMEASSISTANT_RUNNING=true
TARGET_HOMEASSISTANT_RUNTIME_ID_EXACT=true
PRODUCTION_CONFIG_RW_BIND=true
MANAGER_RUNNING_EXACT=true
BROKER_RUNNING_EXACT=true
SERVICES_OWNER_ACTIVE=true
BROKER_LISTENER_CONTRACT=true
MANAGER_MQTT_CURRENT_AUTHENTICATION=true
HOMEASSISTANT_MQTT_CURRENT_AUTHENTICATION=true
HOMEASSISTANT_HTTP_READY=true
U12_STATE_ROOT_ABSENT=true
U12_ACCEPTANCE=false
U13_PLUS=false
```

Any mismatch is a STOP. A PASS establishes only `U12_READONLY_ELIGIBLE=true`.

The preflight hashes only small authority/source/JSON files. It must not hash or reread the 835 MB target archive or the predecessor archive for timing purposes, must not perform an additional image load, and must not restart any service.

## 4. Timing contract

Elapsed durations use `time.monotonic_ns()` and are emitted as integer milliseconds. Wall-clock timestamps may be added later for forensic correlation, but elapsed acceptance decisions never depend on wall clock.

The read-only preflight records:

```text
installed_source_verification_ms
transaction_verification_ms
r42_ledger_verification_ms
usb_mirror_verification_ms
runtime_identity_verification_ms
broker_listener_readiness_ms
mqtt_acceptance_observation_ms
homeassistant_readiness_observation_ms
acceptance_readiness_observation_ms
preflight_total_ms
```

These are Gate-A diagnostic timings only. They are not the final U12 acceptance measurement and are not the normal OTA baseline.

## 5. U12 live instrumentation design for the next gate

The future U12 live controller should reuse existing read-only probes and add timing around the acceptance operation without changing safety ordering.

Recommended order:

```text
fresh U11 preflight
-> start U12 monotonic timer
-> broker listener readiness
-> Manager MQTT current-auth readiness
-> Home Assistant MQTT current-auth readiness
-> Home Assistant HTTP readiness
-> production service-owner/runtime/binding final check
-> build record_target_accepted(current)
-> sync U12 USB metadata
-> persist host U12 transaction
-> stop U12 timer
-> persist supplemental sanitized performance evidence
-> terminal read-only reconciliation
```

The functional U12 transition remains the authority for acceptance. Performance evidence is supplemental and must not weaken or skip a safety check.

If supplemental performance evidence persistence fails after U12 itself is already durable, do not replay the U12 mutation. Report a separate performance-evidence failure and reconcile the durable U12 state read-only before any later gate.

## 6. Long-running execution vs client/SSH wait

U12 itself should be short, but the same instrumentation contract must be reusable by a future clean OTA.

For long operations, remote execution and client observation must be separate:

```text
remote durable execution state
!=
SSH client wait state
```

A client timeout after a claim must return `STOP_UNKNOWN` locally, never authorize replay, and trigger status/reconciliation against durable remote ledgers. Durable remote PASS is authoritative when independently verified.

No future clean OTA should depend on one SSH call remaining open for the complete upgrade duration.

## 7. Future clean OTA phase timings

A legitimate future normal OTA should collect, without deliberate downgrade/re-upgrade:

```text
OTA_TOTAL
DOWNLOAD_OR_ARTIFACT_PREPARE
TARGET_ARCHIVE_VERIFY
HA_DATA_BACKUP
PREDECESSOR_RECOVERY_EXPORT_VERIFY
TARGET_IMAGE_LOAD
TARGET_RUNTIME_VERIFY
BINDING_PUBLISH
SERVICES_START
HOMEASSISTANT_READY
U12_ACCEPTANCE
USER_VISIBLE_SERVICE_DOWNTIME
```

No extra full-file hash, archive reread, image load, service restart, or duplicate validation may be introduced solely for timing.

Engineering targets remain:

```text
USER_VISIBLE_SERVICE_DOWNTIME_TARGET_SECONDS<=300
USER_VISIBLE_SERVICE_DOWNTIME_HARD_LIMIT_SECONDS<=600
NO_PROGRESS_VISIBILITY_LIMIT_SECONDS<=300
OTA_TOTAL_TARGET_SECONDS<=1800
```

R42's ~47-minute recovery remains an abnormal recovery reference, not the normal-production OTA baseline.

## 8. Source/test scope

Added in this gate:

- `tools/execution_packages/n3w/r7a/u12_target_acceptance_readonly_preflight/executor.py`
- `tools/execution_packages/n3w/r7a/u12_target_acceptance_readonly_preflight/manifest.json`
- `tests/tools/test_n3w_t1_u12_target_acceptance_readonly_preflight.py`
- this design record.

Focused tests must prove:

- no mutation command is present in the U12 preflight payload;
- exact U11/R42/USB/runtime authorities are checked before eligibility;
- monotonic elapsed timing is used;
- large target/predecessor archives are not reread or rehashed;
- existing U12 state or an R42 failure ledger fail closed;
- U12 live remains unauthorized.

## 9. Stop boundary

```text
R42_REPLAY=false
U12_LIVE_EXECUTION=false
TRANSACTION_MUTATION=false
USB_MUTATION=false
SERVICE_MUTATION=false
U13_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

After source review and applicable CI are green, the next physical action may only be the packaged real-T1 U12 read-only preflight. Any U12 durable mutation remains a separate explicit authorization boundary.
