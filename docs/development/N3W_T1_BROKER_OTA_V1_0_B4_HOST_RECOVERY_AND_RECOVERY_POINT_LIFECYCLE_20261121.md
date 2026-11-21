# N3-W T1 Broker OTA V1.0 — B4 宿主自动接管与 Recovery Point 生命周期

DATE=2026-11-21  
STATUS=SOURCE_IMPLEMENTATION  
STACKED_BASE_PR=817  
STACKED_BASE_HEAD=b79ec0ffc4f118ccffc94f2bcc328ab2715ab140  
B3_STATUS=CLOSED_PASS  
PRODUCT_AUTHORITY=T1_Core_Stack_OTA_V1.2  
T1_ACCESS=false  
PRODUCTION_MUTATION=false  

## 1. B4 目标

B3 已解决“目标 Broker 可能写过数据时，回滚必须恢复静止 Recovery Point”。

B4 补齐 V1.2 的下一条责任：

> updater 进程退出或 T1 重启以后，不依赖用户重新判断阶段，也不依赖 Manager/HA/UI 在线；宿主根据持久事务与实时运行事实接管未完成 Broker OTA。

B4 不建立第二套状态机。自动接管复用 Generic V2 的 runtime classifier、rollback、Broker Recovery Point 和证书生命周期锁。

## 2. 自动接管入口

新增受限命令：

```text
t1-core-updater recover-broker-pending
```

它不接受 target、路径、authorization 或 confirmation 参数。

允许的行为只有：

1. 没有 V2 transaction：NO_TRANSACTION；
2. 当前 transaction 不是 Broker：NOT_BROKER_TRANSACTION；
3. Broker transaction 已 COMMITTED/ROLLED_BACK：只维护 Recovery Point 生命周期，不切换运行版本；
4. Broker transaction 为 APPLYING/ROLLING_BACK/FAILED_EMERGENCY：从 fresh runtime facts 进入同一 Generic V2 rollback；
5. runtime 无法安全分类：fail closed，不猜测、不删除 transaction、不重放 authorization。

## 3. 掉电断点的关键事实

B4 新增并持久保存：

```text
rollback_source_phase
```

第一次进入恢复时，它固定为：

```text
existing rollback_source_phase
or failure_phase
or current phase
```

之后重入不得被 `ROLLBACK_AUTHORIZED`、`FAILED_EMERGENCY` 等后续阶段覆盖。

这是 Broker 数据恢复所需的写入边界事实。

典型断点：

```text
target Broker started
-> target may write dynamic-security.json / mosquitto.db
-> recovery restores predecessor binding
-> host loses power before predecessor start
```

重启后现场只看 binding 会看到 predecessor，但 `rollback_source_phase=ACTIVATING` 仍证明 target 曾可能写数据，因此必须再次幂等恢复 B3 Recovery Point，再启动 predecessor。

## 4. stopped 状态的证书锁

旧 Generic V2 在 application already stopped 时可以跳过 `quiesce_component()`。

对 Broker 不再这样做。

任何需要 Broker 数据恢复/重新启动的非健康路径都重新调用 Broker quiesce：

- 获取 KF-100 certificate-lifecycle exclusive lock；
- 证明 Manager/HA/Broker writer 均已停止；
- 再恢复持久数据和 binding；
- 最后启动 Broker -> Manager/HA。

因此“已经 stopped”只意味着不用等待业务退出，不意味着可以绕过 TLS/证书生命周期并发保护。

## 5. Recovery Point 生命周期

规则：

```text
NONTERMINAL -> Recovery Point 必须保留
COMMITTED   -> 不再拥有回滚授权，可以 retire
ROLLED_BACK -> predecessor 数据已恢复并健康，可以 retire
```

新增 `retire()`：

- 只接受 transaction 绑定的 Recovery Point key；
- snapshot 仍存在时先完整验证 manifest/digest/shape；
- 完整验证后先将 exact Recovery Point directory 原子重命名为同 transaction 的 `.retired` tombstone 并 fsync；
- 再删除 tombstone 并再次 fsync recovery root；
- 删除过程断电时，下次只恢复清理该 tombstone，不把半删目录重新解释为有效 Recovery Point；
- 重复 retire 为 PASS；
- 不删除 recovery root 下任何其他 transaction。

终态 transaction 记录：

```text
broker_recovery_retired=true
broker_recovery_cleanup_pending=false
broker_recovery_retired_at_unix=...
```

如果终态业务已经成立但 cleanup 失败：

```text
broker_recovery_cleanup_pending=true
```

业务终态不得因此从 SUCCESS/FAILURE 反转，也不得重新启动/回滚服务。后续宿主维护入口重试 cleanup。

为了避免 orphan snapshot，新的 V2 transaction 在归档前一笔 terminal Broker transaction 前会检查：若它仍绑定 Recovery Point 且没有 retired 事实，则先停止新事务并要求完成 retirement。

## 6. 开机 systemd 入口

新增源文件：

```text
infra/n3w-t1/systemd/n3wfc4-core-updater-broker-recovery.service
```

B4 只冻结 unit 语义，不在真实 T1 安装。

设计：

- ConditionPathExists 仅在 `upgrade.json` 存在时运行；
- 等 Docker、Broker activation、Services activation 的启动尝试结束后接管；
- **不使用 Before=Broker/Services**，避免 recovery service 内调用现有 service owner 时形成 systemd ordering cycle；
- oneshot；
- 失败最多由 systemd 在 120 秒窗口内重试 3 次；
- 不无限轮询；
- ExecStart 只调用固定 installed updater 的 `recover-broker-pending`。

为什么允许 product units 先完成启动尝试：

- 若目标 Broker 曾启动，B3 Recovery Point 已经在目标启动前成立；
- B4 会重新静止所有 writer 并恢复 snapshot；
- 若目标本身无法启动，activation job 结束后 recovery 仍能恢复 predecessor；
- 这样避免新增“pre-recovery unit + post-recovery unit”双阶段架构。

正式安装/enable 该 unit，以及把含 Broker recovery module 的 exact updater pyz 安装到固定路径，留到 Broker package/deployment 阶段；B4 不假装已经部署。

## 7. B4 确定性覆盖

新增/扩展测试证明：

- target-running 非终态 Broker 自动回滚，不需要用户 confirmation；
- target 已写、binding 已是 predecessor、服务 stopped 的重启断点仍先恢复数据再启动；
- ROLLING_BACK 重入保留最初 rollback_source_phase；
- terminal Recovery Point retirement 幂等；
- terminal cleanup 不重启业务；
- 非 Broker transaction 不被 Broker startup recovery 改动；
- 未 retire 的 Broker Recovery Point 阻止下一笔 transaction 被归档成 orphan；
- systemd startup unit 有界重试且不存在 Broker/Services Before cycle；
- CLI 自动恢复入口不接受外部 target/authorization。

## 8. B4 不包含

```text
T1 live install=false
systemd enable=false
real reboot=false
Broker target package=false
Broker image A->B live apply=false
multi-component release=false
merge=false
release=false
```

下一阶段需要把 B3/B4 模块装入 Broker exact updater package，安装/enable 固定宿主恢复 unit，并做 isolated Mosquitto + process-death/reboot deterministic package simulation；通过后才进入备用 T1 只读预检。
