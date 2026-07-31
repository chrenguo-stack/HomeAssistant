# D2-17 G14 consumed post-VERIFY failure and G15 forensic-export contract

## Frozen G14 disposition

G14 returned `FAIL / CONSUMED_FAILED` after claim. Flash, PREPARE and VERIFY were
executed, while recovery, ACTIVATE and CLEANUP were not executed.

- terminal record: `45b1aa3438257be87170e68c4308af697f5d6bde468248318fded4fd2e3c97c1`
- physical result: `81dc50c77be871c26b5030cd85bd27c07acd7886a3cd642875a6ab2450c99735`
- authorization marker: `223e4549c3f86c9a02e270f9672ccd056797b2e58175610e1d391ec46693a4f8`
- disposition binding: `23692fe5e7a9a21f8fdaf804cb5b90cc219496f9ac834487f58bf58e35e2d869`

G14 is retired permanently. Replay, retry, authorization reuse, package reuse and
runtime mutation are forbidden.

## Publicly provable diagnosis boundary

`POST_CLAIM_EXECUTION_FAILED` is the terminalization fallback default. The outer
terminal proves that the run reached the post-VERIFY result/terminalization path,
but it does not carry the fallback result's secondary generator failure. Therefore
the exact leaf root cause must not be guessed from the outer terminal.

## G15 host-only forensic export

The G15 source-only exporter reads only allow-listed JSON evidence from the
already terminal G14 runtime:

- the exact outer terminal;
- the exact physical result;
- the consumed authorization marker;
- terminalization guard and locked-recovery terminal records, when present;
- redacted evidence manifests and transport-delivery summaries.

It emits only allow-listed scalar values and hashes. It never emits paths, raw
serial or broker logs, command material, credentials or secrets.

It performs no board, USB, serial, esptool, Flash/NVS, network, Broker, PREPARE,
VERIFY, recovery, ACTIVATE or CLEANUP operation.

## Next exact gate

`D1-H3N2-STAGE2D9R-G3R-D2-17-G15-PRIVATE-FORENSIC-EXPORT-AND-TARGET-MAC-HOST-ONLY-CHECK-AUTHORIZATION-CREATION-20260731-01`

The next gate may create a new private forensic package and execute one host-only
Target Mac check. It does not authorize physical execution or G14 replay.
