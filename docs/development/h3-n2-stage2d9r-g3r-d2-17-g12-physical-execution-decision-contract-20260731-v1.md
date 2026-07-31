# H3/N2 Stage 2D-9R G3R D2-17 G12 physical-execution decision contract

## Exact boundary

- Base Draft PR: `#246`.
- Exact base HEAD: `0dcf8dd52c7c7bdadef6f81e581bed91a8ab6d6d`.
- Decision: `D1-H3N2-STAGE2D9R-G3R-D2-17-G12-PHYSICAL-EXECUTION-20260731-01`.
- Authorization expiry: `2026-07-31T11:44:35.654243Z`.

## Accepted prerequisites

- G12 static terminal: `432ef9cbe74bb1c688ed7a88192c230b8c0e04ff2361dfe543282245ff9345fa`.
- G12 authorization record: `f670b5f5b637445a09975de1f9e0d23c3eda0d6c8910ec50a4e64a440b8a8963`.
- G12 acceptance binding: `f7bcfce8d3c10f337076fbaba916526fde54f152fda3876e321ab304bdcc37ff`.
- G12 physical-pending binding: `b7b1d4b71e815b28a2bb7468715abcdd5b9977962890f207a36c723122a3c64f`.
- G12 repair lineage: `741fb6de67f9dd0722835827e249c49d0498d1b2b1966c118efd1f183c54e8a6`.
- Physical decision binding: `a97131f4a2e6e42d73992b029a5bf3e9ee3d6ab6778d212fe9ececdfd5fc5ac8`.
- Authorized-pending binding: `85dc4f789e85bbf415955027e4e7eb1bd4933be833a1e940d5842b039d4fd74d`.

## One-shot execution

The operator package may run exactly once before expiry. It revalidates the immutable G12 target-Mac runtime, the exact public acceptance Artifact, the authorization state, target-tool digests, board/serial identity and NVS baseline before inherited claim. The G12 baseline repair creates the unique baseline work directory before inherited `read_flash`, and the terminalizer preserves inherited string subcodes.

Any output, non-zero exit, PASS, FAIL or BLOCKED terminal retires the package. Replay and automatic retry are forbidden. At most one locked recovery restricted to the test partition is allowed only after a destructive-boundary failure.

ACTIVATE, CLEANUP, Ready, merge, release, tag and deployment are forbidden.
