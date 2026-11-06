# N3-W T1 Core Updater — Home Assistant runtime-template convergence read-only closure

Date: 2026-11-05

## Gate

```text
TASK=N3W_T1_CORE_UPDATER_HOMEASSISTANT_RUNTIME_TEMPLATE_CONVERGENCE_READONLY_PREFLIGHT_20261105_01
RESULT=CLOSED_PASS

EXECUTION_HEAD=60af31fc661434c9b5ae3166a3f9ebafcde7ce63
AUTHORITY_PARENT_HEAD=9aa8c9b42f32d94804decdb6b360ade58e4d728d
INSPECTOR_BLOB=9e8ad6ced381e6b4fa9ec146b4f143769c316ceb
CURRENT_AUTHORITY_BLOB=07ceb3b352f21d925127caa71304cc3b29827fdb
```

## Real T1 result

The exact versioned executor completed two consecutive read-only inspections against the real T1.

```text
STATUS=PASS
DOUBLE_READ_STABLE=true

EXPECTED_HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_BINDING_MODE=legacy_static
CANDIDATE_BINDING_MODE=dynamic

CURRENT_COMPOSE_SHA256=9ea58161d5f8e24233bacbfe1f31edd5f6f6c62c272271823788c0c5b59e8357
CURRENT_ENV_SHA256=c39fdd5fad101d0283297f2d29a454f3dcd516ee5426e1eeb392bff1e5d7eeb0
CANDIDATE_COMPOSE_SHA256=f5fc319e155e89c50d1a52fa7813a00f3cf36b4203937cae0d99c9ae5dbb9d15
CANDIDATE_ENV_SHA256=ce6ecf840fd7eff13a8471793706313d3b43c2f6424f590b3c8451c89bf1b83b

CURRENT_RENDER_SHA256=1705f3a87f058f68a4846865ebd52270d5ddd812ad4138ef37eff5cbbc077e7c
CANDIDATE_RENDER_SHA256=1705f3a87f058f68a4846865ebd52270d5ddd812ad4138ef37eff5cbbc077e7c
RENDER_SEMANTICALLY_EQUAL=true
```

The complete rendered Compose semantic hash is identical before and after the proposed
Home Assistant binding convergence.

## Mutation boundary

```text
MUTATION=false
PERSISTENT_T1_FILE_WRITE=false
TEMPORARY_SCRATCH_WRITE=true
SERVICE_RESTART=false
IMAGE_LOAD=false
UPDATER_APPLY=false
UPDATER_ROLLBACK=false
BOARD_ACCESS=false
RAW_TARGET_PUBLIC_OUTPUT=false
```

The only target-side writes were temporary scratch files used by `docker compose config`; they
were automatically removed. No product path was written.

## Earlier transport STOP

The first versioned attempt stopped with `remote_report_json_invalid`. A bounded direct read-only
transport diagnostic then proved:

```text
REMOTE_RC=0
STDERR_BYTES=0
INSPECTOR_STATUS=PASS
```

That STOP was not evidence of Home Assistant semantic drift. The subsequent exact versioned
executor run completed both required reads and closed this gate.

## Evidence handling

Private raw evidence remains local to the operator machine:

```text
inspection-1.json
inspection-2.json
result.json
```

The public repository stores only sanitized hashes and verdicts. The raw T1 locator is not
published.

## Closure meaning

This gate proves the minimal Home Assistant runtime-template convergence:

```text
legacy_static -> dynamic
```

is semantically neutral for the currently accepted Home Assistant predecessor image.

It does not authorize a live template mutation and does not prove the Home Assistant 2026.10.4
target artifact.

## Next gate

```text
NEXT_ONE_GATE=N3W_T1_CORE_UPDATER_HOMEASSISTANT_2026_10_4_EXACT_ARM64_ARTIFACT_BUILD_AND_COMPONENT_TARGET_20261105_01

NEXT_GATE_T1_ACCESS=false
NEXT_GATE_T1_MUTATION=false
LIVE_HA_UPGRADE_READY=false
STACK_1_1_0_BUILD=false
```
