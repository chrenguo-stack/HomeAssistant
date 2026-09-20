# N3-W PR #437 177468e Board B post-write release-boot + Manager Direct baseline

Status: PREPARED_FOR_OPERATOR_EXECUTION

## Authority

```text
TASK=N3W_PR437_BOARD_B_POSTWRITE_RELEASE_BOOT_AND_MANAGER_DIRECT_BASELINE_20260920_01

PRODUCT_SOURCE_HEAD=177468e290a207f2fb7f6c554aedf60b61373b4d
APPLICATION_SHA256=74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093

BOARD_B_HARDWARE_ID_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee
BOARD_B_NODE_ID_SHA256=dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59
```

## Scope

This gate performs one intentional hard reset from the current ROM bootloader state into the flashed application, then observes Manager canonical durable state.

It performs no flash write, no NVS write, no application-serial open, and no T1 mutation.

The T1 target is supplied only as a local command-line argument and is not stored in GitHub.

## Sequence

1. Read Manager running/restart/start-time state over SSH.
2. Use ROM esptool `read-mac` with `--before no-reset --after hard-reset` to prove the connected board identity and release Board B into normal boot.
3. Wait 30 seconds for preserved Wi-Fi/MQTT state to reconnect.
4. Read Board B canonical cursor from Manager SQLite in URI read-only mode.
5. Require `last_source=direct`.
6. Observe exactly 90 seconds.
7. Read the cursor again.
8. Require same boot session, Direct at both ends, seq delta >=10, updated_at advancement, and unchanged Manager restart count/start time.

## Execution

```bash
python3 /tmp/n3w-pr437-177468e-postwrite-direct-baseline.py \
  --port /dev/cu.usbmodem14101 \
  --t1-target <PRIVATE_T1_SSH_TARGET> \
  --output /tmp/n3w-pr437-177468e-postwrite-direct-baseline.json
```

The current established private target is supplied locally by the operator; do not commit it to public evidence.

## Boundary

```text
BOARD_RELEASE_HARD_RESET=true
BOARD_FLASH_WRITE=false
PRODUCT_NVS_WRITE=false
APPLICATION_SERIAL_OPEN=false
T1_ACCESS=SSH_READ_ONLY
T1_MUTATION=false
PR437_MERGE=false
```

A PASS establishes only the fresh post-write Direct baseline. It does not yet validate Direct -> Relay -> Direct physical failover for the new 177468e artifact.
