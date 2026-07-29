# H3/N2 Stage 2D-9R G3R PREPARE loopTask watchdog root-cause and firmware repair

Decision: `D1-H3N2-STAGE2D9R-G3R-PREPARE-LOOPTASK-WATCHDOG-ROOT-CAUSE-AND-FIRMWARE-REPAIR-20260729-01`.

## Permanent predecessor state

`D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260729-09` is permanently `CONSUMED_FAILED`, failure code `PREPARE_RESULT_TIMEOUT`, terminal state `LOCKED_RECOVERY_COMPLETED`, PREPARE count 1, VERIFY count 0, and successful test-partition-only recovery. Replay and automatic retry are prohibited.

Its realtime evidence recorded nine reset cycles after the PREPARE command. Eight complete cycles share `MEPC=0x4080211c`, `RA=0x4080210a`, `Saved PC=0x4001975a`, and the same reset signature. The diagnostic output identifies the ESP-IDF task watchdog and `loopTask (CPU 0)`.

## Exact symbolication and root cause

The old source `8a6fdd7c74341448d275a4412e36b303d7c95e85` must be rebuilt at the canonical checkout path with ESPHome 2026.4.3 and the original fixed build epoch. The rebuilt application must equal SHA-256 `383463b5a3f4481cf41f8f185c7649a80fd62baf1a6836a69ac3c5047b75950d` before its ELF or map is accepted.

The exact ELF maps MEPC and RA to `esp_cpu_wait_for_intr` in ESP-IDF `esp_hw_support/cpu.c`. The executor calls blocking POSIX `read(STDIN_FILENO, ...)` from its ESPHome `loop()` and handles `EAGAIN`, but the old source never sets `STDIN_FILENO` to `O_NONBLOCK`. After PREPARE reboots into VERIFY-ready state while the host is still waiting for the PREPARE result, no input is available; `loopTask` sleeps in the blocking read until the task watchdog aborts it.

This supersedes the earlier unproven hypothesis that the persistence transaction itself consumed the full watchdog interval.

## Firmware repair

The successor shall:

1. preserve all PREPARE, VERIFY, persistence, authorization, partition, and private-command semantics;
2. set `STDIN_FILENO` to `O_NONBLOCK` before the first executor `loop()` call;
3. verify the resulting descriptor flags and fail closed if nonblocking mode cannot be established;
4. keep the existing `EAGAIN`/`EWOULDBLOCK` no-data path;
5. measure the executor console-loop duration and fail closed after a returned operation exceeds the four-second safety bound;
6. never call a task-watchdog reset/feed/delete/deinit API and never increase the watchdog timeout;
7. retain ELF and map files for every new immutable build lane;
8. include normalized parsing for `Task watchdog got triggered`, the starved task and CPU, `Aborting.`, register-dump CPU, addresses, and complete/incomplete cycles.

## Payload freeze

The old immutable TAR `3a3e96c267fd53723e7cbe6cbce959a90d2bf3f08adedcf97255395f91adc4ea` and old recovery TAR `08cff687947c2f9b9cbd2df09f16b14b95beeacf2de5683055d6572fafd6cf8f` are permanently sealed. They may be copied only as comparison evidence and cannot be modified, rebound, or reused as the repaired successor.

Two independent build lanes must produce a byte-identical new immutable TAR. Two independent recovery lanes must produce a byte-identical new recovery TAR. Both new TAR digests must differ from the sealed predecessors. The review Artifact must retain the new ELF/map and the exact old symbolication evidence.

## Boundary

This decision creates no physical request and no physical authorization. It permits source changes, deterministic compilation, symbolication, tests, CI, and review Artifact creation only. It does not permit board connection, USB enumeration/access, serial access, esptool, Flash/NVS operations, Broker startup, PREPARE, VERIFY, ACTIVATE, CLEANUP, Ready, merge, release, tag, or deployment.
