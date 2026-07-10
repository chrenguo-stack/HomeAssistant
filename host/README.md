# 主机端工作区

## greenhouse-manager

唯一规范状态和 MQTT Discovery 发布者，负责：

- manager 自动发现响应；
- 节点配对和 NODE_ID 分配；
- Mosquitto Dynamic Security 凭据与 ACL；
- ingress 校验；
- BOOT_ID + SEQ 去重；
- Wi-Fi、ESP-NOW、LoRa 路径租约；
- availability 和诊断状态；
- MQTT Discovery 发布与恢复；
- 节点撤销、迁移和凭据轮换。

## greenhouse-init

只在首次初始化或明确维护操作时运行，负责生成 SYSTEM_ID、CA、管理凭据和初始配置，完成后退出。

## greenhouse-system

Home Assistant 轻量配套集成，只负责配置、注册确认、修复提示、仪表盘资源和诊断，不接管正式环境传感器实体。

## simulator

在真实固件接入前用于验证 MQTT 协议、Discovery、路径切换、失联、重放、重复和乱序场景。
