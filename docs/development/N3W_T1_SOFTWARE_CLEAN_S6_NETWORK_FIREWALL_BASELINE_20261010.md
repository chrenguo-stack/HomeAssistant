# N3-W T1 S6 清洁主机网络与防火墙就绪取证（2026-10-10）

## 依据与路线

- 用户现场粘贴的 S6 只读结果：`S6_DEPLOY_READINESS=PASS`，SSH 退出码 `0`，`T1_MUTATION=false`。
- 保留现有 Armbian、网络、SSH、Docker Engine；新部署的产品目标是一个 Home Assistant、一个 Broker、一个 Manager；旧业务状态不迁移。
- 本文仅归档脱敏数据和检查结果，不包含终端操作指令或私人主机地址。

## S6 已确认事实

```text
DOCKER_EMPTY=PASS
NETWORK_ATTACHMENTS_EMPTY=PASS
S6_DEPLOY_READINESS=PASS
T1_MUTATION=false
BOARD_ACCESS=false
SSH_OR_REMOTE_EXIT_CODE=0
```

- `n3wfc4-private`：bridge、local、internal=true、IPv6=false、无容器、IPAM 一项。
- `n3wfc4-services`：bridge、local、internal=false、IPv6=false、无容器、IPAM 一项。
- `INPUT` 与 `DOCKER-USER`：每条链恰有一个项目专用 ingress guard anchor，且各在第一条。
- `N3WFC4-BROKER-INGRESS`：3 条规则，末尾 DROP。该事实属于结构检查，尚不等于真实 TLS/外网否定路径验收。
- 6 个已归属 systemd 单元的文件哈希与 FragmentPath 已实际取得。旧两个 P4 部署单元均 failed/static；Broker activation failed/disabled；证书 lifecycle service inactive/static、timer inactive/disabled；**ingress guard active/enabled**。
- Docker network、service 的现存部分是旧部署遗留，尚无完整新产品安装包；无旧 Broker 可供再使用。
- 基础服务与旧清理 S5 均已 PASS，现场不需要 OS 重装。

## 下一步风险与冻结要求

- 替换废弃 systemd unit 时只能按 exact `FragmentPath`、SHA256、状态执行；不允许对整目录批量删除。
- 保留旧 guard service 及其项目自有防火墙 chain/anchor，直至新 Broker 的先 guard 后 publication 验收通过。
- 旧 NetworkManager dispatcher 隔离状态不能长期作为成品状态；须在新 Broker 正式安装并经配置验证后恢复/替换为合法的守护流程。
- `/run` 下失败的 P4 部署单元与旧 Broker activation、证书服务为 legacy retirement candidates；本次 S6 并未执行卸载。
- 旧数据已 S4 清理；45 个尚未证明归属的 Docker volumes 仍保留，不把“无容器引用”当作可删授权。
- 生产级 Broker 双网络、8883/loopback TLS、DynSec ACL、证书及新 Manager 镜像/6 mount/健康检查和唯一 HA，需要单独构建与现场验收。

```text
S6_CLOSED=PASS
NEXT_ONE_GATE=N3W_T1_S7_EXACT_LEGACY_UNIT_RETIREMENT_AND_GUARD_PRESERVATION
S7_NOT_YET_EXECUTED=true
T1_MUTATION_THIS_DOC=false
PR541=OPEN_DRAFT
```

所有面向用户的操作命令均直接放在对话中；GitHub 只归档源代码、设计、脱敏证据及状态。
