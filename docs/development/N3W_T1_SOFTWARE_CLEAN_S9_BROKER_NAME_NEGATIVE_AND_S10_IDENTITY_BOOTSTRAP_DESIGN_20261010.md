# N3-W T1 清洁部署：S9 Broker 名称解析结果与 S10 证书/连接边界设计（2026-10-10）

## S9 现场取证

用户在 Mac 和 T1 分别进行只读解析验证，原始日志留在私有环境：

- `mqtt.greenhouse.local`：Mac 常规解析无地址；Mac mDNS 返回 `No Such Record`（伴随占位 `0.0.0.0`），**不是可用 IPv4**；T1 `getent` 无地址。
- `armbian.local`：Mac 无肯定的解析结果；T1 同时给出多个 Docker bridge IPv4 及当前 LAN IPv4，因此不是已证明的、适合分发给 ESP32-C6 的唯一稳定节点地址。
- `armbian`：T1 仅回环 IPv4。
- `avahi-daemon`：inactive。
- `S9_T1_READONLY_COMPLETE=true`、`SSH_OR_REMOTE_EXIT_CODE=0`、`T1_MUTATION=false`。
- Broker/Manager/HA 未因此部署或启动，DNS 解析失败不得归因于尚不存在的新 Broker。

```text
S9_PROBE=PASS
S9_CANONICAL_MQTT_HOST_RESOLUTION=FAIL
S9_ARMBIAN_LOCAL_SINGLE_VALID_LAN_ADDRESS=NOT_PROVEN
BROKER_TLS_IDENTITY_NOT_YET_FROZEN=true
BROKER_CONTAINER_STARTED=false
```

## Source 证据

- Manager `runtime/config.py` 默认 `GH_N3W_PAIRING_ADVERTISED_HOST` 与节点 `GH_N3W_NODE_BROKER_HOST`、`GH_N3W_NODE_BROKER_TLS_SERVER_NAME` 是不同字段；节点 Broker 端口为 8883，默认 canonical TLS 名是 `mqtt.greenhouse.local`。
- 节点 `n3w_simple_product_component.cpp` 分别调用 `set_broker_address(broker_state_.broker_host)`、`set_tls_server_name(broker_state_.broker_tls_server_name)`、`set_ca_certificate(...)`；这支持地址与 TLS name 的**源码结构分离**，但**尚未证明 ESPHome 当前 TLS 库在连接 IP literal 时的真实证书主机名验证结果**。
- Manager MQTT `mqtt_service.py` 使用 `tls_set(ca_certs=...)` 后以 `self.settings.mqtt_host` 实际连接；目前没有独立的 Manager MQTT TLS SNI 设置。因此 Manager 以 `127.0.0.1` 连接时，证书必须允许 IPv4 SAN `127.0.0.1` 并通过实际 TLS probe；不得直接以只含 DNS SAN 的证书宣称回环连接有效。
- `GH_N3W_PAIRING_ADVERTISED_HOST=auto` 仅处理未配对节点对 Manager 的动态发现；**不是**已配对设备的 Broker 地址更新机制。
- 原冻结 Broker LAN-IP-independent binding 不依赖当前 DHCP 地址；Broker host publication 仍为 `0.0.0.0:8883`，由现存 ingress guard 覆盖。
- B2 稳定可解析名称和 B3 已配对节点 IP 自动迁移目前均无闭环证据。

## S10 最小方案候选：IP 连接 + 固定 TLS 名称 + 明确人工安全回退

这是**待源码和实机合同复核的设计候选，不是已验证的生产行为**：

1. Broker 新生成私有 CA、server key/cert；计划证书 SAN 至少包含 DNS `mqtt.greenhouse.local` 和 IPv4 `127.0.0.1`；两份 CA authority（系统初始化 CA、Broker 通信 CA）独立建档，不因同名而混用。
2. Manager 在 T1 host namespace 使用 `127.0.0.1:8883` 加 TLS CA 校验，需要实际 IP SAN 证书匹配与权限、网络保护检查。
3. 节点首次配对时可以在候选 V1 方案中把当前 T1 LAN IPv4 放入 **Broker 连接地址**，保留 `broker_tls_server_name=mqtt.greenhouse.local`；但在正式修改 product bundle/Manager 前必须验证当前 ESPHome TLS 严格校验（CA + SAN name），且此 IP 只是可更换连接定位，不是长期安全身份。
4. 用户此前选择不做完整 B2 稳定主机名方案，若 DHCP/IP 变化，已配对节点**不会因此自动恢复 Broker 连接**；必须有有界的人工清除失效通信地址/安全重新配对流程。此处不得自称 B3 已解决，亦不得用放宽 TLS、匿名 MQTT、复用旧密钥方式救急。
5. Manager 的 `GH_N3W_NODE_BROKER_HOST` 如果依赖启动时注入当前 IPv4，IP 改变后也可能过期，恢复流程需要重新获取最新地址且验证 `GH_N3W_PAIRING_ADVERTISED_HOST=auto` 依然正常；不能把当前私人 DHCP IP 固化在源码或仓库。
6. 在源审/host-only isolated TLS 功能测试与 exact Compose deployment gate 通过以前，不生成真实证书、不建立生产 DynSec 状态、不开放 8883、不修改板卡。

## NEXT_ONE_GATE

```text
S9_READONLY_RESULT=PASS
CANONICAL_BROKER_HOSTNAME_LAN_RESOLUTION=NOT_READY
S10=SCOPE_FREEZE_BROKER_TLS_SAN_MANAGER_LOOPBACK_AND_NODE_IP_CONNECT_PROOF
S10_REQUIRED=SOURCE_REVIEW_PLUS_ISOLATED_TLS_TESTS
S10_PRODUCT_NODE_IP_FALLBACK=DESIGN_CANDIDATE_ONLY
B2_STABLE_HOSTNAME=NOT_IMPLEMENTED
B3_PAIRED_NODE_IP_CHANGE=NOT_IMPLEMENTED
T1_MUTATION=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
```

继续采用既有安全入口 guard、双网络和独立 Broker/Manager/HA；所有用户终端执行指令直接给出于对话，GitHub 仅归档设计、源码、测试与脱敏证据。
