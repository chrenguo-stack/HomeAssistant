# N3W T1 量产受控放行机制设计 — 2026-10-14

## 1. 决策

最终量产流程保留严格自动检查，但不采用“忽略全部错误并继续”的通用按钮。

引入受控放行机制：

```text
PRODUCTION_CONTROLLED_OVERRIDE_FRAMEWORK=APPROVED_FOR_F5_DESIGN
DEFAULT_POLICY=STRICT_FAIL_CLOSED
UNKNOWN_FAILURE_OVERRIDE_ALLOWED=false
HARD_STOP_OVERRIDE_ALLOWED=false
WHITELISTED_OVERRIDE_ONLY=true
PASS_WITH_OVERRIDE_REQUIRED=true
F3_CURRENT_STRICTNESS_UNCHANGED=true
```

本设计进入 F5 量产流程收敛，不改变当前 F3/F4 的既有门槛。

## 2. 三类检查

### 2.1 HARD_STOP

以下类型默认不可人工绕过：

- artifact / payload 哈希、内容集合、来源绑定不一致；
- CPU/体系结构或明确不兼容的目标 OS；
- 设备唯一身份冲突；
- 一次性授权已消耗、授权状态未知或无法证明；
- TLS、密钥、凭据或设备身份生成/验证失败；
- 实际安装容量低于确定的绝对最低容量；
- 不可逆步骤后状态未知；
- 未分类的新错误、程序异常或无法确认安全边界的错误。

规则：

```text
SEVERITY=HARD_STOP
OVERRIDE_ALLOWED=false
DEFAULT_ACTION=STOP
```

### 2.2 OVERRIDABLE

只有事先在源码中白名单化、且已经证明继续执行不会破坏核心安全和身份边界的检查，才允许人工放行。

典型候选：

- 剩余磁盘空间低于推荐安全余量，但仍高于动态计算的绝对最低容量；
- Docker 已存在，但版本、包来源、daemon 状态和配置经兼容性检查通过；
- fresh-host 理想基线的非关键偏差；
- Ubuntu 小版本/补丁级差异，经兼容性合同证明可接受；
- 其他经源码、测试和真实设备验证后显式升级为可放行的环境偏差。

规则：

```text
SEVERITY=OVERRIDABLE
OVERRIDE_ALLOWED=true
DEFAULT_ACTION=STOP_AND_REQUEST_OPERATOR_DECISION
```

每个可放行检查必须有固定 CHECK_ID，不允许运行时临时把未知错误降级为可放行。

## 2.3 WARNING

非关键诊断项只记录，不阻塞部署：

```text
SEVERITY=WARNING
OVERRIDE_REQUIRED=false
DEFAULT_ACTION=CONTINUE_AND_RECORD
```

## 3. 禁止“全局忽略错误”

量产程序不得提供以下语义：

```text
IGNORE_ALL_ERRORS=true
CONTINUE_ON_UNKNOWN_ERROR=true
FORCE_INSTALL_ANYWAY=true
```

任何未知错误都按 HARD_STOP 处理。

原因：通用“继续”会把真正的软件缺陷、身份冲突、安全检查失败和不可逆状态异常一起绕过，无法形成可靠的量产证据。

## 4. 放行结果语义

标准全绿设备：

```text
DEVICE_ACCEPTANCE=PASS
```

发生过人工放行但最终端到端验收通过：

```text
DEVICE_ACCEPTANCE=PASS_WITH_OVERRIDE
```

不得把 PASS_WITH_OVERRIDE 重写成普通 PASS。

至少记录：

- CHECK_ID；
- 检查严重级别；
- 预期值；
- 实际值；
- 允许放行的固定原因/政策版本；
- 操作员明确选择继续；
- source head；
- exact artifact identity/digest；
- 设备公开安全身份绑定；
- 时间；
- 最终端到端验收结果。

私有 locator、密码、私钥、原始秘密和敏感凭据不得进入公共 GitHub。

## 5. 容量检查采用双阈值

容量类检查优先采用：

```text
RECOMMENDED_RESERVE_THRESHOLD
ABSOLUTE_MINIMUM_THRESHOLD
```

语义：

- >= 推荐安全线：PASS；
- >= 绝对最低值但 < 推荐安全线：OVERRIDABLE；
- < 绝对最低值：HARD_STOP。

绝对最低值必须来自当前 exact artifact / image 运输与加载模型动态计算，不能使用随意固定常数代替真实峰值需求。

现有 5 GiB 规则在 F3 继续作为严格门槛，不因本设计自动下调。

## 6. F5 实现要求

F5 收敛最终量产安装器时，需要：

1. 为每个检查定义稳定 CHECK_ID；
2. 在源码中静态声明 severity 与 override policy；
3. 建立允许放行的白名单；
4. 未知 CHECK_ID 或未知异常 fail-closed；
5. UI/CLI 必须展示失败原因、实际值、建议值和继续风险；
6. 人工放行必须要求明确动作，不能由默认超时自动接受；
7. 生成可追溯 PASS_WITH_OVERRIDE 证据；
8. 最终端到端验收仍必须执行；
9. 某项检查被放行不等于后续相关检查也自动放行；
10. 安全、身份、完整性、一次性授权和不可逆状态边界永久禁止绕过。

## 7. 与当前 F3 的关系

本设计只冻结未来 F5 的量产操作模型。

当前真实 F3 继续使用现有严格合同：

```text
F3_OVERRIDE_FRAMEWORK_ACTIVE=false
F3_STRICT_CHECKS=true
F3_UNKNOWN_FAILURE=STOP
F3_PRODUCTION_SERVICE_START=false
```

F3 仍用于证明严格路径在真实 fresh Armbian T1 上完整可行；不得为了推进本轮现场部署而临时降低检查标准。

## 8. 设计结论

最终产品目标是：

> 后台检查继续严格，前台操作显著简化；只有经过工程验证并在源码中明确白名单化的环境偏差才允许人工放行。

这既避免“检查过严导致无必要阻塞”，也避免“操作员一键忽略真正故障”。
