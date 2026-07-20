# H3/N2 Stage 2B-1 安全传输实现说明

**基线：** `main = 9978853ebbca9d0703930b1a0ee8091b47854852`  
**开发分支：** `feature/h3-n2-stage2b-secure-transport-20260720-v38`  
**状态：** 源码开发中

## 1. 本工作包目标

把 Stage 2A 已签发但尚未允许网络传输的 `CredentialBundle` 放入经过 QR 配对秘密认证的临时安全通道，形成可供后续 mDNS/UDP/HTTP 承载层调用的纯 Python 协议核心。

## 2. 文件范围

- `host/greenhouse-manager/src/greenhouse_manager/pairing_secure_transport.py`
- `host/greenhouse-manager/tests/test_pairing_secure_transport.py`
- `host/greenhouse-manager/pyproject.toml`
- `protocols/pairing/gh-h3-secure-pairing-transport-v1.md`
- 本说明文档

## 3. 实现内容

- X25519 临时密钥交换；
- HKDF-SHA256 方向密钥派生；
- ChaCha20-Poly1305 AEAD；
- 双临时公钥和 nonce 绑定的 QR PoP；
- manager-to-node / node-to-manager 独立密钥；
- 确定性 96-bit nonce 与严格 uint64 sequence；
- canonical AAD；
- 密文认证、方向、session、content type 和重放拒绝；
- 凭据 envelope 幂等缓存；
- 加密 delivery ACK；
- abort / proof-lockout 时调用底层 Stage 2A 回滚；
- 内存 key bytearray 清零；
- 测试中的非生产 node reference。

## 4. 依赖策略

`cryptography` 只加入 `pairing` 和 `dev` optional extra。默认 manager 运行路径和现有 M2/T1 工具不导入本模块，因此本工作包不改变当前生产容器行为，也不升级 Manager 版本号。

实际网络服务接入时，候选镜像必须明确安装 `greenhouse-manager[pairing]`，并通过依赖锁定、SBOM 和 ARM64 构建验证。

## 5. 测试门

- Ruff；
- 新模块 Python compile；
- X25519/AEAD 完整往返；
- 双公钥 PoP 绑定；
- 三次错误证明锁定；
- ciphertext tamper；
- replay；
- direction mismatch；
- 凭据 envelope 幂等；
- ACK 精确合同；
- abort 回滚；
- 全 greenhouse-manager CI；
- Public repository safety CI；
- M0 和 M2 Dynamic Security 回归。

## 6. 安全边界

- 不修改 M401A、T1、Home Assistant、真实 Broker 或节点；
- 不生成或读取生产凭据；
- 不关闭 anonymous MQTT；
- 不把明文 MQTT 密码、PAIR_SECRET、共享秘密或 AEAD key 写入 Git、日志、YAML 或进程参数；
- 测试中的 node reference 不是 ESP32-C6 生产固件；
- 编译和模拟结果不能替代 Stage 2C/2D 实板验收。
