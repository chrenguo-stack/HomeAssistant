# T1 S11 新 Broker TLS 实测验收与 S12 镜像/配置准备（2026-10-10）

## S11 现场执行（用户提供的完整终端结果）

```text
S11_PRECHECK=PASS
NEW_TLS_ROOT_CREATED=True
BROKER_CA_CERT_SHA256=ce1fa7cbe9918f2a926fbfa91747c34d71543c519fe38795082b5b1f938b0322
BROKER_SERVER_CERT_SHA256=87c2783264bb29dad9a457ba5c80d21809f041309fef0d9f85b551cfe2db5c88
TLS_DNS_ARMBIAN=PASS
TLS_DNS_MQTT_GREENHOUSE_LOCAL=PASS
TLS_IP_LOOPBACK=PASS
TLS_WRONG_NAME_REJECTED=True
BROKER_CA_KEY_MODE=0600_ROOT
BROKER_SERVER_KEY_MODE=0600_UID1883
BROKER_CONTAINER_STARTED=False
HOST_8883_PUBLICATION=False
INGRESS_GUARD_PRESERVED=True
BOARD_ACCESS=False
S11_RESULT=PASS
SSH_OR_REMOTE_EXIT_CODE=0
```

以上为用户现场输出，不是仓库 CI。不包含 CA 私钥、服务器私钥或 MQTT 凭据。新生成 Broker CA 与 TLS server cert 的 SHA-256 指纹为后续精确绑定依据；不继承旧 CA/旧证书指纹。

## S12 现行产品源码核对

1. 新 Broker 的 `docker-compose` 必须符合 `tools/n3w_pairing_deployment_gate.py` /2 合同：唯一显式 IPv4 wildcard TCP/8883，项目 `n3wfc4`，Broker 精确连接 `n3wfc4-private`、`n3wfc4-services`，Broker restart=no；Manager host-network、无端口映射、`GH_N3W_PAIRING_ADVERTISED_HOST=auto`。真实 manager loopback TLS 验收后置。
2. 历史运行的是 Mosquitto 2.1.2；PR #480 的动态安全插件从 `plugin` 更新为 `global_plugin /usr/lib/mosquitto_dynamic_security.so`，去除旧 `per_listener_settings false`，保留 `allow_anonymous false`。实验 `infra/compose/m2-dynsec/` 的匿名监听 1883 和明文 env 密码配置 **不可直接作为生产安装配置**。
3. Broker 新证书存放于一个新建私有树内；server.key 0600/UID1883 只是宿主机检查，还需要证明选定容器镜像、进程 UID/GID、`/mosquitto/tls` 的容器内 parent traversal 与只读文件绑定都实际可读取。若采用三个单文件 bind，宿主父目录 0700 不等于容器内父目录权限；不可直接推导 pass/fail，必须由后续 exact-image 隔离测试证明。
4. 服务器证书 SAN 含 `DNS:armbian`、`DNS:mqtt.greenhouse.local`、`IP:127.0.0.1`。Node 连接 locator 由当前 T1 LAN 获取而非源码固化；固定 TLS 名称配合 PR #522 auto 恢复。全新的 CA 与 H0/H1 System CA 分开。
5. **镜像标签/本地缓存镜像 ID 不能替代 source+digest/架构身份**，现有缓存镜像只为下一门选择候选，不直接作为最新产品批准版。
6. 当前还不能启动 Broker：需要完成新的 DynSec 初始化、独立 Manager/HA 账号 ACL、受限配置和 persistence 数据目录、准确 Compose 渲染 gate、入口防护状态与真实失败路径验证。生产 CA 私钥不应挂载到 Broker 容器。

## 下一门与 STOP

```text
S11_RESULT=PASS
NEXT_ONE_GATE=N3W_T1_S12_EXACT_TLS_FILE_AND_MOSQUITTO_IMAGE_READONLY_PREFLIGHT
S12_T1_MUTATION=false
S12_DOCKER_CONTAINER_CREATE=false
S12_SERVER_START=false
S12_KEY_ROTATION=false
S12_DYNSEC_INITIALIZE=false
S12_BOARD_ACCESS=false
S11_TLS_KEY_MATERIAL_GITHUB=false
PR541=OPEN_DRAFT
```

终端执行脚本仅贴在会话中，GitHub 保存脱敏源设计、证据、软件及测试，不提交私有运行参数或账号凭据。
