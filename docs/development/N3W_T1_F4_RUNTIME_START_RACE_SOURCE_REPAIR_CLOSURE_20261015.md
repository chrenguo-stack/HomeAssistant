# N3-W T1 F4 Runtime Start Race Source Repair Closure — 2026-10-15

~~~text
TASK=N3W_T1_F4_ACTIVATE_RUNTIME_SERVICE_SET_FAILURE_SOURCE_REPAIR_20261015_01
RESULT=CLOSED_PASS_SOURCE_LIVE_RECOVERY_PENDING

FAILED_ACTIVATE_GATE=N3W_T1_F4_ACTIVATE_TO_RUNTIME_STARTED_LIVE_20261015_01
FAILED_ACTIVATE_AUTHORIZATION_CLAIMED=true
FAILED_ACTIVATE_AUTHORIZATION_CONSUMED=true
FAILED_ACTIVATE_AUTHORIZATION_REPLAY_ALLOWED=false

REAL_T1_TRANSACTION_STAGE=STOPPED_RUNTIME
REAL_T1_ERROR_CODE=runtime_service_set_invalid
REAL_T1_ROLLBACK_PROVEN=true
REAL_T1_ROLLBACK_ERROR_COUNT=0
REAL_T1_PRODUCTION_SERVICE_START=false
REAL_T1_PRODUCT_LISTENER_PORTS=[]
REAL_T1_BROKER_ACTIVE=inactive
REAL_T1_SERVICES_ACTIVE=failed

ROOT_CLASS=F4_RUNTIME_STARTUP_OBSERVATION_RACE
PRODUCT_APP_CRASH_PROVEN=false
OOM_PROVEN=false
ROLLBACK_FAILURE=false

DEFECTIVE_SOURCE_HEAD=444ed085104080ea68ea073c1ff426f676d70db1
REPAIRED_SOURCE_HEAD=8f870d027eea674a4443097ab0d5761542b28a73
REPAIRED_SOURCE_CI=13_SUCCESS_0_FAILURE_0_PENDING

REPLACEMENT_ARTIFACT_ID=11978339595
REPLACEMENT_ARTIFACT_ZIP_SHA256=9c05e14c212b265d93af7f753d4a453c4e22357a4bc3da7802c9da3882dd4b3c
REPLACEMENT_CONTROL_TAR_BYTES=204800
REPLACEMENT_CONTROL_TAR_SHA256=e700c747f33695aad5ca73fa93784eb3982c119db951a7128b1cf21854ad7205
REPLACEMENT_PACKAGE_MANIFEST_SHA256=c88c4677cb621f20e7f093bfcfca9d6ef8ae3752b2c8d0bddba9d0bc1732e868
REPLACEMENT_LAUNCHER_SHA256=56445c031e20a7b4870b65dd8d0ee96b019314deb634123904f418630b268907
REPLACEMENT_LAUNCHER_FIRST_LINE=#!/usr/bin/python3

LIVE_RECOVERY_AUTHORIZATION=NOT_GRANTED
BOARD_ACCESS=false
REBOOT=false
~~~

## 1. Real-T1 failure evidence

The first live activation reached Broker readiness, then started the Manager/Home Assistant systemd unit. The transaction
failed with `runtime_service_set_invalid` and the F4 fail-closed path stopped Services and Broker.

Read-only forensic evidence after rollback:

~~~text
TRANSACTION_STAGE=STOPPED_RUNTIME
ERROR_CODE=runtime_service_set_invalid
ROLLBACK_PROVEN=true
ROLLBACK_ERROR_COUNT=0
PRODUCTION_SERVICE_START=false
RUNNING_SERVICES=[]
PRODUCT_LISTENER_PORTS=[]

BROKER_CONTAINER_STARTED_AT=2026-10-15T13:52:10.623613742Z
BROKER_CONTAINER_FINISHED_AT=2026-10-15T13:52:33.138113803Z
BROKER_CONTAINER_EXIT_CODE=0
BROKER_CONTAINER_OOM_KILLED=false

HOMEASSISTANT_CONTAINER_STARTED_AT=2026-10-15T13:52:19.855367585Z
HOMEASSISTANT_CONTAINER_FINISHED_AT=2026-10-15T13:52:31.382541947Z
HOMEASSISTANT_CONTAINER_EXIT_CODE=137
HOMEASSISTANT_CONTAINER_OOM_KILLED=false
HOMEASSISTANT_CONTAINER_DOCKER_ERROR=null

MANAGER_CONTAINER_STARTED_AT=2026-10-15T13:52:19.858474836Z
MANAGER_CONTAINER_FINISHED_AT=2026-10-15T13:52:31.638399502Z
MANAGER_CONTAINER_EXIT_CODE=137
MANAGER_CONTAINER_OOM_KILLED=false
MANAGER_CONTAINER_DOCKER_ERROR=null
~~~

The simultaneous Manager/Home Assistant exit after the F4 error and successful rollback is consistent with the
subsequent `systemctl stop n3wfc4-services-activation.service` rollback. It is not evidence that either application
independently crashed before the F4 service-set check.

## 2. Root cause

`n3wfc4-services-activation.service` is `Type=simple`. Therefore `systemctl start` may return once the compose
process is active, before both application containers are simultaneously observable as running.

The defective source performed one immediate check:

~~~text
systemctl start Services
is-active Services == active
docker compose ps --status running --services
require exact {broker, manager, homeassistant}
~~~

A transient incomplete set was therefore treated as a terminal runtime failure.

## 3. Source repair

The repaired source replaces the one-shot observation with a bounded readiness wait:

~~~text
EXPECTED_RUNTIME_SERVICES={broker,manager,homeassistant}
TIMEOUT=60 seconds
POLL_INTERVAL=1 second
~~~

Rules:

- while the Services unit remains `active` or `activating`, continue observing the service set;
- PASS only when the exact expected three-service set is present;
- fail immediately if an unexpected service appears;
- fail immediately if the Services unit leaves active/activating;
- fail with a bounded timeout if the exact set is not reached within 60 seconds.

This does not convert a real application failure into PASS.

## 4. Consumed activation authority and bounded recovery

The failed activation authorization is permanently consumed and cannot be replayed.

The repaired source adds:

~~~text
repair-stopped-runtime-start
~~~

This recovery is locked to the exact failed state:

~~~text
FROM_SOURCE_HEAD=444ed085104080ea68ea073c1ff426f676d70db1
FROM_PACKAGE_MANIFEST_SHA256=b5d06fa0531b23155c41c245ae07f8edc2fc71a0552cb566d96dc83e424eaad1
FROM_LAUNCHER_SHA256=fcbbf9d20f1ca82089f5e3dfd1bd8923cc8893ebaf6a04c36b36e0c46f330a01

TRANSACTION_STAGE=STOPPED_RUNTIME
ERROR_CODE=runtime_service_set_invalid
ROLLBACK_PROVEN=true
ROLLBACK_ERROR_COUNT=0
PRODUCTION_SERVICE_START=false
~~~

The recovery:

- requires a separate one-shot recovery authorization;
- proves the runtime remains fully stopped;
- proves all non-launcher F4 package files are unchanged;
- atomically replaces only the F4 activation launcher;
- preserves the failed activation authorization in immutable history;
- returns to `PREPARED`;
- sets `activation_retry_eligible=true`;
- never replays the failed activation authorization.

A later runtime retry must use a new, distinct activation authorization.

## 5. Next boundary

~~~text
NEXT_ONE_GATE=N3W_T1_F4_RUNTIME_START_RACE_CONTROL_REPAIR_LIVE_20261015_01
LIVE_RECOVERY_AUTHORIZATION=NOT_GRANTED
AUTO_EXECUTE_NEXT_GATE=false
~~~

That gate may only install the exact repaired launcher and return the transaction to `PREPARED`. It may not start
Broker, Manager or Home Assistant.

After recovery PASS, a separate new activation authorization is required.
