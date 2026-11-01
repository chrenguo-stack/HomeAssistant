# gh-h3-node-persistent-credentials-v1

## 1. 定位

本合同冻结 H3/N2 Stage 2D-1 节点凭据持久化语义。它允许真实 NVS blob 操作，但不授权生产配对自动写入、真实 MQTT profile 切换或 eFuse 自动烧写。

## 2. 命名

默认 namespace：

```text
gh_pair_v1
```

固定键：

```text
slot_a
slot_b
active
```

## 3. 槽记录

每个槽记录必须：

- 使用 schema version 1；
- 绑定物理槽 A 或 B；
- 状态仅为 PREPARED 或 COMMITTED；
- generation 非零；
- 明文长度非零且不超过 12288 bytes；
- 包含使用独立 digest key 计算的 HMAC-SHA256 payload digest；
- 使用 96 位随机 nonce；
- 记录根密钥必须域分离派生 encryption key 与 digest key；
- 使用 ChaCha20-Poly1305；
- header 全部作为 AEAD AAD；
- 解密后重新计算并常量时间比较摘要；
- 凭据 generation 与信封 generation 精确一致。

## 4. active marker

active marker 必须使用与槽记录相同的认证加密 envelope 机制。其解密正文只允许包含 marker magic、marker schema version、slot、保留字节和 generation。

验证必须同时满足：

- envelope slot 为 A 或 B；
- envelope state 为 COMMITTED；
- envelope generation 非零；
- marker 正文 slot 与 envelope slot 精确一致；
- marker 正文 generation 与 envelope generation 精确一致；
- marker 指向同槽、同 generation 的 COMMITTED credential 记录；
- AEAD、keyed digest 和正文结构全部通过。

不得使用 CRC、明文 selector 或未认证 metadata 作为 active 选择依据。没有合法 marker 时不得自动选择任意 COMMITTED 记录。

## 5. 写入顺序

Prepare：

```text
candidate PREPARED write
→ commit
→ read-back verify
```

Commit：

```text
candidate COMMITTED write
→ commit
→ read-back verify
→ authenticated active marker write
→ commit
→ decrypt and read-back verify
```

不得在 candidate COMMITTED 读回验证前写 marker。

## 6. Mutation 失败

任一 write、erase 或 commit 错误必须 poison 当前 read-write backend。poisoned backend 不得继续读取、写入、擦除或提交；必须销毁并重新打开后才能恢复。不得通过后续无关 commit 将失败事务的缓存内容意外持久化。

## 7. 恢复

- marker 对应槽有效：允许输出 active credentials；
- 非活动 PREPARED generation 必须大于 active；
- 非活动 COMMITTED generation 小于 active：旧基线；
- 非活动 COMMITTED generation 大于 active：orphan，不自动激活；
- 非活动损坏：active 可继续输出，但 candidate 激活失败关闭；
- active 槽损坏：不输出 credentials；
- marker 损坏或不匹配：不输出 credentials；
- 无 marker 时任何槽都不得自动成为 active；
- 双 PREPARED、同 generation 双槽或其他歧义：失败关闭；
- CONFLICT 状态不得向调用者保留 active 或 candidate credential 输出。

## 8. 密钥

生产实现必须使用设备唯一、不可由固件读取的根密钥派生记录根密钥。ESP32-C6 路线冻结为 HMAC upstream eFuse key。记录根密钥必须分别使用 `gh-persist-encryption-v1` 和 `gh-persist-digest-v1` 域派生两个子密钥。仓库不得包含根密钥或不可逆 eFuse 写入动作。

## 9. 清零

以下数据在完成或失败路径均必须主动清零：

- 派生记录根密钥；
- encryption key 和 digest key；
- 明文凭据编码；
- 解密输出临时缓冲区；
- 摘要临时缓冲区；
- nonce 临时缓冲区；
- 编解码失败前调用者持有的旧输出；
- 语义冲突时的 active/candidate 输出；
- 被覆盖的旧 `RamCredentialBundle` 字符串。

## 10. 防回滚限制

认证 marker 能阻止任意修改和伪造，但不能识别曾经合法的旧 marker 与旧 slot 快照重放。若攻击者恢复一份内部自洽的旧快照，当前 generation 规则无法证明其陈旧。生产防回滚需要后续使用受保护单调计数器、可信版本锚点，或与 Secure Boot/Flash Encryption 制造策略共同冻结。

## 11. 范围限制

本合同不代表：

- HMAC eFuse 已烧写；
- NVS 分区容量已冻结；
- 实板掉电测试已通过；
- MQTT candidate 已验证；
- production MQTT 已切换；
- Home Assistant、T1 或 M401A 已变更。
