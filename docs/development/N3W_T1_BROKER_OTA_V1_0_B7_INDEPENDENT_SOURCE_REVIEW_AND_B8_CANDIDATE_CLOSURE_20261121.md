# N3-W T1 Broker OTA V1.0 — B7 Independent Source Review and B8 Candidate Closure

DATE=2026-11-21
STATUS=CLOSED_PASS
PR=820
B7_EXECUTABLE_SOURCE_HEAD=dbc4f1ca5ce90f39e64887fb361d074ec51a7130
T1_ACCESS=false
T1_MUTATION=false
BROKER_LIVE_APPLY=false
MERGE=false
RELEASE=false

## 1. Scope

B7 independently reviews the frozen Broker OTA source after B6 exact target binding. It does not access T1 and does not install or enable the recovery package on a real host.

Reviewed paths include:

- LocalBrokerRecoveryPoint create / verify / restore / retire;
- Generic V2 apply / automatic rollback / explicit rollback / recover-broker-pending;
- runtime classification and rollback_source_phase preservation;
- Broker certificate-lifecycle exclusive guard;
- writer quiescence before Recovery Point create/restore;
- terminal Recovery Point retirement and crash-resumable tombstone;
- bounded systemd recovery unit;
- exact recovery-support package build / re-download / recheck;
- frozen Broker 2.1.4 target manifest and exact artifact binding.

## 2. B6 closure evidence

Frozen target:

- target manifest: infra/n3w-t1/upgrades/broker-2.1.4.json
- target image: local/n3w-mosquitto:2.1.4-5d96ab48
- predecessor: local/n3w-mosquitto:2.1.2-3184566d
- target artifact run: 44921739065
- target artifact ID: 14713718457
- target artifact digest: sha256:36d2d820b1d793f64014d910d08eace4d7ef90375adb2e43b1ba8e46a5195cf3
- target archive SHA256: 35630ff4b3ba710d26f1b44ac022b806c3ad53c2f1a015195e48c79690d26f3e
- target archive size: 13799035 bytes
- upstream linux/arm64 manifest: sha256:5d96ab48dab65f1198659af538139d999ab474dd78ee1c231ffff0f4d52552e0

Phase 2 run 44922182784 closed with source SUCCESS, exact-binding SUCCESS, isolated-a-to-b SUCCESS, and exact-artifact SKIPPED as required after freeze.

Frozen exact-binding markers:

- BROKER_2_1_4_FROZEN_TARGET_METADATA=PASS
- BROKER_2_1_4_FROZEN_EXACT_BINDING=PASS
- BROKER_TARGET_ARTIFACT_ID=14713718457
- BROKER_TARGET_IMAGE=local/n3w-mosquitto:2.1.4-5d96ab48

## 3. Independent source review

Result: NEW_SOURCE_BLOCKER_COUNT=0.

Key findings:

1. Recovery Point create binds source-root metadata, exact flat-file inventory, per-file size/mode/uid/gid and SHA256. The scan-to-open metadata race is closed by fstat checks before and after copy; destination bytes are checked against the original SHA256 before snapshot commit.
2. Restore verifies snapshot manifest/digests first and rejects source-root metadata drift before replacing any Broker state file.
3. Generic V2 creates the Broker Recovery Point only after Broker/Manager/Home Assistant writers are quiesced. Any failure from ACTIVATING onward is treated as target-write-capable and restores Broker persistent state before predecessor activation.
4. Host restart recovery uses the same durable V2 transaction and the same rollback engine. rollback_source_phase preserves the original write-capable phase across re-entry.
5. Even if Broker is already stopped, rollback reacquires the certificate-lifecycle exclusive lock and re-proves writer quiescence.
6. COMMITTED Broker transactions cannot use a stale Recovery Point for rollback. Terminal recovery only retires the Recovery Point; it does not restart product runtime.
7. Recovery Point retirement is idempotent and crash-resumable through the transaction-specific tombstone path. A new transaction is blocked until terminal Broker recovery retirement is recorded.
8. The recovery systemd unit is bounded, root-owned, condition-gated by upgrade.json, restart-limited, and does not create a Before-cycle with product activation owners.
9. The support installer enables the recovery unit without starting it, rejects active-unit installation, rejects partial/drifted payloads, and rolls back a failed enable attempt.

Direct regression coverage includes target automatic rollback, stopped-predecessor recovery ordering, rollback re-entry, certificate lock exclusivity, source metadata race, source-root drift, snapshot tamper, symlink source rejection, capacity preflight, stale committed snapshot rejection, terminal maintenance, retirement re-entry, and new-transaction retirement gating.

## 4. Final B8 candidate set

Recovery support exact package from current executable head dbc4f1ca5ce90f39e64887fb361d074ec51a7130:

- workflow run: 44922182840
- artifact ID: 14714301747
- artifact name: n3w-t1-core-updater-broker-recovery-support
- artifact digest: sha256:ca2d4ffdce131b2916d2a4d8ccf3d38d5a9c28781a65af51fdbb0cbac0068f09
- package manifest SHA256: 29be11a66e3bf53c4073120340064fab9f56fbe2c0c6e4a55e0dfb299ddf652f
- updater pyz SHA256: 1daed02060fe51b64d0ee648fd5855926e5759770a6634fccddc7c2804d2371d
- recovery unit SHA256: d5bea0c625edfcf46729170eac30872ae8a11c59fce14c89c6c585d46438ce19
- exact-package = SUCCESS
- artifact-recheck = SUCCESS

B8 candidate is the pair of the frozen target artifact and the current recovery-support artifact above. Old B5 artifact 14711625754 is historical only and must not be used for B8 because it predates the B7 Recovery Point hardening.

## 5. Boundary

B6=CLOSED_PASS
B7=CLOSED_PASS
B8=NOT_STARTED
B8_SCOPE=REAL_T1_READONLY_PREFLIGHT
B8_REQUIRES_EXPLICIT_T1_READONLY_AUTHORIZATION=true

No real T1 access, package installation, systemd enablement, Broker live apply, reboot/power-loss test, merge or release is authorized by this closure.
