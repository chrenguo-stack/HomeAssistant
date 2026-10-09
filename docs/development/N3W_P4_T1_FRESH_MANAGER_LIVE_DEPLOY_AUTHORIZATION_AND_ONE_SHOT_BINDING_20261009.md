# N3-W P4 T1 — Manager-only Fresh Deployment Live Authorization / One-shot Binding

Date: 2026-10-09

## Exact authorization

User explicitly authorized **one production replacement of the T1 greenhouse-manager service** in the current conversation. This supersedes the earlier `GRANTED=false` state for this one live Manager replacement only. It does not grant a second run, a Broker reset, a board boot, Setup Secret import, PR merge, old-data deletion or any identity migration.

```text
TASK=N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_LIVE_DEPLOY
LIVE_PRODUCTION_MANAGER_REPLACEMENT_AUTHORIZED=true
AUTHORIZATION_ID=N3W_P4_T1_FRESH_MANAGER_ONE_SHOT_LIVE_DEPLOY
AUTHORIZATION_CONSUMPTION=ON_ACTUAL_TRANSACTION_CLAIM
SECOND_EXECUTION_WITHOUT_NEW_AUTHORIZATION=false
T1_LIVE_EXECUTION_STATUS=AWAITING_MAC_OPERATOR_OUTPUT
BOARD_FIRST_NORMAL_BOOT_AUTHORIZED=false
SETUP_SECRET_IMPORT_AUTHORIZED=false
BROKER_MUTATION_AUTHORIZED=false
OLD_MANAGER_AND_R5_BACKUP_DELETION_AUTHORIZED=false
MERGE=false
```

## Exact immutable source binding

```text
REPOSITORY=chrenguo-stack/HomeAssistant
CANDIDATE_SOURCE=3d86d6bfaf361dc3a3d7295d046f541a544d552d
FINAL_AUDITED_NINE_SOURCE_COMMIT=5bc6c5cf116708ebf47f76b9b2d0c71ab570da6e
MAC_ONE_SHOT_LAUNCHER_COMMIT=0a0e163e8cc13ad8ecf8717a399f29dac0192369
MAC_LAUNCHER_BLOB_SHA1=83ee246eedaa012c1034839ce6aad97315119c49
TEST_CI_RUN=37937707160
SYNTHETIC_TESTS=104_PASS
PUBLIC_SAFETY_CI_RUN=37937707237
GREENHOUSE_MANAGER_CI_RUN=37937707221
CI=PASS_SOURCE_ONLY
```

Launcher: `tools/execution_packages/n3w/p4_manager_cold_backup/fresh_manager_mac_launcher.py`.

The Mac launcher downloads exactly nine Python files from immutable commit `5bc6c5c`, checks each exact Git blob SHA, sends the bound tar stream over SSH, and invokes root-only T1 staging via `sudo -n python3`. The T1 stage discovers exactly one eligible R5 private directory under /root, verifies 0600/0700 permissions and the archive's exact Git blob hashes, refuses pre-existing stage paths, and runs the source-reviewed `fresh_manager_operator.py` preflight and single supervised execute sequentially without intermediate manual gate confirmations. Output is one final `T1_FRESH_MANAGER=PASS` or `STOP:<class>`. Stage errors or missing sudo/SSH fail without stopping Manager.

## Runtime contract and rollback

- Candidate image is the prebuilt T1-local `n3w-p4-manager:3d86d6bfaf361dc3a3d7295d046f541a544d552d`, bound to current immutable image ID at runtime, linux/arm64 only.
- Current old Manager `docker inspect` six bind mounts (3 RW + 3 RO) are the recreate authority, **not** old 3-mount Compose.
- Three newly created empty RW roots must start with zero registration/credential/replay and empty relay keys; no old registration/credential/replay/relay-key data is copied to new Manager.
- Three existing RO secret sources, Broker, TLS, T1 networks and system identity stay unchanged.
- Keep the original stopped/parked container with original three RW data sources and the R5 root-private backup. Never delete, overwrite, or use original RW sources for candidate.
- systemd ExecStopPost plus operator post-completion guard attempt original-container restoration on failure. Rollback failure is `STOP` and requires manual recovery, not a second automatic attempt.
- No real node is powered, so no 90-second zero-traffic false telemetry test. Board first normal boot and Setup Secret import are separate later authorizations.

The final source review additionally repaired the last-operator-check failure window: if systemd finishes successfully but the operator's final runtime proof fails, it marks the transaction uncommitted, invokes strict identity-checked rollback of the parked original, and returns STOP. A missing or mismatched identity must stop safely rather than guessing a container.

## Authoritative safety classification

```text
SOURCE_AND_104_SYNTHETIC_TESTS=CLOSED_PASS
LIVE_PRODUCTION_MANAGER_REPLACEMENT=AUTHORIZED_NOT_YET_OBSERVED
REAL_T1_EXECUTION_PROVEN=false
REAL_T1_NEW_MANAGER_RUNNING=UNKNOWN_PENDING_OUTPUT
ROLLBACK_RUNTIME_RESULT=UNKNOWN_PENDING_OUTPUT
OLD_MANAGER_R5_BACKUP_AND_RESTORE=CLOSED_PASS_HISTORICAL_NO_REPEAT
NO_AUTO_RETRY=true
```

The next response after actual Mac Terminal execution must read the terminal's final result and independently distinguish success, preflight STOP, partial cutover with rollback PASS, or `FAILED_STOP_MANUAL`. Do not archive any real private hostname, host source, image ID, raw credential, key, Setup Secret or identity snapshot in GitHub.
