# N3-W Production Multi-Relay Gateway Selection V1 — Board C Wi-Fi/provisioning loss diagnosis

Status: `READONLY_DIAGNOSIS`

## Observed USB log

The current Board C boot reports:

```text
WIFI_CONNECTED=false
WIFI_FALLBACK_AP_STARTED=true
N3W_PROVISIONING_STATE=UNPROVISIONED
SAFE_MODE_UNSUCCESSFUL_BOOT_ATTEMPTS=0
```

The boot also reports reset reason `USB_UART_HPSYS` during the USB diagnostic capture.
This is not a brownout proof.

The current exact firmware source has no fixed production STA SSID/password in the image.
Wi-Fi Direct operation after captive-portal setup therefore depends on persisted Wi-Fi
credentials. The product N3-W runtime separately persists peer/broker provisioning state
in the NVS partition.

## Evidence interpretation

Board C had already passed a post-write Manager-visible Direct baseline on exact artifact
10693728323. Therefore the exact application write itself did not leave Board C
unprovisioned.

The present combination of:

- fallback AP active,
- no Direct Wi-Fi connection,
- N3-W runtime declaring the node unprovisioned,
- earlier repeated Board C boot-session changes and suspected unstable power,
- firmware configuration `factory_reset: resets_required: 3, max_delay: 10s`,

is strongly consistent with the fast-power-cycle factory-reset path having erased NVS after
the earlier successful baseline.

This is a diagnosis, not yet a destructive repair authorization.

## Current disposition

```text
BOARD_C_WIFI_DIRECT_FAILURE=PROVISIONING_STATE_LOSS_STRONGLY_SUPPORTED
BOARD_C_N3W_PROVISIONING_LOSS=OBSERVED
BOARD_C_BROWNOUT=NOT_PROVEN_BY_CURRENT_USB_LOG
EXACT_ARTIFACT_APPLICATION_DEFECT=NOT_SUPPORTED
PRODUCT_FLASH_REWRITE_REQUIRED=false
NVS_REPAIR_OR_REPROVISION_REQUIRED=LIKELY
BOARD_C_POWER_STABILITY_REPAIR_REQUIRED=YES
```

Sensor startup failures observed on SCD30/SHT3x/BH1750 are separate from this Wi-Fi/N3-W
provisioning diagnosis and are not used as the cause of the Direct-connect failure.

Before any re-provisioning, keep the Gateway Selection physical acceptance paused and
stabilize Board C power. Any NVS-changing recovery requires a separate bounded gate.
