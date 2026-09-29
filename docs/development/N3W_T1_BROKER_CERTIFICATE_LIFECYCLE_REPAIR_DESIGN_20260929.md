# N3-W T1 Broker Certificate Lifecycle Repair Design — 2026-09-29

Status: `DESIGN_COMPLETE_PENDING_REVIEW`  
Baseline authority: `docs/development/N3W_T1_BROKER_CERTIFICATE_LIFECYCLE_RUNTIME_BASELINE_20260929.md`  
Repair branch: `fix/n3w-t1-broker-certificate-lifecycle-20260929`  
Branch base: `main=60c05ada52c48a58243f666b3e631fd228c53df4`

## 1. Problem statement

The current production TLS chain is healthy, but certificate lifecycle handling is incomplete.

Confirmed current expiry authority:

```text
BROKER_SERVER_CERT_NOT_AFTER=2028-11-22T04:18:40Z
FC4_PRIVATE_CA_NOT_AFTER=2036-08-17T04:18:39Z
SYSTEM_CA_NOT_AFTER=2036-07-30T15:32:24Z

BROKER_SERVER_CERTIFICATE_RENEWAL_AUTOMATION=NOT_IMPLEMENTED
CERTIFICATE_EXPIRY_ALERTING=NOT_IMPLEMENTED
CA_ROLLOVER_AUTOMATION=NOT_IMPLEMENTED
```

The first repair target is ordinary Broker server-certificate renewal and expiry observability. CA replacement is intentionally not treated as ordinary renewal.

## 2. Existing source/runtime constraints

The design preserves the existing accepted T1 architecture:

- Compose project identity remains `n3wfc4`.
- Broker Compose service remains `broker`.
- Broker TCP/8883 publication remains exactly one explicit IPv4 wildcard publication.
- Broker Compose restart policy remains `no`.
- `n3wfc4-broker-ingress-guard.service` remains the ingress owner.
- `n3wfc4-broker-activation.service` remains the Broker lifecycle owner.
- Manager remains on its existing host-network TLS client path.
- The Broker certificate, CA certificate and server key are current single-file bind mounts.
- Ordinary node trust uses the same FC4 private CA as the Broker.
- Existing paired nodes must not be re-paired merely because the Broker server certificate renews.

A critical existing guard applies: replacing a host-side file that is individually bind-mounted can create a new inode while a running container continues to see the old inode. Therefore an atomic host-side certificate replacement is not sufficient by itself. The Broker must be recreated/restarted through the existing activation owner before the new certificate is considered active.

## 3. Repair scope

V1 source repair SHALL implement:

1. a repository-versioned host tool that audits the Broker server certificate and active FC4 CA;
2. deterministic expiry states and machine-readable status;
3. automatic server-certificate renewal when the renewal threshold is reached;
4. fail-closed validation of the CA certificate/private-key pair before signing;
5. reuse of the existing Broker server private key in V1;
6. atomic candidate-certificate validation and replacement;
7. Broker restart through the existing `n3wfc4-broker-activation.service`;
8. post-restart TLS verification against loopback TCP/8883 with the configured TLS server name;
9. automatic certificate rollback plus a second Broker restart if post-activation TLS verification fails;
10. a daily systemd timer and oneshot service;
11. durable public-safe status JSON containing dates, remaining lifetime, fingerprints and action/result, but never certificate/private-key bodies or private paths;
12. warning/renewal/critical lifecycle states for the active FC4 CA;
13. optional read-only monitoring of the H0/H1 System CA;
14. host-only tests covering the full renewal and rollback state machine.

V1 SHALL NOT:

- replace or automatically regenerate the FC4 private CA;
- replace or automatically regenerate the H0/H1 System CA;
- change node trust anchors;
- rotate MQTT credentials or N3-W keys;
- rotate the Broker server private key;
- change the Broker hostname/TLS server-name policy;
- change Broker publication, firewall, Compose network topology, Dynamic Security or Home Assistant configuration;
- mutate a live T1 merely because this source repair is merged.

## 4. Lifecycle policy

Frozen V1 defaults:

```text
SERVER_CERT_VALIDITY_DAYS=825
SERVER_CERT_WARNING_DAYS=90
SERVER_CERT_RENEW_DAYS=60
SERVER_CERT_CRITICAL_DAYS=30

CA_WARNING_DAYS=730
CA_CRITICAL_DAYS=365
CA_RENEWAL_MODE=MANUAL_CONTROLLED_ROLLOVER

SYSTEM_CA_WARNING_DAYS=730
SYSTEM_CA_CRITICAL_DAYS=365
SYSTEM_CA_RENEWAL_MODE=MANUAL_CONTROLLED_ROLLOVER

AUTO_RENEW_CHECK_CADENCE=DAILY
```

The thresholds are policy values, not assumptions about the current date. Tests must use injected/frozen time.

Server-certificate renewal is allowed only when the signing CA remains valid long enough to cover the complete new server-certificate lifetime plus a safety margin:

```text
MIN_CA_REMAINING_FOR_SERVER_RENEWAL_DAYS
  = SERVER_CERT_VALIDITY_DAYS + CA_SIGNING_SAFETY_MARGIN_DAYS

CA_SIGNING_SAFETY_MARGIN_DAYS=90
```

If this condition is not met, automatic server renewal fails closed with `ca_rollover_required`. It must not silently issue a certificate that outlives the trusted CA.

## 5. Host tool

Add:

```text
tools/n3w_broker_certificate_lifecycle.py
```

The tool SHALL use Python standard-library orchestration plus the host `openssl` CLI. It must not require the greenhouse-manager Python environment or import production Manager code.

Primary modes:

```text
audit
auto-renew
```

`audit` is read-only.

`auto-renew` remains read-only while the server certificate has more than the configured renewal threshold remaining. Once renewal is required it enters the mutation state machine below.

All certificate/key paths, TLS server name, status path and activation-unit name are explicit inputs. No private production path is hard-coded in repository source.

## 6. Pre-renewal fail-closed checks

Before any candidate write or service action:

1. required files exist and are regular non-symlink files;
2. certificate/key path parents satisfy the configured safety root;
3. current server certificate parses;
4. FC4 CA certificate parses and has `CA:TRUE`;
5. current server certificate verifies against the supplied FC4 CA;
6. current server certificate verifies for the configured TLS server name;
7. current server certificate public key matches the current server private key;
8. FC4 CA certificate public key matches the supplied FC4 CA private key;
9. FC4 CA has enough remaining lifetime for a complete V1 server certificate plus the safety margin;
10. existing target certificate metadata, mode, UID and GID are captured for exact restoration;
11. the current Broker activation unit is active before renewal;
12. a pre-change loopback TLS probe succeeds and presents the current expected certificate.

Any failure before mutation returns a nonzero result and leaves the certificate and Broker untouched.

## 7. Candidate generation

V1 intentionally reuses the current Broker server private key. The candidate certificate is generated from that key and signed by the same FC4 private CA.

Required candidate properties:

- same configured TLS DNS server name;
- SAN contains that DNS name;
- server authentication extended key usage;
- non-CA basic constraints;
- SHA-256 signature;
- validity no longer than 825 days;
- issuer matches the configured FC4 CA;
- public key matches the current server key.

The candidate is generated in a private temporary directory. CSR/candidate/temp files are never written into GitHub or public evidence.

The candidate must pass the same chain/hostname/key checks before the active certificate path is touched.

## 8. Replacement and single-file bind handling

Replacement sequence:

```text
validated candidate
→ preserve exact old certificate bytes + metadata in private rollback workspace
→ write candidate to same filesystem
→ fsync candidate
→ set target mode/uid/gid
→ atomic os.replace(candidate, active-server-cert)
→ fsync parent directory
→ restart n3wfc4-broker-activation.service
→ verify new loopback TLS endpoint
```

The service restart is mandatory because the active Broker certificate is currently a single-file bind mount.

The renewal tool must not restart Manager or Home Assistant.

## 9. Post-activation verification and rollback

Post-activation success requires all of the following:

```text
BROKER_ACTIVATION_UNIT_ACTIVE=true
TLS_LOOPBACK_HANDSHAKE=PASS
TLS_CA_VERIFY=PASS
TLS_SERVER_NAME_VERIFY=PASS
PRESENTED_CERT_EQUALS_NEW_CERT=true
PRESENTED_CERT_NOT_AFTER_EQUALS_NEW_CERT=true
```

If any post-activation condition fails:

```text
restore preserved old certificate atomically
→ restart Broker activation again
→ verify old certificate through loopback TLS
```

If rollback verification succeeds, the operation reports `renewal_failed_rolled_back`.

If rollback verification cannot be proven, the operation reports `rollback_unproven`, exits nonzero, preserves all private recovery material, and must not claim runtime recovery.

## 10. Status and expiry warning contract

Default durable status location is configured outside the repository and must be under a root-owned private directory.

Status JSON contains only public-safe fields such as:

```text
schema
checked_at
server_not_after
server_remaining_seconds
server_state
server_sha256_fingerprint
ca_not_after
ca_remaining_seconds
ca_state
ca_sha256_fingerprint
system_ca_not_after
system_ca_remaining_seconds
system_ca_state
action
result
renewal_attempted
rollback_attempted
```

It must not contain:

- PEM bodies;
- private-key data;
- MQTT credentials;
- private network addresses;
- private absolute certificate/key paths;
- raw system-private identifiers.

State normalization:

```text
HEALTHY
WARNING
RENEW_DUE
CRITICAL
EXPIRED
CA_ROLLOVER_REQUIRED
INVALID
```

## 11. systemd integration

Add:

```text
infra/n3w-t1/systemd/n3wfc4-broker-certificate-lifecycle.service
infra/n3w-t1/systemd/n3wfc4-broker-certificate-lifecycle.timer
infra/n3w-t1/broker-certificate-lifecycle.env.example
```

The oneshot service calls the repository-versioned installed tool in `auto-renew` mode.

The timer runs daily with bounded randomized delay. It must use `Persistent=true` so a missed powered-off interval is checked after the next boot.

The service must not use `Restart=always`. A failed renewal remains visible as a failed oneshot and is retried by the next scheduled timer or explicit operator action.

The existing persistence installer is extended to enable the timer without using `enable --now`. Installing source must not itself trigger a certificate check, restart or live renewal.

## 12. Deployment/environment contract

The private lifecycle environment file SHALL provide logical inputs equivalent to:

```text
N3WFC4_CERT_SERVER_CERT_FILE
N3WFC4_CERT_SERVER_KEY_FILE
N3WFC4_CERT_CA_CERT_FILE
N3WFC4_CERT_CA_KEY_FILE
N3WFC4_CERT_SERVER_NAME
N3WFC4_CERT_STATUS_FILE
N3WFC4_CERT_SYSTEM_CA_FILE
N3WFC4_CERT_ACTIVATION_UNIT
N3WFC4_CERT_PROBE_HOST
N3WFC4_CERT_PROBE_PORT
```

Repository example values must use non-production placeholders only.

The private CA-key path is required for `auto-renew` when renewal becomes due. Its absence during a renewal-due state is a hard fail-closed condition. Audit mode may operate without the private key.

## 13. Source tests

Add focused tests for at least:

- healthy certificate: audit only, no mutation;
- warning window: status warning, no renewal;
- exactly-at-renew threshold;
- critical window;
- expired server certificate;
- malformed certificate;
- hostname mismatch;
- wrong server private key;
- wrong CA private key;
- non-CA signing certificate;
- insufficient CA remaining lifetime;
- candidate chain mismatch;
- candidate SAN mismatch;
- candidate validity exceeds policy;
- candidate write failure before replace;
- service restart failure after replace;
- post-restart endpoint still presenting old certificate;
- post-restart CA verification failure;
- successful rollback;
- rollback restart failure;
- rollback verification failure remains `UNKNOWN/UNPROVEN`;
- status JSON public-safety contract;
- no PEM/private-key body in stdout/status;
- system CA monitoring only, never automatic rollover;
- systemd unit/timer static contract;
- persistence installer enables the timer but never starts it;
- no regression to existing ingress-guard/activation unit ordering and Broker deployment gate.

## 14. Live validation boundary

Source CI success will not prove live renewal.

A later live gate, requiring explicit live-mutation authorization, must independently bind:

- exact T1 runtime;
- exact active server certificate/CA/key authority;
- the actual FC4 CA private-key authority;
- exact Broker activation unit and Compose authority;
- private rollback snapshot;
- pre/post Manager TLS MQTT continuity;
- Broker/Dynamic Security/HA continuity;
- no node re-pairing and no node trust-anchor change.

No live T1 certificate mutation is part of this source-repair gate.

## 15. Design disposition

```text
DESIGN_SCOPE=SERVER_CERT_RENEWAL_PLUS_ALL_CERT_EXPIRY_MONITORING
SERVER_KEY_ROTATION=DEFERRED
FC4_CA_AUTO_REPLACEMENT=FORBIDDEN
SYSTEM_CA_AUTO_REPLACEMENT=FORBIDDEN
NODE_REPAIRING_REQUIRED=false
BROKER_RESTART_REQUIRED_ON_RENEWAL=true
MANAGER_RESTART_REQUIRED=false
HOME_ASSISTANT_RESTART_REQUIRED=false
LIVE_MUTATION=false

NEXT_ONE_GATE=N3W_T1_BROKER_CERTIFICATE_LIFECYCLE_REPAIR_DESIGN_REVIEW_20260929_01
```
