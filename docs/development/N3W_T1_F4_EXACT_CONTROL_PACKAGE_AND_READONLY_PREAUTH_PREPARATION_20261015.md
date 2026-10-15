# N3-W T1 F4 Exact Control Package and Read-only Preauthorization Preparation — 2026-10-15

~~~text
TASK=N3W_T1_F4_EXACT_CONTROL_PACKAGE_AND_READONLY_PREAUTH_PREPARATION_20261015_01
RESULT=CLOSED_PASS_SOURCE_PREPARATION

SOURCE_HEAD=ad65bf7d10db76f12a09e19b337f4a0c7782894a
SOURCE_CI=13_SUCCESS_0_FAILURE_0_PENDING

ARTIFACT_ID=11967018401
ARTIFACT_NAME=n3w-t1-f4-control-package-ad65bf7d10db76f12a09e19b337f4a0c7782894a
ARTIFACT_ZIP_SHA256=6308fdc64347949d463f251713c359571b40f067182cfd4d686ba4495d6d162f
CONTROL_TAR_SHA256=13ecd035890dc88731bac6909ed1cb13ca33afd86b04d5d147d24003afbcf9f7
PACKAGE_MANIFEST_SHA256=9ed2ce124fbe0e621b4443a655c1cb78285db79b30489e2d41bcf73f4ee5e230
PACKAGE_FILE_COUNT=8
PACKAGE_SOURCE_HEAD=ad65bf7d10db76f12a09e19b337f4a0c7782894a

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
~~~

## 1. Purpose

This gate freezes the exact package acquisition, local integrity checks, real-T1 read-only preauthorization
contract, live transfer boundary and safe STOP conditions before any F4 mutation.

It does not access the real T1 and does not transfer, extract, install or execute the F4 package on T1.

## 2. Exact artifact authority

The GitHub artifact ZIP was downloaded and re-hashed locally during this preparation.

Observed exact bindings:

~~~text
ZIP_SHA256=6308fdc64347949d463f251713c359571b40f067182cfd4d686ba4495d6d162f
ZIP_FILE_COUNT=3

ZIP_CONTENTS=
  n3w-t1-f4-control-package.tar
  n3w-t1-f4-control-package.tar.sha256
  build-report.json

CONTROL_TAR_SHA256=13ecd035890dc88731bac6909ed1cb13ca33afd86b04d5d147d24003afbcf9f7

BUILD_REPORT_STATUS=PASS
BUILD_REPORT_SOURCE_HEAD=ad65bf7d10db76f12a09e19b337f4a0c7782894a
BUILD_REPORT_MANIFEST_SHA256=9ed2ce124fbe0e621b4443a655c1cb78285db79b30489e2d41bcf73f4ee5e230
BUILD_REPORT_FILE_COUNT=8
BUILD_REPORT_SECRET_VALUES_INCLUDED=false
BUILD_REPORT_PRODUCTION_SERVICE_START=false
BUILD_REPORT_BOARD_ACCESS=false
~~~

The tar contains one top-level directory:

~~~text
f4-package/
~~~

with these exact eight files:

~~~text
infra/n3w-t1/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
infra/n3w-t1/f4/n3wfc4-broker-activation.service
infra/n3w-t1/f4/n3wfc4-broker-certificate-lifecycle.service
infra/n3w-t1/f4/n3wfc4-services-activation.service
infra/n3w-t1/systemd/n3wfc4-broker-certificate-lifecycle.timer
tools/n3w_broker_certificate_lifecycle.py
tools/n3w_t1_broker_authenticated_readiness.py
tools/n3w_t1_f4_activation_host.py
~~~

The package manifest source head and manifest SHA256 are exact and are the same values required by the F4
consumer before it can claim the F4 authorization.

## 3. Local acquisition and verification contract

Before every real-T1 F4 attempt:

1. acquire artifact ID 11967018401 or a previously cached byte-identical ZIP;
2. SHA256 the ZIP and require the exact ZIP hash above;
3. extract only the three expected ZIP members into a new local private temporary directory;
4. SHA256 the control tar and require the exact tar hash above;
5. parse build-report.json and require exact source head, manifest SHA, file count and safety booleans;
6. extract the control tar into a new private directory;
7. reject symlinks, absolute paths, dot-dot traversal, unexpected top-level entries or extra files;
8. invoke the exact source-head F4 consumer validation against f4-package;
9. require source head, manifest SHA, file set, per-file size/SHA256 and safety flags all PASS;
10. remove temporary local extraction after the gate or preserve only a verified cache entry.

A local artifact mismatch is a STOP before T1 access.

## 4. Real-T1 read-only preauthorization contract

The later read-only preauthorization gate may use SSH but must perform no remote file creation, deletion, chmod,
chown, package transfer, systemd enable/start/stop/reload, Docker create/start/stop, certificate mutation or board
access.

It must prove the real T1 still satisfies the exact F3/F4 entry boundary.

Required PASS evidence:

~~~text
PROVISION_VERIFY=PASS
PROVISION_STATE=DEVICE_READY
DEPLOYED_RELEASE_ID=6ac82ae0872b05644e59470ffef7307dad14d359
CURRENT_HOST_BINDING=PASS
CURRENT_SYSTEM_BINDING=PASS

FACTORY_ACCEPTED_PRESENT=false
F4_TRANSACTION_PRESENT=false
F4_RUNTIME_ACCEPTANCE_PRESENT=false

PRODUCT_CONTAINERS=0
PRODUCT_LISTENERS=0

INGRESS_GUARD_ACTIVE=true
INGRESS_GUARD_ENABLED=true
PROVISION_RESUME_ENABLED=true

BROKER_ACTIVATION_ACTIVE=false
SERVICES_ACTIVATION_ACTIVE=false
CERTIFICATE_TIMER_ACTIVE=false

BROKER_ACTIVATION_ENABLED!=enabled
SERVICES_ACTIVATION_ENABLED!=enabled
CERTIFICATE_TIMER_ENABLED!=enabled

F4_CANONICAL_CONTROL_TARGETS_ABSENT=true
F4_CERTIFICATE_STATUS_ROOT_ABSENT_OR_EMPTY=true

EXACT_THREE_PRODUCT_IMAGES_PRESENT=true
PUBLIC_PRODUCT_SOURCE_PRESENT=true
PER_DEVICE_IDENTITY_PRESENT=true
PER_DEVICE_SERVICE_CREDENTIALS_PRESENT=true
PER_DEVICE_TLS_PRESENT=true

BOARD_ACCESS=false
~~~

Read-only preauthorization must not print raw SYSTEM_ID, host identity, credentials, passwords, private keys or
the private T1 locator.

## 5. Remote canonical-target preflight

Because F4 prepare is a first-install transaction, the following canonical targets must be absent before the later
live claim:

~~~text
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
~~~

An unexpected existing file is not overwritten and is a STOP for forensic classification.

The already-staged ingress-guard executable/unit and provisioning-resume unit are predecessor authorities and are
not part of this absence list.

## 6. Capacity contract

The exact control package is small:

~~~text
CONTROL_TAR_BYTES=174080
MANIFEST_DECLARED_FILE_BYTES=157546
~~~

The later preauthorization should report remote free bytes but must not introduce a large arbitrary fixed reserve.

For the live transfer/install path, required temporary capacity is derived from exact material:

~~~text
remote_staging_tar
+ extracted F4 package
+ canonical installed copy
+ bounded transaction/report/status metadata
~~~

If capacity cannot be proven for that bounded material, STOP before transfer.

## 7. Live transfer boundary

The later live F4 mutation gate may transfer the already-verified control tar only after:

~~~text
READONLY_PREAUTH=CLOSED_PASS
NEW_F4_AUTHORIZATION_GRANTED=true
~~~

Remote transfer uses a new private randomized staging directory.

The transfer path must:

~~~text
copy tar to temporary remote pathname
verify exact remote tar size + SHA256
atomically publish the final staged tar name
extract into transaction-owned staging directory
reject symlink/path traversal/extra files
verify exact package manifest using the staged source helper
~~~

Remote staging before the durable F4 claim is transport-only state. If transfer/extraction fails before claim,
cleanup is limited to the exact transaction-owned staging directory and the F4 authorization remains unclaimed.

No canonical F4 target may be modified before the helper reaches the durable F4 transaction claim.

## 8. Live claim boundary

The exact live command must use one new F4 authorization ID and the exact package bindings:

~~~text
n3w-t1-f4-activation prepare
  --authorization-id <new F4 authorization>
  --confirm "PREPARE F4 ACTIVATION: YES"
  --package-root <verified staged f4-package>
  --package-manifest-sha256 9ed2ce124fbe0e621b4443a655c1cb78285db79b30489e2d41bcf73f4ee5e230
  --package-source-head ad65bf7d10db76f12a09e19b337f4a0c7782894a
~~~

The authorization is claimed/consumed when the durable F4 transaction record is created.

After that point:

~~~text
replay_allowed=false
blind retry=false
delete transaction to retry=false
reuse provisioning authorization=false
~~~

## 9. Live sequence after claim

The later live F4 execution remains split by STOP points:

~~~text
A. prepare
   → FACTORY_ACCEPTED
   → exact control material installed
   → PREPARED
   → STOP / evidence

B. activate
   → Broker
   → authenticated readiness
   → Manager + HA
   → RUNTIME_STARTED
   → STOP / evidence

C. accept-runtime
   → runtime end-to-end acceptance
   → RUNTIME_ACCEPTED
   → STOP / evidence

D. enable-persistence
   → Broker + Services enable only
   → PERSISTENCE_ENABLED
   → STOP / evidence

E. certificate-audit
   → first per-device lifecycle audit
   → certificate_first_audit_passed=true
   → STOP / evidence

F. enable-certificate-timer
   → timer enable only
   → PRE_REBOOT_READY
   → STOP
~~~

Reboot is not part of that authorization and remains a later gate.

## 10. Failure handling

Preclaim failure:

~~~text
authorization_claimed=false
canonical_product_mutation=false
cleanup_only_transaction_staging=true
~~~

Postclaim failure:

~~~text
authorization_consumed=true
replay_allowed=false
FACTORY_ACCEPTED/transaction preserved
source-defined fail-closed rollback used
manual classification required before any successor live authorization
~~~

Missing log text alone is never sufficient to classify a product failure.

## 11. Gate closure

~~~text
F4_EXACT_CONTROL_PACKAGE_BINDING=CLOSED_PASS
F4_READONLY_PREAUTH_CONTRACT=FROZEN
F4_LIVE_TRANSFER_CONTRACT=FROZEN
F4_LIVE_CLAIM_BOUNDARY=FROZEN
F4_LIVE_SEQUENCE_STOP_POINTS=FROZEN

REAL_T1_READONLY_PREAUTH=false
LIVE_F4_AUTHORIZATION=NOT_GRANTED
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false

CURRENT_STOP_POINT=AFTER_F4_EXACT_PACKAGE_PREAUTH_PREPARATION_BEFORE_REAL_T1_READONLY_PREAUTH

NEXT_ONE_GATE=N3W_T1_F4_REAL_T1_READONLY_PREAUTH_20261015_01
AUTO_EXECUTE_LIVE_F4=false
~~~
