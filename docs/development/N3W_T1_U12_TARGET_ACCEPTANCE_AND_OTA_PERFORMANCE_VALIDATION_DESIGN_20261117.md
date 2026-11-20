# N3W T1 U12 target acceptance + OTA performance validation design — 2026-11-17

## 1. Purpose

U11 is physically complete after R42 timeout reconciliation. U12 has not been entered.

The next stage must do two things together:

1. close U12 target acceptance safely from the exact durable U11 state;
2. add production-oriented OTA performance evidence so future clean upgrades can be judged by user-visible downtime and total upgrade duration instead of only PASS/FAIL.

This document does **not** authorize U12 live execution, R42 replay, board access, merge, or any other live mutation.

## 2. Current authority

```text
PR=807
PR_STATE=OPEN_DRAFT_UNMERGED
MAIN_HEAD=3e7faf258d670c9eaf3be6ede9bbb02df2ac009d
R42_CLOSURE_COMMIT=033bfd50ef9ffe622cb98da22e219ce7a4580c11
R42_EXECUTION_ID=u11-r42-live02-20261116T152940Z
R42_DURABLE_RESULT=U11_R42_POST_R40_SUCCESSOR_RECOVERY_PASS
R42_AUTHORIZATION_CLAIMED=true
R42_AUTHORIZATION_CONSUMED=true
R42_REPLAY_PERMITTED=false
LIVE_TRANSACTION_PHASE=U11_TARGET_INSTALLED_STARTED
LIVE_TRANSACTION_SHA256=33350ba47e0af43b4f0e11fac990e24924f22057da60d980b26453b4e80e0471
USB_TRANSACTION_PHASE=U11_TARGET_INSTALLED_STARTED
U11_PHYSICAL_COMPLETE=true
U12_ACCEPTANCE=false
U13_PLUS=false
```

## 3. U12 stage boundary

U12 must begin with a fresh read-only preflight proving:

- host transaction is exact U11;
- USB phase mirror is exact U11;
- all four USB mirror documents remain consistent;
- R42 success ledger exists and R42 failure ledger does not supersede it;
- R42 authorization remains consumed/no-replay;
- exact target Home Assistant image/runtime is running;
- production `/config` RW bind is present;
- Manager and Broker are running with expected identities;
- services owner is active;
- no U12 acceptance or U13+ state already exists.

Any drift stops before U12 mutation.

## 4. Performance validation scope

Performance evidence is a product acceptance concern, not an R42 recovery replay.

The stage must preserve two separate measurements:

### 4.1 Current U12 acceptance timing

Measure the duration of the U12 acceptance checks themselves on the current real T1:

- Home Assistant readiness / HTTP health;
- Manager readiness;
- Broker listener readiness;
- MQTT application-path acceptance;
- required production service ownership checks;
- final U12 durable persistence.

This measures the target-acceptance phase only.

### 4.2 Future clean OTA end-to-end baseline

A later **clean, normal production OTA** must collect end-to-end timings without deliberately replaying the current upgrade.

Required phase timings:

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

R42 recovery timing must be retained only as an anomaly/recovery reference and must not be treated as the normal-production baseline.

## 5. Instrumentation contract

Performance instrumentation should be lightweight and must not materially increase upgrade duration.

Requirements:

- use monotonic timing for elapsed durations;
- optionally retain UTC wall-clock timestamps for forensic correlation;
- record phase start/end/duration in durable structured evidence;
- do not hash or reread large archives merely for timing;
- do not add extra Docker image loads;
- do not restart services solely to collect timing data;
- do not expose credentials, private host locators, MQTT secrets, or raw private evidence;
- preserve existing transaction safety/ordering;
- timing failure must never weaken upgrade safety checks;
- execution and status observation should be decoupled so a client/SSH timeout cannot turn a durable remote PASS into a false operational failure.

## 6. Production UX targets

These are engineering acceptance targets, not yet proven measurements:

```text
USER_VISIBLE_SERVICE_DOWNTIME_TARGET_SECONDS<=300
USER_VISIBLE_SERVICE_DOWNTIME_HARD_LIMIT_SECONDS<=600
NO_PROGRESS_VISIBILITY_LIMIT_SECONDS<=300
OTA_TOTAL_TARGET_SECONDS<=1800
OTA_OVER_1800_SECONDS=PERFORMANCE_INVESTIGATION_REQUIRED
```

The most important metric is user-visible service downtime, not raw background preparation duration.

## 7. R42 performance finding

R42 Attempt 02 used a 2400-second local SSH execute timeout but the remote recovery completed later. Manager/Home Assistant runtime start evidence is roughly 47 minutes after the execution-id timestamp.

The R42 recovery path is intentionally heavier than normal U11 because it includes repeated successor read-only verification and recovery-asset integrity work. Therefore:

```text
R42_47_MINUTES_NORMAL_PRODUCTION_BASELINE=false
R42_TIMEOUT_FALSE_NEGATIVE=true
NORMAL_OTA_PERFORMANCE_NOT_YET_PROVEN=true
```

The 47-minute R42 result must trigger instrumentation and clean-baseline work, but it must not be presented as expected customer upgrade duration.

## 8. Acceptance gates

### Gate A — U12 read-only preflight + timing design
Must be source-reviewed and CI-green before any U12 live acceptance.

### Gate B — U12 live target acceptance
Requires separate live authorization. Must stop after U12 and before U13+.

### Gate C — clean normal OTA performance baseline
Performed only when a legitimate future clean upgrade is available. Do not downgrade/re-upgrade or replay a consumed transaction solely to produce a benchmark.

## 9. Required outputs

U12 closure should report at least:

```text
U12_ACCEPTANCE_RESULT
U12_ACCEPTANCE_DURATION_MS
HOMEASSISTANT_READINESS_DURATION_MS
MQTT_ACCEPTANCE_DURATION_MS
USER_VISIBLE_DOWNTIME_MEASURED
PERFORMANCE_TARGET_STATUS
NORMAL_OTA_BASELINE_AVAILABLE
```

If normal end-to-end baseline is not yet available, state `NORMAL_OTA_BASELINE_AVAILABLE=false`; do not substitute R42 recovery timing.

## 10. Next gate

```text
NEXT_ONE_GATE=N3W_T1_U12_READONLY_PREFLIGHT_AND_PERFORMANCE_INSTRUMENTATION_SOURCE_DESIGN
LIVE_MUTATION=false
R42_REPLAY=false
U12_LIVE_EXECUTION=false
U13_PLUS=false
BOARD_ACCESS=false
MERGE=false
```
