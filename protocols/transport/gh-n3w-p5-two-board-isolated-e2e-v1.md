# N3-W P5 两板隔离 E2E 合同 v1

状态：Preparation-only contract；未授权任何实板、空口或生产执行。

## 1. 目标与边界

P5 只验证 N3-W Wi-Fi 产品线的单跳补盲闭环：

```text
ESP32-C6 Child
  ├─ Wi-Fi Direct ───────────────────────────────┐
  └─ ESP-NOW ─> ESP32-C6 Relay ─> isolated MQTT ├─> Manager ─> isolated HA
                                                  ┘
```

禁止 Mesh、禁止多跳、禁止 Child 转发其他节点。路径切换不能改变 NODE_ID；Relay 只拥有独立 GATEWAY_ID。Manager 是唯一 canonical publisher，Relay 不发布 Home Assistant Discovery。

P5 使用新建的隔离 lab 资产，不修改 `firmware/esphome_rc/f1_0_rc2` 产品固件，也不接触生产 T1、Broker、HA 或 Manager 数据。

## 2. 两块板角色

### Board A — Child

- 硬件/工具链：ESP32-C6、`esp32-c6-devkitm-1`、8MB、ESP-IDF、ESPHome 2026.4.3，与已接受 N2 实板工具链血缘一致。
- 一个稳定 NODE_ID，Direct 与 Relay 路径复用该 NODE_ID。
- P4a 持久 boot-session + 单调 seq；相同 key epoch 下不得复用 `(boot_session, seq)`。
- 持有 Child↔Manager application key；Relay 不持有该 key。
- Wi-Fi Direct 时只写 `gh/v1/<system_id>/ingress/node/<node_id>/telemetry`。
- Relay 时先生成同一 `gh.telemetry/1` 明文，再由 P4a AES-256-GCM 封装并经 P4b 分片发送。
- 本地 P5 控制只用于隔离测试：PATH DIRECT/RELAY、KEY 1/2、RESEND、REORDER、RESTART。它不是产品控制面。

### Board B — Relay

- 同一 ESP32-C6 工具链血缘。
- 独立 `gateway_id` 与物理 MAC 绑定。
- 只接受已私有绑定 Child MAC 的加密 ESP-NOW peer。
- 只能重组并转发 Child 已加密的 `gh.relay/1`；不得获得 application key 或解密 Child telemetry。
- 转发主题固定为 `gh/v1/<system_id>/ingress/gateway/<gateway_id>/<node_id>/frame`，QoS 1、retain=false。
- 仅当本地 MQTT forward sink 接收成功后，才允许发送 `ACCEPTED_FOR_FORWARDING` ReceiptAck；该 ACK 不是 Manager canonical-acceptance ACK。

## 3. 无线与频道

- ESP-NOW 仅单跳加密 unicast。
- PMK 16 bytes；Child↔Relay LMK 16 bytes；真实值只存在于未来 private physical package。
- P5 两板与隔离 AP 使用同一 2.4 GHz Wi-Fi channel；物理执行前必须读取/冻结实际 channel。
- Broadcast discovery 仍是 untrusted hint；不得通过 discovery 自动改变 `gateway_id ↔ Relay MAC` 私有绑定。
- authenticated Probe/ProbeAck 成功后 Child 才能进入 Relay-active。
- datagram `<=240` bytes，ciphertext fragment payload 180 bytes，1024-byte application ciphertext 最多 6 片。

## 4. application-key 生命周期

P5 私有包必须创建两个仅用于 P5 的 32-byte application key：epoch 1 与 epoch 2。

- 初始：Manager epoch 1 ACTIVE；epoch 2 STAGED；Child 选择 epoch 1。
- 轮换：Manager 将 epoch 2 ACTIVATED、epoch 1 进入 GRACE 后，Child 切换 epoch 2；两阶段均验证 canonical 连续性。
- 撤销：测试完成后两 epoch 均必须进入 REVOKED/被销毁。
- P5 key 永不得复制到 P6/生产；public evidence 只记录 SHA-256 fingerprint、epoch 和生命周期状态，不记录 key bytes。

## 5. 隔离 Manager / Broker / HA

P5 使用 `infra/compose/n3w-p5-two-board-isolated`，与生产卷、网络、system_id、凭据完全分离。

- synthetic system_id：`n3wp5lab`（private package 可保持该值，不得改成生产 system_id）。
- Manager 仅在该隔离 compose 中设置 `GH_N3W_RUNTIME_ENABLED=true`。
- registration DB 仅含一个 ACTIVE Child NODE_ID。
- replay/path lease DB 为专用新建数据库。
- relay authorization DB/key dir 仅包含 P5 gateway grant 与 P5 key epochs。
- HA Discovery 在隔离 HA 中开启，验证同 NODE_ID 在 Direct/Relay 切换前后只形成同一 device/entity 集。
- Broker 必须使用 P5 独立用户名/密码；不得复用生产凭据。

## 6. 必测矩阵

物理执行授权只有在以下矩阵已经冻结到 exact execution package 后才可创建：

1. Direct steady state。
2. Direct→Relay，稳定窗口后切换；old-path grace 有界。
3. Relay→Direct，稳定窗口后切换。
4. 同 NODE_ID / 同 HA Device；Discovery 不重复。
5. 同 tuple duplicate、跨路径 duplicate、fragment reorder、late old frame；canonical 不回滚。
6. Child restart：boot-session 前进，seq 从新 session 重新开始且无 nonce reuse。
7. Relay restart：重新 Probe/peer/reassembly，canonical 连续。
8. Manager restart：replay/high-water + path lease 持久恢复。
9. gateway grant revoke：Relay ingress fail closed，旧 Relay lease 失效；re-grant 后重新走稳定确认。
10. application key epoch 1→2 rotation；旧 epoch grace/revoke 行为符合授权状态。
11. Broker outage：Relay 不发送假阳性 ReceiptAck；Child bounded cache/retry；恢复后不重复 canonical。
12. 清理：停止隔离栈、销毁 P5 credentials/key files/DB/HA volume/evidence temporary plaintext，保留 secret-free evidence。

任一物理尝试一旦开始即为单次 terminal attempt。失败不得在相同 physical authorization 下自动重试或重放。

## 7. Evidence 合同

Evidence 必须绑定：exact main/base、execution-package digest、Child/Relay firmware ELF/bin/map digest、两板实际 MAC、角色绑定、toolchain fingerprint、P5 secret fingerprints、AP channel、container image digests、DB before/after hashes、sanitized MQTT trace、sanitized serial logs、restart counts、lease/replay snapshots、HA registry before/after、matrix verdicts 和 cleanup proof。

Evidence 中禁止包含 Wi-Fi PSK、MQTT password、PMK、LMK、application key bytes、生产地址/凭据或其他 secret material。

## 8. 当前 preparation gate 明确不允许

当前门不得连接或枚举板卡，不得打开串口，不得 Flash/erase/OTA，不得发 ESP-NOW 空口帧，不得生成/使用真实 P5 key，不得启动 board-facing live isolated stack，不得访问生产资源，不得 Ready/merge/deploy/release/tag/N3-L。

下一物理门仅作为未来候选：

`D1-N3W-P5-TWO-BOARD-ISOLATED-E2E-PHYSICAL-EXECUTION-20260807-01`

其当前状态为 `NOT_APPROVED_NOT_CREATED_AS_CONSUMABLE_AUTHORIZATION`。
