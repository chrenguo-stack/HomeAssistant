# KF-050 — N3-W boot-session 随机化违反单调持久化合同

状态：OPEN / repair successor in progress

## 现象

FC4 Final Physical Acceptance 的 F3:50 单板 Direct telemetry 观察中，两次串口观察均触发设备重新启动；新的 telemetry 序列重新从 `seq=1` 开始。第二次观察窗口内，Manager 对该节点的 Direct telemetry 全部拒绝，拒绝码全部为 `stale_boot_session`。

关键现场事实：

- R3-E2 窗口：`accepted_direct=0`；
- R3-E2 窗口：`rejected_direct=39`；
- R3-E2 窗口：`stale_boot_session=39`；
- `stale_sequence=0`、duplicate=0、canonical validation reject=0；
- registration / credential continuity PASS；Manager/Broker/HA 均 running、restart=0。

因此故障不是 MQTT、registration、credential、HA 或 Manager 生命周期异常，而是 boot-session replay 合同冲突。

## 根因

正式 `gh-n3w-single-hop-v1` 合同规定：

- `boot_id` 的 16 位十六进制部分是节点身份生命周期内持久化的非零 64-bit 单调 session counter；
- 节点必须先原子递增并持久化 counter，再使用新 session 发送第一帧；
- Manager 持久化最高 session，高于高水位才推进，低于高水位必须拒绝；
- counter 丢失、损坏或回退不确定时必须 fail closed。

但 FC4 `generic.yml` 曾使用每次 runtime 启动生成的 8-byte random 值作为 `boot_id`，并由 harness 自己持有本地 `static uint32_t seq`。随机 64-bit 值没有单调性，因此合法重启后的新随机值可能低于 Manager durable high-water，导致整个新 boot session 被 `stale_boot_session` 拒绝。

仓库实际上已经存在完整的 `BootSessionManager` 与 ESP32 `NvsBootSessionStore`，缺陷是 Simplified Product / Phase4 generic harness 没有接入该 durable primitive。

## 修复方向

Repair successor 采用最小收敛方案：

1. 不修改 Manager replay/high-water 安全语义；
2. 复用既有 `BootSessionManager` + `NvsBootSessionStore`；
3. `GreenhouseN3wCore` 取得 telemetry `boot_id + seq` ownership；
4. Phase4 generic harness 删除 random boot 和本地 static seq，仅向 product component 申请下一 telemetry identity；
5. sequence 在分配时即 burn，即使后续 transport 失败也不复用 tuple；
6. 只有本进程启动时不存在既有持久化 product identity 的 fresh identity candidate，才允许在缺失 boot counter 时建立初始 floor=0；
7. 已 provisioned identity 如果 durable counter 缺失、损坏或 I/O 失败，必须 fail closed，不得自动从 0 重建；
8. 保留既有 `gh_n3w/boot_state` namespace/key，避免为了命名整齐迁移 durable counter；
9. Manager replay relaxation 禁止作为该缺陷的修复手段。

## 当前兼容性边界

现有已 provisioned 设备若此前从未写入 `gh_n3w/boot_state`，升级到修复固件后会按设计 fail closed，而不是自动从 0 开始。该状态需要独立、受控的 recovery-floor 流程或重新建立身份/key epoch 后再恢复 telemetry；不得通过清除 Manager replay high-water 来伪造修复成功。

## Regression guards

至少保持：

- Phase4 source contract 明确禁止 `std::array<uint8_t, 8> random_boot`；
- Phase4 source contract 明确禁止 harness `static uint32_t seq` ownership；
- generic harness 必须调用 `take_telemetry_identity`；
- product component 必须绑定 `NvsBootSessionStore` 与 `BootSessionManager`；
- missing durable boot state + existing provisioned identity 必须 fail closed；
- fresh identity 才允许初始化 zero floor；
- Manager `stale_boot_session` / durable high-water 语义保持不变。

## FC4 执行约束

在该修复重新冻结 source、CI、构建制品并完成针对性 reboot regression 前：

- `R3_F_EXECUTED=false`；
- 不进入真实 Wi-Fi loss / Relay gate；
- 不把现有 F3:50 Direct telemetry 状态写成 PASS；
- 不重放已消费的 R3-C scoped NVS erase 或 R3-D authorization claim。
