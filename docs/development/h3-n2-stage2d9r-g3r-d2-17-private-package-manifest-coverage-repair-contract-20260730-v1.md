# H3/N2 Stage 2D-9R G3R D2-17 私有包根清单覆盖修复合同 V1

## 1. 状态与边界

- 公共修复决策：`D1-H3N2-STAGE2D9R-G3R-D2-17-PRIVATE-SHA256SUMS-COVERAGE-REPAIR-20260730-01`
- 常设授权：`STANDING-D1-PUBLIC-HOST-ONLY-SUCCESSOR-REPAIR-AUTHORIZATION-20260730-01`
- 基线：Draft PR #217 exact HEAD `97e712f94913ad05bcae7ce140758fef6bf61f34`
- 本合同仅允许公共、host-only、add-only 修复和 CI 验证。
- 本合同不授权创建 G02 私有包、目标 Mac 授权、目标 Mac static-check 或任何物理决策。

## 2. G01 正式失败处置

D2-17 G01 私有包永久进入：

`PRIVATE_PACKAGE_STATIC_CHECK_FAILED_RETIRED`

目标 Mac 入口在创建 runtime root 和授权之前返回：

`PRIVATE_SHA256SUMS_COVERAGE_MISMATCH`

当时：

- `authorization_created=false`
- `authorization_claimed=false`
- `authorization_consumed=false`
- `runtime_root_created=false`
- `terminal_file_created=false`
- 全部板卡、USB、串口、esptool、Flash/NVS、网络、Broker、PREPARE、VERIFY 和 recovery 标志为 `false`

G01 禁止重跑、修改、重打包或复用。

## 3. 根因

G01 根清单生成器使用了 basename 条件：

```python
p.name != "SHA256SUMS"
```

该条件错误地排除了任意层级中所有名为 `SHA256SUMS` 的文件，而不是只排除正在生成的根目录清单。G01 实际有 105 个应覆盖的普通文件，根清单只记录 103 个，漏掉：

- `public-review/SHA256SUMS`
- `public-review/d2-17-execution-identity-frozen-physical-d2-execution-package/SHA256SUMS`

这是私有交付构建器缺陷，不是目标 Mac 操作错误。

## 4. 冻结修复规则

根清单必须只排除精确路径：

```python
root / "SHA256SUMS"
```

任何嵌套层级中的同名文件都是普通 payload，必须被根清单覆盖和验签。

修复实现必须满足：

1. 先规范化并严格解析包根目录；
2. 拒绝根目录及任意后代中的 symlink；
3. 只排除精确的根 `SHA256SUMS` 文件；
4. 覆盖所有其他普通文件，包括嵌套 `SHA256SUMS`；
5. 比较期望路径集合和实际路径集合；
6. 路径集合不一致时保留 `PRIVATE_SHA256SUMS_COVERAGE_MISMATCH`；
7. 成员摘要错误时保留 `PRIVATE_MEMBER_DIGEST_MISMATCH:<relative-path>`；
8. 支持含空格路径及 macOS/POSIX 规范路径；
9. 不生成 Python bytecode；
10. 公共 CI 中至少使用两个嵌套 `SHA256SUMS` 进行真实写入、验证和篡改回归。

## 5. 后继私有包要求

后继包必须使用全新 generation、全新包名、全新私有交付 binding 和全新决策门。不得修补 G01 原目录或沿用其根清单。

后继私有构建器必须调用本 PR 中的公共 manifest-coverage 合同，或者逐字等价实现并通过相同测试。私有构建完成后必须：

- 分别解压 ZIP 与 TAR.GZ；
- 对两种格式执行完整根清单验证；
- 比较二者的规范文件树与摘要；
- 明确报告嵌套 `SHA256SUMS` 数量和路径；
- 在交付前再次确认 PR、SHA、CI 与 Artifact 未漂移。

完成公共 CI 和承重 Artifact 后，才可提出新的 G02 私有包与目标 Mac static-check 创建决策。
