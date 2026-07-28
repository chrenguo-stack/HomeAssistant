# H3/N2 Stage 2D-9R G3R repaired host-only final preflight contract V1

## Frozen inputs

- base Draft PR: `#188`;
- exact base HEAD: `8a6fdd7c74341448d275a4412e36b303d7c95e85`;
- baseline original main: `c16da1a2d4d8300198b0603359eea349a034e2ea`;
- accepted current main after zero-net correction:
  `0229002cc5037f83bc77426f439bdb9e6d63318c`;
- accidental audit commit:
  `61f8db5696c726137952b98825040c4f3a8efd5c`;
- correcting audit commit:
  `0229002cc5037f83bc77426f439bdb9e6d63318c`;
- canonical immutable/recovery Artifact:
  `8676269782` /
  `83eb3cd85e04835eb412dfe9288c3f3445c0b5aefa23dec21532a8500e8fe5b8`;
- final execution binding:
  `387602804793c7ab110817d56aa4c26114632bde31050e95847833f98d83b6c1`;
- consumed baseline result:
  `f3522e98d5c0c8fdf4f5fa2b8486e6c782c7262ae4321e9525471bc0f12cacf4`;
- independently verified baseline public TAR:
  `15849f8a42f0cfa4aa594512dc0928a8ac5e4e3479dc51dfa59390d28c67e0f9`.

The baseline remains bound to the original main. Every final-preflight result
must also bind the accepted current main and explicitly prove the two main
commits have zero net tree difference.

## Review package

CI builds two deterministic copies of a public review package. It includes:

1. the canonical immutable/recovery ZIP without modification;
2. the redacted baseline public TAR;
3. an unauthorized physical-D2 execution package;
4. the frozen successor executor core;
5. the repaired serial-first handshake adapter;
6. a repaired wrapper that binds `tlsvalid03`;
7. a partition-only locked-recovery implementation;
8. a host-only final-preflight probe;
9. a physical-D2 request draft with `authorized=false`.

The physical execution package contains no private command or authorization
record. Its locked recovery is exactly:

```text
read 0x400000 / 0x10000
→ erase_region 0x400000 / 0x10000
→ read 0x400000 / 0x10000
→ require SHA-256 71189f7f...da9063
```

Whole-chip recovery erase and recovery `write_flash` are prohibited.

## Future host-only execution

A later exact `H2-H3N2-STAGE2D9R-G3R-REPAIRED-HOST-FINAL-PREFLIGHT-20260728-01`
authorization may run the host probe once. Before its atomic claim the probe may
only validate the public package and hash the local toolchain. After claim it
may read the existing `tlsvalid03` private custody to verify:

- all required files remain mode `0600`;
- the private-material aggregate remains
  `d2749c4a173876282275e476a577a7e4a27440429b31592c379bdedd1d3bfa0f`;
- the public and private descriptor hashes remain frozen;
- password database, candidate, unlock digest, PREPARE and VERIFY commands
  reconstruct exactly;
- the offline certificate chain, hostname, DER and SPKI bindings remain valid.

The host probe emits hash-only evidence and an unauthorized exact physical-D2
request. Failure consumes the host authorization and cannot be retried.

## Explicit exclusions

This source/CI/Artifact layer does not authorize or perform:

- board connection;
- USB or serial enumeration/open;
- esptool invocation;
- Flash or physical NVS access;
- network or Broker operation;
- PREPARE, VERIFY, ACTIVATE or CLEANUP;
- Ready, merge, release, tag or deployment.

The physical launcher must not be executed until a later exact physical D2
authorization is created, claimed and bound to the final host-preflight result.
