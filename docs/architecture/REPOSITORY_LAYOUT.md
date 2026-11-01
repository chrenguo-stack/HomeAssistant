# 仓库架构说明

## 目录结构

```text
.
├── firmware/
│   ├── common/              # 两个硬件版本共享的采集、显示、电源、身份和协议代码
│   ├── wifi_node/           # Wi-Fi 版节点固件
│   ├── wifi_gateway/        # ESP-NOW 单跳中继固件
│   ├── lora_node/           # LoRa 子节点固件
│   ├── lora_gateway/        # LoRa 网关节点固件
│   ├── lora_repeater/       # 后续专用射频中继验证，不属于首版量产范围
│   └── esphome_rc/          # ESPHome 验证期配置与本地 external components
├── host/
│   ├── greenhouse-manager/  # 配对、凭据、入口校验、租约、去重、规范状态和 Discovery
│   ├── greenhouse-init/     # 首次初始化，完成后退出
│   ├── greenhouse-system/   # Home Assistant 轻量配套集成
│   └── simulator/           # 模拟节点、模拟网关和故障注入工具
├── protocols/
│   ├── mqtt/                # 主题、负载、QoS、Retain 和 ACL
│   ├── pairing/             # 首次配对、PoP、TLS 信任引导和凭据生命周期
│   ├── discovery/           # mDNS、UDP 回退和多主机处理
│   ├── transport/           # ESP-NOW、LoRa 紧凑帧和端到端认证
│   └── state/               # availability、路径租约、去重和状态机
├── infra/
│   ├── compose/             # T1 Docker Compose 产品栈
│   ├── mosquitto/           # Broker、Dynamic Security 和 TLS 模板
│   ├── backup/              # 备份与恢复
│   └── ota/                 # manifest、发布、回滚和版本策略
├── hardware/
│   ├── wifi/                # Wi-Fi 版硬件资料
│   ├── lora/                # LoRa 版硬件资料
│   └── shared/              # 公共 GPIO、传感器、LCD 和电源资料
├── tests/
│   ├── unit/
│   ├── protocol/
│   ├── integration/
│   ├── hardware/
│   └── field/
├── docs/
│   ├── architecture/
│   ├── adr/                 # Architecture Decision Records
│   ├── roadmap/
│   └── handover/
└── tools/
```

## 依赖方向

```text
protocols  ← firmware
protocols  ← host
protocols  ← tests

firmware/common ← wifi_node / wifi_gateway / lora_node / lora_gateway
host/greenhouse-manager ← greenhouse-system / greenhouse-init
```

禁止 `protocols/` 依赖具体固件或主机实现。

## 产品边界

- Wi-Fi 版使用 Wi-Fi 直连，弱覆盖时允许 ESP-NOW 单跳到中继节点。
- LoRa 版使用 LoRa 子节点到 LoRa 网关，网关通过 Wi-Fi 接入主机。
- 普通 LoRa 子节点不转发其他子节点。
- 专用 LoRa 射频中继仅作为后续独立验证目标。
- 两个 SKU 共享 NODE_ID、配对、TLS、MQTT 和 Home Assistant 数据模型。
