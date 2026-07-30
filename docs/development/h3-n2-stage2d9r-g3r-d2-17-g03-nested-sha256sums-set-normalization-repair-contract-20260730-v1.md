# D2-17 G03 嵌套 SHA256SUMS 集合归一化修复合同

- 决策：`D1-H3N2-STAGE2D9R-G3R-D2-17-G03-NESTED-SHA256SUMS-SET-NORMALIZATION-REPAIR-20260730-01`
- base：PR #221 exact HEAD `205963a0680e177476a50c6c38a9eb5d294cb804`
- 状态：公共、Draft、host-only、add-only

## 失败处置

G03 在授权创建前以 `PRIVATE_NESTED_SHA256SUMS_SET_INVALID` 失败并永久退役。授权创建、claim、consume 均为 false；所有板卡、USB、串口、esptool、Flash/NVS、Broker、PREPARE、VERIFY 和 recovery 标志均为 false。

G03 私有包、runtime、终端文件和后续衍生材料不得重放、修改、重打包或复用。

## 根因

控制器通过集合推导得到实际嵌套清单：

```python
nested = {...}
```

冻结期望值却使用 tuple：

```python
expected_nested = (...)
```

随后直接执行 `nested == expected_nested`。Python 的 `set` 与 `tuple` 即使包含完全相同的元素也不相等，因此真实的 7 项完整集合被错误拒绝。

## 修复规则

1. 实际路径和期望路径都规范化为 `set[str]`；
2. 先验证每个嵌套 `SHA256SUMS` 均被根清单覆盖；
3. 再验证规范化后的集合完全相等；
4. 缺少根清单覆盖继续返回 `PRIVATE_NESTED_SHA256SUMS_NOT_COVERED`；
5. 集合成员缺失或多余继续返回 `PRIVATE_NESTED_SHA256SUMS_SET_INVALID`；
6. 不允许通过排序、重复项或展示顺序掩盖成员变化。

## 安全边界

本修复不创建 G04 私有包或授权，不 claim/consume，不执行任何物理操作。下一门为：

`D1-H3N2-STAGE2D9R-G3R-D2-17-G04-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260730-01`
