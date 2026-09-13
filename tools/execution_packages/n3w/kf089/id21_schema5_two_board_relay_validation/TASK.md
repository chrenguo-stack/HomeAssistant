# KF-089 ID21 — Schema-v5 Two-Board Relay Validation

Status: `HOST_ONLY_PACKAGE_PREPARATION`

This package is the next gate after ID20R1 PASS. It does not itself authorize any physical action. A fresh explicit physical authorization bound to the final exact package commit is required before execution.

## Goal

Prove the Board-B-to-Board-A **board-side Relay telemetry chain** in a fresh Schema-v5 experiment while keeping T1 out of scope:

```text
B authenticated Relay acquisition
-> B relay telemetry submit
-> B unicast TX completion
-> A compact RX
-> A compact decode
-> A compact wrap/forward attempt
-> A compact forward submit
```

A PASS does **not** yet prove Manager/Broker/T1 receipt. PASS routes only to:

```text
PREPARE_KF089_T1_RELAY_INGRESS_CONFIRMATION_PACKAGE
```

## Why two independent boot sessions are required

ID21 deliberately separates the Direct baseline and selective-RF Relay experiment into different application boot sessions. Schema-v5 diagnostics reset at each `begin_boot_session()`, so the Relay-phase counters are directly attributable to that phase rather than inferred from a historical subtraction.

## Frozen predecessor

```text
ID20R1_RESULT=PASS
ID20R1_EXECUTION_PACKAGE_COMMIT=88c7d29a1c6f9fc2b17e371b0c6dd95f8867ab61
BOARD_A_SELECTED_SLOT=0
BOARD_A_ACTIVE_OTA_SEQ=5
BOARD_A_ACTIVE_OTA_STATE=2
BOARD_A_APP0_EXACT_SCHEMA5=true
BOARD_A_SCHEMA5_RUNTIME_ALIVE=true
BOARD_A_SCHEMA5_COMPACT_BASELINE_ZERO=true
```

Exact Schema-v5 image authority:

```text
SOURCE_COMMIT=5d58727f5040281ee2beb9597f66a6a2da9bac57
FIRMWARE_SIZE=1115648
FIRMWARE_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
```

## Physical execution sequence after later authorization

### P0 — fresh two-board ROM preclaim

Both boards begin fully unpowered. Each is placed into fresh ROM Download mode using BOOT/GPIO9 low during USB power-on. Only the two target `/dev/cu.usbmodem*` devices may remain enumerated.

The executor then:

1. reads complete silicon `BASE MAC:` from both boards;
2. maps Board A by public-safe suffix `F3:50` and Board B by suffix `F4:5C`;
3. reads partition table, otadata, exact-size app0/app1 windows, and NVS from both boards;
4. verifies both selected applications are the exact Schema-v5 image;
5. verifies Board A still selects app0 with `ota_seq=5`, state VALID;
6. verifies both diagnostic snapshots are Schema v5;
7. verifies the preserved Board A compact baseline is still all-zero before ID21 traffic.

USB paths are locators only. Complete MAC values remain private evidence and are never public authority.

### P1 — Direct baseline boot session

From ROM mode:

1. fully power off both boards;
2. normal-boot A and B exactly once with BOOT released;
3. keep both boards in normal AP coverage for at least 60 seconds;
4. do not create selective RF isolation;
5. fully power both boards off;
6. re-enter fresh ROM Download on both boards;
7. capture and decode both NVS snapshots.

PASS requires both boards to finish Direct (`path_state=0`), neither board to become RelayActive, neither board to send relay telemetry, and Board A compact counters to remain all-zero.

### P2 — selective-RF Relay boot session

From the Direct-baseline ROM state:

1. fully power off both boards;
2. normal-boot both boards exactly once;
3. keep both in normal AP coverage for at least 45 seconds;
4. only then move/isolate Board B into the already-qualified selective-RF condition while keeping Board A in normal AP coverage;
5. maintain the selective-RF condition for at least 150 seconds;
6. do not open serial and do not access T1;
7. at the end, power Board B off first;
8. keep Board A running for at least 10 additional seconds to allow diagnostics persistence;
9. power Board A off;
10. bring both boards back unpowered, then re-enter fresh ROM Download on both;
11. capture and decode both NVS snapshots.

The selective-RF condition is the previously qualified physical condition where Board B loses AP/Wi-Fi reachability while Board A remains Direct and A<->B ESP-NOW remains viable. ID21 does not use AP shutdown as a substitute when that would also disconnect Board A.

## PASS criteria

Board B must prove in the fresh Relay boot session:

```text
path_state=RELAY_ACTIVE
relay_active_count>=1
accept_verify>=1
peer_install_success>=1
relay_telemetry_attempts>=1
relay_telemetry_success>=1
unicast_completion_success>=1
```

Board A must prove in the same fresh Relay boot session:

```text
path_state=DIRECT
compact_rx_count>=1
compact_decode_success>=1
compact_forward_attempts>=1
compact_forward_submit_success>=1
```

Nonzero reject/failure counters do not automatically invalidate a successful chain if the required downstream success counters are also nonzero. The closure records all relevant counts and identifies the first unproven stage if the chain does not complete.

## Fail-closed localization order

```text
B_RELAY_ACTIVE
B_AUTHENTICATED_RELAY_ACQUISITION
B_RELAY_TELEMETRY_SUBMISSION
B_UNICAST_TX_COMPLETION
A_COMPACT_RX
A_COMPACT_STATE_GATE / A_COMPACT_CHILD_BINDING / A_COMPACT_DECODE
A_COMPACT_WRAP / A_COMPACT_FORWARD_ATTEMPT
A_COMPACT_FORWARD_SUBMIT
```

A STOP is final for that authorization. No automatic boot retry, reconnect retry, second capture, mutation retry, or improvised recovery is allowed.

## Forbidden

```text
FLASH_WRITE=false
FLASH_ERASE=false
NVS_WRITE=false
OTADATA_WRITE=false
APP_WRITE=false
PARTITION_TABLE_WRITE=false
BOOTLOADER_WRITE=false
PAIRING_CHANGE=false
CREDENTIAL_CHANGE=false
SERIAL_OPEN=false
T1_ACCESS=false
FIRMWARE_REFLASH=false
AUTO_RETRY=false
AUTO_ROLLBACK=false
THIRD_NORMAL_BOOT=false
```

ID21 is a controlled RF experiment but is otherwise read-only from the host. The only expected device-side writes are the product firmware's normal diagnostic NVS persistence during the two authorized application boot sessions.

## Evidence boundary

Private evidence root stores command argv/stdout/stderr/results, complete silicon identities, raw NVS images, and local device paths. Public GitHub may contain only sanitized counts, source/package hashes, public-safe suffixes, and adjudication summaries.
