# N3-W P4 T1 — Logging-option source repair / safe R2 live-resume authority

## User-approved scope and T1 read-only evidence

Original user authorization remains scoped to **one successful or genuinely claimed Manager-only production replacement**, not a second speculative deployment. The R1 attempt stopped during read-only `non_mutating_preflight` at `LOG_OPTIONS_UNSUPPORTED`, before transaction journal creation, old Manager stop, parking, candidate creation, or service-unit install. R1 stopped by a proven source-contract mismatch; it did not consume a live transaction claim. This scoped R2 successor addresses that STOP only.

After R1 the user ran an explicit T1 **read-only** Docker inspect, reporting:

```text
OLD_MANAGER_RUNNING=true
BROKER_RUNNING=true
MANAGER_LOG_DRIVER=json-file
LOG_OPTION_NAMES=max-file,max-size
LOG_MAX_SIZE=10m
LOG_MAX_FILE=3
PARKED_ROLLBACK_CONTAINER_EXISTS=false
FAILED_CANDIDATE_CONTAINER_EXISTS=false
STOPPED_SHADOW_CONTAINER_EXISTS=false
FRESH_MANAGER_REPLACEMENT_NOT_COMPLETED=true
```

No private T1 address, host path, credential, container ID or source path is stored here.

## Source repair and exact follow-up binding

The earlier source incorrectly rejected any non-empty `HostConfig.LogConfig.Config`; additionally, new `docker create` omitted those settings. New source reads the *actual* Docker inspect config, allows validated string log options on the json-file driver, reproduces `--log-driver json-file --log-opt max-file=3 --log-opt max-size=10m` (or the actual matching validated entries) and compares stopped shadow/running candidate logging parity. It does not relax six-mount/3 RW empty/3 RO secrets contracts.

```text
SOURCE_REPAIR_CODE_REF=fd98c06d02037cba4f18043afeac62cd75893108
FRESH_DEPLOY_SCRIPT_BLOB=d07e119f83ed6c76789f6c4de277e33b65b80dad
SYSTEMD_UNIT_SCRIPT_BLOB=4a7a5950aff578382db09846f41cecbc0262a5cb
MAC_LAUNCHER_REBIND_COMMIT=56471330eabb67470bf28f4ad5ddb6721d509c0f
MAC_LAUNCHER_BLOB_SHA1=fcc9409ecee61265dc1e3d8f341caf91ba3ba509
EXPECTED_STAGE=p4-fresh-manager-deploy-r2
LEGACY_STAGE_R1=RETAIN_AS_EVIDENCE_NO_REPLAY
OLD_R5_PRIVATE_BACKUP=KEEP
T1_MUTATION_AFTER_R1_STOP=NOT_OBSERVED
LIVE_MANAGER_REPLACEMENT_NOW=AUTHORIZED_PENDING_R2_TERMINAL_OUTCOME
NO_AUTO_RETRY=true
```

The new Mac launcher pins nine source blobs to the exact repaired source commit and stages to R2, refusing to overwrite R1 or reuse an existing R2. The systemd unit code also binds R2. It automatically checks R5 root-private backup, current exact old Manager/Broker/runtime/image/mount authorities and systemd rollback before any old-Manager stop. Old Compose with historical three mounts remains forbidden as recreate authority.

## Review and status

```text
REPAIR_SYNTHETIC_TESTS=107_PASS_AT_SOURCE_HEAD
REPAIR_CI_RUN=37938973508
R2_LAUNCHER_CI_RUN=37940159499
R2_LAUNCHER_TESTS=108_PASS
R2_FINAL_TEST_CI_RUN=37940408654
R2_PUBLIC_SAFETY_CI_RUN=37940408611
R2_MANAGER_CI_RUN=37940408555
LATEST_FOLLOWUP_PIN_TEST_CI=PASS
PRODUCTION_R2_EXECUTION=NOT_YET_OBSERVED
BOARD_FIRST_NORMAL_BOOT_AUTHORIZED=false
SETUP_SECRET_IMPORT_AUTHORIZED=false
BROKER_MUTATION_AUTHORIZED=false
PR_MERGE=false
```

Proceed only after latest follow-up pin test and public safety CI PASS, as a **single Mac Terminal command** whose source download is checked against the exact Git blob SHA. The user has asked not to repeat granular manual validations. On STOP, do not rerun automatically: classify whether preflight, transaction, or rollback and archive public-safe evidence. Never infer production success from synthetic tests.

## STOP boundary

Current state = R1 preflight STOP + old Manager/Broker confirmed running, patched source CI PASS, R2 entrypoint ready pending final CI verification. No live P4 acceptance claimed until exact real T1 result.
