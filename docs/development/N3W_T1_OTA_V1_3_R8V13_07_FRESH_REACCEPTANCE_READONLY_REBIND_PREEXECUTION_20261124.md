# N3-W T1 Core Stack OTA V1.3 — R8V13-07 fresh reacceptance read-only rebind pre-execution

Date: 2026-11-24

## 0. Status

```text
TASK=R8V13_07_FRESH_REACCEPTANCE_READONLY_REBIND
STATUS=EXECUTOR_READY_FOCUSED_CI_PENDING
PERSISTENT_CONFIGURATION_MUTATION=false
NEW_HA_TRANSACTION=false
OLD_TRANSACTION_REPLAY=false
R8V13_07_RESULT=NOT_PASS
R8V13_08_BLOCKED=true
BROKER_OTA=DEFERRED
```

KF-153 live repair is closed PASS and guarded. This new gate is only a fresh operational rebind before any new transaction authority.

## 1. Guarded entry authority

```text
KF152_STATUS=GUARDED
KF153_STATUS=GUARDED
LIVE_RECOVERY_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a

OLD_TRANSACTION_ID_SHA256=afbfeeb85c3ab579b62d86d347f76b7f6ee7f203b068eac028be1d18761950c3
OLD_TRANSACTION_FILE_SHA256=b5b7120b17539d1c4178450793dcf3d6900d0cba46c518132ad76fade8af04a0
OLD_TRANSACTION_STATUS=ROLLED_BACK
OLD_TRANSACTION_PHASE=U8_RECOVERY_ADMISSION_COMPLETE
OLD_TRANSACTION_FAILURE=ha_usb_release_predecessor_container_drift
OLD_TRANSACTION_REPLAY=false

LIVE_HOMEASSISTANT=local/n3w-homeassistant:2026.10.4-5881590f
LIVE_HOMEASSISTANT_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
LIVE_MANAGER=local/greenhouse-manager:fresh-1cae18039eee
LIVE_MANAGER_IMAGE_ID=sha256:c4bcb441de0554ebb20e3feb2b98a65cc435750539a2c951eb7be710ff191221
LIVE_BROKER=local/n3w-mosquitto:2.1.2-3184566d
LIVE_BROKER_IMAGE_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
EXPECTED_USB_UUID=b72ac2fc-79a0-4fb8-888e-f35b0114f959
```

## 2. Executor

```text
EXECUTOR=tools/execution_packages/n3w/t1_ota_r8v13_07/N3W_T1_R8V13_07_FRESH_REACCEPTANCE_READONLY_REBIND_20261124_04.sh
EXECUTOR_SOURCE_HEAD=6b9536803d42a167fe5954bb15aa73366e2f0fdc
EXECUTOR_SHA256=PENDING_FOCUSED_CI
FOCUSED_CI_RUN=45381783929
FOCUSED_CI_STATUS=PENDING_AT_THIRD_CHECK
```

The executor contains no systemctl start/stop/restart, Docker mutation, mount/unmount, image load/removal, authority publication, transaction creation or recovery replay.

It observes:

- exact guarded KF-153 pyz;
- exact terminal old transaction and no-replay semantics;
- exact HA/Manager/Broker runtime identities and restart counts;
- recovery retry timer + IPC socket state;
- target 10.0 Docker image absence;
- exact current predecessor launch binding;
- fresh Manager→Broker→HA maintenance self-test;
- historical prepare/install/release authority file existence, hashes, expiry and old transaction binding where present;
- approved manifest presence/hash;
- bound USB UUID/device/filesystem/mount state;
- current root and mounted-USB available bytes.

The maintenance self-test exercises the already-approved monitoring path but does not publish a new OTA authority or mutate product configuration.

## 3. Success contract

```text
OLD_TRANSACTION_TERMINAL_NO_REPLAY=PASS
RUNTIME_IDENTITIES=PASS
CURRENT_PREDECESSOR_BINDING=PASS
MANAGER_BROKER_HA_SELF_TEST=PASS
BOUND_USB_PRESENT=PASS
LIVE_RECOVERY_PYZ_SHA256=5208dadc14c2cf0024c0711de60ce0f70f5a19ea27de4e74f290d4c3c8bcfe0a
TARGET_10_0_PRESENT=false
PERSISTENT_CONFIGURATION_MUTATION=false
OLD_TRANSACTION_REPLAY=false
RESULT=R8V13_07_FRESH_REACCEPTANCE_READONLY_REBIND_PASS
```

Historical authorities may be absent or present only if expired. Any still-active historical authority is a STOP.

## 4. Downstream boundary

A PASS does not authorize a new transaction.

After PASS, the returned USB mount/capacity and authority state must be classified. Only then may a separate fresh R8V13-07 execution contract be prepared and explicitly authorized.

The fresh transaction must have a new transaction ID and fresh authority. It must never reuse transaction `afbfeeb8...`, its install authority, or the old continuation executor.

Success/failure contract remains:

```text
SUCCESS => new fresh transaction U13A_COMMITTED + healthy exact Home Assistant 2026.10.0
FAILURE => automatic safe recovery + healthy exact Home Assistant 2026.10.4
```
