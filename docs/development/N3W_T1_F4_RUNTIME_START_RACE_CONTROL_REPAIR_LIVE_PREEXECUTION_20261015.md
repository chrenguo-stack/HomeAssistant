# N3-W T1 F4 Runtime Start Race Control Repair Live — Preexecution — 2026-10-15

~~~text
TASK=N3W_T1_F4_RUNTIME_START_RACE_CONTROL_REPAIR_LIVE_20261015_01
STATUS=AUTHORIZED_READY_TO_EXECUTE

AUTHORIZATION_GRANTED=true
AUTHORIZATION_ID=N3W_T1_F4_RUNTIME_START_RACE_CONTROL_REPAIR_LIVE_20261015_01
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_ALLOWED=true:ONLY_UNTIL_RUNTIME_START_REPAIR_CLAIM

FROM_SOURCE_HEAD=444ed085104080ea68ea073c1ff426f676d70db1
FROM_PACKAGE_MANIFEST_SHA256=b5d06fa0531b23155c41c245ae07f8edc2fc71a0552cb566d96dc83e424eaad1
FROM_LAUNCHER_SHA256=fcbbf9d20f1ca82089f5e3dfd1bd8923cc8893ebaf6a04c36b36e0c46f330a01

REAL_T1_STAGE=STOPPED_RUNTIME
REAL_T1_ERROR_CODE=runtime_service_set_invalid
REAL_T1_ROLLBACK_PROVEN=true
REAL_T1_ROLLBACK_ERROR_COUNT=0
REAL_T1_PRODUCTION_SERVICE_START=false
REAL_T1_PRODUCT_LISTENER_PORTS=[]

FAILED_ACTIVATION_AUTHORIZATION=N3W_T1_F4_ACTIVATE_TO_RUNTIME_STARTED_LIVE_20261015_01
FAILED_ACTIVATION_AUTHORIZATION_CLAIMED=true
FAILED_ACTIVATION_AUTHORIZATION_CONSUMED=true
FAILED_ACTIVATION_AUTHORIZATION_REPLAY_ALLOWED=false

TO_SOURCE_HEAD=8f870d027eea674a4443097ab0d5761542b28a73
TO_SOURCE_CI=13_SUCCESS_0_FAILURE_0_PENDING
REPLACEMENT_ARTIFACT_ID=11978339595
REPLACEMENT_ARTIFACT_ZIP_SHA256=9c05e14c212b265d93af7f753d4a453c4e22357a4bc3da7802c9da3882dd4b3c
REPLACEMENT_CONTROL_TAR_BYTES=204800
REPLACEMENT_CONTROL_TAR_SHA256=e700c747f33695aad5ca73fa93784eb3982c119db951a7128b1cf21854ad7205
REPLACEMENT_PACKAGE_MANIFEST_SHA256=c88c4677cb621f20e7f093bfcfca9d6ef8ae3752b2c8d0bddba9d0bc1732e868
REPLACEMENT_LAUNCHER_SHA256=56445c031e20a7b4870b65dd8d0ee96b019314deb634123904f418630b268907

BOARD_ACCESS=false
REBOOT=false
~~~

Authorized scope is one bounded `repair-stopped-runtime-start` transaction.

The repair must:

- verify the exact failed STOPPED_RUNTIME state and rollback proof;
- verify the consumed failed activation authorization remains no-replay;
- prove product runtime and product listeners are stopped;
- verify every non-launcher F4 package file is unchanged;
- claim and consume this recovery authorization;
- atomically replace only /usr/local/sbin/n3w-t1-f4-activation;
- preserve the failed activation authorization in activation_authorization_history;
- rebind package provenance to the repaired exact source;
- return transaction stage to PREPARED;
- set activation_retry_eligible=true;
- directly execute installed status and eligibility inspect;
- STOP.

Not authorized:

~~~text
replay failed activate
start Broker
start Manager
start Home Assistant
activate with a new authorization
accept-runtime
enable-persistence
certificate-audit
enable-certificate-timer
reboot
board access
~~~

Any result after the durable runtime-start repair claim is no-replay.

Expected PASS boundary:

~~~text
TRANSACTION_STAGE=PREPARED
RUNTIME_START_RACE_REPAIR_PASSED=true
ACTIVATION_RETRY_ELIGIBLE=true
PACKAGE_SOURCE_HEAD=8f870d027eea674a4443097ab0d5761542b28a73
PACKAGE_MANIFEST_SHA256=c88c4677cb621f20e7f093bfcfca9d6ef8ae3752b2c8d0bddba9d0bc1732e868
INSTALLED_LAUNCHER_SHA256=56445c031e20a7b4870b65dd8d0ee96b019314deb634123904f418630b268907
PRODUCTION_SERVICE_START=false
RUNNING_SERVICES=[]
~~~
