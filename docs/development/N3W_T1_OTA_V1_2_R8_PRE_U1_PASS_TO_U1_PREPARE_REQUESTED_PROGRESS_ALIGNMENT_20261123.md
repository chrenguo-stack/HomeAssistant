# N3-W T1 OTA V1.2 R8 PRE_U1 PASS → U1 PREPARE_REQUESTED Progress Alignment

## Scope

This record aligns the current chat/live-T1 state for PR #824 before switching conversations.
It does not authorize a merge, release, Broker OTA, USB format, reboot, or unrelated T1 mutation.

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR=824
CANDIDATE_BRANCH=review/t1-ota-r8-existing-tx-predecessor-prep-20261123
EXECUTABLE_SOURCE_HEAD=ea68af045fdde8c32e66d688bc7a136a80b30122
EXECUTABLE_HEAD_CI=16/16_SUCCESS
PR_STATE=OPEN_DRAFT
PR_MERGEABLE=true
```

## Source and artifact closure

The R8 predecessor-preparation implementation reuses the existing Home Assistant U0-U13 durable transaction and recovery engine.
A scratch parallel state-machine route remains superseded and must not be resumed.

The final activation-preflight compatibility repair at `ea68af045fdde8c32e66d688bc7a136a80b30122` keeps Manager monitoring self-test optional:
- current accepted live Manager may use natural telemetry only;
- Manager self-test is enabled only when the running Manager supports it;
- probe execution/import failures remain fail-closed;
- natural-only acceptance still fails closed when qualifying telemetry is unavailable.

Exact recovery artifact:

```text
ARTIFACT_ID=14782528541
ARTIFACT_NAME=n3w-t1-ha-recovery-install-ea68af045fdde8c32e66d688bc7a136a80b30122
ARTIFACT_ZIP_SHA256=dd2449ac934357a06e8889c3663add8ae2c018832b7c1db798aa9585e305973a
ARTIFACT_MANIFEST_SHA256=39e55949233f06afa535ac6dbc3ae3ca2fa72e04d8294c29c7dba0cefb2ee290
HA_RECOVERY_PYZ_SHA256=ffc402f72fe56309b0f108c870230d8288dba740859232b9bc749abc354492b1
DELTA_FROM_BE36C978=ha-recovery.pyz_only
```

## Live PRE_U1 closure

The exact ea68 updater is installed on the spare T1. Activation preflight passed with the actual accepted live Manager.

```text
CANDIDATE_ACTIVATION_PREFLIGHT_PASS=true
MANAGER_MONITORING_SELF_TEST_AVAILABLE=false
MONITORING_MODE=natural_only
STOP_POINT=PRE_U1
MANAGER_RUNTIME_UNCHANGED=PASS
HOMEASSISTANT_RUNTIME_UNCHANGED=PASS
NO_NEW_HA_TRANSACTION=PASS
CURRENT_10_4_STILL_RUNNING=PASS
TARGET_10_0_NOT_PRESENT=PASS
ACTIVE_COMPOSE_UNCHANGED=PASS
ACTIVE_ENV_UNCHANGED=PASS
USB_TRANSACTION_WRITE=false
HA_MANAGER_STOPPED=false
```

Live application identities observed during the closure:

```text
BROKER_IMAGE=local/n3w-mosquitto:2.1.2-3184566d
BROKER_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
MANAGER_IMAGE=local/greenhouse-manager:fresh-44e7d7472714
MANAGER_IMAGE_ID=sha256:1471828ab07cf9b71c01a6e78994711a5954f0a178b8be087a28bb65a967c7d2
HOMEASSISTANT_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
HOMEASSISTANT_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
ACTIVE_COMPOSE_SHA256=f5fc319e155e89c50d1a52fa7813a00f3cf36b4203937cae0d99c9ae5dbb9d15
ACTIVE_ENV_SHA256=3aa68488b4b08b0a099fc9492746cfa66e45274b6027a5eb83d8f4aee8c28f18
INSTALLED_UPDATER_PYZ_SHA256=ffc402f72fe56309b0f108c870230d8288dba740859232b9bc749abc354492b1
```

The prior HA USB transaction remained terminal:

```text
PREVIOUS_HA_USB_TX_STATUS=ROLLED_BACK
PREVIOUS_HA_USB_TX_PHASE=U13B_ROLLED_BACK
OLD_TRANSACTION_REUSE=false
```

## Frozen exact 2026.10.0 target

```text
TARGET_ARTIFACT_RUN_ID=41275979177
TARGET_ARTIFACT_ID=13070404405
TARGET_ARTIFACT_NAME=n3w-t1-fresh-exact-arm64-24382caae4a1f5d459297f86e8d18f10a848ca64
TARGET_ARTIFACT_DIGEST_SHA256=99eae7602eb2f8318bb7c0fff29d71fa61471071902b854a90666d4beb931b93
TARGET_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
TARGET_IMAGE=local/n3w-homeassistant:2026.10.0-0c73235a
TARGET_IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
TARGET_ARCHIVE_SIZE_BYTES=2448553472
TARGET_ARCHIVE_SHA256=e52d12779f7562d3f37a265d622fbaf31e758deba5998e40cafb5a33a118b663
TARGET_PLATFORM=linux/arm64
```

Local exact target archive was reverified before the handoff.

## Read-only capacity and predecessor measurement

The USB block device is present and exact identity is known, but it was not mounted in the host namespace at the measurement stop.

```text
USB_DEVICE_CLASS=existing_removable_ext4
USB_FILESYSTEM_UUID=b72ac2fc-79a0-4fb8-888e-f35b0114f959
USB_FSTYPE=ext4
USB_MAJOR_MINOR=8:1
USB_MOUNT_PRESENT=false
USB_PREPARATION_STATE=ORIGINAL_MOUNT_REQUIRED
USB_FORMAT_REQUIRED=false
USB_FORMAT_AUTHORIZED=false
```

Current internal free and exact predecessor export stream measurement:

```text
INTERNAL_AVAILABLE_BYTES=4748656640
PREDECESSOR_IMAGE=local/n3w-homeassistant:2026.10.4-5881590f
PREDECESSOR_DOCKER_SAVE_SIZE_BYTES=2447090176
PREDECESSOR_DOCKER_SAVE_SHA256=6502b8cdbf706d746e32311fdaa39ffc5ca703d76f766806bbb21d3c71278d1f
```

The measurement was read-only: no transaction creation, USB write, service stop, image load/release, target materialization, reboot or format occurred.

## Exact next execution contract already provided to the operator

The operator has intentionally not run the next command yet and will run it before/new-chat and paste its terminal result into the next conversation.

The command is bounded to:
1. retrieve the repository-owned exact R8 predecessor target manifest at executable head `ea68af045fdde8c32e66d688bc7a136a80b30122`;
2. construct and verify the approved local release envelope for exact 2026.10.0;
3. mount the already identified ext4 USB at the controlled host mountpoint `/mnt/n3w-ha-r8-predecessor` without formatting;
4. upload/publish the exact 2026.10.0 tar to updater-owned internal spool;
5. run `materialize-candidate`;
6. submit `--maintenance-submit-approved-release PREPARE`;
7. create a fresh normal Home Assistant transaction and stop at `U1_PREPARE_REQUESTED`.

Expected success markers:

```text
USB_MOUNTED_FOR_PREPARATION=PASS
REMOTE_APPROVED_ENVELOPE_EXACT=PASS
INTERNAL_TARGET_SPOOL_EXACT=PASS
CANDIDATE_MATERIALIZED=PASS
U1_TRANSACTION_EXACT=PASS
SERVICES_UNCHANGED=PASS
TARGET_10_0_NOT_LOADED=PASS
USB_TRANSACTION_DIRECTORY_CREATED=false
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
STOP_POINT=U1_PREPARE_REQUESTED
LOCAL_RESULT=PASS
```

The U1 command must not:
- stop HA, Manager or Broker;
- load exact 2026.10.0 into Docker;
- release current exact 2026.10.4;
- create/write the new `N3W-OTA/<transaction>/` directory;
- claim or consume install authorization;
- format USB;
- reboot/power-cycle;
- mutate Broker;
- merge or release PR #824.

After U1 PASS, the next source-backed operation is prepare-authority issuance and U1→U4 preparation, using the measured predecessor export size and actual USB free space. U1→U4 is the first step that writes the new transaction recovery directory on USB.

## Authorization state

The user explicitly authorized this bounded spare-T1 predecessor-preparation transaction:
exact Home Assistant 2026.10.4 → exact 2026.10.0, with existing U13B automatic rollback if needed.

The authorization permits the required updater deployment, target materialization, new normal U0-U13 transaction, existing-USB binding, fresh exact 10.4 rollback material, protected HA data backup, necessary HA/Manager stop/start, predecessor release and exact 10.0 load/acceptance subject to existing gates.

It does not authorize:
- USB formatting;
- reboot or power cycle;
- Broker OTA/mutation;
- PR merge;
- production release;
- unrelated T1 mutation.

Current handoff stop is before the next command's U1 transaction creation. The user plans to provide that command's output in the next conversation.

## Public evidence

Key PR #824 comments:
- bounded authorization: issue comment 7087966758;
- legacy Manager monitoring root cause and repair: 7089147017;
- live runtime correction: 7089366939;
- clean post-checksum rebind: 7089423519;
- mount-discovery measurement STOP: 7089552674;
- completed read-only predecessor/capacity measurement: 7089661164.

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```
