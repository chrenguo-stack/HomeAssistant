# H3/N2 Stage 2D-9R G3R D2-17 G13 physical-execution decision contract

## Exact boundary

- Base Draft PR: `#249`.
- Exact base HEAD: `f34b3ae551843eae87cb91869e6267ddb9f9c5f0`.
- Decision: `D1-H3N2-STAGE2D9R-G3R-D2-17-G13-PHYSICAL-EXECUTION-20260731-01`.
- Authorization expiry: `2026-07-31T13:54:24.915627Z`.

## Accepted prerequisites

- G13 static terminal: `7ed21be49a4322b6856b08f1648be4392f68b2bb8e001ddc6873b4ee69b87b14`.
- G13 authorization record: `5eb016ae2ac929dcb5d407aaf16a1ffdbdffea743a60a376d244be03b398c75a`.
- G13 acceptance binding: `80d85d4e44eaeff5f0eaaa979fd34651547f4aa5b055cc2d5ddfe9d46d4ae92a`.
- G13 physical-pending binding: `c87b17599c3c7e20182ca2c8ddc5abba0c49d8bfb7cda46bba48f2acf5b1ab03`.
- G13 repair lineage: `6b55377ca34d2c71e9653ef1708ce4ad8a2c06ef5b936b7c2ce1e715561ae596`.
- G12 consumed disposition: `bbc16258410a53363349c7b71323f0b7fcb33548f561dfa3b0dc71be5fcb7bc3`.
- Physical decision binding: `313280a26f193a36fbb4c4af5bbcb9af953cbf8551d16c4145b823849b5cf6b5`.
- Authorized-pending binding: `af5e0918ab2f20effbf8e33d259208156b41992bef054c59a81fc92529a770a4`.

## One-shot execution

The operator package may run exactly once before expiry. It revalidates the immutable G13 target-Mac runtime, exact acceptance Artifact, authorization state, target-tool digests, board/serial identity and NVS baseline before inherited claim. The G13 compatibility adapter accepts the inherited existing empty real mode-0700 TemporaryDirectory, bypasses the incompatible G12 wrapper, and derives claim state from CLAIMED/CONSUMED markers.

Any output, non-zero exit, PASS, FAIL or BLOCKED terminal retires the package. Replay and automatic retry are forbidden. At most one locked recovery restricted to the test partition is allowed only after a destructive-boundary failure.

ACTIVATE, CLEANUP, Ready, merge, release, tag and deployment are forbidden.
