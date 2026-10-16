# N3-W T1 F4 Reboot Successor Control Install — Read-only Preauthorization

Date: 2026-10-16

```text
TASK=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_READONLY_PREAUTH_20261016_01
MODE=READ_ONLY
T1_MUTATION=false
LIVE_RUNTIME_MUTATION=false
ARTIFACT_STAGING=false
AUTHORIZATION_CLAIM=false
REBOOT=false
BOARD_ACCESS=false
MERGE=false

SOURCE_REPAIR_HEAD=5368acc1eb50f1fc62bbd7c16ff9e64139131a29
SOURCE_REPAIR_PR=600
SOURCE_CLOSURE_PR=601
SOURCE_CI=14_SUCCESS_0_FAILURE_0_PENDING

EXACT_ARTIFACT_RUN_ID=38859830604
EXACT_ARTIFACT_ID=12028807237
EXACT_ARTIFACT_ZIP_SHA256=5af048d98ebfdcfb4ede62a8e958e3583dc60e2057d36d6f20123cbd7b74d4b4
EXACT_CONTROL_TAR_SHA256=e429201e41c8bb9154fe9c3397e06421bef147dc9117fea8d72184e97edef0a0
EXACT_MANIFEST_SHA256=2f2ae69dbf78d5f578fa60bbee7fb269a5d0c3b17a00e2f697bc65d3ed91c40c

EXPECTED_F4_TRANSACTION_SHA256=49e7839ffe5d9e00391577a78c7c6ceb9c85a9a7cdd240ee22cc38485a3e569b
EXPECTED_RUNTIME_ACCEPTANCE_SHA256=c938244cda069247f3288d0cc14fbdd37dcf7c389e8a16669ea8a6c3fcecbfd4
EXPECTED_CERTIFICATE_STATUS_SHA256=446404d0e3725bf0e8fa9b6bd11bd67c83f16871a6e196b1cc950043ad229af4
EXPECTED_RUNTIME_SNAPSHOT_SHA256=7a6c2f989ce2a585012f9a44841c6a53036e064ba3051aa95d407b789bac6b92
EXPECTED_CERTIFICATE_IDENTITY_SNAPSHOT_SHA256=0a7bdd09d9647eac208dccfa150779b31db55ba61636230f35da089bf5067a4f

PROPOSED_CONTROL_INSTALL_AUTHORIZATION=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_LIVE_20261016_01
AUTHORIZATION_GRANTED=false
```

## Purpose

This gate proves that the real T1 is still at the exact PRE_REBOOT_READY baseline required by the reviewed
successor authority and that no successor-control residue already exists.

It does not download or stage the artifact on the T1, create authorization records, install files, reload systemd,
start or restart services, reboot, or access boards.

## Read-only checks

The collector must prove all of the following before the live install authorization can be requested:

- F4 launcher `status` is PASS with Broker, Manager and Home Assistant running;
- F4 `eligibility --phase certificate` remains PASS before successor installation;
- F4 transaction remains SHA-256 `49e7839ffe5d9e00391577a78c7c6ceb9c85a9a7cdd240ee22cc38485a3e569b`;
- runtime-acceptance report remains SHA-256 `c938244cda069247f3288d0cc14fbdd37dcf7c389e8a16669ea8a6c3fcecbfd4`;
- certificate status remains SHA-256 `446404d0e3725bf0e8fa9b6bd11bd67c83f16871a6e196b1cc950043ad229af4`;
- runtime and certificate identity snapshots remain unchanged;
- transaction state remains `PERSISTENCE_ENABLED` with persistence, first audit, timer enablement and
  `pre_reboot_ready=true`;
- Broker/Services/Guard/Provision persistence remains enabled and current runtime remains healthy;
- certificate timer remains enabled but inactive before reboot;
- certificate lifecycle service remains inactive;
- product listener set remains exactly 1883, 8123 and 8883;
- the successor install-claim, reboot-claim and successor authority lock records are absent;
- all five successor install targets are absent, including the exact systemd drop-in and installed manifest;
- the lifecycle service has no loaded successor drop-in yet;
- the proposed control-install authorization does not collide with any F4 authorization ID/history;
- collector before/after transaction, runtime-acceptance, certificate-status, runtime-identity,
  certificate-identity and boot-ID hashes are unchanged.

## Stop conditions

Any mismatch is a fail-closed STOP. Do not stage the successor artifact and do not request or claim a live install
authorization until the mismatch is classified.

A PASS only makes the bounded control installation eligible for an explicit user authorization. It does not
authorize installation or reboot.

```text
PASS_NEXT_ONE_GATE=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_LIVE_20261016_01
AUTO_EXECUTE_LIVE_INSTALL=false
REBOOT_AUTHORIZATION_GRANTED=false
```
