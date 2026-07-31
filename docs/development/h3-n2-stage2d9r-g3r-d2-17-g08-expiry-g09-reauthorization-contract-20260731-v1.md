# H3/N2 Stage 2D-9R G3R D2-17：G08 超期未执行与 G09 后继授权合同

## 结论

G08 物理授权于 `2026-07-31T01:53:32.629244Z` 到期。操作员报告 G08 物理执行包未运行；现有证据状态为授权已创建、未 claim、未 consume，且没有创建 G08 物理 runtime。

G08 私有包、授权、static-check runtime 和物理执行包均冻结为历史材料。过期时间不能在旧 JSON 或旧 ZIP 中修改，旧包不能重新签名、重新打包或重放。

## 为什么不能直接重新生成 G08 ZIP

物理执行包绑定以下不可分割事实：

- G08 授权文件与授权语义记录；
- 固定到期时间；
- G08 static-check terminal；
- PR #232/#233 exact HEAD 与承重 Artifact；
- identity adapter、configured-validator 证据和 generation-local marker 设计。

替换到期时间会同时改变授权记录摘要、验收绑定、物理决策绑定和操作包根清单。继续称其为原 G08 将破坏一次性授权和不可变证据合同。

## G08 处置

G08 状态固定为 `EXPIRED_UNEXECUTED_RETIRED_NO_REPLAY`：

- 不删除、不修改 G08 私有 runtime；
- 不运行 G08 static-check；
- 不运行 G08 物理执行包；
- 不修改授权 JSON；
- 不复用 G08 generation-local marker 作为后继授权状态；
- 不触碰已保留的 G07 consumed marker。

## G09 后继方案

下一代必须为全新的 G09：

1. 基于 PR #233 exact HEAD 的公共后继链构建新的私有包；
2. 继承已验证的 shell handoff、identity adapter、configured `core.validate_authorization` 和 generation-local marker 修复；
3. 不复制 G08 授权、runtime、terminal 或物理 marker；
4. 在目标 Mac 上创建新的 G09 runtime、execution identity 与一次性授权；
5. 重新执行 host-only static-check 和真实 configured validator；
6. 停在 claim 前，等待新的 G09 物理授权门。

## 当前边界

本公共处置不创建 G09 私有包或授权，不访问板卡、USB、串口、esptool、Flash/NVS、网络或 Broker，也不执行 PREPARE、VERIFY、recovery、ACTIVATE 或 CLEANUP。

下一显式决策门：

`D1-H3N2-STAGE2D9R-G3R-D2-17-G09-PRIVATE-PACKAGE-AND-TARGET-MAC-STATIC-CHECK-AUTHORIZATION-CREATION-20260731-01`

Ready、merge、release、tag 和 deployment 继续禁止。
