# 温室环境监测系统（ESP32-C6）
# N3-W R3 注册后 Direct Telemetry / Home Assistant 验收失败归档
# KF-140 OPEN — 2026-11-03

```text
EXECUTION_ID=N3W_T1_CORE_STACK_R3_POST_REGISTRATION_DIRECT_TELEMETRY_AND_HA_DISCOVERY_ACCEPTANCE_20261103_01
RESULT=FAIL
KF=KF-140
KF_STATE=OPEN
KF139_REOPEN=false
ROOT_CAUSE=TBD
SOURCE_RISK_PROVEN=true
PRODUCT_RUNTIME_E2E_FAILURE_PROVEN=true
```

## 1. 结论

R3 已注册节点可以使用现有 generation-1 MQTT 凭据建立 authenticated Direct MQTT session；Broker DynSec node role / client-id binding / Direct ingress publish ACL 正确，Manager Direct ingress subscription 正常，T1 Manager/Broker/Home Assistant runtime 稳定，pairing window 保持 CLOSED。

但是同一真实物理窗口内，板端已经明确生成并向 Direct MQTT 路径提交 telemetry seq=35，而 Manager 在对应 UTC 窗口内既没有 accepted telemetry，也没有 rejected telemetry，Home Assistant 也没有新的运行态 receipt。因此本 Gate 判定 FAIL。

这不是 KF-139 复发；KF-139 保持 CLOSED_PASS。

## 2. Frozen authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
MAIN=e0841a5a43fd5847d5c5c40ab1cece42faedf3c8
BOARD_DEPLOYED_SOURCE=414ff0290db37e89a0e137d30f491e6c17cba2b0
MANAGER_PRODUCT_SOURCE=b863ddd959090ca139af76bd68dbef31d773e6de
BOARD_FIRMWARE=F1.0-RC2-N3W-TARGET-0.1
ESPHOME_RUNTIME=2026.4.3
N3W_TELEMETRY_INTERVAL=60s
IDF_SEND_ASYNC=true
```

## 3. Durable/runtime baseline remained healthy

```text
GEN1_CREDENTIAL_ACTIVE=true
PENDING_CREDENTIAL_GENERATION=null
UNRESOLVED_FIRST_REGISTRATION_COUNT=0
DURABLE_BINDING_CONSISTENT=true

PAIRING_WINDOW=CLOSED
PAIRING_CLOSE_REASON=committed
TCP_47112=0

MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0
BROKER_RUNNING=true
BROKER_RESTART_COUNT=0
HOMEASSISTANT_RUNNING=true
HOMEASSISTANT_RESTART_COUNT=0

TCP_8883=1
TCP_47110=1
UDP_47111=1
```

## 4. Direct MQTT identity / ACL / subscription evidence

Focused read-only forensic result:

```text
NODE_CLIENT_ID_BINDING=PASS
EXPECTED_GENERATION1_USERNAME_SEEN=true
EXPECTED_ROLE_ASSIGNMENT=PASS
EXPECTED_ROLE_COUNT=1
DIRECT_INGRESS_PUBLISH_ACL_COUNT=1
DIRECT_INGRESS_PUBLISH_ACL=PASS
DYNSEC_DEFAULT_DENY=PASS

BROKER_FINAL_NODE_SESSION=AUTHENTICATED_CURRENT
BROKER_NODE_DENIAL_COUNT=0

MANAGER_DIRECT_INGRESS_SUBSCRIPTION_COUNT=1
MANAGER_MQTT_CONNECTION_REJECTED_COUNT=0
MANAGER_UNEXPECTED_MQTT_DISCONNECT_COUNT=0
```

Therefore the failure is not currently explained by wrong generation-1 credential, wrong client-id, missing node role, missing Direct ingress ACL, Manager missing subscription, or an observed Broker ACL denial.

## 5. Board-side positive telemetry evidence

ESPHome Native API network-log capture succeeded without USB/serial/reflash/NVS mutation.

```text
BOARD_API_CONNECTED=true
BOARD_ACCESS=NETWORK_LOG_READ_ONLY
FLASH=false
NVS_MUTATION=false
REBOOT=false
SERIAL=false
```

Exact board log evidence:

```text
2026-11-03 20:52:58.578 +08:00
N3-W telemetry held seq=35 depth=1 path=0 ownership=0

2026-11-03 20:52:58.584 +08:00
N3-W telemetry Direct single attempt submitted seq=35 depth_after=0
```

Source authority defines:

```text
LocalPathState::DIRECT=0
```

Therefore:

```text
SEQ_35_GENERATED=true
SEQ_35_PATH=DIRECT
SEQ_35_N3W_FIFO_ENQUEUE=true
SEQ_35_DIRECT_MQTT_SUBMIT_CALL_RETURNED_SUCCESS=true
```

The first “held” line is normal FIFO admission followed approximately 6 ms later by Direct submit and queue removal. It is not a stuck-queue failure.

Time binding clarification:

ESPHome 2026.4.3 `esphome logs` does not preserve a device-origin wall-clock timestamp in this prefix. The CLI adds the prefix when each API log message arrives by calling `datetime.now().astimezone()` on the operator host.

```text
LOG_PREFIX_AUTHORITY=OPERATOR_MAC_RECEIPT_WALL_CLOCK
OPERATOR_MAC_TIMEZONE_AT_CAPTURE=Asia/Singapore
SEQ35_LOG_RECEIVED_LOCAL=2026-11-03T20:52:58+08:00
SEQ35_LOG_RECEIVED_UTC=2026-11-03T12:52:58Z
DEVICE_ORIGIN_WALL_CLOCK_TIMESTAMP=NOT_PROVEN
```

Therefore the UTC conversion remains valid for the host-observed receive window, but the timestamp must not be described as a device-generated board timestamp.

## 6. Same-window downstream correlation

Read-only T1/HA correlation window:

```text
START_UTC=2026-11-03T12:52:30Z

MANAGER_ACCEPTED_COUNT=0
MANAGER_ACCEPTED_UNIQUE_SEQ_COUNT=0
MANAGER_REJECTED_COUNT=0
MANAGER_DISCOVERY_PUBLISH_COUNT=0

BROKER_DENIAL_COUNT=0

HA_CONNECTIVITY_ENTITY_PRESENT=true
HA_CONNECTIVITY_STATE=on
HA_UPDATED_AFTER_BOARD_SUBMIT_WINDOW=false
HA_RUNTIME_RECEIPT_OK=false
```

Thus the physical business path is not accepted:

```text
BOARD_DIRECT_SUBMIT=PASS
BROKER_OR_MANAGER_DELIVERY=FAIL_NOT_OBSERVED
MANAGER_DELIVERY=FAIL
HA_RUNTIME_RECEIPT=FAIL
OVERALL=FAIL
```

## 7. Test-harness errors that are NOT product failures

Three intermediate board-log attempts failed before establishing a valid API log session:

1. local command executed outside a Git repository and could not resolve repository-relative product YAML;
2. a temporary source tree was incomplete and missing display font files;
3. a minimal diagnostic YAML omitted a network component required by ESPHome `api:`.

These are classified as harness errors only. The final R4 capture passed config preflight and successfully connected to the real board Native API.

## 8. Source-level risk discovered during failure analysis

Current N3-W source:

- `SimpleProductComponent::publish_direct()` calls ESPHome `mqtt::global_mqtt_client->publish(..., qos=1, retain=false)`;
- on returned `true`, N3-W logs “Direct single attempt submitted”, removes the item from its own telemetry FIFO and does not retain it for downstream acknowledgement.

Current product target enables:

```text
idf_send_async=true
```

ESPHome 2026.4.3 source behavior under `USE_MQTT_IDF_ENQUEUE`:

1. backend `publish()` enqueues a copied message into ESPHome's outbound queue;
2. a `true` result therefore proves local queue admission, not Broker QoS1 acknowledgement;
3. a separate FreeRTOS MQTT task later calls `esp_mqtt_client_publish(...)`;
4. the async task does not propagate the return value of that later call back to the N3-W caller;
5. `MQTT_EVENT_PUBLISHED` exists, but current N3-W Direct telemetry path does not bind it to the original seq or use it as the release/acceptance oracle.

Therefore the current log text “Direct single attempt submitted” must be interpreted only as:

```text
LOCAL_ASYNC_MQTT_QUEUE_ADMISSION_ACCEPTED
```

It must NOT be interpreted as:

```text
BROKER_RECEIVED
QOS1_PUBACK_CONFIRMED
MANAGER_RECEIVED
```

This semantic/observability gap is source-proven and is a strong candidate for the observed physical failure, but it is not yet proven to be the exact live root cause of seq=35 disappearance.

## 9. Current root-cause classification

```text
KF140_ROOT_CAUSE=TBD
PROVEN_FAILURE_BOUNDARY=AFTER_N3W_DIRECT_ASYNC_QUEUE_ADMISSION_AND_BEFORE_MANAGER_TELEMETRY_ACCEPTANCE
ASYNC_MQTT_COMPLETION_GAP=PROVEN_SOURCE_RISK
SEQ35_ESP_MQTT_CLIENT_PUBLISH_RETURN=NOT_PROVEN
SEQ35_QOS1_PUBACK=NOT_PROVEN
SEQ35_BROKER_INGRESS=NOT_PROVEN
```

No speculative source repair is authorized before distinguishing those stages.

## 10. Closed routes

```text
REOPEN_KF139=false
RETRY_FIRST_REGISTRATION=false
ROTATE_GENERATION1_CREDENTIAL=false
CHANGE_DYNSEC_ACL=false
RESTART_T1_SERVICES=false
FLASH_BOARD=false
ERASE_OR_MUTATE_NVS=false
ENTER_DIRECT_RELAY_FAILOVER=false
SENSOR_ACCEPTANCE=false
```

## 11. Next focused gate

```text
NEXT_ONE_GATE=N3W_KF140_DIRECT_ASYNC_MQTT_DELIVERY_COMPLETION_FORENSIC_20261103_01
```

Purpose:

- preserve current same-boot Direct state;
- obtain evidence after N3-W async queue admission and before Manager ingest;
- determine whether the ESPHome async MQTT task actually transmits the queued telemetry and whether QoS1 completion/PUBACK is observed;
- keep Broker/Manager/HA and credential state unchanged;
- only after that evidence classify source repair.

```text
T1_MUTATION=false
SERVICE_RESTART=false
CREDENTIAL_MUTATION=false
DYNSEC_MUTATION=false
BOARD_FLASH=false
BOARD_NVS_MUTATION=false
BOARD_REBOOT=false
BOARD_LOCATION_CHANGE=false
ROOT_CAUSE_REQUIRED_BEFORE_SOURCE_REPAIR=true
```


## 12. Manager live Direct receive ACL closure

Fresh live read-only DynSec evidence:

```text
DEFAULT_PUBLISH_CLIENT_RECEIVE=false
DEFAULT_SUBSCRIBE=false

MANAGER_CLIENT_COUNT=1
MANAGER_CLIENT_ID_OK=true
MANAGER_ROLE_ASSIGNMENT_OK=true
MANAGER_ROLE_COUNT=1

DIRECT_SUBSCRIBE_PATTERN=true
DIRECT_PUBLISH_CLIENT_RECEIVE=true
DIRECT_UNSUBSCRIBE_PATTERN=true
OVERALL_EXACT_DIRECT_RECEIVE_CONTRACT=true
```

The live Manager role carries the expected exact Direct ingress filter:

```text
gh/v1/<system_id>/ingress/node/+/telemetry
```

with both:

```text
subscribePattern allow priority=100
publishClientReceive allow priority=100
```

Therefore current KF-140 evidence excludes these candidate explanations:

```text
MANAGER_SUBSCRIBE_ACL_MISSING=false
MANAGER_PUBLISH_CLIENT_RECEIVE_ACL_MISSING=false
MANAGER_IDENTITY_ROLE_BINDING_DRIFT=false
LIVE_DYNSEC_DIRECT_RECEIVE_CONTRACT_DRIFT=false
```

Updated failure boundary:

```text
PROVEN_HEALTHY_UPSTREAM=
GEN1_AUTH;
NODE_DIRECT_PUBLISH_ACL;
MANAGER_DIRECT_SUBSCRIBE_ACL;
MANAGER_DIRECT_PUBLISH_CLIENT_RECEIVE_ACL;
MANAGER_MQTT_SUBSCRIPTION

PROVEN_BOARD_EVENT=
N3W_DIRECT_ASYNC_QUEUE_ADMISSION_ACCEPTED

UNPROVEN_BOUNDARY=
ESPHome_ASYNC_MQTT_WORKER_ACTUAL_SEND;
BROKER_QOS1_RECEIPT_OR_PUBACK;
MANAGER_MESSAGE_DELIVERY
```

Next focused evidence remains read-only packet/timestamp correlation. No ACL repair is justified.


## 13. Broker namespace live TCP session evidence

Fresh read-only `ss -tin` evidence from the running Broker container network namespace proves the registered board has a live established TLS/MQTT transport to Broker port 8883.

```text
BOARD_IP_PRIVATE_REDACTED=true
BROKER_SOCKET_STATE=ESTABLISHED
BROKER_LOCAL_PORT=8883
BOARD_PEER_MATCH=true
BYTES_RECEIVED_AT_SAMPLE=145354
DATA_SEGS_IN_AT_SAMPLE=1583
BYTES_SENT_AT_SAMPLE=19849
DATA_SEGS_OUT_AT_SAMPLE=551
TCP_RETRANSMISSION_OBSERVED=true
```

This closes the candidate explanation that the board has no live TCP/TLS connection to the Broker. The transport session is alive and exchanging data. It does not by itself prove that a specific telemetry payload reached Broker MQTT processing.

Updated KF-140 focused boundary:

```text
NODE_AUTH_SESSION=PASS
BROKER_TCP_TLS_SESSION=PASS
NODE_DIRECT_PUBLISH_ACL=PASS
MANAGER_DIRECT_RECEIVE_ACL=PASS
MANAGER_SUBSCRIPTION=PASS
N3W_DIRECT_ASYNC_QUEUE_ADMISSION=PASS

SPECIFIC_TELEMETRY_TCP_DELIVERY=UNPROVEN
BROKER_MQTT_INGRESS_FOR_SEQ=UNPROVEN
MANAGER_ACCEPT_FOR_SEQ=UNPROVEN
```

Next read-only step is time-correlated socket-counter sampling around the next board-side Direct submit.


## 14. MQTT log-topic interference excluded

Fresh source review of deployed board source `414ff0290db37e89a0e137d30f491e6c17cba2b0` confirms:

```yaml
mqtt:
  id: n3w_mqtt_client
  broker: 127.0.0.1
  enable_on_boot: false
  discovery: false
  reboot_timeout: 0s
  idf_send_async: true
  log_topic: null
```

Therefore ESPHome runtime log lines such as `N3-W telemetry Direct single attempt submitted` are not mirrored to Broker through MQTT logging. This materially strengthens the planned correlation oracle: a near-synchronous increase in Broker-side TCP `bytes_received` around a fresh Direct telemetry submit cannot be explained by ESPHome MQTT log-topic traffic.

The socket-counter method still proves transport bytes rather than plaintext topic/payload because TLS remains encrypted.


## 15. CORRECTION — previous Manager accepted-count oracle was invalid

Fresh source review of deployed Manager source `b863ddd959090ca139af76bd68dbef31d773e6de` found that the active simplified N3-W Direct path logs accepted telemetry as:

```text
Accepted simplified N3-W telemetry source=direct node=<node> gateway=None key=(<node>, <boot>, <seq>)
```

and rejected telemetry as:

```text
Rejected simplified N3-W ingress source=direct node=<node> gateway=None code=<code>
```

The earlier acceptance harness incorrectly counted:

```text
Accepted telemetry node=
Rejected telemetry node=
```

Those strings do not match the deployed simplified N3-W path. Therefore:

```text
PREVIOUS_MANAGER_ACCEPTED_COUNT_ZERO_VALID=false
PREVIOUS_MANAGER_REJECTED_COUNT_ZERO_VALID=false
PREVIOUS_MANAGER_DELIVERY_FAIL_PROVEN=false
PREVIOUS_OVERALL_PRODUCT_FAIL_PROVEN=false
KF140_PRODUCT_DEFECT_STATUS=UNDER_REVIEW
TEST_HARNESS_ORACLE_DEFECT=PROVEN
```

The board-side Direct submit and Broker TCP correlation evidence remain valid independently:

```text
SEQ71_DIRECT_SUBMIT_OBSERVED=true
NEAR_SUBMIT_BROKER_BYTES_RECEIVED_DELTA=1077
NEAR_SUBMIT_BROKER_DATA_SEGS_IN_DELTA=4
PREBASELINE_BYTES_DELTA=31
MQTT_LOG_TOPIC=null
```

Next required step is a fresh read-only Manager log query using the deployed exact log strings and exact seq=71 correlation. No product repair is justified unless that corrected oracle still proves a real failure.
