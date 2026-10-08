# N3-W P4 private pairing read-only prestage — Mac syntax STOP and exact source repair — 2026-10-08

```text
STAGE=P4_PRIVATE_PAIRING_IPC_AND_SNAPSHOT_READONLY_PRESTAGE
ORIGINAL_EXECUTOR_BLOB_SHA=95b95d1586adb856415dd23565f345ed9753acc4
ORIGINAL_EXECUTOR_RESULT=INVALID_HOST_PYTHON_SYNTAX
ORIGINAL_EXECUTOR_REPLAY=false
HOST_PYTHON_COMPILE=FAILED
HOST_PREFLIGHT_PASS=NOT_PRINTED

AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
T1_ACCESSED=false
BOARD_ACCESS=false
BOARD_WRITE=false
MANAGER_DB_MUTATION=false
SETUP_SECRET_IMPORTED=false
P4_PRODUCT_NORMAL_BOOT_STARTED=false
P4_FIRST_BOOT_AUTHORIZATION_GRANTED=false
STOP=true
```

## 1. Evidence and source of failure

Operator Terminal output stopped at Python compile:

```text
File ".../n3w-p4-private-prestage.XXXXXXXX/executor.py", line 362
    ipc_probe = """import json, os, shutil, stat
                   ^^^^^^
SyntaxError: invalid syntax
```

This was the pre-execution `python3 -m py_compile` command, before the shell printed `HOST_PREFLIGHT_PASS=true` or invoked `python3 executor.py`. Therefore no SSH/T1 access or executor authorization claim could occur. P3 and earlier P4 preboot live closure remain valid.

The nested `ipc_probe = """...` prematurely closed the enclosing `remote = r"""...` literal. Root classification: `EXECUTOR_AUTHORING_SYNTAX_ERROR`, not an ESP32-C6 firmware or Manager product failure.

## 2. Exact minimal source repair

```text
REPAIRED_EXECUTOR_PATH=tools/execution_packages/n3w/auto_safe_fallback/p4_private_pairing_prestage_readonly/executor.py
REPAIRED_EXECUTOR_BLOB_SHA=58959cc509a4e88dae9bb20fda7a14d7d4e6f938
REPAIR_COMMIT=9874532b1d2d2e73dc9624f4f33b54bbcac760ee
CHANGED_SOURCE_LINES=362,380
CHANGE=INNER_TRIPLE_DOUBLE_QUOTES_TO_INNER_TRIPLE_SINGLE_QUOTES_ONLY
OUTER_REMOTE_RAW_TRIPLE_DOUBLE_QUOTES_UNCHANGED=true
SOURCE_REBIND_STATIC_REVIEW=PASS
MAC_PYTHON_COMPILE=NOT_YET_CONFIRMED
T1_RUNTIME_PROBE=NOT_EXECUTED
```

Source diff is exactly two delimiter replacements. The repaired file has one outer triple-double-quoted remote string and one enclosed triple-single-quoted IPC probe, no source/firmware change, no board access, no secret import, and no extra host mutation.

## 3. Corrected preflight required before any T1 contact

Mac bootstrap for the new exact executor must check PR state/HEAD and exact Git blob, then run:

```text
HOST_STAGE_1=python3 -m py_compile executor.py
HOST_STAGE_2=Python AST parse of outer module with exact embedded remote string
HOST_STAGE_3=Python AST parse of embedded remote script with exact embedded ipc_probe string
HOST_STAGE_4=python3 executor.py only after stages 1..3 pass
```

The stage 2 and stage 3 AST parsing validates the two nested scripts without running either or opening a socket.

If any preflight fails, STOP without T1 access and without claiming the one-shot read-only authorization. Do not reuse the original malformed SHA. A later remote execution begins only after exact Mac-local compilation/AST checks pass, and remains bounded to read-only Manager IPC and preboot snapshot readiness.

## 4. Next execution boundary

```text
NEXT_ONE_GATE=N3W_CLEAN_PRODUCT_FIRST_PAIR_P4_PRIVATE_PAIRING_IPC_AND_SNAPSHOT_READONLY_PRESTAGE_20261008_01_R1
NEXT_SCOPE=CORRECTED_EXACT_EXECUTOR_HOST_PREFLIGHT_THEN_ONCE_READONLY_T1
CURRENT_STATUS=REPAIR_PREPARED_NOT_EXECUTED
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
AUTO_RETRY=false
AUTO_P4=false
PRODUCT_NORMAL_BOOT_AUTHORIZATION_GRANTED=false
STOP=true
```

This repair is limited to the host-only P4 prestage executor. The real optical QR identity binder and private Setup Secret importer remain separate future implementation and authorization gates. Do not boot the board or start a pending pairing transaction to test this repair.
