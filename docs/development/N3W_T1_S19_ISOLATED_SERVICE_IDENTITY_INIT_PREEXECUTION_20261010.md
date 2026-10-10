# N3-W T1 S19：三类服务身份的无网络隔离初始化预执行（2026-10-10）

## S18 事实锚点

S18-R3 已在 T1 实机通过：DynSec 初始 admin 的唯一默认接收权限已修复为 deny，生产 JSON SHA256 = `94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5`。UID1883/mode0600、根目录 0700，root-only 原字节备份 `/etc/n3wfc4/private/dynsec-s18-pre-receive-deny.json`，原备份 SHA256 = `93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da`。S18 敏感候选已安全删除；正式 Broker 未启动，T1 8883 未监听，45 个 Docker 卷和 ingress guard 保持。

## S19 服务身份权威

源代码只取 `host/greenhouse-manager/src/greenhouse_manager/runtime/service_identity_plan.py` 和 `dynsec_api.py` 中的三服务身份与 ACL，不新增一套产品权限模型。system_id=`greenhouse`，generation=1：

- provisioning：username `ghs_greenhouse_provisioning`，client id `gh-provisioning-greenhouse`，role `gh-service-greenhouse-provisioning`。仅 DynSec 控制请求和响应权限，明确禁止应用 `gh/#` 和 `homeassistant/#`。
- manager：username `ghs_greenhouse_manager`，client id `gh-manager-greenhouse`，role `gh-service-greenhouse-manager`；节点 ingress、网关 ingress、状态 telemetry 订阅/接收、配对 hello、canonical state/当前两种 HA Discovery 发布；禁止 `$CONTROL/#` 和无关 Topic。
- homeassistant：username `ghs_greenhouse_homeassistant`，client id `gh-homeassistant-greenhouse`，role `gh-service-greenhouse-homeassistant`；接收 HA Discovery 与 canonical state，允许发布 `homeassistant/status`，禁止其他应用写入。
- 每个角色使用 `service_identity_plan.py` 中冻结的准确 ACL type/topic/allow/priority；身份使用相互独立的 32 bytes 随机密码，绑定唯一 MQTT client id。管理员与业务账号相互独立。
- 所有服务的 `publishClientSend`/`publishClientReceive`/`subscribe` 默认拒绝，`unsubscribe` 默认允许。将来节点账号依据 `dynsec_plan.py` 在真实首次配对时按节点单独生成，不在 S19 预先创建节点账号。

## S19-R1 唯一允许的执行动作

首次执行仅在 T1 创建临时私有目录，以**新随机临时管理员**初始化与生产相同版本 Mosquitto 动态权限库，然后在一个 `--network none`（仅容器内部 127.0.0.1:18883）、`--pull never`、`--read-only`、`--cap-drop ALL`、`--security-opt no-new-privileges`、`--user 1883:1883` 的无宿主端口发布容器里，一次提交官方 DynSec 控制 API JSON 命令：设置默认 ACL、创建 3 个服务角色、创建 3 个绑定 client ID/角色/随机密码的服务客户端。命令经容器 stdin 传输，密码不出现在 argv、环境变量或 GitHub。

候选数据库必须检查：恰好 4 个客户端（throwaway admin + 3 services）、4 个角色、4 项默认 ACL 符合强制基线、服务用户名/clientid/角色映射准确、每个角色 ACL 多重集合精确匹配 `service_identity_plan.py`、角色优先级正确、无密码明文、临时目录加密性权限。成功后立即删除**仅该阶段创建**的 throwaway 数据；失败时敏感临时数据原位保留并 STOP，先分类取证，不循环重试。

下一阶段才使用新的短命候选执行 3 服务的认证 client ID 绑定和 Topic 允许/拒绝**运行时矩阵**，不得把 S19-R1 的 JSON 结构检查冒充正反例通信通过。真实 DynSec 数据库完全不动且 SHA 保持 `94f3c0...`；原始 root 0600 备份、管理员口令、CA/server TLS 不进入临时容器。

前后检查：宿主无 Docker containers、45 个原有 Docker volume 名称集合无变、两条 n3wfc4 网络无连接、入口 guard active 且规则首位拦截+终止 DROP、宿主 8883/18883 都无监听、镜像 ID/架构、真实新 JSON SHA、root-only 备份 SHA/元数据、生产 mosquitto.conf SHA；严禁启动正式 Broker、Manager/HA 或触碰板卡。

```text
S18=PASS
S19_R1_NEXT_ONE_GATE=N3W_T1_S19_R1_ISOLATED_THREE_SERVICE_IDENTITY_CREATION_AND_STATIC_ACL_PROOF
S19_R1_ONLY_THROWAWAY_PASSWORDS=true
S19_R1_PRODUCTION_DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
S19_R1_PRODUCTION_SECRET_MOUNTS=false
S19_R1_HOST_PORT_PUBLICATION=false
S19_R1_LIVE_SERVICE_START=false
S19_R1_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```
