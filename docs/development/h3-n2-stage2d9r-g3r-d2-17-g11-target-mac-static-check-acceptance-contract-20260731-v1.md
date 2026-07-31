# D2-17 G11 target-Mac static-check acceptance contract

## Decision

This add-only public record accepts the operator-provided G11 Target Mac host-only
static-check export summary. The accepted terminal state is
`TARGET_MAC_STATIC_CHECK_PASSED_AUTHORIZATION_UNCLAIMED_UNCONSUMED`.

The G11 authorization was created with expiry
`2026-07-31T09:41:35.816151Z`; it remains unclaimed and unconsumed. The
configured runtime authorization validator executed, both the execution-identity
adapter and marker-digest adapter were installed, marker compatibility was
verified, and the outer path did not call `configure_core()`.

## Frozen evidence

- Target Mac terminal record: `308f7c426d7e4be1c7d31d595aa18b1abc79736857f2f730f377c6d48c6ac17c`
- authorization file: `18d8ea178ab571e6511c4e7ebad41f483657f10f26b09334a240db4e1ece7687`
- authorization semantic record: `fe0e9a997e2e1674d8960a63fb87f1ad23e1dde486dec7639b2209a088b1fc09`
- execution identity: `9e234234aed566752ab8feb771e4cb84c3946d83857ee13d3d211d6c7e11f00c`
- configured-validator evidence: `037b39227757f1433dcfe45a4befbeda2f66774621819283f50b79f4d79892d7`
- public export summary: `6d0a4c55f2467e544592951dae3f194f0fa4c43c82ccdd5ba15362e2a3e36f4f`
- G11 private-delivery binding: `a488108f42e2a6f0a857aa6e14e7e00b1a1e8c9334e415c28d298890fab92cf2`
- G10 expired-unexecuted disposition: `eca6986ee9fba51bcd877969a924203fd10f3f5f2954e6be1d1fc2f669282b5b`
- G11 successor-pending lineage: `db404b7ca1367c2bd5bd6adf82d3060d8ac34c7056e5576907e0e8d77fae7281`
- exact G10 disposition Artifact: `8786121320`
- exact disposition Artifact SHA-256: `77e9a40adbd97bb2cb4b28557bdd0d179015c19b861b0c46b8aaca1d2ebd869d`

## Boundary

This record authorizes no board, USB, serial, esptool, Flash/NVS, network,
Broker, PREPARE, VERIFY, recovery, ACTIVATE or CLEANUP operation. It creates no
physical decision and stops before inherited claim.

The next explicit gate is
`D1-H3N2-STAGE2D9R-G3R-D2-17-G11-PHYSICAL-EXECUTION-20260731-01`.
Ready, merge, release, tag and deployment remain forbidden.
