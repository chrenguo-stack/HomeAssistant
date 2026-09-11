# N3W KF-089 Board B ID09 passive runtime observation authorization — 2026-09-11

User explicitly authorized the following one-time physical observation gate:

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_PASSIVE_RUNTIME_OBSERVATION_20260911_09
AUTHORIZATION_GRANTED=true
REPLAY_PERMITTED=false
TARGET_ROLE=BOARD_B
PURPOSE=PASSIVE_USB_SERIAL_JTAG_RUNTIME_OBSERVATION
```

Authorized actions only:

1. Open the currently enumerated Board B USB Serial/JTAG interface using the already host-tested passive observer.
2. Keep DTR/RTS in the tested safe state that does not intentionally reset or force ROM download mode.
3. Passively read for at most 60 seconds under the monotonic deadline.
4. If USB re-enumeration occurs during observation, use the tested stable-device matching and bounded rebind path.
5. Classify observed evidence for current product runtime, N3-W runtime, Schema-v5 diagnostics, crash, or reboot-loop indications.
6. Stop at the deadline or earlier if the observer reaches a terminal classification.

Explicitly forbidden:

```text
RESET=false
REBOOT=false
BOOT_STRAP_CHANGE=false
FLASH_WRITE=false
OTADATA_WRITE=false
APP0_WRITE=false
NVS_MUTATION=false
ROLLBACK=false
AUTO_RETRY=false
BOARD_A_ACCESS=false
T1_MUTATION=false
```

The authorization is consumed at the first software open of the real Board B serial interface under this gate. No result from this observation implicitly authorizes any subsequent reset or write.
