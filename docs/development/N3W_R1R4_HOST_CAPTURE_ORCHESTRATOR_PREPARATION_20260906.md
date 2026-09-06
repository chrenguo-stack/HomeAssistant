# N3W R1R4 host capture orchestrator preparation

This is a host-only preparation boundary. It does not open a real serial
port, reset or flash a board, or execute RF.

## Implemented scope

`experiments/n3w_r1r4_host_capture_orchestrator.py` provides a small state
machine with an injected byte-source boundary and a lazy `pyserial` live
backend. It writes independent raw byte
files (`control.raw` and `dut.raw`) and host-timestamped JSONL event files,
plus a durable host event stream (`host.events.jsonl`), and writes a final
`capture-manifest.json`.

The state machine distinguishes:

- `collector_ready`: a reader has reported a matching unique device binding;
- `heartbeat_received`: actual bytes contained a heartbeat;
- `experiment_started`: the host entered the fixed live capture window;
- `experiment_start_observed`: a device lifecycle gate was observed;
- `summary_received` / `experiment_end_observed`: a role emitted its summary;
- `port_disconnected`, `port_reconnected`, `log_missing`, and
  `summary_missing`.

The lifecycle gate is never used as the startup barrier. The manifest reports
`capture_completeness` and `observed_lifecycle_results` separately. A summary
does not become an experiment PASS automatically; the parser preserves the
real CONTROL fields (`baseline`, `probe_tx_api`, `home_ack`) and DUT fields
(`baseline`, `roc_req`, `probe_rx`, `roc_cancel`, `home_recovery`,
`home_ack_tx`, `disconnect_count`). The final product conclusion remains a
raw-log review outcome.

Replay mode has no `serial` import. Explicit live mode uses `SerialBackend`,
which opens with `dsrdtr=false`, `rtscts=false`, and DTR/RTS driven low before
open; it never writes bytes to a board. It verifies the pre-bound descriptor,
records reader-ready only after a successful open, detects read failures, and
attempts bounded reconnects. A reconnect with no observed boot boundary is
not spliced into a valid capture once the experiment has started; a boot
marker after a heartbeat is `device_reboot_detected` and invalidates the run.

The current host virtualenv has Python 3.11.9/pytest 8.4.2 and `pyserial` 3.5.
Import/version verification passed; no live backend was opened in this
host-only boundary.

## Simulated validation

`tests/n3w_r1r4_host_capture/test_orchestrator.py` covers:

1. normal CONTROL/DUT completion;
2. one endpoint with no data and bounded `log_missing`;
3. startup heartbeat missing while a lifecycle gate is present;
4. mid-run disconnect/reconnect and missing summary;
5. summary presence without an explicit product PASS;
6. lifecycle gate arriving before host start, which is recorded as a timing
   violation rather than accepted as a barrier.
7. duplicate device binding, role swap, non-empty output directory, and the
   simulated serial backend's disconnect/reconnect plus boot-session guard.
8. bytes received after `HOST_COLLECTOR_READY` followed by disconnect before
   the capture window completes, which is invalidated rather than treated as a
   complete capture.
9. a bounded live window that starts without operator input.

These tests prove only the host state machine and replay behavior. They do not
prove real USB enumeration timing.

## Physical execution order after a separate physical gate

1. Preserve the current product/diagnostic artifact and recovery evidence;
   bind each physical USB identity to CONTROL or DUT before opening a reader.
2. Start both reader loops and their durable raw/event outputs.
3. Require two explicit `collector_ready` events with matching identities.
4. Announce `HOST_COLLECTOR_READY` only after the reader loop is running, then
   start the fixed 60-second capture window immediately. No Enter or other
   operator input is required, and the reader never blocks on stdin.
5. Power/reset/start the diagnostic application according to the
   already-approved physical procedure. Do not wait for a device lifecycle
   gate to start capture.
6. Keep reading until both role summaries are received or the bounded 60-second
   window ends. Require heartbeat → lifecycle gate → summary on each endpoint;
   otherwise write `capture_completeness=INCOMPLETE` and
   `capture_valid=false`.
7. If USB re-enumerates, record disconnect, accept only the same bound device
   identity on reconnect, and resume the same role's files. A mismatch is a
   hard stop.
8. Preserve raw bytes, host events, manifest, artifact hash, and role binding
   evidence. Evaluate summary presence and product PASS independently.

The existing firmware starts its capture task before its autonomous lifecycle
tasks, which is useful evidence, but it cannot guarantee that a host reader
was already running. No firmware host-arm change is implemented here. Such a
change would be required only if the physical procedure cannot ensure the
power/start action occurs after both host `collector_ready` events.

For port handoff, the flasher must be stopped and its handle released before
the collector opens the port. After capture closes both handles, a separately
authorized flasher may reacquire them. No DTR/RTS reset pulse or data write is
part of this collector handoff.

## Recovery-material classification

The R1R4 diagnostic artifact is a diagnostic build package, not an original
product recovery package. It contains CONTROL/DUT diagnostic images,
`flasher_args.json`, partition tables, and role `sdkconfig` files. The
original product image, target-specific backup, identity state, and persistence
preservation remain governed by the existing product recovery chain and must
be bound before any physical action. This preparation does not repeat a full
flash or backup and does not change partition layout or persistence policy.

The existing R1 physical closeout records reusable target-specific recovery
evidence: both CONTROL and DUT were 8 MiB full-flash images, with pre-flash
SHA-256 values
`66027fd84b8e1d20c47e8abf198d772d71a65e09a18ad033e2d812b4dbbc59f0` and
`32bf1bdd8761603d5e61ee1aa59179797d78aa13c869cdc4dcbbc77b3f2e2e68`,
respectively. It records byte-exact restore verification and product boot after
restore as PASS. Those are recovery-chain records, not files contained in the
R1R4 diagnostic ZIP; the diagnostic ZIP must never be labelled as the original
product recovery package.

The current public closeout records do not contain an exact filesystem path for
either binary backup. Therefore a path-specific existence check cannot be
performed from this repository without inventing a path; the backup remains an
explicit physical-preparation requirement. No full backup or credential was
copied or uploaded by this preparation.
