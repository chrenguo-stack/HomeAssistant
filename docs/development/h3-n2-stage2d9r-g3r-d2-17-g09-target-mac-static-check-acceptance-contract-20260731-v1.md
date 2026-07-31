# D2-17 G09 target-Mac static-check acceptance contract

## Decision

This add-only public successor accepts the secret-free facts produced by the
G09 target-Mac host-only static check under `D1-H3N2-STAGE2D9R-G3R-D2-17-G09-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01`.

The accepted terminal record is `14643799387e280f4af7dd0e4b657abe8602548b98f4b5ee2f53fcc7ad7428c0`. The
authorization was created, remains unclaimed and unconsumed, and expires at
`2026-07-31T04:31:11.211315Z`. The configured runtime validator and
the identity-adapter-backed `core.validate_authorization` path both executed.
All physical-operation flags remained false.

## Bindings

- base PR: #234
- exact base HEAD: `bc7e30535dc569a3b82be17f531c39bd9c4dfabf`
- G09 private-delivery binding: `47d9ed8e27cf3df6794de6148a94dbdf0b6724c7bf9104864a6763dcb42ba19c`
- G09 acceptance binding: `e8eda357a8dd6a25855808344ca0ebf44c9932e382c0ec5a308ab29634e6b264`
- physical-pending binding: `03bd4217a0cd8426a78ba79619f3e9bd7e9cb4092082d1e7ae7bd7b6e1cdee15`
- G08 expired-unexecuted disposition: `ad6dcc2ab884a358ae07d90ed157b27f5943757c85898a5440cf06f5b2c12795`

## Boundary

This record authorizes no board, USB, serial, esptool, Flash/NVS, network,
Broker, PREPARE, VERIFY, recovery, ACTIVATE or CLEANUP operation. It creates no
physical decision and stops before claim.

The next explicit gate is `D1-H3N2-STAGE2D9R-G3R-D2-17-G09-PHYSICAL-EXECUTION-20260731-01`. Ready, merge, release, tag and
deployment remain forbidden.
