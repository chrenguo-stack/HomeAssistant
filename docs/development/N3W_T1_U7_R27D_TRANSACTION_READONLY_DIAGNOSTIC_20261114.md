# N3W T1 U7 R27D Transaction Read-Only Diagnostic — 2026-11-14

## Trigger

The first real R27 post-reboot preflight stopped safely with:

\`\`\`text
status=STOP
reason=Stop:u7_u6_transaction_invalid
transaction_mutation=false
usb_data_mutation=false
service_stop=false
u7_transition=false
\`\`\`

The aggregate R27 error covers multiple independent transaction predicates and
is insufficient to decide whether the live transaction has unsafe semantic
drift or only byte-level provenance drift.

## R27D purpose

R27D is a bounded read-only diagnostic. It does not rerun R26 and does not
relax R27.

It reports, independently:

- phase/status/transaction-id equality;
- exact transaction-file SHA-256 equality;
- target/predecessor verification flags;
- HA backup absence;
- product authorization unclaimed/unconsumed/ID-absent;
- recovery/failure markers;
- safe created/updated timestamps;
- current transaction mtime relative to the current boot epoch;
- canonical SHA-256 of predecessor identity without emitting the identity;
- R26 durable claim/success terminal predicates.

## Boundary

\`\`\`text
R26_REPLAY=false
SOURCE_DEPLOYMENT=false
SERVICE_STOP=false
SERVICE_RESTART=false
USB_DATA_MUTATION=false
TRANSACTION_MUTATION=false
U7_TRANSITION=false
U8_PLUS=false
BOARD_ACCESS=false
MERGE=false
\`\`\`

R27D itself never authorizes source activation or U7 live execution.

## Decision after R27D

If every semantic predicate remains true but only the exact transaction file
SHA-256 differs, the next task is to identify the legitimate writer and decide
whether R27 incorrectly treats whole-file historical byte equality as current
business authority.

If any U6/U9 semantic predicate differs, R27 remains correctly blocked and the
specific drift must be classified before any mutation.
