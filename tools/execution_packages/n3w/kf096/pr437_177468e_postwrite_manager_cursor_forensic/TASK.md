# N3-W PR #437 177468e post-write Manager cursor forensic

Status: PREPARED_FOR_OPERATOR_EXECUTION

## Trigger

The preceding 90-second Manager baseline observer reached its real liveness gate and raised:

```text
StopExecution: Board B canonical seq did not advance enough
```

Its exception printer then raised a second harness-only error because `sys` was not imported:

```text
NameError: name 'sys' is not defined
```

The second error does not erase the first result. Reaching the sequence threshold proves that the prior observer had already passed these checks:

```text
Manager running at start and end
Board B canonical cursor FOUND at start and end
source=direct at start and end
Manager restart count unchanged
Manager StartedAt unchanged
same boot_session during the 90-second window
seq delta < 10
```

The exact seq values and cursor freshness were not persisted before the threshold raise, so product failure is not yet classified.

## Scope

This gate is purely forensic and read-only. It does not reset or access Board B.

```text
BOARD_ACCESS=false
BOARD_RESET=false
BOARD_FLASH_WRITE=false
PRODUCT_NVS_WRITE=false
APPLICATION_SERIAL_OPEN=false
T1_ACCESS=SSH_READ_ONLY
T1_MUTATION=false
```

It observes the same Board B canonical cursor for exactly 30 seconds and reports:
- exact seq before/after and delta;
- source before/after;
- updated_at before/after;
- age of each cursor timestamp at observation time;
- same-boot result;
- Manager restart/start-time continuity;
- activity classification: ADVANCING, STALE, or INCONSISTENT.

No minimum seq delta is used in this forensic gate.

## Execution

```bash
python3 /tmp/n3w-pr437-177468e-postwrite-manager-cursor-forensic.py \
  --t1-target <PRIVATE_T1_SSH_TARGET> \
  --output /tmp/n3w-pr437-177468e-postwrite-manager-cursor-forensic.json
```

Use the result to decide whether the 90-second failure was merely a too-strict threshold, a stale pre-reset canonical cursor, or a real post-write runtime liveness problem.
