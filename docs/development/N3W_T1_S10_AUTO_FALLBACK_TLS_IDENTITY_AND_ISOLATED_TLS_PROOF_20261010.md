# T1 全新部署 S10：auto 安全回退身份绑定与隔离 TLS 校验

日期：2026-10-10。目标：不实施完整 B2 稳定主机名开发；保留既有 PR #522 auto Broker 地址恢复机制，在清洁 T1 上重建新 Broker 的 TLS 根证书和服务端身份。

## Authority

- PR #541：T1 保留 Armbian 的清洁部署，S3–S9 现场均已只读/定向完成，Broker/Manager/HA 还未重新运行。
- PR #522：Draft 未合并。已开发并实板证明旧地址失效→Manager discovery→RAM-only Broker retarget→MQTT 恢复→Broker-to-Manager ingress；正式 clean-product Gate F 仍 PENDING，不能当作生产完成。
- 本阶段不改 PR #522 任何固件代码，也不在 PR #541 复制同名新回退状态机。

## 经过源码核对的地址和 TLS 关系

1. 未配对设备寻找 Manager：`GH_N3W_PAIRING_ADVERTISED_HOST=auto`；这个字段不是 Broker 新地址缓存。
2. 首次配对时，由实际连接中的 T1 `eth0` 得到当前 Broker IPv4 locator，仅写入 T1 私有运行配置，不能把 DHCP IP 固化进公开源码。
3. 已配对节点通过 PR #522 的 Manager broadcast rediscovery，在 MQTT 持续不可用时寻找 T1 新地址；新候选仅更新 RAM，保留绑定的 CA/TLS 名称、MQTT 用户名/密码、Client ID 及 generation，不覆盖 durable 配对记录。Gate F 实板最终验收仍须完成。
4. Node product `set_broker_address(...)` 与 `set_tls_server_name(...)` 分离；历史 Board B 的 `armbian` TLS 名称曾经在实机恢复测试中通过。
5. Manager `mqtt_service.py` 调用 `tls_set(ca_certs=...)` 后连接 `GH_MQTT_HOST`，不提供单独的 TLS server-name override；建议 `GH_MQTT_HOST=127.0.0.1` 并要求服务端证书带 `IP:127.0.0.1` SAN。
6. 清洁 T1 Broker 新证书冻结候选 SAN：`DNS:armbian`、`DNS:mqtt.greenhouse.local`、`IP:127.0.0.1`；`mqtt.greenhouse.local` 目前不可解析，只作为可选证书别名，不依赖 DNS 作实际连接。Node 连接按当前 IP，TLS name 用 `armbian`；CA 每套新温室系统独立生成，短主机名相同不意味着可跨系统信任。
7. Broker host publication 仍为 **仅一个显式 `0.0.0.0:8883`**，双 Docker 网络及现存 fail-closed guard 均保持。Broker 证书无需包含当前或未来 DHCP LAN IP SAN。
8. 这套 FC4 Broker CA 与 H0/H1 System CA 是不同信任材料；不能把 Broker CA 当作系统身份 CA。旧 CA、旧证书和旧 Dynamic Security 数据已被用户明确放弃，均不得复用。
9. 需后续证明 Manager 实际 Python/paho 连接成功，Node 当前 ESPHome TLS 验证成功，凭据认证/ACL 成功，以及干净产品板 A→B 的真实 T1 地址变更 Gate F。孤立 host TLS 测试不能替代这些物理证据。

## 本轮本机隔离功能测试（非 T1、非 ESP32-C6）

使用临时私有 CA + P-256 服务端密钥、上述 SAN，OpenSSL 生成证书，Python SSL 在 `127.0.0.1` 进行真实 TLS 会话，不使用生产密钥，不修改 T1。

```text
HOST_TLS_CA_DNS_ARMBIAN=PASS
HOST_TLS_CA_DNS_MQTT_GREENHOUSE_LOCAL=PASS
HOST_TLS_CA_IP_LOOPBACK=PASS
HOST_TLS_REJECTS_WRONG_NAME=PASS
HOST_TLS_REAL_LOOPBACK_HANDSHAKES_FOR_NAME_AND_IP=PASS
ISOLATED_TEST_COUNT=5
ISOLATED_TEST_PASS=5
T1_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_TLS_TEST=NOT_YET_EXECUTED
```

这是当前会话本地可复算证据，**不是** GitHub CI 或 ESP32 实板证明。

## S11 下一步执行边界

```text
S10_SOURCE_REVIEW=PASS
S10_ISOLATED_TLS_PROOF=PASS
S11_NEXT_GATE=FRESH_BROKER_PRIVATE_CA_AND_SERVER_CERT_MATERIALIZATION
S11_ALLOW=ONLY_NEW_PRIVATE_TLS_FILES_UNDER_VERIFIED_ABSENT_PRODUCT_ROOT
S11_DOCKER_CONTAINER_CREATE=false
S11_HOST_8883_PUBLICATION=false
S11_FIREWALL_MUTATION=false
S11_MANAGER_MUTATION=false
S11_BOARD_ACCESS=false
S11_KEY_MATERIAL_TO_GITHUB=false
```

T1 下一步仅生成全新受控 CA/证书、校验身份和文件权限，严格检测目标目录不存在且安全 guard/系统服务有效。停在证书材料制作完成；之后仍须使用现行 deployment gate 审核新 Compose、DynSec/Manager/HA 和 ingress runtime acceptance，再单独启动 Broker。执行命令仅在对话中交付，仓库不存放终端 runbook、私钥或私有地址。
