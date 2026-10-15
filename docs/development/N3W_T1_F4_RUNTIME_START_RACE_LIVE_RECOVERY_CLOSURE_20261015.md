# N3-W T1 F4 Runtime Start Race Live Recovery Closure — 2026-10-15

~~~text
TASK=N3W_T1_F4_RUNTIME_START_RACE_CONTROL_REPAIR_LIVE_20261015_01
RESULT=CLOSED_PASS

RECOVERY_AUTHORIZATION_CLAIMED=true
RECOVERY_AUTHORIZATION_CONSUMED=true
RECOVERY_AUTHORIZATION_REPLAY_ALLOWED=false

TRANSACTION_STAGE=PREPARED
RUNTIME_START_RACE_REPAIR_PASSED=true
ACTIVATION_RETRY_ELIGIBLE=true

FAILED_ACTIVATION_AUTHORIZATION=N3W_T1_F4_ACTIVATE_TO_RUNTIME_STARTED_LIVE_20261015_01
FAILED_ACTIVATION_AUTHORIZATION_PRESERVED=true
FAILED_ACTIVATION_AUTHORIZATION_REPLAY_ALLOWED=false

PACKAGE_SOURCE_HEAD=8f870d027eea674a4443097ab0d5761542b28a73
PACKAGE_MANIFEST_SHA256=c88c4677cb621f20e7f093bfcfca9d6ef8ae3752b2c8d0bddba9d0bc1732e868
INSTALLED_LAUNCHER_SHA256=56445c031e20a7b4870b65dd8d0ee96b019314deb634123904f418630b268907
INSTALLED_LAUNCHER_MODE=0755
INSTALLED_LAUNCHER_FIRST_LINE=#!/usr/bin/python3
INSTALLED_LAUNCHER_EXACT=true

BROKER_ACTIVE=inactive
SERVICES_ACTIVE=failed
BROKER_ENABLED=disabled
SERVICES_ENABLED=disabled
CERT_TIMER_ACTIVE=inactive
PRODUCTION_SERVICE_START=false
RUNNING_SERVICES=[]
BOARD_ACCESS=false
REBOOT=false
~~~

The bounded recovery succeeded and returned the real T1 to PREPARED without starting product services.

The failed activation authorization remains permanently consumed and no-replay. It is also preserved in
`activation_authorization_history`. The repaired transaction explicitly sets
`activation_retry_eligible=true`, allowing only a new distinct activation authorization to attempt runtime start.

The residual `SERVICES_ACTIVE=failed` state is the systemd result from the previous fail-closed activation. No
application container is running, Broker is inactive, Broker/Services are disabled, and production_service_start is
false. A future fresh systemctl start is expected to transition the unit anew; no reset-failed mutation was needed
for this recovery gate.

Next boundary:

~~~text
NEXT_ONE_GATE=N3W_T1_F4_ACTIVATE_TO_RUNTIME_STARTED_LIVE_R2_20261015_01
NEW_ACTIVATION_AUTHORIZATION=REQUIRED
AUTO_EXECUTE_NEXT_GATE=false
~~~

The next gate may start ingress guard, Broker, Manager and Home Assistant and must stop at RUNTIME_STARTED.
It does not authorize runtime acceptance, persistence enablement, certificate lifecycle mutation, reboot or board
access.
