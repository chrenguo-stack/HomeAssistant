# D2-17 G07 PRECLAIM identity-adapter TypeError repair contract

Decision: `D1-H3N2-STAGE2D9R-G3R-D2-17-G07-PRECLAIM-IDENTITY-ADAPTER-TYPE-CONTRACT-REPAIR-20260731-01`.

## Frozen failure

The exact G07 physical result is `CONSUMED_FAILED_PRECLAIM` with `failure_code=TypeError` and `failure_stage=PRECLAIM`. The inherited executor reports authorization created/claimed/consumed as `true/false/true`; all inherited board, USB, serial, esptool, NVS, network, Broker, Flash, PREPARE and VERIFY flags are false. The earlier outer baseline probe is recorded separately and does not change the inherited PRECLAIM boundary.

G07 is permanently consumed and non-replayable. No G07 package, authorization, marker, runtime or result may be reused.

## Root cause

After `bind_complete_chain`, the D2-11 module global `contract` is the D2-17 execution-identity contract. The frozen D2-11 configured runtime validator still calls:

```python
contract.validate_authorization_contract(value, request, package_root)
```

The D2-17 contract requires the third argument to be the frozen execution-identity dictionary. Supplying a `Path` causes a Python `TypeError` before inherited claim or hardware access.

The previous full-chain static check called the legacy base validator and then the D2-17 contract directly with the identity dictionary. It did not invoke the configured runtime `core.validate_authorization`, so the mismatch was not exercised.

## Repair

The host-only adapter preserves the legacy base validator, then validates the returned authorization with the exact D2-17 request and the already validated execution identity. It replaces both the D2-11 module `configure_core` entry and the handoff entry, is idempotent for the same identity binding, and fails closed on binding drift or missing request state.

The repair does not chmod, rewrite or replace the frozen execution package. It contains no board, USB, serial, esptool, Flash/NVS, network, Broker, PREPARE, VERIFY or recovery operation.

## Successor boundary

Only public add-only code, tests, CI and review Artifact are authorized in this PR. A new G08 private package, target-Mac static check and one-shot authorization require explicit approval of:

`D1-H3N2-STAGE2D9R-G3R-D2-17-G08-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01`
