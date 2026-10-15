# N3-W T1 F4 Runtime Continuation Authority Control Repair Live — Preexecution — 2026-10-15

~~~text
TASK=N3W_T1_F4_RUNTIME_CONTINUATION_AUTHORITY_CONTROL_REPAIR_LIVE_20261015_01
STATUS=AUTHORIZED_READY_TO_EXECUTE

AUTHORIZATION_GRANTED=true
AUTHORIZATION_ID=N3W_T1_F4_RUNTIME_CONTINUATION_AUTHORITY_CONTROL_REPAIR_LIVE_20261015_01
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_ALLOWED=true:ONLY_UNTIL_RUNTIME_CONTINUATION_REPAIR_CLAIM

REAL_T1_STAGE=RUNTIME_STARTED
REAL_T1_RUNTIME_STARTED=true
REAL_T1_RUNTIME_ACCEPTANCE_REQUIRED=true
REAL_T1_RUNNING_SERVICES=[broker,homeassistant,manager]
REAL_T1_PRODUCTION_SERVICE_START=true
REAL_T1_PERSISTENCE_ENABLED=false

FROM_SOURCE_HEAD=8f870d027eea674a4443097ab0d5761542b28a73
FROM_PACKAGE_MANIFEST_SHA256=c88c4677cb621f20e7f093bfcfca9d6ef8ae3752b2c8d0bddba9d0bc1732e868
FROM_LAUNCHER_SHA256=56445c031e20a7b4870b65dd8d0ee96b019314deb634123904f418630b268907

TO_SOURCE_HEAD=ffcbb1a890e42ac776c6d90000bf3f25195da01d
TO_SOURCE_CI=13_SUCCESS_0_FAILURE_0_PENDING

REPLACEMENT_ARTIFACT_ID=11982052678
REPLACEMENT_ARTIFACT_ZIP_SHA256=beb128f237d2e07f29a5f9a32d35a535de1bf8b2a099a5a3c55fbfff7d34071b
REPLACEMENT_CONTROL_TAR_BYTES=215040
REPLACEMENT_CONTROL_TAR_SHA256=9d24125d136ed5a2c5e8f98687a2718a8caa50c565a8fa0d389e4ceabd09c074
REPLACEMENT_PACKAGE_MANIFEST_SHA256=4df1d95b0849aa4ca574f31f8fd55e57fe118fba1c5913d2d8b3f96e286ec669
REPLACEMENT_LAUNCHER_SHA256=f7f742505f439675fb19ecf8f98b8235703d6e2a1c5c9217ecfe01a025be3c8b

RUNTIME_ACCEPTANCE_AUTHORIZED=false
PERSISTENCE_AUTHORIZED=false
CERTIFICATE_AUDIT_AUTHORIZED=false
CERTIFICATE_TIMER_AUTHORIZED=false
REBOOT=false
BOARD_ACCESS=false
~~~

Authorized mutation is limited to one bounded
`repair-runtime-continuation-authority` transaction.

The repair must:

- verify the exact currently installed RUNTIME_STARTED source/manifest/launcher binding;
- verify the product runtime is active with exactly Broker, Manager and Home Assistant;
- prove every non-launcher F4 package payload remains byte-identical;
- snapshot the running product containers before the claim;
- durably claim/consume this control-repair authorization;
- atomically replace only `/usr/local/sbin/n3w-t1-f4-activation`;
- prove the exact same runtime container identities and start timestamps remain after replacement;
- rebind the package source/manifest and installed launcher binding;
- remain at `RUNTIME_STARTED`;
- STOP.

Not authorized:

~~~text
restart Broker
restart Manager
restart Home Assistant
accept-runtime
enable-persistence
certificate-audit
enable-certificate-timer
reboot
board access
~~~

Any result after the durable repair claim is no-replay.

Expected PASS boundary:

~~~text
TRANSACTION_STAGE=RUNTIME_STARTED
RUNTIME_CONTINUATION_AUTHORITY_REPAIR_PASSED=true
PACKAGE_SOURCE_HEAD=ffcbb1a890e42ac776c6d90000bf3f25195da01d
PACKAGE_MANIFEST_SHA256=4df1d95b0849aa4ca574f31f8fd55e57fe118fba1c5913d2d8b3f96e286ec669
INSTALLED_LAUNCHER_SHA256=f7f742505f439675fb19ecf8f98b8235703d6e2a1c5c9217ecfe01a025be3c8b
RUNNING_SERVICES=[broker,homeassistant,manager]
PRODUCTION_SERVICE_START=true
PERSISTENCE_ENABLED=false
~~~
