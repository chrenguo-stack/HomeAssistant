# 协议冻结区

本目录存放固件、网关、greenhouse-manager 和 Home Assistant 之间的正式接口。

任何跨组件行为必须先在此处定义，再进入编码。

## 待冻结协议

1. `mqtt/gh-mqtt-v1.md`：主题、JSON 负载、QoS、Retain 和 ACL。
2. `pairing/gh-pairing-v1.md`：一次性二维码、PoP、安全会话和长期凭据。
3. `discovery/gh-discovery-v1.md`：mDNS、UDP 回退、重试和多主机处理。
4. `state/gh-path-lease-v1.md`：直连/中继路径租约、去重和切换滞回。
5. `state/gh-availability-v1.md`：节点、传输、数据新鲜度和传感器健康状态。
6. `transport/gh-radio-frame-v1.md`：ESP-NOW 与 LoRa 紧凑帧、认证和序列规则。

## 变更规则

- 已发布的协议字段不得无版本号变更语义。
- 新字段默认必须允许旧端忽略。
- 删除字段或改变单位必须升级主版本。
- 示例报文同时作为自动化协议测试输入。
