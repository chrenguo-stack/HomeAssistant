# N3-W T1 Explicit Device Provisioning P2 Host Resume / Activation Guard Source Plan（2026-10-13）

TASK=
`N3W_T1_EXPLICIT_DEVICE_PROVISIONING_P2_HOST_RESUME_ACTIVATION_GUARD_SOURCE_PLAN`

## 0. Decision

P1 independent source review is PASS at `e464c103c9c5cbc2aa2d57d9e853d9e85e73596d`.
P2 now starts as source-only work. No T1, live systemd, activation topology, board or merge action is authorized by this document.

Fresh source mapping shows an important boundary:

- `device_firstboot.py` now has correct pure start/resume/verify semantics;
- current `LiveFreshInstallerAdapters` still belongs to the historical fresh-bootstrap transport and does not implement the new `preflight_clone / ensure_os_identity / verify_os_identity` product adapter contract;
- current activation units and NetworkManager dispatcher are valid for the already-provisioned runtime but can automatically enter Broker activation when installed/enabled;
- current golden-master public staging only commits public source plus the ingress-guard executable/unit and does not install those activation units/dispatcher.

Therefore P2 must not directly wire the legacy activation installer into the golden image.

## 1. P2 split

### P2A — pure boot/activation policy contract

Implement first:

1. `reconcile_boot_device_provisioning()`;
2. UNPROVISIONED -> NOOP;
3. INITIALIZING -> resume existing transaction only;
4. DEVICE_READY -> verify-only;
5. CONFLICT -> fail-closed;
6. activation eligibility remains false until a secure `FACTORY_ACCEPTED` record is present and exactly bound to release, current host and product SYSTEM_ID;
7. add a source-only resume unit definition that has no authority to start Broker/Manager/HA;
8. keep the existing persistence installer unchanged, so the new unit is not live-installed by this source step.

### P2B — real host adapter / CLI wiring

Only after P2A review/CI:

- extract a single reusable instance-provisioning adapter from the current fresh-bootstrap implementation;
- implement the product host adapter for clone/release evidence and current OS-host identity;
- wire the real `n3w-t1-provision` host command;
- provide `status/start` plus internal `resume-if-needed/verify`;
- install the resume unit only through the future golden-master install path;
- keep current production activation topology untouched until the new activation gate is the actual owner.

This split avoids mixing an unresolved target-Armbian OS-identity implementation with the already-closed P1 transaction core.

## 2. P2A activation marker contract

P2A only validates, never creates, the future factory-acceptance record.

```text
schema=gh.n3w.t1-factory-accepted/1
status=PASS
factory_accepted=true
release_id=<exact>
host_instance_id=<current verified host>
system_id=<DEVICE_READY system>
system_id_sha256=<exact>
```

Record requirements:

- regular file;
- current euid owner;
- mode 0600;
- nlink=1;
- no symlink;
- all bindings exact.

Missing marker is a normal DENY, not an error.
Malformed/mismatched marker is fail-closed.

## 3. Boot helper contract

```text
UNPROVISIONED
→ NOOP
→ no transaction creation
→ no product activation

INITIALIZING
→ resume existing durable transaction
→ no new start authority

DEVICE_READY
→ verify current live host binding
→ no identity regeneration
→ no product activation

CONFLICT
→ service failure / fail-closed
```

The pure runtime module must not import or reference `start_device_provisioning`.

## 4. Source-only systemd definition

Add:

```text
infra/n3w-t1/systemd/n3wfc4-provision-resume.service
```

It is intentionally not added to the existing `install-systemd-persistence.sh` in P2A.

The unit may only invoke:

```text
/usr/local/sbin/n3w-t1-provision resume-if-needed
```

and must order before the existing Broker/services activation units without pulling them in.

## 5. P2A files

ADD:

```text
host/greenhouse-manager/src/greenhouse_manager/bootstrap/device_provisioning_runtime.py
host/greenhouse-manager/tests/bootstrap/test_device_provisioning_runtime.py
infra/n3w-t1/systemd/n3wfc4-provision-resume.service
```

This plan document is the fourth added file.

Do not modify in P2A:

```text
infra/n3w-t1/install-systemd-persistence.sh
infra/n3w-t1/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
infra/n3w-t1/systemd/n3wfc4-broker-activation.service
infra/n3w-t1/systemd/n3wfc4-services-activation.service
tools/n3w_t1_fresh_product_bootstrap.py
firmware
```

## 6. Acceptance

P2A PASS requires:

```text
UNPROVISIONED_BOOT_NOOP=true
INITIALIZING_RESUME_ONLY=true
DEVICE_READY_VERIFY_ONLY=true
BOOT_START_AUTHORITY_ABSENT=true
FACTORY_ACCEPTANCE_REQUIRED_FOR_ACTIVATION=true
FACTORY_MARKER_BINDING_FAIL_CLOSED=true
PRODUCTION_SERVICE_START=false
LEGACY_ACTIVATION_TOPOLOGY_UNCHANGED=true
CI=PASS
```

P2A does not prove the future host CLI is deployable and does not permit enabling the new systemd unit on T1.
