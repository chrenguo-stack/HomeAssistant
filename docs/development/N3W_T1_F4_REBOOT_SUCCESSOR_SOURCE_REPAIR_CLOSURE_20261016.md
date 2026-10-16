# N3-W T1 F4 Reboot Successor — Source Repair Closure

Date: 2026-10-16

```text
TASK=N3W_T1_F4_REBOOT_SUCCESSOR_SOURCE_REPAIR_20261016_01
RESULT=CLOSED_PASS_SOURCE_REPAIR

PR=600
PR_STATE=OPEN_DRAFT
REVIEW_BASE=f492eb07e05dacfbc96dac3616c927bc6815641d
REVIEW_HEAD=5368acc1eb50f1fc62bbd7c16ff9e64139131a29

SOURCE_CI=14_SUCCESS_0_FAILURE_0_PENDING
EXACT_ARTIFACT_RUN_ID=38859830604
EXACT_ARTIFACT_ID=12028807237
EXACT_ARTIFACT_ZIP_SHA256=5af048d98ebfdcfb4ede62a8e958e3583dc60e2057d36d6f20123cbd7b74d4b4
EXACT_CONTROL_TAR_SHA256=e429201e41c8bb9154fe9c3397e06421bef147dc9117fea8d72184e97edef0a0
EXACT_MANIFEST_SHA256=2f2ae69dbf78d5f578fa60bbee7fb269a5d0c3b17a00e2f697bc65d3ed91c40c
EXACT_FILE_COUNT=4

T1_ACCESS=false
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
REBOOT=false
BOARD_ACCESS=false
MERGE=false

LIVE_REBOOT_AUTHORIZATION_READY=false
RAW_SYSTEMCTL_REBOOT_FORBIDDEN=true

NEXT_ONE_GATE=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_READONLY_PREAUTH_20261016_01
AUTO_EXECUTE_NEXT_GATE=false
```

## Closure decision

The source blocker recorded by the reboot-successor preparation gate is closed at the source/artifact layer.

The repaired design intentionally does not rewrite the already installed and F4-transaction-bound
`/usr/local/sbin/n3w-t1-f4-activation`. Replacing that file would itself violate the existing installed-material
binding. Instead, the successor boundary is implemented by a separate repository-owned F4 authority
(`n3w_t1_f4_reboot_authority.py`) that imports and reuses the frozen F4 host's provisioning, factory,
installed-material, runtime-acceptance, runtime-snapshot and certificate-identity contracts.

This is an explicit implementation refinement of the preparation requirement, not a relaxation of the F4
authorization model.

## Reboot authorization contract

The successor authority now enforces the exact PRE_REBOOT_READY contract before accepting any new install or
reboot authorization.

A control-install authorization is durably written before control-file mutation. The durable claim records:

- source head and exact control-manifest SHA-256;
- unchanged F4 transaction SHA-256;
- pre-install runtime-container identity snapshot;
- pre-install certificate/key identity snapshot;
- exact file hashes, sizes, targets and modes;
- claimed=true, consumed=true, replay_allowed=false.

The control install is bounded to four exact files and a manifest, followed by `systemctl daemon-reload` and a
read-only verification pass. It does not start/restart production services, does not start the certificate timer,
does not reboot, and does not access boards.

The reboot authorization is a separate one-shot claim. It is durably written before any later reboot actuation
and binds:

- source head;
- exact successor manifest;
- unchanged F4 transaction SHA-256;
- pre-reboot certificate/key identity snapshot;
- pre-reboot boot-ID SHA-256;
- claimed=true, consumed=true, replay_allowed=false;
- reboot_acceptance_passed=false.

The authority itself does not silently reboot the host. Actual reboot remains a later separately authorized live
actuation step. A raw ad-hoc reboot remains forbidden until the exact successor control is installed, verified and
the dedicated reboot authorization has been durably claimed.

## Certificate lifecycle status evolution repair

The old lifecycle service precheck required the live `status.json` SHA-256 to remain equal to the first-audit
hash forever. That was incompatible with the lifecycle helper, which legitimately rewrites status on every
scheduled check.

The successor package installs a systemd drop-in that replaces only that precheck with the repository-owned
runtime guard.

The runtime guard still fail-closes on:

- invalid F4 transaction/factory/installed-material/runtime contract;
- invalid root ownership, permissions, symlinks or link count;
- invalid status schema, action, result or transition;
- certificate/status fingerprint mismatch;
- server/CA/system-CA drift;
- runtime service-set drift.

Legitimate lifecycle status evolution is accepted, including HEALTHY/WARNING/RENEW_DUE/CRITICAL/EXPIRED and
CA_ROLLOVER_REQUIRED states where the lifecycle result contract allows them.

The final repair also closes a focused review defect found after the first green candidate: a legitimate
`ca_rollover_required` lifecycle result can carry `server_state=RENEW_DUE`; the guard now explicitly accepts
that state and has regression coverage for it.

## Regression coverage

The source CI now covers:

- root-owned record and installed-file safety contracts;
- fresh one-shot install/reboot authorization and replay rejection;
- durable claim persistence before live mutation;
- exact successor control-package file-set binding;
- post-reboot boot-ID change requirement;
- F4 transaction immutability across reboot;
- exact installed successor-control binding;
- certificate identity immutability across reboot;
- provisioning/ingress/Broker/Services persistence checks;
- certificate timer active policy after reboot;
- certificate lifecycle oneshot success result;
- Manager MQTT/runtime stability and Home Assistant MQTT non-duplication;
- two successive real lifecycle status evolutions remaining guard-eligible;
- CA-rollover-required / RENEW_DUE compatibility;
- absence of hidden reboot/poweroff actuation in the authority/verifier.

## Exact artifact provenance

The exact successor artifact is bound to:

```text
SOURCE_HEAD=5368acc1eb50f1fc62bbd7c16ff9e64139131a29
ARTIFACT_ID=12028807237
ARTIFACT_ZIP_SHA256=5af048d98ebfdcfb4ede62a8e958e3583dc60e2057d36d6f20123cbd7b74d4b4
CONTROL_TAR_SHA256=e429201e41c8bb9154fe9c3397e06421bef147dc9117fea8d72184e97edef0a0
MANIFEST_SHA256=2f2ae69dbf78d5f578fa60bbee7fb269a5d0c3b17a00e2f697bc65d3ed91c40c
```

The manifest contains exactly:

```text
tools/n3w_t1_f4_certificate_runtime_guard.py
  sha256=06f122d478176271f0db8f7f6222ef6ce618e94bf958f72ca62474ca2d76d57c

tools/n3w_t1_f4_reboot_authority.py
  sha256=b132ec94ae115766b580480b2d58850ee052639d772ab21dbec4c83f0c769822

tools/n3w_t1_f4_reboot_verify.py
  sha256=ab1b5a31c265643be00575688dd09248359794f3cb230b24f8ce9025e3c7408b

infra/n3w-t1/f4/reboot-successor/n3wfc4-broker-certificate-lifecycle.service.d/10-runtime-status-evolution.conf
  sha256=9a731615268cee76819e28fa2aede8993f4f59ab65b48c5a6c8e09ebdee2c256
```

The artifact contains no secret values, performs no mutation by being built, does not execute reboot, and has
`board_access=false`.

## Remaining live boundary

Source repair closure does not mean the T1 has been modified.

The live T1 remains at the previously verified PRE_REBOOT_READY state. The successor control has not yet been
installed there, no reboot authorization has been claimed, and no reboot has occurred.

The next gate is therefore strictly a read-only T1 preauthorization/preinstallation inspection:

```text
N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_READONLY_PREAUTH_20261016_01
```

Only after that read-only gate closes may a fresh explicit one-shot authorization be requested for the bounded
successor-control installation. Reboot remains a later separate authorization boundary.
