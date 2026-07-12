# T1 Broker 身份生产激活故障矩阵 V1

状态：M2.4g-5v Draft

## 1. 目的

本协议冻结生产激活编排器在授权、快照、claim、mutation、postactivation 和 rollback 各阶段的故障行为。矩阵只使用临时私有材料和注入式 adapters，不连接真实 T1。

## 2. 必测场景

1. adapter `prepare` 失败：不得 claim 授权，不得进入 mutation；
2. 快照完成后的第二次授权验证失败：不得 claim 授权，不得进入 mutation；
3. claim 目标已存在：原授权名必须保留，不得进入 mutation；
4. mutation 失败：授权保持 consumed，必须执行完整 rollback；
5. postactivation 失败：必须执行完整 rollback；
6. rollback 失败：必须明确报告终止故障；
7. 成功事务后的授权重放：必须因原授权名不存在或 consumed 状态而拒绝；
8. readiness、plan、adapter、executor 或 runtime 任一绑定漂移：必须在创建事务 workspace 前拒绝。

## 3. 不变量

- 授权只有在完整快照和第二次验证通过后才能 claim；
- claim 使用同文件系统 hardlink + source unlink；
- claimed authorization 必须原子标记为 consumed；
- mutation 开始后，任何失败都不能恢复授权为未消费；
- rollback 成功和 rollback 失败必须分别写入终止 journal phase；
- 所有测试不得调用 Docker、真实 MQTT 或宿主机服务路径。

## 4. 当前结论

故障矩阵通过只证明编排状态机和 fail-closed 语义成立，不等同于真实 T1 激活验证。正式执行仍要求新鲜 runtime binding、短时授权和独立执行确认。
