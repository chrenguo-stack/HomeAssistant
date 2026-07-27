# H3/N2 Stage 2D-9R G3R successor D2 合同与只读预检

- 文档版本：V1
- 日期：2026-07-27
- 仓库：`chrenguo-stack/HomeAssistant`
- 目标：为新的独立精确 D2 建立公开合同、状态机、failure matrix、审核 Artifact 和只读预检
- 当前授权：`D2_AUTHORIZED=false`
- 当前物理执行：`PHYSICAL_EXECUTION_AUTHORIZED=false`

## 1. U1 公开闭环

本提交公开记录两项不可重放结论：

- `U1-H3N2-STAGE2D9R-SUCCESSOR-PRIVATE-CONTENT-BINDING-20260727-01`
  为 `INVALIDATED_BEFORE_CLAIM`，已确认未声明、未消费且未创建 marker；
  是否曾生成独立授权记录不在现有公开证据中作无依据断言；
- `U1-H3N2-STAGE2D9R-SUCCESSOR-PRIVATE-CONTENT-BINDING-20260727-02`
  为 `CONSUMED_PASS`，授权记录摘要为
  `88314a56bc5d7dd3e175278e2b01409cde611562f1bea11690adb9ff3f71f348`，
  结果摘要为
  `9ad24d630640ab485e055e7cb8f08c1320f19b6ca37d43e36303ce44d62d0b08`。

公开记录不包含 consumed marker 的实时 SHA-256。该摘要必须由未来的只读
preflight 在私密主机上重新计算并冻结，不能从历史材料猜测或沿用。

## 2. D2 状态机

正常路径：

```text
D2_REVIEWED
→ D2_AUTHORIZED
→ AUTHORIZATION_CLAIMED
→ BOARD_BOUND
→ BASELINE_VERIFIED
→ FLASH_ERASED
→ FLASH_WRITTEN_AND_VERIFIED
→ AUTO_RESET_COMPLETED
→ PREPARE_EXECUTED_ONCE
→ AUTO_RESTART_OBSERVED
→ VERIFY_EXECUTED_ONCE
→ PREPARED_VERIFIED
→ CONSUMED_PASS
```

声明前漂移：

```text
D2_REVIEWED / D2_AUTHORIZED
→ INVALIDATED_BEFORE_CLAIM
```

声明后失败：

```text
任一已声明状态
→ CONSUMED_FAILED
```

破坏性边界后的特定失败可进入最多一次 `LOCKED_RECOVERY_ENTERED`。recovery
完成后仍以 `CONSUMED_FAILED` 终止，不会返回普通执行路径，也不会变成重试。

## 3. 精确允许范围

新的 D2 最多允许：

1. 再次核验冻结的公开与私密元数据；
2. 声明一次精确 D2；
3. 绑定一块目标测试板和一个串口候选；
4. 只读板卡基线；
5. 擦除一次；
6. 写入冻结 immutable firmware 一次；
7. Flash 校验一次；
8. 自动 hard reset；
9. `GH2D9R_PREPARE_V1` 一次；
10. 观察固件自动重启；
11. 只读 `GH2D9R_VERIFY_V1` 一次；
12. 写入 D2 consumed marker 一次；
13. 满足条件时最多一次 locked recovery。

Stage 2D-9R 不允许 `ACTIVATE` 或 `CLEANUP`。

## 4. failure matrix 原则

- main、PR、CI、Artifact、U1 marker、custody 或工具链在声明前漂移：
  `INVALIDATED_BEFORE_CLAIM`，不消费；
- 声明后板卡/串口不唯一或基线不允许：`CONSUMED_FAILED`，不得 recovery；
- 擦除后 Flash、启动、PREPARE、重启、VERIFY 或 TLS/PREPARED 绑定失败：
  `CONSUMED_FAILED`，仅在精确授权包含且前置条件满足时允许一次 locked recovery；
- 重放、第二次 PREPARE、第二次 VERIFY、自动重试或禁止操作：
  直接 `CONSUMED_FAILED`，不得 recovery。

机器可读完整矩阵由
`tools/h3_n2_stage2d9r_successor_d2_contract_20260727_v1.py` 冻结。

## 5. 授权前只读 preflight

授权前仍禁止连接测试板和访问串口。因此 preflight 分为：

- **公开 GitHub 侧**：复核 main、PR #180、PR #176、当前 HEAD CI、review
  Artifact、public preflight Artifact 和 immutable Artifact；
- **私密主机侧元数据**：复用已审核的 host/custody probe，只读取 descriptor、
  public descriptor、U1 marker/record/result 元数据和文件属性，不读取秘密材料；
- **目标身份**：使用此前已经冻结在私密证据中的 board/serial 身份摘要，不进行
  实时 USB 枚举或串口访问；
- **授权后首步**：声明 D2 后才允许实际枚举唯一板卡和唯一串口，并将观察结果与
  授权中的身份摘要比对。

只读 preflight 输出只包含 SHA-256、布尔状态、公开错误码和脱敏身份摘要。

## 6. 精确授权请求的生成条件

`h3_n2_stage2d9r_successor_d2_readonly_preflight_20260727_v1.py` 只有在下列
值全部存在且匹配时才生成 `authorized=false` 的精确请求对象：

- 新 HEAD、main、PR #176 frozen HEAD；
- 全部当前 HEAD CI 成功；
- review Artifact ID/digest/source/expiry；
- public preflight Artifact ID/digest/source/expiry；
- immutable Artifact 及其冻结摘要；
- U1-02 record/result/实时 consumed marker SHA-256；
- custody root、descriptor、package、candidate、PKI 和命令摘要；
- Python/OpenSSL 工具链；
- 既有私密 board/serial 身份摘要和基线状态摘要；
- 已审核 execution package、execution script、launcher 和 execution marker 名称摘要；
- locked recovery package 摘要；
- 不超过两小时的 issued/expires 时间。

生成的对象仍不是授权记录，`authorized=false`。只有用户明确接受完全相同的
精确请求后，才可进入独立授权签发和物理执行。

## 7. 持续禁止

在新的精确 D2 获得授权前，禁止测试板、串口、Flash、物理 NVS、Broker、
PREPARE、VERIFY、ACTIVATE、CLEANUP、生产服务、M401A、T1、Home Assistant、
greenhouse-manager、eFuse、Secure Boot、Flash Encryption、Ready、merge、
release、tag 和 deployment。PR #180 与 PR #176 必须保持 Draft。
