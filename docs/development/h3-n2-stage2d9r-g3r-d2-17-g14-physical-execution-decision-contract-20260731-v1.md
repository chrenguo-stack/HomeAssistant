# H3/N2 Stage 2D-9R G3R D2-17 G14 physical-execution decision contract

## Exact boundary

- Base Draft PR: `#252`.
- Exact base HEAD: `cf759fc64ad60ff672ff0053fee640fda3728c2d`.
- Decision: `D1-H3N2-STAGE2D9R-G3R-D2-17-G14-PHYSICAL-EXECUTION-20260731-01`.
- Authorization expiry: `2026-07-31T15:28:23.051833Z`.

## Accepted prerequisites

- G14 static terminal: `78c532585e1c93cf0bd0489dfbbec310350112d05290b2411516b9fa49235345`.
- G14 authorization record: `47bd58b60acb94ccf3d9e470359936fd8b610987dba99cc81adcddaf09ce1b29`.
- G14 acceptance binding: `44e21d03db295975439c77389f57b89b57e838db74a67c644035822d914adfe4`.
- G14 physical-pending binding: `18b5d0f710ac8cd2bb1c889745795e5820a8df8ffceda0aebe1bb924cb0cc675`.
- G14 repair lineage: `a91a3b699122ee83af663ef2c014115d1db02b28b9aa8890876a810462023d92`.
- G13 consumed disposition: `2c37dcd807731d47c25f7a5b6a2ec0a03add0efc01ee461526cd95f86868915c`.
- Physical decision binding: `4eab159a58853a1e99e9e77d7aa07b6859dfda6136f8c496731946798dd7550d`.
- Authorized-pending binding: `4535ec7283b110b22db62aea26b55c81f0bf4b32ad0562da4898c3ab9c29dd33`.

## One-shot execution

The operator package may run exactly once before expiry. It revalidates the immutable G14 target-Mac runtime, exact acceptance Artifact, authorization state, target-tool digests, board/serial identity and NVS baseline before inherited claim. The inherited executor receives only the byte-equivalent mode-normalized execution view whose directory is mode `0700` and every file is mode `0600`; the frozen canonical execution root remains unchanged. The G13 compatibility adapter remains active for the inherited existing empty real mode-0700 baseline directory and claim-state derivation.

Any output, non-zero exit, PASS, FAIL or BLOCKED terminal retires the package. Replay and automatic retry are forbidden. At most one locked recovery restricted to the test partition is allowed only after a destructive-boundary failure.

ACTIVATE, CLEANUP, Ready, merge, release, tag and deployment are forbidden.
