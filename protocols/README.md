# 协议冻结区

本目录存放固件、网关、greenhouse-manager 和 Home Assistant 之间的正式接口。

任何跨组件行为必须先在此处定义，再进入编码。

## 协议状态

1. `mqtt/gh-mqtt-v1.md`：已冻结最小遥测、Topic、QoS、Retain 和 ACL 基线，并已由 N1/M1 实现。
2. `pairing/gh-pairing-v1.md`：M2.0 Draft，定义一次性二维码、每机 PoP、安全会话、运行时凭据与生命周期，待设计审查后冻结。
3. `pairing/gh-node-credential-delivery-v1.md`：M2.4g-3 Draft，定义节点双槽写入、候选连接、claim/commit、原子切换、断电恢复和宽限期回退。
4. `discovery/gh-discovery-v1.md`：待冻结 mDNS、UDP 回退、重试和多主机处理；M2.0 pairing Draft 已给出最小发现依赖。
5. `state/gh-path-lease-v1.md`：待冻结直连/中继路径租约、去重和切换滞回。
6. `state/gh-availability-v1.md`：待将 M1 已验证行为整理为独立协议。
7. `transport/gh-radio-frame-v1.md`：待冻结 ESP-NOW 与 LoRa 紧凑帧、认证和序列规则。

## 变更规则

- 已发布的协议字段不得无版本号变更语义。
- 新字段默认必须允许旧端忽略。
- 删除字段或改变单位必须升级主版本。
- 示例报文同时作为自动化协议测试输入。
