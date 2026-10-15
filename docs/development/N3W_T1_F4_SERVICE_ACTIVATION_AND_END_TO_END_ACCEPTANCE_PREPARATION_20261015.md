# N3-W T1 F4 Service Activation and End-to-End Acceptance Preparation — 2026-10-15

```text
TASK=N3W_T1_F4_SERVICE_ACTIVATION_AND_END_TO_END_ACCEPTANCE_PREPARATION_20261015_01
RESULT=CLOSED_PASS_SOURCE_PREPARATION

SOURCE_AUTHORITY_MAIN=0877b0fc51727df9a9175fdfb838616a3c625147
LIVE_PRODUCT_RELEASE_ID=6ac82ae0872b05644e59470ffef7307dad14d359
LIVE_PRODUCT_STATE=DEVICE_READY

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
```

## 1. Purpose and boundary

This gate maps the exact post-DEVICE_READY source and freezes the minimum F4 repair/acceptance path.

It does not access the real T1 and does not create `FACTORY_ACCEPTED`, install activation units, enable
production persistence, start Broker/Manager/Home Assistant, activate the certificate timer, reboot the host,
or access any board.

The governing route remains:

```text
DEVICE_READY
→ FACTORY_AUDIT
→ FACTORY_ACCEPTED
→ CONTROLLED_PRODUCT_ACTIVATION
→ END_TO_END_ACCEPTANCE
→ REBOOT_PERSISTENCE_ACCEPTANCE
```

F4 remains a separately authorized live stage.

## 2. Exact source rebind

Current GitHub authority after the convergence gate:

```text
main=0877b0fc51727df9a9175fdfb838616a3c625147
PR543=CLOSED_SUPERSEDED
PR544=MERGED
PR545=MERGED
PR546=MERGED
```

The real T1 remains on product release:

```text
release_id=6ac82ae0872b05644e59470ffef7307dad14d359
provisioning_state=DEVICE_READY
production_service_start=false
```

The existing activation-related source blobs are unchanged between deployed release `6ac82ae...` and current
main for the following already-existing assets:

```text
production compose
Broker activation unit
Manager/Home Assistant activation unit
certificate lifecycle service/timer
NetworkManager ingress-guard dispatcher
broker activation environment example
certificate lifecycle environment example
Broker authenticated-readiness helper
Broker certificate-lifecycle helper
production activation enable script
device provisioning runtime eligibility evaluator
```

Therefore the F4 gap is not caused by post-R4 drift in these legacy assets. The gap is ownership/wiring for the
new fresh-Armbian + explicit-provisioning route.

## 3. What F3 intentionally installed

The fresh product path deliberately leaves production services stopped.

Current F3 source installs the public product tree plus:

```text
/usr/local/sbin/n3w-broker-ingress-guard
/usr/local/sbin/n3w-t1-provision
/usr/local/sbin/n3w-t1-systemd-staged-install
/usr/local/sbin/n3w-t1-production-activation-enable
/etc/systemd/system/n3wfc4-broker-ingress-guard.service
/etc/systemd/system/n3wfc4-provision-resume.service
```

It intentionally requires these later-production targets to remain absent before F4:

```text
/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
/usr/local/sbin/n3w-t1-broker-authenticated-readiness
/usr/local/sbin/n3w-broker-certificate-lifecycle
/etc/systemd/system/n3wfc4-broker-activation.service
/etc/systemd/system/n3wfc4-services-activation.service
/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service
/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer
```

This matches the real stopped-boundary evidence. Their absence is not a product failure.

## 4. Reusable closed primitives

The following existing contracts are suitable to reuse in F4.

### 4.1 DEVICE_READY authority

`n3w-t1-provision verify` already proves:

- durable provisioning completion exists;
- exact release binding is valid;
- current host identity still matches the persisted host binding;
- SYSTEM_ID is returned from the completed provisioning record;
- it has no production-service start authority.

### 4.2 Fresh stopped-state audit primitive

The fresh bootstrap adapter already has `instance_stopped_postcheck(system_id)`, which verifies current
instance material while production services remain stopped. It includes:

- no running product containers/listeners;
- all fresh instance roots present;
- rendered Compose + image-lock deployment gate PASS;
- Manager state audit;
- system identity audit;
- fresh DynSec audit;
- service credential bundle audit;
- zero node credential state.

This audit must be re-run at F4 time; the existing `n3w-t1-provision verify` alone does not re-run it.

### 4.3 Activation eligibility validator

`greenhouse_manager.bootstrap.device_provisioning_runtime.evaluate_product_activation()` already defines
the policy primitive:

```text
DEVICE_READY without FACTORY_ACCEPTED → activation_eligible=false
exact FACTORY_ACCEPTED binding         → activation_eligible=true
production_service_start              → always false in evaluator
```

It validates a root-owned mode-0600 regular file through one validated descriptor and binds:

```text
schema=gh.n3w.t1-factory-accepted/1
status=PASS
factory_accepted=true
release_id=<exact deployed release>
host_instance_id=<current verified host>
system_id=<current DEVICE_READY system>
system_id_sha256=<exact>
```

It intentionally does not create the record and does not start services.

### 4.4 Existing runtime assets

The existing production assets remain useful after they are put behind the new F4 gate:

- fail-closed Broker ingress guard;
- Broker activation unit;
- Manager/Home Assistant activation unit;
- authenticated Broker readiness helper;
- rendered Compose deployment gate;
- production activation enable helper;
- certificate lifecycle implementation and timer concepts.

They are reusable components, not the final F4 owner by themselves.

## 5. Open source blockers

### F4-B1 — no FACTORY_AUDIT → FACTORY_ACCEPTED creator

Current source can validate a future `FACTORY_ACCEPTED` record but no current fresh-route host command owns:

```text
current DEVICE_READY re-audit
→ factory audit PASS
→ durable one-time FACTORY_ACCEPTED creation
```

This is the primary blocker before service activation.

The F4 source repair must freeze the canonical path as:

```text
/var/lib/n3w-t1-provisioning/FACTORY_ACCEPTED.json
```

and create it only after a fresh current-host stopped-state audit passes.

Required write contract:

```text
owner=root
mode=0600
regular_file=true
symlink=false
link_count=1
atomic_write=true
new_record_only=true
overwrite_existing=false
directory_fsync=true
```

An existing exact record is verify-only. An existing malformed or mismatched record is fail-closed and must never
be deleted merely to regain eligibility.

### F4-B2 — current enable helper is not the activation authority

`infra/n3w-t1/activate-systemd-production.sh` only executes `systemctl enable` for the activation units/timer.
It does not:

- create or validate FACTORY_ACCEPTED;
- install the currently absent activation material;
- verify current DEVICE_READY stopped state;
- start Broker/Manager/Home Assistant;
- perform end-to-end acceptance;
- own rollback/recovery.

It must remain a low-level persistence helper, not become the top-level F4 authority.

The activation units also need an independent fail-closed eligibility precheck so that a direct
`systemctl start` cannot bypass FACTORY_ACCEPTED.

### F4-B3 — fresh activation package is missing

The real fresh route has all three exact images and per-device identity material, but F4 still needs a
repository-owned bounded package that installs only the later activation material.

At minimum F4 must own installation/verification of:

```text
/etc/n3wfc4/docker-compose.yml
/etc/n3wfc4/broker-activation.env
/usr/local/sbin/n3w-t1-broker-authenticated-readiness
/usr/local/sbin/<F4 activation eligibility guard>
/etc/systemd/system/n3wfc4-broker-activation.service
/etc/systemd/system/n3wfc4-services-activation.service
/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
```

The install transaction must not start services and must leave production persistence disabled until live runtime
acceptance has passed.

The old `tools/n3w_t1_production_stack_staging.py` is not the owner for this fresh route. It contains historical
fixed system/image/baseline assumptions and must not be revived as the F4 executor.

### F4-B4 — certificate lifecycle must be adapted to per-device fresh identity

The old KF-100 certificate installation path is not directly reusable unchanged for the new fresh route.

The current fresh provisioning model generates a unique per-device Broker CA/server certificate. In contrast, the
historical KF-100 deployment preflight/installer contains fixed certificate fingerprints and assumes an already
running Broker plus the older system-CA/private-CA authority layout.

The generic example environment also points at historical paths, while the fresh route places the Broker CA private
key under the per-device secret root.

Therefore F4 must create a fresh-route certificate-lifecycle binding from the current provisioned identity instead
of copying the historical environment unchanged.

No certificate or CA replacement is part of initial F4 activation. The first lifecycle audit must be read-only.

## 6. Frozen F4 owner model

F4 source repair will introduce one repository-owned host orchestration authority. The exact implementation may use
small internal helpers, but externally it must expose bounded phases with no hidden transition:

```text
preflight
→ read-only DEVICE_READY + stopped-state factory audit

apply
→ exact F4 authorization check/claim
→ re-run fresh factory audit
→ create FACTORY_ACCEPTED
→ install exact activation material with services still disabled/stopped
→ prove ingress guard
→ start Broker
→ authenticated Broker readiness
→ start Manager + Home Assistant
→ runtime end-to-end acceptance
→ only after PASS enable reboot persistence
→ STOP before reboot

verify
→ read-only ACTIVE runtime verification

rollback-status
→ read-only classification after failed/partial activation
```

A failure before the F4 durable claim permits no mutation.
A failure after claim consumes the authorization and forbids blind replay.

## 7. Factory audit contract

Immediately before FACTORY_ACCEPTED creation, the fresh audit must prove at least:

```text
PROVISION_VERIFY=PASS
PROVISION_STATE=DEVICE_READY
CURRENT_HOST_BINDING=PASS
DEPLOYED_RELEASE_BINDING=PASS

INSTANCE_STOPPED_POSTCHECK=PASS
EXACT_THREE_IMAGE_BINDING=PASS
RENDERED_COMPOSE_GATE=PASS

PRODUCT_CONTAINER_COUNT=0
PRODUCT_LISTENER_COUNT=0

INGRESS_GUARD_UNIT=loaded
INGRESS_GUARD_ENABLED=enabled
INGRESS_GUARD_EFFECTIVE=PASS

BROKER_ACTIVATION_ACTIVE=false
SERVICES_ACTIVATION_ACTIVE=false
CERTIFICATE_TIMER_ACTIVE=false

MANAGER_BUSINESS_STATE_EMPTY=true
NODE_CREDENTIAL_COUNT=0
DYNSEC_NODE_COUNT=0
SERVICE_CREDENTIAL_BUNDLE=PASS

FACTORY_ACCEPTED_PREEXISTING=false
```

The public report must contain only booleans/hashes/status and must not disclose raw SYSTEM_ID, host identity,
passwords, private keys, setup secrets, or the private T1 locator.

## 8. Runtime activation order

The old preparation document enabled persistence before first start. For the new fresh route the safer F4 order is
frozen as:

```text
FACTORY_ACCEPTED exact
→ install units/helpers/env/dispatcher
→ daemon-reload
→ keep Broker/Services/timer disabled
→ validate rendered Compose and guard
→ systemctl start n3wfc4-broker-activation.service
→ authenticated TLS/MQTT readiness
→ systemctl start n3wfc4-services-activation.service
→ Manager + Home Assistant runtime acceptance
→ only after runtime PASS enable Broker/Services persistence
→ complete fresh certificate-lifecycle install + first read-only audit
→ enable certificate lifecycle timer only after lifecycle audit PASS
→ STOP before reboot
```

This prevents an incomplete first activation from becoming an automatic reboot-time start policy.

## 9. End-to-end acceptance contract

Before F4 live activation can be called PASS, runtime checks must cover:

### Broker

- exactly expected Broker container/image binding;
- TCP/8883 wildcard publication owned only by Broker;
- TCP/1883 loopback-only publication;
- ingress guard remains exact and fail-closed;
- CA validation and TLS server-name verification;
- server certificate/key match;
- anonymous connection rejected;
- invalid client rejected;
- Manager, Home Assistant and provisioning identities remain distinct.

### Manager

- exact fresh Manager image binding;
- process runs as 999:999 with expected read-only rootfs contract;
- authenticated TLS MQTT connection succeeds;
- fresh Manager database remains valid;
- no historical node/pairing/retirement/replay payload is present;
- product pairing remains disabled until the later board gate;
- no unexpected Discovery/canonical state is emitted for nonexistent nodes.

### Home Assistant

- exact Home Assistant image binding;
- Home Assistant reaches runtime readiness;
- MQTT bootstrap uses the dedicated Home Assistant credential;
- exactly one intended MQTT integration/bootstrap result is produced;
- restart/reboot must not duplicate the integration;
- no node/entity history is fabricated before board pairing.

### Global

- three service identities remain distinct and minimally privileged;
- no secret value appears in public evidence;
- product service start is traceable to the F4 authorization;
- board access remains false.

## 10. Reboot boundary

Initial service activation and live end-to-end acceptance stop before reboot.

Reboot persistence is a separate explicit live subgate because it mutates host runtime availability and tests a
different failure domain.

After initial F4 activation PASS, the next live acceptance must prove:

```text
reboot
→ provisioning resume helper performs verify-only on DEVICE_READY
→ FACTORY_ACCEPTED remains exact
→ Broker guard precedes Broker publication
→ Broker/Manager/Home Assistant return automatically
→ certificate timer policy remains correct
→ identities/credentials unchanged
→ HA MQTT integration not duplicated
→ Manager business state remains fresh
```

No board pairing is included.

## 11. Planned source-repair surface

The next source gate may change only the minimum F4 ownership surface.

Expected additions/modifications:

```text
ADD:
  tools/n3w_t1_f4_activation_host.py
  tests/tools/test_n3w_t1_f4_activation_host.py

MODIFY as required:
  tools/n3w_t1_device_provisioning_host.py
    - expose a read-only current stopped-state audit seam; never add automatic new provisioning

  infra/n3w-t1/systemd/n3wfc4-broker-activation.service
  infra/n3w-t1/systemd/n3wfc4-services-activation.service
    - fail-closed FACTORY_ACCEPTED eligibility precheck

  infra/n3w-t1/activate-systemd-production.sh
    - remain persistence-only; no --now/start/restart

  certificate lifecycle install/preflight source
    - replace old fixed-identity assumptions with fresh per-device identity binding

  fresh deployable payload workflow/tests
    - carry the exact small F4 control package
```

The source repair must not alter ESP32 firmware, pairing/NVS behavior, N3-W radio state machines, or the already
consumed provisioning transaction.

## 12. Required source tests

At minimum:

```text
DEVICE_READY_AUDIT_CURRENT_STATE_REQUIRED=true
FACTORY_ACCEPTED_MISSING_DENY=true
FACTORY_ACCEPTED_EXACT_BINDING_PASS=true
FACTORY_ACCEPTED_HOST_DRIFT_FAIL_CLOSED=true
FACTORY_ACCEPTED_SYSTEM_ID_DRIFT_FAIL_CLOSED=true
FACTORY_ACCEPTED_RELEASE_DRIFT_FAIL_CLOSED=true
FACTORY_ACCEPTED_SYMLINK_FAIL_CLOSED=true
FACTORY_ACCEPTED_MODE_OWNER_LINK_GUARD=true
FACTORY_ACCEPTED_NO_OVERWRITE=true

DIRECT_SYSTEMD_START_WITHOUT_ACCEPTANCE_DENIED=true
F4_INSTALL_DOES_NOT_START_SERVICES=true
F4_PARTIAL_FAILURE_PERSISTENCE_NOT_ENABLED=true

BROKER_START_BEFORE_SERVICES=true
AUTHENTICATED_READINESS_BEFORE_APPLICATION_SERVICES=true
APPLICATION_RUNTIME_FAILURE_STOPS_EXPANSION=true

FRESH_CERT_LIFECYCLE_PER_DEVICE_BINDING=true
FIXED_CERT_FINGERPRINT_DEPENDENCY_REMOVED_FROM_FRESH_ROUTE=true
CERT_TIMER_NOT_ENABLED_BEFORE_FIRST_AUDIT=true

BOARD_ACCESS=false
PROVISIONING_START_REPLAY=false
```

Required CI remains focused plus the existing greenhouse-manager, DynSec, Mosquitto, public-repository-safety and
fresh-bootstrap/deployable payload guards affected by the changed files.

## 13. Authorization model

This preparation gate grants no live authorization.

The later F4 live authorization must be a new one-shot authorization independent from the already consumed
Provisioning authorization.

```text
PROVISIONING_AUTHORIZATION=CONSUMED_NO_REPLAY
F4_AUTHORIZATION=NOT_GRANTED
F4_AUTHORIZATION_CLAIMED=false
F4_AUTHORIZATION_CONSUMED=false
```

The F4 durable claim must occur before the first F4 mutation, including FACTORY_ACCEPTED creation.

## 14. Gate closure

```text
F4_PREPARATION=CLOSED_PASS
F4_SOURCE_READY=false

F4_B1_FACTORY_ACCEPTANCE_CREATOR=OPEN_SOURCE_REPAIR
F4_B2_ACTIVATION_AUTHORITY_WIRING=OPEN_SOURCE_REPAIR
F4_B3_FRESH_ACTIVATION_INSTALL_PACKAGE=OPEN_SOURCE_REPAIR
F4_B4_FRESH_CERT_LIFECYCLE_BINDING=OPEN_SOURCE_REPAIR

NEW_PRODUCT_FAILURE=false
NEW_KNOWN_FAILURE=false

CURRENT_STOP_POINT=AFTER_F4_PREPARATION_BEFORE_F4_SOURCE_REPAIR

NEXT_ONE_GATE=N3W_T1_F4_FACTORY_ACCEPTANCE_AND_ACTIVATION_SOURCE_REPAIR_20261015_01

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
AUTO_EXECUTE_LIVE_F4=false
```
