# N3-W T1 S7 旧部署服务退役验收与 S8 新 Broker 安装准备（2026-10-10）

## S7 现场验收

依据用户直接提供的 T1 终端输出，执行到完整 STOP，远程退出码 0：

```text
S7_PRECHECK=PASS
S7_OLD_UNIT_FILES_REMOVED=5
SYSTEMD_DAEMON_RELOAD=PASS
INGRESS_GUARD_PRESERVED=true
FIREWALL_GUARD_PRESERVED=true
ARMBIAN_CORE_PRESERVED=true
BOARD_ACCESS=false
S7_RESULT=PASS
SSH_OR_REMOTE_EXIT_CODE=0
```

五个旧 systemd 部署 unit 文件已由 exact path + SHA256 + state 前检通过后移除：两项 P4 Manager failed unit、旧 Broker activation service、旧 Broker certificate lifecycle service/timer。现存 ingress guard service 和防火墙 anchor/chain 均保留。由 S3/S4/S5/S6/S7 的实测结果可界定旧业务清洁部署阶段完成；不推定未归属的 45 个 Docker 卷已可安全删除。

## 新 Broker 仍需的正式安装准备

现行源合同：
- `infra/n3w-t1/README.md` 与 `tools/n3w_pairing_deployment_gate.py` 要求唯一 TCP/8883 wildcard publication、两条精确 bridge network、先 ingress guard 后 Broker activation、Manager host mode/无 ports、loopback TLS runtime probe。
- `docs/adr/0008-n3w-pairing-recovery-simplification-v2.md` 规定首次配对与独立安全生命周期，旧业务配对状态不得迁移。
- `host/greenhouse-manager/src/greenhouse_manager/bootstrap/system_init.py` 可以生成新 SYSTEM_ID、MANAGER_ID、SYSTEM_ROOT_KEY 及 H0/H1 System CA；**H0 System CA 与 Broker FC4 CA 不能未经合同证明就视作同一 CA**。
- `docs/development/N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_PRODUCTION_DEPLOYMENT_PREPARATION_20260929.md` 已有证据说明 Broker 的 server.key 应为进程 UID 1883/GID 1883 可读的 0600 文件；FC4 CA 私钥应另存 root-only 0600。旧证书的指纹和旧 TLS hostname 不属于本次新部署 authority。
- 旧 `infra/compose/t1/docker-compose.manager.yml` 为实验复用 1883/匿名 MQTT 的早期合同，不能直接用于清洁生产。
- 缺少已验证的全新 T1 complete production compose/initialization package，禁止直接根据旧实验编排启动。

## S8 的下一个现场门

只读取得：hostname/主机名解析和 LAN 网卡信息（用于 TLS SAN/节点连接合同）、docker arch/compose、容器镜像可用性/精确摘要、旧 8883 guard 状态及网络余量。准备新的非秘密 Compose/证书配置源码与相应离线测试，完成前不可打开 8883，亦不可生成或提交实际密钥。终端命令全部直接在对话提供，GitHub 不发布执行命令或私有路径/凭据。

```text
S7_RESULT=PASS
S8_NEXT_ONE_GATE=N3W_T1_FRESH_BROKER_TLS_IDENTITY_AND_IMAGE_AUTHORITY_READONLY
S8_SOURCE_PACKAGE=PREPARATION_REQUIRED
S8_T1_MUTATION=false
BROKER_CA_REUSE=false
BROKER_8883_PUBLICATION=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
```
