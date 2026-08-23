# N3-W F350 Codex Development / RCA / Test Archive — 2026-08-23

## 1. Scope

本归档记录从 `温室环境监测系统_F350_BSR-R2_Epoch3_Helper_RCA_Codex交接文档_V1.0_20260823.md` 交给 Codex 后，到本归档冻结点为止实际发生的工作。

范围包括：

- exact authority、helper source、目标 artifact 和既有 durable state 的复核；
- selected helper-specific offline bundle 的 same-name 搜索、generated-manifest compatibility probe 和离线 Control-A 构建；
- F350 helper app0 / active OTA slot / boot handoff / NVS durable transition RCA；
- 经逐次独立授权执行的 direct-ROM、controlled attach+run、`FLASH_END(0)`、外部 hard reset 和只读 NVS 取证；
- 产品 app-only restore 的 host-only authority 和离线依赖材料设计。

本归档不包含新的产品功能开发，不重放 BSR-R2，不执行 Manager/Broker/HA mutation，不恢复产品 app，不进入 FC4 Final Physical Acceptance。

## 2. Starting Baseline

交接时可复核的冻结状态：

| 项目 | 值 |
|---|---|
| Repository authority | `chrenguo-stack/HomeAssistant` |
| Authority commit | `4f39013222e53ac353846d5b2c5528c9c3be0ed3` |
| Authority tree | `3bf9e5364fe09e60a0de277bd0e160c2975b8c4b` |
| Helper source | `firmware/esphome_rc/board_lab/n3w_boot_session_recovery/pairing_epoch_successor_helper.yml` |
| Helper source blob | `d18c5095038a8df9fbd4b526c003503e9287aaf6` |
| Target helper app SHA-256 | `aff3d0d281461031d0f4c956ce0e1cf8e055296c3e3ee068ff706eda322c43c4` |
| Pairing epoch on board | `2` |
| Epoch 3 durable | `false` |
| BSR-R2 executed | `false` |
| Product app restored | `false` |
| Last proven physical state | `ROM_DOWNLOAD_MODE` |
| FC4 Final Physical Acceptance | `NOT_PASS_YET` |

原 selected R2 helper bundle 的安全 binding：

- `dependencies.lock` SHA-256: `d3edfd47d6c9992e576ddfa42fa3d3935b4fc4546d531e7865ce82b88a5fdee4`
- generated `src/idf_component.yml` SHA-256: `7f89ed0deb6b575bc33901bbb1ae43a8616fca1ecad63241f8e8ba5ad6423c18`
- direct dependency: `bblanchon/arduinojson@7.4.2`
- framework/target: `idf@5.5.4`, `esp32c6`

## 3. Development Timeline

1. 使用 Python 代替失败的 macOS awk executor，从 exact helper YAML 唯一提取 `esphome.name=gh-n3w-repair-epoch-successor`；authority blob 保持匹配。
2. 只读扫描本机 surviving `.esphome/build/gh-n3w-repair-epoch-successor`，未发现 complete same-name bundle。
3. 生成当前 helper manifest 并与 selected R2 helper bundle 比较；direct dependency、版本、IDF 和 target 兼容。
4. Control-A 早期尝试分别停在 executor 诱发的 Python dependency install 和 IDF Component Manager registry resolution；编译器尚未到达时的旧分类结果被 supersede。
5. 注入 exact-bound helper lock/managed component 后，在 `PLATFORMIO_OFFLINE=1` 和 loopback proxy fail-closed 条件下完成临时 Control-A 构建。Control-A 生成代码明确冻结 nonzero recovery floor（原值只保留于 private evidence）、current epoch `2`、successor epoch `3`。
6. Control-A 新构建 whole-image SHA 与目标 helper 不同；未把“不相同”误判为 tuple 不同。Control-A generated source 只证明该次 Control 构建参数为 `2 -> 3`，不证明目标 helper 的 bit-for-bit compile-time provenance；目标 helper 的 `2 -> 3` 语义由 exact app0 binding、active-slot forensic、hard-reset success marker 和 durable NVS transition 共同证明。
7. 经独立授权对 F350 执行 helper app0 binding/write/readback 和多条启动路径 RCA。app0 独立 readback 与目标 helper SHA 完全一致。
8. direct-ROM API、controlled attach+run、`FLASH_END(0)` 等路径均未产生可接受的 application marker 或 durable epoch transition；active OTA forensic 证明目标为 app0，wrong-slot 假设被排除。
9. 最终在一次明确外部 hard reset 前启动连续日志捕获，观察到一次 helper success marker；随后只读 NVS 证明 pairing epoch 从 `2` 单调推进到 `3` 且 durable。
10. 进入产品恢复 host-only 设计：复核此前 F350 产品 app-only restore authority 仍是 exact-current `n3w_phase4_physical/generic.yml`，但原产品二进制和 same-name build 已不存在。
11. 当前产品 generated manifest 要求 ArduinoJson、mDNS 和 multipart-parser；helper-only bundle 不兼容。只读找到两组等价的完整本地 product-compatible bundle，完成 manifest compatibility PASS；没有开始产品 build 或 flash。

## 4. Problems Encountered

### 4.1 macOS awk quoting/parser failure

- **现象**：authority helper binding 已 PASS 后，复杂 awk 在解析 `esphome.name` 时语法错误；复制、构建和板卡访问均未开始。
- **触发条件**：macOS/BSD awk 执行带多层 shell quoting 和状态逻辑的嵌入脚本。
- **根因**：host executor parser 不可移植，不是 source drift 或 bundle incompatibility。
- **旧判断**：无；该阶段正确 fail-closed，但旧 awk executor 不可重放。
- **修复**：Python 对 exact YAML 文本做作用域受限、唯一值提取。
- **防回归**：KF-055；parser smoke test、exact blob binding、唯一 `esphome.name`。
- **验证**：成功提取 `gh-n3w-repair-epoch-successor` 并完成 same-name 扫描。
- **残余风险**：仓库尚无通用 executor 实现；本轮只有流程 guard。

### 4.2 Offline build failure misclassification and incomplete bundle scope

- **现象**：早期 Control-A 被误分为 esptool/CPP failure；真实日志先后显示 Python dependency install 和 registry resolution，CPP compiler 尚未到达。产品探针又发现 helper bundle 缺少两个直接依赖。
- **触发条件**：临时构建使用共享 PioArduino/ESP-IDF 工具链但没有完整、与当前 manifest 匹配的 lock/managed component set。
- **根因**：failure classifier 过宽；离线 bundle compatibility 只看共同组件/target，没有先 exact-bind 当前 generated manifest 的完整 direct dependency set。
- **被 supersede 的旧判断**：`ESPTOOL_LOCAL_INSTALL_STAGE_FAILURE` 和 `CPP_COMPILE_ERROR`；两者均无编译器证据。
- **修复**：按第一个真实失败阶段分类；先生成 manifest，再精确绑定 lock、target、版本和 managed-component tree；保持 shared `.platformio` 不变。
- **防回归**：KF-056；helper/product bundle 分域，不允许因同为 ESP32-C6/IDF 就互换。
- **验证**：helper Control-A 离线构建 PASS；产品 current manifest 与完整三组件本地 bundle 逐字节匹配。
- **残余风险**：当前产品临时离线 build 尚未执行；产品 artifact SHA 为 UNKNOWN。

### 4.3 Whole-image mismatch did not disprove the compiled tuple

- **现象**：新 Control-A app SHA-256 为 `2ad1038b8d921e3e480d72e302645b2603b22e946469307d1189c96fda84efcb`，与目标 helper `aff3d0d2...43c4` 不同。
- **触发条件**：在不同临时 build context/time 中重建 exact source 和 substitutions。
- **根因**：whole-image 差异的精确来源未证明；不能把整个 image hash 当作 compile-time tuple 的唯一 oracle。
- **被 supersede 的旧判断**：`whole-image mismatch == tuple mismatch` 被拒绝。
- **修复**：保存 Control-A ELF 和 generated `main.cpp`，直接复核该次 Control 构建的编译常量和控制流；目标 helper 另以 runtime evidence chain 验证，不把两者混为同一 provenance oracle。
- **验证**：Control-A generated source 明确为 current epoch `2`、successor epoch `3`，且先验证 recovery oracle、再单调写入、最后 readback verify。目标 helper 的运行时语义由 exact app0 readback、active app0、hard-reset marker 和 durable NVS `2 -> 3` transition 证明。
- **残余风险**：目标 helper 与新 Control-A 的 bit-for-bit reproducibility 未复现；`TARGET_BINARY_WHOLE_IMAGE_PROVENANCE=NOT_BIT_FOR_BIT_REPRODUCED`。

### 4.4 ROM/stub handoff was not an application boot oracle

- **现象**：目标 helper 已写入 app0 且独立 readback SHA 正确，但多种 ROM/stub run handoff 未产生 success marker，NVS 仍为 epoch 2。
- **触发条件**：ESP32-C6 native USB Serial/JTAG 下依赖 direct-ROM API、attach+run、`FLASH_END(0)` 或晚启动的观察窗口证明应用启动。
- **根因**：这些路径没有形成已证明的外部 hard-reset application boot；不是 helper source、tuple、wrong-slot 或 app corruption 的证据。各失败 handoff 的更低层差异仍为 UNKNOWN。
- **被 supersede 的旧判断**：无 marker 曾支持“helper 未执行/tuple 或固件错误”的假设；app0 readback、active-slot forensic 和最终 hard reset 证据推翻了该归因。
- **修复**：把 write/readback、boot action、continuous serial observation 和 durable NVS 取证分成独立 oracle；最终使用明确外部 hard reset。
- **防回归**：KF-057。
- **验证**：10 秒连续捕获 2324 bytes，success marker 恰好一次；无参数拒绝、oracle 拒绝、persist/verify failure、panic、abort、invalid-header 或 download-mode marker。随后只读 NVS 语义验证 epoch `3`。
- **残余风险**：为什么前三种 handoff 没有形成等价启动仍未定位到芯片/工具实现细节；流程上已 fail-closed。

### 4.5 Product restore artifact was stale/missing

- **现象**：此前产品 restore 记录绑定 app SHA `a32eddf3d0663d29a1023b15a79ddfa67b1f82d749214da496dfcb00462bf418`，但该二进制与 same-name build 不再存在。
- **触发条件**：helper RCA 完成后准备恢复产品 app0。
- **根因**：历史临时 artifact 未作为可持续 public artifact 保存；现存 S5 R8 package 绑定旧 source，不能替代 current authority。
- **修复**：重新绑定 current product YAML，并在新 build 前执行 current generated-manifest compatibility probe。
- **验证**：产品 YAML SHA-256 仍为 `3ff521c65e1fea2b1406d9994d583c43ec64cb2dbe33901aad7d88c661612def`；source 无 drift；兼容 bundle已找到。
- **残余风险**：新的 current product app 尚未构建、未写入、未启动验证。

## 5. Superseded Hypotheses

- “没有 helper marker即 helper source/tuple 错误”：被 exact generated tuple、app0 readback 和最终 hard-reset success 推翻。
- “helper可能写入非 active OTA slot”：被只读 otadata/partition forensic 推翻；active slot 为 app0。
- “esptool hard reset 或 ROM/stub run return 即足以证明 application boot”：被多次无 durable transition 的实际结果推翻。
- “Control-A 的 esptool/CPP compiler 失败”：编译器未到达；真实问题是 executor dependency install 与 IDF Component Manager registry resolution。
- “同一个 ESP32-C6/IDF bundle 可同时服务 helper 和 product”：产品 generated manifest 的额外 mDNS/multipart-parser 依赖推翻该假设。
- “S5 R8 固件可作为 current exact product restore”：其 source head 早于当前产品/boot-session/epoch修复，不能称为 current exact。

## 6. Source Changes

本轮 Codex RCA 没有修改产品、helper 或 Manager source。进入 Codex 时，restart-safe epoch successor helper 与 Manager epoch3 recovery source/test 已存在于 authority history。本轮只验证其构建、运行和 durable semantics。

归档阶段只修改：

- `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`
- 本文档

## 7. Test Changes

本轮没有新增或修改自动化测试代码。新增的是 KF-055/KF-056/KF-057 流程型 regression guard 和本归档的可审核证据索引。

## 8. Test Results

### 8.1 Local unit/static tests

- `python -m pytest -q tests/n3w_boot_recovery`：`10 passed`。
- `python -m pytest -q host/greenhouse-manager/tests/runtime/test_n3w_epoch3_expired_recovery.py`：`4 passed`。
- `python tools/check_public_repository_safety.py`：PASS。
- 首次使用系统 Python 的两次 pytest：`NOT_EXECUTED_ENVIRONMENT_MISSING`（没有 pytest）；随后按 KF-027 使用既有验证环境重跑 PASS。这不是测试失败。

### 8.2 Compile/build tests

- Helper current-manifest probe：PASS。
- Helper temporary offline Control-A compile：PASS；app size `566304` bytes，SHA-256 `2ad1038b8d921e3e480d72e302645b2603b22e946469307d1189c96fda84efcb`。
- Product `esphome compile --only-generate` under offline/network-fail-closed environment：PASS。
- Product full compile：`NOT_EXECUTED`。

### 8.3 Host-only RCA

- exact authority/helper/source binding：PASS。
- surviving same-name helper bundle search：0 complete bundles。
- helper selected-bundle current-manifest compatibility：PASS。
- product source binding：PASS。
- product helper-bundle compatibility：FAIL（依赖集合不完整，正确 fail-closed）。
- product complete local-bundle compatibility：PASS。

### 8.4 Physical board tests

以下测试均来自本轮各自独立授权；授权已消费，不可重放：

- helper app0 write + independent readback：PASS。
- direct-ROM API Gate：未证明 application boot；epoch 保持 2。
- controlled-ROM attach+run Gate：未证明 application boot；epoch 保持 2。
- controlled-ROM `FLASH_END(0)` reboot Gate：未证明 application boot；epoch 保持 2。
- external hard-reset continuous boot capture：PASS；success marker exactly once。
- post-hard-reset read-only NVS semantic forensic：PASS；epoch 3 durable。

以上 physical 结果不自动授权或证明 BSR-R2、产品恢复、Manager cutover、telemetry E2E 或 FC4 Final Acceptance。

### 8.5 CI

归档分支 exact-head CI 将在 push/PR 后单独记录；提交前为 `NOT_EXECUTED`，不得写作 PASS。

### 8.6 Tests not executed

- 新的 current product full offline build。
- 产品 app0 restore、启动、runtime 或 telemetry。
- BSR-R2 Manager cutover。
- Broker/Manager/HA production-equivalent mutation。
- FC4 Final Physical Acceptance。

## 9. Evidence

仅列安全摘要；以下 private evidence 目录内容本身不进入 Git：

| Sanitized evidence reference | Safe result |
|---|---|
| `N3W_FC4_F350_CONTROL_A_OFFLINE_SUCCESSOR_20260823_R3` | firmware SHA-256 `2ad1038b8d921e3e480d72e302645b2603b22e946469307d1189c96fda84efcb`; ELF SHA-256 `ce7fd5d3dc9d3faa33aaa76ad54b24fdcf91379b4bbe9793c78f9a0f45eaabe8`; generated source SHA-256 `a59fda9c79e987b4f5553653eadb71e3cbeaf3d96bb289885982835558059961` |
| `N3W_FC4_F350_EXISTING_HELPER_UNINTERRUPTED_EPOCH3_20260823_R1` | app0 readback SHA-256 `aff3d0d281461031d0f4c956ce0e1cf8e055296c3e3ee068ff706eda322c43c4`; pre-final NVS SHA-256 `901962cc58e227813a4f766ae15eb3e86658411dad613202eb37b92aa33c7c60` |
| `N3W_FC4_F350_OTADATA_ACTIVE_SLOT_FORENSIC_20260823_R1` | otadata SHA-256 `8ba3b110139f45443d4f268d1a3373ef99a1718b71d51664531b83ee2d4b91a3`; active slot app0 |
| `N3W_FC4_F350_HARD_RESET_EPOCH3_DURABLE_20260823_R1` | boot log SHA-256 `eb646ed2c37018227de9423846f8d8a32933a4d7172374dbf32feaabe590f285`; post-reset NVS SHA-256 `c732d998405f997af995a501ac8062a2ed4100c24ae1640a7578b7ceff9c9acd` |
| Current product manifest probe | generated manifest SHA-256 `5e5fc5629fb719c87421e889bb186990cf246e99b9412f03eab6276456327543`; compatible lock SHA-256 `8be21d04555b6de009758fbf7242338e7372db039c7a5fcce2772652e33da89c`; managed-component tree SHA-256 `8f4ce2e7745528beb9d3bb70f74dffa9631a74479856a97874abde6e19f52f74` |

NVS semantic evidence：page 0–3 CRC valid；authority-defined epoch record 的 magic/version/reserved 和 embedded SHA-256 valid；epoch `3`。原始 NVS、logs、ROM identity 和 device identifiers 均保持 private。

## 10. Current Frozen State

| 项目 | 冻结值 |
|---|---|
| `PAIRING_EPOCH_CURRENT` | `3` |
| `PAIRING_EPOCH_3_DURABLE` | `true` |
| `F350_EPOCH3_HELPER_RCA` | `RESOLVED_PASS` |
| `BSR_R2_EXECUTED` | `false` |
| `PRODUCT_APP_RESTORED` | `false` |
| `F350_LAST_PROVEN_PHYSICAL_STATE` | `RAM_STUB_AFTER_READ_ONLY_NVS_READBACK` |
| `FC4_FINAL_PHYSICAL_ACCEPTANCE` | `NOT_PASS_YET` |

最后一次只读 NVS readback 为取得证据进入 RAM stub；不得把之前的成功应用启动状态当作当前仍在运行产品 app。

## 11. Remaining Work

1. 使用已通过 compatibility probe 的完整三组件离线 bundle，执行新的临时 current-product Control-A build。
2. 绑定产品 firmware SHA、size、partition compatibility、app0-only restore plan 和 readback oracle。
3. 取得新的独立物理授权后，才可恢复产品 app0；不得写 NVS、partition table 或执行 chip erase。
4. 产品启动验证、BSR-R2 Manager cutover、Setup Secret/credential activation、telemetry E2E 和 FC4 Final Acceptance 均为后续独立 Gate。
5. 若继续研究 prior ROM/stub handoff failure，只能先做 host/tool source RCA；当前不需要为完成 epoch3 durable 结论重放物理动作。

## 12. Audit Notes for ChatGPT

请独立重点审核：

1. 是否正确区分 helper source correctness、artifact readback、boot handoff、serial marker 和 durable NVS 五类证据；
2. `F350_EPOCH3_HELPER_RCA=RESOLVED_PASS` 是否没有越界暗示 BSR-R2 或 Final Acceptance 已 PASS；
3. whole-image mismatch 下以 generated source 证明 tuple 的边界是否表述准确；
4. helper/product offline bundle 的 manifest compatibility guard 是否足够 fail-closed；
5. KF-057 应保持 `OPEN` 还是可在流程意义上降为 `RESOLVED`；
6. public Git scope 是否只包含脱敏文档，且没有私有 evidence、原始身份或凭据；
7. PR exact-head CI 与 public-repository-safety check 是否真实绑定最终 commit。

合并前必须完成 ChatGPT independent audit。
