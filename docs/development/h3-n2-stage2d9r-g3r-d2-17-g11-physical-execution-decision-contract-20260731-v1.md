# D2-17 G11 physical-execution decision contract

`D1-H3N2-STAGE2D9R-G3R-D2-17-G11-PHYSICAL-EXECUTION-20260731-01` authorizes exactly one inherited claim, one consume and one frozen D2-17 physical execution using the existing G11 authorization.

The decision binds PR #241 exact HEAD `037f7dbceefb7255cacde4c6fef2a424f1fc69df`, acceptance Artifact `8786628160` (`aa37f736b0adaa0256fd4da66330f9558f4a5eb2472f4628af680f88e0cc7924`), G11 acceptance `f45a7a5865ff383378dd3fd0cbb0a035c600eb3271777a330fc9ceb486f92582`, physical-pending binding `a7b3b259c45ef058111b15e5fbc67ccd0b0fa8474fd1762f3ac5cc483a1d4dfa`, authorization record `fe0e9a997e2e1674d8960a63fb87f1ad23e1dde486dec7639b2209a088b1fc09`, configured-validator evidence `037b39227757f1433dcfe45a4befbeda2f66774621819283f50b79f4d79892d7`, static terminal `308f7c426d7e4be1c7d31d595aa18b1abc79736857f2f730f377c6d48c6ac17c`, G10 expired disposition `eca6986ee9fba51bcd877969a924203fd10f3f5f2954e6be1d1fc2f669282b5b`, G11 reauthorization lineage `db404b7ca1367c2bd5bd6adf82d3060d8ac34c7056e5576907e0e8d77fae7281`, and expiry `2026-07-31T09:41:35.816151Z`.

Before inherited claim, the operator driver verifies the public artifacts, the unique G11 Target Mac runtime, execution identity, authorization, configured validator evidence, tool digests and current expiry. It performs one authorized board/serial/NVS baseline verification. The runtime entry installs both the execution-identity adapter and marker-digest compatibility adapter in the inherited execute process. G11 claim/consume state remains isolated under `authorization-state-g11` in the G11 Target Mac runtime.

Any drift fails closed. The package is one-shot. Replay, automatic retry, ACTIVATE, CLEANUP, Ready, merge, release, tag and deployment are forbidden.
