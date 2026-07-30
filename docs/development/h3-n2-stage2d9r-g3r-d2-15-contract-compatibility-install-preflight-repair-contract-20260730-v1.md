# H3/N2 Stage 2D-9R G3R D2-15 contract compatibility and install-preflight repair

## Predecessor terminal disposition

D2-14 is permanently stopped after one authorized outer invocation returned code `1` before producing a physical result. The redacted terminal evidence recorded empty stdout and non-empty stderr. The runtime contained only empty payload/evidence roots and the outer terminal record. No board, USB, serial, esptool, Flash/NVS, Broker, PREPARE, VERIFY, ACTIVATE or CLEANUP operation occurred.

The failure is reproducible at the inherited D2-11 host installation boundary: D2-11 assigns `core.canonical_package_digest = contract.canonical_package_digest`, while the D2-14 contract omitted that compatibility symbol. Python therefore raises `AttributeError` before the physical parser, payload extraction, authorization claim or core execution starts.

D2-14 request, authorization, decision, closure and execution package are non-replayable.

## D2-15 repair

D2-15 is an add-only successor stacked on PR #213 exact HEAD `1d62ba600f68e4dd5e91f0cd63331e85a1d9f95d`.

It:

1. exports `canonical_package_digest(root)` from the current contract and binds it to the current D2-15 execution package;
2. provides a real host-only `install-preflight-check` that executes the inherited D2-11 `install()` path without parsing a physical command or accessing hardware;
3. requires the preflight in unit, shell and CI tests;
4. catches any exception escaping before normal preclaim terminalization and writes a stable result/marker with all physical-operation flags false;
5. preserves D2-14 single-owner payload extraction, empty-root, path-normalization and payload-TAR handoff repairs;
6. creates a new unauthorized request identity. No private authorization is included.

## Safety boundary

The public package does not authorize physical execution. It contains no private paths, credentials or authorization record. It does not connect or enumerate a board, access serial, invoke esptool, modify Flash/NVS, start a Broker, send PREPARE/VERIFY, run recovery, mark a PR Ready, merge, release, tag or deploy.
