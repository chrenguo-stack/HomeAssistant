# N3-W KF-089 Relay Acquisition, Telemetry Observability, and Schema v5 Progress Alignment

Status: `PUBLIC_SAFE_PROGRESS_ALIGNMENT_ARCHIVE`  
Date: `2026-09-10`  
Scope: public-safe source, runtime, physical-boundary, and acceptance alignment. Raw credentials, private identities, raw NVS, private addresses, USB paths, local absolute paths, and private logs are intentionally excluded.

## 1. Purpose and scope

This archive supersedes the current-state portion of the 2026-09-07 local-chat alignment while preserving all historical archives unchanged. It records the 2026-09-10 KF-089 evidence after T1 runtime convergence, including durable Direct-to-DISCOVERY behavior, Relay advertisement acceptance, authenticated Relay acquisition, the remaining downstream telemetry boundary, PR #381 Schema-v5 observability, and the next physical gate.

T1 runtime convergence is closed and is not reopened by this archive.

## 2. Repository and source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR381_BASE_MAIN=f7083fbb7a7ba228dcd5f253b9cba752f6c7104c
PR381_HEAD=b521ad1a5e223d2cf5a0de43fa6ff956339e9a0e
PR381_MERGE_COMMIT=5d58727f5040281ee2beb9597f66a6a2da9bac57
PR381_MERGE_TREE=b27b2968ea4e0b3bcb5f8312c3d31d391bd8d3ed
DIAGNOSTIC_SCHEMA_VERSION=5
PR381_SCOPE=OBSERVABILITY_ONLY
```

PR #381 changed diagnostics and host-side observability only. It did not change protocol, wire format, cryptography, path state machine, retry policy, channel policy, MQTT topics, or asynchronous completion behavior.

The frozen product behavior source authority remains separate from the current diagnostic source authority:

```text
PRODUCT_BEHAVIOR_SOURCE_AUTHORITY=fe116efabbd986263b043aa1a36ad74bf283bafa
DIAGNOSTIC_SOURCE_AUTHORITY=5d58727f5040281ee2beb9597f66a6a2da9bac57
```

## 3. T1 detour closure

```text
T1_RUNTIME_CONVERGENCE=CLOSED_PASS
ACTIVE_DETOUR=NONE
```

The detailed T1 archive remains authoritative for that infrastructure detour:
`N3W_KF089_T1_RUNTIME_CONVERGENCE_ISSUES_AND_PROGRESS_ALIGNMENT_20260909.md`.

## 4. Board identity and physical-boundary guards

```text
BOARD_A_BOARD_B_MAPPING_CORRECTED=true
USB_PORT_IS_LOCATOR_ONLY=true
BOARD_IDENTITY_REQUIRES_FRESH_SILICON_BINDING_BEFORE_MUTATION=true
```

Historical A/B role labels were corrected. Future board-targeted mutation must use explicit operator target confirmation followed by fresh ROM silicon identity verification. No raw MAC, node ID, credential, Setup Secret, or local USB path is public authority.

Current public-safe physical boundary:

```text
BOARD_B_STATE=ROM_DOWNLOAD_MODE
BOARD_B_USB_CONNECTED_TO_TEST_MAC=true
BOARD_B_BATTERY_CONNECTED=false
BOARD_B_APPLICATION_BOOT_AFTER_FROZEN_CAPTURE=false
BOARD_A_ACCESSED_DURING_LATER_HOST_ONLY_GATES=false
```

No Schema-v5 physical deployment has been executed.

## 5. AP-loss durable discovery evidence

```text
TEST_WINDOW_SECONDS=30
DIRECT_TO_DISCOVERY_DURABLE_OBSERVED=true
DISCOVERY_SCAN_DURABLE_OBSERVED=true
KF089_DIRECT_TO_DISCOVERY_TRANSITION=PASS
KF089_AUTONOMOUS_DISCOVERY_SCAN=PASS
```

The durable scan evidence included `scan_attempts=453`, with attempts roughly balanced across channels 1, 6, and 11. Discovery counters are boot-session cumulative; an older boot's rejection count must not be attributed to one AP-loss window.

## 6. Static Relay-handshake preconditions

```text
STATIC_HANDSHAKE_PRECONDITIONS=PASS
FIRST_STATIC_BLOCKER=NONE
```

Per-node application keys and key epochs do not need to be equal. The handshake depends on same-system peer trust credentials, not equality of Child telemetry application keys. Raw key material is excluded.

Fresh Direct accepted telemetry also supports the following public-safe preclaim:

```text
BOARD_A_CURRENT_RELAY_CAPABILITY_PRECLAIM=PASS
```

## 7. Selective-RF capture

```text
TEST_WINDOW_SECONDS=90
BOARD_A_DIRECT_COUNT_DURING_WINDOW=18
BOARD_A_REMAINED_DIRECT_DURING_TEST=true
BOARD_B_DIRECT_COUNT_DURING_WINDOW=0
BOARD_B_RELAY_COUNT_DURING_WINDOW=0
SELECTIVE_RF_AP_ISOLATION=PASS_FROM_RUNTIME_EVIDENCE
```

T1 did not expose Board B Relay ingress in that window. The later durable device diagnostics provide the next layer of evidence; the absence of T1 frame logs is not itself a negative proof.

## 8. NVS readback incident and controlled recovery

The first explicit no-stub NVS readback stopped at `C000 Bad data length`.

```text
FIRST_FAILED_STAGE=ROM_NVS_READBACK
READBACK_FAILURE_ROOT_CAUSE=NOT_PROVEN
SPI_FLASH_CONFIG_DEFECT_PROVEN=false
FLASH_HARDWARE_FAULT_PROVEN=false
NVS_CORRUPTION_PROVEN=false
```

A controlled default flasher stub path then passed with before/after no-reset evidence. The NVS image size was 458752 bytes. The result is deliberately limited to:

```text
DEFAULT_STUB_PATH_SUCCEEDED_AFTER_NO_STUB_PATH_FAILED=true
NO_STUB_ROOT_CAUSE_PROVEN=false
```

Raw NVS images are not committed to the public repository.

## 9. Schema-v4 durable Relay evidence

The decisive cold-discovery capture used a new boot session distinct from the earlier session. Public-safe counters were:

```text
RUNTIME_START_MODE=DISCOVERY
PATH_STATE=RELAY_ACTIVE
SCAN_ATTEMPTS=202
SCAN_SUCCESSES=119
SCAN_FAILURES=83
DISCOVERY_RX=48
DISCOVERY_REJECTED=38
DISCOVERY_ACCEPTED=10
DISCOVERY_REJECT_STATE=36
DISCOVERY_REJECT_CHANNEL_MISMATCH=2
CHALLENGE_TX=10
CHALLENGE_TX_SUBMIT_SUCCESS=4
ACCEPT_RX=2
ACCEPT_VERIFY=2
PEER_INSTALL_ATTEMPTS=2
PEER_INSTALL_SUCCESS=2
RELAY_ACTIVE_COUNT=2
RELAY_TELEMETRY_ATTEMPTS=18
RELAY_TELEMETRY_SUBMIT_SUCCESS=16
COLD_DISCOVERY_ENVIRONMENT=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PASS
KF089_AUTHENTICATED_RELAY_ACQUISITION=PASS
```

The `STATE_NOT_DISCOVERY` rejection class primarily occurred after the node had already left discovery. It does not invalidate the successful acquisition evidence.

## 10. Telemetry semantic correction

In Schema v4, `relay_telemetry_success` denotes synchronous `esp_now_send(...)` submission accepted by the local API. It does not prove asynchronous wireless delivery.

```text
B_UNICAST_SUBMIT=PASS
B_UNICAST_DELIVERY=NOT_PROVEN
```

Schema v5 adds separate unicast-completion counters so downstream adjudication can distinguish local submit from asynchronous completion.

## 11. Downstream source/evidence audit

```text
A_GATEWAY_FRAME_TOPIC_PUBLISH_ALLOWED=true
MANAGER_GATEWAY_SUBSCRIPTION_CONFIGURED=true
MANAGER_COMPACT_RELAY_CORE_WIRED=true
MANAGER_MULTI_INGRESS_ROUTER_WIRED=true
MANAGER_CANONICAL_INGRESS_WIRED=true
MANAGER_B_RELAY_KEY_LOOKUP=PASS
A_TO_MANAGER_PROTOCOL_CONTRACT_MATCH=true
```

The Board A zero-knowledge forwarding contract passes: Board A wraps the encrypted compact frame without holding or decrypting the Child application key; Manager uses the Child key.

In the 90-second window:

```text
BROKER_GATEWAY_TOPIC_EVENT_FOUND=false
MANAGER_GATEWAY_FRAME_RX_FOUND=false
BROKER_LOG_NEGATIVE_EVIDENCE_CAPABLE=false
MANAGER_LOG_NEGATIVE_EVIDENCE_CAPABLE=false
DOWNSTREAM_ROOT_CAUSE_PROVEN=false
FIRST_UNPROVEN_STAGE=B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX
ROOT_CLASS=DEVICE_SIDE_UNICAST_DELIVERY_OR_GATEWAY_FORWARDING_UNOBSERVED
```

Therefore `A_DID_NOT_PUBLISH` is not proven.

## 12. PR #381 observability repair and validation

```text
PR_NUMBER=381
TITLE=diag(n3w): close relay telemetry observability gap
SCHEMA_BEFORE=4
SCHEMA_AFTER=5
V4_BINARY_PREFIX_PRESERVED=true
TARGETED_TESTS=PASS
TEST_COUNT=37
ESP32_C6_COMPILE=PASS
CI_ALL_PASS=true
PR381_MERGED=true
```

Schema-v5 additions include Board B unicast completion totals/success/failure and Board A compact RX, state rejection, child-binding, compact decode, compact-wrap, forward-attempt, and local-submit counters.

```text
PROTOCOL_CHANGE=false
WIRE_FORMAT_CHANGE=false
CRYPTO_CHANGE=false
PATH_STATE_MACHINE_CHANGE=false
RETRY_POLICY_CHANGE=false
CHANNEL_POLICY_CHANGE=false
MQTT_TOPIC_CHANGE=false
ASYNC_COMPLETION_BEHAVIOR_CHANGE=false
```

## 13. Exact-main Schema-v5 artifact

```text
SOURCE_COMMIT=5d58727f5040281ee2beb9597f66a6a2da9bac57
SOURCE_TREE=b27b2968ea4e0b3bcb5f8312c3d31d391bd8d3ed
FIRMWARE_BIN_SIZE=1115648
FIRMWARE_BIN_SHA256=5168a1958669ce06002cc5cb507fda7fc7477ca53294a73dbcf582e5879f383b
FIRMWARE_ELF_SHA256=83065aae1b4bef9273f73f9618bc3b525cdf4543af1a61bfb0dc0ff04b81fa07
SCHEMA_V5_BINARY_BINDING=PASS
SAME_BINARY_VALID_FOR_A_AND_B=true
```

Local temporary build paths and raw private artifacts are not public authority.

## 14. Dual-slot deployment and OTA activation method

```text
OTADATA_OFFSET=0x9000
OTADATA_SIZE=0x2000
APP0_OFFSET=0x10000
APP0_SIZE=0x3C0000
APP1_OFFSET=0x3D0000
APP1_SIZE=0x3C0000
NVS_OFFSET=0x790000
NVS_SIZE=0x70000
APP0_EQUALS_OTA0=true
APP1_EQUALS_OTA1=true
CURRENT_ACTIVE_SLOT=app1
TARGET_SLOT=app0
ROLLBACK_SLOT=app1
```

The recovered exact method is ESP-IDF 5.5.4 `components/app_update/otatool.py`: read the physical partition table and current OTA selection; write the exact firmware only to the inactive app slot; perform exact-size readback and SHA-256 verification; then use `switch_ota_partition --slot 0`; finally read and verify `otadata` and boot normally. The previously successful deployment used the same command form for slot 1.

```text
OTADATA_CONTROLLED_BOOT_SELECTION_MUTATION_REQUIRED=true
OTADATA_ERASE=false
OTADATA_FULL_REPLACEMENT=false
NVS_UNTOUCHED_BY_HOST=true
APP1_UNTOUCHED=true
BOOTLOADER_UNTOUCHED=true
PARTITION_TABLE_UNTOUCHED=true
```

This section records method authority only; no physical deployment was performed in this alignment.

## 15. Current product acceptance boundary

```text
KF089_STARTUP_GATE_REPAIR=PASS
KF089_DIRECT_TO_DISCOVERY_TRANSITION=PASS
KF089_AUTONOMOUS_DISCOVERY_SCAN=PASS
KF089_A_B_ESPNOW_REACHABILITY=PASS
SELECTIVE_RF_ZONE_QUALIFIED=PASS
KF089_RELAY_ADVERTISEMENT_DECODED=PASS
KF089_RELAY_ADVERTISEMENT_ACCEPTED=PASS
KF089_AUTHENTICATED_RELAY_ACQUISITION=PASS
KF089_END_TO_END_RELAY_TELEMETRY=NOT_PROVEN
FIRST_UNPROVEN_STAGE=B_UNICAST_TX_COMPLETION_OR_A_COMPACT_RX
```

No new KF identifier is created. The remaining boundary is downstream telemetry localization, not a newly proven Board B radio, Board A receiver, gateway, Broker, or Manager defect.

## 16. Next physical gate

```text
NEXT_ONE_GATE=N3W_KF089_SCHEMA_V5_TWO_BOARD_DEPLOYMENT_AND_RELAY_TELEMETRY_LOCALIZATION
PHYSICAL_AUTHORIZATION_REQUIRED=true
```

Route:

```text
SCHEMA_V5_TWO_BOARD_DEPLOYMENT
-> TWO_BOARD_DIRECT_BASELINE
-> SELECTIVE_RF_LOCALIZATION_CAPTURE
-> B/A DURABLE_SCHEMA_V5_READBACK
-> DOWNSTREAM_RELAY_TELEMETRY_ADJUDICATION
```

This route has not been executed or implicitly authorized by this documentation archive.

## 17. Public/private evidence boundary

GitHub public-safe authority may contain sanitized counts, commit/tree hashes, firmware artifact hashes, source/tests, architecture decisions, and closure documents. It must not contain raw NVS dumps, raw MACs, raw node IDs, Setup Secrets, application/system peer keys, MQTT credentials, private T1 addresses, USB device paths, local absolute user paths, or raw private logs containing secrets.

