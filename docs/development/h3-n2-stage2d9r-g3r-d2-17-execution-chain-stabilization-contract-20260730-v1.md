# H3/N2 Stage 2D-9R G3R D2-17 execution-chain stabilization contract

## Status and scope

D2-17 is an add-only public, unauthorized successor stacked on Draft PR #215 exact HEAD
`bea9a5c2af242f0830163ebdfd49c5023a6e437f`. It stabilizes the host-side execution chain only.
It does not authorize a private package, a physical authorization, board access, USB or serial access,
`esptool`, Flash/NVS, Broker startup, PREPARE, VERIFY, recovery, ACTIVATE, CLEANUP, Ready, merge,
release, tag, or deployment.

The public request identifier is:

`D2-H3N2-STAGE2D9R-G3R-EXECUTION-IDENTITY-FROZEN-PREFLIGHT-STABILIZED-PHYSICAL-20260730-17`

It remains unauthorized until a later, separate private-package decision gate.

## D2-16 terminal disposition

D2-16 is permanently `STATIC_CHECK_FAILED_RETIRED`. Its target-Mac host-only check failed before claim,
consume, or any physical boundary. The outer code was
`D2_16_FULL_INHERITED_AUTHORIZATION_PREFLIGHT_CHECK_FAILED`; the preserved first leaf code was
`AUTHORIZATION_IMMUTABLE_PAYLOAD_TAR_SHA256_MISMATCH`.

The D2-16 authorization recorded immutable/recovery payload TAR digests before the full successor chain
was bound. Final binding changed both TAR bytes. The retired package and authorization must not be
executed, rerun, modified, repacked, or reused. The exact evidence is frozen in
`docs/acceptance/h3-n2-stage2d9r-g3r-d2-16-static-check-failure-disposition-20260730-v1.json`.

## Required order

Every public-CI model, future private-package model, and target-Mac model uses the same order:

```text
canonical builder
  -> bind_complete_chain()
  -> verify bind/install idempotency
  -> freeze_execution_identity()
  -> reverify frozen identity
  -> create_authorization_from_frozen_identity()
  -> shell outer
  -> shell launcher
  -> D2-17 wrapper
  -> inherited successor layers
  -> original _BASE_VALIDATE_AUTHORIZATION
  -> stop before claim
```

Authorization creation before complete binding and identity freeze is prohibited and must fail closed.

## Frozen execution identity

The frozen identity includes at least:

- stage, request identifier, authorization schema, and result schema;
- immutable and recovery payload TAR SHA-256 values from final package bytes;
- request, closure, execution-package, and delivery-equivalence bindings;
- canonical outer, launcher, wrapper, contract, builder, and original controller SHA-256 values;
- Python, OpenSSL, esptool, and Mosquitto executable SHA-256 values;
- complete authorization field inventory and its digest;
- bind and install call counts;
- explicit false values for claim, consume, and every physical boundary.

Any post-freeze drift causes `EXECUTION_IDENTITY_DRIFT` or a more specific digest leaf failure.

## Single canonical builder

`h3_n2_stage2d9r_g3r_d2_17_canonical_builder_20260730_v1.py` is the only allowed builder. The builder
accepts a delivery profile but does not change execution bytes, field sources, binding order, argument
order, or digest computation. Public CI, a future private package, and a target-Mac extraction must differ
only in separately governed private material and authorization permissions.

The builder:

1. verifies the exact PR #215 Artifact ZIP and its recursive manifest;
2. copies the inherited package without modifying historical files;
3. adds the D2-17 source and canonical shell entrypoints;
4. freezes a file/mode delivery manifest, closure, package binding, and request;
5. emits two reproducible lanes and a deterministic review TAR;
6. rejects symlinks, Python bytecode, incomplete manifests, unsafe paths, and stale payload bytes.

## Real shell full-chain check

The load-bearing test starts at `run_d2_17_canonical_delivery_outer_20260730_v1.sh`, not at an imported
intermediate function. It uses a path containing spaces and executes the canonical launcher and D2-17
wrapper. The wrapper binds D2-16 through D2-11 and calls the original inherited
`_BASE_VALIDATE_AUTHORIZATION`. Success requires the original validator to return before claim.

## Bind/install idempotency

Within one Python process:

- `bind_complete_chain()` may be called repeatedly;
- the underlying inherited install operation occurs exactly once;
- every repeated call recomputes and compares a binding signature;
- any mutation after the first call fails as `COMPLETE_CHAIN_BINDING_DRIFT`;
- focused tests require three bind calls and one install call.

## Hardware-call sentinels

Host-only validation replaces concrete inherited USB enumeration, serial, esptool, Flash/NVS, Broker,
recovery, process, and network boundaries with fail-closed sentinels. Any unexpected attempt fails
immediately as `UNEXPECTED_PHYSICAL_BOUNDARY_REACHED`. The normal static-check result includes zero
counters and false flags for board, USB, serial, esptool, Flash/NVS, network, Broker, PREPARE, VERIFY,
recovery, ACTIVATE, and CLEANUP.

The sentinels are defense in depth. They do not convert any public test into a physical authorization.

## Leaf error preservation

The result records the original leaf code and stage. Digest failures also record the affected field and the
expected and actual SHA-256 values, without paths or secret preimages. The outer layer must not replace a
specific inherited error with a generic D2-17 failure code.

Required negative regression: tampering only the immutable payload digest in a synthetically generated
host-only authorization, while recomputing its record digest, must reach the original validator and return
`AUTHORIZATION_IMMUTABLE_PAYLOAD_TAR_SHA256_MISMATCH`, with claim/consume false and every physical
flag false.

## Delivery equivalence

CI package, future private-package execution payload, and target-Mac extraction are equivalent only when
they have the same:

- complete file inventory and file SHA-256 values;
- executable/file modes;
- canonical outer, launcher, wrapper, contract, and builder;
- argument order and environment-variable names;
- normalized resolved package root;
- request, closure, package, delivery, and execution-identity bindings.

Two independent builder lanes must be byte-identical. Extraction under a path containing spaces and under
a symlink alias must produce the same delivery-equivalence fingerprint after strict path resolution. The
same synthetic host-only static check must be byte-identical for `public-ci`, `private-package`, and
`target-mac-static-check` delivery profiles.

## Target-Mac and physical gates

A future private-package gate may only create a new D2-17 package and one-shot authorization after exact-
HEAD CI and Artifact verification. The target Mac must then run the complete host-only static check.
No physical decision may be created until that result explicitly reports the original inherited validator,
payload digests, executable digests, request/closure/package binding, delivery equivalence, bind/install
counts, and untouched sentinels as PASS while claim and consume remain false.
