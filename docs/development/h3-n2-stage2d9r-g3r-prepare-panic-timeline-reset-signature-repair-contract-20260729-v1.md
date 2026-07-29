# H3/N2 Stage 2D-9R G3R PREPARE panic timeline and reset-signature repair

Decision: `D1-H3N2-STAGE2D9R-G3R-PREPARE-PANIC-TIMELINE-AND-RESET-SIGNATURE-REPAIR-20260729-01`.

## Frozen predecessor

`D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-08` is permanently `CONSUMED_FAILED` with terminal state `LOCKED_RECOVERY_COMPLETED`, failure code `PREPARE_RESULT_TIMEOUT`, PREPARE count 1, VERIFY count 0, and successful test-partition-only recovery. Replay and automatic retry are prohibited.

## Repair

The serial reader timestamps bytes when they are received, using both UTC and `time.monotonic_ns()`. Capture is partitioned into `startup`, `ready_wait`, `ready_observed`, `post_command`, `late_window`, and `result` phases. Evidence transcription after timeout must not invent event times.

One normalized reset signature is emitted per boot/panic cycle. A signature may contain reset reason, panic class, core, MEPC, RA, Saved PC, hashes of backtrace or stack lines, first and last receipt times, and a deterministic signature digest. One panic report must not expand into many reset timeline events.

Local evidence remains redacted and private. The public review Artifact contains source, synthetic tests, hashes, and contracts only; it contains no real-board panic values or private paths.

## Successor boundary

The review package creates the still-unauthorized request `D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-09`.

PREPARE and VERIFY remain limited to one each. Locked recovery remains test-partition-only and at most once. ACTIVATE, CLEANUP, production operation, Ready, merge, release, tag, and deployment are not authorized.

The immutable payload TAR remains `3a3e96c267fd53723e7cbe6cbce959a90d2bf3f08adedcf97255395f91adc4ea`. The recovery payload TAR remains `08cff687947c2f9b9cbd2df09f16b14b95beeacf2de5683055d6572fafd6cf8f`.
