# T1 清洁部署 S3/S4 实测结论（2026-10-10）

当前路线：保留 Armbian，温室专用业务重建；旧 R4/B1I1 路线终止；生产目标为 Home Assistant、MQTT Broker、Greenhouse Manager 各一套。

## S3

用户在 T1 执行的定向旧容器退出结果：

- S3_PRECHECK=PASS
- DISPATCHER_DISABLED=QUARANTINED_EXACT_FILE
- OLD_CERT_TIMER=DISABLED_STOPPED
- OLD_BROKER_AUTOSTART=DISABLED_STOPPED
- S3_OLD_CONTAINERS_REMOVED=6
- HOST_TCP_8883_LISTENER=0
- INGRESS_GUARD_PRESERVED=true
- OLD_DATA_DELETED=false
- DOCKER_VOLUMES_DELETED=false
- S3_RESULT=PASS

## S4

用户报告的现场终端结果：

- S4_PRECHECK=PASS
- 六个精确旧业务目录清理均为 DELETE_PASS
- 一个由旧两个 Broker 共用的日志卷清理为 VOLUME_DELETE_PASS
- S4_OLD_BUSINESS_ROOTS_REMOVED=6
- S4_CONFIRMED_BROKER_VOLUME_REMOVED=1
- UNCLASSIFIED_VOLUMES_PRESERVED=45
- INGRESS_GUARD_PRESERVED=true
- ARMBIAN_CORE_PRESERVED=true
- BOARD_ACCESS=false
- S4_RESULT=PASS
- SSH_OR_REMOTE_EXIT_CODE=0

以上是已完成 S3/S4 实测输出的脱敏摘要。旧容器和业务数据已按明确授权清理，45 个没有独立证明归属的 Docker 卷未清理。本记录不证明新 T1 已完成部署。

## 后续工作

进入新环境的只读现场预检，核实剩余 systemd/NetworkManager 安全入口、Docker 网络与宿主工具链状态。新 Broker 的 TLS/证书、DynSec、双网络及防火墙保护，新 Manager 的初始化和三类持久状态，以及唯一一套 Home Assistant，均需重新部署和验收。旧 systemd unit 可能引用已不再存在的业务配置，严禁直接激活。

执行命令只在用户对话中给出；GitHub 仅归档结论与软件源代码。不提交私有路径、主机地址、秘密材料及实测日志正文。

S5_NEW_STACK_PREFLIGHT=PENDING
HOST_MUTATION_THIS_STEP=false
