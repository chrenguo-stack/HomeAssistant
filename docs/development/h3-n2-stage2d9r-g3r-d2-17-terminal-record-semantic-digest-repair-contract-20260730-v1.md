# D2-17 G02 终端记录摘要语义修复合同

## 失败处置

G02 物理执行入口在 inherited claim 前以 `TERMINAL_FILE_DIGEST_DRIFT` 阻断。授权未 claim、未 consume，板卡、USB、串口、esptool、Flash/NVS、Broker、PREPARE、VERIFY 与 recovery 均未执行。

该物理尝试和对应 G02 私有材料永久退役，不得重放、修改、重打包或复用。

## 根因

`terminal_record_sha256` 由终端 JSON 去掉自身摘要字段后，按排序键和紧凑分隔符规范化计算。它描述的是**记录语义**，不是 pretty-printed JSON 文件的原始字节。

G02 物理驱动错误地执行了：

```text
sha256_file(terminal.json) == terminal_record_sha256
```

同一 JSON 记录采用缩进、紧凑格式或不同键展示顺序时，文件摘要不同但语义完全相同，因此该比较必然产生假漂移。

## 冻结修复

后继链必须：

1. 解析 JSON，拒绝 symlink、非对象或非法 UTF-8/JSON；
2. 将嵌入的 `terminal_record_sha256` 与冻结预期值比较；
3. 删除该摘要字段后，对其余对象计算 canonical SHA-256；
4. 将 canonical 结果与冻结预期值比较；
5. 逐项验证状态、授权、物理门和绑定字段；
6. 不把空格、缩进、末尾换行或键展示顺序作为执行身份的一部分。

语义篡改必须保留叶子错误：

- `TERMINAL_RECORD_DIGEST_BINDING_DRIFT`
- `TERMINAL_RECORD_DIGEST_DRIFT`
- `TERMINAL_FIELD_DRIFT:<field>`

## 安全边界

本修复仅为公共 host-only 代码、回归测试和失败处置。它不创建 G03 私有包或授权，不允许 claim/consume，不允许任何物理操作，也不允许 Ready、merge、release、tag 或 deployment。
