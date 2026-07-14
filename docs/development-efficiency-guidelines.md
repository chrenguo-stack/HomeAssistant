# 开发效率改进与工程化执行指南

> 状态：指导性文档  
> 适用范围：温室环境监测系统的固件、`greenhouse-manager`、T1 主机、MQTT、Home Assistant、配对、安全迁移、ESP-NOW、LoRa 与后续控制节点开发  
> 首次建立：2026-07-14

## 1. 目的

本项目已经形成较完整的技术架构、监测样机和主机数据闭环，但前期开发也暴露出以下效率问题：

- 现场脚本版本较多，文件名、SHA、路径和执行顺序依赖人工核对；
- 测试代码、生产代码和临时诊断代码之间可能出现细微差异；
- 一些真实对象结构、容器重建时序和网络启动竞态直到 T1 正式执行阶段才被发现；
- 项目状态分散在对话、交接文档、GitHub、T1 `/tmp` 和人工记录中；
- 正式失败后的诊断信息不够细，导致需要追加临时只读脚本才能定位根因；
- 多条产品路线并行展开时，容易分散当前关键路径上的开发资源。

本指南的目标不是降低安全要求，而是在保留双重确认、一次性授权、精确绑定、失败关闭和强制回滚的前提下，减少重复操作、无效实机循环和交接成本。

## 2. 当前开发优先级

在 `greenhouse-manager` 独立 MQTT 身份迁移完成前，主线固定为：

```text
H3：greenhouse-manager 独立 MQTT 身份迁移
→ 节点凭据生命周期
→ N1/N2 真实节点安全接入
```

执行原则：

1. 任一时刻只设置一个阻塞整体进度的主任务；
2. 最多并行一个不影响主线的硬件验证任务；
3. ESP-NOW、LoRa 正式协议和控制节点不与 H3 抢占主线资源；
4. 未达到阶段验收条件，不提前进入依赖该阶段的后续开发。

## 3. 从临时脚本驱动转向仓库工具驱动

### 3.1 目标形态

逐步将 6Q、6R、6S、审计和回滚状态查询统一为仓库内版本化工具，例如：

```bash
ghctl m2 status
ghctl m2 prepare
ghctl m2 preflight
ghctl m2 authorize
ghctl m2 execute
ghctl m2 audit
ghctl m2 rollback-status
```

### 3.2 基本要求

- 工具代码必须进入 GitHub，并由 CI 测试；
- 生产执行器、回滚器、审计器和合同生成器必须调用同一套核心实现；
- 每次运行只生成数据包、授权、事务日志和证据，不再生成一套新的 Python 执行逻辑；
- 正式执行必须绑定仓库提交、工具版本、配置合同、目标主机状态和一次性授权；
- 临时执行材料允许位于 `/tmp`，但程序本身不得只存在于 `/tmp`；
- 继续保留两次独立操作员确认，不因工具整合而减少确认次数。

核心原则：

```text
程序固定、输入变化；
代码进入仓库、证据进入运行包。
```

## 4. 四级测试门禁

所有影响生产路径的功能必须依次经过以下验证：

| 级别 | 环境 | 主要目标 |
|---|---|---|
| L1 | 单元测试 | 字段、合同、授权、状态机、错误码、失败关闭 |
| L2 | 真实类集成测试 | 使用实际 factory、wrapper、adapter、driver 和嵌套结构 |
| L3 | 隔离容器测试 | recreate、挂载、权限、环境变量、MQTT 建连、故障注入和回滚 |
| L4 | T1 生产测试 | 只验证前三层无法证明的真实主机行为 |

### 4.1 必备回归场景

至少覆盖：

- 前几次轮询没有 MQTT socket，随后建立并保持稳定；
- 整个超时窗口内始终没有 MQTT socket；
- 密码文件存在但权限或所有者错误；
- 密码挂载存在但目标路径错误；
- Broker 明确拒绝认证；
- 容器启动成功但 manager 进程退出；
- factory/wrapper 使用真实嵌套结构；
- claim 前失败不消费授权；
- claim 后任意失败强制进入 rollback；
- rollback 后认证环境、overlay、挂载、密码文件和新建目录全部消失；
- Mosquitto、Home Assistant 和节点在 manager-only 事务中保持不变。

只有 L1—L3 全部通过后，才准备新的 T1 正式授权链。

## 5. 唯一机器可读项目状态

建议建立：

```text
project-state/
├── current-baseline.json
├── stage-status.json
├── retired-authorizations.json
└── production-runs/
    └── <run-id>.json
```

### 5.1 `current-baseline.json`

至少记录：

```json
{
  "repository_sha": "<approved-sha>",
  "manager_version": "<version>",
  "manager_image_digest": "<digest>",
  "active_stage": "H3",
  "last_verified_state": "anonymous_runtime_restored",
  "last_production_run": "<run-id>",
  "migration_completed": false
}
```

### 5.2 规则

- 状态文件由仓库工具读取和校验；
- 生产运行结束后自动生成候选更新；
- 退役授权、确认字符串和失败执行包只记录不可逆退役状态，不记录秘密值；
- 交接文档应尽量从机器状态和证据包生成，不再依赖人工复制大量 SHA；
- 状态文件不能替代真实运行时校验，只作为唯一的项目记录入口。

## 6. 生产运行证据包

每次正式或候选运行应生成脱敏证据目录：

```text
evidence/<run-id>/
├── metadata.json
├── preflight.json
├── authorization.json
├── transaction.json
├── failure-diagnostic.json
├── rollback-audit.json
├── service-fingerprints.json
└── summary.md
```

要求：

- 整体计算 SHA-256；
- 不包含密码、完整客户端 ID、秘密路径或敏感配置内容；
- 明确记录代码提交、工具版本、目标版本、执行阶段和最终结论；
- 失败时记录原始失败阶段和 rollback 是否完成；
- 可作为 CI artifact、GitHub Release 附件或受控内部证据保存；
- 新对话或新开发阶段首先读取最新证据包和 `current-baseline.json`。

## 7. 正式错误码和诊断设计

正式代码必须提供足以直接定位问题的脱敏子错误码，避免失败后再编写一次性诊断脚本。

建议至少区分：

```text
M2_IDENTITY_RUNTIME_OWNERSHIP_FAILED
M2_IDENTITY_ENV_BINDING_FAILED
M2_IDENTITY_PASSWORD_MOUNT_FAILED
M2_IDENTITY_PASSWORD_SOURCE_FAILED
M2_IDENTITY_BROKER_REJECTED
M2_IDENTITY_MQTT_SOCKET_TIMEOUT
M2_IDENTITY_SESSION_UNSTABLE
M2_IDENTITY_LOG_BINDING_FAILED
M2_ROLLBACK_RUNTIME_RESTORE_FAILED
M2_ROLLBACK_DIRECTORY_CLEANUP_FAILED
```

诊断记录应包含：

```json
{
  "stage": "authenticated_identity",
  "substage": "mqtt_session_wait",
  "attempts": 8,
  "elapsed_ms": 16234,
  "socket_seen": false,
  "broker_rejection_seen": false,
  "rollback_required": true
}
```

禁止记录：

- 密码和秘密文件内容；
- 完整用户名或客户端 ID；
- 未脱敏的主机敏感路径；
- 完整 Compose、`.env` 或 Home Assistant 存储内容；
- 未经过白名单约束的异常消息。

## 8. 自动化上传和校验

将以下机械步骤收敛到固定部署工具：

- 上传批准 artifact；
- SHA-256 校验；
- 文件权限校验；
- Python 编译或入口自检；
- 只读 preflight；
- 日志和证据保存；
- SHA、版本或合同不匹配时立即停止。

示例目标接口：

```bash
./tools/t1-deploy \
  --host 192.168.68.126 \
  --artifact dist/ghctl.py \
  --expected-sha <sha>
```

部署自动化不得代替两次操作员生产确认，也不得自动执行未确认的生产事务。

## 9. 统一完成状态

每项功能统一使用以下状态：

| 状态 | 含义 |
|---|---|
| `CODE_COMPLETE` | 代码、静态检查和单元测试完成 |
| `LAB_VERIFIED` | 真实类或隔离容器环境验证完成 |
| `FIELD_ACCEPTED` | 指定实机和验收周期通过 |

使用规则：

- PR 合并不等于 `FIELD_ACCEPTED`；
- preflight 通过不等于迁移完成；
- 一次短时实机成功不等于长期验收完成；
- 对外进度统计必须注明采用哪一种完成口径。

## 10. 单轮开发节奏

### 10.1 开始

每轮必须先冻结：

```text
本轮唯一目标
输入基线
允许修改范围
禁止修改范围
完成条件
测试矩阵
预计产物
```

### 10.2 开发

```text
修改仓库代码
→ L1 单元测试
→ L2 真实类集成测试
→ L3 隔离容器测试
→ PR 审核与合并
→ 准备 L4 T1 验证
```

### 10.3 实机

```text
只读 preflight
→ 第一次操作员确认
→ 创建一次性授权
→ 第二次操作员确认
→ 执行事务
→ 自动审计
→ 生成证据包
```

### 10.4 收尾

```text
更新 project-state
→ 标记 CODE_COMPLETE / LAB_VERIFIED / FIELD_ACCEPTED
→ 退役一次性授权和确认
→ 生成交接摘要
→ 确定下一轮唯一主任务
```

## 11. 近期实施顺序

按收益和依赖关系排序：

1. 修复 manager 重建后 MQTT 会话等待逻辑，使用有界轮询而不是首次无 socket 即失败；
2. 为认证身份阶段增加细分错误码和安全诊断记录；
3. 增加真实 wrapper/factory 与延迟 MQTT 建连的 L2/L3 回归测试；
4. 建立 `project-state/current-baseline.json` 和生产证据包格式；
5. 将现有 6Q/6R/6S 核心逻辑逐步收敛为版本化 `ghctl`；
6. 建立固定 T1 上传、校验和日志归档工具；
7. H3 完成并达到 `FIELD_ACCEPTED` 后，再恢复节点凭据、ESP-NOW、LoRa 和控制节点主线开发。

## 12. 不可削弱的安全边界

效率改进不得改变以下约束：

- 正式生产事务继续要求两次明确操作员确认；
- 授权必须短时、一次性、精确绑定且不可重放；
- claim 后任何失败都必须进入标准 rollback；
- rollback 失败或目录非空/不安全时必须停止并进入人工恢复；
- manager-only 事务不得修改 Mosquitto、Home Assistant、节点或 HA `.storage`；
- 匿名兼容路径在正式关闭条件达成前继续保留；
- 节点凭据不得在 manager 身份迁移完成前提前下发；
- 任何自动化都不能绕过版本、SHA、合同、目标状态和授权校验。

## 13. 预期收益

完成上述改造后，预期获得：

- 更少的临时脚本和人工复制错误；
- 更少的正式授权消耗和无效 T1 循环；
- 更快的失败根因定位；
- 更低的新对话和阶段交接成本；
- 更清晰、可审计的真实项目进度；
- 更稳定的生产执行、回滚和后续售后基础。

本指南作为后续开发、PR 规划、测试设计和实机执行的参考基线；具体协议和安全合同仍以对应版本化协议文件及实现代码为准。