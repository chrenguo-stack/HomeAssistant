# N3-W Board D First Wi-Fi Provisioning Acceptance — 2026-10-24

```text
TASK=N3W_BOARD_D_FIRST_WIFI_PROVISIONING_ACCEPTANCE_20261024_01
RESULT=CLOSED_PASS

BOARD_D_HARDWARE_ID_SHA256=3991b9af9e7604190a8ac8e60b780911a8faed6698cda5421eaf1eb686210df5
CURRENT_APPLICATION=DEV_LOW_BATTERY_BYPASS
CURRENT_APPLICATION_IS_PRODUCTION_EXACT_R4=false

APP0_FULL_SLOT_SHA256=c50e71ad3842bb2aa041896442ec4fb64f8326826086c06ba6d09a6a9aedef6d
APP1_FULL_SLOT_SHA256=c50e71ad3842bb2aa041896442ec4fb64f8326826086c06ba6d09a6a9aedef6d

PRECHANGE_NVS_SHA256=d0c4bacc28291348669bf56ec25386685778eb2380c993dbd63583efcd548ab9
PRIVATE_FULL_NVS_SNAPSHOT_SAVED=true
POST_PROVISIONING_NVS_SHA256=UNKNOWN_FRESH

READONLY_PREFLIGHT=PASS
LCD_PRE_PROVISIONING_5_PAGE_CYCLE=PASS
LCD_PRE_PROVISIONING_PAGE5=配置节点网络
LCD_PRE_PROVISIONING_FREEZE_OR_CORRUPTION=false

AUTHORIZATION=N3W_BOARD_D_FIRST_WIFI_PROVISIONING_ACCEPTANCE_20261024_01
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_PERMITTED=false

WIFI_PROVISIONING_TRANSACTION_COUNT=1
WIFI_PROVISIONING_RESULT=PASS
BOARD_D_JOINS_TARGET_WIFI=true
MDNS_DISCOVERY=PASS
NATIVE_API_NETWORK_PATH=PASS

LCD_5_PAGE_CYCLE_AFTER_PROVISIONING=PASS
LCD_FREEZE_OR_CORRUPTION_AFTER_PROVISIONING=false
LCD_PAGE5_AFTER_PROVISIONING=正在查找主机
LCD_PAGE5_CLASSIFICATION=EXPECTED_HOST_DISCOVERY_WAIT

T1_PAIRING_EXECUTED=false
MQTT_RUNTIME_ACCEPTANCE_EXECUTED=false
DIRECT_RELAY_ACCEPTANCE_EXECUTED=false
SOFTWARE_ESP_RESTART_EXECUTED=false

FIRMWARE_WRITE=false
DIRECT_RAW_NVS_WRITE=false
MERGE=false
```

## Scope and outcome

Board D completed exactly one product-supported Wi-Fi fallback-AP/captive-portal provisioning transaction. The device joined the selected target Wi-Fi, was discoverable by mDNS, and the Native API network path was reachable. Wi-Fi credentials, SSID, IP address, full hostname, and the private NVS snapshot are intentionally not recorded in GitHub.

The fresh full NVS snapshot immediately before provisioning is bound by SHA256 `d0c4bacc28291348669bf56ec25386685778eb2380c993dbd63583efcd548ab9`. This supersedes the older postwrite-only NVS value as the rollback baseline for this provisioning transaction. No post-provisioning raw NVS read was performed in this gate.

## LCD page-5 classification

The post-provisioning LCD page-5 text `正在查找主机` is expected for the current product source and is not a provisioning failure.

At DEV product source `a15daad779adde74cdead4702f017553118321f8`:

- `firmware/esphome_rc/f1_0_rc2/packages/display.yml` blob `0551c13a7c0c751d08723547fc60cdac37a6cd58` renders:
  - `配置节点网络` when Wi-Fi is not connected;
  - `正在查找主机` when Wi-Fi is connected, pairing display is enabled, the product is not provisioned, and pairing handoff is not yet ready;
  - the pairing QR / `等待添加` only after pairing handoff becomes ready.
- `firmware/esphome_rc/f1_0_rc2/packages/n3w_product_transport.yml` blob `6458c2bb5d52a9050859c75feefcd8f03b49b73c` sets `n3w_pairing_display_ready=false` while Wi-Fi is connected but `pairing_handoff_ready()` is false.

Therefore the observed final page is consistent with the source-defined transition from network provisioning into host-discovery wait. It does not prove T1 pairing and does not authorize or execute the later T1/pairing stage.

## Boundary after this gate

This gate stops here.

- Do not repeat Wi-Fi provisioning under the consumed authorization.
- Do not invoke Native API Reboot or `esp_restart()` in this gate.
- Do not begin T1 pairing, MQTT, Direct/Relay, or RF acceptance automatically.
- PR #663 remains DEV ONLY / OPEN DRAFT / DO NOT MERGE.
- KF-130 remains OPEN because software-restart LCD behavior is still independently unvalidated.
