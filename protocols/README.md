# 协议冻结区

本目录存放固件、网关、greenhouse-manager 和 Home Assistant 之间的正式接口。

任何跨组件行为必须先在此处定义，再进入编码。

## 协议状态

1. `mqtt/gh-mqtt-v1.md`：已冻结最小遥测、Topic、QoS、Retain 和 ACL 基线，并已由 N1/M1 实现。
2. `pairing/gh-pairing-v1.md`：M2.0 Draft，定义一次性二维码、每机 PoP、安全会话、运行时凭据与生命周期，待设计审查后冻结。
3. `pairing/gh-node-credential-delivery-v1.md`：M2.4g-3 Draft，定义节点双槽写入、候选连接、claim/commit、原子切换、断电恢复和宽限期回退。
4. `pairing/gh-t1-homeassistant-mqtt-reconfigure-handoff-v1.md`：M2.4g-4 Draft，定义官方 MQTT 重配置交接、即时回退材料、UI 操作边界和后置校验。
5. `pairing/gh-t1-broker-identity-activation-handoff-v1.md`：M2.4g-5a Draft，定义保持匿名兼容的 Broker 身份激活交接、精确候选演练、fresh rollback 与禁用的 live apply 边界。
6. `pairing/gh-t1-broker-identity-preactivation-and-postaudit-v1.md`：M2.4g-5b Draft，定义真实 Broker 激活前的禁用门、指纹重绑定及激活后的只读身份/匿名兼容审计。
7. `pairing/gh-t1-broker-identity-activation-authorization-v1.md`：M2.4g-5c Draft，定义短时、单次、全指纹绑定的操作员授权材料；授权模块自身仍禁止执行 live apply。
8. `pairing/gh-t1-broker-identity-activation-transaction-v1.md`：M2.4g-5d Draft，定义默认禁用的授权 claim、私有事务日志、强制 postactivation 与 rollback 状态机；生产 executor 尚未接入。
9. `pairing/gh-t1-broker-identity-isolated-transaction-v1.md`：M2.4g-5e Draft，定义仅在 fresh rollback 临时快照和 `--network none` 候选上运行的 mutation、postactivation、rollback 适配器与完整故障注入矩阵；仍无真实 T1 写入口。
10. `pairing/gh-t1-broker-identity-production-executor-contract-v1.md`：M2.4g-5f Draft，定义生产 executor 的精确输入绑定、命令 allowlist、原子写入、单服务重启、强制回退、官方 Home Assistant UI 边界与节点未验证阻塞条件；仍不提供 executor 或 live apply。
11. `pairing/gh-t1-broker-identity-live-mount-gate-v1.md`：M2.4g-5g Draft，定义真实 Mosquitto 容器、镜像、Compose 来源、config/data bind mount、基线配置与 fresh rollback 的只读绑定门；仍不安装 executor、不消费授权、不修改 T1。
12. `pairing/gh-t1-broker-identity-production-adapter-skeleton-v1.md`：M2.4g-5h Draft，定义 mutation、postactivation、rollback 三个生产适配器的不可调用骨架；全部写入、Docker 变更、授权 claim 与 live apply 能力保持不存在。
13. `pairing/gh-t1-broker-identity-host-replica-adapters-v1.md`：M2.4g-5i Draft，定义仅在系统临时目录标记副本上运行的原子文件事务、注入式 Broker 驱动、强制回退与故障注入；不允许真实 T1 目标或 Docker 命令。
14. `pairing/gh-t1-broker-identity-host-replica-fault-matrix-v1.md`：M2.4g-5j Draft，定义每个故障阶段独立临时副本、内存 Broker 驱动、完整回退、回退失败显式报告和模板不可变验证。
15. `pairing/gh-t1-broker-identity-production-driver-contract-v1.md`：M2.4g-5k Draft，冻结生产 Broker driver 的最小 Docker 命令、进程内 MQTT 控制、原子文件事务和默认禁用边界；仍不安装 driver 或执行 live apply。
16. `pairing/gh-t1-broker-identity-runtime-binding-manifest-v1.md`：M2.4g-5l Draft，定义真实 T1 容器身份、Compose 与 bind-mount 路径的 mode-0600 私有绑定材料；生成过程只读运行时并与服务目录隔离。
17. `pairing/gh-t1-broker-identity-production-driver-preflight-v1.md`：M2.4g-5m Draft，重新验证 driver、executor、私有运行时绑定、live mount gate 与 preactivation gate；通过后仍保持 production execution 禁用。
18. `pairing/gh-t1-broker-identity-activation-readiness-bundle-v1.md`：M2.4g-5n Draft，将 production preflight、运行时绑定与 Home Assistant 目标冻结为私有、不可执行、无密钥的操作员决策材料。
19. `pairing/gh-t1-broker-identity-activation-readiness-authorization-v1.md`：M2.4g-5o Draft，定义与 readiness bundle 全指纹绑定的短时、单次操作员授权；仍不 claim 授权或启用 live apply。
20. `pairing/gh-t1-broker-identity-activation-readiness-transaction-plan-v1.md`：M2.4g-5p Draft，将有效授权与 readiness bundle 再绑定为不可执行的私有事务计划，冻结未来 claim、journal、postactivation 与 rollback 顺序。
21. `pairing/gh-t1-broker-identity-production-transaction-adapter-contract-v1.md`：M2.4g-5q Draft，冻结生产事务 adapter 清单、阶段顺序、Docker allowlist、原子文件事务、进程内 MQTT 与强制回退合同；仍不安装 adapter 或提供 live apply。
22. `pairing/gh-t1-broker-identity-activation-decision-packet-v1.md`：M2.4g-5r Draft，以单个只读流程刷新真实 T1 的全部易漂移绑定并输出 readiness bundle 与精确授权确认字符串；不会创建授权或修改服务。
23. `pairing/gh-t1-broker-identity-production-transaction-adapters-v1.md`：M2.4g-5s Draft，实现严格绑定的宿主机 config/data 快照、原子变更与完整回退 adapter；尚无 live CLI、授权 claim 或默认生产 driver。
24. `pairing/gh-t1-broker-identity-production-broker-driver-v1.md`：M2.4g-5t Draft，实现仅允许 inspect/restart Mosquitto 的运行时控制和进程内 paho-mqtt 身份生命周期检查；仍无 CLI、授权 claim 或 live apply。
25. `pairing/gh-t1-broker-identity-production-activation-orchestrator-v1.md`：M2.4g-5u Draft，将短时授权、事务计划、生产 adapters 与 Broker driver 编排为原子 claim、私有 journal、强制 postactivation 和 rollback 状态机；默认禁用且无 CLI。
26. `pairing/gh-t1-broker-identity-production-activation-fault-matrix-v1.md`：M2.4g-5v Draft，覆盖快照前失败、二次验证失败、claim 冲突、授权重放、绑定漂移和 rollback 终止语义，全部使用临时材料和注入式 adapters。
27. `pairing/gh-t1-broker-identity-activation-execution-preparation-packet-v1.md`：M2.4g-5w Draft，使用新鲜 bundle 确认创建短时授权、事务计划、adapter contract 与最终执行请求；不 claim 授权、不重启服务、不修改 T1。
28. `pairing/gh-t1-broker-identity-production-activation-packet-v1.md`：M2.4g-5x Draft，提供双重显式确认、原子 claim、强制 postactivation 与 rollback 的唯一真实 Broker 激活命令行入口；仍不重配置 Home Assistant、不下发节点凭据、不关闭匿名。
29. `pairing/gh-t1-homeassistant-mqtt-postactivation-handoff-v1.md`：M2.4g-6a Draft，将已提交 Broker 事务、Broker 当前只读审计、Home Assistant 官方重配置 handoff、保存 postcheck 与实时 postcheck 绑定为私有交接包；仅允许进入 manager 身份迁移准备，继续禁止 apply、节点凭据下发和匿名关闭。
30. `pairing/gh-t1-manager-identity-migration-preparation-v1.md`：M2.4g-6b Draft，绑定 6a 交接、inactive Stage、manager 当前容器/Compose 基线与独立凭据材料，生成私有且不可执行的 manager 迁移准备包；只允许进入后续一次性授权设计。
31. `pairing/gh-t1-manager-identity-migration-authorization-v1.md`：M2.4g-6c Draft，定义与 6b 准备包和新鲜 manager/Compose 状态全绑定的短时、单次操作员授权；授权自身不 claim、不执行、不重启服务。
32. `pairing/gh-t1-manager-identity-migration-host-replica-v1.md`：M2.4g-6d Draft，定义仅在系统临时目录标记副本和注入式 manager driver 上运行的原子凭据/Compose overlay 事务、身份/订阅/发布验证、完整回退和故障注入矩阵；不允许真实 T1 目标。
33. `pairing/gh-t1-manager-identity-production-transaction-adapter-contract-v1.md`：M2.4g-6e Draft，冻结 manager 密码、认证环境和 Compose overlay 原子写入、manager-only recreate、postactivation 与 rollback 的生产 adapter 契约；默认不可调用。
34. `pairing/gh-t1-manager-identity-production-driver-contract-v1.md`：M2.4g-6f Draft，冻结 manager 生产 driver 的 14 个方法、命令 allowlist、验证、journal 与强制回退边界；driver 尚未安装。
35. `pairing/gh-t1-manager-identity-production-driver-replica-fault-matrix-v1.md`：M2.4g-6g Draft，在系统临时副本上覆盖 manager driver 全方法、成功路径、写入前后故障和回退失败终止语义。
36. `pairing/gh-t1-manager-identity-live-runtime-gate-v1.md`：M2.4g-6h Draft，以只读 `docker inspect greenhouse-manager` 绑定真实容器、Compose、mount、安全配置和 inactive secret target。
37. `pairing/gh-t1-manager-identity-execution-preparation-v1.md`：M2.4g-6i Draft，捕获并验证 manager-only 新鲜回滚包，重跑 runtime gate 检测漂移；不创建授权或执行迁移。
38. `pairing/gh-t1-manager-identity-execution-authorization-v1.md`：M2.4g-6j Draft，定义与 6i、6f、6e、runtime、live binding 和 preparation 全绑定的短时单次授权 request/create/verify 流程。
39. `pairing/gh-t1-manager-identity-execution-transaction-gate-v1.md`：M2.4g-6k Draft，验证仍新鲜的授权与回滚包、重跑真实 runtime gate，并生成第二次精确执行确认；自身不 claim 或 apply。
40. `pairing/gh-t1-manager-identity-production-orchestrator-v1.md`：M2.4g-6l Draft，定义 6k 绑定、第二次确认、原子授权 claim、私有 journal、manager-only mutation、postactivation 和强制 rollback 的库级生产编排器；真实 adapters 和 CLI 仍未安装。
41. `pairing/gh-t1-manager-identity-production-host-adapters-v1.md`：M2.4g-6m Draft，定义真实主机路径绑定、fresh rollback snapshot、三类原子写入、manager-only Compose 命令、运行时探针和完整回滚；仍无 execute CLI 或真实 apply。
42. `pairing/gh-t1-manager-identity-production-runtime-probe-v1.md`：M2.4g-6n Draft，定义被动真实遥测、认证环境与只读 mount、稳定 MQTT socket、绑定 Docker JSON log、Discovery 身份连续性及 6l/6m integration factory；仍无 execute CLI 或真实 apply。
43. `pairing/gh-t1-manager-identity-production-execution-packet-v1.md`：M2.4g-6o Draft，定义双 enable flag、第二次精确确认、三容器只读基线、事务内 protected-service guard 和唯一 manager production execute CLI；代码合并后仍需新的两次真实操作员确认。
44. `pairing/gh-t1-manager-identity-stdlib-mqtt-preflight-v1.md`：M2.4g-6p Draft，定义宿主机无 paho 依赖的标准库 retained reader、只读 preflight、禁止 PUBLISH 与短时材料生成前置门。
45. `pairing/gh-t1-manager-identity-failure-diagnostic-v1.md`：M2.4g-6q Draft，定义主迁移与回滚的 allowlisted 子阶段、固定错误码、无异常 message 的私有诊断材料及 legacy transaction 只读兼容。
46. `pairing/gh-t1-manager-runtime-secret-ownership-gate-v1.md`：M2.4g-6r Draft，绑定容器、镜像与隔离候选的非 root 运行 UID/GID；活动密码保持 0600 且归属运行用户，并在授权前完成 network-none 配置/可读性探针。
47. `pairing/gh-t1-manager-identity-postrollback-audit-v1.md`：M2.4g-6t Draft，冻结回滚后只读闭环、认证变量 present/nonempty 基线、exact target 清理和缺基线不误报 manual recovery 的语义。
48. `pairing/gh-t1-manager-identity-legacy-review-bridge-v1.md`：M2.4g-6u Draft，仅在旧回滚缺失两类历史基线、全部确定性安全检查通过且操作员明确接受时记录人工复核；不伪造 audit pass、不豁免新证据链基线、不创建授权或执行生产变更。
49. `pairing/gh-t1-manager-identity-fresh-chain-preparation-v1.md`：M2.4g-6v Draft，在精确仓库提交和 Manager 版本上重新发现并验证 legacy review bridge、postactivation handoff、inactive Stage 与私有输出根；默认输出根必须是唯一的 bridge-workspace sibling，显式路径也必须属于已验证候选；只允许生成新的 bridge-bound preparation，不创建授权或生产执行包。
50. `discovery/gh-discovery-v1.md`：待冻结 mDNS、UDP 回退、重试和多主机处理；M2.0 pairing Draft 已给出最小发现依赖。
51. `state/gh-path-lease-v1.md`：待冻结直连/中继路径租约、去重和切换滞回。
52. `state/gh-availability-v1.md`：待将 M1 已验证行为整理为独立协议。
53. `transport/gh-radio-frame-v1.md`：待冻结 ESP-NOW 与 LoRa 紧凑帧、认证和序列规则。

## 变更规则

- 已发布的协议字段不得无版本号变更语义。
- 新字段默认必须允许旧端忽略。
- 删除字段或改变单位必须升级主版本。
- 示例报文同时作为自动化协议测试输入。
