# N3-W T1 R7 legacy OTA cutover precheck

The first spare T1 cutover returned `R7_LEGACY_CUTOVER_PRECHECK_STOP` with `legacy_daemon_state_mismatch` before stopping any unit or parking the application drop-in. The subsequent read-only observation confirmed that the legacy daemon was active and enabled, with its socket present and no pending daemon reload.

The loaded `90-u9plus-fault-acceptance.conf` matched the historical Phase A generator at `7811b6bc2fc3cdc5b1cecb45549cb81b6d80784c`. Its SHA-256 was `dcb4e566c12e6f57add6bcfb100a69001b3146b47abf4cb824a166726938aa6a`. The file replaces the legacy daemon's original start command with the Phase A candidate. For a terminal U13B transaction, the historical daemon can still evaluate the recovery completion checks on startup, including bound USB evidence.

The revised [executor](https://github.com/chrenguo-stack/HomeAssistant/blob/580609fd2bc850c6df2f8015c9b49e7a6881c1dd/tools/execution_packages/n3w/t1_legacy_ota_cutover/executor.py) binds the known legacy drop-in and command. It keeps the existing daemon process alive while it starts and verifies the standard application. If the application cutover fails, it restores the old application supervision using the same running daemon. The final step disables and stops the legacy daemon. An ambiguous finalization reports `R7_LEGACY_CUTOVER_FINALIZATION_PENDING` and leaves the verified standard application running.

Offline simulations passed for success, application startup failure and rollback, mismatched eligibility, mismatched transaction, unexpected drop-in, failed daemon stop, and a lost response after the daemon stopped. The revised script has not been executed on the spare T1. Live cutover and a fresh R7 read-only observation remain pending.

## Follow-up precheck

The revised executor stopped before stopping any unit with `systemd_properties_missing`. The prior forensic normalized absent and empty stop commands to the same boolean, so the live output does not identify which property rows were omitted. The [follow-up executor](https://github.com/chrenguo-stack/HomeAssistant/blob/d6d639644dbfb00f8dfc6994b8a20f80447a22a7/tools/execution_packages/n3w/t1_legacy_ota_cutover/executor.py) accepts omitted empty `ExecStop` and `ExecStopPost` on the legacy service. Exact checks of the unit and drop-in still bind both files to the known no-stop-hook configuration. Any nonempty stop hook still blocks execution. A missing required property reports its name and the unit.

Offline coverage used systemctl-shaped output with both stop rows omitted, a missing required `MainPID`, and a populated `ExecStop`. All nine simulated cutover and precheck cases passed. The shell launcher syntax and exact SSH payload also passed. Live cutover and a fresh R7 read-only observation remain pending.
