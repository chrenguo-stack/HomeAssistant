# N3-W T1 清洁部署 S5 基础环境验收与 S6 源码部署前置（2026-10-10）

## 当前路线
保留运行中的 Armbian、SSH、NetworkManager、Docker Engine。用户已批准清除旧温室业务，且 T1 是专用主机。旧两套 Home Assistant、两个 Broker、旧 Manager/影子容器不恢复；新生产目标为 HA/Broker/Manager 各一套。

## S5 实测 PASS
证据来源是用户提供的 T1 终端只读输出，原始日志保留在用户私有环境；本归档不含个人用户、主机地址、秘密或 SSH 路径。

- `S5_PREFLIGHT_RESULT=PASS`、`SSH_OR_REMOTE_EXIT_CODE=0`、`T1_MUTATION=false`；
- Docker 容器 0；旧六个业务根目录均不存在；
- Docker volume 仍有 45 个：来源未识别，不做批量删除；
- 目标 TCP 8883/8123/47112、UDP 47111 均无监听；
- SSH/NetworkManager/Docker 均 active；
- Docker 29.7.1、Compose v5.4.0、Python 3.14.4、OpenSSL 3.5.5、Git 2.53.0；
- `n3wfc4-private` / `n3wfc4-services` 两网络存在，**未有容器身份、属性、驱动和旧附件确证**，下一门只读核对；
- 旧两个 P4 service 为 failed，旧 Broker activation 为 failed/disabled；旧证书 timer inactive/disabled；入口安全 guard active/enabled；NetworkManager 的旧 dispatcher 在隔离位置；
- 三项旧业务部署工具中 guard 与证书生命周期脚本存在，持久化安装工具缺失；**不能运行旧启动命令或假定可以从旧目录恢复配置**。

## 源码部署依据与差距

- `infra/n3w-t1/README.md`：Manager host network 无 ports；Broker IPv4 0.0.0.0:8883 唯一发布、两个明确网络、先 guard 后 activation 的安全顺序及 loopback TLS；
- `tools/n3w_pairing_deployment_gate.py`：静态校验现行部署合同，包括 `GH_N3W_PAIRING_ADVERTISED_HOST` 和双网络；
- `docs/adr/0008-n3w-pairing-recovery-simplification-v2.md`：新主机与板卡首次配对需要新的随机配对事务和安全凭据；板卡属于之后独立验收；
- 早期 `infra/compose/t1/README.md` 仍描述实验性的匿名 MQTT 1883 和复用老 Broker，**不能作为本次安装流程**；
- `infra/compose/m2-dynsec/docker-compose.yml` 是实验服务组合示例，**不能未经改造直接用于安全生产**；
- 当前已审阅源码不构成完整的、对清洁 T1 可直接使用的产品级安装包；需重新绑定实际运行配置、CA/TLS、DynSec 初始化、Manager 精确镜像/六挂载、单 HA 与自启动。

## NEXT_ONE_GATE

```text
S5_HOST_BASELINE=PASS
S6_FRESH_NETWORK_AND_RESIDUAL_UNIT_READONLY_BINDING=PENDING
PRODUCTION_COMPOSE_DEPLOY_PACKAGE=PREPARATION_REQUIRED
LEGACY_DOCKER_COMPOSE_AUTO_RUN=FORBIDDEN
BROKER_8883_GUARD=KEEP_ACTIVE
S6_LIVE_MUTATION=false
BOARD_ACCESS=false
```

后续 Mac Terminal 命令直接在对话中交付；GitHub 仅保留脱敏技术结论和正式软件/测试材料，不新增命令式 runbook。
