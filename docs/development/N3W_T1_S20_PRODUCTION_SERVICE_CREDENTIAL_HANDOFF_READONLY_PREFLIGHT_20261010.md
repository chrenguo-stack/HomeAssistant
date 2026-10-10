# N3-W T1 S20 生产服务账号/密码交付只读预检（2026-10-10）

## 冻结的上游验收

S19 隔离服务身份与权限设计验收已 CLOSED_PASS：R1 静态三服务 10/17/9 ACL、R3 Provisioning MQTT DynSec 控制查询、R5 节点→Manager→HA 正向投递、R6A 正确 ID/错误 ID/匿名拒绝、R6B 跨主题不合法发布/订阅及测试专用允许订阅但默认接收拒绝全部通过。R2/R4 旧失败按测试可观察性/管理员错作业务发送端历史留档，没有抹除。

截至 R6B 现场输出，生产 `/var/lib/n3wfc4-broker/dynamic-security.json` 的现用 SHA256 保持 `94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5`，S18 私有备份原数据 SHA256 `93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da`，host TCP/8883 未发布，正式 Broker 未启动、45 volumes/guard 不变，临时数据已删除。三生产服务账号尚未写入，不应假装存在。

## 主线源码的可用能力（只读确认）

- `host/greenhouse-manager/src/greenhouse_manager/runtime/service_identity_plan.py`：定义 provisioning/manager/homeassistant 的独立 username、client ID、角色/ACL/随机密码；绑定 main blob SHA `19d95cfe59c12ee0abeaddf8c777fb663a5bd399`。
- `host/greenhouse-manager/src/greenhouse_manager/runtime/dynsec_api.py`：包含按规划创建 role、client 和默认 ACL 的 DynSec 控制命令，main blob SHA `6a75b60de88689524ec3b6d0105e0b3f66f5a682`。
- `host/greenhouse-manager/src/greenhouse_manager/runtime/config.py`：支持 Manager MQTT 的 `GH_MQTT_PASSWORD_FILE` 与独立 Provisioning 的 `GH_N3W_PROVISIONING_PASSWORD_FILE`，并处理 `GH_MQTT_USERNAME`、`GH_MQTT_CLIENT_ID`、`GH_N3W_PROVISIONING_USERNAME`、`GH_N3W_PROVISIONING_CLIENT_ID`；main blob SHA `fabb2affa9fb8ce76aa8ed94ce4f4ea9745402cd`。
- `protocols/pairing/gh-t1-manager-runtime-secret-ownership-gate-v1.md` main blob SHA `02b001967c7356adc0d6adee53854f3fb3643bb7`：Manager 必须使用与其实际运行 UID/GID 匹配、0600、只读挂载到 `/run/secrets/gh_manager_mqtt_password` 的文件；内联 `GH_MQTT_PASSWORD` 必须为空，并先用运行镜像下的 `--check-config`/固定 fallback 仅做只读验证。此为曾有迁移现场的已归档安全约束，fresh T1 部署仍需实际 image/Compose/UID 映射新鲜验证，不能直接宣称旧方案已部署。
- 发现历史 `host/greenhouse-manager/src/greenhouse_manager/ops/t1_migration_package.py` main blob SHA `3714a63f13f38f3f82a5f6c54a274ccebc23a3ca` 的旧迁移材料生成**三服务 + 一个 node 账号**。它不能不加修改用于 clean-product 首次配对 T1：Node 仍须首次 Gate F 后按实体逐节点生成，不允许预置共享或假节点身份。
- 仓库存在 Home Assistant MQTT 凭据轮换相关的测试，但截至本门只读源码检查，**尚未确认 fresh T1 的 HA 运行时实际秘密文件挂载/运行 UID/消费位置和精确 deployment binding**；此为待验事实，不是断言 HA 功能缺失。

## S20 进入生产账号创建前必须确定的 5 个条件

1. 真实 Manager 容器/image 版本、运行 UID、Manager MQTT 和 Provisioning **两套分离密码文件**的 0600 owner、只读 mount 和运行时读取路径，且无生产 plaintext env / argv。
2. Home Assistant 真实运行时（非旧迁移容器）的 MQTT 凭据创建、保存、消费和恢复路径；不依赖在 Broker 建账号之后手工把密码抄入 UI。
3. 账号/角色与持久化目录按配置的唯一责任方，密钥生成后只在受保护文件中一次写入，断电和容器重建后不丢失。
4. 更新真实 DynSec 前、后精确备份、单独 staging、失败 STOP、清晰回滚/继续边界；不复用历史迁移工具自动生成 node；admin 原身份与默认拒绝必须保留。
5. 正式启动 Broker/TLS/8883 的安全闸门独立于三服务账号写入门：可信且来源可证明的镜像、证书/主机名、受控 Compose 部署、guard、TLS 管理与实际客户端收发均须另行验证。

## 当前只读门结论

已有 Manager 文件读取机制、Provisioning 独立文件接口、三角色生成源和隔离 ACL 行为证据；生产运行时 credential handoff **尚未完成完整闭环绑定**，不能现在直接创建三服务真实账号。下一步仅做精确生产部署文件、Manager/HA runtime secret ownership 和最新 T1 环境的 source-to-runtime read-only check，确认三个密码各自由哪个消费者接收。若发现缺失先以源代码/部署设计做有限修补并测试，而非直接在 T1 投放凭据。

```text
S19_ISOLATED_ACL_ACCEPTANCE=CLOSED_PASS
S20_GATE=PRODUCTION_THREE_SERVICE_SECRET_HANDOFF_PREFLIGHT
S20_SCOPE=SOURCE_AND_T1_READ_ONLY
S20_PRODUCTION_CLIENT_CREATION=false
S20_PRODUCTION_BROKER_START=false
S20_HOST_8883_PUBLICATION=false
S20_BOARD_ACCESS=false
PR541=OPEN_DRAFT
```
