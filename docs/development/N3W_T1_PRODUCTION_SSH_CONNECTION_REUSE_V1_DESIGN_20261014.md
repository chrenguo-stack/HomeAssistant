# N3W T1 量产远程接管与 SSH 连接复用 V1 设计 — 2026-10-14

## 1. 决策

为避免量产工程膨胀，当前阶段不引入完整的每机永久 SSH 管理密钥体系。

F5 量产安装流程采用：

```text
F5_V1_REMOTE_ACCESS_MODEL=INTERACTIVE_PASSWORD_ONCE_WITH_SSH_CONNECTION_REUSE
SSH_CONTROL_CONNECTION=true
HOST_KEY_CHECKING=true
NORMAL_DEPLOYMENT_PASSWORD_PROMPTS=1

PER_DEVICE_MANAGEMENT_KEY=false
SSH_KEY_ROTATION=false
SSH_ACCOUNT_LIFECYCLE=false
PASSWORD_AUTH_DISABLE=false
DEDICATED_N3W_ADMIN_ACCOUNT=false
```

目标：操作员在新 T1 开始部署时输入一次 SSH 密码，随后整个自动部署流程复用同一 SSH 控制连接，不再重复询问密码。

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

正常流程中，除第一次密码输入外，不应再出现交互式密码提示。

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

> SSH 只解决部署通道；产品密钥只解决产品身份。量产阶段第一次输入一次密码，之后复用 SSH 控制连接自动完成部署，不在当前阶段引入永久 SSH 管理密钥体系。

这项收敛优先控制工程复杂度，同时保留 Host Key、安全边界和不可变产物哈希验证。
