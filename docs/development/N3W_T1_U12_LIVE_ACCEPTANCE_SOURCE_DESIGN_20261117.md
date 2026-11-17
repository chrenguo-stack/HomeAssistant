# N3-W T1 U12 live acceptance source design — 2026-11-17

## 1. Authority and entry state

```text
PR=807
READONLY_SOURCE_HEAD=f535284fc1095c8cba214ac671a4c2793dadc1eb
READONLY_CLOSURE_COMMIT=5ecb9345bffa2c4334ae81f6aaae14dfa1720113
READONLY_EXECUTION_ID=u12-readonly01-20261116T235054Z
READONLY_RESULT=U12_READONLY_PREFLIGHT_PASS
U11_DURABLE_PASS=true
U12_ACCEPTANCE=false
USER_U12_LIVE_AUTHORIZATION=true
```

The user explicitly authorized continuing U12 live acceptance without a second authorization prompt. This authorization applies only to the bounded U12 acceptance transition defined here.

## 2. Allowed mutation

The live gate may perform only the durable state changes required to enter U12:

```text
U11_TARGET_INSTALLED_STARTED
-> U12_TARGET_ACCEPTANCE
```

Allowed writes:

- one-shot U12 gate authorization claim/progress/success or failure ledger;
- USB transaction mirror update from U11 phase to U12 phase;
- host Home Assistant USB transaction update from U11 to U12;
- sanitized U12 acceptance performance evidence.

The gate does not restart services, load/delete images, change runtime bindings, replay R42, enter U13, access boards, or merge PR #807.

## 3. Execution order

The executor preserves the established fail-closed ordering:

```text
fresh real-T1 U12 read-only preflight
-> create one-shot U12 claim
-> lock host transaction
-> revalidate exact U11 transaction
-> revalidate R42 consumed/no-replay
-> revalidate bound USB
-> revalidate target runtime and production /config
-> revalidate broker listener contract
-> revalidate Manager + Home Assistant current MQTT authentication
-> revalidate Home Assistant HTTP readiness
-> record_target_accepted(U11)
-> sync U12 USB transaction metadata
-> persist host U12 transaction
-> terminal U12 read-only verification
-> persist supplemental U12 performance evidence
-> persist success ledger
-> STOP before U13+
```

USB metadata is persisted before the host transaction, matching the existing transaction ordering used by earlier destructive phases.

## 4. Transition authority

The live executor does not rewrite installed product source.

It binds the repository version of `tools/n3w_t1_core_updater_ha_usb.py` into the exact execution package and loads only:

- `record_target_accepted()`;
- `destructive_cutover_allowed()`.

The existing transaction authorization from U9 remains consumed and valid. U12 adds a separate one-shot outer execution claim only to prevent replay of this physical gate.

## 5. Failure and replay behavior

Before the outer U12 claim, any failure is safe to retry after correcting the cause.

After the claim:

```text
REPLAY_PERMITTED=false
```

A client/SSH error triggers status reconciliation instead of blind replay.

If the host transaction is already durable U12, terminal U12 evidence is authoritative and the executor reports a reconciled PASS when runtime/readiness also remain valid.

If USB metadata reached U12 but the host transaction remains U11, the executor reports:

```text
STOP_PARTIAL_U12_USB_ONLY
```

and does not complete or replay U12 automatically.

## 6. Performance evidence

U12 live records monotonic elapsed timing for the acceptance phase, including:

```text
U12_ACCEPTANCE_DURATION_MS
ACCEPTANCE_READINESS_DURATION_MS
BROKER_LISTENER_READINESS_MS
MQTT_ACCEPTANCE_DURATION_MS
HOMEASSISTANT_READINESS_DURATION_MS
```

No service is deliberately interrupted by this gate, therefore:

```text
USER_VISIBLE_DOWNTIME_MEASURED=false
NORMAL_OTA_BASELINE_AVAILABLE=false
PERFORMANCE_TARGET_STATUS=U12_ACCEPTANCE_PHASE_ONLY_PASS
```

This evidence must not be presented as the normal end-to-end OTA baseline.

## 7. Stop boundary

```text
U12_LIVE_EXECUTION_AUTHORIZED=true
R42_REPLAY=false
SERVICE_MUTATION=false
IMAGE_MUTATION=false
U13_PLUS=false
BOARD_ACCESS=false
MERGE=false
STOP_AFTER_DURABLE_U12_BEFORE_U13_PLUS=true
```
