# N3-W T1 Broker Certificate Lifecycle Repair Design Review — 2026-09-29

Status: `DESIGN_REVIEW_PASS`  
Reviewed design: `docs/development/N3W_T1_BROKER_CERTIFICATE_LIFECYCLE_REPAIR_DESIGN_20260929.md`  
Runtime baseline: `docs/development/N3W_T1_BROKER_CERTIFICATE_LIFECYCLE_RUNTIME_BASELINE_20260929.md`  
Review branch head before this review: `3b6e7d15e5f7ece34c0cc3f3c55c7246b4491d3f`

The review re-read the current T1 ingress/activation source, deployment gate, Manager TLS configuration, node CA delivery path, H0/H1 System CA source, current systemd persistence installer, and the read-only runtime evidence archived for this repair.

## Review results

```text
A1_CURRENT_RUNTIME_AUTHORITY=PASS
A2_SINGLE_FILE_BIND_ROTATION_HANDLING=PASS
A3_SERVER_CA_TRUST_CONTINUITY=PASS
A4_NODE_REPAIRING_AVOIDANCE=PASS
A5_CA_ROLLOVER_SCOPE_SEPARATION=PASS
A6_FAIL_CLOSED_SIGNING_AUTHORITY=PASS
A7_ATOMIC_REPLACE_AND_ROLLBACK=PASS
A8_SYSTEMD_OWNERSHIP_AND_PERSISTENCE=PASS
A9_PUBLIC_SAFE_STATUS_CONTRACT=PASS
A10_HOST_ONLY_TESTABILITY=PASS

DESIGN_BLOCKER_COUNT=0
LIVE_DEPLOYMENT_PRECONDITION_COUNT=1
DESIGN_REVIEW=PASS
```

### A1. Current runtime authority

The design preserves the current accepted authority split:

```text
n3wfc4-broker-ingress-guard.service
→ ingress/firewall owner

n3wfc4-broker-activation.service
→ Broker lifecycle owner

Compose project=n3wfc4
Compose service=broker
Broker Compose restart=no
host TCP/8883 publication=single explicit IPv4 wildcard
```

No new component takes ownership of firewall, Compose topology, Dynamic Security, Manager, Home Assistant or node identity.

### A2. Single-file bind rotation

The active TLS files are single-file bind mounts. An atomic host-side rename alone cannot prove that a running container sees the replacement inode.

The design explicitly requires the existing Broker activation owner to restart/recreate the Broker after atomic certificate replacement and verifies the presented certificate afterward. This closes the main inode-authority hazard.

### A3. Trust continuity

Ordinary renewal keeps the current FC4 private CA unchanged. The active Manager CA and node-facing CA are byte-identical copies of that same logical CA.

Therefore a correctly signed replacement server certificate does not require a node CA update or node re-pairing.

### A4. Re-pairing boundary

No pairing, NODE_ID, MQTT credential, N3-W application-key or peer-trust generation changes are part of renewal. The design correctly treats server-certificate replacement as a transport identity maintenance operation inside an unchanged trust root.

### A5. CA rollover separation

Automatic CA replacement is intentionally forbidden. This is correct because CA rollover requires a separate trust-migration protocol with old/new overlap and node acknowledgement; it must not be hidden inside ordinary server renewal.

The lifecycle repair still monitors FC4 CA and optional System CA expiry so a controlled rollover can begin well before expiry.

### A6. Signing authority

The source repair requires an explicit CA certificate/private-key pair and validates that the public keys match before signing. It also requires enough CA remaining lifetime to cover the entire new server certificate plus a safety margin.

Implementation must use an explicit random positive serial for each new server certificate and must not depend on an unmanaged OpenSSL `.srl` side file.

### A7. Replacement and rollback

The design has distinct pre-mutation, post-replace and post-activation boundaries.

Required implementation ordering is:

```text
validate current authority
→ build and validate candidate
→ preserve old certificate
→ atomic replace
→ restart activation owner
→ verify presented new certificate
→ PASS

post-activation failure
→ restore old certificate atomically
→ restart activation owner
→ verify old certificate
→ rolled-back failure or rollback-unproven
```

This is acceptable and does not claim rollback success from file restoration alone.

### A8. systemd ownership

A separate oneshot + timer is preferable to embedding renewal into Manager runtime or Broker activation startup:

- ordinary Manager execution does not gain CA-private-key access;
- Broker startup does not unexpectedly mutate certificates;
- daily lifecycle checking remains independently observable;
- installation can enable the timer without starting it;
- renewal only restarts the Broker when the renewal threshold is actually reached.

The existing persistence installer can be extended from two enabled units to two services plus one timer while preserving the existing prohibition on `enable --now`.

### A9. Public-safe status

The proposed status schema is sufficient for expiry operations without copying certificate bodies, private keys, credentials, private paths or network locators into durable diagnostics.

Implementation must ensure exception messages and subprocess stderr are normalized before any status JSON is written, so an OpenSSL error cannot accidentally inject a private path into the durable public-safe status document.

### A10. Host-only testability

The repair can be tested without T1 access:

- ephemeral test CA/server material can be generated under pytest temp directories;
- service restart and live TLS probe boundaries can be injected/mocked;
- source tests can prove exact action ordering and rollback semantics;
- static tests can inspect systemd/timer and installer contracts.

## Live deployment precondition

One item remains intentionally unproven by the current read-only evidence:

```text
CURRENT_FC4_CA_PRIVATE_KEY_RUNTIME_AUTHORITY=UNPROVEN
```

The runtime inventory proved the active CA certificate but did not establish the current FC4 CA private-key location, permissions or certificate/key match.

This does not block source repair or host-only testing. It is a hard precondition for any later live automatic-renewal activation. A future live gate must read-only bind the exact CA private-key authority before enabling the timer.

## Implementation refinements frozen by review

The source implementation shall additionally enforce:

- random explicit certificate serial, no unmanaged CA serial side file;
- private temporary workspace mode `0700`;
- candidate and rollback material mode no broader than `0600`;
- target certificate mode/UID/GID preserved across atomic replacement;
- candidate workspace on the same filesystem as the active certificate;
- all subprocess calls use argv arrays, never `shell=True`;
- status output uses normalized reason codes rather than raw subprocess stderr;
- renewal lock prevents concurrent timer/manual runs;
- audit mode never requires or reads the CA private key;
- source tests must prove that healthy/warning audit paths do not invoke signing, restart or replacement.

## Review disposition

```text
DESIGN_REVIEW=PASS
DESIGN_REPAIR_REQUIRED=false
SOURCE_REPAIR_AUTHORIZED_BY_PROJECT_WORKFLOW=true
LIVE_T1_MUTATION=false

NEXT_ONE_GATE=N3W_T1_BROKER_CERTIFICATE_LIFECYCLE_SOURCE_REPAIR_20260929_01
```
