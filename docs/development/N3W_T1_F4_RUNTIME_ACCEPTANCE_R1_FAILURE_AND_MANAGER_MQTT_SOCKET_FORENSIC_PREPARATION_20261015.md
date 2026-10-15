## 2026-10-15 — F4 runtime acceptance R1 stopped-state forensic: Manager MQTT session stayed connected until rollback

~~~text
TASK=N3W_T1_F4_RUNTIME_ACCEPTANCE_R1_MANAGER_MQTT_SOCKET_FORENSIC_READONLY_20261015_01
RESULT=PARTIAL_PASS_ROOT_CAUSE_NARROWED

LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START_MUTATION=false
BOARD_ACCESS=false

TRANSACTION_STAGE=STOPPED_RUNTIME_ACCEPTANCE
ERROR_CODE=manager_mqtt_socket_count_invalid
ROLLBACK_PROVEN=true
ROLLBACK_ERROR_COUNT=0
PRODUCT_LISTENER_PORTS=[]
RUNTIME_ACCEPTANCE_AUTHORIZATION=CONSUMED_NO_REPLAY
RUNTIME_ACCEPTANCE_REPORT_PRESENT=false

MANAGER_CONTAINER_RESTART_COUNT=0
MANAGER_CONTAINER_OOM_KILLED=false
MANAGER_CONTAINER_EXIT_CODE=137
MANAGER_STARTED_AT=2026-10-15T14:32:04.514214222Z
MANAGER_FINISHED_AT=2026-10-15T15:30:36.088141749Z

BROKER_MANAGER_AUTHENTICATED_CONNECT_AT=2026-10-15T14:32:15.264549180Z
BROKER_MANAGER_TLS_NEGOTIATED_AT=2026-10-15T14:32:15.264686765Z
BROKER_MANAGER_DISCONNECT_AT=2026-10-15T15:30:36.082122041Z
MANAGER_DISCONNECT_MATCHES_ROLLBACK_STOP=true

ACCEPTANCE_TLS_PROBE_CONNECT_AT=2026-10-15T15:30:08.252808824Z
ACCEPTANCE_TLS_PROBE_DISCONNECT_AT=2026-10-15T15:30:08.311452766Z

REAL_MANAGER_MQTT_CONNECTIVITY_FAILURE_PROVEN=false
MANAGER_MQTT_SESSION_CONTINUITY_THROUGH_ACCEPTANCE_FAILURE=PROVEN_BY_BROKER_LOG
SOCKET_COUNT_ORACLE_CONTRADICTS_BROKER_SESSION_EVIDENCE=true
ROOT_CAUSE=NARROWED_TO_SOCKET_COUNT_ORACLE_PATH
EXACT_SOCKET_PROBE_MECHANISM_ROOT_CAUSE=TBD
~~~

The Broker retained one authenticated Manager MQTT client continuously from 14:32:15.264Z until 15:30:36.082Z.
The Manager container finished at 15:30:36.088Z, so the Manager disconnect aligns with the fail-closed rollback stop,
not with a spontaneous MQTT failure before acceptance.

The unauthenticated 8883 connection at 15:30:08.252Z matches the acceptance source's host-side live TLS probe and
closed at 15:30:08.311Z. It is separate from the long-lived authenticated Manager session.

Therefore this failure must not be classified as a proven Manager/Broker connectivity defect. The next read-only
substep is to identify why the in-container socket-owner probe returned a count other than exactly one despite
Broker-side evidence of the live Manager MQTT session.

# N3-W T1 F4 Runtime Acceptance R1 Failure and Manager MQTT Socket Forensic Preparation — 2026-10-15

~~~text
TASK=N3W_T1_F4_RUNTIME_ACCEPTANCE_LIVE_20261015_01
RESULT=FAILED_STOPPED_FAIL_CLOSED

RUNTIME_ACCEPTANCE_AUTHORIZATION_CLAIMED=true
RUNTIME_ACCEPTANCE_AUTHORIZATION_CONSUMED=true
RUNTIME_ACCEPTANCE_AUTHORIZATION_REPLAY_ALLOWED=false

PRECHECK=PASS
PRECHECK_STAGE=RUNTIME_STARTED
PRECHECK_SOURCE_HEAD=ffcbb1a890e42ac776c6d90000bf3f25195da01d
PRECHECK_PACKAGE_MANIFEST_SHA256=4df1d95b0849aa4ca574f31f8fd55e57fe118fba1c5913d2d8b3f96e286ec669
PRECHECK_LAUNCHER_SHA256=f7f742505f439675fb19ecf8f98b8235703d6e2a1c5c9217ecfe01a025be3c8b
PRECHECK_RUNTIME_CONTINUATION_AUTHORITY_REPAIR_PASSED=true
PRECHECK_RUNNING_SERVICES=[broker,homeassistant,manager]
PRECHECK_PRODUCTION_SERVICE_START=true
PRECHECK_PERSISTENCE_ENABLED=false
PRECHECK_BROKER_SERVICES_ENABLED=false
PRECHECK_CERTIFICATE_TIMER_ENABLED=false

FAILURE_ERROR_CODE=manager_mqtt_socket_count_invalid
ACCEPT_RC=2

POST_STAGE=STOPPED_RUNTIME_ACCEPTANCE
POST_RUNTIME_ACCEPTANCE_PASSED=UNSET
POST_PRODUCTION_SERVICE_START=false
POST_RUNNING_SERVICES=[]
POST_BROKER_ACTIVE=inactive
POST_SERVICES_ACTIVE=failed
POST_BROKER_ENABLED=disabled
POST_SERVICES_ENABLED=disabled
POST_PERSISTENCE_ENABLED=false
POST_CERTIFICATE_TIMER_ENABLED=false

ROLLBACK_PROVEN=true
ROLLBACK_AUTHORITY=exact source _downstream_fail_closed plus durable stage STOPPED_RUNTIME_ACCEPTANCE
RUNTIME_ACCEPTANCE_REPORT_CREATED=false
BOARD_ACCESS=false
REBOOT=false
MERGE=false
~~~

## What happened

The fresh live precheck passed every frozen entry condition. The real T1 was still at `RUNTIME_STARTED`, exact source/package/launcher binding matched the repaired `ffcbb1a...` control source, the continuation-authority repair was already claimed/consumed/PASS, and Broker, Manager and Home Assistant were all running with persistence and the certificate timer disabled.

The one-shot runtime acceptance authorization was then claimed and consumed exactly once.

Runtime acceptance failed inside the Manager MQTT continuity check with:

~~~text
manager_mqtt_socket_count_invalid
~~~

The exact source checks this condition inside a 10-second Manager stability loop and requires the observed established TCP connection count to remote port 8883 to equal exactly one on every sample.

The current error does **not** record whether the failing observed count was zero or greater than one. Therefore the root cause is not yet proven.

## Fail-closed result

The exact source invokes the downstream fail-closed rollback on any runtime-acceptance exception. The durable poststate is:

~~~text
TRANSACTION_STAGE=STOPPED_RUNTIME_ACCEPTANCE
RUNNING_SERVICES=[]
PRODUCTION_SERVICE_START=false
BROKER_ACTIVE=inactive
SERVICES_ACTIVE=failed
BROKER_ENABLED=disabled
SERVICES_ENABLED=disabled
PERSISTENCE_ENABLED=false
CERTIFICATE_TIMER_ENABLED=false
~~~

In the exact source, `STOPPED_RUNTIME_ACCEPTANCE` without the `_ROLLBACK_UNPROVEN` suffix is written only when the rollback proof succeeds, including empty product listeners, disabled Broker/Services/timer, inactive certificate lifecycle, stopped product runtime and zero rollback errors.

The runtime acceptance report was not created by this attempt: it is written only after `_runtime_acceptance_report()` returns successfully, while this attempt failed inside that function; the precheck also proved the report was absent before the attempt.

## Failure classification

~~~text
KF-121_STATUS=OPEN
DOMAIN=T1_F4_RUNTIME_ACCEPTANCE
FAILURE_CLASS=RUNTIME_ACCEPTANCE_ORACLE_OR_RUNTIME_CONNECTIVITY_UNCLASSIFIED
PRODUCT_DEFECT_PROVEN=false
ACCEPTANCE_ORACLE_DEFECT_PROVEN=false
RUNTIME_CONNECTIVITY_DEFECT_PROVEN=false
ROOT_CAUSE=TBD
~~~

Evidence already narrows the failure substantially:

- exact Broker/Manager/Home Assistant service set existed before the acceptance attempt;
- source/package/launcher binding was exact;
- runtime continuation authority repair was already complete;
- the acceptance code had already passed earlier checks in `_runtime_acceptance_report()` before it reached `_manager_runtime_stability()`, including runtime image/container contracts, Broker runtime contract, Manager runtime contract, Home Assistant runtime contract, service-identity binding, ingress guard, TLS verification and Manager fresh-state audit;
- the failing oracle did not preserve the observed socket count;
- rollback stopped the product runtime immediately after failure, so post-failure socket inspection cannot reconstruct the exact failing count.

No source repair is justified until read-only forensic evidence distinguishes a real Manager MQTT disconnect/reconnect from an over-strict or incorrect socket-count oracle.

## Closed / forbidden routes

~~~text
REPLAY_RUNTIME_ACCEPTANCE_AUTHORIZATION=CLOSED
REPLAY_RUNTIME_CONTINUATION_REPAIR=CLOSED
ENABLE_PERSISTENCE=CLOSED
CERTIFICATE_AUDIT_OR_TIMER=CLOSED
REBOOT=CLOSED
BOARD_USB_SERIAL_FLASH_NVS_RF=CLOSED
MERGE=CLOSED
AUTOMATIC_RUNTIME_RESTART_FOR_FORENSICS=CLOSED
~~~

## Next ONE Gate

~~~text
NEXT_ONE_GATE=N3W_T1_F4_RUNTIME_ACCEPTANCE_R1_MANAGER_MQTT_SOCKET_FORENSIC_READONLY_20261015_01
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
~~~

Purpose: inspect the durable failed transaction and stopped-container/journal evidence without restarting Broker, Manager or Home Assistant.

Required evidence:

1. exact transaction fields: stage, error code, rollback proof/count/listeners and runtime-acceptance authorization state;
2. stopped Manager container identity/state and relevant retained logs around the failure;
3. Broker retained logs around Manager connect/disconnect events, without exposing passwords or secret values;
4. source-level reconstruction of whether the Manager can legitimately own zero, one or more MQTT sockets at the acceptance boundary;
5. explicit classification:
   - real Manager MQTT connectivity failure;
   - transient/reconnect observation that the oracle should tolerate;
   - socket-probe implementation defect;
   - still inconclusive.

STOP after read-only classification. Do not restart production runtime and do not design a live retry authorization in the same gate.
