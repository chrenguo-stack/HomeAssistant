# 温室环境监测系统（ESP32-C6）
# N3-W FC-2 Final Firmware Artifact Evidence

版本：V1.0  
日期：2026-08-19  
范围：N3-W Final Closure / FC-2 only

---

## 1. 结论

FC-2 已完成：最终三板产品 E2E 所使用的 N3-W generic factory validation firmware 已从 Phase 5 final exact source 独立材料化，并完成 source/tree/config/toolchain/binary/package cryptographic freeze。

本阶段仅执行 GitHub cloud source/config/compile/package/hash 操作；未访问任何板卡、USB、串口、Flash、Erase 或 RF，也未修改生产 Broker、Manager 或 Home Assistant。

```text
FC2=PASS
FC2_SOURCE_BINDING=PASS
FC2_GENERIC_FACTORY_SOURCE_CONTRACT=PASS
FC2_EXACT_SOURCE_COMPILE=PASS
FC2_BINARY_FREEZE=PASS
FC2_PACKAGE_HASH=FROZEN
FINAL_N3W_FIRMWARE_ARTIFACT=FROZEN

FC3_STARTED=false
FC4_AUTHORIZED=false
READY_AUTHORIZED=false
MERGE_AUTHORIZED=false
```

---

## 2. Exact product source binding

唯一产品源码仍绑定 PR #324 的 Phase 5 final exact source；FC-2 helper 提交位于独立 build branch，不改变产品 HEAD。

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PR324_STATE=OPEN
PR324_DRAFT=true
PR324_MERGED=false
PR324_MERGEABLE=true

FINAL_SOURCE_HEAD=147ead29b5963150e17d582492b148854b0250b4
FINAL_SOURCE_TREE=9c62b1c87549120e0b8f53b0bd949ce5b00a0569
FINAL_FIRMWARE_TREE=0bc639f301dae9964061bd2b7b72a21ef2a88341
PR324_BASE_SHA=ab0adabe7d66c389f0496cf6d8386832c67debfe
```

目标配置：

```text
TARGET_CONFIG=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
TARGET_CONFIG_BLOB=6e40a198c5fcc9f445668da6e78f455a390e991f
TARGET_NAME=gh-n3w-phase4-generic
PACKAGE_ID=N3W-FC2-FINAL-147ead29-20260819
```

---

## 3. Generic factory source contract

材料化 workflow 在编译前重新验证 exact HEAD、repository tree、firmware tree 与 target config blob，并验证 generic factory source contract。

冻结结果：

```text
GENERIC_FACTORY_SOURCE_CONTRACT=PASS
LEGACY_RADIO_SELECTED=false
RETIRED_PRODUCT_RUNTIME_SELECTED=false
```

该 target 保持以下产品边界：

- factory YAML 不预置 NODE_ID / SYSTEM_ID / GATEWAY_ID；
- 不预置 peer MAC / peer key / SYSTEM_PEER_KEY / LMK；
- 不预置用户 Wi-Fi credential；
- 不预置 Manager/site 现场绑定；
- setup AP 使用通用 `Greenhouse N3-W Setup`；
- MQTT broker 仅为 `127.0.0.1` inert placeholder，`enable_on_boot: false`；
- selected runtime 为 `greenhouse_n3w_core` + simplified Phase 4 product runtime；
- retired legacy radio / old product runtime 不进入 selected product build。

因此该 artifact 可作为后续 FC-3/FC-4 同型号三板使用的唯一 final generic factory validation image；但本文件本身不授权任何物理写入。

---

## 4. FC-2 helper failure and repair

第一次材料化 run：

```text
FAILED_RUN_ID=32205370657
FAILED_JOB_ID=95927476903
CHECKOUT_EXACT_SOURCE=PASS
GENERIC_FACTORY_SOURCE_CONTRACT=PASS
EXACT_SOURCE_COMPILE=PASS
FREEZE_TOOLCHAIN_AND_BINARY_HASHES=FAIL
UPLOAD_ARTIFACT=SKIPPED
```

根因不是产品源码或编译失败，而是 post-build artifact collector 假定 `.esphome/build` 位于 checkout 根目录。ESPHome 2026.4.3 对该配置实际生成：

```text
source/firmware/esphome_rc/board_lab/n3w_phase4_physical/.esphome/build/gh-n3w-phase4-generic
```

修复仅调整 helper 的 `BUILD_ROOT`，按 `TARGET_CONFIG` 所在目录绑定真实 ESPHome build root；未修改 product source、target config、ESPHome version 或 compile contract。

```text
HELPER_BRANCH=build/n3w-fc2-final-artifact-20260819-v1
HELPER_FIX_COMMIT=aaa46d3d5d772bb8a09751a1b70a36d1df627af3
HELPER_FIX_MESSAGE=ci(n3w): fix FC-2 artifact build path
```

---

## 5. Successful exact-source materialization

成功 run：

```text
WORKFLOW=N3W FC2 Final Firmware Artifact
RUN_ID=32214600842
RUN_EVENT=pull_request
RUN_HEAD_BRANCH=build/n3w-fc2-final-artifact-20260819-v1
RUN_HEAD_SHA=aaa46d3d5d772bb8a09751a1b70a36d1df627af3
RUN_CREATED_AT=2026-08-19T04:07:35Z
RUN_UPDATED_AT=2026-08-19T04:11:49Z
RUN_CONCLUSION=success

JOB_ID=95953637621
JOB_NAME=exact-source-firmware-materialization
JOB_CONCLUSION=success
```

关键步骤全部为 success：

```text
Checkout exact Phase5 final source=PASS
Set up Python 3.11=PASS
Install exact ESPHome=PASS
Bind exact source and generic factory contract=PASS
Compile exact final N3-W validation firmware=PASS
Freeze toolchain and binary hashes=PASS
Upload frozen FC2 artifact=PASS
```

workflow helper HEAD 与 product source 被明确分离：helper run 由 `aaa46d3...` 触发，但 compile checkout 显式固定为 `147ead29...`。

---

## 6. Frozen build environment

```text
RUNNER_IMAGE=ubuntu-24.04
PYTHON_VERSION=3.11.15
ESPHOME_VERSION=2026.4.3
PLATFORMIO_CORE_VERSION=6.1.19
ESP_IDF_VERSION=5.5.4
PIO_PLATFORM_ESPRESSIF32=55.3.38
FRAMEWORK_ESPIDF_PACKAGE=3.50504.0
RISCV32_ESP_GCC=14.2.0
RISCV32_ESP_GCC_BUILD=crosstool-NG esp-14.2.0_20260121
PIP_ESPTOOL_VERSION=5.2.0
PIP_CRYPTOGRAPHY_VERSION=46.0.7
PIP_AIOESPHOMEAPI_VERSION=44.16.1
```

PlatformIO global package inventory、pip freeze、ESP-IDF version source 与 RISC-V toolchain version 均包含在冻结 package 内。

---

## 7. Final binary SHA-256 freeze

以下 hash 来自成功 run 上传的 artifact 内部 `BINARY_SHA256SUMS.txt`，并由下载后的冻结 tar 再次读取核验：

```text
BOOTLOADER_SHA256=a107f538e90357738d011c509e2d80a711e1206ad5ee4338a2400b152654f4f7
PARTITIONS_SHA256=6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca
APP_SHA256=fbb6a1b5d2fad984a0f809d422dbe2fcea687eba4eeea7771910bfb530111d81
FACTORY_IMAGE_SHA256=5632712cc9d79fc0633344a7cb58f53c11ff4e0bfa8a6a77391be77171377ab7
PACKAGE_SHA256=f8174bf3bdbed6083aef61a2092ed45fd15056ec7a1a34e586553a31bdf4e2ea
```

对应文件与尺寸：

```text
bootloader.bin  22576 bytes
partitions.bin   3072 bytes
app.bin       1106320 bytes
factory.bin   1171856 bytes
```

其中：

- `app.bin` 为 final application image；
- `factory.bin` 为 bootloader + partitions + OTA initial data + app 的 combined factory image；
- `PACKAGE_SHA256` 对应 deterministic tar `N3W-FC2-FINAL-147ead29-20260819.tar`；
- package 自身不包含自己的 hash，`.tar.sha256` 位于 tar 外部，因此不存在 circular self-hash。

---

## 8. GitHub artifact custody

```text
ARTIFACT_ID=9351968978
ARTIFACT_NAME=N3W-FC2-FINAL-147ead29-20260819
ARTIFACT_SIZE_BYTES=2324996
ARTIFACT_EXPIRED=false
ARTIFACT_CREATED_AT=2026-08-19T04:11:44Z
ARTIFACT_EXPIRES_AT=2026-09-18T04:11:44Z
ARTIFACT_ZIP_SHA256=400ef32624ac6af818eb7602140f5468afbecdf842b651aec5d58ad6af08b3a5
```

下载后的 GitHub ZIP SHA-256 与 GitHub artifact digest 一致；ZIP 内包含：

```text
N3W-FC2-FINAL-147ead29-20260819.tar
N3W-FC2-FINAL-147ead29-20260819.tar.sha256
```

其中 `.tar.sha256` 声明的 package SHA-256 与实际下载 tar 重新计算结果一致：

```text
PACKAGE_SHA256_MATCH=true
```

---

## 9. Safety / phase boundary

本 FC-2 仅为云端材料化与 cryptographic freeze：

```text
BOARD_ACCESS=false
USB_ACCESS=false
SERIAL_OPEN=false
FLASH=false
ERASE=false
RF_PHYSICAL_EXECUTION=false

PRODUCTION_BROKER_MUTATION=false
PRODUCTION_MANAGER_MUTATION=false
PRODUCTION_HA_MUTATION=false

R5_REPLAY=false
OLD_AUTH_REUSE=false
N3L=false
```

本 artifact 的冻结不等于 FC-3 开始，也不等于 FC-4 物理授权。后续三板物理测试必须继续遵循 Final Closure 计划的新独立 gate 与新明确 physical authorization。

---

## 10. Terminal evidence

```text
FC2=PASS
FC2_SOURCE_BINDING=PASS
FC2_GENERIC_FACTORY_SOURCE_CONTRACT=PASS
FC2_EXACT_SOURCE_COMPILE=PASS
FC2_BINARY_FREEZE=PASS
FC2_PACKAGE_HASH=FROZEN
FINAL_N3W_FIRMWARE_ARTIFACT=FROZEN

FINAL_SOURCE_HEAD=147ead29b5963150e17d582492b148854b0250b4
FINAL_SOURCE_TREE=9c62b1c87549120e0b8f53b0bd949ce5b00a0569
FINAL_FIRMWARE_TREE=0bc639f301dae9964061bd2b7b72a21ef2a88341
TARGET_CONFIG_BLOB=6e40a198c5fcc9f445668da6e78f455a390e991f

FC3_STARTED=false
FC4_AUTHORIZED=false
READY_AUTHORIZED=false
MERGE_AUTHORIZED=false
```

FC-2 在此终结；下一边界为 FC-3 three-board pre-authorization gate，本文件不越界执行。