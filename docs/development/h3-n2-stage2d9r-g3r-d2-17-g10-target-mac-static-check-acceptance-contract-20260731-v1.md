# D2-17 G10 target-Mac static-check acceptance contract

## Decision

This add-only public successor accepts the secret-free facts produced by the
G10 target-Mac host-only static check under
`D1-H3N2-STAGE2D9R-G3R-D2-17-G10-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01`.

The accepted terminal record is
`9cbf3a52192df3f0d4ecbb785ea220247e624e0503763d2b417ba01b2cd238cd`. The authorization was created, remains
unclaimed and unconsumed, and expires at `2026-07-31T06:43:11.473014Z`.
The configured runtime validator, identity adapter and marker-digest compatibility
adapter all executed. The outer closure did not call `configure_core()`. All
hardware sentinels and physical-operation flags remained false.

## Bindings

- base PR: #238
- exact base HEAD: `b830358b36491eb698703a259d4697099a1e6076`
- G10 private-delivery binding: `db77e7a90cd2379d245f2bbe4293afede97cf6ac281a82c06fc66e1df1397b92`
- G10 acceptance binding: `a74ef9f82b4339ab3f066804127fdbcd050c0846c44ee44c3d064093215997d3`
- physical-pending binding: `9d4ad3b74f1fdcb2094ad0e93b229b37d5b642ba9f341e3935b43c05dadb9710`
- G09 failure disposition: `3430906e3b3fb7890e2bade085e5c7adb949444005fe421698c640a0913d35f0`
- G10 marker-digest repair binding: `67a59fcfb78a6ad4805ec26239921a80d874a70ed128d9bc155c619aa7c4681e`
- exact repair Artifact: `8782989455`
- exact repair Artifact SHA-256: `2ab42b044e30e9b8f324942bf3c4ac9e4facda98c55c6b8d7c665d9a15ed84ab`

## Boundary

This record authorizes no board, USB, serial, esptool, Flash/NVS, network,
Broker, PREPARE, VERIFY, recovery, ACTIVATE or CLEANUP operation. It creates no
physical decision and stops before claim.

The next explicit gate is
`D1-H3N2-STAGE2D9R-G3R-D2-17-G10-PHYSICAL-EXECUTION-20260731-01`.
Ready, merge, release, tag and deployment remain forbidden.
