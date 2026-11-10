# N3-W T1 Home Assistant mandatory-USB OTA P5 / R7A Boundary B PREPARE-only preexecution closure — 2026-11-08

## 1. Gate

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_BOUNDARY_B_PREPARE_ONLY_PREEXECUTION_20261108_01
RESULT=CLOSED_PASS

A1_CLOSURE_HEAD=276811043c9eca9ba6c66198588fb89b14cd3b36
A1_CLOSURE_CI=25_SUCCESS_0_FAILURE_0_PENDING
A1_LIVE_RESULT=PASS

SOURCE_REVIEW=PASS
SOURCE_REPAIR_REQUIRED=false
DESIGN_CORRECTION_REQUIRED=true
DESIGN_CORRECTION=PREPARE_BEFORE_USB_INSERTION
```

This gate is source/design only. It does not access the real T1, insert a USB device, create a new live PREPARE transaction, invoke destructive confirmation, or enter U2+.

## 2. Correct Boundary B sequence

The frozen physical sequence is:

```text
A1 software activation healthy
-> dedicated test USB absent
-> user presses Home Assistant "准备 Home Assistant 升级"
-> Manager sends PREPARE only
-> privileged host creates U1 transaction
-> current removable-device inventory is recorded as baseline
-> phase=USB_REQUIRED
-> user inserts exactly one dedicated removable test USB
-> discovery worker enumerates block devices read-only
-> exactly one fresh eligible candidate appears
-> candidate model/capacity is projected to Home Assistant
-> phase=USB_REQUIRED_CONFIRMATION
-> destructive confirmation button becomes visible
-> STOP
```

A USB inserted before PREPARE is part of the baseline and is intentionally not eligible as the new candidate. This is a safety property, not a defect.

## 3. Source-path proof

### Product control surface

`host/greenhouse-manager/src/greenhouse_manager/runtime/ha_update.py` publishes two separate Home Assistant entities:

- `n3w_t1_homeassistant_prepare` -> `PREPARE`;
- `n3w_t1_homeassistant_confirm_usb` -> `CONFIRM_USB_ERASE`.

The confirmation entity is published only when the runtime phase is `USB_REQUIRED_CONFIRMATION`, `usb_confirmation_required=true`, and the candidate model/capacity are visible.

### Manager control gate

`T1OtaManager.handle_control()` accepts PREPARE only when no transaction is already in progress. It accepts `CONFIRM_USB_ERASE` only when the runtime already reports the confirmation phase.

### Privileged PREPARE path

`HaUsbIpcExecutor.submit("PREPARE", ...)`:

1. resolves the exact approved release;
2. creates a new transaction;
3. transitions only U0 -> U1;
4. calls `HaUsbPrepareController.begin()`;
5. records the current removable-device public fingerprints as the baseline;
6. writes U1 state;
7. starts the discovery worker.

No confirmation worker is started by PREPARE.

### Read-only discovery

The discovery worker calls only `ensure_started()` and `refresh_candidate()`. The host inventory backend uses `findmnt` and `lsblk` for read-only classification. Candidate projection does not call `format_and_mount()`.

Exactly one fresh eligible candidate is required. Multiple fresh candidates produce `usb_multiple_eligible_devices`. Root-backed or mounted devices are excluded.

### Destructive boundary

The path that may reach `wipefs`, partitioning, `mkfs.ext4`, mount and target download is behind the distinct `CONFIRM_USB_ERASE` action and `confirm_and_prepare()`. That action is outside Boundary B.

## 4. Existing regression evidence

The current test suite already guards the required contract, including:

- `test_prepare_records_inserted_baseline_and_requires_new_usb`;
- `test_multiple_new_usb_devices_fail_closed_before_format`;
- `test_root_or_mounted_device_never_becomes_confirmation_candidate`;
- `test_confirmation_without_published_candidate_does_not_format`;
- `test_raw_capacity_below_floor_never_formats_media`;
- `test_read_only_usb_never_becomes_confirmation_candidate`;
- `test_prepare_creates_only_u1_transaction`;
- `test_dispatcher_rejects_path_injection_without_executor_call`;
- `test_r7a_status_is_read_only_for_u1_candidate_projection`;
- Home Assistant discovery tests that keep PREPARE and `CONFIRM_USB_ERASE` on separate entities.

No runtime source repair is needed for this gate.

## 5. Physical evidence contract for the next gate

Before real execution, the operator must verify:

```text
A1_HOST_DAEMON_ACTIVE=true
MANAGER_OTA_ENABLED=true
RECOVERY_REQUIRED=false
NO_ACTIVE_HA_USB_TRANSACTION=true
DEDICATED_TEST_USB_INSERTED=false
SECOND_REMOVABLE_DEVICE_PRESENT=false
```

After PREPARE but before USB insertion:

```text
PHASE=USB_REQUIRED
USB_CONFIRMATION_REQUIRED=false
USB_CANDIDATE=null
CONFIRM_USB_ERASE_INVOKED=false
```

After inserting exactly one dedicated USB:

```text
PHASE=USB_REQUIRED_CONFIRMATION
USB_CONFIRMATION_REQUIRED=true
USB_CANDIDATE_MODEL_VISIBLE=true
USB_CANDIDATE_CAPACITY_VISIBLE=true
CONFIRM_USB_ERASE_INVOKED=false
WIPEFS=false
PARTITION_WRITE=false
MKFS=false
MOUNT=false
TARGET_DOWNLOAD=false
```

The public GitHub record must not contain the private T1 locator, operator known_hosts path, host-key fingerprint, raw USB serial/WWN, or credentials.

## 6. Hard stop and next gate

```text
REAL_USB_INSERTION_AUTHORIZED=false
PREPARE_EXECUTION_AUTHORIZED=false
CONFIRM_USB_ERASE_AUTHORIZED=false
U2_PLUS_AUTHORIZED=false
BOARD_ACCESS_AUTHORIZED=false
MERGE_AUTHORIZED=false

NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_BOUNDARY_B_REAL_USB_PREPARE_ONLY_EXECUTION_20261108_01
AUTO_EXECUTE_NEXT_GATE=false
```

The next gate is a physical acceptance gate and requires explicit user authorization. It must stop at `USB_REQUIRED_CONFIRMATION` and must not press or invoke the destructive confirmation action.
