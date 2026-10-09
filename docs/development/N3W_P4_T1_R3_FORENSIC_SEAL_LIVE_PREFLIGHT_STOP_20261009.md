# N3-W P4 T1 — R3 first live execution STOP at R2 forensic-seal revalidation (2026-10-09)

## 1. Actual Mac Terminal evidence (sanitized)

The user executed the exact ten-file R3 Mac one-shot. Output supplied:

```text
SOURCE_EXACT_TEN_FILES=PASS
R5_PRIVATE_AND_LIVE_PREFLIGHT=AUTOMATED
R3_TRANSACTION_STATE=ABSENT
R3_MANAGER_RUNNING=true
R3_MANAGER_ORIGINAL_ID=true
R3_BROKER_RUNNING=true
R3_BROKER_ORIGINAL_ID=true
R3_BROKER_START_RESTART_UNCHANGED=true
R3_DEPLOY_STOP_CODE=R3_FORENSIC_SEAL_INVALID
T1_FRESH_MANAGER=STOP:FRESH_MANAGE
```

The final `T1_FRESH_MANAGER` marker is **truncated in the text pasted to the conversation**; do not reconstruct or claim a complete final code. The specific `R3_DEPLOY_STOP_CODE` comes directly from T1 journal's real `P4_FRESH_MANAGER_DEPLOY=STOP:R3_FORENSIC_SEAL_INVALID` output.

## 2. Source-order interpretation

R3 exact immutable ten-source code `9441a73658d21566f981e7986b0e0de9093d14da`. The Mac launcher invokes R3 operator preflight, followed by `r3_seal.seal_r2(private)` and supervised `execute`. On the server, `LiveOps.preflight` calls `r3_seal.require_r3_seal(private)` before `TransactionState.create`, before fresh R3 RW directory creation, before stopped shadow creation, and before any old Manager stop. This translates any `r3_seal.SealStop` to the observed `R3_FORENSIC_SEAL_INVALID`.

Therefore:
- The R3 production transaction journal was not created, consistent with `R3_TRANSACTION_STATE=ABSENT`.
- R3 old-Manager stop was not reached; original Manager remains alive and original identity-bound.
- Broker remains running with its original identity, start and restart history unchanged.
- R2/R3 private stage and R2 stopped shadow should be preserved. The R3 forensic seal **may** have been created prior to the failure; do not erase it, infer it is valid, or rerun the operator.
- The error code is **not** the exact root cause. It masks different possible `SealStop` causes (e.g. changed R2 journal/shadow snapshot hash, original R2 evidence drift, or missing/insecure seal) until read-only evidence identifies the specific source.

## 3. Required next action and strict STOP

```text
CURRENT_GATE=N3W_P4_T1_R3_FORENSIC_SEAL_READONLY_DIFF
R3_REAL_PRODUCTION_RESULT=STOP_PREFLIGHT
ORIGINAL_MANAGER_RUNNING=true
BROKER_RUNNING_ORIGINAL_UNCHANGED=true
R3_TRANSACTION_STATE=ABSENT
R3_LIVE_CUTOVER_REACHED=false
R3_PRODUCTION_RETRY_AUTHORIZED=false
R3_PRIVATE_STAGE_OR_SEAL_CLEANUP=false
R2_PRIVATE_JOURNAL_SHADOW_FRESH_DIRS=KEEP
R5_BACKUP_OLD_RW_ROOTS=KEEP
BROKER_MUTATION=false
BOARD_BOOT=false
SETUP_SECRET_IMPORT=false
MERGE=false
```

Perform one **read-only** T1 probe using staged exact `r3_forensic_seal.py`: compare the R3 0600 saved forensic-seal field names with freshly derived `verify_r2` fields, output only `DIFF_FIELD` names and safe STOP class, never raw hashes, container IDs, inspect, environment, host source paths, key values or secrets. If `verify_r2` raises `SealStop`, report that exact safe error code instead of assuming an inspect hash changed. Only after evidence-driven source review may a replacement R4 isolated gate be designed and a fresh live authorization sought. Never use existing R3 stage/journal or forensic seal as replay authority.
