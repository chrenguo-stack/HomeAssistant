# FC4 Board-C P9 Setup-Secret Capture Authority Recovery (2026-08-28)

Status: `SOURCE_GUARDED_PHYSICAL_VALIDATION_PENDING`

This archive records the host-only guard for first-registration setup-secret
capture. It does not authorize or perform board, USB, serial, runtime, broker,
Home Assistant, database, or setup-secret operations.

## Risk and boundary

Opening a pySerial port can apply RTS/DTR control-line state. On ESP32-C6
hardware that transition may reset the board before the capture window is
observed. The capture executor therefore treats reset avoidance as unproven.

The executor now constructs the serial object closed, disables hardware flow
control (`rtscts=false`, `dsrdtr=false`), deasserts DTR and RTS, and opens
once only after those settings are applied. A caller must explicitly
acknowledge live serial-open risk; the default invocation fails before any
serial object is opened. No retry is permitted.

The public output contains only status and hashes. Pairing identifiers, setup
secrets, private locators, and raw payloads are never printed. Normal capture
still requires exact hardware identity and pairing-id hash binding and writes a
new exclusive mode-0600 handoff under a private parent.

## Verification contract

Host tests cover closed construction, pre-open control-line state, disabled
flow control, the acknowledgement gate, zero-open output/identity guards,
single-open capture, secret-safe output, and backward-compatible exact-pairing
capture. These tests model the control-line transitions that the previous
double omitted.

`SERIAL_CONTROL_LINE_POLICY=PRECONFIGURED_DEASSERTED_BEST_EFFORT` is an
implementation policy, not proof that opening cannot reset hardware.
`SERIAL_OPEN_NO_RESET_PROVEN=false` remains explicit. Physical validation is
pending and must use a separately authorized, prepared route; this change
performs no physical execution.

Any future authority-recovery mode must require exact board identity and a
valid 32-byte secret, write a private exclusive 0600 artifact, and mark the
result `NON_CURRENT_TRANSACTION_AUTHORITY`; it must never silently reuse an
old pairing as current authority.
