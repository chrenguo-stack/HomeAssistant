# G13 Target Mac static-check acceptance contract

This public, add-only contract accepts the operator-returned G13 host-only static-check result.

## Frozen source

- source PR: `#248`
- source HEAD: `89b8a4bf84d6cb236e775055d3427e21dde138e6`
- source Artifact: `8791335916`
- Artifact SHA-256: `6430bac9aeea3961df9f3f29fbd6c882ac25b40786f9313e542fbf2d1511ca17`

## Accepted state

- status: `PASS`
- terminal state: `TARGET_MAC_STATIC_CHECK_PASSED_AUTHORIZATION_UNCLAIMED_UNCONSUMED`
- authorization created/claimed/consumed: `true/false/false`
- terminal record: `7ed21be49a4322b6856b08f1648be4392f68b2bb8e001ddc6873b4ee69b87b14`
- export summary: `125d61749a15603a9d6f8f0cd017bd844e00da7a3a15ae06a6f8439df8c333b4`
- G13 acceptance binding: `80d85d4e44eaeff5f0eaaa979fd34651547f4aa5b055cc2d5ddfe9d46d4ae92a`
- physical-pending binding: `c87b17599c3c7e20182ca2c8ddc5abba0c49d8bfb7cda46bba48f2acf5b1ab03`

The G13 static check validates the existing-empty-real-0700 and missing-directory paths, negative directory cases, bypass of the incompatible G12 wrapper, and claim-state derivation. All hardware sentinels and physical-operation flags remain false.

## Next gate

`D1-H3N2-STAGE2D9R-G3R-D2-17-G13-PHYSICAL-EXECUTION-20260731-01`

This contract authorizes no physical operation. Ready, merge, release, tag, deployment, ACTIVATE and CLEANUP remain forbidden.
