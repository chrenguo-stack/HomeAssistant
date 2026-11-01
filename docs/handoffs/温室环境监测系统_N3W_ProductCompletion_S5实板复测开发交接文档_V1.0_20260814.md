# 温室环境监测系统 N3-W Product Completion S5 实板复测开发交接文档

**版本：** V1.0
**日期：** 2026-08-14
**仓库：** `chrenguo-stack/HomeAssistant`
**交接范围：** S5 最小 S3/S4 实板集成、ESP-NOW 初始化崩溃修复、两块 ESP32-C6 隔离复测与后续边界

---

## 1. 本轮结论

本轮已完成 PR #322 中 ESP-NOW 初始化崩溃的定位、修复、CI 和两块绑定 ESP32-C6 的隔离实板复测。

当前阶段分类为：

```text
S5_DRIVER_INITIALIZATION_CRASH_FIX=PHYSICAL_VERIFIED
S5_FULL_TWO_BOARD_E2E=PENDING
PR322=OPEN_DRAFT_CLEAN
PRODUCTION_ACCESS=false
N3L_STARTED=false
```

这证明修复后的 Child 与 Relay 均能初始化 ESP-NOW 并稳定完成启动，不表示 Manager 授权、Relay advertisement、加密 peer、遥测转发或 Home Assistant 身份连续性的完整 S5 验收已经通过。

## 2. 精确 GitHub 与代码绑定

- 基线 `main`：`38c3b692d4ebe90d0040c732b6c0313fdfdc1ef6`。
- 开发分支：`feature/n3w-product-completion-s5-two-board-isolated-20260814-v1`。
- Draft PR：#322，标题为 `feat(n3w): add minimal S5 board integration`。
- 已完成实板复测的实现提交：`ae8dda51998c46bf9ac86dda4ca0219112c378aa`。
- PR 在交接归档前为 `OPEN / DRAFT / CLEAN`。

本交接归档提交只包含公共、脱敏的决策和交接材料；实板身份、PMK、原始串口记录及私有固件摘要不进入 GitHub。

## 3. 开发成果

PR #322 当前累计包含：

1. Child/Relay 共用的 ESPHome S5 最小集成入口，默认公共编译配置保持 inert。
2. S3 产品运行时与 S4 Manager eligibility/peer authorization 边界接线。
3. 运行期授权 peer 与 LMK 材料安装边界，不固化 peer MAC 或节点身份。
4. S2 历史门禁的 lineage-aware 修复。
5. ESP-NOW 初始化前的 Wi-Fi 驱动生命周期修复：初始化 netif/event loop/Wi-Fi、启用无连接 STA、启动 Wi-Fi 后再调用 `esp_now_init()`。
6. 对既有 Wi-Fi 驱动的共享与所有权跟踪，以及初始化失败时仅清理由本组件创建资源的回滚路径。
7. Child/Relay ESP32-C6 编译、host contract、S2/S3/S5 门禁和安全检查。

修复没有配置 SSID 或密码，没有调用 Wi-Fi 连接，也没有加入生产端点。

## 4. 失败定位与修复

第一次单次绑定尝试 `S5-PHYSICAL-20260814-01` 使用提交 `fd509538086479361ce931d9c073564606d53ae0`。

两种角色均在启动时稳定复现相同终止故障：

```text
classification=deterministic_runtime_crash_before_espnow_initialization
exception=Load access fault
symbol=esp_now_init
affected_roles=child,relay
```

根因是 ESP-NOW 初始化发生在 ESP-IDF Wi-Fi 驱动初始化和启动之前。修复提交 `ae8dda51998c46bf9ac86dda4ca0219112c378aa` 建立了正确的生命周期顺序，并补充失败回滚及合同门禁。

## 5. CI 结果

修复提交上的适用检查全部通过。关键公开运行包括：

- N3-W Product Completion S5 board integration CI：run `31786353110`。
- N3-W Product Completion S3 disconnected ESP-NOW runtime CI：run `31786353131`。
- N3-W Product Completion S2 host-only core CI：run `31786353137`。
- Public repository safety CI：run `31786353125`。
- greenhouse-manager CI：run `31786353175`。
- M2 private Mosquitto CI：run `31786353094`。

Child、Relay 两个 ESP32-C6 board compile 及 ESP32-C6 driver compile 均为 SUCCESS。按路径过滤跳过的无关 job 不构成失败。

## 6. 修复后的两板实测

第二次单次绑定尝试 `S5-PHYSICAL-20260814-02` 精确绑定修复提交 `ae8dda51998c46bf9ac86dda4ca0219112c378aa` 和原 Child/Relay 两块设备。

脱敏结果：

```text
BOARD_BINDINGS_VERIFIED=true
CHILD_ERASE_FLASH_VERIFY=PASS
RELAY_ERASE_FLASH_VERIFY=PASS
CHILD_ESPNOW_INIT=PASS
RELAY_ESPNOW_INIT=PASS
CHILD_SETUP=PASS
RELAY_SETUP=PASS
IMMEDIATE_LOAD_ACCESS_FAULT_REPRODUCED=false
POST_INIT_STABILITY_SECONDS=45
DELAYED_CRASH_OR_REBOOT_OBSERVED=false
```

测试结束后，两块设备均重新进入 ROM bootloader 并保持 no-reset，应用已停止，ESP-NOW RF 已关闭。

## 7. 尚未完成的 S5 范围

以下项目仍明确为 pending，不得由本轮结果推导为 PASS：

1. 隔离 Manager 授权测试适配器。
2. Relay advertisement 的真实广播与 Child 提示验证。
3. 两端 Manager grant 校验与相同非零 LMK 派生。
4. 自动安装加密 peer 并建立 Child↔Relay 链路。
5. Relay telemetry 到隔离 Manager 和 Home Assistant 的端到端转发。
6. 单一 NODE_ID、单一 HA Device 和 canonical sequence 连续性。
7. 授权到期、撤销、重放、重启及清理矩阵。

继续上述工作应先完成 Manager/advertisement 测试适配开发与 CI，再生成新的单次实板执行绑定。不得重放本轮临时包或授权。

## 8. 公共与私有证据边界

公共 GitHub 仅保存：

- 精确公开提交、PR 和 CI 状态；
- 脱敏的失败分类、修复说明和 PASS/PENDING 结论；
- 最终设备与安全边界。

以下内容不进入仓库：

- 板卡 MAC、USB 身份和端口绑定细节；
- PMK、LMK 或任何运行期授权材料；
- 私有固件摘要、执行包摘要和原始串口日志；
- 可重放的实板命令或授权材料。

## 9. 最终安全状态

```text
CHILD_STATE=ROM_BOOTLOADER_NO_RESET
RELAY_STATE=ROM_BOOTLOADER_NO_RESET
ESPNOW_RF_ACTIVE=false
WIFI_CREDENTIALS_USED=false
WIFI_CONNECTION_ATTEMPTED=false
PRODUCTION_T1_ACCESS=false
PRODUCTION_MANAGER_MUTATION=false
PRODUCTION_BROKER_MUTATION=false
PRODUCTION_HOME_ASSISTANT_MUTATION=false
```

两块板原有固件已在本轮授权测试中擦除并替换为修复版测试固件；该操作可通过后续重新烧录恢复或替换。

## 10. 下一位接手者的恢复顺序

1. 只读确认 PR #322 当前 head、Draft 状态及 CI；若 head 已前进，重新评估本交接绑定。
2. 保留第一次失败尝试，不得改写为成功或删除根因历史。
3. 以 `S5_DRIVER_INITIALIZATION_CRASH_FIX=PHYSICAL_VERIFIED` 恢复，而不是声明 `S5_FULL_TWO_BOARD_E2E=PASS`。
4. 在新分支或 PR #322 的明确后续范围内补齐 Manager/advertisement 隔离适配与自动链路测试。
5. 新的擦除、烧录、串口或 ESP-NOW RF 动作必须重新确认设备状态并建立新的单次执行绑定。
6. 在完整 S5 验收前，不得开始生产变更，也不得把本轮结果扩展为 N3-L 授权。

本交接文档是开发归档，不授权新的板卡、RF、生产网络、服务、合并、发布或部署动作。
