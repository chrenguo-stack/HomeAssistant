# D2-17 G07 target-Mac static-check acceptance

## Accepted evidence

G07 target-Mac host-only static-check completed with `PASS`. A fresh one-shot
authorization was created but not claimed or consumed. Every board, USB, serial,
esptool, Flash/NVS, Broker, PREPARE, VERIFY, recovery, ACTIVATE and CLEANUP flag
remained false.

The accepted terminal semantic SHA-256 is
`7916d2ac33f9010a215b4f5f8698eb7b4d2c9a833b27aa8697cc2ddf83f2d029`.
The authorization record SHA-256 is
`37fa9803c4ce96083f2b58d4b973c8373326c179d609645f35af1ec72076a601`.

## Contract

The acceptance record binds the exact request and decision IDs, G07 source and
delivery binding, terminal and authorization records, outer and inner launcher
digests, target-tool digests, and the unclaimed/unconsumed authorization state.
The binding is canonical JSON SHA-256 with the binding field removed.

The pending physical decision is not authorization. Physical execution requires:

`D1-H3N2-STAGE2D9R-G3R-D2-17-G07-PHYSICAL-EXECUTION-20260731-01`

## Safety

This public record contains hashes and state only. It contains no authorization
JSON, execution-identity contents, local paths, credentials, private logs or
payload bytes. Ready, merge, release, tag and deployment remain forbidden.
