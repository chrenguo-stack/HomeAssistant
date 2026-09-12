# N3W KF-089 ID20 Board A Schema-v5 boot postcheck

ID19 proved that Board A app0 contains the exact Schema-v5 image and that OTA selection now points to app0 (`ota_seq=5`, state `VALID`) while app1 remains the frozen rollback image. ID20 is the first normal application boot after that slot switch.

ID20 is intentionally split by an operator interlock inside one executor process. The executor claims the fresh authorization after host-only preflight, then waits while the operator performs exactly one normal Board A boot and a later fresh ROM re-entry. Only after the operator confirms that sequence does the executor perform read-only post-boot evidence capture.

Frozen predecessor:

```text
ID19_RESULT=PASS
ID19_EXECUTION_PACKAGE_COMMIT=643df426a03a20b319d8faa2a9d62eda9c56d6a6
SELECTED_SLOT=0
ACTIVE_OTA_SEQ=5
ACTIVE_OTA_STATE=2
APP0_SCHEMA5_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
APP1_ROLLBACK_SHA256=5a3004647de0ef71e7be5664863a62b76a47c0cfdb32e38b07a296ca379f7562
ID16_BOARD_A_PRIOR_SCHEMA=3
ID16_BOARD_A_PRIOR_BOOT_SESSION=11540229135812003068
```

## Operator interlock

After a separately granted ID20 physical authorization, start the executor while Board A is still in the ID19 ROM-download state. After host preflight and authorization claim, the executor prints the interlock instructions and waits.

The operator must then:

1. ensure Board B and every other N3-W test node capable of sending compact telemetry are fully powered off;
2. disconnect every Board A power source and USB so Board A is fully off;
3. release BOOT/GPIO9 completely;
4. connect Board A normally exactly once, without pressing BOOT, and leave the application running for at least 45 seconds;
5. do not open serial, do not reset, and do not perform a controlled Relay/RF experiment during that window;
6. fully power Board A off once;
7. hold BOOT/GPIO9 low, connect USB, wait for enumeration, release BOOT, and leave Board A in fresh ROM Download mode;
8. ensure no other `/dev/cu.usbmodem*` device is attached for this gate;
9. type the exact executor confirmation token only after the fresh ROM re-entry is complete.

The executor enforces a minimum 45-second interlock elapsed time. There is no automatic retry and no second normal boot under the same authorization.

Normal product Wi-Fi / ESP-NOW activity caused by the single application boot is expected and is not classified as a controlled RF experiment. The isolation requirement above is used to establish a clean Schema-v5 compact-telemetry baseline before the later separately authorized A/B Relay experiment.

## Read-only postcheck

After the operator interlock, the executor may only:

- route to the single enumerated USB modem and prove canonical Board A identity with `BASE MAC:`;
- read the partition table, full otadata, app0 image window, app1 image window, and NVS partition with reset suppression and `--no-stub`;
- decode `gh_n3w_diag/snapshot` offline using the frozen repository parser;
- write private evidence files outside the repository.

PASS requires all of the following:

```text
POST_SELECTED_SLOT=0
POST_ACTIVE_OTA_SEQ=5
POST_ACTIVE_OTA_STATE=2
APP0_EXACT_SCHEMA5=true
APP1_ROLLBACK_HASH_EXACT=true
DIAGNOSTIC_SCHEMA_VERSION=5
DIAGNOSTIC_BOOT_SESSION_NONZERO=true
DIAGNOSTIC_BOOT_SESSION_CHANGED_FROM_ID16=true
SNAPSHOT_UPTIME_MS>=5000
FINAL_PATH_STATE=DIRECT
CURRENT_CHANNEL in {1,6,11}
DIRECT_CHANNEL_HINT=CURRENT_CHANNEL
RELAY_ADVERTISEMENT_ATTEMPTS>=1
RELAY_ADVERTISEMENT_SUBMIT_SUCCESS>=1
BROADCAST_COMPLETION_COUNT>=1
RELAY_ACTIVE_COUNT=0
RELAY_TELEMETRY_ATTEMPTS=0
ALL_SCHEMA5_COMPACT_COUNTERS=0
```

This proves that the selected app0 Schema-v5 application actually executed and reached a live Direct N3-W runtime while establishing an uncontaminated compact-receive baseline. It does **not** prove Relay telemetry reception or end-to-end Relay telemetry.

A PASS routes only to `PREPARE_KF089_SCHEMA5_TWO_BOARD_RELAY_VALIDATION_PACKAGE`.

## Safety boundary

```text
FLASH_WRITE=false
FLASH_ERASE=false
NVS_WRITE=false
OTADATA_WRITE=false
APP0_WRITE=false
APP1_WRITE=false
PAIRING_CHANGE=false
T1_ACCESS=false
BOARD_B_PHYSICAL_ACCESS=false
CONTROLLED_RF_EXPERIMENT=false
SERIAL_OPEN=false
AUTO_RETRY=false
AUTO_ROLLBACK=false
SECOND_NORMAL_BOOT=false
```

This package does not itself authorize the physical boot. A fresh explicit ID20 authorization is required after exact-head host acceptance.