# N3-W T1 U12 Read-only Preflight Execution Closure — 2026-11-17

## 1. Scope

This record closes the authorized real-T1 **U12 read-only preflight only**.

It does **not** authorize or record:
- U12 durable acceptance transition;
- transaction mutation;
- USB metadata mutation;
- service mutation;
- R42 replay;
- U13 or later phases;
- board access;
- PR merge.

## 2. Source authority

```text
PR=807
SOURCE_HEAD=f535284fc1095c8cba214ac671a4c2793dadc1eb
SOURCE_HEAD_CI=16_OF_16_SUCCESS
EXECUTION_ID=u12-readonly01-20261116T235054Z
RESULT_SCHEMA=gh.n3w-t1-u12-readonly-preflight/1
STATUS=U12_READONLY_PREFLIGHT_PASS
REMOTE_RETURNCODE=0
```

The exact source head was confirmed green before the physical read-only execution.

## 3. Durable state continuity

```text
U11_DURABLE_PASS=true
TRANSACTION_PHASE=U11_TARGET_INSTALLED_STARTED
TRANSACTION_SHA256=33350ba47e0af43b4f0e11fac990e24924f22057da60d980b26453b4e80e0471

R42_CLAIMED=true
R42_CONSUMED=true
R42_FAILURE_LEDGER_PRESENT=false
R42_REPLAY_PERMITTED=false
R42_SUCCESS_SHA256=a68199255967d63dd8f009aa71e254c16dee895649e57656d3da5c46ac011921
R42_REPLAY=false
```

The U12 read-only execution observed the existing durable U11/R42 state; it did not alter it.

## 4. Recovery-media / U11 mirror continuity

Resolved recovery media:

```text
FILESYSTEM_UUID=967cf065-abe5-49ee-8499-7c3f50d2c48f
SOURCE_KIND=block_device
MOUNT_TARGET=/run/n3w-t1-ota/media/ca89774eb4254d0f
MIRROR_EXACT=true
```

Observed exact U11 mirror SHA-256 values:

```text
MANIFEST_SHA256=3aa5e247636b1bb891aa151a8fb0219294d4803ea22dc7b66d821f6250d9e728
PHASE_SHA256=8f2ba37e93577452ffd2b6dfc1cc5febbf717d1bf8c3ed2de8ec57ccf69e6921
CONTENT_AUTHORITY_SHA256=3da14eb03447beaf38579a3fa5e4e076d4f3e806f7a787cbc0bba6b2cb1b8727
CHECKSUMS_SHA256=2a21aa2b8fb362242fa087a49a2ebfb93caf65d1dd8a6f9c6da44edbb9f8c7f2
```

## 5. Runtime target acceptance observations

```text
BROKER_RUNNING=true
MANAGER_RUNNING=true
HOMEASSISTANT_RUNNING=true
SERVICES_OWNER_ACTIVE=true
PRODUCTION_CONFIG_MOUNTED=true
TARGET_RUNTIME_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
SOURCE_HASH_COUNT=15
```

Listener contract:

```text
TCP_8883=1
TCP_47110=1
UDP_47111=1
TCP_47112=0
```

Current authentication/readiness:

```text
MANAGER_MQTT_AUTHENTICATED=true
HOMEASSISTANT_MQTT_AUTHENTICATED=true
HOMEASSISTANT_HTTP_STATUS=401
```

HTTP 401 is accepted by this preflight as proof that the Home Assistant HTTP endpoint is responding and requires authentication.

## 6. Performance instrumentation observations

Top-level monotonic timings:

```text
INSTALLED_SOURCE_VERIFICATION_MS=92
TRANSACTION_VERIFICATION_MS=409
R42_LEDGER_VERIFICATION_MS=3
USB_MIRROR_VERIFICATION_MS=73
RUNTIME_IDENTITY_VERIFICATION_MS=702
ACCEPTANCE_READINESS_OBSERVATION_MS=1822
PREFLIGHT_TOTAL_MS=3106
```

Nested readiness timings:

```text
BROKER_LISTENER_READINESS_MS=83
MQTT_ACCEPTANCE_OBSERVATION_MS=1138
HOMEASSISTANT_READINESS_OBSERVATION_MS=74
```

These values are **U12 read-only preflight timing evidence only**.

```text
NORMAL_OTA_BASELINE_AVAILABLE=false
PERFORMANCE_INSTRUMENTATION_DESIGN_ONLY=true
```

No downgrade/re-upgrade or OTA replay was performed for benchmarking. Therefore this execution must not be used as a normal OTA total-duration baseline.

## 7. Mutation boundary proof

```text
READ_ONLY=true
T1_ACCESS=true
REMOTE_PREFLIGHT_INVOKED=true
SSH_MASTER_CLEANUP=true

TRANSACTION_MUTATION=false
USB_MUTATION=false
SERVICE_MUTATION=false

U12_READONLY_ELIGIBLE=true
U12_ACCEPTANCE=false
U12_LIVE_EXECUTION_AUTHORIZED=false
U12_TRANSITION=false

U13_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

## 8. Closure decision

```text
U12_READONLY_PREFLIGHT=PASS
U11_DURABLE_PASS=true
U12_READONLY_ELIGIBLE=true
U12_ACCEPTANCE=false
NORMAL_OTA_BASELINE_AVAILABLE=false
UNAUTHORIZED_MUTATION_OBSERVED=false
```

The real-T1 U12 read-only preflight is closed PASS.

The repository and physical evidence are sufficient to state that the current U11 target is eligible for a future separately authorized U12 live acceptance operation. No such live operation was performed here.

## 9. Stop point

```text
STOPPED_BEFORE_U12_LIVE_MUTATION=true
NEXT_U12_LIVE_AUTHORIZATION_REQUIRED=true
U13_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

This closure intentionally stops before any U12 durable mutation.
