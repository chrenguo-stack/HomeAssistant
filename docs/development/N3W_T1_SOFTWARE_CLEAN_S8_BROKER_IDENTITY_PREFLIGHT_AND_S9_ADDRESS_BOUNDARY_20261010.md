# N3-W T1 S8 清洁部署 Broker 身份预检及 S9 地址边界（2026-10-10）

## S8 用户现场证据

- `S8_READONLY_RESULT=PASS`，远端 SSH return code=0，`T1_MUTATION=false`，`BOARD_ACCESS=false`。
- 宿主机 hostname/FQDN 均为通用短名 `armbian`，解析结果只有 IPv4 loopback，不能证明 LAN 中的 ESP32-C6 可以直接解析此名称。
- `eth0` connected，有一个当前 IPv4 /24 LAN assignment；该地址**不得**进入长期不变的 Broker publication 合同。避免在 GitHub 记录当前私人 LAN IP。
- T1 NTP 同步，ARM64/Linux，Docker 29.7.1，剩余空间约 6.02 GiB。
- 两个精确 Docker network 为空且可查询，当前 Broker ingress guard active/enabled。
- 本机仍有旧 Manager、Mosquitto、Home Assistant 镜像，缓存标签及本机镜像 ID 不能替代正式 source->exact-image 构建与验收；不直接用于新产品。
- 当前没有创建新 Broker、TLS 私钥或业务 state。

## S9 必须分开的两个地址

1. `GH_N3W_PAIRING_ADVERTISED_HOST=auto` 是未配对节点的 Manager UDP discovery 目标地址，根据请求来源做 route-based 发现，**不等于** MQTT Broker 的域名/地址变化处理。
2. 当前 Manager 产品配置默认 `GH_N3W_NODE_BROKER_HOST=mqtt.greenhouse.local` 与 `GH_N3W_NODE_BROKER_TLS_SERVER_NAME=mqtt.greenhouse.local`；Board 产品源确实分别保存 `broker_host`、`broker_tls_server_name`、CA。
3. 当前 T1 现场没有提供 `mqtt.greenhouse.local` 在节点实际网络上的解析证明；`armbian` 本机回环解析也不能替代。
4. Broker 应有唯一 0.0.0.0:8883 TCP publication、受保护的 ingress guard、两条精确网络；Manager host-network 的 loopback TLS 验证必须在现场实际证明。
5. 不把旧历史 Broker TLS cert/SAN/CA 当作新系统 authority；不得将 B1 wildcard publication 修复误记为 B2 稳定 hostname 或 B3 已配对节点 IP 迁移闭环。
6. S9 先进行小范围真实网络解析只读核查，再决定是继续现有 canonical Broker hostname 路线，还是按用户既有 auto 安全回退产品取舍另行冻结 V1 限制。任何 V1 临时地址机制均须显式注明 DHCP 变更影响，不能暗中改变现有产品设计。

## 冻结执行边界

```text
S8_STATUS=PASS
S9_NEXT_ONE_GATE=FRESH_BROKER_CANONICAL_HOST_RESOLUTION_AND_MANAGER_TLS_NAME_GATE
S9_RUNTIME_MUTATION=false
S9_CERT_GENERATION=false
S9_BROKER_START=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
```

终端执行指令直接在对话内提供，不新增 GitHub runbook。GitHub 仅保存脱敏验收、设计及后续正式产品源码/测试材料。
