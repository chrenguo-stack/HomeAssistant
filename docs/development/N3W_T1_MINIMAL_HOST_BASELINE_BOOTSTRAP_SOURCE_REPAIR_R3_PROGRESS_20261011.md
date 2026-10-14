# N3-W T1 minimal-host fresh bootstrap R3 source repair progress（2026-10-11）

## 结论

R3 已把“从干净宿主开始”的安装顺序写成正式 source orchestration。

顺序固定为：

```text
只读检查宿主干净
→ 离线装入 3 个镜像
→ 创建新 System Identity
→ 创建空 Manager / N3-W 状态
→ 创建 Broker TLS 与三套服务凭据
→ 初始化 DynSec
→ 安装运行文件 / 网络 / guard
→ 提交 candidate
→ stopped-state 验收
```

任何一步失败，只允许清理由本次 transaction 新建的内容。若清理结果无法证明，直接进入人工恢复状态，不猜测、不覆盖旧内容。

## 本轮 source

新增：

```text
host/greenhouse-manager/src/greenhouse_manager/bootstrap/fresh_product_state.py
host/greenhouse-manager/src/greenhouse_manager/bootstrap/fresh_installer.py
host/greenhouse-manager/tests/bootstrap/test_fresh_installer.py
```

R1 的 fresh Manager/N3-W state 核心逻辑从临时 tool 中提升为 Manager package 的正式模块；原 tool 保留为薄 CLI wrapper，避免两份业务逻辑继续漂移。

R3 installer 目前只负责顺序、检查和失败清理合同，不包含 T1 SSH/传输，也不提供生产 activation CLI。真正 host wrapper / artifact transport 留给 R4。

## R3 关键边界

```text
OLD_45_VOLUME_FINGERPRINT_NOT_USED=true
PRECREATED_IDENTITY_NOT_REQUIRED=true
PRECREATED_SECRET_NOT_REQUIRED=true
PRECREATED_DYNSEC_NOT_REQUIRED=true
LEGACY_PROVENANCE_NOT_REQUIRED=true
NODE_CREDENTIAL_PRECREATION=0
PRODUCTION_SERVICE_START=false
ACTIVATION_AUTHORIZED=false
T1_ACCESS=false
BOARD_ACCESS=false
```

CI 已把 fresh installer/fresh broker tests 加入 Manager state binding focused gate。

```text
R3_SOURCE_COMMITTED=true
R3_CI=PENDING
NEXT_ONE_GATE=N3W_T1_MINIMAL_HOST_BASELINE_BOOTSTRAP_SOURCE_REPAIR_R4_20261011_01
R4_SCOPE=HOST_WRAPPER_AND_ARTIFACT_TRANSPORT
```
