# H3/N2 Stage 2 功能追踪与缺口审计

**审计基线：** `a965f1346ab95224aeb71283a28018da532bc352`  
**更新时间：** 2026-07-20

| 能力 | 当前状态 | 已有实现 | 下一动作 |
|---|---|---|---|
| 配对 Hello 严格 schema | 已完成 | `gh.pair.hello/1` JSON Schema | 保持兼容 |
| Pending 注册持久化 | 已完成 | `RegistrationRegistry` SQLite | 增加配对服务协调 |
| Pairing ID 重放拒绝 | 已完成 | pairing ID、epoch、过期状态 | 纳入端到端测试 |
| 显式用户批准 | 已完成 | `approve` 只记录批准，不发凭据 | 保留双门 |
| Repair 授权 | 已完成 | 一次显式 re-pair 窗口 | 后续接 UI |
| NODE_ID 唯一性 | 已完成 | SQLite 唯一约束 | 后续迁移合同 |
| 节点最小 MQTT ACL | 已完成 | `build_node_provisioning_plan` | 复用 |
| DynSec 事务和回滚 | 已完成并实机验收 | `DynsecProvisioner` | 复用 |
| 一次性配对会话 | 本工作包实现 | 内存状态机、超时、单次消费 | 后续持久化策略 |
| PoP 所有权证明 | 本工作包实现合同核心 | HMAC-SHA256 transcript | 后续固件与端点接入 |
| 错误次数限制 | 本工作包实现 | 三次默认锁定 | 故障矩阵 |
| 凭据签发双门 | 本工作包实现 | proof verified + approved | 后续加密交付 |
| 凭据交付 ACK | 本工作包实现核心 | issued/consumed 状态 | 后续网络 ACK |
| 未确认凭据回滚 | 本工作包实现核心 | abort/expire deprovision | 隔离 Broker 测试 |
| mDNS 发现 | 缺失 | 仅路线定义 | Stage 2B |
| UDP nonce 回退 | 缺失 | 仅路线定义 | Stage 2B |
| 多主机选择 | 缺失 | 仅产品要求 | Stage 2B/N1 |
| ECDH/X25519 | 缺失 | 无正式依赖 | Stage 2B |
| AEAD 临时通道 | 缺失 | 无正式实现 | Stage 2B |
| 配对端点 | 缺失 | 无 HTTP/UDP 服务 | Stage 2B |
| CA 与 TLS 主机名交付 | 部分 | bundle 合同字段 | Stage 2B 加密封装 |
| 节点安全存储 | 缺失 | MQTT boot-profile 仅候选能力 | Stage 2C |
| LCD 配对状态机 | 缺失 | 第五页需求已冻结 | Stage 2C |
| 正式 register/ack | 缺失 | MQTT topic 基础存在 | Stage 2C |
| 自动进入 HA | 部分 | manager Discovery 已有 | Stage 2D |
| 撤销 | 部分 | DynSec deprovision 有基础 | Stage 2E |
| 恢复出厂 | 缺失 | 产品需求 | Stage 2E |
| 主板迁移 | 缺失 | NODE_ID 持久映射基础 | Stage 2E |
| 主机备份恢复信任 | 缺失 | 路线已定义 | S1 |

## 结论

当前最短关键路径不是 LoRa 或 ESP-NOW，而是完成 H3/N2 的安全绑定和身份生命周期闭环。Stage 2A 先建立可测试的主机端协议核心；实际网络发现、加密传输和固件接入按后续独立工作包推进。
