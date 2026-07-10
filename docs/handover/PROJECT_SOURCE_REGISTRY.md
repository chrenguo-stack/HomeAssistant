# 项目资料来源登记表

- 建立日期：2026-07-10
- 用途：记录对话中收到的固件、硬件和设计资料，避免历史版本被误当成当前生产基线。
- 当前架构基线：V0.5 双产品线与接口冻结版。

## 判定等级

- **现行基线**：后续代码可以直接以此为准。
- **候选基线**：内容有用，但仍需补齐依赖、编译或实板验证。
- **历史参考**：只用于提取算法、显示布局或故障经验，不得直接作为当前硬件固件烧录。
- **硬件证据**：用于核对原理图、PCB、BOM、网络和引脚，不自动代表设计已通过审核。

## 2026-07-10 收到的资料

| 原文件 | SHA-256 | 分类 | 结论 |
|---|---|---|---|
| `14_7_1.yaml` | `882584cb42fef418bfc6abc3519ce75e376fa47c9be856f6f207c97db2599ccb` | 历史参考 | 旧 14.x MQTT/ESP-NOW 产品化试验线。使用旧板级引脚和节点直接发布 MQTT Discovery 的架构，不符合 V0.5 的 manager 规范状态模型。 |
| `14_8_0.yml` | `9de0c66b05dcff13329fd298528b910b7e4b5e9b81c1ef1ffcbd3afb5b72b1f2` | 历史参考 | 在 14.7.1 基础上合并 ADC 中值滤波与共享 availability 修复。可复用低电保护、LCD、HTTP Pull OTA、ESP-NOW 帧和诊断思路，但不得直接用于当前 WROOM-1 PCB。 |
| `15_1_2_rs485_modbus_echo_filter.yml` | `dd9c3e5b3a683ac71f7508daf732096e13160eb762529051271c55496f6b7a71` | 候选基线 | ESP32-C6-WROOM-1 的 RS485 专项测试配置；GPIO15 供电、GPIO21 TX、GPIO17 RX 与当前硬件方向一致。缺少 `my_components/echo_filtered_modbus` 完整源码，暂时不能独立编译。 |
| `PCB设计.zip` | `99ccd3011af79ae34c2b15674e4fdfb8ea1b607e1bb275cd03883d4d0f85475d` | 硬件证据 | 2026-07-09 导出的当前整板资料包，包含网表、双层 PCB 图片、原理图 PDF 和 Gerber。用于后续 GPIO、器件连接和 PCB 审核。 |

## 14.x 文件的已知外部依赖

两个 14.x 文件均引用以下未随本次上传提供的文件：

```text
src/custom_includes.h
src/qrcodegen.h
src/qrcodegen.c
fonts/fusion-pixel-10px-monospaced-zh_hans.bdf
```

并使用：

```yaml
mqtt_password: !secret mqtt_password
```

仓库只能保存 `secrets.example.yaml`，不得提交真实密码。

## 15.1.2 文件的已知外部依赖

```text
my_components/
└── echo_filtered_modbus/
    ├── __init__.py
    ├── echo_filtered_modbus.h
    └── echo_filtered_modbus.cpp
```

在上述源码补齐前，该 YAML 只作为 RS485 设计与测试记录。

## 当前权威性顺序

出现冲突时按以下顺序处理：

1. 已接受的 ADR 和 `protocols/` 冻结协议；
2. V0.5 路线及当前已确认 GPIO 映射；
3. 当前 PCB 网表和经实板验证的结果；
4. WROOM-1 专项测试固件；
5. 14.x 历史固件；
6. 早期 XIAO ESP32-C6 资料。

## 保存策略

- 文本源码在依赖齐全并完成脱敏后导入 `firmware/esphome_rc/`。
- PCB、Gerber、PDF 和图片优先保留原始导出包与 SHA-256；未进入当前开发路径的大型二进制文件不重复提交。
- 每次收到新资料时更新本表，标明来源、版本、硬件对象、依赖和验证状态。
