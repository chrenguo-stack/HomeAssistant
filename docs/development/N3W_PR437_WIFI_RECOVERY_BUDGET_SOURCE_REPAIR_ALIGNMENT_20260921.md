# N3-W PR #437 Wi-Fi Recovery Budget Source Repair Alignment — 2026-09-21

> Status: current public progress alignment  
> Repository: `chrenguo-stack/HomeAssistant`  
> Primary task: `N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE`

## 1. Fresh repository authority

```text
REPOSITORY_MAIN=a5a4dc06e86374287348bb8718e7f7fb7d6c42d2
REPOSITORY_MAIN_TREE=291cd078000d82e811a65d44ae782aa0b044bda9

PR437_STATE=OPEN_DRAFT
PR437_MERGED=false
PR437_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
PR437_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f
PR437_BASE=d9afc55b04042806ed8b6e1b1ae3553742aba2be
PR437_VS_CURRENT_MAIN=AHEAD_50_BEHIND_42
PR437_MERGE_BASE=d9afc55b04042806ed8b6e1b1ae3553742aba2be
```

Current exact-head CI:

```text
PR437_HEAD_WORKFLOW_COUNT=11
PR437_HEAD_WORKFLOW_SUCCESS_COUNT=11
PR437_HEAD_WORKFLOW_FAILURE_COUNT=0
CURRENT_HEAD_CI=PASS
```

## 2. Current deployed Board B authority

The board has not been reflashed with `4270f24...`. The latest physically verified application bytes remain the earlier PR #437 artifact:

```text
DEPLOYED_SOURCE_HEAD=177468e290a207f2fb7f6c554aedf60b61373b4d
DEPLOYED_SOURCE_TREE=a50ff98887b14b70cf9d278c6f8b7edf536eae88
DEPLOYED_ARTIFACT_ID=10607030747
DEPLOYED_ARTIFACT_NAME=n3w-pr437-boardb-exact-source
DEPLOYED_ARTIFACT_ZIP_SHA256=371d4369b791df527c595bc43ac203487f18a000b47ec73692d728ce58483dd8
DEPLOYED_APPLICATION_SIZE=1145984
DEPLOYED_APPLICATION_SHA256=74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093
DEPLOYED_APPLICATION_READBACK=PASS
```

The post-boot OTA-data partition changed from the initial all-FF image as expected after boot; byte-for-byte comparison to the initial OTA-data image is not a valid post-boot verifier.

## 3. Post-write failure evidence

The exact application did boot and reached Manager via Direct through sequence 49. It then stopped producing fresh Manager-visible Direct telemetry.

```text
POSTWRITE_DIRECT_BASELINE=FAIL
LAST_MANAGER_CANONICAL_SEQ=49
LAST_MANAGER_CANONICAL_SOURCE=direct
LAST_MANAGER_CANONICAL_UPDATED_AT=2026-09-20T14:35:06.070Z

EXACT_BOARD_B_MQTT_DISCONNECT=PROVEN
EXACT_BOARD_B_MQTT_DISCONNECT_AT=2026-09-20T14:35:30.732623821Z
BOARD_B_RECONNECT_IN_INITIAL_180S=NOT_OBSERVED
BOARD_B_LATE_RECONNECT_OBSERVED=false

MANAGER_RESTART_COUNT=0
BROKER_RESTART_COUNT=0
MANAGER_DISCONNECT_IN_EVENT_WINDOW=0
MASS_CLIENT_DISCONNECT_NEAR_EVENT=false
BROKER_ERROR_CLUSTER_NEAR_EVENT=false
```

A later LAN discriminator used the exact client's last pre-disconnect source address privately and emitted only public-safe conclusions:

```text
DIRECT_L2_ROUTE=true
FOUR_PACKET_PING_RECEIVED=0
NEIGHBOR_STATE_AFTER=INCOMPLETE

DIRECT_RECOVERY_OBSERVATION_SECONDS=150
DIRECT_RECOVERY_SAMPLE_INTERVAL_SECONDS=5
DIRECT_RECOVERY_PING_SAMPLE_COUNT=25
DIRECT_RECOVERY_PING_SUCCESS_COUNT=0
DIRECT_RECOVERY_NEIGHBOR_STATE_INCOMPLETE_COUNT=25
LATE_BROKER_CONNECT_COUNT=0
CANONICAL_ADVANCED=false
```

USB-only read-only inspection then established:

```text
BOARD_B_EXPECTED_USB_PATH_PRESENT=true
USBMODEM_CANDIDATE_COUNT=1
EXPECTED_PORT_OPEN_OWNER_COUNT=0
APPLICATION_SERIAL_OPEN=false
BOARD_RESET=false
FLASH_WRITE=false
NVS_WRITE=false
```

This makes a T1-wide Broker/Manager outage and local serial ownership poor explanations for the observed stall. It does not by itself prove application-runtime liveness or a unique device-side root cause.

## 4. Source defect isolated

Exact-source review against ESPHome 2026.4.3 found a concrete integration mismatch.

ESPHome permits the normal reconnect state machine to consume fallback time sequentially:

```text
ESPHOME_WIFI_SCAN_FALLBACK_MS=31000
ESPHOME_WIFI_CONNECT_FALLBACK_MS=46000
SEQUENTIAL_FALLBACK_MS=77000
```

The older N3-W recovery windows could preempt the upstream state machine before that legal sequence completed. Repeated `enable -> partial scan/connect -> early disable` can therefore starve Direct recovery even when the AP is available.

An intermediate repair at `164def447...` still had two review blockers:

```text
SR-B1=50S_WIFI_PHASE_DID_NOT_COVER_31S_SCAN_PLUS_46S_CONNECT
SR-B2=HEALTHY_RELAY_ABSOLUTE_WAS_WIDENED_30S_TO_90S
```

Both are closed in current exact HEAD `4270f24...`:

```text
NO_RELAY_WIFI_RECOVERY_BUDGET_MS=85000
MQTT_RECOVERY_BUDGET_MS=25000
DIRECT_CONFIRM_BUDGET_MS=5000
NO_RELAY_ABSOLUTE_RECOVERY_BUDGET_MS=120000
HEALTHY_RELAY_ABSOLUTE_RECOVERY_BUDGET_MS=30000

SR-B1=CLOSED_BY_SOURCE
SR-B2=CLOSED_BY_SOURCE
CURRENT_EXACT_HEAD_SOURCE_REVIEW=PASS
CURRENT_HEAD_CI=11_OF_11_PASS
```

The host regression now models Wi-Fi becoming ready after the full 77 s sequential fallback, MQTT becoming ready later, and concrete Direct commit at 104 s. The healthy-Relay test separately preserves the 30 s hard return-to-Relay ceiling.

## 5. Scope preserved

```text
SINGLE_RADIO_OWNERSHIP_SEMANTICS=UNCHANGED
OPTION_B_QUEUE_SEMANTICS=UNCHANGED
RELAY_RESTORE_BUDGET=UNCHANGED
MQTT_PHASE_BUDGET=UNCHANGED
PR437_MERGE=false
BOARD_B_REFLASH=false
```

The physical symptom is consistent with the confirmed source defect, but unique physical causation is not yet proven because the repaired exact head has not been built or deployed.

## 6. Current disposition

```text
KF096_STATUS=OPEN
PR437_SOURCE_GATE=PASS
PR437_CURRENT_HEAD_CI=PASS
PR437_EXACT_ARTIFACT_FOR_4270F24=NOT_BUILT
EXACT_ARTIFACT_READY=true
PHYSICAL_REVALIDATION_REQUIRED=true
PR437_MERGE_READY=false
```

## 7. Next route

```text
NEXT_ONE_GATE=N3W_PR437_4270F24_EXACT_ARTIFACT_BUILD_AND_BINDING_PREPARATION_20260921_01
```

The next gate is GitHub/build-only. It must bind a fresh artifact to exact source HEAD/tree/config and stop before any Board B flash/reset/NVS operation.
