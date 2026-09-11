# N3W KF089 Board B ID10 True System Reset and Schema-v5 Observation Authorization

AUTHORIZATION_ID=N3W_KF089_BOARD_B_TRUE_SYSTEM_RESET_AND_SCHEMA_V5_OBSERVATION_20260911_10
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_PERMITTED=false

Purpose: perform one true ESP32-C6 system reset that re-samples boot straps, then observe Board B USB Serial/JTAG for up to 60 seconds using the already host-tested bounded re-enumeration observer.

Authorized physical scope:
- Start observer first.
- Confirm observer is ready without stdin dependency.
- Confirm BOOT/GPIO9 is physically released/not held low.
- Perform exactly one EN/CHIP_PU reset, or one complete power-cycle if EN/CHIP_PU reset cannot be proven available.
- Observe boot/runtime evidence for up to 60 seconds.

Forbidden:
- esptool/RTS-only hard reset as substitute for the system reset.
- second reset or automatic retry.
- flash/app0/otadata/NVS writes.
- rollback/reflash.
- Board A access.
- T1 mutation.

Known preconditions:
- existing app0 image was previously verified exact.
- persistent otadata was previously verified EXPECTED_POSTCHANGE_EXACT selecting app0.
- firmware failure is not proven.
- ID06 and ID07 were CORE_RESET_ONLY and did not resample boot straps.
- ID09 captured ROM DOWNLOAD mode with `waiting for download`.
- passive observer serial open path has been host-audited for DTR/RTS safe-open behavior.

Success evidence should include normal boot (not DOWNLOAD), product runtime, N3-W runtime, and Schema-v5 evidence such as N3W_DIAG_DISCOVERY and/or PHASE4_LAB_TELEMETRY.
