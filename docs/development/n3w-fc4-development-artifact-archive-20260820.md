# N3-W FC4 development artifact archive — 2026-08-20

This document closes the public-safe archive gap found before the KF-036 live
recovery boundary. The machine-readable companion is
`archive-manifests/n3w-fc4-archive-audit-20260820.json`.

## Authoritative source

```text
REMOTE_MAIN=3bd3f0736eb387dc76d53f472da59056e05a88e3
REMOTE_MAIN_TREE=b0d6fd40c196ba63f6aedec51a591b51bac68676
CLEAN_SUCCESSOR=933a1a00ef05c919d3809b96edb1c2dd459e0aca
PR=327
CI_SUCCESS=26
CI_SKIPPED=1
CI_FAILURE=0
```

PR #327 archives the KF-034, KF-035, and KF-036 source, tests, deployment gate,
operator documentation, and KNOWN_FAILURES entries. Older diagnostic commits,
the f38 detached worktree, and the old Manager settings worktree are not valid
exact-source bindings.

## Live-boundary chronology

The session included FC4 private-state/TLS/DynSec/runtime materialization,
Manager source rebinding, sequential board work, network diagnosis, and the
source implementation for expired-first-registration recovery. Historical
private evidence from the earlier S1A–S1D and P2B3A–P2B3C boundaries was not
given a complete public hash/size manifest at creation time. This is now a
durable legacy limitation: those chat transcripts and filenames alone are not
acceptance authority and must not be reconstructed or promoted by inference.

The latest authoritative runtime closure is P2B3D. Its public-safe binding is
captured in the companion JSON. It proves an ARM64 Manager image built from
main `3bd3f073`, host-network Manager health, Broker TLS continuity, one MQTT
connection, the expected UDP/HTTP listeners, zero critical log matches, and no
board access or KF-036 recovery during that boundary.

Raw claim and closure evidence remain mode `0600` in the private T1 evidence
root. Only their hashes, purpose, and path classes are public. Their sizes were
not captured before the archive rule became active, so the manifest records
`legacy-not-captured` rather than inventing a value.

## Quarantined board readbacks

Six local firmware/readback files were created with legacy A/B/C filenames.
Later in the session, board identity authority changed to MAC-tail identifiers.
No reliable MAC-tail-to-file binding exists for these six files.

They are therefore:

```text
CLASSIFICATION=PRIVATE_REQUIRED
IDENTITY_BINDING=QUARANTINED_UNBOUND
PUBLIC_RAW_EXPOSURE=false
ACCEPTANCE_AUTHORITY=false
```

Their hashes, sizes, and capture times are retained in the companion JSON so
future work can recognize them without opening or publishing raw firmware.
They must never be relabeled from an A/B/C filename by inference. A future
board readback is authoritative only if the same boundary binds the observed
chip MAC tail, serial/USB identity, flash range, file hash, and capture time.

## Reproducibility and temporary helpers

The ARM64 Python base transport is bound by digest, hash, and size. The FC4
firmware build package is privately retained and hash-bound, but is not bound
to a board identity. Two temporary runtime-edit helpers are hash-recorded but
superseded: their reusable network semantics are represented by KF-034/KF-035
and `tools/n3w_pairing_deployment_gate.py`. They are not deployment authority.

## Recovered terminal-only knowledge

- Host `install -o 999 -g 999` attempted NSS name resolution and failed when
  UID 999 had no passwd entry. Host directories must be created root-owned and
  then assigned with numeric `chown 999:999`; a container UID is not a host
  account name. This is KF-037.
- The final-product simplified pairing endpoint returns
  `gh.pair.simple-health/1`, while the legacy endpoint returns
  `gh.pair.health/1`. A preclaim must select the schema from the deployed
  endpoint composition, not from a generic pairing assumption. This is KF-038
  and now has a direct endpoint regression test.
- Valuable results were left across temporary files, private evidence, and
  conversation state after meaningful boundaries. Repository-level archive
  rules, an AGENTS entry point, and this sanitized manifest now guard that
  failure mode as KF-039.

## Physical authorization boundary

The first archive-recovery commit did not access T1 or boards and did not claim
the then-pending KF-036 live authorization. The later live boundary did claim
and consume that authorization; its terminal state is recorded below.

## KF-036 consumed failure and unchanged-state adoption

The corrected read-only preclaim uniquely bound the F4:5C current registration
as expired, epoch 1, never approved, without NODE_ID, location, repair flag,
node history, lease, or credential assignment. It also found an FC4-specific
path contract:

```text
REGISTRATION_CONTAINER_PATH=/var/lib/greenhouse-manager/manager/registration.sqlite3
CREDENTIAL_CONTAINER_PATH=/var/lib/greenhouse-manager/n3w/credential-lifecycle.sqlite3
GENERIC_REGISTRATION_DEFAULT_APPLIES=false
```

After claim, the executor stopped Manager and created two mode-0600 private
database backups. The isolated Manager-image command used `python -` to read
its program from stdin, but the `docker run` invocation omitted `-i` /
`--interactive`. Docker therefore closed stdin; Python read EOF, performed no
recovery, emitted no JSON, and exited zero. The nonempty-result/JSON oracle then
failed. This is KF-040.

The automatic failure trap restarted Manager. Read-only post-failure audit
proved:

```text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
TERMINAL=CONSUMED_FAILED
AUTHORIZATION_REPLAY_PERMITTED=false

REGISTRATION_DATABASE_MUTATED=false
CREDENTIAL_DATABASE_MUTATED=false
CURRENT_EXPIRED_REGISTRATION_PRESENT=true
CREDENTIAL_ASSIGNMENT_COUNT=0
MANAGER_HEALTH=PASS
MANAGER_RESTART_COUNT=0
BOARD_ACCESS=false
DEVICE_RESET=false
```

The exact before/after hashes and four private evidence bindings are in the
companion manifest. A successor must explicitly adopt those unchanged hashes,
use a fresh private evidence namespace and a new authorization, pass the exact
FC4 container paths, keep stdin attached with `--interactive`, and reject an
empty result before JSON parsing. The consumed authorization must never be
rerun.

## KF-036 successor recovery success and false terminal oracle

The successor authorization adopted the unchanged databases and prior private
evidence, used the exact FC4 paths and kept container stdin attached with
`--interactive`. The native recovery CLI returned a nonempty successful JSON
result. It released the current registration pointer and appended the explicit
`expired_first_registration_abandoned` event with reason
`expired_first_pairing_recovery`.

The executor then stopped at an incorrect postcondition: it expected the old
pairing session reason itself to change to the recovery reason. That expectation
contradicts the replay-tombstone contract. The immutable session correctly
remained `state=expired, reason=expired`; the separate event records why the
current pointer was abandoned. This executor-oracle defect is KF-041, not a
product recovery failure.

Corrected read-only terminal audit proved:

```text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
TERMINAL=CONSUMED_PARTIAL_SUCCESS_STOPPED_AT_FALSE_TOMBSTONE_REASON_ORACLE
AUTHORIZATION_REPLAY_PERMITTED=false

PRODUCT_RECOVERY_SUCCEEDED=true
CURRENT_REGISTRATION_COUNT=0
REPLAY_TOMBSTONE_STATE=expired
REPLAY_TOMBSTONE_REASON=expired
RECOVERY_EVENT=expired_first_registration_abandoned
RECOVERY_EVENT_REASON=expired_first_pairing_recovery
NODE_HISTORY_COUNT=0
NODE_LEASE_COUNT=0
CREDENTIAL_ASSIGNMENT_COUNT=0
MANAGER_HEALTH=PASS
MANAGER_RESTART_COUNT=0
CRITICAL_LOG_COUNT=0
BOARD_ACCESS=false
```

No closure evidence was created after the false oracle. A later authorization
must adopt this already-mutated valid database state, must not invoke the
recovery CLI again, and may only close the missing evidence before any newly
authorized physical continuation.

## KF-041 closure successor

The separately authorized closure successor re-bound the exact valid recovery
state, exact Manager image, service listeners, database hashes and fresh
private evidence paths before claim. It then created only a mode-0600 claim and
closure record. It did not run the recovery CLI and did not mutate either
database, any container or a board.

```text
TERMINAL=CLOSED_VALID_RECOVERY_STATE
RECOVERY_REPLAY=false
REGISTRATION_DATABASE_MUTATED_IN_THIS_BOUNDARY=false
CREDENTIAL_DATABASE_MUTATED_IN_THIS_BOUNDARY=false
CONTAINER_MUTATION=false
BOARD_ACCESS=false
```

The private claim and closure are bound by sanitized SHA-256 and size metadata
in the companion manifest. This closes the missing recovery evidence boundary;
it does not authorize a device reset or any subsequent physical test.

## F4:5C pre-physical archive recovery

The next physical preclaim found two valuable legacy files that the first
archive sweep had missed: a raw F4:5C factory readback and the one-time helper
used to capture a Setup Secret handoff from serial output. The handoff JSON
itself was already absent, so no secret value was recovered or exposed.

Before claiming the pending physical authorization, both surviving files were
copied with mode 0600 into the established private evidence root. Their
sanitized hashes, sizes and purposes are recorded in the companion manifest;
neither raw file is committed. This archive-recovery action did not open the
serial port, access the board, reset pairing state or modify Flash.

## F4:5C post-KF-036 scoped NVS reset

The authorized physical successor bound the sole USB device to base MAC
`sha256:de6b31f7d4d166afb8edcce53fe77e8cf3e723676ebac2360a405884dc846108`, ESP32-C6 revision 0.2, 8 MiB Flash and the frozen
application image. After claim it captured a mode-0600 private backup of the
exact NVS partition and successfully erased only `0x790000/0x70000`; it did not
rewrite the application or erase the full Flash.

The executor then hard-reset the board and attempted to prove the erased
partition was still entirely `0xFF`. That oracle was invalid: the application
booted before the following readback connection and immediately initialized
NVS. The readback therefore contained new state. A secret-free serial
classifier proved the board had generated a new pairing ID different from the
expired identity and was still emitting a 32-byte Setup Secret representation.
No handoff file was created. This is KF-042.

```text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
TERMINAL=CONSUMED_PARTIAL_SUCCESS_STOPPED_AT_POST_ERASE_ALL_FF_ORACLE
NVS_SCOPED_ERASE=true
APPLICATION_FLASH_REWRITE=false
FULL_FLASH_ERASE=false
NEW_PAIRING_ID_DIFFERENT=true
PRIVATE_HANDOFF_FILE_PRESENT=false
T1_CURRENT_REGISTRATION_COUNT=0
T1_CREDENTIAL_ASSIGNMENT_COUNT=0
```

The consumed authorization must not erase NVS again. A successor must adopt
the current new pairing identity, capture its handoff into the private evidence
root, wait for the operator to restore Wi-Fi, observe the new pending
registration, then deliver the mode-0600 handoff to the exact Manager inbox.

## KF-042 successor handoff capture

The successor authorization adopted the new pairing ID hash and the prior
scoped NVS erase without repeating any Flash operation. After a final
secret-free serial rebind it created a private claim and captured the new Setup
Secret handoff directly into the approved private evidence root with mode 0600.
Only the file hash and size are public.

```text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
TERMINAL=CONSUMED_PARTIAL_SUCCESS_WAITING_FOR_OPERATOR_WIFI_CONFIGURATION
PRIVATE_HANDOFF_CAPTURE=PASS
SECRET_VALUE_EXPOSED=false
REPEAT_NVS_ERASE=false
FLASH_MUTATION=false
T1_MUTATION=false
```

The board now waits for the operator to restore Wi-Fi. The handoff must not be
placed in the Manager inbox until the new registration is observed as pending,
because the inbox deliberately rejects and removes secrets whose registration
does not yet exist in pending state.

## F4:5C final-product E2E closure

After the operator restored Wi-Fi, T1 observed the new pairing identity as a
fresh epoch-1 pending registration. The exact private handoff was then copied
under a non-matching temporary name, hash-checked, changed to mode 0600 and
numeric UID/GID 999:999, and atomically renamed into the Manager inbox. Manager
consumed the file and completed automatic approval and credential issuance.

The board stopped emitting the Setup Secret payload and produced six observed
`accepted=true` telemetry cycles. T1 accepted 37 telemetry messages with zero
rejections, published both Home Assistant discovery records, and Home Assistant
materialized one device and five entities. Manager, Broker and Home Assistant
remained running with zero restarts and no critical errors.

```text
TERMINAL=PASS_F45C_FINAL_PRODUCT_E2E
PAIRING_SESSION_STATE=approved
PAIRING_EPOCH=1
CREDENTIAL_ASSIGNMENT_COUNT=1
SERIAL_PAIRING_QR_PAYLOAD_COUNT=0
MANAGER_ACCEPTED_TELEMETRY_COUNT=37
MANAGER_REJECTED_TELEMETRY_COUNT=0
HA_DEVICE_REGISTRY_MATCH_COUNT=1
HA_ENTITY_REGISTRY_MATCH_COUNT=5
```

The mode-0600 private closure is hash-bound in the companion manifest. This
live result closes KF-036 as guarded. It validates F4:5C only and does not grant
or imply authorization for another board.

## F3:50 sequential preclaim and portable handoff capture guard

The next sequential-board read-only preclaim found exactly one USB device and
bound it to ESP32-C6 base MAC `sha256:c25b9bc46cf2c4247c607e6cc9ff7536fb22bac5c4e38fe610ca1f176b2f7ca6`, hardware ID
`ghw-c6-98a316a9f350`, chip revision 0.2 and 8 MiB Flash. Secure Boot and Flash
Encryption were disabled. A verify-only application comparison passed against
the frozen application SHA-256
`95e177042fd15cb0e4b4aef762adf37811c736d34579e480f534ffbe5ee14a7a`.
Serial observation showed an unprovisioned board emitting a private pairing
payload; only the pairing-ID SHA-256 and encoded Setup Secret length were
retained publicly. No handoff file was created and the pending physical
authorization remained unclaimed.

That preclaim also found that the surviving one-time F4:5C capture helper
hard-coded its USB device and temporary output paths. Reusing it for F3:50
would violate the exact-device boundary. KF-043 replaces that helper with the
supported `greenhouse-manager-n3w-setup-secret-capture` entry point. The command
requires explicit serial, hardware-ID, pairing-ID-hash and absolute output
bindings; validates a private parent directory before opening serial; creates
the output exactly once with mode 0600; and emits only hashes, lengths and a
`SECRET_VALUE_EXPOSED=false` marker. CLI call-chain regressions cover success,
identity mismatch, unsafe parent permissions and overwrite refusal.

```text
AUTHORIZATION_APPROVED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
BOARD_BASE_MAC_SHA256=c25b9bc46cf2c4247c607e6cc9ff7536fb22bac5c4e38fe610ca1f176b2f7ca6
PAIRING_ID_SHA256=7ea23bfae78dcd4d2ae20f66d4b73bd2785a6ceb7afaea5d6b112e1f72052049
SETUP_SECRET_ENCODED_LENGTH=43
PRIVATE_HANDOFF_FILE_PRESENT=false
FLASH_MUTATION=false
```

The next physical entry may resume only after this source/test/documentation
boundary is pushed and exact-bound. It must re-check that the authorization is
still unclaimed and must use the new command rather than the retired temporary
helper.

## F3:50 bound handoff capture

After the KF-043 source boundary was pushed and exact-bound, the final
preclaim repeated the clean worktree, exact USB serial and fresh private
namespace checks. The approved authorization was then claimed and consumed by
creating its mode-0600 private claim. The new supported capture entry point
observed the same expected hardware ID and pairing-ID hash and created exactly
one mode-0600 private handoff.

```text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
PRIVATE_PAIRING_PAYLOAD=CAPTURED
PAIRING_ID_SHA256=7ea23bfae78dcd4d2ae20f66d4b73bd2785a6ceb7afaea5d6b112e1f72052049
SETUP_SECRET_ENCODED_LENGTH=43
SECRET_VALUE_EXPOSED=false
FLASH_MUTATION=false
NVS_ERASE=false
T1_MUTATION=false
TERMINAL=CONSUMED_PARTIAL_SUCCESS_WAITING_FOR_OPERATOR_WIFI_CONFIGURATION
```

The private claim, secret-safe capture result and Setup Secret handoff are
represented only by sanitized hash/size/mode bindings in the companion
manifest. The consumed authorization must not capture another handoff or reset
the board. Continuation waits for operator Wi-Fi configuration, then must
observe this exact pairing identity as pending before delivering the existing
handoff to Manager.

## F3:50 expired before atomic handoff delivery

After Wi-Fi configuration, T1 observed exactly one matching F3:50 session as
`pending`, epoch 1. The local handoff was rebound by mode and SHA-256, then
copied to an inbox filename that Manager does not scan. Before atomic rename,
the remote fail-closed validator repeated the handoff hardware/pairing binding
and live session-state check. That final state check failed because the session
had just transitioned to `expired`; the staging file was removed and the final
inbox filename was never created.

Read-only classification proved the pending lifetime was exactly 120 seconds:

```text
FIRST_SEEN_AT=2026-08-21T01:38:22.870Z
LAST_SEEN_AT=2026-08-21T01:40:17.915Z
EXPIRES_AT=2026-08-21T01:40:22.870Z
PAIRING_SESSION_STATE=expired
PAIRING_SESSION_REASON=expired
HANDOFF_ATOMIC_DELIVERY=false
T1_STAGING_REMOVED=true
T1_FINAL_INBOX_FILE_PRESENT=false
LOCAL_PRIVATE_HANDOFF_PRESERVED=true
SECRET_VALUE_EXPOSED=false
```

This is KF-044. A boolean pending check is insufficient near the end of a
fixed, non-renewing TTL; delivery must require an explicit remaining-time
margin before transfer and must still re-check immediately before atomic
rename. The current authorization is consumed and cannot be replayed. A new
authorization must explicitly adopt the expired tombstone, the preserved
private handoff hash and this stopped state before any recovery or board reset.

## KF-044 source-only TTL margin gate

The separately approved source-only boundary added the supported
`greenhouse-manager-n3w-setup-secret-delivery-gate` entry point. It performs no
delivery and has two read-only phases:

- `pretransfer` binds the read-only registration database, current registration,
  exact hardware ID, pairing-ID SHA-256, `pending` state and an explicit minimum
  number of remaining seconds;
- `predelivery` repeats those checks and additionally validates that the staged
  handoff is a regular mode-0600 file with the expected UID/GID, exact schema,
  hardware identity, pairing identity and 32-byte encoded Setup Secret.

Both phases emit only hashes, expiry/remaining-time facts and explicit
`PAIRING_ID_RAW_EXPOSED=false` / `SETUP_SECRET_EXPOSED=false` markers. The
integration regression proves the database content hash remains unchanged and
covers adequate margin, inadequate margin, non-current pairing identity,
valid private handoff and unsafe handoff permissions. Related registration and
private-inbox regressions also pass.

```text
SOURCE_AUTHORIZATION_CLAIMED=true
SOURCE_AUTHORIZATION_CONSUMED=true
SOURCE_MUTATION_ONLY=true
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
SERIAL_ACCESS=false
FLASH_MUTATION=false
PRIVATE_HANDOFF_DELIVERY=false
TARGETED_AND_RELATED_TESTS=36 passed
FULL_MANAGER_TESTS=1115 passed, 1 skipped, 5 subtests passed
```

The first full-suite run in the restricted workspace reported four
`PermissionError: Operation not permitted` failures at local TCP/UDP loopback
socket bind points. An otherwise identical run with local loopback binding
permitted passed the complete suite. These were sandbox false failures, not
source regressions; no source change was made in response.

KF-044 remains OPEN until a separately authorized live successor proves the
gate on a fresh pending identity and completes E2E. The expired F3:50 physical
authorization remains non-replayable.

## KF-044 live successor stopped at isolated DB path binding

The live successor passed exact source, USB, chip, Flash, application,
tombstone, database, inbox and service-health preclaims. After claim it stopped
the exact Manager container, machine-proved `exited/PID 0`, captured the private
inspect document and mode-0600 backups of both databases, then launched the
recovery program through attached stdin in the exact Manager image.

Recovery stopped before opening the mutation transaction with
`registration database binding mismatch`. The executor passed the Manager
container destination as `--db`; the safety gate compares that resolved path
with the host Source path derived from the captured inspect mount. Both paths
were visible inside the isolated container, but they are different path
domains. This is KF-045.

Post-failure classification proved:

```text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_PERMITTED=false
TERMINAL=CONSUMED_FAILED_AT_ISOLATED_RECOVERY_REGISTRATION_DB_BINDING
REGISTRATION_DATABASE_MUTATED=false
CREDENTIAL_DATABASE_MUTATED=false
CURRENT_REGISTRATION_COUNT=1
PAIRING_SESSION_STATE=expired
RECOVERY_EVENT_COUNT=0
RECOVERY_RESULT_SIZE=0
MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0
POSTCLAIM_BOARD_ACCESS=false
NVS_ERASE=false
FLASH_MUTATION=false
```

A successor must adopt the unchanged DB hashes and all private evidence, use a
fresh authorization/namespace, mount the state root RW at its original host
absolute path, pass those host paths to `--db/--credential-db`, and reserve the
Manager destination paths exclusively for the two `*-container-path` binding
arguments. It must reject an empty result before JSON parsing. No board or NVS
operation may begin until recovery and Manager health both close successfully.

## KF-045 source-only host-source recovery executor

The approved source-only boundary added the supported
`greenhouse-manager-n3w-expired-first-recovery` entry point. The executor
requires separate arguments for the host-source registration/credential files
and Manager container destinations. It also requires a mode-0600 stopped
Manager inspect document, exact pre-mutation hashes, hardware ID, pairing-ID
SHA-256 and explicit stopped confirmation.

The executor locates the raw pairing ID only in memory by its expected hash,
injects the real inspect document into the existing recovery CLI, captures its
raw result privately in memory, rejects a nonzero or empty result before JSON
parsing, verifies the immutable expired tombstone and separate recovery event,
and emits only a sanitized result. It never prints the raw pairing ID.

The integration regression uses the real registration and credential stores
plus a Docker-inspect-shaped mount document. It proves the exact host-source
path succeeds, while an otherwise identical destination-domain database copy
fails before mutation with its content hash unchanged. An injected empty nested
result is also rejected before parsing.

```text
SOURCE_AUTHORIZATION_CLAIMED=true
SOURCE_AUTHORIZATION_CONSUMED=true
TARGETED_REGISTRATION_CREDENTIAL_TESTS=51 passed
FULL_MANAGER_TESTS=1119 passed, 1 skipped, 5 subtests passed
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
SERIAL_ACCESS=false
RECOVERY_EXECUTED_LIVE=false
```

KF-045 remains OPEN pending a new live successor. The prior unchanged database
hashes and private failure evidence remain the required adoption authority.

## KF-045 live recovery closure

The next live successor adopted the unchanged databases and all KF-045 private
evidence, materialized an exact source archive at `a9b754b2`, and proved the new
executor imports inside the exact ARM64 Manager image before stopping service.
It then captured a fresh stopped inspect and backups and ran the executor with
the state root mounted RW at its original host absolute path.

The executor returned exit 0 with a nonempty sanitized result. It released the
current registration, preserved the original `expired/expired` replay tombstone,
appended the separate `expired_first_registration_abandoned` event with reason
`expired_first_pairing_recovery`, and left the credential database unchanged.
Manager returned healthy with zero restarts.

The initial shell output did not include its planned terminal footer, so no
board work followed. A separate read-only replay of every result, DB, Manager
and health oracle passed. Recovery was not repeated.

```text
TERMINAL=CONSUMED_PARTIAL_SUCCESS_RECOVERY_CLOSED_BOARD_NOT_STARTED
RECOVERY_EXECUTOR_RESULT=PASS
HOST_SOURCE_DATABASE_PATHS_VERIFIED=true
RAW_RECOVERY_RESULT_NONEMPTY=true
CURRENT_REGISTRATION_COUNT=0
REPLAY_TOMBSTONE_STATE=expired
REPLAY_TOMBSTONE_REASON=expired
RECOVERY_EVENT=expired_first_registration_abandoned
RECOVERY_EVENT_REASON=expired_first_pairing_recovery
CREDENTIAL_DATABASE_MUTATED=false
MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0
READONLY_OUTER_ORACLE=PASS
BOARD_ACCESS_AFTER_RECOVERY=false
NVS_ERASE=false
FLASH_MUTATION=false
```

This live result closes KF-045 as GUARDED. The consumed authorization may
continue only from its already-approved post-recovery board boundary; it must
not invoke recovery again. KF-044 remains open until a fresh pairing identity
passes both TTL delivery gates and completes E2E.

## F3:50 scoped NVS reset and Wi-Fi handoff gate

The same consumed successor continued only from its approved post-recovery
board boundary. USB serial `sha256:c25b9bc46cf2c4247c607e6cc9ff7536fb22bac5c4e38fe610ca1f176b2f7ca6`, base MAC
`sha256:c25b9bc46cf2c4247c607e6cc9ff7536fb22bac5c4e38fe610ca1f176b2f7ca6`, application image and partition-table hashes were rebound
before mutation. Flash verification proved the installed application still
matches the bound FC4 image.

The executor captured a private mode-0600 backup, erased only the calculated
NVS range `0x790000+0x70000`, held the chip in the bootloader, and read the
entire range back before application startup. All 458,752 read-back bytes were
`0xFF`; only then was the application hard-reset. No bootloader, partition
table, OTA metadata or application region was written.

The first 25-second pairing observation correctly produced no payload. NVS
reset also removed the operator Wi-Fi configuration, so the board has not yet
reached the network-dependent fresh-pairing phase. No observation file, setup
secret handoff or capture result was created. The boundary stops at the
operator Wi-Fi configuration gate; the old expired handoff remains forbidden.

```text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
RECOVERY_REPLAYED=false
USB_IDENTITY_SHA256=c25b9bc46cf2c4247c607e6cc9ff7536fb22bac5c4e38fe610ca1f176b2f7ca6
BASE_MAC_SHA256=c25b9bc46cf2c4247c607e6cc9ff7536fb22bac5c4e38fe610ca1f176b2f7ca6
APPLICATION_FLASH_VERIFY=PASS
SCOPED_NVS_RANGE=0x790000+0x70000
NVS_BACKUP_SIZE=458752
NVS_BACKUP_NON_FF_BYTES=3320
NVS_ERASED_PREBOOT_READBACK_SIZE=458752
NVS_ERASED_PREBOOT_NON_FF_BYTES=0
SCOPED_NVS_ERASE_PREBOOT_ORACLE=PASS
APPLICATION_FLASH_REWRITE=false
FULL_FLASH_ERASE=false
NEW_PAIRING_PAYLOAD_OBSERVED=false
NEW_PRIVATE_HANDOFF_CREATED=false
NEXT_GATE=OPERATOR_WIFI_CONFIGURATION_THEN_SECRET_SAFE_CAPTURE
```

This closes the scoped NVS-reset sub-boundary. KF-044 remains OPEN until a new
identity is captured, passes the formal pre-transfer and pre-delivery TTL
gates, and completes the final-product E2E.

## F3:50 fresh handoff capture and setup-AP identity diagnosis

A normal board reset proved the application healthy and produced a fresh local
pairing identity for `ghw-c6-98a316a9f350`. The formal capture entry point then
rebound the hardware and pairing hashes and exclusively created a mode-0600
private handoff. The new pairing hash differs from the expired tombstone; no
old handoff was adopted or delivered.

The generated exact firmware source explains why the operator did not find a
Wi-Fi network named after F3:50: this image configures the generic fallback SSID
`Greenhouse N3-W Setup` and an AP timeout of 90 seconds. The board identifier is
not part of that SSID. This discovery and the diagnostic redaction gap are
recorded as KF-046.

During diagnosis, a filter that redacted `GHN3W2` payload lines still admitted
one ordinary status line containing the raw pairing ID into the controlled tool
transcript. It was not written to an evidence file, repository or GitHub, and
the setup secret was not exposed. Subsequent filters must reject the complete
line on either payload or `pairing_id=` markers and emit only hashes/lengths.

```text
PAIRING_PAYLOAD_OBSERVED=true
HARDWARE_ID_SHA256=f1f1e36fe4784a26b936d6a2bc5d239ab531f5683aca91356a5e39f3f566b1eb
PAIRING_ID_SHA256=480a6813f0342528a5c8ae91f7086e84e8ad1a73105ce0363bd10406da0cf526
PAIRING_ID_DIFFERS_FROM_EXPIRED=true
SETUP_SECRET_LENGTH=43
PRIVATE_HANDOFF_SHA256=68caeb775c45e8652e706a8b814d9de54a60e5779a440708f089742f02d688f3
PRIVATE_HANDOFF_MODE=0600
SECRET_VALUE_EXPOSED=false
SETUP_AP_SSID=Greenhouse N3-W Setup
SETUP_AP_TIMEOUT_SECONDS=90
KF046_STATUS=OPEN
NEXT_GATE=ARCHIVE_REMOTE_EXACT_THEN_RESET_AND_CONNECT_EXACT_SETUP_SSID
```

KF-044 remains OPEN. No private transfer may start until a fresh exact pending
session exists and the formal pre-transfer TTL gate passes with sufficient
margin.

### KF-046 live correction: saved STA continuity

A second strict Wi-Fi-only serial observation corrected the setup-AP
assumption. F3:50 loaded Wi-Fi state outside the scoped product pairing-NVS
reset and connected successfully to the saved `OrayBox-6806` STA. ESPHome
therefore correctly did not broadcast its fallback AP. The operator does not
need to configure Wi-Fi again.

```text
SCOPED_PAIRING_NVS_ERASE=PASS
SAVED_WIFI_CREDENTIAL_CONTINUITY=true
WIFI_STA_SSID=OrayBox-6806
WIFI_STA_CONNECTED=true
FALLBACK_AP_EXPECTED=false
WIFI_CONFIGURATION_REQUIRED=false
SECRET_VALUE_EXPOSED=false
NEXT_GATE=FORMAL_PRETRANSFER_TTL_GATE
```

The corrected guard is: prove STA state first; only instruct fallback AP setup
when the board is actually disconnected and the exact fallback start marker is
observed. This result supersedes the earlier operator-Wi-Fi gate assumption but
does not invalidate the fresh handoff.

## F3:50 second KF-044 TTL stop

The formal pre-transfer gate was invoked from the exact archived T1 source only
after the saved-STA diagnosis and its mandatory GitHub archive completed. It
correctly rejected the exact current session because the fixed 120-second
pending window had expired. No handoff bytes crossed from the Mac to T1.

The first attempt used a nonexistent extracted-source path and therefore
produced no gate output; it was not accepted as success. A read-only path audit
located the exact module under the successor `source` tree, proved its hash,
size, import origin and `main` entry, and only then ran the formal gate.

```text
DELIVERY_GATE=FAIL:EXACT_CURRENT_PAIRING_SESSION_NOT_PENDING
EXACT_CURRENT_MATCH_COUNT=1
PAIRING_ID_SHA256=480a6813f0342528a5c8ae91f7086e84e8ad1a73105ce0363bd10406da0cf526
CURRENT_PAIRING_EPOCH=1
CURRENT_STATE=expired
CURRENT_REASON=expired
CURRENT_FIRST_SEEN_AT=2026-08-21T02:44:35.797Z
CURRENT_LAST_SEEN_AT=2026-08-21T02:46:34.254Z
CURRENT_EXPIRES_AT=2026-08-21T02:46:35.797Z
REGISTRATION_DB_SHA256=3b54e11081a5db0ccd638120b687136a639b4d8ab6adb8f157065e886616591c
PRIVATE_HANDOFF_TRANSFERRED=false
RECOVERY_REPLAYED=false
PAIRING_ID_RAW_EXPOSED=false
SETUP_SECRET_EXPOSED=false
TERMINAL=CONSUMED_STOPPED_AT_SECOND_EXPIRED_PRETRANSFER_GATE
```

The next successor must first adopt this expired tombstone and private handoff,
close all preparatory archive work, and pre-arm a single executor that performs
pending observation, both formal TTL gates, private transfer and atomic delivery
within the active window. The existing recovery and NVS operations must not be
replayed under the consumed authorization.

## KF-047 successor stopped before database mutation

The next approved successor passed source/archive, USB, Flash, Manager image,
second expired tombstone and fresh-namespace preclaims, then claimed and
consumed its authorization. It stopped Manager, captured a mode-0600 inspect
document and both database backups, and attempted the formal recovery module in
the exact product image.

The product image has `ENTRYPOINT=greenhouse-manager`. Because the invocation
did not override it, the appended `python -m ...` tokens were passed to the
product CLI, which rejected them as unrecognized arguments with exit 2. The
recovery module never started. The empty result was rejected before parsing;
Manager was restarted by the failure path.

Read-only classification proves both live databases exactly equal their
pre-mutation backups, the second `expired/expired` current tombstone remains,
Manager is running with zero restarts, and no board or handoff operation began.

```text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_PERMITTED=false
RECOVERY_EXECUTOR_RC=2
RECOVERY_RESULT_SIZE=0
FAIL_STAGE=EXACT_IMAGE_ONE_SHOT_ENTRYPOINT_BINDING
REGISTRATION_SHA256_BEFORE=3b54e11081a5db0ccd638120b687136a639b4d8ab6adb8f157065e886616591c
REGISTRATION_SHA256_AFTER=3b54e11081a5db0ccd638120b687136a639b4d8ab6adb8f157065e886616591c
CREDENTIAL_SHA256_BEFORE=25840bf73043640867a75eedc06e782231569b9c22f4c3b80efe591eff3ed50e
CREDENTIAL_SHA256_AFTER=25840bf73043640867a75eedc06e782231569b9c22f4c3b80efe591eff3ed50e
DATABASE_MUTATION=false
SECOND_EXPIRED_TOMBSTONE_PRESERVED=true
MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0
BOARD_ACCESS=false
NVS_ERASE=false
PRIVATE_HANDOFF_TRANSFER=false
TERMINAL=CONSUMED_FAILED_BEFORE_DATABASE_MUTATION
```

KF-047 requires a source/regression boundary before another live successor:
explicitly bind the one-shot entrypoint and prove the constructed exact-image
command before service stop. KF-044 remains OPEN and no active TTL window was
started in this failed authorization.

## KF-047 exact-image one-shot source guard

The approved source-only boundary added
`greenhouse-manager-n3w-exact-image-one-shot`. Its preflight reads real Docker
image-inspect JSON, requires the exact immutable image ID and the bound product
entrypoint `greenhouse-manager`, then launches the recovery module `--help` in a
network-none, read-only, capability-dropped container with an explicit
`--entrypoint python`.

The formal run command is built only from a successful binding. It uses the
immutable image ID instead of a tag, keeps source read-only, mounts the state
root at the same absolute host/container path, retains network/capability
isolation, explicitly overrides the entrypoint, and forwards recovery arguments
as an argv tuple without a shell. Nonzero or empty module output fails closed.

Regression coverage proves the exact entrypoint position, immutable image ID,
same-path state mount, wrong/missing product entrypoint rejection, image-ID
drift rejection, preflight failure before recovery construction, and empty
success-output rejection. The first full-suite invocation used a relative
`PYTHONPATH`; three existing CLI subprocess tests changed cwd and reproduced
KF-027. Re-running with the absolute source path passed without source changes.

```text
SOURCE_AUTHORIZATION=D1-N3W-FC4-F350-KF047-EXACT-IMAGE-ONE-SHOT-ENTRYPOINT-GATE-IMPLEMENTATION-TEST-AND-GITHUB-PUSH-20260821-01
SOURCE_AUTHORIZATION_CLAIMED=true
SOURCE_AUTHORIZATION_CONSUMED=true
SOURCE_PARENT_HEAD=115b402454063dcc884221058c9a1d54b2d45c2b
FORMAL_ENTRYPOINT=greenhouse-manager-n3w-exact-image-one-shot
EXACT_IMAGE_ID_REQUIRED=true
PRODUCT_ENTRYPOINT_REQUIRED=greenhouse-manager
EXPLICIT_ONE_SHOT_ENTRYPOINT=python
PREFLIGHT_NETWORK_NONE=true
PREFLIGHT_READ_ONLY=true
RECOVERY_SHELL_EXECUTION=false
TARGETED_TESTS=12 passed
FULL_MANAGER_TESTS=1127 passed, 1 skipped, 5 subtests passed
RUFF=PASS
T1_ACCESS=false
BOARD_ACCESS=false
USB_ACCESS=false
DATABASE_MUTATION=false
RECOVERY_EXECUTED_LIVE=false
```

KF-047 remains OPEN only for live acceptance. A new successor must adopt the
unchanged database hashes and all KF-047 private evidence, run the formal
preflight before stopping Manager, and use the formal runner for recovery. The
consumed failed authorization remains non-replayable.

## KF-048 live successor stopped at runtime-UID mount authority

The KF-047 live successor passed all read-only bindings, claimed its fresh
authorization, materialized source `1a01c650` with identical local/T1 archive
hashes, and ran the formal exact-image preflight while Manager remained
running. The preflight proved the immutable image ID, product entrypoint,
explicit Python entrypoint and recovery module help.

After Manager stopped and fresh mode-0600 inspect/database backups were
captured, the formal runner returned its generic isolated-execution failure.
The failure path restarted Manager. Read-only classification proved both live
database hashes still exactly equal their backups, the second expired current
tombstone remains, and no board, NVS or handoff operation began.

An isolated read-only probe using the exact image then established the root
cause. Its effective identity is `999:999`; the runner mounted the whole FC4
private root, which is `0700 root:root`, so that identity cannot traverse to
either database. The stopped inspect is independently `0600 root:root` and
also unreadable. In contrast, the exact registration and credential parent
directories are both `0700 999:999` and are the correct minimal RW mount roots.

The outer runner also reduced the inner failure to a generic message and
printed `RECOVERY_STARTED=false`, even though Python had launched the recovery
module. That diagnostic contract must be corrected together with the mount
contract.

```text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_PERMITTED=false
EXACT_IMAGE_ONE_SHOT_PREFLIGHT=PASS
EXACT_IMAGE_RUNTIME_UID=999
EXACT_IMAGE_RUNTIME_GID=999
FC4_PRIVATE_ROOT_MODE=0700
FC4_PRIVATE_ROOT_OWNER=0:0
REGISTRATION_PARENT_MODE_OWNER=0700:999:999
CREDENTIAL_PARENT_MODE_OWNER=0700:999:999
INSPECT_MODE_OWNER=0600:0:0
REGISTRATION_SHA256_BEFORE=3b54e11081a5db0ccd638120b687136a639b4d8ab6adb8f157065e886616591c
REGISTRATION_SHA256_AFTER=3b54e11081a5db0ccd638120b687136a639b4d8ab6adb8f157065e886616591c
CREDENTIAL_SHA256_BEFORE=25840bf73043640867a75eedc06e782231569b9c22f4c3b80efe591eff3ed50e
CREDENTIAL_SHA256_AFTER=25840bf73043640867a75eedc06e782231569b9c22f4c3b80efe591eff3ed50e
DATABASE_MUTATION=false
SECOND_EXPIRED_TOMBSTONE_PRESERVED=true
MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0
BOARD_ACCESS=false
NVS_ERASE=false
PRIVATE_HANDOFF_TRANSFER=false
TERMINAL=CONSUMED_FAILED_BEFORE_DATABASE_MUTATION
```

KF-047 entrypoint enforcement remains valid. KF-048 is the new blocker: use
least-privilege same-path directory mounts and runtime-UID ownership, add a
pre-stop accessibility probe, and preserve sanitized inner errors. The
consumed authorization must not be replayed.

## Public repository safety follow-up

The current exact-head manual audit detected 14 MAC-shaped raw board identifiers
across the public FC4 archive manifest, this development archive, and its
manifest regression. Public archive identity bindings are now represented as
SHA-256 of the normalized lowercase identifier instead of the raw MAC/USB
serial value. Raw board readbacks and other private evidence remain only in
the established private evidence domain.

This is a source/docs/tests-only repair. It did not access T1, a board, USB or
serial, and did not perform Flash, reset, NVS, registration, credential,
Broker, Manager, or Home Assistant mutation. The public-repository safety scanner, FC4 archive manifest regression, and Ruff
validation subsequently passed. The final staged-secret guard also passed
with all four repair files checked. KF-049 is guarded at source level; the
Git commit remains pending explicit authorization.
