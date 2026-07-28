# H3/N2 Stage 2D-9R G3R repaired U1 host preauthorization contract V1

## Purpose

This layer converts the frozen public `tlsvalid03` U1 source review into a host-specific, still unauthorized decision request. It validates the public package, hashes the exact host toolchain, and checks only whether the uniquely selected private custody root is absent and structurally safe for a later one-shot generation.

It does not generate any private material and does not create, claim, or consume a U1 authorization.

## Frozen inputs

- Base PR: #186.
- Base HEAD: `2ed70e3292e5b6522ac3a5bc279c94535cd7b784`.
- Public U1 review Artifact ID: `8672973249`.
- Public U1 review Artifact SHA-256: `c493c4464935ecbf2f71952ebadfcbab28c9f9d1cf5203afb4350fc95bb31b50`.
- Inner deterministic tar SHA-256: `4fd6ed8d359e49583229ab4068312bdca9e15a0d422097d3c5a5ac16bd46b8fb`.
- Upstream review binding SHA-256: `ccc25531d868bd09f66f4d98cb907c0272408edee97f2700e818274a1a0efd3c`.
- Material source SHA: `2ed70e3292e5b6522ac3a5bc279c94535cd7b784`.
- Main SHA: `c16da1a2d4d8300198b0603359eea349a034e2ea`.
- Repair source binding: `0a2c96b7615d9f222cf72fcf899b6caf3a7c875f`.
- Run suffix: `tlsvalid03`.

The host-preflight source is a new layer above the material source. It must not change the frozen generator, private-material contract, command protocol, repaired host controller, or other upstream source inventory.

## Read-only host probe

The explicit host probe may perform only these actions:

1. Read and hash the public host-preflight review package.
2. Validate the deterministic tar inventory and metadata.
3. Validate the frozen upstream source inventory byte-for-byte.
4. Resolve regular, non-symlink executables for Python, OpenSSL, and `mosquitto_passwd`.
5. Run only version/help commands for OpenSSL and `mosquitto_passwd`.
6. Hash those executables and the frozen generator/contract/protocol files.
7. Derive the custody-root digest from the fixed selection rule.
8. Check only that the exact `tlsvalid03` custody root does not exist.
9. If its parent exists, check only that it is a regular directory with mode `0700`.
10. Emit an `authorized=false` request carrying public digests and no absolute private path.

The probe must not read a private material file, enumerate custody directory contents, create a directory, write a marker, or modify permissions.

## Request semantics

A successful host probe produces:

- state `HOST_PREFLIGHT_PASS_AWAITING_EXACT_U1_DECISION`;
- exact material source SHA and host-preflight source SHA;
- exact public package bindings;
- generator, contract, chain-contract, protocol and executable SHA-256 values;
- tool versions;
- custody-root digest and parent metadata;
- a canonical `request_binding_sha256`;
- `authorization_id=null`, `issued_at=null`, `expires_at=null`;
- `authorized=false`.

The output is not an authorization record and cannot be passed to the private-material generator as one. A later exact operator decision must independently choose the authorization ID and validity window and bind every host field.

## Fail-closed conditions

The host probe fails if any package member, source digest, package binding, tool executable, custody selection rule, custody-root state, parent mode, or request field differs from the contract. Failure does not permit automatic retry with changed inputs; changed inputs require a new reviewed package or decision.

## Explicit exclusions

This layer does not authorize or perform:

- secret, key, certificate, password, command, or private descriptor generation;
- private custody writes;
- authorization creation, claim, or consumption;
- board connection or USB/serial enumeration;
- esptool, Flash, NVS, erase, or readback;
- network or Broker startup;
- PREPARE, VERIFY, ACTIVATE, or CLEANUP;
- Ready, merge, release, tag, or deployment.

The retired physical D2 remains permanently `CONSUMED_FAILED / LOCKED_RECOVERY_COMPLETED` and non-replayable.
