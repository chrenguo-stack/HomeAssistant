# N3-W T1 R7 legacy OTA cutover precheck

The first spare T1 cutover returned `R7_LEGACY_CUTOVER_PRECHECK_STOP` with `legacy_daemon_state_mismatch` before stopping any unit or parking the application drop-in. The subsequent read-only observation confirmed that the legacy daemon was active and enabled, with its socket present and no pending daemon reload.

The loaded `90-u9plus-fault-acceptance.conf` matched the historical Phase A generator at `7811b6bc2fc3cdc5b1cecb45549cb81b6d80784c`. Its SHA-256 was `dcb4e566c12e6f57add6bcfb100a69001b3146b47abf4cb824a166726938aa6a`. The file replaces the legacy daemon's original start command with the Phase A candidate. For a terminal U13B transaction, the historical daemon can still evaluate the recovery completion checks on startup, including bound USB evidence.

The revised [executor](https://github.com/chrenguo-stack/HomeAssistant/blob/580609fd2bc850c6df2f8015c9b49e7a6881c1dd/tools/execution_packages/n3w/t1_legacy_ota_cutover/executor.py) binds the known legacy drop-in and command. It keeps the existing daemon process alive while it starts and verifies the standard application. If the application cutover fails, it restores the old application supervision using the same running daemon. The final step disables and stops the legacy daemon. An ambiguous finalization reports `R7_LEGACY_CUTOVER_FINALIZATION_PENDING` and leaves the verified standard application running.

Offline simulations passed for success, application startup failure and rollback, mismatched eligibility, mismatched transaction, unexpected drop-in, failed daemon stop, and a lost response after the daemon stopped. The revised script has not been executed on the spare T1. Live cutover and a fresh R7 read-only observation remain pending.

## Follow-up precheck

The revised executor stopped before stopping any unit with `systemd_properties_missing`. The prior forensic normalized absent and empty stop commands to the same boolean, so the live output does not identify which property rows were omitted. The [follow-up executor](https://github.com/chrenguo-stack/HomeAssistant/blob/d6d639644dbfb00f8dfc6994b8a20f80447a22a7/tools/execution_packages/n3w/t1_legacy_ota_cutover/executor.py) accepts omitted empty `ExecStop` and `ExecStopPost` on the legacy service. Exact checks of the unit and drop-in still bind both files to the known no-stop-hook configuration. Any nonempty stop hook still blocks execution. A missing required property reports its name and the unit.

Offline coverage used systemctl-shaped output with both stop rows omitted, a missing required `MainPID`, and a populated `ExecStop`. All nine simulated cutover and precheck cases passed. The shell launcher syntax and exact SSH payload also passed. Live cutover and a fresh R7 read-only observation remain pending.

## First live cutover and verified rollback

The spare T1 reached `SWITCH_SUPERVISION`, then returned `R7_LEGACY_CUTOVER_ROLLED_BACK` / exit 3 with `application_unit_state_mismatch`. The standard application had not been started and legacy daemon retirement had not begun. The return receipt reported both MQTT identities authenticated, Home Assistant HTTP 401 at version 2026.10.4, application data mount bindings preserved, the same broker runtime, and unchanged OTA transaction records. The parked application drop-in remains as a backup for the next attempt.

The previous acceptance required `ActiveState=inactive` after reload even after both containers had stopped. The failed receipt grouped active state, load state, enablement, and reload state, so it does not prove which property caused this attempt. The historical [U7 / KF-158 physical evidence](https://github.com/chrenguo-stack/HomeAssistant/blob/7811b6bc2fc3cdc5b1cecb45549cb81b6d80784c/docs/development/N3W_T1_U13B_P3_U7_READONLY_PREFLIGHT_20261118.md#u7-实机停点确认) shows this same unit can report `failed/failed/exit-code` with exit 130 after a confirmed stop.

The revised [executor](https://github.com/chrenguo-stack/HomeAssistant/blob/d7d1c3bc9de29a4ce39715a2d82fdbcb816c5c6d/tools/execution_packages/n3w/t1_legacy_ota_cutover/executor.py) accepts that narrowly defined stop state only with no main/control PID, zero restarts, and neither application container running. It retains loaded unit checks, emits the stop state before and after reload, and reuses an existing backup only after exact SHA-256 and ownership checks. Fifteen offline scenarios passed, including the historical stop shape, incorrect exit status, residual process, residual container, reload mismatch, safe backup reuse, and backup content mismatch. Live standard cutover and a fresh R7 read-only observation remain pending.

## Live stop with systemd exit status 137

The follow-up attempt reused the verified backup, stopped at `STOP_APPLICATION`, and returned `R7_LEGACY_CUTOVER_ROLLED_BACK` / exit 3. Systemd reported `failed/failed/exit-code`, `ExecMainStatus=137`, `MainPID=0`, `ControlPID=0`, and `NRestarts=0`. The receipt came from the systemd owner; the previous guard returned before reading the individual container states. Rollback verified both MQTT identities authenticated, Home Assistant HTTP 401 at version 2026.10.4, preserved application mount bindings, the same Broker instance, and unchanged OTA transaction records. Supervision was not switched in this attempt.

The revised [executor](https://github.com/chrenguo-stack/HomeAssistant/blob/6e9928a04fb81b9613c5e46e422eb10770926785/tools/execution_packages/n3w/t1_legacy_ota_cutover/executor.py) follows the stopped-owner semantics in `LocalHost.stop_services` and reuses its Docker running counts. Stop admission requires a terminal systemd state, no main/control process or restart, no running application replicas, and both original Docker containers exited. It records the systemd and per-container exit codes independently. A running/restarting container, Docker runtime error, or container OOM still blocks the switch. Nineteen offline scenarios passed. The combined launcher verifies all payload digests and runs the previously bound R7 read-only observer only after cutover success, with USB observation unrequested. Shell syntax, exact payload and observer sequencing passed offline. The revised attempt is pending on the spare T1.

## Spare T1 cutover and strict R7 running baseline passed

The operator ran cutover executor `6e9928a04fb81b9613c5e46e422eb10770926785` and read-only observer `3af2bf616d5e56c69f695b18a16d5377bb070950` against the recovery build for `84da7cd68e2f65fb011c32db1c3683b76a48112b`. The combined command returned `EXIT_CODE=0`.

| Evidence | Physical result |
| --- | --- |
| Legacy cutover | `R7_LEGACY_CUTOVER_PASS`; standard application verified, legacy daemon retired, verified drop-in backup reused |
| Strict running baseline | `RUNNING_BASELINE_PASS`, `diagnostic_only=false`, `errors={}`, Clean Reference records match |
| Runtime | ARM64; expected listeners and Compose references match; each reported restart count is zero |
| Application | Home Assistant stays at 2026.10.4; API returned the expected HTTP 401; Manager and Home Assistant MQTT identities authenticated |
| Continuity | Same Broker instance; application data mount bindings preserved; stable OTA transaction records (`COMMITTED` stack, `ROLLED_BACK` HA USB, no legacy Manager record) |
| Stop evidence | systemd main status 137 before and after reload; both original containers independently reported `exited` with exit 137, zero PID, no restart, no Docker runtime error and no OOM flag |
| Free host and Docker space | 4,759,891,968 bytes available; observed runtime storage is writable |
| Recovery package and USB | package absent, three recovery units inactive; USB `NOT_REQUESTED` |

This closes the standard-supervision drift and the running-baseline scope of R7. Package deployment, USB qualification and OTA execution are still pending. The existing target manifest binds predecessor `local/n3w-homeassistant:2026.10.0-0c73235a` and target `local/n3w-homeassistant:2026.10.4-5881590f`. The current live image is already the target, so this manifest cannot admit a genuine OTA from the present baseline.
