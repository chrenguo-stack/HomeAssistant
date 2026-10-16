# N3-W T1 F4 reboot successor control install postclaim failure forensic

Date: 2026-10-16

```text
TASK=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_POSTCLAIM_FAILURE_FORENSIC_20261016_01
RESULT=CLOSED_PASS_POSTCLAIM_FORENSIC

REAL_T1_STAGE=PERSISTENCE_ENABLED
F4_TRANSACTION_SHA256=49e7839ffe5d9e00391577a78c7c6ceb9c85a9a7cdd240ee22cc38485a3e569b
RUNTIME_ACCEPTANCE_SHA256=c938244cda069247f3288d0cc14fbdd37dcf7c389e8a16669ea8a6c3fcecbfd4
CERTIFICATE_STATUS_SHA256=446404d0e3725bf0e8fa9b6bd11bd67c83f16871a6e196b1cc950043ad229af4
BOOT_ID_SHA256=459bba3071dd3d48b7dd0a2cb750cfa9dcb09b456236564940c8fad85f79f95d
RUNTIME_SNAPSHOT_SHA256=29183afd73d71d4e85d8481d96f062b7c099d6721b46708a49495d58a39994f0
CERTIFICATE_IDENTITY_CANONICAL_SHA256=68264cf00af8a5748fc20c17edb4969533d326905bb3e959960b3f2ab0103947

CONTROL_REPAIR_AUTHORIZATION_ID=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_LIVE_20261016_01
CONTROL_REPAIR_AUTHORIZATION_CLAIMED=true
CONTROL_REPAIR_AUTHORIZATION_CONSUMED=true
CONTROL_REPAIR_AUTHORIZATION_REPLAY_ALLOWED=false

INSTALL_CLAIM_STAGE=CONTROL_APPLYING
INSTALL_CLAIM_SHA256=6c8cad9331094bbb0abe89ff67bc75b724d66c7eb97cdf6f4117c3bce5ed4d80
INSTALL_SOURCE_HEAD=5368acc1eb50f1fc62bbd7c16ff9e64139131a29
INSTALL_MANIFEST_SHA256=2f2ae69dbf78d5f578fa60bbee7fb269a5d0c3b17a00e2f697bc65d3ed91c40c
INSTALLATION_APPLY_STARTED=true
INSTALLATION_VERIFIED=null

REBOOT_AUTHORIZATION_CLAIMED=false
REBOOT_EXECUTED=false
BOARD_ACCESS=false
```

## Failure and exact installed state

The one-shot control-install authorization was durably claimed and consumed before mutation. The installer then
persisted `CONTROL_APPLYING`, installed all four successor files and the exact manifest, reloaded systemd, and failed
when the installed certificate runtime guard checked the live F4 contract.

All installed bytes and metadata matched the original exact package:

```text
/usr/local/sbin/n3w-t1-f4-certificate-runtime-guard
  sha256=06f122d478176271f0db8f7f6222ef6ce618e94bf958f72ca62474ca2d76d57c
  metadata=0:0:755:7763:1

/usr/local/sbin/n3w-t1-f4-reboot-authority
  sha256=b132ec94ae115766b580480b2d58850ee052639d772ab21dbec4c83f0c769822
  metadata=0:0:755:32682:1

/usr/local/sbin/n3w-t1-f4-reboot-verify
  sha256=ab1b5a31c265643be00575688dd09248359794f3cb230b24f8ce9025e3c7408b
  metadata=0:0:755:15707:1

/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service.d/10-runtime-status-evolution.conf
  sha256=9a731615268cee76819e28fa2aede8993f4f59ab65b48c5a6c8e09ebdee2c256
  metadata=0:0:644:95:1

/usr/local/share/n3w-t1-f4-reboot-successor/reboot-successor-manifest.json
  sha256=2f2ae69dbf78d5f578fa60bbee7fb269a5d0c3b17a00e2f697bc65d3ed91c40c
  metadata=0:0:644:856:1
```

The successor drop-in is loaded. The certificate timer remains enabled but inactive, and the certificate lifecycle
service remains inactive. Broker and Services activation units remain active. Broker, Manager and Home Assistant
remain healthy and the product listener set remains exactly `1883,8123,8883`.

## Confirmed root cause

The installed guard required:

```python
runtime.get("board_access") is False
```

but the frozen F4 `_runtime_activity()` contract does not return a `board_access` member. The lookup therefore
returns `None` and rejects an otherwise healthy runtime with `f4_runtime_contract_invalid`. This is a deterministic
successor-source defect, not evidence of a product runtime failure.

PR #605 removes only that impossible field requirement and adds regression coverage for the real runtime-activity
shape while preserving the production-service and exact service-set checks. Exact head
`99e0c4aecb013cf0dc8b350f851a38d670b9d6e7` has 13 successful GitHub workflow runs and no failed or pending run,
but the PR remains draft and unmerged. This source result is not T1 acceptance.

## Forensic closure

The read-only forensic proved all durable and live identities remained unchanged during collection:

```text
TX_UNCHANGED=true
RUNTIME_ACCEPTANCE_UNCHANGED=true
CERT_STATUS_UNCHANGED=true
BOOT_ID_UNCHANGED=true
RUNTIME_IDENTITY_UNCHANGED=true
CERTIFICATE_IDENTITY_UNCHANGED=true
FORENSIC_MUTATION=false
FORENSIC_TAIL_RESULT=CLOSED_PASS
```

The installed authority has no safe continuation command for this state: `install-control` accepts only
`INSTALL_CLAIMED` and requires absent targets, while `verify-install` accepts only `CONTROL_READY`. A dedicated,
tested recovery contract is therefore required before any T1 write.

## Binding stop rules

- Never replay `N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_LIVE_20261016_01`.
- Do not rerun the original `install-control` command.
- Do not manually edit or replace installed successor files.
- Do not claim reboot authority and do not reboot while the claim remains `CONTROL_APPLYING`.
- Do not start or trigger the certificate lifecycle service or timer.
- Any recovery must bind the consumed claim, original installed file hashes, repaired exact package, unchanged F4
  transaction/runtime/certificate/boot identities, and a fresh independent recovery authorization.
- Recovery must reach and durably persist `CONTROL_READY` before reboot eligibility can be reconsidered.

```text
NEXT_ONE_GATE=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_APPLYING_RECOVERY_SOURCE_REPAIR_20261016_01
AUTO_EXECUTE_NEXT_GATE=false
T1_RECOVERY_AUTHORIZATION_GRANTED=false
REBOOT_AUTHORIZATION_GRANTED=false
```
