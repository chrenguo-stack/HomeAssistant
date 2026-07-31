# D2-17 G08 physical-execution decision contract

`D1-H3N2-STAGE2D9R-G3R-D2-17-G08-PHYSICAL-EXECUTION-20260731-01` authorizes exactly one inherited claim, one consume and one frozen D2-17 physical execution using the existing G08 authorization.

The decision binds private source `13da1725a1abef398fec2edf6c053a34911b02d3`, acceptance source `5508344b84189f42fce04721b8a70ba02cb7b933`, acceptance Artifact `8778807759`, authorization record `76e089d31b40b0fefd1fd6613592e9be3d71ae03e1b063d26e7c1701430b46bb`, configured-validator evidence `73b4f52441643b4b7209745abdcb7357dbff16e68c20c780ce5b1ac21e472561`, runtime identity adapter `4b421d626e313a26c4815ef502b6aa76105a8685414ed2be3b4062a0387ef5ff`, and expiry `2026-07-31T01:53:32.629244Z`.

Before inherited claim, the driver verifies all public/private manifests, target tools, authorization state and expiry, execution identity, configured runtime validator evidence, and the authorized board/serial/NVS baseline. The frozen executor is not modified. A content-bound runtime entry imports the frozen chain, installs the verified identity adapter in the same Python process, and then invokes the inherited `execute` command.

Any drift fails closed. Replay, automatic retry, ACTIVATE, CLEANUP, Ready, merge, release, tag and deployment are forbidden.
