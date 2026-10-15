# N3-W T1 F4 Activation Authority Boundary Repair — 2026-10-15

~~~text
TASK=N3W_T1_F4_ACTIVATE_TO_RUNTIME_STARTED_LIVE_20261015_01
STATUS=AUTHORIZED_BUT_BLOCKED_BEFORE_LIVE_START

ACTIVATE_AUTHORIZATION_GRANTED=true
ACTIVATE_AUTHORIZATION_ID=N3W_T1_F4_ACTIVATE_TO_RUNTIME_STARTED_LIVE_20261015_01
ACTIVATE_AUTHORIZATION_CLAIMED=false
ACTIVATE_AUTHORIZATION_CONSUMED=false

BLOCKER=OLD_ACTIVATE_REUSED_PREPARE_AUTHORIZATION_ID
LIVE_PRODUCT_MUTATION_FOR_ACTIVATE=false

REPAIRED_SOURCE_HEAD=444ed085104080ea68ea073c1ff426f676d70db1
REPAIRED_SOURCE_CI=13_SUCCESS_0_FAILURE_0_PENDING

REPAIRED_ARTIFACT_ID=11976711799
REPAIRED_ARTIFACT_ZIP_SHA256=0344e9848f96c88c013b8f630dcb996dfe8cf8237c260ec6abad2befee9540fb
REPAIRED_CONTROL_TAR_SHA256=1af3e11662c556194fc68395aa0ed31f571ee48dcfd54cb7d331e18e033e888a
REPAIRED_PACKAGE_MANIFEST_SHA256=b5d06fa0531b23155c41c245ae07f8edc2fc71a0552cb566d96dc83e424eaad1
REPAIRED_LAUNCHER_SHA256=fcbbf9d20f1ca82089f5e3dfd1bd8923cc8893ebaf6a04c36b36e0c46f330a01

INSTALLED_T1_SOURCE_HEAD=2b30e541d561e6878525a95ee15aa426cc743595
INSTALLED_T1_STAGE=PREPARED
INSTALLED_T1_RUNTIME_STOPPED=true
~~~

The pre-live source review found that the old activate command required the durable PREPARE authorization ID.
That would violate the project's separate-live-authorization rule and reuse an already-consumed authority.

The repaired source now:

- requires a fresh activation authorization ID;
- rejects the original PREPARE authorization;
- rejects the earlier KF-117 control-repair authorization;
- rejects the activation-authority-control-repair authorization;
- durably records ACTIVATION_CLAIMED before any guard/Broker/Services live mutation;
- permanently marks the activation authorization consumed/no-replay;
- preserves fail-closed rollback semantics.

The real T1 still has the previous repaired launcher source 2b30e541... installed. A bounded PREPARED control repair
must therefore update only that launcher before the already-granted activation gate can run.

The source includes the exact successor command:

~~~text
repair-prepared-activation-authority
~~~

It is locked to:

~~~text
FROM_SOURCE_HEAD=2b30e541d561e6878525a95ee15aa426cc743595
FROM_MANIFEST_SHA256=4407e16e29b3da2fe498f82909dedce85dd6c822bd0cd1f4da5c58330a64a7b4
FROM_LAUNCHER_SHA256=2a91b0fe3edfce86187d98eadbe47d3f91a5e40a477f938bf8ff728bd0bef0ff
TRANSACTION_STAGE=PREPARED
PRODUCT_RUNTIME_STOPPED=true
~~~

The repair allows only the launcher payload to differ from the currently installed PREPARED package, claims a
separate one-shot repair authorization, atomically replaces the launcher, rebinds package provenance, and returns
to PREPARED.

~~~text
NEXT_ONE_GATE=N3W_T1_F4_ACTIVATION_AUTHORITY_CONTROL_REPAIR_LIVE_20261015_01
REPAIR_LIVE_AUTHORIZATION=NOT_GRANTED

AFTER_REPAIR_PASS=
RESUME_ALREADY_GRANTED_N3W_T1_F4_ACTIVATE_TO_RUNTIME_STARTED_LIVE_20261015_01

AUTO_EXECUTE_REPAIR=false
BOARD_ACCESS=false
REBOOT=false
~~~
