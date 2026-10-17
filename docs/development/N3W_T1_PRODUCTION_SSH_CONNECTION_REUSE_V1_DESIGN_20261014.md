# N3W T1 量产远程接管与 SSH 连接复用 V1 设计 — 2026-10-14

## 1. 决策

为避免量产工程膨胀，当前阶段不引入完整的每机永久 SSH 管理密钥体系。

F5 量产安装流程采用：

```text
F5_V1_REMOTE_ACCESS_MODEL=INTERACTIVE_PASSWORD_PER_CONNECTION_EPOCH_WITH_SSH_CONNECTION_REUSE
SSH_CONTROL_CONNECTION=true
HOST_KEY_CHECKING=true
NORMAL_DEPLOYMENT_PASSWORD_PROMPTS_BEFORE_REBOOT=1
POST_REBOOT_PASSWORD_PROMPTS=1
NORMAL_FULL_RUN_PASSWORD_PROMPTS=2

PER_DEVICE_MANAGEMENT_KEY=false
SSH_KEY_ROTATION=false
SSH_ACCOUNT_LIFECYCLE=false
PASSWORD_AUTH_DISABLE=false
DEDICATED_N3W_ADMIN_ACCOUNT=false
```

目标：每个 SSH connection epoch 只交互输入一次密码并复用同一控制连接。正常 F5 run 包含一次 T1 reboot，因此重启前输入一次，重启后重新认证再输入一次；生产批准仍只有一次。

本设计只进入 F5 量产流程收敛，不改变当前 F3/F4 已冻结的严格执行合同。

## 2. V1 操作模型

最终量产操作：

```text
操作员输入一次 T1 SSH 密码
        ↓
建立 SSH ControlMaster/ControlPath 控制连接
        ↓
系统与容量检查
        ↓
Docker / Compose 安装
        ↓
产品 payload 与镜像传输
        ↓
产品 provisioning
        ↓
服务激活与端到端验收
        ↓
证据归档
        ↓
关闭 SSH 控制连接
```

正常流程中，同一个 SSH connection epoch 内不应重复提示密码。一次正常 reboot 会终止旧连接，重启后需要第二次交互式认证，但不重新请求生产批准。

## 3. 明确不做的内容

当前 V1 不开发：

- 每台 T1 永久管理 SSH key；
- SSH key rotation；
- bootstrap key 生命周期；
- 独立 n3w-admin 账户；
- 自动关闭 password authentication；
- 重新 enrollment 状态机；
- 工厂 PKI / 一次性 per-device SSH bootstrap secret；
- 将产品 TLS 私钥复用于 SSH。

这些能力如未来产品规模、远程维护或安全要求确实需要，再以独立后续版本评估，不进入当前 F5 最小闭环。

## 4. Host Key 边界

V1 虽不引入永久管理 key，但仍保留 SSH Host Key 校验。

原则：

```text
HOST_KEY_CHECKING=true
HOST_KEY_MISMATCH=STOP
UNKNOWN_SSH_ERROR=STOP
IGNORE_HOST_KEY_ERROR=false
```

不得为了减少人工输入而使用关闭 Host Key 校验的方式。

首次连接的 Host Key 接受/绑定方式由 F5 具体实现阶段进一步收敛，但不得退化为无校验连接。

## 5. 与产品身份密钥分离

SSH 远程部署通道和产品运行身份必须保持分离。

产品 provisioning 生成的以下内容继续保留：

- SYSTEM_ID；
- Broker CA / TLS key / certificate；
- Manager identity；
- Broker service credentials；
- 其他每机运行时身份材料。

这些材料不得用于 SSH 登录，也不得为了简化 SSH 流程而移除。

## 6. 对哈希验证的影响

### 6.1 不变的哈希

SSH 连接复用不会改变既有不可变产物：

- GitHub artifact digest；
- runtime payload SHA-256；
- payload manifest SHA-256；
- exact image tar / image digest；
- source binding。

因此量产仍可严格验证：

```text
IMMUTABLE_ARTIFACT_HASH=PASS
IMAGE_DIGESTS=PASS
PRODUCT_SOURCE_BINDING=PASS
```

### 6.2 每机运行时内容本来就不同

正式 provisioning 会生成每机不同的：

- TLS private key；
- certificate；
- SYSTEM_ID；
- Manager identity；
- Broker credentials；
- runtime state。

因此不采用“所有成品整盘 SHA-256 必须完全一致”作为验收合同。

正确模型是：

```text
IMMUTABLE_SOFTWARE_CONTENT=HASH_BOUND
PER_DEVICE_IDENTITY=RELATIONSHIP_AND_VALIDITY_VERIFIED
WHOLE_DISK_EQUALITY_REQUIRED=false
```

每机秘密只验证内部一致性、唯一性、证书/密钥匹配和运行合同，不要求不同设备之间哈希相同。

## 7. 为什么优先采用连接复用

相比永久 SSH key 体系，本方案：

- 直接解决当前重复密码提示；
- 不新增目标机长期 SSH 凭据；
- 不新增 key rotation / reenrollment / account lifecycle；
- 不改变产品身份设计；
- 不影响 artifact/source/image 哈希绑定；
- 基本使用 OpenSSH 原生机制即可实现；
- 更符合当前项目“先完成量产最小闭环，再按真实需求扩展”的工程原则。

## 8. F5 实现要求

F5 实现时至少验证：

1. 第一次密码认证成功后建立 SSH 控制连接；
2. 后续 ssh/scp 复用连接，不重复提示密码；
3. 控制连接失效时明确 STOP，不静默切换到未知认证方式；
4. Host Key 检查保持启用；
5. 密码不写入 GitHub、日志、artifact 或长期部署记录；
6. 部署结束或失败清理控制连接；
7. 安装过程进度可见；
8. F5 自动化测试覆盖连接建立、复用、断线、清理与错误分类。

## 9. 与当前 F3 的关系

```text
F3_REMOTE_ACCESS_MODEL=CURRENT_EXISTING_PATH
F3_STRICT_CHECKS=true
F3_AUTHORIZATION_SEMANTICS_UNCHANGED=true
F3_OVERRIDE_FRAMEWORK_ACTIVE=false
F5_V1_SSH_CONNECTION_REUSE=DESIGN_ONLY
```

当前 F3 不为此方案临时修改源码。先完成真实 F3/F4 路径验证，再在 F5 将人工复杂度收敛。

## 10. 结论

当前项目冻结的量产 V1 原则是：

> SSH 只解决部署通道；产品密钥只解决产品身份。每个 SSH connection epoch 第一次输入一次密码并复用控制连接；一次正常 reboot 的完整 F5 run 共两次密码输入，不在当前阶段引入永久 SSH 管理密钥体系。

这项收敛优先控制工程复杂度，同时保留 Host Key、安全边界和不可变产物哈希验证。


## 11. F5-0 架构合同冻结补充 — 2026-10-17

本节冻结首次主机信任、重启后的重新认证和连接所有权；与前文早期“一次密码覆盖整次 run”的表述
冲突时，以本节和本文件第 1 节更新后的字段为准。

~~~text
PRODUCTION_AUTHORIZATION_PROMPTS=1
PRE_REBOOT_PASSWORD_PROMPTS=1
POST_REBOOT_PASSWORD_PROMPTS=1
NORMAL_FULL_RUN_PASSWORD_PROMPTS=2
PASSWORD_PERSISTED=false
NEW_SSH_LOGIN_KEY=false
HOST_KEY_CHECKING=true
HOST_KEY_MISMATCH=STOP
UNKNOWN_SSH_ERROR=STOP
~~~

### 11.1 首次 Host Key 信任

首次网络连接不能用“从同一未验证网络连接看到的 key”证明自己可信。

优先从该 T1 的本地控制台或已有私有资产台账取得 SSH host public-key fingerprint，再与网络连接
提供的 key 比对。缺少独立可信 fingerprint 时停在信任建立边界，不进入生产批准。

`ssh-keyscan` 只能用于取得候选 key，不能独立建立信任。已知 key mismatch 必须 STOP；不得通过删除
旧 known_hosts 记录、换 alias 或 accept-new 静默绕过。

### 11.2 ControlMaster 所有权

Mac production orchestrator 是正常生产路径唯一的 SSH master/socket/config owner。所有正常路径的
ssh/scp 调用必须通过同一个经过测试的 transport adapter 复用连接。

socket 使用本机私有、短路径、随机目录，不放仓库或共享/同步目录。密码由 OpenSSH 直接从终端读取，
F5 程序不读取、不缓存、不写参数、环境变量、日志或 artifact。

ControlPath 丢失、master 死亡或认证路径不确定时必须 STOP，不能静默开一个普通新连接继续 mutation。

### 11.3 正常 reboot

取得合法 reboot authority 后，原 SSH 控制连接会随 T1 reboot 失效。编排器有界等待 SSH 恢复，
重新严格核对同一个 host key，然后提示第二次密码并建立新的 master。第二次密码只是重新认证，
不是第二次生产授权。

非预期断线时停止后继 mutation，先只读核对目标 durable state；UNKNOWN 不能自动重放。

### 11.4 Cleanup

成功、失败和 Ctrl-C 都必须有界关闭本 run 拥有的 master、确认不再有活的受控连接，再删除本 run
socket/config 临时资料。不得使用广泛 `pkill ssh` 或清理用户其他 SSH 资源。

如果设备验收已 PASS，但无法证明生产会话已经安全关闭，则保留设备通过事实，F5 综合流程结果仍不能
写成普通 PASS。
