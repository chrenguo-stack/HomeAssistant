# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Current progress alignment: `docs/development/N3W_PROGRESS_ALIGNMENT_20260918.md`  
Previous progress alignment: `docs/development/N3W_PROGRESS_ALIGNMENT_20260917.md`  
Historical PR #416 handoff: `docs/development/N3W_PR416_CONTROLLED_CHANNEL_TX_POSTFLASH_DIRECT_BASELINE_NEW_CHAT_HANDOFF_V1.0_20260917.md`  
Current local-development-environment authority: `docs/development/local-environment-records/2026-09-17-macos-x86_64.json`  
Current KF-089 Relay end-to-end closeout: `docs/development/N3W_KF089_RELAY_END_TO_END_CLOSEOUT_20260914.md`  
Active product-direction authority: `docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

## Repository / product source authority at this alignment

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE

FROZEN_PRODUCT_SOURCE_HEAD=096528fbf61948d6c69197f1c8994ce8e7d672f4
FROZEN_PRODUCT_SOURCE_TREE=6cfa25f5168fc720590f186871c038e3d4a5307f
```

Always fresh-query repository `main`. A documentation-only merge after this point may advance `main` without changing the frozen Board B product source above.

## Recent merged route

```text
PR420=MERGED   # documentation alignment
PR421=MERGED   # retained RTC watchdog breadcrumb
PR422=MERGED   # Relay unicast channel observability
PR423=MERGED   # async MQTT / no MQTT log forwarding in physical harness
PR424=MERGED   # explicit single-radio ownership
PR425=MERGED   # transactional Direct failback + Relay channel fixation
```

Exact relevant merge commits:

```text
PR421=fb762e2ccb54393e7610339d05d164b7ea975bba
PR422=a01725644d9b0b4ee0a461c1579211829f1aa69e
PR423=35944fa928bb1fcf5527e476fb5dbfcfcdc11ead
PR424=664fcbe88bae76bc9fc6e5e240067e3cbae7c649
PR425=096528fbf61948d6c69197f1c8994ce8e7d672f4
```

## Frozen accepted baselines

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=FROZEN_PASS
KF089_RELAY_END_TO_END_CLOSEOUT=PASS
KF092_STATUS=CLOSED_PASS
```

## Current defect / repair sequence

### Watchdog

Source forensic plus RTC breadcrumb evidence identified synchronous MQTT/log forwarding during disappearing Direct Wi-Fi as the leading cause of the transition `TASK_WDT`.

PR #423 repaired the physical harness, and a fresh same-boot retest proved:

```text
TASK_WDT_REPRODUCED=false
UNCOMMANDED_REBOOT=false
PR423_TASK_WDT_REPAIR_PHYSICAL_VALIDATION=PASS
```

### Radio channel ownership

The same retest still had approximately a 110.061 s Manager-visible blackout and captured encrypted-unicast channel mismatch:

```text
CURRENT_CHANNEL=5
PEER_CHANNEL=11
RAW_ERROR=12397
RAW_ERROR_12397=ESP_ERR_ESPNOW_CHAN
```

PR #424 introduced explicit `DIRECT_WIFI / RELAY_ESPNOW / DIRECT_PROBE` ownership.

PR #425 then fixed:

- Direct logical state commit occurring before concrete channel restore;
- possible persistent `DIRECT + DIRECT_PROBE` no-send state after restore failure;
- Relay channel fixation before encrypted-peer installation and `RelayActive` commit;
- active Challenge path use of a new temporary off-channel operation after Relay already owns the radio.

## PR #425 CI / artifact status

```text
PR425_POST_MERGE_CI=PASS
POST_MERGE_GREENHOUSE_MANAGER_RUN=35293249780

PR425_EXACT_MAIN_ARTIFACT_BUILD=PASS
ARTIFACT_RUN_ID=35294123841
ARTIFACT_ID=10528055066
ARTIFACT_NAME=n3w-pr425-boardb-exact-main
```

Frozen write material:

```text
firmware.bin
SIZE=1128720
SHA256=bf3af5490745f1279a4e90d57a8e96b46525ae8debaf6f806ed2ae72180836c0

ota_data_initial.bin
SIZE=8192
SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

Board B has not yet been flashed with these PR #425 artifacts.

## Current acceptance matrix

```text
PR423_TASK_WDT_REPAIR=PASS
PR423_PHYSICAL_VALIDATION=PASS
PR424_SINGLE_RADIO_OWNERSHIP_SOURCE_REPAIR=PASS
PR425_FAILBACK_COMMIT_ORDER_SOURCE_REPAIR=PASS
PR425_POST_ACCEPT_CHANNEL_FIXATION_SOURCE_REPAIR=PASS
PR425_POST_MERGE_CI=PASS
PR425_EXACT_MAIN_ARTIFACT_BINDING=PASS

PR425_BOARD_B_DEPLOYMENT=PENDING
PR425_DIRECT_TO_RELAY_PHYSICAL_VALIDATION=PENDING
PR425_RELAY_STEADY_STATE_PROBE_GAP_VALIDATION=PENDING
PR425_RELAY_TO_DIRECT_FAILBACK_VALIDATION=PENDING
```

## Current ONE gate

```text
NEXT_ONE_GATE=N3W_PR425_BOARD_B_WRITE_TARGET_PREFLIGHT_20260918_01
BOARD_ACCESS_REQUIRED=true
PREFLIGHT_READ_ONLY=true
FLASH_WRITE=false
SERIAL_OPEN=false
T1_MUTATION=false
```

Next step: after explicit Board B read-only preflight authorization, freshly bind the physically connected target by ROM silicon identity and verify flash/security state. Do not write firmware until that preflight passes and a separate write authorization is granted.
