# N3-W T1 F4 KF-118 Activation Authority Control Repair Live — Preexecution — 2026-10-15

~~~text
TASK=N3W_T1_F4_ACTIVATION_AUTHORITY_CONTROL_REPAIR_LIVE_20261015_01
STATUS=AUTHORIZED_READY_TO_EXECUTE

AUTHORIZATION_GRANTED=true
AUTHORIZATION_ID=N3W_T1_F4_ACTIVATION_AUTHORITY_CONTROL_REPAIR_LIVE_20261015_01
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_ALLOWED=true:ONLY_UNTIL_ACTIVATION_AUTHORITY_REPAIR_CLAIM

FROM_SOURCE_HEAD=2b30e541d561e6878525a95ee15aa426cc743595
FROM_PACKAGE_MANIFEST_SHA256=4407e16e29b3da2fe498f82909dedce85dd6c822bd0cd1f4da5c58330a64a7b4
FROM_LAUNCHER_SHA256=2a91b0fe3edfce86187d98eadbe47d3f91a5e40a477f938bf8ff728bd0bef0ff

TO_SOURCE_HEAD=444ed085104080ea68ea073c1ff426f676d70db1
TO_SOURCE_CI=13_SUCCESS_0_FAILURE_0_PENDING
REPLACEMENT_ARTIFACT_ID=11976711799
REPLACEMENT_ARTIFACT_ZIP_SHA256=0344e9848f96c88c013b8f630dcb996dfe8cf8237c260ec6abad2befee9540fb
REPLACEMENT_CONTROL_TAR_BYTES=194560
REPLACEMENT_CONTROL_TAR_SHA256=1af3e11662c556194fc68395aa0ed31f571ee48dcfd54cb7d331e18e033e888a
REPLACEMENT_PACKAGE_MANIFEST_SHA256=b5d06fa0531b23155c41c245ae07f8edc2fc71a0552cb566d96dc83e424eaad1
REPLACEMENT_LAUNCHER_SHA256=fcbbf9d20f1ca82089f5e3dfd1bd8923cc8893ebaf6a04c36b36e0c46f330a01

REAL_T1_STAGE=PREPARED
REAL_T1_RUNTIME_STOPPED=true
ACTIVATE_GATE_AUTHORIZATION_ALREADY_GRANTED=true
ACTIVATE_GATE_AUTHORIZATION_CLAIMED=false
ACTIVATE_GATE_AUTHORIZATION_CONSUMED=false

BOARD_ACCESS=false
REBOOT=false
~~~

Authorized mutation is limited to one bounded PREPARED launcher update using
`repair-prepared-activation-authority`.

The repair must:
- verify the currently installed exact source/manifest/launcher binding;
- prove runtime stopped and product listeners absent;
- prove every non-launcher INSTALL_MAP file is byte-identical;
- claim/consume this repair authorization before replacement;
- atomically replace only /usr/local/sbin/n3w-t1-f4-activation;
- rebind installed_files and package source/manifest;
- return transaction to PREPARED;
- directly execute status and eligibility inspect;
- STOP.

This authorization does not allow Broker/Manager/Home Assistant start, activate, runtime acceptance, persistence,
certificate lifecycle mutation, reboot or board access.

After PASS, resume the already-granted
`N3W_T1_F4_ACTIVATE_TO_RUNTIME_STARTED_LIVE_20261015_01` gate. Do not request a second activation authorization.

Any result after the durable repair claim is no-replay.
