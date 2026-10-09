# N3-W P4 — R2 forensic seal and isolated R3 Manager replacement authority

## Explicit authorization and exact scope

2026-10-09: user replied **“同意授权”** immediately after the R2 OomKillDisable source-only closure and explanation that R3 production operations require a fresh explicit authorization. Treat this as authorization for **one R3** Manager-only live replacement **only after** strict R2 forensic verification, an independent new R3 transaction and current-source tests. No Broker/network/system/TLS change; no old container or old three RW source deletion; no R5 root-private backup deletion; no board first boot; no Setup Secret import; no PR merge.

```text
TASK=N3W_P4_T1_R2_FORENSIC_SEAL_AND_R3_RESUME
NEW_R3_LIVE_AUTHORIZATION=GRANTED_ONCE
AUTHORIZATION_ID=N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_LIVE_DEPLOY_R3
R2_RESULT=FAIL_CLOSED_SHADOW_HOST_SECURITY_PARITY
R2_LAST_JOURNAL_PHASE=FRESH_SOURCES_PREPARED_EMPTY
R2_OLD_MANAGER_STOPPED=false
R2_ROLLBACK_RESULT=PASS
R2_ORIGINAL_MANAGER_RUNNING=true
R2_BROKER_UNCHANGED=true
R2_SHADOW=STOPPED_PRESERVE
R2_JOURNAL=RETAIN_NO_RESET
R2_FRESH_ROOTS=RETAIN
R2_SYSTEMD_UNIT_FAILED=RETAIN
R3_LIVE_RESULT=NOT_YET_OBSERVED
```

## T1-sourced read-only evidence

The R2 shadow versus original HostConfig comparison identified exactly **one** difference: `OomKillDisable` original `None`, stopped shadow `False`; all other inspected host fields equal. Both representations allow the Docker OOM-kill mechanism. The source fix permits exactly `None` and `False` per-side, never `True` or integer `0`. Synthetic tests 111 PASS at earlier closure. The shadow has not been removed; no original Manager stop was reached.

## R3 implementation

R3 deliberately does **not clean or overwrite R2**. Instead it:

1. Locates the unique root-private R5 backup authority on T1. Uses original six-bind live Docker inspect, broker/TLS/network identity; no stale three-mount Compose.
2. Validates R5 immutable archival authority and old Manager still original and running, Broker ID/started_at/restart_count unchanged.
3. Rechecks exact R2 journal (`committed=false`, phase `FRESH_SOURCES_PREPARED_EMPTY`, rollback PASS and original-restored marker, no candidate ID, original and broker identities), retained stopped shadow ID/image/mount/security parity, and untouched empty R2 fresh roots. Any drift => STOP before production service change.
4. Seals SHA256 of R2 journal bytes and canonical shadow inspect into a private 0600 nonreplayable R3 forensic record. No private secrets, Docker inspect, host paths or raw environment variables go to GitHub.
5. Uses **independent names**:
   - `p4-fresh-manager-deploy-r3` staging;
   - `fresh-manager-r3-deploy-state-private.json` durable transaction;
   - `fresh-manager-r3-runtime-state` three new empty RW sources;
   - `greenhouse-manager-p4-r3-shadow`, `greenhouse-manager-p4-r3-rollback`, `greenhouse-manager-p4-r3-failed`;
   - `n3w-p4-fresh-manager-r3-deploy.service` systemd one-shot;
   - `fresh-manager-r3-env-private` temporary env.
6. Performs current source-reviewed shadow contract (including R2 OOM default correction) before stopping original. Then supervised one-shot cutover with exact image, six mounts, three existing RO secrets unchanged, three new empty RW roots, running config/socket/TLS-8883/check-config and zero registration/credential/replay/relay-key postflight proof.
7. The **actual** `fresh_manager_operator.main` now calls the guarded `execute(private,text=text)` path, including rollback upon final operator verification failure; test asserts it seals before guarded execution and rejects unauthorized `main` before seal.
8. Failure prints sanitized transaction phase, rollback status, original Manager running/identity, Broker running/identity and systemd error class. It never sends secret values or host paths to GitHub or terminal. STOP implies no automatic replay; if Docker/host failure occurs rollback may require manual intervention.

## Exact frozen source

```text
NINE_PLUS_SEAL_SOURCE_COUNT=10
EXACT_TEN_SCRIPT_SOURCE_REF=9441a73658d21566f981e7986b0e0de9093d14da
R3_LAUNCHER_CODE_COMMIT=2eb24f25730a353f0cdc575e210e5aa6f92233bc
R3_MAC_LAUNCHER_FILE_BLOB=TO_BE_FINAL_BOUND
R3_REAL_PRODUCTION_COMMAND=ONE_MAC_TERMINAL_COMMAND
THIRD_R3_LIVE_DEPLOY_ATTEMPT_STATUS=PENDING_MAC_OUTPUT
NO_AUTO_RETRY=true
```

R3 package preserved under PR #540 draft branch `tools/n3w-p4-manager-consistent-cold-backup-20261009`. A separate final launcher commit improves sanitized failure classification without changing those ten protected scripts. The launcher pins exact ten Git blob hashes and R3 authorization ID; stops on a preexisting R3 stage or journal. Its startup may produce a private forensic seal file prior to running systemd. Source CI success alone is not production PASS.

## Required outcome evaluation and STOP

Read exactly one Mac result:

- `T1_FRESH_MANAGER=PASS`: still verify real T1 final candidate ID/image, R3 transaction committed, old parked same exact ID and stopped, Broker not restarted, zeros in new RW. Do not initiate board boot or Setup Secret import.
- `T1_FRESH_MANAGER=STOP:...`: use same output's R3 sanitized state; if needed run new *read-only* forensics; do not rerun or delete R3/R2 artifacts.
- `SSH_TIMEOUT_STATE_UNKNOWN_NO_RETRY`: runtime unknown, immediate STOP + status check, never assume rollback.
- Broker/Manager drift: stop and check manually before any additional mutating command.

No R2 or R3 private journal, R5 backup, stopped shadow, original old Manager data, or past logs should be removed as part of this gate. After the one-shot result, synchronize safe summary into GitHub; mark physical product P4 first normal boot as separately unauthorized.
