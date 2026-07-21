# H3/N2 Stage 2D-1 双槽 NVS 凭据持久化实现

**基线：** `main = 76dba47bbb4badb8412afaaa3f2e93f6ec53af19`  
**开发分支：** `feature/h3-n2-stage2d1-nvs-persistence-20260721-v49`  
**范围：** 节点凭据的真实 NVS 后端、应用层认证加密、掉电恢复状态机与非生产编译目标

## 1. 阶段目标

Stage 2D-1 将 Stage 2C-3 的纯内存 journal 合同落实为可调用的持久化实现，但仍不接入生产配对闭环，也不切换真实 MQTT profile。

本阶段实现：

- ESP-IDF NVS blob 读、写、擦除和显式 `nvs_commit()` 后端；
- `slot_a`、`slot_b`、`active` 三键双槽事务；
- HMAC eFuse 根密钥派生的每槽、每 generation 密钥；
- ChaCha20-Poly1305 认证加密信封；
- 明文 SHA-256 摘要、固定 schema、slot、state、generation 和长度绑定；
- 凭据确定性二进制编码与严格解码；
- PREPARED、COMMITTED、active marker 最后切换；
- 掉电、写失败、marker 失败、密文损坏和冲突状态恢复；
- 最小 ESP32-C6 与完整 RC2 产品板的非生产编译目标。

## 2. 存储布局

NVS namespace 默认为 `gh_pair_v1`，键名均不超过 ESP-IDF NVS 的 15 字符限制：

```text
slot_a
slot_b
active
```

槽记录为单个认证加密 blob：

```text
magic
schema_version
physical_slot
record_state
credential_generation
plaintext_size
plaintext_sha256
nonce
ciphertext
poly1305_tag
```

active marker 为固定长度 blob：

```text
magic
schema_version
active_slot
active_generation
crc32
```

marker 不包含凭据正文，也不包含密钥。

## 3. 密钥模型

ESP32-C6 正式后端使用 HMAC 外设的 upstream 模式：

1. 产品制造或安全初始化阶段向选定 eFuse key block 写入随机根密钥；
2. key purpose 必须设置为 HMAC upstream；
3. 根密钥不由应用读取；
4. 软件向 HMAC 外设提交固定 domain、slot 和 generation；
5. HMAC 输出作为当前记录的 256 位 ChaCha20-Poly1305 密钥；
6. 密钥、明文和临时缓冲区在使用后主动清零。

当前仓库不包含：

- eFuse 烧写命令；
- 根密钥；
- 自动 key provisioning；
- 自动启用 Secure Boot、Flash Encryption 或 NVS Encryption。

这些操作不可逆，必须在后续制造安全阶段单独冻结和授权。

## 4. 凭据编码

`RamCredentialBundle` 被编码为确定性、长度前缀二进制格式。解码要求：

- magic、schema version 和字段数量精确匹配；
- 输入必须完整消费，不允许尾随数据；
- 字符串不得包含 NUL；
- 字段长度分别受限；
- schema、system ID、node ID、Broker host、TLS server name、用户名、client ID、generation、端口和密码均重新验证；
- 解码失败时临时字符串主动清零；
- 输出对象在覆盖前先清除旧凭据。

## 5. 事务顺序

### 5.1 Prepare

```text
恢复当前状态
→ 选择非活动槽
→ 编码凭据
→ 以 PREPARED 状态认证加密
→ nvs_set_blob(candidate)
→ nvs_commit()
→ 读回、解密并验证
```

### 5.2 Commit

```text
恢复 PREPARED candidate
→ 重新封装为 COMMITTED
→ nvs_set_blob(candidate)
→ nvs_commit()
→ 读回验证
→ 写 active marker
→ nvs_commit()
→ 读回验证 marker
```

active marker 永远最后写入。旧 active 槽在新 marker 成功前保持不变。

### 5.3 Rollback

仅允许擦除 PREPARED candidate。较高 generation 的 COMMITTED orphan 不会自动激活，也不会被普通 rollback 静默删除。

## 6. 掉电恢复语义

- active marker 与对应 COMMITTED 槽完全匹配：恢复 active；
- active + 更高 PREPARED：保留旧 active，并暴露待验证 candidate；
- active + 更高 COMMITTED orphan：保留旧 active，新记录绝不自动激活；
- active + 较低 COMMITTED：视为旧基线槽；
- active + 损坏的非活动槽：继续提供 marker 选定的 active，同时阻止损坏槽被误激活；下一次 prepare 可以覆盖损坏槽；
- marker 损坏、marker 指向不存在或不匹配的槽、双槽歧义：失败关闭；
- 无 marker + PREPARED：没有 active；
- 无 marker + COMMITTED orphan：没有 active，不自动猜测；
- active 槽认证失败：失败关闭。

## 7. 当前非生产包装器

`greenhouse_pairing_persistence_lab` 仅用于编译和后续隔离测试：

- setup 只构造对象；
- 开机不打开 NVS；
- 开机不读取 NVS；
- 开机不写 NVS；
- 内部按钮仅提供人工触发的 `NVS_READONLY` recovery probe；
- 不提供 prepare、commit、erase 或 eFuse 写入动作；
- 不接入正式 MQTT；
- 不修改生产 RC2 YAML。

## 8. CI 与故障矩阵

host 故障矩阵覆盖：

- 空存储；
- 首次 enrollment 的 4 个 commit 掉电点；
- 已有 active 时 prepare 的 2 个掉电点；
- 已有 PREPARED 时 commit 的 4 个掉电点；
- PREPARED rollback；
- 有 active 或无 active 的 COMMITTED orphan 均需显式丢弃；
- active marker 损坏；
- active 槽密文/tag 损坏；
- inactive 槽密文/tag 损坏；
- 损坏 inactive 槽被下一次 prepare 安全覆盖；
- 新 generation 成功切换；
- 较高 COMMITTED orphan 不自动激活。

ESP32-C6 编译门覆盖：

- 最小板非生产目标；
- 完整 RC2 产品板非生产目标；
- NVS、HMAC、ChaCha20-Poly1305 源文件编译和链接；
- 生产 YAML、真实 Broker、MQTT setter、eFuse 写入和 NVS 全分区擦除边界扫描。

## 9. 仍未完成

Stage 2D-1 完成后仍需后续阶段处理：

- 冻结产品专用 NVS 分区大小和分区表迁移；
- 制造阶段 HMAC eFuse key provisioning；
- 实板写入、断电和擦写寿命测试；
- NVS 空间不足与 `ESP_ERR_NVS_NO_FREE_PAGES` 实板恢复策略；
- OTA 跨 schema 迁移；
- candidate MQTT profile 真实验证器；
- 配对 worker、持久化和 MQTT 激活的完整事务编排；
- 正式产品 UI 与恢复出厂流程。
