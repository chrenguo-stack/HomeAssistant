# 温室环境监测系统 N3-W Product Completion S5 完整双板隔离物理 E2E 准备合同

**版本：** V1.0  
**日期：** 2026-08-14  
**仓库：** `chrenguo-stack/HomeAssistant`  
**PR：** #322  
**准备授权：** `D1-N3W-PRODUCT-COMPLETION-SUCCESSOR-S5-FULL-TWO-BOARD-ISOLATED-PHYSICAL-E2E-PREPARATION-20260814-01`

## 1. 本文档的权限边界

本文档和配套工具只完成完整 S5 双板隔离物理 E2E 的**准备与绑定**。它们不授权、也不执行擦除、烧录、串口、USB/JTAG 板卡访问、ESP-NOW RF、Wi-Fi 连接、真实 MQTT 网络 E2E、T1/生产服务访问、PR 合并、发布、部署或 N3-L。

完整实板执行必须在私有包物化、只读绑定复核通过后获得新的、单独的一次性 physical execution authorization。

当前分类保持：

```text
S5_DRIVER_INITIALIZATION_CRASH_FIX=PHYSICAL_VERIFIED
S5_AB_HOST_COMPILE=PASS
S5_C_HOST_COMPILE=PASS
S5_D_LIFECYCLE_NEGATIVE_HOST_MATRIX=PASS
S5_FULL_TWO_BOARD_E2E=PENDING
```

## 2. 冻结源绑定

- `main`: `38c3b692d4ebe90d0040c732b6c0313fdfdc1ef6`
- S5-D runtime implementation: `660acf72b701d9ff8e3a881e97e5d15357286786`
- S5-D archive / 本准备阶段起点: `eb2fdc795850fedd4f49ce3fbba8cd03a4548de9`
- branch: `feature/n3w-product-completion-s5-two-board-isolated-20260814-v1`
- PR #322 必须保持 Draft / Open / Unmerged。

本准备阶段只允许新增/更新准备合同、私有包生成器、host-only 准备测试和对应 CI；另外只允许对既有 S5-D CI 的 successor-lineage scope gate 做兼容性修复，以便在**冻结 S5-D implementation checkpoint 不变**的前提下重新执行原 S5-D regression matrix。该兼容性修复不得修改 S5-D runtime、Manager 产品实现或扩大物理权限。若 runtime/Manager 产品实现发生任何额外变化，现有准备绑定失效，必须重新评估。

## 3. 私有包物化输入

物化发生在操作者本地私有目录，不在 GitHub Actions、公开仓库或生产 T1 上进行。需要：

- Child 自身注册后凭据：`system_id`、`node_id`、`credential_generation`、`key_epoch`、`application_key_hex`、本机 `local_mac`；
- Relay 自身注册后凭据：相同字段；
- 精确绑定 runtime implementation 构建出的 Child 固件；
- 精确绑定 runtime implementation 构建出的 Relay 固件；
- 隔离 Manager 状态 bundle；
- 新鲜 ESP-NOW PMK：由私有包生成器本地创建，每个 package 唯一，禁止复用旧尝试材料。

任何公开/出厂材料都不得包含 peer MAC、peer NODE_ID、固定 gateway_id、pair LMK 或固定 peer relationship。

所有私有输入文件必须为仅所有者可读写的权限；生成目录为 `0700`，生成文件为 `0600`。

## 4. 私有包生成器

公开工具：

`tools/n3w_product_s5_prepare_physical_package.py`

工具只做：输入合法性校验、文件 SHA-256 绑定、新鲜 PMK 生成、私有 manifest/cleanup contract/read-only gate 写入。工具没有进程启动、网络、串口或板卡访问能力，也不输出物理执行命令。

本地物化时，操作者必须显式提供本准备阶段最终公开 preparation HEAD。例如：

```text
python3 tools/n3w_product_s5_prepare_physical_package.py \
  --preparation-head <EXACT_PREPARATION_HEAD> \
  --child-credentials <PRIVATE_CHILD_SELF_CREDENTIAL_JSON> \
  --relay-credentials <PRIVATE_RELAY_SELF_CREDENTIAL_JSON> \
  --child-firmware <PRIVATE_CHILD_FIRMWARE_BIN> \
  --relay-firmware <PRIVATE_RELAY_FIRMWARE_BIN> \
  --manager-bundle <PRIVATE_ISOLATED_MANAGER_STATE_BUNDLE> \
  --output <NEW_PRIVATE_PACKAGE_DIRECTORY>
```

这条命令是 host-only 私有包准备动作，不是实板执行。输出中的 `execution_authorized` 必须仍为 `false`，`physical_execution_authorization` 必须仍为空。

私有 PMK、应用密钥、MAC、固件内容、Manager 状态、原始串口日志均不得粘贴到 GitHub 或公开交接文档。后续只读复核只需要 package id 和脱敏 SHA-256 绑定。

## 5. 后续 physical execution 的冻结顺序

下一阶段授权后，实板测试必须按单次执行状态机推进；任一终止失败不得在同一 package 上“修好后继续”。逻辑顺序冻结为：

1. **Preflight**：精确 source/package/firmware/Manager bundle/两板身份绑定；确认隔离环境、无生产路由、私有权限、两板初始状态。
2. **Material activation**：仅在 physical authorization 被明确写入本次 package 后才允许进入实板动作。
3. **Child/Relay bring-up**：分别验证固件哈希、启动、ESP-NOW 初始化，无复现崩溃/重启。
4. **Relay advertisement**：Relay 仅在 Direct 可用且 Manager eligibility 满足时广播；Child 只能把 advertisement 当作 untrusted hint。
5. **Pair authorization**：Child/Relay provisional handshake 后由 S4 Manager authority 验证注册、system、credential generation、key epoch、health、freshness 和 replay。
6. **Grant/LMK**：两端各自验证自己的 grant；两端独立派生相同、非零、pair-specific 16-byte LMK；Manager 不产生也不分发 LMK。
7. **Encrypted peer**：自动安装动态加密 peer，不允许静态 peer 身份或工厂绑定参与。
8. **Reliable telemetry**：Child 使用既有 `gh.relay/1` / `RelayFrame` / `DATA_FRAGMENT` / authenticated `RECEIPT_ACK`，Relay 送入隔离 Manager 的既有 unified ingress；不引入第二 telemetry schema。
9. **Identity continuity**：验证原 NODE_ID、boot_id、seq、dedup key、canonical telemetry 和 Home Assistant device/topic 连续。
10. **Lifecycle matrix**：finite expiry、精确 authorization_id revoke、duplicate/replay/stale/credential mismatch、Child restart、Relay restart。
11. **Retry-cache binding**：Relay-1 绑定的旧 `gh.relay/1` frame 不得被 Relay-2 继承或重放。
12. **Cleanup**：冻结脱敏证据后，删除 private credentials copy、PMK/LMK material、Manager state copy、private firmware package、raw serial evidence；两板回 ROM bootloader/no-reset，ESP-NOW RF stopped。

## 6. 必须 PASS 的完整验收矩阵

完整 S5 只有在同一个有效的一次性执行包中形成足够证据，才可从 `PENDING` 升级：

- Relay advertisement 真实可见且仅作 untrusted hint；
- Manager 对 unregistered / cross-system / stale / replay fail closed；
- Child grant 与 Relay grant 分别通过端点验证；
- 两端 LMK 相同、非零、16 byte、pair-specific；
- 动态 encrypted peer 自动建立；
- Child telemetry 经 Relay 到隔离 Manager；
- `gh.relay/1` / `gh.telemetry/1` / ReceiptAck / replay/path lease/canonical sequence 语义保持；
- 单一 NODE_ID / 单一 HA Device / boot+sequence+dedup 连续；
- expiry 和 exact revoke 均移除动态 peer；
- duplicate/replay/stale/credential mismatch 均 fail closed；
- Child/Relay restart 均清除 transient peer/key state 并能重新走授权恢复；
- retry cache 不跨 Relay 身份 re-home；
- 私有证据清理完成；
- 最终两板 ROM bootloader/no-reset、RF stopped；
- 全程无生产 T1/Manager/Broker/HA 访问或修改。

## 7. 终止条件

出现以下任一项立即终止本次 package，不得在同 package 上继续：source/firmware digest 漂移、板卡绑定漂移、私有权限不合规、意外 Wi-Fi/生产路由使用、板卡异常 crash/reset、Manager authority time 不可用、grant/identity 绑定不一致、peer/LMK 在应清理边界后残留、或发现使用了旧 package/secret。

终止后只允许完成安全 cleanup 和脱敏失败归档。任何代码修复、重新构建、重新生成密钥或再次物理尝试都需要新 package 和新 physical authorization。

## 8. 公共证据允许范围

GitHub 可以保存：精确公开 SHA、CI run、脱敏 PASS/FAIL 分类、package id、私有文件 SHA-256、最终 board/RF/production 边界。

GitHub 不保存：MAC 明文、USB/端口绑定、application key、PMK、LMK、完整 Manager state、private firmware、原始 serial log、可重放的实板命令或 physical authorization material。

## 9. 下一决策门

公共准备 CI 通过后，仍必须先在本地物化新的 private package，并把生成器 stdout 中的脱敏 JSON 返回用于**只读绑定复核**。只有该复核通过，才生成下一枚一次性 physical execution authorization。
