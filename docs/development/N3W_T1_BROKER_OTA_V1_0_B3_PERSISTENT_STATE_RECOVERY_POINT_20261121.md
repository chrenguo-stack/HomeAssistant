# N3-W T1 Broker OTA V1.0 — B3 持久状态 Recovery Point 设计与源码实现

DATE=2026-11-21  
STATUS=SOURCE_IMPLEMENTATION  
STACKED_BASE_PR=816  
STACKED_BASE_HEAD=9c58cc1dada31488d70e1d15b3d263b5f077781c  
PRODUCT_AUTHORITY=T1_Core_Stack_OTA_V1.2  
T1_ACCESS=false  
PRODUCTION_MUTATION=false  

## 1. B3 目标

B2 已把 Broker 从历史 literal image 安全收敛到 `GH_BROKER_IMAGE`。B3 解决下一条独立责任：

> 目标 Broker 一旦有机会启动，就不能仅恢复旧镜像；必须能够恢复升级前静止状态下的 Broker 持久数据。

首版 Broker OTA 仍是 `IMAGE_ONLY_V1`。B3 不引入 Broker 配置迁移、TLS/CA 迁移、DynSec schema 迁移或 USB。

## 2. 受保护数据范围

当前产品 Broker writable root：

```text
/var/lib/n3wfc4-broker
```

B3 将该目录中的平面 regular-file 集合整体视为 Broker 持久状态，且至少要求：

```text
dynamic-security.json
mosquitto.db
```

这样既保护当前已知的两类角色，也不会只备份其中一项而遗漏 retained/persistence 内容。

以下内容不属于 B3 Recovery Point：

```text
/etc/n3wfc4/tls/*
/opt/HomeAssistant/infra/n3w-t1/broker/mosquitto.conf
Manager / HA 数据
Docker image
证书生命周期状态
```

原因是 IMAGE_ONLY_V1 不允许这些身份在本次 Broker 镜像升级中发生迁移。

## 3. 创建顺序

```text
healthy predecessor
  -> read-only capacity preflight
  -> persist Generic V2 transaction/recovery responsibility
  -> acquire certificate-lifecycle lock
  -> stop Manager + HA owner
  -> stop Broker owner
  -> prove all three containers stopped
  -> create + fsync Broker Recovery Point
  -> persist Recovery Point binding in transaction
  -> publish target image binding
  -> start target Broker
```

Recovery Point 创建失败时，目标 Broker 尚未启动，因此直接启动原 Broker，不需要做数据回写。

## 4. Recovery Point 结构

默认私有目录：

```text
/var/lib/n3w-t1-core-updater/broker-recovery/<transaction-key>/
  manifest.json
  state/
    dynamic-security.json
    mosquitto.db
    ...
```

要求：

- recovery root/transaction directory 为当前 root owner 且不向 group/other 开放；
- snapshot 文件为 root-only copy，不复用生产 UID 权限；
- manifest 绑定源目录 identity、每个文件的 size/SHA-256/mode/uid/gid；
- manifest 自身 SHA-256 与 source-tree SHA-256 写入 Generic V2 transaction；
- snapshot 回读验证成功后才允许发布 target binding；
- source/snapshot 任一 symlink、子目录或非 regular file 都 fail closed；
- 快照不会包含密钥目录或 TLS 私钥。

## 5. 容量

第一次停服之前执行只读容量检查：

```text
required_free =
  broker_state_total_bytes
  + largest_state_file_bytes
  + 16 MiB reserve
```

第一项是 Recovery Point 本体；第二项为恢复时同目录原子单文件替换所需峰值；reserve 给事务和文件系统开销留余量。

Broker 停止后再次以最终静止大小执行相同检查。若最终大小超过准备估计导致空间不足，Recovery Point 不成立，Generic V2 启动前代并终止本次升级。

## 6. 回滚规则

只有以下阶段认为 target Broker **可能已经写入持久数据**：

```text
ACTIVATING
TARGET_RUNTIME_STARTED
VERIFYING
以及对应 rollback activation phases
```

失败发生在这些阶段时：

1. 再次静止 Broker/Manager/HA；
2. 验证 Recovery Point；
3. 将 snapshot 中每个文件通过同目录临时文件 + fsync + `os.replace` 恢复；
4. 删除 target-only regular files；
5. 对恢复后的 live tree 重新计算 source-tree SHA-256；
6. 只有精确匹配才恢复 predecessor image binding 并启动旧服务。

每个文件替换都是幂等的；同一 Recovery Point 可重复执行 restore。B4 的宿主开机接管将复用这一幂等原语。

## 7. 提交后的边界

V1.2 规定持久提交后本笔自动回滚权结束。因此 B3 明确拒绝把已 COMMITTED Broker 事务的旧 Recovery Point 当作普通显式 rollback 材料：

```text
broker_committed_recovery_point_expired
```

否则会把提交后新增的合法 DynSec/retained 状态覆盖回旧快照。

B3 当前保留已提交 snapshot，清理/断电接管的生命周期由下一阶段接线；保留 snapshot 本身不构成回滚授权。

## 8. 源码落点

- `tools/n3w_t1_core_updater_broker_recovery.py`
  - capacity preflight
  - snapshot create/verify
  - idempotent restore
- `tools/n3w_t1_core_updater_host.py`
  - 仅在三服务写入方均静止时允许 create/restore
- `tools/n3w_t1_core_updater_v2.py`
  - Broker plan 增加 Recovery Point 动作
  - target 启动前持久绑定 snapshot
  - target 可能写入后失败时自动恢复 snapshot
  - 保存 failed-emergency 的原 failure phase
  - 禁止 COMMITTED Broker 使用 stale Recovery Point 回滚
- `tests/tools/test_n3w_t1_core_updater_a2.py`
  - snapshot round trip
  - tamper rejection
  - symlink rejection
  - capacity rejection
  - Broker activation failure restores old state
  - committed snapshot cannot be reused as rollback authority

## 9. B3 完成条件

```text
B2_CLOSED_PASS=true
BROKER_RECOVERY_CAPACITY_PREFLIGHT=true
BROKER_STATIC_RECOVERY_POINT=true
BROKER_RECOVERY_POINT_TRANSACTION_BOUND=true
BROKER_TARGET_WRITE_FAILURE_RESTORES_STATE=true
BROKER_RECOVERY_RESTORE_IDEMPOTENT=true
BROKER_SNAPSHOT_TAMPER_FAIL_CLOSED=true
BROKER_COMMITTED_STALE_ROLLBACK_BLOCKED=true
T1_ACCESS=false
LIVE_APPLY=false
BOOT_RECOVERY_INTEGRATION=false
TARGET_RELEASE=false
```

B3 源码/CI 通过后，下一阶段才处理宿主启动时对未完成 Broker transaction 的自动接管及 Recovery Point 生命周期。
