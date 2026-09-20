# N3-W PR #437 177468e post-write Manager Direct baseline recovery

Status: PREPARED_FOR_OPERATOR_EXECUTION

## Why this recovery gate exists

The preceding release-boot executor stopped with:

```text
STOP=connected target is not frozen Board B identity
```

That STOP is an execution-harness defect, not current evidence of a wrong physical target.

The repository's frozen public-safe Board B identity authority is:

```text
FROZEN_BOARD_B_HARDWARE_ID_SHA256=
cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0
```

The stale value used by the earlier PR437 write/preflight package was:

```text
3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee
```

That stale hash corresponds to a six-byte truncation of the ESP32-C6 printed EUI-64 prefix, not the board's Base MAC-derived hardware identity. The earlier preflight's automated identity PASS is therefore invalidated as an identity proof.

The later independent ROM output exposed the actual Base MAC, and its hardware-ID SHA-256 matches the repository-frozen Board B hash above. This separately recovers the target identity.

The release executor itself used the correct `BASE MAC` parser but retained the stale expected hash. Because esptool ran with `--after hard-reset`, the hard-reset command completed before Python evaluated the hash mismatch. Application start is not claimed until Manager evidence below proves it.

## Scope

This recovery package performs no USB access and no board reset. It only observes Manager canonical durable state over SSH for exactly 90 seconds.

```text
BOARD_ACCESS=false
BOARD_RESET=false
BOARD_FLASH_WRITE=false
PRODUCT_NVS_WRITE=false
APPLICATION_SERIAL_OPEN=false

T1_ACCESS=SSH_READ_ONLY
T1_MUTATION=false
```

The replay database path is discovered from the running Manager's own `GH_N3W_REPLAY_DB_PATH` environment and opened SQLite URI `mode=ro`; no hardcoded deployment path is assumed.

## Acceptance

Require:

```text
Manager running at both ends
Manager restart count unchanged
Manager StartedAt unchanged
Board B canonical cursor found at both ends
source=direct at both ends
same boot_session
seq delta >= 10 over exactly 90 s
updated_at advanced
```

## Execution

```bash
python3 /tmp/n3w-pr437-177468e-postwrite-manager-baseline-recovery.py \
  --t1-target <PRIVATE_T1_SSH_TARGET> \
  --output /tmp/n3w-pr437-177468e-postwrite-manager-baseline-recovery.json
```

A PASS closes the post-write Direct baseline only. It does not yet validate Direct -> Relay -> Direct physical failover.
