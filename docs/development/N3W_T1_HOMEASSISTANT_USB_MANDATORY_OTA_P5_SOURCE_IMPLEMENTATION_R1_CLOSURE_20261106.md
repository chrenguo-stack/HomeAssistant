# N3-W T1 Home Assistant mandatory-USB OTA P5 source implementation R1 closure — 2026-11-06

## 1. Gate result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_IMPLEMENTATION_R1_20261106_01
GATE_RESULT=CLOSED_PASS

SOURCE_DESIGN_HEAD=14a085f5efa7cce7439c084924ed7da53c19b620
R1_EXECUTABLE_SOURCE_HEAD=284a7120da246df733de61668f20fd46510c81ca
PR=#788
BRANCH=review/n3w-t1-core-updater-storage-policy-20261105

REAL_USB_FORMAT=false
LIVE_T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
R2_ENTERED=false
```

R1 implements only the mandatory-USB Home Assistant transaction contracts, durable state, removable-media admission logic, backup/recovery interfaces and mutual-exclusion guards. It does not perform a real block-device format, Docker image mutation, Home Assistant stop/start, live backup/restore or T1 mutation.

## 2. Implemented source

Added:

```text
tools/n3w_t1_core_updater_ha_usb.py
tools/n3w_t1_core_updater_ha_usb_state.py
tools/n3w_t1_core_updater_ha_usb_media.py
tools/n3w_t1_core_updater_ha_backup.py
tools/n3w_t1_core_updater_ha_recovery.py
tests/tools/test_n3w_t1_core_updater_ha_usb_r1.py
```

Localized Generic V2 repair:

```text
tools/n3w_t1_core_updater_v2_state.py
```

The Generic V2 change is deliberately small: an active HA-USB transaction blocks a new Generic V2 transaction, while an active Generic V2 or legacy transaction blocks creation of a new HA-USB transaction. Both transaction families use the same process-level state-root lock.

## 3. R1 contracts

### 3.1 Removable media

R1 freezes these pure admission rules:

```text
USB_FILESYSTEM_REQUIRED=ext4
USB_LABEL=N3W-UPDATE
USB_MEASURED_USABLE_CAPACITY_MIN_BYTES=15032385536
USB_NOMINAL_CAPACITY_NOT_AUTHORITY=true
EXACTLY_ONE_ELIGIBLE_NEWLY_INSERTED_REMOVABLE_DEVICE=true
ROOT_OR_PRODUCTION_BACKING_DEVICE_ALLOWED=false
READ_ONLY_DEVICE_ALLOWED=false
DISPLAY_IDENTITY_MATCH_REQUIRED=true
FILESYSTEM_UUID_BINDING_REQUIRED=true
```

Capacity admission is:

```text
USB_REQUIRED_BYTES =
  target_artifact_bytes
+ predecessor_recovery_worst_case_bytes
+ ha_data_backup_worst_case_bytes
+ transaction_metadata_and_working_bytes
+ removable_media_reserve_bytes

USB_PASS =
MEASURED_USABLE_BYTES >= 14_GiB
AND
MEASURED_USABLE_BYTES >= USB_REQUIRED_BYTES
```

No marketed-capacity field participates in the hard admission decision.

### 3.2 Backup/recovery

R1 requires an exact predecessor recovery record and a consistent pre-upgrade HA data recovery record before destructive cutover can be admitted.

The HA data record requires complete /config coverage, .storage/state coverage, metadata preservation, consistency, verification, fsync, confidentiality and authenticity. Unsupported external persistent state fails closed unless a later exact adapter exists.

### 3.3 Durable transaction state

R1 defines the U0-U13A/U13B transaction sequence under:

```text
/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json
```

State writes are private, atomic and fsync-backed. Terminal state is archived before a new HA-USB transaction is created. Raw authorization IDs and sensitive fields are not stored.

The destructive boundary remains closed until U9 and requires target, predecessor recovery, HA backup, production prestate, capacity and fresh one-shot authorization gates to have passed.

## 4. Historical P4/P5 exact-source binding repair

The first R1 executable candidate correctly caused the historical Home Assistant target-binding CI to fail because the old P4/P5 execution packages freeze the predecessor blob:

```text
tools/n3w_t1_core_updater_v2_state.py
HISTORICAL_FROZEN_BLOB=a5260f1097983cad4818f626826accbb185e4a37
```

R1 legitimately changes this file to add HA-USB/Generic-V2 mutual exclusion. The historical manifests and execution packages were therefore NOT rebound to the new blob.

The tests were corrected to prove all three facts:

1. the historical source-binding blob remains unchanged;
2. the R1 successor blob is different;
3. the historical executor rejects the successor source with source_blob_mismatch.

This preserves historical execution evidence instead of rewriting it.

## 5. Exact-head CI

Executable authority:

```text
R1_EXECUTABLE_SOURCE_HEAD=284a7120da246df733de61668f20fd46510c81ca
WORKFLOW_COUNT=16
SUCCESS=16
FAILURE=0
```

Focused required workflows include:

```text
N3W T1 Core Updater Manager A-to-B CI=SUCCESS
N3W T1 Core Updater Home Assistant 2026.10.4 target binding CI=SUCCESS
N3W T1 Core Stack current authority CI=SUCCESS
N3W Broker ingress guard CI=SUCCESS
N3W CI fast source and exact closure contract=SUCCESS
```

The HA target-binding workflow explicitly compiles the R1 HA-USB modules and executes the R1 focused test suite.

## 6. Updater package identity and baseline impact

Because R1 changes `n3w_t1_core_updater_v2_state.py`, the previous Generic V2 updater PYZ identity is historical only.

Current CI rebuilt and re-downloaded the Manager A-to-B Generic V2 package and verified its package binding:

```text
GENERIC_V2_SUCCESSOR_PACKAGE_RUN_ID=42164980902
GENERIC_V2_SUCCESSOR_PACKAGE_ARTIFACT_ID=13478294921
GENERIC_V2_SUCCESSOR_PACKAGE_ARTIFACT_NAME=n3w-t1-core-updater-manager-v2-5b32e1ae8210
GENERIC_V2_SUCCESSOR_PACKAGE_ARTIFACT_DIGEST_SHA256=79ad50e886373cc9110503c8b9cf5347325ec7978d58d7cd7978773011499505
GENERIC_V2_SUCCESSOR_UPDATER_PYZ_SHA256=5c094e6c147cfa4ca1c17e93d8c94a8334930a7a87c58eb179533fb9daf72095
GENERIC_V2_SUCCESSOR_UPDATER_PYZ_SIZE_BYTES=212673

OLD_ACCEPTED_UPDATER_PYZ_SHA256=65a5f62dcf9640d55067ab3104a8475a5bd1372ff1fce9a4441f18e3f53b2b46
OLD_ACCEPTED_UPDATER_PYZ_DISPOSITION=HISTORICAL_PACKAGE_EVIDENCE_ONLY
```

Important scope note:

```text
HA_USB_R1_MODULES_INCLUDED_IN_MANAGER_A_TO_B_GENERIC_V2_PACKAGE=false
R1_HOST_INTEGRATION_COMPLETE=false
```

The package above is proof that the existing Generic V2 package identity changed after the localized v2_state repair. It is NOT a complete HA-USB production execution package. Packaging/host integration remains a later bounded gate.

## 7. Production baseline classification

R1 source work did not modify the accepted T1 three-container production baseline:

```text
CURRENT_AUTHORITY_MANIFEST_CHANGED=false
U0_HISTORICAL_BASELINE_CHANGED=false
PRODUCTION_COMPOSE_CHANGED=false
GREENHOUSE_MANAGER_SOURCE_CHANGED=false
HOMEASSISTANT_CONFIG_CHANGED=false
BROKER_SOURCE_CHANGED=false
LIVE_T1_RUNTIME_STACK_CHANGED=false
```

Canonical live/repository product authority remains:

```text
CURRENT_AUTHORITY_MANIFEST=infra/n3w-t1/production/t1-core-stack-current.json
CURRENT_REPOSITORY_PRODUCT_SOURCE_HEAD=5b32e1ae82104a42f9e4e6907fe44d9172e87615
CURRENT_REPOSITORY_MANAGER=local/greenhouse-manager:fresh-5b32e1ae8210
CURRENT_REPOSITORY_HOMEASSISTANT=local/n3w-homeassistant:2026.10.0-0c73235a
CURRENT_REPOSITORY_BROKER=local/n3w-mosquitto:2.1.2-3184566d
LIVE_DEPLOYMENT_STATE=APPLIED_ACCEPTED
```

R1 changes development/updater source authority, not the currently deployed product stack.

## 8. Static safety review

At the R1 executable exact head, the HA-USB R1 modules contain no real execution paths for:

```text
mkfs/parted/sgdisk
/dev/* block-device mutation
docker load/rmi/prune
systemctl mutation
subprocess-based host execution
```

Therefore R1 remains a source-contract/state implementation gate.

## 9. Deferred work

R1 intentionally does not implement:

- real USB enumeration/format/mount commands;
- real Docker predecessor export/load/remove;
- real HA quiesce/backup/restore;
- power-loss host execution;
- greenhouse-manager MQTT Update control plane;
- approved OTA manifest/download provider;
- production host IPC;
- live T1 execution.

The MQTT Update/Manager control plane remains later work and must remain a projection/intent layer over T1 Core Updater, not a second upgrade authority.

## 10. Next gate

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_IMPLEMENTATION_R2_20261106_01
R2_SCOPE=SIMULATED_USB_TRANSACTION_ONLY
AUTO_EXECUTE_NEXT_GATE=false

REAL_USB_FORMAT=false
LIVE_T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

R2 may exercise the transaction against synthetic/loopback resources and fault injection, but it must not format real removable media or mutate the live T1.
