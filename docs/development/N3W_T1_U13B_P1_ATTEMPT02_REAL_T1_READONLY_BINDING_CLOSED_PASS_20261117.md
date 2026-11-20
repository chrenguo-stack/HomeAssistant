# N3-W T1 U13B P1 Attempt 02 real-T1 read-only binding CLOSED_PASS — 2026-11-17

## Result

```text
GATE=N3W_T1_U13B_REAL_T1_READONLY_BINDING_PREFLIGHT_20261117_01
ATTEMPT=02
EXECUTION_ID=u13b-p1-readonly02-20261117T122835Z
EXACT_EXECUTION_PACKAGE=e41723d8fa278021db95fc497426678a8a52d3c2
ATTEMPT02_RC=0
STATUS=U13B_REAL_T1_READONLY_BINDING_PASS

T1_ACCESS=true
READ_ONLY=true
FRESH_BINDING=true
EXPECTED_TERMINAL_U13A=true
ROLLBACK_ELIGIBLE=false
NEW_CLEAN_OTA_REQUIRED=true
```

## Fresh terminal binding

```text
HISTORICAL_TRANSACTION_PHASE=U13A_COMMITTED
HISTORICAL_TRANSACTION_STATUS=COMMITTED
HISTORICAL_TRANSACTION_SHA256=06951ac4d8a8723ae808f25d955560052eee02f884ab78f5c6ffe0580e84b600
HISTORICAL_USB_PHASE_SHA256=11d150bc3828a0e400a90670671a607a02f6d1a53350ef53b3366d95fcb64288
HISTORICAL_U13A_AUTHORIZATION_CLAIMED=true
HISTORICAL_U13A_AUTHORIZATION_CONSUMED=true
HISTORICAL_U13A_REPLAY_PERMITTED=false
```

The fresh real-T1 probe confirms the historical terminal U13A transaction remains exact and committed. The successful historical U13A transition is terminal and remains non-replayable.

The delegated U13A status record reports historical transaction/USB mutation as true because those mutations occurred during the already completed U13A commit. They are historical facts and are intentionally separated from the current P1 probe.

## Current-probe safety result

```text
CURRENT_PROBE_TRANSACTION_MUTATION=false
CURRENT_PROBE_USB_MUTATION=false
CURRENT_PROBE_SERVICE_MUTATION=false
CURRENT_PROBE_IMAGE_MUTATION=false
CURRENT_PROBE_HA_DATA_MUTATION=false
CURRENT_PROBE_AUTHORIZATION_CLAIM=false
CURRENT_PROBE_U13A_TRANSITION=false
CURRENT_PROBE_U13B_TRANSITION=false

U13B_LIVE_EXECUTION_AUTHORIZED=false
NEW_CLEAN_OTA_MUTATION_AUTHORIZED=false
CONTROLLED_ROLLBACK_MUTATION_AUTHORIZED=false
BOARD_ACCESS=false
MERGE=false
```

No T1 transaction, USB metadata, service, image, Home Assistant data, authorization, U13A transition, U13B transition, board or merge mutation occurred during Attempt 02.

## Evidence and archive

Raw evidence remains in the operator's approved private Mac evidence root and is intentionally not uploaded to public GitHub. This public record retains the execution ID, exact package authority, terminal hashes and sanitized result.

```text
PRIVATE_RAW_EVIDENCE_PRESENT=true
PRIVATE_RAW_EVIDENCE_PUBLICLY_EXPOSED=false
PUBLIC_RESULT_ARCHIVED=true
UNARCHIVED_CRITICAL_KNOWLEDGE=0
```

A post-execution shell session-save warning occurred after the executor had already returned RC=0 and emitted the complete binding result. It does not alter the executor result or the T1 read-only evidence.

## Stop boundary

P1 is CLOSED_PASS. This closure does not authorize a new clean OTA transaction, U13B live rollback, board access or merge.

```text
P1_CLOSED_PASS=true
NEXT_MUTATION_BOUNDARY=NEW_CLEAN_OTA_REQUIRES_SEPARATE_AUTHORIZATION
U13B_LIVE_ROLLBACK_NOT_ENTERED=true
BOARD_NOT_ENTERED=true
MERGE_NOT_ENTERED=true
```
