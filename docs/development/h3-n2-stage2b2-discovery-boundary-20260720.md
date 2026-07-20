# H3/N2 Stage 2B-2 发现与网络边界实现说明

**基线：** `main = 8820af96cb8d185b8f97d042e38c9cc5a87f6f20`  
**开发分支：** `feature/h3-n2-stage2b2-discovery-boundary-20260720-v39`  
**状态：** 源码与模拟网络验证

## 1. 目标

在 Stage 2A 一次性会话和 Stage 2B-1 AEAD 安全传输之上，实现可独立测试的局域网发现与节点网络端点，同时保持现有 Manager 默认运行路径和生产环境不变。

## 2. 实现范围

### Manager 发现

- `_greenhouse._tcp.local.` mDNS ServiceInfo；
- 严格 mDNS 名称注册，不自动改名；
- mDNS TXT 只发布候选元数据；
- 显式发布 `scheme`、host、port 和 path；
- nonce/request-id 绑定的 UDP 回退；
- 1400 字节 datagram 上限；
- 本地源地址过滤和每 IP 速率限制；
- 候选 TTL、去重和显式多 Manager 选择。

### 配对端点

- 受信任本地 UI 的扫码导入 registry；
- 节点 claim 不传输 `PAIR_SECRET`；
- claim 使用 `HMAC-SHA256(PAIR_SECRET, hardware_id + pairing_id transcript)`；
- 无效 claim 不绑定源 IP、不消费 session、不触发 Stage 2B-1 锁定；
- 首次有效 claim 绑定节点源 IP；
- 终态清除 claim proof 摘要和 registry 映射；
- Stage 2B-1 establish、credentials、ACK、abort、status 路由；
- 精确 JSON 字段校验；
- 16 KiB body、5 秒 socket timeout、30 请求/分钟/IP；
- 16 个并发线程上限；
- 禁止 chunked request；
- no-store、nosniff 和连接关闭响应头；
- 通用错误码，不回显内部异常或秘密。

### 生命周期

- HTTP、UDP、mDNS 原子启动；
- mDNS 启动失败时回滚 HTTP/UDP；
- 关闭过程幂等；
- closed 实例禁止重启。

## 3. 文件范围

- `host/greenhouse-manager/src/greenhouse_manager/pairing_discovery.py`
- `host/greenhouse-manager/src/greenhouse_manager/pairing_endpoint.py`
- `host/greenhouse-manager/src/greenhouse_manager/pairing_network_service.py`
- `host/greenhouse-manager/tests/test_pairing_discovery.py`
- `host/greenhouse-manager/tests/test_pairing_endpoint.py`
- `host/greenhouse-manager/tests/test_pairing_network_service.py`
- `host/greenhouse-manager/pyproject.toml`
- `protocols/pairing/gh-h3-discovery-and-endpoint-v1.md`
- 本说明

## 4. 依赖边界

`zeroconf>=0.150,<1` 只加入 `pairing` 和 `dev` optional extra。默认 Manager 安装、现有入口和版本号仍保持 `0.4.94`。

mDNS 模块采用延迟导入；未安装 `pairing` extra 时，现有 Manager 路径不受影响。正式候选镜像必须明确安装 `greenhouse-manager[pairing]`。

## 5. 安全审计结论

- mDNS/UDP 不是身份认证通道，只提供候选发现；
- UDP nonce 不被描述为认证能力；
- 多 Manager 时不根据 priority 自动选择；
- 配对秘密不进入网络协议；
- claim 不能仅凭公开标识抢占，必须通过 QR 秘密 HMAC；
- 明文 HTTP 仅承载公开元数据和 Stage 2B-1 密文；
- credential request 仍受用户批准和 NODE_ID 双门约束；
- session 终态从网络 registry 移除；
- 非本地源地址拒绝；
- 资源限制防止局域网内简单耗尽攻击；
- 代码未接入生产主程序，不能声明生产开放端口。

## 6. 验证计划

Focused tests 覆盖：

- 严格 query/response 和 nonce 回显；
- UDP 本地真实 socket roundtrip；
- public source、协议不匹配和速率限制；
- 候选 TTL、去重、多 Manager 显式选择；
- mDNS ServiceInfo 字段和注册/注销幂等；
- claim 不泄露秘密、HMAC 验证、错误证明不抢占及首 IP 绑定；
- establish、credentials、ACK、abort、status；
- 非 JSON、未知字段、超大 body、速率限制；
- 真实 loopback HTTP health；
- HTTP/UDP/mDNS 生命周期与失败回滚；
- 全量 greenhouse-manager、M0、M2 和公共仓库安全 CI。

## 7. 未完成范围

- 主程序配置装配与默认关闭开关；
- 容器端口和防火墙策略；
- 本地扫码 UI；
- ESP32-C6 discovery/client 实现；
- session 持久化；
- HTTPS；
- M401A、T1 和真实节点测试。

下一工作包建议为 Stage 2B-3：受控配置装配、默认关闭的 Manager 入口、隔离容器网络验证和部署合同。Stage 2C 再进入 ESP32-C6 固件。
