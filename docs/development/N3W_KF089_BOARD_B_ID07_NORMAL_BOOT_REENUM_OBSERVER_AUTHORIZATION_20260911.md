# N3W KF-089 Board B ID07 normal boot with USB re-enumeration observer authorization — 2026-09-11

User explicitly authorized this one-time physical gate:

```text
AUTHORIZATION_ID=N3W_KF089_BOARD_B_NORMAL_BOOT_WITH_REENUM_OBSERVER_20260911_07
AUTHORIZATION_GRANTED=true
REPLAY_PERMITTED=false
TARGET_ROLE=BOARD_B
PURPOSE=NORMAL_BOOT_AND_SCHEMA_V5_OBSERVATION_WITH_USB_REENUMERATION_FOLLOW
```

Authorized actions only:

1. Start the reviewed USB re-enumeration observer before the physical boot/reset action.
2. Perform exactly one normal product boot/reset of Board B.
3. Follow USB Serial/JTAG disappearance and re-enumeration using stable device metadata; port path alone is not identity.
4. Re-bind the observer to the uniquely matched re-enumerated device and continue read-only serial capture.
5. Observe bounded evidence for app0 boot, product runtime, N3-W runtime, Schema-v5 diagnostics, reboot loop, or crash.
6. Stop after the bounded observation window.

Explicitly forbidden:

```text
FLASH_WRITE=false
OTADATA_WRITE=false
APP0_WRITE=false
FIRMWARE_REFLASH=false
ROLLBACK=false
SECOND_BOOT=false
AUTO_RETRY=false
BOARD_A_ACCESS=false
T1_MUTATION=false
```

Safety conditions:

- Observer must already be running before reset.
- Observer must not itself trigger reset or boot-mode changes.
- DTR/RTS must be held in the reviewed safe state.
- If stable identity cannot be uniquely re-bound after re-enumeration, STOP.
- If the one normal boot/reset yields no decisive evidence, STOP; do not perform a second boot under this authorization.
- This authorization is consumed at the first Board B software-open/physical boot action in this gate.
