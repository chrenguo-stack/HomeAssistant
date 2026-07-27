# H3/N2 Stage 2D-9R G3R successor：只读板卡基线采集门合同 V1

## 1. 决策依据

决策 `D1-H3N2-STAGE2D9R-G3R-BASELINE-READONLY-GATE-20260727-01`
批准仓库侧开发、测试和公开 Artifact 冻结。独立物理门
`D2-H3N2-STAGE2D9R-G3R-BASELINE-READONLY-20260727-01`
已经获得一次性授权并以 `CONSUMED_PASS` 结束；该授权已经消费，不得重放或自动重试。

## 2. 需要解决的两个缺口

### 2.1 consumed marker 持久证据

U1-02 的原始 authorization/result 文件已退休，但 mode-0600 consumed marker
仍同时绑定公开冻结的 authorization-record SHA-256 和 result SHA-256。新的验证器：

- 优先接受原始文件与 marker 的三方一致性验证；
- 当两份原始文件均不存在时，允许 marker-only 验证；
- 不允许只提供其中一份原始文件；
- 不重建、不伪造、不重放原始 authorization 或 result；
- marker 必须为 `CONSUMED` 或 `CONSUMED_PASS`；
- marker 必须 `one_shot=true`、`replay_permitted=false`、
  `automatic_retry_permitted=false`；
- 验证前后 marker 的原始字节摘要必须不变。

### 2.2 板卡身份与基线摘要

最终 D2 必须在授权前绑定：

- `board_identity_sha256`；
- `serial_identity_sha256`；
- `baseline_state_sha256`。

现有私密主机原先没有可复用的冻结基线，因此新增独立物理门：

`D2-H3N2-STAGE2D9R-G3R-BASELINE-READONLY-20260727-01`

该物理门已经完成并消费，其公开接受记录只保存摘要和保护边界，不包含原始串口路径、
芯片输出、Flash 输出或分区内容。

## 3. 物理门允许的唯一操作

获得单独、当前有效、最长 7200 秒的一次性授权后，执行器只允许：

1. 枚举并选择恰好一个 Espressif USB 串口候选；
2. `esptool chip_id`；
3. `esptool flash_id`；
4. `esptool read_flash 0x400000 0x10000`。

输出只包含摘要，不包含原始串口路径、芯片输出、Flash 输出或分区内容。

## 4. 明确禁止

无论成功或失败，均禁止：

- 第二个串口候选或第二次执行；
- 自动重试或授权重放；
- `erase_flash`、`write_flash`、`verify_flash`；
- 打开或写入物理 NVS；
- Wi-Fi、MQTT、Broker；
- `GH2D9R_PREPARE_V1`、`GH2D9R_VERIFY_V1`；
- ACTIVATE、CLEANUP；
- eFuse、Secure Boot、Flash Encryption；
- M401A、T1、Home Assistant、Mosquitto、greenhouse-manager；
- Ready、merge、release、tag、deployment。

候选数量不为 1 或声明后的任一失败均消费该次授权并失败关闭，不得自动重试。

## 5. 授权前边界

执行器必须先完成以下检查，且在 atomic claim 之前不得枚举 USB：

- authorization 文件为普通 mode-0600 文件；
- authorization 自摘要正确；
- 当前时间位于授权窗口内；
- package、脚本、Python 和 esptool 摘要精确匹配；
- operation set 精确匹配；
- consumed/claimed marker 不存在。

完成 atomic claim 后才允许进入 USB/串口只读阶段。

## 6. Review Artifact

Review Artifact 只包含：

- D1 决策记录；
- 本合同；
- marker-only 验证器；
- 只读基线执行器源代码；
- D2 V3 只读预检适配器；
- 单元测试；
- 非授权完整性探针。

Artifact 不得包含 authorization record、物理执行 launcher、私密路径、秘密值或
板卡原始身份。Artifact 中所有物理和生产授权字段必须为 `false`。

## 7. D2 V3 接入

只读基线执行成功后，V3 D2 preflight：

- 使用 consumed marker 验证 U1-02，不重建原始文件；
- 校验只读基线结果为 mode-0600、`CONSUMED_PASS`、不可重放；
- 从结果中取得三个精确摘要；
- 继续执行冻结的 V2 repository、Artifact、recovery、execution 检查；
- 生成 `authorized=false` 的精确 D2 请求草案；
- V3 preflight 自身不访问板卡、串口、Flash、NVS、网络或 Broker。

## 8. 已消费基线结果

公开接受记录：

`docs/acceptance/h3-n2-stage2d9r-baseline-readonly-d2-acceptance-20260727-v1.json`

冻结摘要：

- authorization record：`9c0dcab46d772f8506ef24039e2ccbaeb6cdeccf53cac011486ae0270f6e2842`；
- result：`83de8568ddfe73fc98c1408c1347a9817b03c4a9adb4ef091990d9b3b39ceab9`；
- board identity：`2607b7df80b8b636548a8d9d97c0a6b4e4ead57e9a2cc6fcb7f93643617242f8`；
- serial identity：`b6dba7ee0db02feba166935ae8ec2bbd946dbf66926e5421cfa1c1c8b8a4f2c3`；
- baseline state：`15ad524c4328fd93c99a10e1e0955080e5dedeb8df371832c4d437538dc8944a`；
- test partition：`a8438e656e6b3327506a988136884113c8df8ed012373b851ea2c6da681e8b7b`，65536 字节。

结果状态为 `CONSUMED_PASS`，且所有擦除、写入、NVS、网络、Broker、PREPARE、
VERIFY、ACTIVATE 和 CLEANUP 字段均为 `false`。测试板不得因该授权再次连接或重跑。
