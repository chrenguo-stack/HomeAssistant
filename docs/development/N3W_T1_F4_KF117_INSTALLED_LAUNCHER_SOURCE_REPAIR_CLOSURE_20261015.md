# N3-W T1 F4 KF-117 Installed Launcher Source Repair Closure — 2026-10-15

~~~text
TASK=N3W_T1_F4_KF117_INSTALLED_LAUNCHER_SOURCE_REPAIR_20261015_01
RESULT=CLOSED_PASS_SOURCE_LIVE_REPAIR_PENDING

DEFECTIVE_SOURCE_HEAD=ad65bf7d10db76f12a09e19b337f4a0c7782894a
FIRST_LIVE_PREPARE=PASS
FIRST_LIVE_AUTHORIZATION_CLAIMED=true
FIRST_LIVE_AUTHORIZATION_CONSUMED=true
FIRST_LIVE_AUTHORIZATION_REPLAY_ALLOWED=false
FIRST_LIVE_PRODUCTION_SERVICE_START=false

POST_PREPARE_FAILURE=INSTALLED_LAUNCHER_DIRECT_EXECUTION_FAILED
ROOT_CAUSE=MISSING_PYTHON_SHEBANG
PRODUCT_RUNTIME_FAILURE=false
SOURCE_CONTROL_MATERIAL_DEFECT=true

REPAIRED_SOURCE_HEAD=2b30e541d561e6878525a95ee15aa426cc743595
REPAIRED_SOURCE_CI=13_SUCCESS_0_FAILURE_0_PENDING

REPLACEMENT_ARTIFACT_ID=11976241619
REPLACEMENT_ARTIFACT_DIGEST=sha256:17b3a5443e500629a876dc4fbd3fc1fecd6de9ad861e6ab988dfe2484e3c031d
REPLACEMENT_CONTROL_TAR_SHA256=d2afa7fa033ef4b586a8cd470ed099bea74fbba7b8ac1dd64042c8716642c974
REPLACEMENT_PACKAGE_MANIFEST_SHA256=4407e16e29b3da2fe498f82909dedce85dd6c822bd0cd1f4da5c58330a64a7b4
REPLACEMENT_LAUNCHER_SHA256=2a91b0fe3edfce86187d98eadbe47d3f91a5e40a477f938bf8ff728bd0bef0ff
REPLACEMENT_LAUNCHER_FIRST_LINE=#!/usr/bin/python3
REPOSITORY_LAUNCHER_MODE=100755

LIVE_CONTROL_REPAIR_AUTHORIZATION=NOT_GRANTED
BOARD_ACCESS=false
REBOOT=false
~~~

## Closure

The original PREPARE command returned PASS only after the durable transaction reached PREPARED and exact control
material was installed. The successor read-only status call then executed the installed launcher directly and the
shell parsed its first Python statement as shell syntax.

The exact source shows why: the tracked F4 activation host had no shebang, while INSTALL_MAP installed it mode 0755
and Broker/Services systemd units call it directly in ExecStartPre.

The source repair:

- restores `#!/usr/bin/python3`;
- tracks the launcher executable;
- adds CI that checks executable mode, exact shebang and direct `--help` execution;
- adds regression coverage;
- adds a bounded `repair-prepared-control` route locked to the exact known defective source/manifest/launcher;
- preserves the original PREPARE authorization as consumed/no-replay;
- uses a distinct successor repair authorization for any real-T1 repair;
- permits only the activation launcher payload to differ from the installed PREPARED package;
- rebinds installed-file and package provenance only after atomic replacement;
- stops fail-closed on any repair error.

No live repair has been executed.

## Next boundary

First perform one minimal read-only classification using Python explicitly, because the installed defective file cannot
be invoked directly.

Expected state:

~~~text
transaction_present=true
factory_accepted_present=true
transaction_stage=PREPARED
production_service_start=false
running_services=[]
installed launcher SHA256=070f24eb...
installed launcher first line lacks shebang
~~~

If exact PREPARED state is confirmed, prepare the successor live repair gate.

~~~text
NEXT_ONE_GATE=N3W_T1_F4_KF117_PREPARED_CONTROL_REPAIR_READONLY_PREFLIGHT_20261015_01
AUTO_EXECUTE_LIVE_REPAIR=false
~~~


## Real-T1 PREPARED repair preflight

~~~text
READONLY_PREFLIGHT=CLOSED_PASS
TRANSACTION_STAGE=PREPARED
FACTORY_ACCEPTED_PRESENT=true
PRODUCTION_SERVICE_START=false
RUNNING_SERVICES=[]
BROKER_ACTIVE_STATE=inactive
SERVICES_ACTIVE_STATE=inactive

INSTALLED_LAUNCHER_SHA256=070f24eb3e53953747392562d425e2c43385c9b5d9c704bc89c4a82bfdc766b7
INSTALLED_LAUNCHER_MODE=0755
INSTALLED_LAUNCHER_HAS_PYTHON_SHEBANG=false

NEXT_ONE_GATE=N3W_T1_F4_KF117_PREPARED_CONTROL_REPAIR_LIVE_20261015_01
LIVE_REPAIR_AUTHORIZATION=NOT_GRANTED
~~~

The original PREPARE is not replayable. The successor live repair is limited to the separately authorized exact
control repair route and must stop again at PREPARED.
