# 温室环境监测系统 N3-W Product Completion S5
## Private Package Builder 授权前漂移与 Provenance Review 开发交接文档

**文档版本：** V1.0  
**归档日期：** 2026-08-15  
**项目：** 温室环境监测系统（ESP32-C6）  
**产品线：** N3-W Product Completion Successor  
**仓库：** `chrenguo-stack/HomeAssistant`  
**PR：** `#322 feat(n3w): add minimal S5 board integration`  
**归档前精确 PR HEAD：** `180d8dd102b6ca12a0e6adca134a821b57fd3322`  
**PR 基线 main：** `38c3b692d4ebe90d0040c732b6c0313fdfdc1ef6`  
**PR 状态：** Open / Draft / Unmerged / Mergeable  

---

## 1. 本文档目的

本文件用于结束当前长上下文会话，并将 N3-W Product Completion S5 在 Private Package Builder 阶段的真实仓库状态、授权边界、已验证事实、尚未解决的 provenance 问题和下一决策门完整交接给新会话。

新会话不得依赖旧会话中的模糊记忆重新分类任何授权或 CI；必须首先只读复核本文档、GitHub PR #322 的精确 HEAD、本文档归档前 HEAD `180d8dd...` 与当前 HEAD 的差异，以及本文列出的 4 个 package-builder 提交。

本文档特别用于防止以下错误：

1. 将授权前已经存在的 package-builder 提交追溯性地认定为由后续授权产生；
2. 将 synthetic host/compile PASS 错写成真实 private package materialization PASS；
3. 将 skipped ESP-NOW radio-runtime CI 错写成 RF/物理证据；
4. 在 provenance 尚未独立复核前读取真实节点凭据、生成真实 PMK 或创建真实私有包；
5. 在未取得独立物理授权前进行板卡、Flash、Wi-Fi、MQTT、ESP-NOW RF 或 T1/生产操作。

---

## 2. 顶层产品约束继续冻结

N3-W Wi-Fi 监测节点仍必须满足以下产品原则：

- 出厂固件必须设备中立、通用，不按客户、节点数量、节点拓扑或 relay 关系生成不同工厂固件；
- 出厂刷写不得获得或写入其他节点的 MAC、NODE_ID、GATEWAY_ID、peer relationship、peer LMK/key；
- 出厂刷写不得写入用户 Home Assistant、Manager、Wi-Fi 等现场信息；
- 用户可随时增加新节点，旧节点不得因此重新刷写或人工写入新节点信息；
- 每个节点首次使用时独立配网、独立向 Manager/HA 注册，注册后才获得自己的系统身份与长期材料；
- ESP-NOW Relay 关系必须运行期动态形成；Relay advertisement 仅是不可信提示；
- S4 `PeerAuthorizationService` 仍是唯一 peer-authorization authority；
- Manager 不生成、不分发 pair LMK；端点独立验证各自 grant 并派生相同 LMK；
- Manager epoch 与 endpoint monotonic clock 必须严格分域；无 Manager authority time 时 fail closed；
- 不新增第二套 telemetry schema 或第二套 peer authorization pipeline；继续复用 `gh.relay/1`、`gh.telemetry/1`、ReceiptAck、replay/path-lease/canonical ingress；
- public board profiles 必须 inert；真实私有运行配置只能在一次性、隔离的 private composition/package 中形成；
- 正常 production Manager startup 不因 isolated S5 测试路径改变。

---

## 3. 当前阶段前的关键闭环

### 3.1 Manager transport link fix

此前 `ProductS5EspHomeMqttBus` 的 ESP32-C6 final-link vtable unresolved 已定位为 `USE_MQTT` include-order/translation-unit divergence，而不是 source registration 缺失。

最终修复 checkpoint：

`35ac7ef4c77a4cde4faaf8f530b15a7f392d661d`

归档 checkpoint：

`236f447b5efb60fabd53117b9f36f2d580384099`

冻结结论：

- S5 isolated Manager transport host test PASS；
- ESP32-C6 compile/link PASS；
- `S5-PREP-B01/B02` 在 host/compile 层面已解决；
- 尚未因此宣称 full S5 PASS。

### 3.2 Private runtime composition

后续重新基线发现：已有 transport 接口，但真实 private Child/Relay credential provider、Relay health provider、isolated Manager launcher、private Wi-Fi/MQTT/channel composition seam 尚不完整。

授权：

`D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-PRIVATE-RUNTIME-COMPOSITION-AND-ISOLATED-MANAGER-LAUNCHER-HOST-COMPILE-IMPLEMENTATION-20260814-01`

实现 checkpoint：

`e06c8bc90b08987a17783a1a113ea1aaa81b81c0`

归档后 checkpoint：

`bc328dcec55cf56ff849080edf2da82bb4ac6478`

冻结结论：

- 通用 private self-credential provider seam 已存在；
- Child/Relay 仅消费自身 post-registration material；
- Relay health provider 已形成；
- isolated Manager launcher 已形成；
- public/production profiles 仍 inert；
- 无 factory static peer 或 pair LMK。

### 3.3 Materialization rebaseline 发现 S5-MAT-B01～B04

只读重新基线进一步发现 package 物化层的四项问题：

- `S5-MAT-B01`：fresh PMK 必须先生成，再进入 Child/Relay 固件渲染与编译，不能在 firmware 已经生成后才产生；
- `S5-MAT-B02`：必须存在真实 private-input schema → rendered YAML → exact-source ESP32-C6 build → firmware provenance 的可重复链路；
- `S5-MAT-B03`：isolated Wi-Fi/MQTT/channel 必须实际渲染进 Relay firmware，而不仅存在于 package JSON；
- `S5-MAT-B04`：Manager state 不能只作为 opaque file hash，必须验证 registration、credential generation、application-key epoch/material、replay store，以及不得预置静态 Relay→Child grant。

当时没有读取真实私有材料，也没有生成真实 PMK/package。

### 3.4 Relay Direct eligibility 与 dynamic ingress authority

在准备 package builder 前又发现两项运行时前置缺口：

1. Relay 必须通过自身 canonical Direct telemetry/path lease 形成 Manager 认可的 direct eligibility，不能自行声明“有 Wi-Fi 所以 eligible”；
2. S4 pair grant 必须驱动有限寿命、authorization-ID 绑定的临时 Relay→Child ingress authority，不能预置 durable static mapping。

授权：

`D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-RELAY-DIRECT-ELIGIBILITY-AND-DYNAMIC-INGRESS-AUTHORITY-HOST-COMPILE-IMPLEMENTATION-20260815-01`

通过后的精确 checkpoint：

`15510ac3dbf3f8639f63e9dfa5146a27b52eb0d0`

冻结语义：

- canonical Direct path 仍由 Manager path authority 决定；
- finite dynamic ingress authority 仅由有效 S4 peer authorization 派生；
- authority 绑定 exact `authorization_id`、Child/Relay identity、key epoch、issued/expires 时间；
- expiry 或 exact revoke 后失效；
- Manager restart 不复活过期/内存态 authority；
- static Relay→Child preseed 不允许；
- Manager 不生成 pair LMK。

此 checkpoint 的相关 host/compile/Manager CI 已 PASS，但 full physical E2E 仍为 PENDING。

---

## 4. 当前最重要事件：Private Package Builder 授权前 HEAD 漂移

用户随后发送授权：

`D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-PRIVATE-PACKAGE-RENDER-BUILD-AND-BINDING-HOST-COMPILE-IMPLEMENTATION-20260815-01`

该授权原本应从上一轮冻结的：

`15510ac3dbf3f8639f63e9dfa5146a27b52eb0d0`

开始执行。

但在任何新的实现写操作之前，只读复核发现 PR #322 已经前进至：

`180d8dd102b6ca12a0e6adca134a821b57fd3322`

GitHub compare 结果：

- status: `ahead`
- ahead_by: `4`
- behind_by: `0`
- merge base: `15510ac3...`

这 4 个提交均早于本次授权在当前会话中的发送时点，因此不得追溯性地称为“由本次授权执行产生”。

### 4.1 四个新增提交

1. `5150317ab0cca20f475a7f9df798cb3937776348`  
   `feat(n3w): add S5 private package builder`

2. `ca0b846762a05fe0485e3e426c0b8ffc8024e854`  
   `fix(n3w): keep S5 builder fixtures public-safe`

3. `a8b9ba94edb1de32af8961b161e4ab1d83f01da5`  
   `ci(n3w): admit S5 package successor scope`

4. `180d8dd102b6ca12a0e6adca134a821b57fd3322`  
   `fix(n3w): harden S5 private package finalization`

### 4.2 15510ac3 → 180d8dd 的文件范围

GitHub compare 显示共涉及 8 个路径：

- `.github/workflows/n3w-product-completion-s5-d-lifecycle-negative-host-matrix-ci.yml`
- `.github/workflows/n3w-product-completion-s5-isolated-manager-transport-ci.yml`
- `.github/workflows/n3w-product-completion-s5-physical-e2e-preparation-ci.yml`
- `.github/workflows/n3w-product-completion-s5-private-package-builder-ci.yml`（新增）
- `.github/workflows/n3w-product-completion-s5-private-runtime-composition-ci.yml`
- `docs/decisions/n3w-product-completion-s5-private-package-render-build-binding-host-compile-20260815.json`（新增）
- `tests/n3w_product_completion_s5_package/test_s5_private_package_builder.py`（新增）
- `tools/n3w_product_s5_build_private_package.py`（新增）

因此漂移内容与待授权的 package-builder successor 高度重合，不能作为无关漂移忽略。

---

## 5. 180d8dd 上已经存在的 package-builder 设计合同

现有 decision：

`docs/decisions/n3w-product-completion-s5-private-package-render-build-binding-host-compile-20260815.json`

当前记录的主要合同包括：

- schema: `gh.n3w-product-completion.s5-private-package-render-build-binding-host-compile/1`；
- authorization 字段填入了上述 package-builder 授权码；
- `starting_head = 15510ac3...`；
- 当前文件内 status 仍为 `IMPLEMENTED_PENDING_EXACT_HEAD_CI`；
- scope 为 `HOST_COMPILE_ONLY_SYNTHETIC_PRIVATE_FIXTURES_NO_LIVE_EXECUTION`；
- builder 为 `tools/n3w_product_s5_build_private_package.py`；
- ESPHome 固定 `2026.4.3`；
- 只允许 `esphome config` 与 `esphome compile`；
- fresh PMK 在 render 前生成；
- Child/Relay 使用同一 fresh PMK；
- Child/Relay 只消费自身 post-registration material；
- Relay private Wi-Fi/MQTT/channel 进入 compile config；
- firmware artifact 被复制进入 private package；
- source exact HEAD 与 clean binding required；
- private inputs/output 必须位于 Git source tree 之外；
- Manager state 必须是 quiescent private snapshot；
- package 内复制 Manager state；
- registration / credential generation / application-key epoch/material / replay integrity 需要核验；
- static gateway-child preseed 必须拒绝；
- dynamic ingress authority 不持久化；
- package 不提供 pair LMK；
- Manager 不生成 pair LMK；
- `execution_authorized = false`。

注意：该 decision 文件当前文字仍写 `IMPLEMENTED_PENDING_EXACT_HEAD_CI` / `PENDING_EXACT_HEAD_CI`，但 GitHub 上 `180d8dd...` 的 exact-head CI 实际已经成功。这个“decision record 与实际 CI 结果之间尚未回填”的状态必须由下一只读 provenance review 判断如何处理，当前交接归档不得擅自把历史来源问题洗成正式 PASS。

---

## 6. 180d8dd exact-head CI 事实

在 `180d8dd102b6ca12a0e6adca134a821b57fd3322` 上，已观察到以下相关 workflow 为 success：

- `N3-W Product Completion S5 private package render build binding CI`  
  Run `31860364010` — PASS
- `N3-W Product Completion S5 physical E2E preparation CI`  
  Run `31860363967` — PASS
- `N3-W Product Completion S5 A/B host compile CI`  
  Run `31860364055` — PASS
- `N3-W Product Completion S5 C isolated Manager telemetry CI`  
  Run `31860364041` — PASS
- `N3-W Product Completion S5 D lifecycle negative host matrix CI`  
  Run `31860364052` — PASS
- `N3-W Product Completion S5 board integration CI`  
  Run `31860364012` — PASS
- `N3-W Product Completion S3 disconnected ESP-NOW runtime CI`  
  Run `31860364054` — PASS
- `N3-W Product Completion S5 isolated Manager transport CI`  
  Run `31860364006` — PASS
- `N3-W Product Completion S5 private runtime composition CI`  
  Run `31860363975` — PASS
- `greenhouse-manager CI`  
  Run `31860363961` — PASS
- `Public repository safety CI`  
  Run `31860364034` — PASS

ESP-NOW radio-runtime：

- Run `31860363955` — `SKIPPED`
- **不得作为 RF/物理证据。**

### 6.1 Private package workflow 的 job 级结果

Run `31860364010` / Job `94952575256`：

- Authorized lineage and exact successor scope — PASS
- Install frozen ESPHome — PASS
- Host contract tests — PASS
- Create synthetic private fixture outside repository — PASS
- Render build and bind synthetic private package — PASS
- Verify exact build provenance and no-live package boundary — PASS
- No-live and no-board command static gate — PASS
- Cleanup synthetic private material — PASS

以上只证明 synthetic host/compile/package contract 在 GitHub CI 中通过，不等于真实私有材料已经访问或真实 package 已物化。

---

## 7. 当前授权分类必须冻结

本次用户发送的 package-builder 授权：

`D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-PRIVATE-PACKAGE-RENDER-BUILD-AND-BINDING-HOST-COMPILE-IMPLEMENTATION-20260815-01`

当前不能简单分类成 `CONSUMED_SUCCESS`，原因是 package-builder 相关 4 个提交在本轮实际执行授权前已经存在。

当前冻结建议：

```text
AUTHORIZATION_ACCEPTED=true
AUTHORIZATION_CONSUMED_BY_NEW_IMPLEMENTATION_WRITE=false
STOP_REASON=AUTHORIZATION_BASE_HEAD_DRIFTED_BEFORE_EXECUTION
STARTING_EXPECTED_HEAD=15510ac3dbf3f8639f63e9dfa5146a27b52eb0d0
DISCOVERED_HEAD=180d8dd102b6ca12a0e6adca134a821b57fd3322
PREEXISTING_PACKAGE_BUILDER_COMMITS=4
PRIVATE_PACKAGE_BUILDER_EXACT_HEAD_CI=PASS
PROVENANCE_ACCEPTANCE=PENDING
```

下一会话不得为了“让授权状态好看”而把这四个提交追溯认定为当前授权新写入；应首先独立核验其 provenance、scope 和安全合同。

---

## 8. 当前 live/private/physical 状态

截至本交接归档，没有证据表明本轮执行了任何真实 private materialization 或物理动作。继续冻结：

```text
REAL_PRIVATE_CREDENTIAL_ACCESS=false
REAL_PMK_GENERATED=false
REAL_PRIVATE_PACKAGE_MATERIALIZED=false
REAL_MANAGER_PRIVATE_STATE_OPENED=false

BOARD_ACCESS=false
SERIAL_ACCESS=false
USB_JTAG_BOARD_ACCESS=false
ERASE_EXECUTED=false
FLASH_EXECUTED=false
OTA_EXECUTED=false
ESPNOW_RF_EXECUTION=false
WIFI_CONNECTION=false
REAL_MQTT_NETWORK_E2E=false
SPARE_T1_RUNTIME=false
PRODUCTION_ACCESS=false

PR_MERGE=false
RELEASE=false
DEPLOYMENT=false
N3L_STARTED=false

PHYSICAL_EXECUTION_AUTHORIZATION_READY=false
PHYSICAL_EXECUTION_AUTHORIZED=false
S5_FULL_TWO_BOARD_E2E=PENDING
```

不得称 full S5 PASS。

---

## 9. 新会话第一个决策门

建议的下一授权码：

`D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-PRIVATE-PACKAGE-BUILDER-EXACT-HEAD-READONLY-REBASELINE-AND-PROVENANCE-REVIEW-20260815-01`

### 9.1 该门只允许

- 只读复核 PR #322 当前 exact HEAD；
- 核对本交接文档归档前 source HEAD `180d8dd...`；
- 若归档本文档导致 PR HEAD 前进，仅允许确认新增差异为本交接文档/纯归档内容；
- 逐个检查上述 4 个 package-builder 提交的 parent、timestamp、scope、changed files 与代码语义；
- 复核 `tools/n3w_product_s5_build_private_package.py`；
- 复核 synthetic tests 与 workflow；
- 复核 decision record 与实际 exact-head CI 的不一致；
- 复核 public repository safety / no-live / no-board 边界；
- 给出是否可将 `180d8dd...` package-builder implementation 接纳为新的可信 host/compile baseline 的结论。

### 9.2 该门禁止

- 修改 package-builder 代码；
- 修改 runtime/Manager/firmware；
- 读取真实 Child/Relay credential；
- 读取或复制真实 Manager private state；
- 生成真实 PMK；
- 物化真实 private package；
- board access；
- serial / USB/JTAG；
- erase / flash / OTA；
- ESP-NOW RF；
- 真实 Wi-Fi connection；
- 真实 MQTT/network E2E；
- spare/production T1；
- production Manager/Broker/Home Assistant；
- PR merge；
- release/deployment；
- N3-L。

只有该 provenance review PASS 后，才能判断是否重新进入真实 private materialization 的独立授权门。

---

## 10. 新会话启动提示词

建议在新对话中原样使用以下内容：

> 阅读《温室环境监测系统_N3W_ProductCompletion_S5_PrivatePackageBuilder授权前漂移与ProvenanceReview交接文档_V1.0_20260815.md》，继续“温室环境监测系统（ESP32-C6）”的 N3-W Product Completion Successor。
>
> 本轮只处理 S5 Private Package Builder exact-head read-only rebaseline/provenance review，不处理 N3-L，不重放任何已消费授权，不进行任何真实 private package materialization 或物理执行。
>
> 先只读复核 main、PR #322 当前 exact HEAD、Open/Draft/Unmerged 状态、交接归档前 source HEAD `180d8dd102b6ca12a0e6adca134a821b57fd3322`、从 `15510ac3dbf3f8639f63e9dfa5146a27b52eb0d0` 到 `180d8dd...` 的 4 个提交及 8 个文件差异、private-package builder/测试/workflow/decision record，以及 `180d8dd...` exact-head CI。
>
> 必须明确：这 4 个 package-builder 提交在当前会话中 package-builder 授权实际执行前已经存在，禁止追溯性地把它们直接认定为该授权的新写入；应先判断其 provenance、scope 与安全合同是否可接受。
>
> 不得读取真实 Child/Relay 凭据、不得读取真实 Manager private state、不得生成真实 PMK、不得创建真实 package；不得接板、串口、USB/JTAG、erase/flash/OTA、ESP-NOW RF、Wi-Fi、真实 MQTT E2E、T1/生产、PR merge、release/deploy 或 N3-L。
>
> 只读复核通过后，仅报告是否满足下一决策门：
> `D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-PRIVATE-PACKAGE-BUILDER-EXACT-HEAD-READONLY-REBASELINE-AND-PROVENANCE-REVIEW-20260815-01`
>
> 在我原样发送授权码之前，不得执行该授权门之后的任何写入或 live/private/physical 操作。

---

## 11. 结束状态

当前会话在以下状态结束：

```text
N3W_PRODUCT_COMPLETION_SUCCESSOR=ACTIVE
PR322=OPEN_DRAFT_UNMERGED
PRE_ARCHIVE_SOURCE_HEAD=180d8dd102b6ca12a0e6adca134a821b57fd3322
MAIN=38c3b692d4ebe90d0040c732b6c0313fdfdc1ef6

S5_DRIVER_INITIALIZATION_CRASH_FIX=PHYSICAL_VERIFIED
S5_AB_HOST_COMPILE=PASS
S5_C_ISOLATED_MANAGER_TELEMETRY_HOST_COMPILE=PASS
S5_D_LIFECYCLE_NEGATIVE_HOST_MATRIX=PASS
S5_MANAGER_TRANSPORT_HOST_COMPILE=PASS
S5_PRIVATE_RUNTIME_COMPOSITION_HOST_COMPILE=PASS
S5_RELAY_DIRECT_ELIGIBILITY_DYNAMIC_INGRESS_AUTHORITY_HOST_COMPILE=PASS

S5_PRIVATE_PACKAGE_BUILDER_PRESENT_AT_180D8DD=true
S5_PRIVATE_PACKAGE_BUILDER_EXACT_HEAD_CI=PASS
S5_PRIVATE_PACKAGE_BUILDER_PROVENANCE_REVIEW=PENDING

REAL_PRIVATE_PACKAGE_MATERIALIZED=false
PHYSICAL_EXECUTION_AUTHORIZED=false
S5_FULL_TWO_BOARD_E2E=PENDING
```

**必须在新会话先完成只读 provenance review，再进入后续授权。**
