# N3-W T1 F4 Factory Acceptance and Activation Source Repair Progress — 2026-10-15

```text
TASK=N3W_T1_F4_FACTORY_ACCEPTANCE_AND_ACTIVATION_SOURCE_REPAIR_20261015_01
STATUS=CLOSED_PASS_INDEPENDENT_REVIEW

BASE_MAIN=b12c69be5c1d1d61887e9be4a776f575141d44c6
LIVE_PRODUCT_RELEASE_ID=6ac82ae0872b05644e59470ffef7307dad14d359
LIVE_PRODUCT_STATE=DEVICE_READY

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
```

## 1. Source repair result

The source repair implements the missing F3 → F4 control boundary without replaying provisioning and without
starting any real production service.

New top-level host authority:

```text
tools/n3w_t1_f4_activation_host.py
```

Command surface:

```text
status
audit
eligibility --phase inspect|broker|services|certificate
prepare --authorization-id <exact> --confirm "PREPARE F4 ACTIVATION: YES"
activate --authorization-id <same exact id> --confirm "START F4 ACTIVATION: YES"
```

No command can invoke `n3w-t1-provision start`. The F4 host calls provisioning `verify` only.

## 2. Factory acceptance ownership

The F4 host now owns the first secure creation of:

```text
/var/lib/n3w-t1-provisioning/F4_ACTIVATION_TRANSACTION.json
/var/lib/n3w-t1-provisioning/FACTORY_ACCEPTED.json
```

The one-shot transaction is claimed before the first F4 mutation. It is exact-bound to:

```text
authorization_id
release_id
host_instance_id
system_id
system_id_sha256
```

The factory-acceptance record uses the already-frozen schema:

```text
gh.n3w.t1-factory-accepted/1
```

and is created only after a fresh stopped-state audit re-verifies the current live DEVICE_READY host.

Both records use root-owned mode-0600 private records. New-record creation is fail-closed and does not overwrite
an existing record.

F4 `prepare` and `activate` are also serialized through an exclusive non-blocking host lock so concurrent
operators cannot both enter the mutation path.

## 3. Phase-locked activation guard

Direct systemd start is no longer sufficient to bypass the F4 owner.

Fresh-route F4 unit variants are introduced under:

```text
infra/n3w-t1/f4/
```

They are installed onto the existing canonical runtime unit names only by F4 preparation.

Broker activation requires:

```text
transaction stage=BROKER_STARTING
FACTORY_ACCEPTED exact
DEVICE_READY current-host verify PASS
```

Manager/Home Assistant activation requires:

```text
transaction stage=SERVICES_STARTING
FACTORY_ACCEPTED exact
DEVICE_READY current-host verify PASS
Broker authenticated readiness PASS
```

Certificate auto-renew requires:

```text
transaction stage=RUNTIME_ACCEPTED or PERSISTENCE_ENABLED
```

Therefore directly starting Services from PREPARED cannot transitively bypass the top-level F4 sequence.

The historical shared activation/certificate unit sources remain byte-for-byte unchanged. The new lifecycle
contract is isolated to the fresh-route F4 package rather than silently changing prior runtime authorities.

## 4. Activation package boundary

F4 `prepare` installs only the later production-control material while services remain stopped and disabled:

```text
/usr/local/sbin/n3w-t1-f4-activation
/usr/local/sbin/n3w-t1-broker-authenticated-readiness
/usr/local/sbin/n3w-broker-certificate-lifecycle

/etc/systemd/system/n3wfc4-broker-activation.service
/etc/systemd/system/n3wfc4-services-activation.service
/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service
/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer

/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
/etc/n3wfc4/docker-compose.yml
/etc/n3wfc4/broker-activation.env
/etc/n3wfc4/broker-certificate-lifecycle.env
```

The Compose runtime source is copied from the exact already-deployed fresh release, not from a newer generic
repository Compose file. This preserves the real release's exact Manager image binding.

Installation does `daemon-reload` only. It does not enable or start Broker, Manager, Home Assistant or the
certificate timer.

## 5. Fresh per-device certificate lifecycle binding

The new F4 package no longer relies on the historical fixed certificate fingerprints.

The fresh binding is derived from the current provisioned T1:

```text
Broker CA cert=/etc/n3wfc4/tls/ca.pem
Broker server cert=/etc/n3wfc4/tls/server.pem
Broker server key=/etc/n3wfc4/tls/server.key
Broker CA private key=/opt/greenhouse-secrets/broker-ca/ca.key
System CA=/var/lib/greenhouse-manager/identity/system-ca.pem
TLS server name=armbian
```

Before installation, source verifies:

- exact file type/owner/mode/link-count expectations;
- Broker CA certificate/private-key match;
- Broker server certificate/private-key match;
- server certificate chain and hostname verification.

The fresh lifecycle service has a separate secret-root allowlist for the Broker CA private key.

No CA or server-certificate replacement occurs in this source gate.

## 6. Runtime activation ownership

The new `activate` path is intentionally bounded:

```text
PREPARED
→ start/verify ingress guard
→ BROKER_STARTING
→ Broker systemd start
→ authenticated MQTT readiness
→ BROKER_READY
→ SERVICES_STARTING
→ Manager + Home Assistant start
→ exact running service set
→ RUNTIME_STARTED
→ STOP
```

It does not enable reboot persistence and does not enable the certificate timer.

If runtime start fails, the host attempts to stop Services and Broker and records either:

```text
STOPPED_RUNTIME
```

or:

```text
STOPPED_RUNTIME_ROLLBACK_UNPROVEN
```

depending on the observed post-rollback service state. Blind replay is forbidden.

## 7. Deliberately still outside this source gate

This repair does not yet declare `RUNTIME_STARTED` to be fully accepted.

The following remain separate source/live gates:

```text
detailed Broker TLS/ACL negative-client acceptance
Manager MQTT/canonical/empty-business-state runtime acceptance
Home Assistant MQTT bootstrap/integration continuity acceptance
RUNTIME_ACCEPTED durable transition
production persistence enablement
certificate lifecycle first read-only audit
certificate timer enablement
reboot persistence acceptance
board pairing / USB / serial / Flash / NVS / RF
```

This keeps service start separate from the later decision that the complete production runtime is accepted.

## 8. Tests and CI

Added:

```text
tests/tools/test_n3w_t1_f4_activation_host.py
.github/workflows/n3w-t1-f4-activation-source-ci.yml
```

Focused tests cover:

```text
no provisioning start replay
exact factory binding
phase-locked Broker/Services/certificate eligibility
claim-before-acceptance/install ordering
failure consumes and stops
single-executor lock
authorization-id binding
guard → Broker → authenticated readiness → Services ordering
no persistence enable during first start
runtime rollback attempt on failure
fresh per-device certificate path binding
legacy persistence helper remains enable-only
```

## 9. Current classification

```text
F4_B1_FACTORY_ACCEPTANCE_CREATOR=CLOSED
F4_B2_ACTIVATION_AUTHORITY_WIRING=CLOSED
F4_B3_FRESH_ACTIVATION_INSTALL_PACKAGE=CLOSED_WITH_EXACT_PACKAGE_BINDING
F4_B4_FRESH_CERT_LIFECYCLE_BINDING=CLOSED_FOR_TRANSITION_SCOPE

F4_RUNTIME_END_TO_END_ACCEPTANCE=NOT_YET_IMPLEMENTED
F4_PERSISTENCE_ENABLEMENT=NOT_YET_IMPLEMENTED
F4_REBOOT_ACCEPTANCE=NOT_ENTERED

NEW_PRODUCT_FAILURE=false
LIVE_F4_AUTHORIZATION=NOT_GRANTED
```

After exact-head CI is green, the next step is an independent source review of this repair before building any
exact F4 control artifact or accessing the real T1.


## 10. Independent review closure

The independent review at source head `be14b74e6c74cc8ac036e41cc99b49439a2fc20c` closed the transition-control
scope after additional source repairs for exact package binding, installed-material drift, post-transition restart
eligibility and Docker-backed rollback proof.

```text
INDEPENDENT_REVIEW=CLOSED_PASS_FOR_TRANSITION_CONTROL_SCOPE
FULL_F4_LIVE_READY=false
NEXT_ONE_GATE=N3W_T1_F4_RUNTIME_ACCEPTANCE_AND_PERSISTENCE_SOURCE_PREPARATION_20261015_01
```

Authority:
`docs/development/N3W_T1_F4_FACTORY_ACCEPTANCE_AND_ACTIVATION_SOURCE_REPAIR_INDEPENDENT_REVIEW_20261015.md`.
