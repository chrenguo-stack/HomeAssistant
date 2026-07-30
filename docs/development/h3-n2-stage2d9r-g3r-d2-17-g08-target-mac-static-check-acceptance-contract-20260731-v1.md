# D2-17 G08 target-Mac static-check acceptance contract

Decision `D1-H3N2-STAGE2D9R-G3R-D2-17-G08-TARGET-MAC-STATIC-CHECK-ACCEPTANCE-20260731-01` accepts the secret-free terminal facts from the one-shot G08 host-only static check.

The accepted result is bound to private source `13da1725a1abef398fec2edf6c053a34911b02d3`, private-delivery binding `de29e81f317c09a8ca6c330e35ae492f10408ff3f2e42e1f0587b0f228c366e6`, terminal record `18557a68c6be29710bc65d681b7aa83ff293835acf7389cbebf0e23d5fca297b`, authorization record `76e089d31b40b0fefd1fd6613592e9be3d71ae03e1b063d26e7c1701430b46bb`, and execution identity `9e234234aed566752ab8feb771e4cb84c3946d83857ee13d3d211d6c7e11f00c`.

G08 additionally proves that the runtime identity adapter was installed and the real configured `core.validate_authorization` path executed successfully. The configured-validator result and file are bound by SHA-256, and all board, USB, serial, esptool, Flash/NVS, network, Broker, PREPARE, VERIFY, recovery, ACTIVATE and CLEANUP flags remain false.

The accepted authorization is created but unclaimed and unconsumed. This acceptance does not authorize physical execution. The only next decision gate is `D1-H3N2-STAGE2D9R-G3R-D2-17-G08-PHYSICAL-EXECUTION-20260731-01`.

Ready, merge, release, tag and deployment remain forbidden. Any source, binding, terminal, authorization, identity, configured-validator, tool or expiry drift fails closed.
