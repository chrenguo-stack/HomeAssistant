# D2-17 G04 physical-execution decision contract

`D1-H3N2-STAGE2D9R-G3R-D2-17-G04-PHYSICAL-EXECUTION-20260730-01` authorizes exactly one claim, one consume and one frozen D2-17 physical execution using the existing G04 authorization.

Exact bindings: PR #223 HEAD `e58b934c7e00125bf7d7c5a75f6ee338dd5dbdd7`, acceptance Artifact `8762446382`, acceptance binding `747dd09b6d84ae697a9b59127349aabf3046ebb54dc8fd98aef5653bb2479f48`, authorization record `be4fa360d122350cece9bc312bf781be8d9f7879cb08bf2330f5e01e8be612ef`, private-delivery binding `95181293b0efc931718d62a269327ac633cf8e2be81c5dd2a8b8bf4ddc639906`, expiry `2026-07-30T15:24:15.860522Z`.

Before claim, the driver validates decision-package coverage, G04 private-package coverage, target tools, canonical terminal-record semantics, authorization state and expiry, then board/serial/baseline. It invokes the frozen outer once with all inherited launcher variables and evidence-root arguments.

Any drift closes the run. Replay, automatic retry, ACTIVATE, CLEANUP, Ready, merge, release, tag and deployment are forbidden.
