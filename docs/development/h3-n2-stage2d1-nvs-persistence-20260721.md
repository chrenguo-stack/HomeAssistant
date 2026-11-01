# H3/N2 Stage 2D-1 双槽 NVS 凭据持久化实现

**基线：** `main = 76dba47bbb4badb8412afaaa3f2e93f6ec53af19`  
**开发分支：** `feature/h3-n2-stage2d1-nvs-persistence-20260721-v49`  
**范围：** 节点凭据的真实 NVS 后端、应用层认证加密、掉电恢复状态机与非生产编译目标

## 1. 阶段目标

Stage 2D-1 将 Stage 2C-3 的纯内存 journal 合同落实为可调用的持久化实现，但仍不接入生产配对闭环，也不切换真实 MQTT profile。

本阶段实现：

- ESP-IDF NVS blob 读、写、擦除和显式 `nvs_commit()` 后端；
- `slot_a`、`slot_b`、`active` 三键双槽事务；
- HMAC eFuse 根密钥派生的每槽、每 generation 记录根密钥；
- 由记录根密钥域分离派生 encryption key 与 digest key；
- ChaCha20-Poly1305 认证加密信封；
- keyed HMAC-SHA256 payload digest；
- 凭据确定性二进制编码与严格解码；
- PREPARED、COMMITTED、active marker 最后切换；
- active marker 自身也使用认证加密信封，不依赖可伪造 CRC；
- NVS mutation 失败后句柄 poisoned，禁止后续读写或意外提交未完成变更；
- 掉电、写失败、marker 失败、密文损坏和冲突状态恢复；
- 最小 ESP32-C6 与完整 RC2 产品板的非生产编译目标。

## 2. 存储布局

NVS namespace 默认为 `gh_pair_v1`：

```text
slot_a
slot_b
active
```

槽记录为认证加密 blob：

```text
magic
schema_version
physical_slot
record_state
credential_generation
plaintext_size
payload_hmac_sha256
nonce
ciphertext
poly1305_tag
```

active marker 同样封装为认证加密 blob，其明文仅包含：

```text
marker_magic
marker_schema_version
active_slot
reserved
active_generation
```

marker 的 envelope metadata、AAD 和解密后正文必须对 slot 与 generation 三重一致。任意位修改都会因 AEAD 或正文校验失败而被拒绝。

## 3. 密钥模型

ESP32-C6 正式后端使用 HMAC 外设的 upstream 模式：

1. 产品制造或安全初始化阶段向选定 eFuse key block 写入随机根密钥；
2. key purpose 必须设置为 HMAC upstream；
3. 根密钥不由应用读取；
4. 软件向 HMAC 外设提交固定 domain、slot 和 generation；
5. HMAC 外设输出作为当前记录的 256 位记录根密钥；
6. 记录根密钥通过 `gh-persist-encryption-v1` 和 `gh-persist-digest-v1` 分别派生 encryption key 与 digest key；
7. digest 使用 HMAC-SHA256，不暴露可用于离线猜测的裸明文摘要；
8. 记录根密钥、子密钥、明文和临时缓冲区在使用后主动清零。

仓库不包含 eFuse 烧写命令、根密钥、自动 key provisioning、Secure Boot 或 Flash Encryption 自动配置。不可逆制造动作必须后续单独冻结和授权。

## 4. 凭据编码

`RamCredentialBundle` 使用确定性、长度前缀二进制格式。解码要求：

- magic、schema version 和字段数量精确匹配；
- 输入完整消费，不允许尾随数据；
- 字符串不得包含 NUL；
- 字段长度分别受限；
- schema、标识符、Broker、TLS 名称、端口、generation 和凭据字段全部重新验证；
- 编解码任何失败路径均清空调用者输出；
- 临时字符串和明文向量主动清零；
- 输出对象在覆盖前清除旧凭据。

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
→ 认证加密 active marker
→ nvs_set_blob(active)
→ nvs_commit()
→ 读回、解密并验证 marker
```

active marker 永远最后写入。旧 active 槽在新 marker 成功前保持不变。

### 5.3 Mutation 失败

任何 `nvs_set_blob`、`nvs_erase_key` 或 `nvs_commit` 错误都会 poison 当前 read-write backend：

- 后续 read、write、erase 和 commit 全部失败关闭；
- 未提交缓存不得被后续无关操作意外提交；
- 只有销毁 backend 并重新打开，通常即重启后，才可再次恢复；
- 不执行自动全分区擦除。

### 5.4 Rollback

仅允许擦除 PREPARED candidate。较高 generation 的 COMMITTED orphan 不自动激活，也不被普通 rollback 静默删除。

## 6. 掉电恢复语义

- marker 与对应 COMMITTED 槽完全匹配：恢复 active；
- active + 更高 PREPARED：保留旧 active，并暴露待验证 candidate；
- active + 更高 COMMITTED orphan：保留旧 active，新记录绝不自动激活；
- active + 较低 COMMITTED：视为旧基线槽；
- active + 损坏非活动槽：继续提供 marker 选定的 active，下一次 prepare 可覆盖损坏槽；
- marker 损坏、marker 指向不匹配槽、双槽同 generation 或其他歧义：失败关闭；
- 语义冲突时 snapshot 不声明任何 credentials available，并清空调用者传入的 active/candidate 输出；
- 无 marker + PREPARED：没有 active；
- 无 marker + COMMITTED orphan：没有 active，不自动猜测；
- active 槽认证失败：不输出 credentials。

## 7. 当前非生产包装器

`greenhouse_pairing_persistence_lab` 仅用于编译和后续隔离测试：

- setup 只构造对象；
- 开机不打开、读取或写入 NVS；
- 内部按钮仅提供人工触发的 `NVS_READONLY` recovery probe；
- read-only namespace 尚不存在时解释为 `EMPTY`；
- 不提供 prepare、commit、erase 或 eFuse 写入动作；
- 不接入正式 MQTT；
- 不修改生产 RC2 YAML。

最小编译目标使用 `enable_on_boot: false` 的临时 Wi-Fi 配置，仅用于让 ESPHome 2026.4.3 管理的 `espressif/mdns` 组件参与编译；不会在启动时连接网络。

## 8. CI 与故障矩阵

host 故障矩阵覆盖：

- codec 失败清空旧输出；
- 加密信封正常打开；
- slot 与 generation AAD 篡改失败；
- 不同设备根密钥无法解密；
- active marker 位修改失败；
- mutation 失败后 live backend poisoned；
- 首次 enrollment 的 4 个 commit 掉电点；
- 已有 active 时 prepare 的 2 个掉电点；
- 已有 PREPARED 时 commit 的 4 个掉电点；
- PREPARED rollback；
- COMMITTED orphan 显式处理；
- active 和 inactive 槽密文/tag 损坏；
- 损坏 inactive 槽被下一次 prepare 安全覆盖；
- 冲突状态清空 active/candidate 输出；
- 新 generation 成功切换；
- 较高 COMMITTED orphan 不自动激活；
- 旧有效 marker 重放的已知防回滚限制被显式测试。

ESP32-C6 编译门覆盖最小板、完整 RC2 产品板、NVS、HMAC、HMAC-SHA256、ChaCha20-Poly1305、managed mDNS 依赖和临时 Wi-Fi 值日志泄漏检查。

## 9. 仍未完成

- 冻结产品专用 NVS 分区大小和分区表迁移；
- 制造阶段 HMAC eFuse key provisioning；
- 实板写入、断电和擦写寿命测试；
- NVS 空间不足与 `ESP_ERR_NVS_NO_FREE_PAGES` 实板恢复策略；
- 完整旧 NVS 快照重放的防回滚锚点；认证 marker 能阻止任意修改，但不能识别一份曾经合法的完整旧 marker/slot 快照；
- OTA 跨 schema 迁移；
- candidate MQTT profile 真实验证器；
- 配对 worker、持久化和 MQTT 激活的完整事务编排；
- 正式产品 UI 与恢复出厂流程。
