# D2-17 G11 preclaim-blocked disposition and forensic contract

## Frozen terminal

The operator returned a canonical terminal with status `BLOCKED_BEFORE_INHERITED_CLAIM`, terminal state `PHYSICAL_DECISION_PRECLAIM_BLOCKED_UNCLAIMED_UNCONSUMED`, failure code `ExecutionError`, and terminal digest `a413862a6bd769d20687a5f4d5b2ebd16a855486c270d22d5a1eeb15d174ddc3`.

Authorization remained unclaimed and unconsumed. The execution crossed the board, USB, serial, esptool and physical-NVS read boundary. It did not erase or write Flash, start a Broker or network operation, execute PREPARE or VERIFY, invoke recovery, ACTIVATE or CLEANUP.

G11 private material, authorization, physical package and runtime are frozen. The package must not be re-extracted or rerun. The authorization must not be reused even though claim and consume remained false.

## Diagnostic limitation

The outer physical driver caught an inherited `ExecutionError` while running the preclaim board baseline, but its public terminalizer retained only the exception class name and discarded the inherited subcode. The public summary therefore cannot distinguish `BASELINE_CHIP_ID_FAILED`, `BASELINE_FLASH_ID_FAILED`, `BASELINE_PARTITION_READ_FAILED` or `BASELINE_STATE_MISMATCH`.

No successor physical package may be created by guessing the missing subcode.

## Next gate

The next gate authorizes only a read-only inspection of metadata already present in the immutable G11 Target Mac runtime. The forensic export must not connect to or query the board, enumerate USB or serial devices, invoke esptool, modify NVS or Flash, start a Broker, access the network, run PREPARE, VERIFY or recovery, or expose local paths or secret values.

The allowed output is a redacted single-line JSON summary sufficient to determine which preclaim baseline stage completed and whether a successor repair is required.

Next gate:

`D1-H3N2-STAGE2D9R-G3R-D2-17-G11-READ-ONLY-PRECLAIM-FORENSIC-EXPORT-20260731-01`
