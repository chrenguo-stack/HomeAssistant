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
13. `discovery/gh-discovery-v1.md`：待冻结 mDNS、UDP 回退、重试和多主机处理；M2.0 pairing Draft 已给出最小发现依赖。
14. `state/gh-path-lease-v1.md`：待冻结直连/中继路径租约、去重和切换滞回。
15. `state/gh-availability-v1.md`：待将 M1 已验证行为整理为独立协议。
16. `transport/gh-radio-frame-v1.md`：待冻结 ESP-NOW 与 LoRa 紧凑帧、认证和序列规则。

## 变更规则

- 已发布的协议字段不得无版本号变更语义。
- 新字段默认必须允许旧端忽略。
- 删除字段或改变单位必须升级主版本。
- 示例报文同时作为自动化协议测试输入。
