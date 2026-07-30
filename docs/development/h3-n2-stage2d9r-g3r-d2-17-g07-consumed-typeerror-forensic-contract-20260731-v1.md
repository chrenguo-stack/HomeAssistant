# D2-17 G07 consumed TypeError forensic closure

## Frozen terminal

G07 is permanently closed as an authorization-consumed failure. The observed terminal record is semantically bound by `e3ec66f159fa2e2c24c15df3896d7004e147ac97ab853015c8c4aa4475f55fb4` and reports `TypeError`, `authorization_consumed=true`, no replay, and no automatic retry.

Board enumeration, serial access, esptool invocation and NVS baseline reading occurred. Flash, Broker startup, PREPARE, VERIFY, recovery, ACTIVATE and CLEANUP did not occur.

## Safety boundary

The G07 private package, authorization, physical package, runtime, physical result, terminal and markers must not be replayed, edited, moved, repacked or reused. A successor physical attempt must use a new generation and a new authorization after a separate explicit gate.

## Forensic requirement

The public terminal does not expose the inherited `failure_stage`. The companion tool validates the terminal semantic digest and can read the frozen physical-result file, verify its exact SHA-256, and emit only a fixed non-secret whitelist. It never accesses the board, USB, serial, esptool, Broker or payload contents.

## Current decision

`D1-H3N2-STAGE2D9R-G3R-D2-17-G07-CONSUMED-TYPEERROR-FORENSIC-CLOSURE-20260731-01` authorizes public add-only forensic records, host-only static analysis, whitelist extraction support, tests and CI. It does not authorize a successor private package or physical execution.
