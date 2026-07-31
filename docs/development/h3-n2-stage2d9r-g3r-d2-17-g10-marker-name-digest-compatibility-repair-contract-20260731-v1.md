# D2-17 G10 marker-name digest compatibility repair

## Scope

This is an add-only, public, host-only successor repair under
`STANDING-D1-PUBLIC-HOST-ONLY-SUCCESSOR-REPAIR-AUTHORIZATION-20260730-01`.
It creates no G10 private material or authorization and performs no board,
USB/serial, esptool, Flash/NVS, network, Broker, PREPARE, VERIFY or recovery
operation.

## Reproduced mismatch

The frozen D2-17 authorization contract stores:

```text
execution_marker_name_sha256 = SHA256(D2_REQUEST_ID)
```

The inherited executor derives:

```text
marker_name = SHA256(D2_REQUEST_ID) + ".json"
required value = SHA256(marker_name)
```

The two values are intentionally distinct inputs and therefore do not match.
The inherited path would fail with `EXECUTION_MARKER_NAME_MISMATCH` after
authorization validation but before claim or hardware access.

## Repair

The compatibility adapter wraps the configured runtime and changes only the
`sha256_bytes()` result for the exact marker filename byte string. It returns
the frozen request-id digest already present in the authorization. The marker
filename, authorization bytes, authorization record digest and every unrelated
digest operation remain unchanged.

The adapter is idempotent for one request identity and fails closed on binding
drift. It composes after the D2-17 execution-identity adapter and before the
inherited executor calls `core.execute()`.

## Required G10 static-check assertions

G10 must verify:

- the exact frozen mismatch is reproducible;
- the compatibility adapter is installed and idempotent;
- the exact marker filename remains unchanged;
- unrelated hash operations remain byte-identical;
- configured authorization validation still passes;
- authorization remains unclaimed and unconsumed;
- every hardware sentinel remains zero;
- execution stops before inherited claim.
