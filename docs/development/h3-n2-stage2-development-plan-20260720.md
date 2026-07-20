# H3/N2 Stage 2 后续开发计划与执行基线

**状态：** 已批准并进入执行  
**基线日期：** 2026-07-20  
**仓库基线：** `main = a965f1346ab95224aeb71283a28018da532bc352`  
**M401A 验收基线：** `26e53e4266ef2a4a073aa5e95f470be9ca3e03d9`

## 1. 已完成边界

- H3/N2 Stage 1C 已通过 M401A 无 runtime overlay 验收；
- Stage 1B 已正式关闭；
- Stage 1C 四个正式路径已通过 PR #152 squash 合并进入 `main`；
- Dynamic Security 最小权限、响应关联、回滚和隔离验证基础已稳定；
- 现场不可变验收候选与仓库后续开发基线分离保存。

上述结论不等于 H3/N2 全部完成。真实节点的发现、一次性绑定、PoP、临时安全通道、凭据交付、注册确认、撤销、恢复出厂和身份迁移仍需开发。

## 2. 执行顺序

1. Stage 2A：能力缺口审计和主机配对服务核心；
2. Stage 2B：发现服务、PoP、临时安全通道和凭据交付；
3. Stage 2C：ESP32-C6 N1/N2 固件接入；
4. Stage 2D：单节点端到端实机验收；
5. Stage 2E：异常、撤销、迁移和恢复矩阵；
6. Wi-Fi 直连小规模试点；
7. N3-L LoRa 星形单跳；
8. N3-W ESP-NOW 单跳补盲；
9. S1 黄金镜像、首启初始化、OTA、备份恢复和老化；
10. N4-L 仅在真实现场证明有必要时评估。

## 3. Stage 2A 当前工作包

本工作包限定为：

- 归档功能追踪矩阵；
- 建立一次性配对会话状态机；
- 使用 32 字节配对秘密和 HMAC-SHA256 建立 PoP 合同；
- 限定次数、超时、重放拒绝和内存秘密清理；
- 明确“持久注册批准”与“Broker 凭据签发”的双门；
- 复用已验收的 `DynsecProvisioner` 和节点最小 ACL；
- 提供凭据交付确认和未确认回滚；
- 添加 focused tests 和协议文档。

暂不声明完成：

- mDNS/UDP 实际发现服务；
- X25519/ECDH；
- AEAD 加密传输；
- 会话秘密加密持久化；
- HTTP/UDP 配对端点；
- ESP32-C6 固件接入；
- 真实节点或生产主机验收。

## 4. 阶段门

Stage 2A 代码门：

- Ruff 通过；
- pairing service focused pytest 通过；
- registration 与 dynsec 相关测试通过；
- 全 greenhouse-manager CI 通过；
- Public repository safety CI 通过；
- M2 Dynamic Security CI 通过；
- 不生成、提交或打印生产凭据；
- 不修改 M401A、T1、Home Assistant 或现场 Broker。

Stage 2A 合并后再进入 Stage 2B，不要求本轮实机测试。
