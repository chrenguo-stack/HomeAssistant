# N3-W T1 F4 Reboot Successor Control Install — Live Authorization

Date: 2026-10-16

```text
TASK=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_LIVE_20261016_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_SOURCE=user_explicit
AUTHORIZATION_ID=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_LIVE_20261016_01

SOURCE_REPAIR_HEAD=5368acc1eb50f1fc62bbd7c16ff9e64139131a29
SOURCE_REPAIR_PR=600
PREAUTH_R2_CLOSURE_PR=603

EXACT_ARTIFACT_RUN_ID=38859830604
EXACT_ARTIFACT_ID=12028807237
EXACT_ARTIFACT_ZIP_SHA256=5af048d98ebfdcfb4ede62a8e958e3583dc60e2057d36d6f20123cbd7b74d4b4
EXACT_CONTROL_TAR_SHA256=e429201e41c8bb9154fe9c3397e06421bef147dc9117fea8d72184e97edef0a0
EXACT_MANIFEST_SHA256=2f2ae69dbf78d5f578fa60bbee7fb269a5d0c3b17a00e2f697bc65d3ed91c40c

EXPECTED_F4_TRANSACTION_SHA256=49e7839ffe5d9e00391577a78c7c6ceb9c85a9a7cdd240ee22cc38485a3e569b
EXPECTED_RUNTIME_ACCEPTANCE_SHA256=c938244cda069247f3288d0cc14fbdd37dcf7c389e8a16669ea8a6c3fcecbfd4
EXPECTED_CERTIFICATE_STATUS_SHA256=446404d0e3725bf0e8fa9b6bd11bd67c83f16871a6e196b1cc950043ad229af4
EXPECTED_BOOT_ID_SHA256=459bba3071dd3d48b7dd0a2cb750cfa9dcb09b456236564940c8fad85f79f95d
EXPECTED_RUNTIME_SNAPSHOT_SHA256=29183afd73d71d4e85d8481d96f062b7c099d6721b46708a49495d58a39994f0

REBOOT_AUTHORIZATION_GRANTED=false
REBOOT=false
BOARD_ACCESS=false
MERGE=false
```

## Authorized mutation scope

The explicit user authorization covers exactly this control-install gate.

Allowed:

1. retrieve the exact GitHub Actions artifact bound to the frozen source head;
2. verify ZIP, tar, manifest, file-set and file hashes before T1 mutation;
3. stage the exact control tar/package on the T1;
4. run the repository-owned successor authority `claim-install`;
5. durably claim and consume the exact control-install authorization;
6. run `install-control` to install exactly the manifest-bound four control files plus installed manifest;
7. execute the authority's bounded `systemctl daemon-reload`;
8. run repository-owned `verify-install` and additional read-only postchecks.

Not authorized:

- `claim-reboot`;
- `systemctl reboot`, shutdown, poweroff or any equivalent reboot actuation;
- starting the certificate lifecycle timer/service;
- restarting Broker/Manager/Home Assistant;
- board access;
- PR merge;
- unrelated T1 mutation.

## Exact install targets

```text
/usr/local/sbin/n3w-t1-f4-certificate-runtime-guard
/usr/local/sbin/n3w-t1-f4-reboot-authority
/usr/local/sbin/n3w-t1-f4-reboot-verify
/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service.d/10-runtime-status-evolution.conf
/usr/local/share/n3w-t1-f4-reboot-successor/reboot-successor-manifest.json
```

The install authorization record is:

```text
/var/lib/n3w-t1-provisioning/F4_REBOOT_SUCCESSOR_INSTALL_AUTHORIZATION.json
```

A lock file may also be created by the repository-owned authority:

```text
/var/lib/n3w-t1-provisioning/.f4-reboot-successor-authority.lock
```

## Required fail-closed order

The live gate must preserve this order:

1. verify exact artifact locally;
2. stage exact control tar;
3. verify exact staged tar/package on T1;
4. prove current frozen F4/runtime/certificate/boot/runtime-snapshot baseline;
5. execute `claim-install`;
6. confirm durable claim reports claimed=true, consumed=true, replay_allowed=false;
7. only then execute `install-control`;
8. verify installed exact control and loaded drop-in;
9. prove F4 transaction, runtime identity, certificate identity, boot identity, product listeners and service activity did not drift;
10. stop.

A failure before step 5 must not create an install claim. A failure after step 5 must never reuse the consumed authorization. Any post-claim failure is a forensic STOP.

## Success boundary

A successful gate ends at `CONTROL_READY`.

It does not claim or grant reboot authorization.

```text
PASS_STATE=CONTROL_READY
PASS_NEXT_ROUTE=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_POSTEXECUTION_READONLY_CLOSURE_20261016_01
REBOOT_AUTHORIZATION_GRANTED=false
AUTO_EXECUTE_REBOOT=false
```

## First live execution — pre-claim STOP on certificate identity comparison

The authorized live gate stopped before any authorization claim or control-file installation:

```text
LOCAL_EXACT_ARTIFACT=PASS
SOURCE_HEAD=5368acc1eb50f1fc62bbd7c16ff9e64139131a29
MANIFEST_FILE_COUNT=4
LIVE_INSTALL_FAIL=certificate_identity_before
AUTHORIZATION_CLAIMED=false
REBOOT_EXECUTED=false
BOARD_ACCESS=false
STOP=true
```

The exact transport tar was copied to the T1 before this check, but the repository-owned successor authority was
not invoked and the install authorization was not claimed or consumed. The package extraction/install stage was
not reached.

The failure is currently classified as a pre-claim forensic STOP, not as a product failure. The failed comparison
used an expected historical certificate-identity digest that was produced by an earlier evidence collector, while
the live wrapper calculated the current identity by canonical-JSON hashing
`_certificate_identity_snapshot()`. These digest methods must be proven equivalent before the mismatch may be
treated as certificate/key drift.

```text
CONTROL_INSTALL_GATE_RESULT=STOP_PRECLAIM
TRANSPORT_TAR_STAGED=true
PACKAGE_EXTRACTION_REACHED=false
INSTALL_AUTHORIZATION_CLAIMED=false
INSTALL_AUTHORIZATION_CONSUMED=false
CONTROL_FILES_INSTALLED=false
DAEMON_RELOAD_REACHED=false
REBOOT_AUTHORIZATION_CLAIMED=false
REBOOT_EXECUTED=false
BOARD_ACCESS=false

NEXT_ROUTE=N3W_T1_F4_REBOOT_SUCCESSOR_CERTIFICATE_IDENTITY_HASH_READONLY_FORENSIC_20261016_01
```

Do not rerun the live install until the identity-hash mismatch is classified.

## Certificate identity hash forensic — CLOSED_PASS

The pre-claim stop was caused by comparing two different evidence-digest algorithms, not by certificate/key drift.

Observed on the live T1:

```text
CERTIFICATE_IDENTITY_CANONICAL_SHA256=68264cf00af8a5748fc20c17edb4969533d326905bb3e959960b3f2ab0103947
CERTIFICATE_IDENTITY_LEGACY_TEXT_SHA256=0a7bdd09d9647eac208dccfa150779b31db55ba61636230f35da089bf5067a4f
LEGACY_EXPECTED_MATCH=true

SERVER_CERT_KEY_MATCH=true
CA_CERT_KEY_MATCH=true

F4_DURABLE_CONTRACT=PASS
TLS_MATERIAL_CONTRACT=PASS
TLS_RUNTIME_CONTRACT=PASS

TX_UNCHANGED=true
RUNTIME_ACCEPTANCE_UNCHANGED=true
CERT_STATUS_UNCHANGED=true
BOOT_ID_UNCHANGED=true

INSTALL_AUTHORIZATION_CLAIMED=false
INSTALL_AUTHORIZATION_CONSUMED=false
CONTROL_FILES_INSTALLED=false
REBOOT_AUTHORIZATION_CLAIMED=false
REBOOT_EXECUTED=false
BOARD_ACCESS=false
FORENSIC_MUTATION=false
FORENSIC_COMPLETE=true
```

The five individual certificate/key file SHA-256 values are unchanged from the legacy evidence set. Certificate
status fingerprints match the live server certificate, broker CA certificate and Manager system CA certificate.
The server certificate/public key matches the server private key, and the broker CA certificate/public key matches
the CA private key.

`CA_SYSTEM_CA_CERT_MATCH=false` is not treated as a failure: the broker CA and Manager system CA are separate
identity materials in the F4 contract. Their required condition here is that each live certificate matches its
own status fingerprint and that the repository-owned F4 TLS material/runtime validators pass, which they did.

The successor authority uses canonical JSON SHA-256 of `_certificate_identity_snapshot()`, so the correct
immediate successor-control baseline is:

```text
CURRENT_CERTIFICATE_IDENTITY_CANONICAL_SHA256=68264cf00af8a5748fc20c17edb4969533d326905bb3e959960b3f2ab0103947
```

The previous live wrapper incorrectly compared that canonical digest against the older path-delimited evidence
digest `0a7bdd...`.

Because no install claim record exists and the authorization was not claimed or consumed, the already explicit
authorization
`N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_LIVE_20261016_01`
remains unconsumed and may continue within the same exact authorized scope after a fresh pre-claim state check.

The exact successor transport tar remains staged only at:

```text
/var/tmp/n3w-f4-reboot-successor-5368acc1eb50f1fc62bbd7c16ff9e64139131a29-53385.tar
sha256=e429201e41c8bb9154fe9c3397e06421bef147dc9117fea8d72184e97edef0a0
```

No successor control file, installed manifest, install claim, reboot claim or reboot actuation exists yet.

```text
CERTIFICATE_IDENTITY_FORENSIC_RESULT=CLOSED_PASS
CERTIFICATE_DRIFT=false
IDENTITY_DIGEST_METHOD_MISMATCH=true
CONTROL_INSTALL_AUTHORIZATION_REMAINS_UNCONSUMED=true
NEXT_ROUTE=N3W_T1_F4_REBOOT_SUCCESSOR_CONTROL_INSTALL_LIVE_20261016_01
```

