# N3-W T1 OTA V1.2 R8 predecessor-switch design

Date: 2026-11-22

## 1. Purpose

Prepare the spare T1 for the real R8 single-image Home Assistant acceptance by establishing a fresh exact `2026.10.0` predecessor runtime without ever starting that image against the current live `2026.10.4` data directory in place.

This is a bounded setup transaction. It is not the R8 OTA itself and it does not include Broker OTA.

```text
CURRENT=local/n3w-homeassistant:2026.10.4-5881590f
PREDECESSOR=local/n3w-homeassistant:2026.10.0-0c73235a
LIVE_WRITE_AUTHORIZATION=NONE
BROKER_OTA=false
R8_OTA=false
```

## 2. Fresh authority already closed

### Current 2026.10.4 rollback point

R8 isolated USB verification Attempt 03 is PASS.

Exact rollback material:

```text
IMAGE_REF=local/n3w-homeassistant:2026.10.4-5881590f
IMAGE_ARCHIVE_SHA256=31108a725e6b6530c68834218d9e41579055d7fe2718b3f42902b71237dc8e5f
IMAGE_ARCHIVE_SIZE=743051918
IMAGE_PORTABLE_IDENTITY_SHA256=efcf67bd4ff40cd902b43fc531aa9dce58d115ececc8ebd4e324a15e0f4952f3

BACKUP_ARCHIVE_SHA256=b6f7ad3803c1ae954d2d946562b5ae1db8725786e4c457db8a1deff7b10623e2
BACKUP_ARCHIVE_SIZE=2090112
BACKUP_MANIFEST_SHA256=1cf39dad34b36b8901c24151cc7d4b3ec6fa09b25264f6812c3a9e51569409ac
```

That P3 point proves a usable emergency rollback image and authenticated historical data snapshot. The switch transaction must additionally create a new current-data backup before altering the current data binding, because the historical P3 data snapshot is not the current data state.

### Exact 2026.10.0 image

Operator Mac cache authority:

```text
IMAGE_REF=local/n3w-homeassistant:2026.10.0-0c73235a
IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
ARCHIVE_SIZE=2448553472
ARCHIVE_SHA256=e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663
PLATFORM=linux/arm64
```

The cache is transferred only after the current HA image has been released and post-release capacity has passed. It must be streamed directly into `docker load`; the 2.45 GB tar must not be copied into the T1 internal filesystem first.

## 3. Data compatibility authority

The frozen product compatibility review is:

`infra/n3w-t1/upgrades/homeassistant-2026.10.4-compatibility-review.json`

It binds:

```text
PREDECESSOR=2026.10.0
CANDIDATE=2026.10.4
MUTATION_PROFILE=IMAGE_ONLY_V1

core.config_entries:  version 1 / minor 5 -> version 1 / minor 5
core.device_registry: version 3 / minor 4 -> version 3 / minor 4
core.entity_registry: version 1 / minor 23 -> version 1 / minor 23

PEER_CONTRACTS_COMPATIBLE=true
PERSISTENT_SCHEMA_COMPATIBLE=true
ROLLBACK_COMPATIBLE_SOURCE_REVIEW=true
```

The frozen target manifest independently states `rollback_compatible=true`.

Therefore the predecessor-switch transaction does not need an unavailable historical 2026.10.0 data backup. Instead it must construct the 10.0 baseline from a **fresh, quiesced snapshot of the current compatible data** while keeping the current 10.4 data directory untouched.

The older rule remains valid in its intended form: never start 10.0 directly on the live 10.4 data directory unless rollback compatibility has been proven. The compatibility review supplies that authority, but this setup still uses an isolated restored copy so the current directory is not mutated by 10.0.

The deferred `2026.11.0` target is explicitly not covered: its entity-registry schema advances and would require a separate migration/rollback design.

## 4. Data-root transaction

Current production data root:

`/var/lib/n3wfc4-homeassistant`

Required sequence after application writers are quiesced:

1. create a fresh protected HA backup on the bound USB in a new transaction-specific directory;
2. immediately verify the encrypted archive, HMAC, decrypted manifest, SQLite integrity and source consistency;
3. materialize that verified backup into a new private staging directory on the same internal filesystem;
4. verify the staged tree before publication;
5. preserve the original current data directory by atomic same-filesystem exchange/rename semantics;
6. publish the staged compatible snapshot at the existing production path;
7. never modify or delete the preserved original 10.4 directory during predecessor setup.

The Compose bind source therefore remains the existing production path. No permanent alternate Compose architecture is introduced.

Rollback before R8 begins:
- stop application writers;
- restore the preserved original 10.4 directory atomically;
- restore the 10.4 image/binding;
- start and verify the previous runtime.

The fresh USB backup is the durable fallback if the internal preserved directory is unavailable.

## 5. Single-image transaction

The setup must enforce:

```text
BEFORE_RELEASE=only current 2026.10.4 resident
AFTER_CURRENT_RELEASE=no HA image resident
AFTER_10_0_IMPORT=only exact 2026.10.0 resident
```

No global Docker prune is permitted.

Release of current 10.4 requires:
- Manager and HA writers stopped;
- exact current HA container identity proven;
- no other container users of the exact image ID;
- current image has no unexpected extra tags/references;
- current rollback image and fresh data backup are already verified;
- release intent is durable before container/image removal.

Only the exact stopped HA container and exact current image ID may be removed.

## 6. Capacity rule

The pre-release free-space readings around 4.75 GB are not an admission result.

The decisive point remains:

```text
CAPACITY_DECISION_POINT=AFTER_RELEASE_BEFORE_NEXT_IMPORT
```

Operator-side source-check must parse the exact 2026.10.0 Docker archive and derive the exact worst-case unpacked-layer requirement using the same portable-image parser used by R8.

Remote execution must:
1. release exact current 10.4;
2. call `statvfs` on the actual Docker/internal filesystem;
3. compare the fresh measured available bytes against the frozen 10.0 import requirement;
4. STOP and automatically restore 10.4 if insufficient;
5. only then accept the Mac-side stream into `docker load`.

No capacity decision may reuse the pre-release measurement.

## 7. 10.0 baseline health

Because the production Compose already mounts:
- the product `configuration.yaml`;
- the `n3w_mqtt_bootstrap` custom component;
- the HA MQTT bootstrap metadata;
- the HA MQTT password;

the restored compatible data copy must be able to start under the normal product stack. The normal bootstrap logic can create or validate the MQTT entry without copying secrets into the execution package.

Baseline PASS requires:
- exact HA image ref and exact expected image ID;
- linux/arm64;
- HA container running with restart count 0;
- product HTTP endpoint ready (200 or 401);
- expected listener contract;
- Manager unchanged and running;
- Broker unchanged and running;
- Manager MQTT authenticated;
- HA MQTT authenticated;
- dynamic HA image binding points at exact 10.0;
- no current 10.4 HA image remains resident;
- preserved original 10.4 data directory remains present and unmodified.

This is stricter than merely seeing the container start. If full product health does not return, setup automatically rolls back instead of accepting a degraded predecessor baseline.

## 8. Failure recovery

The executor is fail-closed and single-process across the destructive window.

Before current image release, a failure only needs to restore any changed data/binding state and restart the original services.

After current image release:
1. quiesce writers;
2. if 10.0 was partially/fully loaded, remove only its exact verified container/image ownership;
3. remeasure internal space;
4. load the freshly verified 10.4 predecessor archive from the bound USB;
5. restore current image binding;
6. atomically restore the preserved original 10.4 data directory;
7. start services;
8. prove exact 10.4 full health.

If USB recovery media becomes unavailable after current image release, the transaction must report a recovery-required terminal and must not fabricate success.

## 9. Interrupted-process / power-loss recovery

This predecessor setup is a one-time laboratory preparation transaction, not the shipped R8 OTA runtime. It therefore does not install a new permanent systemd recovery daemon.

Before the first destructive action the transaction writes a root-owned private journal. Each subsequent phase records:
- exact source head;
- exact current and predecessor image refs/IDs;
- exact P3 rollback transaction/archive authority;
- exact bound USB device identity;
- exact predecessor archive identity and import worst-case;
- fresh backup identity;
- original/staged filesystem IDs and inode identities;
- post-release capacity result where available.

The same exact source exposes:
- `status`: read-only journal observation;
- `recover`: continue the already-authorized transaction only toward exact healthy 2026.10.4.

Recovery does not require a new predecessor-switch authorization because it cannot advance toward 10.0. It can only:
1. verify the persisted exact recovery authority;
2. bind and verify the exact P3 USB recovery point;
3. quiesce application writers;
4. remove an exact 10.0 image/container only when ownership is provable;
5. infer the published/preserved data side from the journaled filesystem/inode identities and restore the original 10.4 directory;
6. restore the exact 10.4 image from the P3 USB archive if it is absent;
7. restore the exact current binding;
8. start and prove full 10.4 health;
9. record `ROLLED_BACK`.

The exact recovery zipapp is cached on the operator Mac during the mandatory read-only preflight, so recovery does not depend on GitHub artifact availability after the live transaction has started.

A narrow fail-closed boundary remains for interruption **inside** `docker load`: if Docker leaves storage residue that is not attributable to the exact 10.0 image ID and that residue prevents the exact 10.4 recovery image from loading, the recovery path reports `RECOVERY_REQUIRED`. It must not use global prune or guess ownership. PR #821's product R8 single-image design remains unchanged; this limitation is specific to the one-time predecessor-setup streaming operation and is not silently promoted to a product guarantee.

## 9. Authorization

Source, tests, CI and read-only preflight may proceed now.

The execution package must default to:

```text
LIVE_WRITE_AUTHORIZATION=NONE
EXECUTION_PERMITTED=false
```

A later live grant must bind at minimum:
- exact execution-package source head;
- spare T1 SSH host-key SHA256;
- current exact 10.4 image ref/id;
- bound USB transaction SHA256 and device identity;
- Attempt 03 rollback image/backup identities;
- exact 10.0 Mac archive SHA256/size/image ref/image ID;
- operator-derived 10.0 import-space requirement;
- exact mutation scope;
- expiry;
- one-time authorization identifier.

The grant must not be committed to GitHub.

## 11. Out of scope

- Broker OTA;
- Manager OTA;
- 2026.11.0 migration;
- production T1;
- board firmware;
- merge/release;
- deleting USB data;
- deleting the preserved original 10.4 data directory;
- historical-data migration coverage outside the frozen 10.0↔10.4 compatibility review.

## 12. Next gates

```text
PRED_SWITCH_SOURCE_AND_TESTS
-> READONLY_SWITCH_PREFLIGHT
-> EXACT_LIVE_AUTHORIZATION
-> CURRENT_10_4_QUIESCE_AND_FRESH_BACKUP
-> EXACT_CURRENT_IMAGE_RELEASE
-> POST_RELEASE_CAPACITY_MEASURE
-> STREAM_EXACT_10_0_IMPORT
-> ISOLATED_COMPATIBLE_DATA_PUBLICATION
-> 10_0_FULL_HEALTH
-> PREDECESSOR_SWITCH_PASS
-> R8_10_0_TO_10_4_ACCEPTANCE
```

No live gate is authorized by this document.
