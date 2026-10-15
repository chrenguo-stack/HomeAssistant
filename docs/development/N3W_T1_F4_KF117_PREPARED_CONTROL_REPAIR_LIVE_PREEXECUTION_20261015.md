# N3-W T1 F4 KF-117 PREPARED Control Repair Live — Preexecution — 2026-10-15

~~~text
TASK=N3W_T1_F4_KF117_PREPARED_CONTROL_REPAIR_LIVE_20261015_01
STATUS=AUTHORIZED_READY_TO_EXECUTE

AUTHORIZATION_GRANTED=true
AUTHORIZATION_ID=N3W_T1_F4_KF117_PREPARED_CONTROL_REPAIR_LIVE_20261015_01
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_ALLOWED=true:ONLY_UNTIL_CONTROL_REPAIR_CLAIM

DEFECTIVE_SOURCE_HEAD=ad65bf7d10db76f12a09e19b337f4a0c7782894a
DEFECTIVE_PACKAGE_MANIFEST_SHA256=9ed2ce124fbe0e621b4443a655c1cb78285db79b30489e2d41bcf73f4ee5e230
DEFECTIVE_LAUNCHER_SHA256=070f24eb3e53953747392562d425e2c43385c9b5d9c704bc89c4a82bfdc766b7

REPAIRED_SOURCE_HEAD=2b30e541d561e6878525a95ee15aa426cc743595
REPAIRED_SOURCE_CI=13_SUCCESS_0_FAILURE_0_PENDING
REPLACEMENT_ARTIFACT_ID=11976241619
REPLACEMENT_ARTIFACT_ZIP_SHA256=17b3a5443e500629a876dc4fbd3fc1fecd6de9ad861e6ab988dfe2484e3c031d
REPLACEMENT_CONTROL_TAR_SHA256=d2afa7fa033ef4b586a8cd470ed099bea74fbba7b8ac1dd64042c8716642c974
REPLACEMENT_PACKAGE_MANIFEST_SHA256=4407e16e29b3da2fe498f82909dedce85dd6c822bd0cd1f4da5c58330a64a7b4
REPLACEMENT_LAUNCHER_SHA256=2a91b0fe3edfce86187d98eadbe47d3f91a5e40a477f938bf8ff728bd0bef0ff

REAL_T1_PREFLIGHT=PASS
TRANSACTION_STAGE=PREPARED
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
REBOOT=false
~~~

## Authorized scope

This authorization permits one bounded repair transaction only.

Allowed:

~~~text
download and verify replacement exact artifact
transfer replacement control tar to a new private staging path
verify remote tar and package exact bindings
run repair-prepared-control exactly once
claim/consume the successor repair authorization
verify original defective PREPARED source/manifest/launcher binding
prove runtime stopped
prove every non-launcher INSTALL_MAP file is byte-identical
atomically replace only /usr/local/sbin/n3w-t1-f4-activation
rebind installed_files and package source/manifest
return transaction stage to PREPARED
directly execute repaired launcher status and inspect eligibility
STOP
~~~

Not authorized:

~~~text
replay original prepare
delete/recreate F4 transaction
start Broker
start Manager
start Home Assistant
activate
accept-runtime
enable-persistence
certificate-audit
enable-certificate-timer
reboot
board access
~~~

## One-shot rule

When the repair helper durably advances the transaction to CONTROL_REPAIR_CLAIMED:

~~~text
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_ALLOWED=false
~~~

Any failure or ambiguous result after that point is a hard STOP. Do not run the repair command a second time.

## Expected PASS boundary

~~~text
TRANSACTION_STAGE=PREPARED
CONTROL_REPAIR_PASSED=true
PACKAGE_SOURCE_HEAD=2b30e541d561e6878525a95ee15aa426cc743595
PACKAGE_MANIFEST_SHA256=4407e16e29b3da2fe498f82909dedce85dd6c822bd0cd1f4da5c58330a64a7b4
INSTALLED_LAUNCHER_SHA256=2a91b0fe3edfce86187d98eadbe47d3f91a5e40a477f938bf8ff728bd0bef0ff
INSTALLED_LAUNCHER_DIRECT_EXECUTION=PASS
PRODUCTION_SERVICE_START=false
RUNNING_SERVICES=[]
BOARD_ACCESS=false
~~~
