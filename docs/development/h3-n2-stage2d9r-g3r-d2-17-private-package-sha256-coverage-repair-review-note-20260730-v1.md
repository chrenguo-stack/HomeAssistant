# D2-17 私有包 SHA256SUMS 覆盖修复审阅说明

本说明用于将 G01 的 `PRIVATE_SHA256SUMS_COVERAGE_MISMATCH` 固化为公共可回归规则。

- G01 已永久退役，禁止重跑、修改、重打包或复用。
- 修复仅排除精确根路径 `root / "SHA256SUMS"`。
- 任意嵌套 `SHA256SUMS` 均作为普通 payload 纳入根清单。
- 公共 CI 必须验证含空格路径、两个嵌套清单、摘要篡改叶子错误和无 symlink/bytecode。
- 本 PR 不创建 G02 私有包，不创建目标 Mac 授权，也不创建物理决策。
