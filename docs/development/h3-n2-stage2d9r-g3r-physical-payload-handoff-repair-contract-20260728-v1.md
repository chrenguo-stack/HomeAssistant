# H3/N2 Stage 2D-9R G3R 物理 Payload Handoff 修复合同

- 决策：`D1-H3N2-STAGE2D9R-G3R-PHYSICAL-PAYLOAD-HANDOFF-REPAIR-20260728-01`
- 精确基线：Draft PR #189 HEAD `45c80baf43ccc3f917ae5964ee92a202a74cc2ba`
- 旧物理 D2：`D2-H3N2-STAGE2D9R-G3R-REPAIRED-PHYSICAL-20260728-01`
- 旧终态：`CONSUMED_FAILED / IMMUTABLE_PAYLOAD_INVALID / NO_REPLAY`

## 唯一修复范围

Shell launcher 不再预先解压后把“解压目录”冒充“原始 TAR 所在目录”。新合同将四个角色分开传递：

1. 原始 immutable TAR；
2. 全新、空的 immutable 解压目录；
3. 原始 recovery TAR；
4. 全新、空的 recovery 解压目录。

Python wrapper 必须先校验原始 TAR SHA-256，再安全解压，并要求 `SHA256SUMS` 精确覆盖全部成员。路径穿越、绝对路径、重复成员、符号链接、硬链接、缺项、额外成员与摘要不一致全部 fail closed。macOS `/var` 与 `/private/var` 通过 realpath 规范化后比较。

## 授权创建后、内部 claim 前失败

只要授权记录文件已经创建，wrapper 在内部 claim 前发生任何失败，就必须：

- 生成公开、脱敏的 `CONSUMED_FAILED_PRECLAIM` 结果；
- 写入阻止后续执行的 consumed marker；
- 明确 `authorization_claimed=false`；
- 明确 `authorization_consumed=true`；
- 明确 `replay_permitted=false` 与 `automatic_retry_permitted=false`；
- 保持板卡、串口、esptool、Flash/NVS、网络、Broker、PREPARE、VERIFY、ACTIVATE、CLEANUP 全部为 false。

## 不变边界

既有 immutable/recovery TAR、二进制、摘要、PR #188、PR #189、旧物理 D2 终态均不得改变或重放。修复评审通过后仍需全新的 host-only final preflight、request binding 与精确物理授权；本层不创建物理授权。
