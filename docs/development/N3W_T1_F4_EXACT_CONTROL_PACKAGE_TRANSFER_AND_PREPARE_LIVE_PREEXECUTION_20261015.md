# N3-W T1 F4 Exact Control Package Transfer and PREPARE Live — Preexecution — 2026-10-15

~~~text
TASK=N3W_T1_F4_EXACT_CONTROL_PACKAGE_TRANSFER_AND_PREPARE_LIVE_20261015_01
STATUS=AUTHORIZED_READY_TO_EXECUTE

AUTHORIZATION_GRANTED=true
AUTHORIZATION_ID=N3W_T1_F4_EXACT_CONTROL_PACKAGE_TRANSFER_AND_PREPARE_LIVE_20261015_01
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_ALLOWED=true:ONLY_UNTIL_FIRST_DURABLE_F4_TRANSACTION_CLAIM

SOURCE_HEAD=ad65bf7d10db76f12a09e19b337f4a0c7782894a
SOURCE_PR=550
SOURCE_PR_STATE=OPEN_DRAFT
SOURCE_PR_MERGEABLE=true

PREAUTH_PR=553
PREAUTH_HEAD=7dee28e66b33c7786badc4bfd339ffd2eb2cf838
PREAUTH_CI=12_SUCCESS_0_FAILURE_0_PENDING
REAL_T1_READONLY_PREAUTH=CLOSED_PASS

ARTIFACT_RUN_ID=38723623711
ARTIFACT_ID=11967018401
ARTIFACT_NAME=n3w-t1-f4-control-package-ad65bf7d10db76f12a09e19b337f4a0c7782894a
ARTIFACT_DIGEST=sha256:6308fdc64347949d463f251713c359571b40f067182cfd4d686ba4495d6d162f
CONTROL_TAR_SHA256=13ecd035890dc88731bac6909ed1cb13ca33afd86b04d5d147d24003afbcf9f7
PACKAGE_MANIFEST_SHA256=9ed2ce124fbe0e621b4443a655c1cb78285db79b30489e2d41bcf73f4ee5e230
PACKAGE_SOURCE_HEAD=ad65bf7d10db76f12a09e19b337f4a0c7782894a
PACKAGE_FILE_COUNT=8

TARGET_LOCATOR=PRIVATE_USER_MANAGED:NOT_PERSISTED_IN_PUBLIC_GITHUB
BOARD_ACCESS=false
REBOOT=false
~~~

## Authorized live scope

This authorization permits exactly one F4 PREPARE transaction on the already-preauthorized T1:

~~~text
1. acquire exact GitHub artifact
2. verify exact control tar and package manifest
3. create one private transaction-owned remote staging directory
4. transfer exact control tar
5. verify remote tar SHA256
6. safely extract exact f4-package
7. validate package using its exact staged F4 consumer
8. execute PREPARE exactly once
9. durable creation of F4_ACTIVATION_TRANSACTION.json claims/consumes authorization
10. create FACTORY_ACCEPTED.json
11. install exact canonical F4 control material
12. reach PREPARED
13. read-only postcheck
14. STOP
~~~

Not authorized:

~~~text
Broker start
Manager start
Home Assistant start
activate
accept-runtime
enable-persistence
certificate-audit
enable-certificate-timer
reboot
board access
~~~

## One-shot rule

Before durable claim, a transport/extraction failure may be cleaned only within the exact temporary staging path.
After durable F4 transaction claim:

~~~text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_ALLOWED=false
BLIND_RETRY=false
DELETE_TRANSACTION_TO_RETRY=false
~~~

Any non-PASS or ambiguous result after claim requires STOP and state classification. Do not run PREPARE a second time.

## Expected PASS boundary

~~~text
F4_TRANSACTION_PRESENT=true
FACTORY_ACCEPTED_PRESENT=true
F4_STAGE=PREPARED
ACTIVATION_MATERIAL_INSTALLED=true
BROKER_ACTIVE=false
SERVICES_ACTIVE=false
CERTIFICATE_TIMER_ENABLED=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
~~~
