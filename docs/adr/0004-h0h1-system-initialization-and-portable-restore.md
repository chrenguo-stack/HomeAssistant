# ADR-0004：H0/H1 系统初始化、可移植加密备份与双主机身份冲突合同

- 状态：已接受（源码与 host-only 合同）；真实 T1 初始化、恢复、匿名关闭和生产激活尚未授权
- 日期：2026-08-02
- 决策：`D1-H0H1-V07-IDENTITY-ALIGNMENT-GREENHOUSE-INIT-PORTABLE-RESTORE-CONTRACT-AND-HOST-ONLY-HARNESS-CREATION-20260802-01`
- 前置：ADR-0002、ADR-0003、技术路线 V0.7
- 关联阶段：H0、H1

## 1. 背景

仓库已经具备 T1 同机回退、Mosquitto/Dynamic Security 隔离演练、Manager 身份迁移、
C-07 可靠退役和大量只读审计工具，但此前没有真正的首次初始化生命周期，也没有一个
可加密离机、可在第二台合格 T1 上恢复并检测系统身份冲突的完整合同。

本决策先冻结源码和 host-only 行为，不直接操作任何 T1、Broker、Home Assistant、节点或
生产凭据。

## 2. 决策

### 2.1 V0.7 身份先行

H0/H1 必须建立在 ADR-0003 的身份语义上：

- NODE_ID 只属于一次 assignment；
- retired NODE_ID 永久封存；
- 已退役 HARDWARE_ID 只有在上一 retirement outbox 完成后，才可使用全新 pairing_id、
  严格递增 pairing_epoch、新凭据、更高 generation 和从未使用的新 NODE_ID 重新配对；
- 不保留跨硬件 NODE_ID 复用开关。

### 2.2 `greenhouse-init` 生命周期

正式模块放入 `greenhouse_manager.bootstrap`，不进入长期运行的 `runtime` 依赖方向。

首次初始化生成：

- `SYSTEM_ID`；
- `MANAGER_ID`；
- 32 字节 SYSTEM_ROOT_KEY；
- 独立 ECDSA P-256 系统 CA 与私钥；
- system/manager identity 文档；
- marker-last 的 `INITIALIZED.json` 自绑定清单。

规则：

1. 初始化根目录必须是真实目录、非符号链接并保持 0700；
2. 所有身份和密钥文件必须为 0600；
3. 任一部分文件存在而 marker 缺失时失败关闭，不自动覆盖；
4. marker 存在时只做完整性复核，重复初始化返回原身份；
5. 新建初始化默认禁用，必须同时提供 enable flag 和精确确认词；
6. 初始化代码不得访问网络、启动子进程或修改生产服务。

### 2.3 可移植加密备份

可移植备份必须包含完整的成对角色清单：

- system identity、SYSTEM_ROOT_KEY、系统 CA 和 CA 私钥；
- manager identity；
- registration、credential lifecycle 和 retirement outbox 状态；
- Broker Dynamic Security 状态；
- Broker persistence 状态。

允许多个逻辑角色由同一 SQLite 文件承载，但每个必需角色都必须显式绑定到清单。缺少、
多出或替换角色均失败关闭。

备份格式：

- envelope：`gh.h0h1.portable-backup-envelope/1`；
- payload manifest：`gh.h0h1.portable-restore-manifest/1`；
- Scrypt 固定参数派生 256 位密钥；
- AES-256-GCM 认证加密；
- manifest、明文 payload、密文和完整 envelope 各自有 SHA-256 绑定；
- passphrase 只从 0600 文件读取，不允许作为 CLI 参数值；
- 输出为 0600，父目录为 0700；
- `portable_off_host=true`，但 `live_apply_enabled=false`。

### 2.4 恢复与身份冲突

恢复必须写入一个尚不存在的目标目录，先写临时 0700 树，逐项校验后 marker-last 原子改名。
恢复结果永远保持：

- `activation_enabled=false`；
- `identity_claim_required_before_activation=true`；
- `production_services_modified=false`；
- `network_operation=false`。

离线身份 guard 维护 `SYSTEM_ID -> host_instance_id` 唯一 claim：

- 同一主机重复 claim 幂等；
- 不同主机同时 claim 同一 SYSTEM_ID 必须失败；
- 原主机显式 release 后，恢复主机才可 claim；
- claim/release 默认禁用并需要精确确认；
- 该 host-only guard 不替代未来生产环境的网络仲裁和提交后审计。

### 2.5 匿名关闭隔离回归

源码阶段只建立 secret-free policy 模型和隔离探针：

- exactly one Manager；
- exactly one Home Assistant；
- at least one node；
- 所有客户端具备独立 client_id、username 和正 generation；
- ACL filter 合法；
- 匿名 publish 和 subscribe 都必须被明确拒绝；
- policy 不得包含 password、secret、token 或 private-key 字段；
- `live_apply_enabled=false`。

该结果不能表述为真实 Mosquitto、真实 T1 或生产匿名关闭验收。

## 3. 安全边界

本决策不授权：

- T1 读写、Docker、Compose 或容器操作；
- 生产 Broker、Home Assistant、Manager 或节点修改；
- 真实 SYSTEM_ID、CA、密钥或备份生成；
- 关闭 anonymous MQTT；
- 真实恢复、服务启动、release、tag、deployment；
- Ready 或 merge。

## 4. 验收层级

源码阶段完成条件：

1. V0.7/C-07 身份语义适配当前 main；
2. bootstrap 模块可由 pyproject CLI 实际调用；
3. focused 单元和 CLI 集成测试通过；
4. 双主机初始化、加密备份、恢复、冲突和匿名拒绝 host-only harness 通过；
5. GitHub CI 生成 secret-free review Artifact；
6. PR 保持 Draft。

H0/H1 的真实验收仍需后续独立阶段门。
