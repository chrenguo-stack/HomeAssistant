# H3/N2 Stage 2D-9R G3R USB 身份证据修复合同 V1

## 1. 决策与范围

本层落实：

```text
D1-H3N2-STAGE2D9R-G3R-USB-IDENTITY-EVIDENCE-REPAIR-20260728-01
```

它是基于 Draft PR #196 精确 HEAD
`3b44bc48cdee79efcb77500c855362b1690d8877` 的源码后继层。仅允许源码、测试、
Draft PR、CI 和公开审查 Artifact。不得连接板卡、枚举或访问 USB、调用 esptool、
打开串口、读写或擦除 Flash/NVS、启动 Broker、执行 PREPARE/VERIFY，亦不得 Ready、
merge、release、tag 或 deployment。

## 2. B1 的永久终态

B1：

```text
B1-H3N2-STAGE2D9R-G3R-BASELINE-EVIDENCE-DIAGNOSTIC-READONLY-20260728-01
```

永久终态为：

```text
status=CONSUMED_FAILED
failure_code=BOARD_IDENTITY_MISMATCH
authorization_record_sha256=1e5a9236f33af37b97128c9247b34128d5c50fb928195467d3bf5a16a5eabb9a
diagnostic_result_sha256=27cab5ab00dd55a1cac8aa2c1284f8b1c90b553073179eb8fdfb4918f1360eae
```

B1 在 USB 候选枚举后、任何 esptool 命令之前失败。没有串口打开、Flash 写入或擦除、
网络、Broker、PREPARE、VERIFY 或未来物理请求创建。B1 不得重放。

## 3. 操作员补充事实

操作员明确报告：B1 连接同一块 ESP32-C6 测试板时，使用了与原基线不同的 USB 接口。
该事实与 `BOARD_IDENTITY_MISMATCH` 高度一致，因为旧 `board_binding` 把 USB `location`
纳入阻塞摘要。

该报告的证据角色为：

```text
EXPLANATORY_NOT_CRYPTOGRAPHIC_PROOF
```

它不能单独证明硬件未更换，但足以证明“USB 传输路径必须与稳定硬件身份分离”是必要修复。

## 4. 原身份模型缺陷

旧板卡身份包括：

```text
VID / PID / serial_number / manufacturer / product / location
```

旧串口身份还包括：

```text
device / location / hwid
```

其中 `device`、`location` 和 `hwid` 会随 Mac USB 口、扩展坞或枚举路径变化，不能继续作为
稳定硬件身份的阻塞字段。B1 又在保存实际观测摘要之前比较旧板卡摘要，导致失败证据没有
记录实际 USB 身份组成。

## 5. 身份证据策略 V2/V3

后继诊断必须先保存 hash-only 传输证据，再执行任何旧身份比较：

- 旧 `board_identity` 摘要；
- 旧 `serial_identity` 摘要；
- 路径中立 USB 身份摘要；
- `serial_number`、manufacturer、product 的独立摘要；
- device path、location、hwid 的独立摘要；
- VID/PID 数值；
- 明确标注传输路径仅为 audit-only。

新的路径中立基线还记录：

- `chip_id` 输出摘要；
- `flash_id` 输出摘要；
- 从 `chip_id` 文本中唯一提取的 MAC 的摘要（若恰好找到一个）；
- 测试分区摘要与长度；
- 旧整体基线是否匹配；
- 路径中立整体基线摘要。

不保存原始设备路径、USB location、hwid、MAC、esptool 原始输出或任何私密值。

## 6. 后继 B2 只读门

下一门仅为：

```text
B2-H3N2-STAGE2D9R-G3R-USB-IDENTITY-AND-BASELINE-DIAGNOSTIC-READONLY-20260728-01
```

它必须单独精确授权、一次性、限时。授权后仅允许：

```text
枚举唯一 ESP32 类 USB 候选
保存 hash-only 传输证据
esptool chip_id
esptool flash_id
read_flash 0x400000 0x10000
```

旧板卡/串口摘要不再是读取前阻塞门。诊断完成后只生成证据，不接受新稳定身份，不创建物理
请求。禁止串口监视器打开、Flash 写入或擦除、NVS 写入、Broker、网络、PREPARE、VERIFY、
ACTIVATE、CLEANUP。

预留物理请求仍为：

```text
D2-H3N2-STAGE2D9R-G3R-PAYLOAD-HANDOFF-REPAIRED-PHYSICAL-20260728-05
```

本层和 B2 都不得创建或授权它。

## 7. 后续接受门

只有在 B2 证据完成后，才能由新的决策门判断：

- 是否确认本次为同一物理板卡的 USB 路径变化；
- 是否采用路径中立硬件身份；
- 是否接受测试分区当前状态为新基线；
- 是否需要重新冻结执行闭包和生成请求 `-05`。

在该接受门之前，不得把操作员报告自动转换为硬件身份接受，也不得继续物理 D2。
