# N3-W T1 U7 — post-R29 live closure and next-gate execution design

Date: 2026-11-15
Repository: chrenguo-stack/HomeAssistant
PR: #807 (OPEN/DRAFT; no merge authority)
Last exact source activation authority: `43818c475dc9230b2e234a1d6c4379eaa8012c9e`

## 1. Last completed gate — repaired R29 CLOSED_PASS

The user-supplied one-shot T1 executor result:

```text
EXECUTION_ID=U7-R29-REPAIRED-LIVE-SOURCE-ACTIVATION-20261114T160201Z
R29_RC=0
STATUS=U7_R29_SOURCE_ACTIVATION_PASS
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false
SOURCE_ACTIVATED=true
ACTIVATED_SOURCE_FILE_COUNT=7
STAGED_IMPORT_VALIDATION=true
INSTALLED_IMPORT_VALIDATION=true
SERVICE_STOP=false
SERVICE_RESTART=false
TRANSACTION_MUTATION=false
USB_MUTATION=false
U6_PRESERVED=true
U7_TRANSITION=false
U8_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

Transaction SHA256: `7f406b5b88f7bd5c3161d7527a001ddcb3414a8ec64fb34cdad444c2c3e62ebe`.
Observed IPC: `PREDECESSOR_RECOVERY_PREPARING`, installed `2026.10.0`.
Containers broker, manager, and Home Assistant remained running with restart_count 0; owner units remained active with NRestarts 0.
Seven post-activation Git blob identities matched exact source authority; both staged and installed imports passed.

Authoritative evidence:
- Pre-live CI/exact review: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6880190913
- R29 live closure: https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6880337212

The private local evidence root is deliberately not copied to the repository. There is no new R29 live authorization. Never replay R29.

## 2. Next gate — U7 execution preparation, not U7 live yet

```text
NEXT_ONE_GATE=N3W_T1_U7_HA_QUIESCE_DATA_BACKUP_LIVE_EXECUTOR_SOURCE_AND_READONLY_PREFLIGHT
CURRENT_DURABLE_PHASE=U6_PREDECESSOR_RECOVERY_PREPARING
U7_LIVE_AUTHORIZATION_GRANTED=false
T1_MUTATION=false
SERVICE_STOP=false
HA_QUIESCE=false
USB_WRITE=false
TRANSACTION_MUTATION=false
U8_PLUS=false
MERGE=false
```

The next lifecycle action is still the frozen V1.2 U6 -> U7 path. Do not introduce a new product phase.

## 3. Frozen U7 operation

The source authority is `docs/development/N3W_T1_U7_HA_QUIESCE_DATA_BACKUP_SOURCE_DESIGN_AND_REVIEW_20261114.md`.
Product implementation already exists in:

- `tools/n3w_t1_core_updater_ha_install.py`, `HaUsbU7BackupController`;
- `tools/n3w_t1_core_updater_ha_backup.py`, `ProtectedHaDataBackupProvider`;
- `tools/n3w_t1_core_updater_host.py`, `LocalHost.quiesce_homeassistant_for_backup()`;
- `tools/n3w_t1_core_updater_ha_usb.py`, durable U7 phase and backup-identity writes;
- `tests/tools/test_n3w_t1_core_updater_ha_backup_u7.py`, focused source tests.

Intended live sequence after separate authorization:

1. Fresh bind source, authorization, current U6 transaction, exact target and predecessor recovery content, compatible safe removable media, and production container/owner-unit baseline.
2. Pre-quiesce safety proof: mounted-media safety, backup capacity, HA persistent data and recorder location, required key availability without exporting key material; reject any unexpected drift.
3. Stop the *application owner* (Manager and Home Assistant together), not an arbitrary single container. Prove owner inactive, HA/Manager stopped and Broker unchanged/running.
4. Persist U7 with exact predecessor evidence.
5. Generate encrypted/authenticated consistent HA backup to recovery media, validate source consistency, manifest, ciphertext checksum, size, MAC, and decryptability; persist verified backup identity.
6. STOP in U7. Do not enter U8 or perform image removal/cutover.

## 4. Live executor requirements before authorization

Current U7 product controller/test implementation must **not** be mistaken for a completed live executor.

The next bounded executor must have:

- exact-code/manifest binding and source drift guard, including all transitive imports (R29 regression);
- read-only mode with no preclaim mutation, no write or service stop; privilege and target guards;
- explicit, separate single-use U7 mutation grant, claim/consumption evidence, fail-closed no-replay behavior;
- private durable host-side progress ledger and bounded sanitized progress messages;
- timeout-safe status reconciliation: client/SSH loss after start is UNKNOWN until durable T1 transaction, USB mirror, and remote execution ledger agree; no blind retries;
- precise state gating and unchanged Broker proof before and after quiesce;
- stage-specific failure recovery that attempts to restore predecessor application owner and verifies readiness, without falsely reporting PASS;
- safe no-secret evidence output; no private addresses, raw key, encrypted backup contents or sensitive paths in public artifacts;
- exact-source focused tests, error-path simulations, CI, independent final review, then fresh T1 *read-only* preflight;
- only thereafter a separately reviewed and explicitly authorized single live U7 execution.

Do not reuse the consumed R29 grant as the U7 live grant. Never automatically enter U8+.

## 5. Minimum test matrix

- Normal: U6 -> quiesced owner -> protected backup -> verified durable U7 -> STOP.
- Fail before stop: no service/transaction/USB mutation.
- Owner/quiesce proof fails: predecessor owner resume attempted and outcome distinguished.
- Backup capacity, SQLite quick_check, external recorder, external/symlink file, root key or crypto failure: fail closed, no U8.
- Backup archive tamper, HMAC failure, manifest mismatch, USB removal: fail closed.
- Failure after quiesce: restore predecessor owner; if unsuccessful, explicit failure/uncertainty evidence.
- Timeout/interrupted SSH: progress ledger and transaction reconciliation; no false PASS/STOP_UNKNOWN replay.
- Poststate: exact content/transaction and Broker continuity; no U8+, no merge, no board access.
- CI validation must be rerun on the final exact source commit; previous R29 CI is not a substitute.

## 6. Disposition

The repaired R29 physical/source-activation gate is complete. The next authorized work is **repository-only** execution-package design, code, simulation tests, CI and independent review. A T1 read-only preflight may be prepared; it is not evidence of live authorization. Do not initiate the HA/Manager stop or write the transaction/USB unless a new explicit U7 live grant has been established and verified.

The earlier V1.2 architecture convergence review also calls for reducing executor/evidence-framework duplication *after* a stable U7 closure. Do not refactor the architecture as an implicit prerequisite to this gate.
