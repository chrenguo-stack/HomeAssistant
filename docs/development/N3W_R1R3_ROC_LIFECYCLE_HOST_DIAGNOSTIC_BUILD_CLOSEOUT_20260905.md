# N3-W R1R3 ROC Lifecycle Host Diagnostic Build — Closeout

Date: 2026-09-05  
Document class: `HOST_ONLY_DIAGNOSTIC_BUILD_CLOSEOUT`

## Gate result

```text
R1R3=ESPRESSIF_OFFICIAL_ROC_LIFECYCLE_AND_HOME_RETURN_BASELINE
HOST_ONLY=true
BOARD_ACCESS=false
FLASH=false
SERIAL_OPEN=false
RF_EXECUTION=false

R1R3_OFFICIAL_ROC_API_AUTHORITY=PASS
R1R3_CONTROL_HOST_COMPILE=PASS
R1R3_DUT_HOST_COMPILE=PASS
READY_FOR_R1R3_SHORT_PHYSICAL_GATE=true
GATE_RESULT=PASS
```

## Repository authority

```text
PARENT_R1R2_CLOSEOUT_COMMIT=3e3d3c8b6c8f91f522bbaf38debd96b5df096a1f
R1R3_DIAGNOSTIC_COMMIT=56d0ec6dcc633f3966affc68a9342716490e370e
R1R3_DIAGNOSTIC_TREE=98b04a42f8f043dc794d90926790e102e658900b
BRANCH=diag/n3w-r1r3-roc-lifecycle-ci-20260905

CURRENT_MAIN=127c3f1e89baaaba7b7fd60d6d263632d30b2461
CURRENT_MAIN_TREE=32135508818124e848bc895073b3cb6aaa6b9af3
PRODUCT_SOURCE_AUTHORITY=bff94bc4922d7a984eb1363cc24a163ad466a166
```

`main` and the product-source authority remained unchanged.

## Exact API authority

```text
ESPRESSIF_OFFICIAL_COMMIT=735507283d5b2f9fb363a1901172dbd9e847945d
PIOARDUINO_FRAMEWORK_COMMIT=8de41af2dbb81bc443a8d7986ebd152f82e10bba

OFFICIAL_PRIMITIVES=
  WIFI_ROC_REQ
  WIFI_ROC_CANCEL
  esp_now_remain_on_channel(...)
  esp_now_switch_channel_tx(...)
```

The CI gate byte-compared the relevant Espressif and pioarduino ESP-NOW / Wi-Fi type headers before compilation.

## Diagnostic harness authority

```text
DIAGNOSTIC_SOURCE_TREE_HASH=cec569a3c2cd024759474aea144448bbbc6b0c15
DIAGNOSTIC_MAIN_SHA256=9cac785e0019dc5d07e641c1c92092455d4a80f6100f170f743765774db07f38

R1R3_HOME_CHANNEL=1
R1R3_TARGET_CHANNEL=6
R1R3_ROC_WAIT_MS=3000
R1R3_ROC_OP_ID=77
EXPLICIT_ROC_CANCEL=true
ROC_REQ_AND_CANCEL_SAME_OP_ID=true
```

The revised harness is intentionally one-directional: Board B as DUT performs `ROC_REQ` on channel 6 while associated to Board A's channel-1 SoftAP; Board A sends one off-channel probe; Board B then performs explicit `ROC_CANCEL` with the same `op_id`, logs channel / association state at each lifecycle boundary, performs bounded reconnect only after cancellation, and finally attempts a normal channel-1 ESP-NOW home-path acknowledgement.

## GitHub Actions authority

```text
WORKFLOW=N3W R1R3 ROC Lifecycle Diagnostic Build
GITHUB_RUN_ID=33951308377
HEAD_SHA=56d0ec6dcc633f3966affc68a9342716490e370e
JOB_ID=101266547679
JOB_RESULT=success

ARTIFACT_ID=9964994892
ARTIFACT_NAME=n3w-r1r3-roc-lifecycle-diagnostic-build
ARTIFACT_SIZE_BYTES=7203965
ARTIFACT_DIGEST=sha256:89956c1d7d07e8a63c139d406ef394095ba6d6f20116b6c8e11e0a76771b2235
```

All workflow steps completed successfully, including exact authority materialization, CONTROL build, DUT build, artifact binding, and artifact upload.

## Artifact hashes

```text
control/bootloader.bin
0d5c8d265e0b4385a52e18fbf586f6741792c7aca557709cc2f5e927af7c4d71

control/flasher_args.json
cdd786791a540f67248043d1869c25d9e15ab2c137cb8be4f617db1f5ab1c0b0

control/n3w_r1r3_roc_lifecycle.bin
9d83ffa9672095a8145a91634c04899514808b0210eee2b90dbb15c3330dc31a

control/n3w_r1r3_roc_lifecycle.elf
ca6e6d4e830702db59bc0e8b30cd32695e6865fb6c94523595cded8999213a38

control/partition-table.bin
7f00b6c042a89b15b0cac534f82ed988caf29278ff5700b0c511eb1b5bb7c820

control/sdkconfig
624b31a5ca24d5f9c20bf78ddd5f5dd4cce313f0971302a6678ed478f9b44a28

dut/bootloader.bin
1db3cc48eda0bdfc5c2c634da849a121204e1b020a3c9a4b11c2a3d71bc2f7aa

dut/flasher_args.json
cdd786791a540f67248043d1869c25d9e15ab2c137cb8be4f617db1f5ab1c0b0

dut/n3w_r1r3_roc_lifecycle.bin
9a5a59e28473a880c717071659cfc7ec41c98542f77f670704e8e887036ac5ff

dut/n3w_r1r3_roc_lifecycle.elf
373d7ea6f8185d1fb99979a5d805ce68aeea575326ebc8f24ece8c1509d24c4b

dut/partition-table.bin
7f00b6c042a89b15b0cac534f82ed988caf29278ff5700b0c511eb1b5bb7c820

dut/sdkconfig
f18d3d2521884b6fa29b62df2204d7add1a2837ce7d30ce22171318cbc7a90ca

n3w-r1r3-build-evidence.txt
2837b8f31eea5d99e5c419940c6fbff0ab004ea84fa6aa24b36f73c28dbd571b

SHA256SUMS
1e183da1dfe549ec71161f0905d2b59b98cc0c0de33e577ea61f6f35a71aab24
```

The downloaded workflow artifact ZIP was independently re-hashed after the workflow completed:

```text
ARTIFACT_ZIP_SHA256=89956c1d7d07e8a63c139d406ef394095ba6d6f20116b6c8e11e0a76771b2235
```

## Boundary integrity

```text
PRODUCT_SOURCE_CHANGED=false
MAIN_CHANGED=false
PR361_CHANGED=false
BOARD_ACCESS=false
USB_ACCESS=false
FLASH=false
SERIAL_OPEN=false
RF_EXECUTION=false
T1_MUTATION=false
MANAGER_MUTATION=false
BROKER_MUTATION=false
DYNSEC_MUTATION=false
KF089_IMPLEMENTATION_AUTHORIZED=false
```

## Next route

The host-only gate is complete and stopped. The next gate, if separately entered, is a short Board A / Board B physical lifecycle check only. It must not chain the previous R1B/R1C bidirectional sequence. Its sole purpose is to establish:

```text
DUT_STA_ASSOCIATED_HOME_CH1
-> ROC_REQ_CH6
-> ONE_OFFCHANNEL_PROBE_RX
-> ROC_CANCEL_SAME_OP_ID
-> HOME_CHANNEL_CH1_RECOVERY
-> STA_ASSOCIATION_RECOVERY
-> NORMAL_HOME_CHANNEL_ESPNOW_ACK
```

No KF-089 product implementation is authorized by this closeout.
