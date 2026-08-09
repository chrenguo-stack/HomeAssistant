# 温室环境监测系统 N3-W / P5 / M02 R3 精确 Factory 镜像绑定执行包准备授权前开发交接文档（公开脱敏版）

- **文档版本**：PUBLIC V1.0
- **归档日期**：2026-08-09
- **项目仓库**：`chrenguo-stack/HomeAssistant`
- **阶段**：N3-W / P5 / R3 / M02 successor recovery
- **用途**：公开仓库中的 secret-free 状态锚点；新会话仍应同时读取用户持有的完整私有交接文档
- **安全原则**：本文件不含 PMK、LMK、application key、`.env` 内容、私密授权正文或私密 evidence 正文

---

## 0. 新会话恢复顺序

新会话不得直接执行下一门。必须先只读复核：

1. 本公开 handoff 与用户持有的完整私有 handoff；
2. `main`；
3. PR #292 / #293 / #294 / #276 的精确 state/base/HEAD；
4. PR #293 CI run `31270136039`；
5. PR #294 CI run `31292771162`；
6. 用户私有 handoff 中最后一个 Factory Verification R2 PASS terminal/hash。

确认 `NO_DRIFT=true` 后，再由用户重新明确授权：

```text
D1-N3W-P5-M02-SUCCESSOR-CHILD-RELAY-PHYSICAL-FIRMWARE-REPLACEMENT-EXECUTION-PACKAGE-PREPARATION-R3-EXACT-FACTORY-IMAGE-BOUND-20260809-01
```

在重新授权前不得生成或 claim R3 package。

---

## 1. 公开 GitHub 精确状态快照

```text
main=
8a57243fce0d347ebb20108f4ec5a2d5d4267486
```

PR #292：

```text
STATE=open
DRAFT=true
MERGED=false
BASE=main
BASE_SHA=8a57243fce0d347ebb20108f4ec5a2d5d4267486
HEAD=752c4709c6c9b60490dbcaf6da5807538dc03fa7
```

PR #293：

```text
STATE=open
DRAFT=true
MERGED=false
BASE_SHA=752c4709c6c9b60490dbcaf6da5807538dc03fa7
HEAD=3f3ccf641a77ef7c9891373299b0e2d4abe4dd6b
CI_RUN=31270136039
CI_CONCLUSION=success
ARTIFACT_ID=9025351711
ARTIFACT_ZIP_SHA256=8637cce425c453e86d17d4889b58807f50f98d032b88b64c7e1803a5f2fbf1b5
```

PR #294：

```text
STATE=open
DRAFT=true
MERGED=false
BASE_SHA=3f3ccf641a77ef7c9891373299b0e2d4abe4dd6b
HEAD=a2014677ea0449552f4f58fb0cca27a4f76e6542
CI_RUN=31292771162
CI_CONCLUSION=success
ARTIFACT_ID=9031937556
ARTIFACT_ZIP_SHA256=6474d8fad7ba222bff4891fc6fe80d0534a20e224007febc1d476573ffa1276f
```

PR #276：

```text
STATE=open
DRAFT=false
MERGED=false
BASE_SHA=2d444f3e392249c8d7bf1a1aa036e738a418d1cb
HEAD=239ea594c643d4990d449187f8b0cabae619e3d7
```

归档后新会话必须实时重新读取这些值。

---

## 2. 当前治理终态

```text
M02_ORIGINAL=CONSUMED_FAILED
M02_ORIGINAL_REPLAY_ALLOWED=false

M02_AEAD_RUNTIME_REPAIR=PASS
M02_MANAGER_REPAIR_DEPLOYMENT=PASS
M02_CHILD_RELAY_LIVENESS_HOSTONLY_REPAIR=PASS
M02_PRIVATE_BINARY_BINDING_R2=PASS

M02_PHYSICAL_PREPARATION_V1=CONSUMED_FAILED
M02_PHYSICAL_PREPARATION_R2=CONSUMED_FAILED

M02_FLASH_METADATA_INVENTORY=PASS
M02_FLASH_METADATA_DECISION_SLICE=PASS

M02_FACTORY_VERIFY_R1=CONSUMED_FAILED
M02_FACTORY_VERIFY_R2=PASS

LIVE_RELAY_FIRMWARE_UPDATED=false
LIVE_CHILD_FIRMWARE_UPDATED=false
M02_PHYSICAL_SUCCESSOR_COMPLETION=false

PATH_RELAY_RESEND_ALLOWED=false
M03_ALLOWED=false
```

原始 M02 的 `PATH RELAY` 已发送一次；不得重放。

---

## 3. PR #293 / #294 已完成内容

PR #293：修复 production Manager runtime 缺失 `cryptography` 的问题；专用 CI PASS。

PR #294：修复 Child relay-cache permanent-full、sequence burn、retry-exhausted discard 和 Relay REJECTED receipt 发出语义；专用 CI PASS。

两 PR 都必须继续保持 Draft / open / unmerged，直到独立授权。

---

## 4. Factory image 最终只读结论

最后一个 private successor gate 已证明：

```text
CANONICAL_PHYSICAL_WRITE_MODE=
EXACT_FROZEN_FACTORY_IMAGE_AT_OFFSET_0

WRITE_OFFSET=0x0
CHIP_ERASE_REQUIRED=false

PARTITION_MD5_VERIFIED_BOTH_ROLES=true
OTA_BOOT_SELECTION_VERIFIED=true
NVS_NONOVERLAP_VERIFIED=true
FACTORY_BIN_WRITE_CANDIDATE_VERIFIED=true
```

公开可记录的 factory SHA：

```text
RELAY_FACTORY_SHA256=
176bdff9151f40e6a1894000e73e4cf3f62f0c6a205846871d6c794d3abe081f
RELAY_FACTORY_SIZE=994384
RELAY_FACTORY_ERASE_END_4K=0xf3000

CHILD_FACTORY_SHA256=
0c4f90f9a3b7995a6f423fa4d41c31eee45ee6e09fa1d11c3ffba58d48525a6b
CHILD_FACTORY_SIZE=994528
CHILD_FACTORY_ERASE_END_4K=0xf3000
```

Partition table：

```text
MD5=84ee6cb6fc810b9aca7cf02a8490330a
MD5_RECORD_OFFSET=0xa0
END_MARKER_OFFSET=0xc0

otadata=0x9000/0x2000
phy_init=0xb000/0x1000
app0=0x10000/0x3c0000
app1=0x3d0000/0x3c0000
nvs=0x790000/0x70000
```

Factory 4 KiB erase-aligned end 为 `0xf3000`，不触及 `app1` 或 `nvs`。

OTA data 初始为空白，无 factory app partition，因此预期 first boot：

```text
app0 / ota_0 / 0x10000
```

以上只是 host-only/read-only 验证结果，不是 Flash 授权。

---

## 5. 最后一个 private PASS 的公开 hash 锚点

```text
FACTORY_VERIFICATION_R2_CLAIM_SHA256=
b1d07160e8939c57133a725f6a5d090735473886051beafbcf622e98f791bb08

FACTORY_VERIFICATION_R2_VERIFICATION_SHA256=
1e81a4e70e568fca401292ad01534d2ad79645d08d17f6583f24f60525fec647

FACTORY_VERIFICATION_R2_TERMINAL_SHA256=
69ed4dbb31473c02d2b0277626908ce2b65fc95ef10df13f82a6ee1159631014
```

私密 evidence 内容和设备私有绑定保留在用户私有根，不上传公开仓库。

---

## 6. 下一门：新会话重新授权前禁止执行

```text
NEXT_GATE=
D1-N3W-P5-M02-SUCCESSOR-CHILD-RELAY-PHYSICAL-FIRMWARE-REPLACEMENT-EXECUTION-PACKAGE-PREPARATION-R3-EXACT-FACTORY-IMAGE-BOUND-20260809-01

READY_FOR_D1_N3W_P5_M02_SUCCESSOR_CHILD_RELAY_PHYSICAL_FIRMWARE_REPLACEMENT_EXECUTION_PACKAGE_PREPARATION_R3_EXACT_FACTORY_IMAGE_BOUND_AUTHORIZATION=true
```

R3 preparation 仅允许 host-only execution engineering：绑定 exact factory image、绑定 esptool toolchain、生成 Relay-first future execution specification、定义 identity/verify/stop conditions。

在用户于新会话完成只读漂移核验并重新明确授权前：

```text
BOARD_ACCESS=false
USB_SERIAL_ACCESS=false
FLASH=false
ERASE=false
OTA=false
POWER_CHANGE=false
MQTT_PUBLISH=false
PATH_COMMAND=false
LIVE_STACK_MUTATION=false
PRODUCTION_NETWORK_ACCESS=false
MAIN_MODIFICATION=false
PR292_MODIFICATION=false
PR293_MODIFICATION=false
PR294_MODIFICATION=false
PR276_MODIFICATION=false
READY_MERGE_RELEASE_TAG=false
M03_ALLOWED=false
```

---

## 7. 归档分支约束

本公开文档应只存在于独立 handoff archive branch，不得提交到 `main` 或 PR #292/#293/#294/#276 的 source branch。

新会话应把 handoff archive branch 视为“文档归档”，不能把它的额外 documentation commit 误判为 PR #294 source drift。

至此公开归档结束。
