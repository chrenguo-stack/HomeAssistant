# N3-W T1 逐台 fresh Armbian 自动产品部署 F0 源码重绑定与缺口复核闭环

Date: 2026-10-14  
Gate: `N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F0_SOURCE_REBIND_AND_GAP_REVIEW_20261014_01`  
Architecture authority: `docs/adr/0010-t1-per-device-fresh-armbian-automated-product-deployment.md`

## 1. 结论

```text
F0_RESULT=CLOSED_PASS_SOURCE_DESIGN
REVIEWED_SOURCE_HEAD=f7bf8828c72f2df9fe497c05c4a2b4557d3f695b
REVIEWED_SOURCE_TREE=a3595a1ea67b648c399eb24f9913be36ed13a6af
PR=541
PR_STATE=OPEN_DRAFT_UNMERGED
SOURCE_CI=27_SUCCESS_0_FAILURE_0_PENDING

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
AUTO_EXECUTE_NEXT_GATE=false
```

F0 已完成 repository-only fresh rebind、active source seam 盘点、旧 clone 路线隔离、
镜像 authority 比较、交付合同选择、容量模型重算和 F1 最小改动范围冻结。

本闭环**不声明真实 T1 已可部署**。F1 仍需实现并通过 CI；之后 F2 必须对 fresh T1
重新做只读 preflight。F3/F4 仍分别需要独立 live authorization。

## 2. Fresh rebind

Fresh rebind 结果：

```text
MAIN=d423211b6196c2f2f0f01dff072c4f877fbe58ee
CANDIDATE_REF=plan/n3w-t1-full-fresh-install-from-zero-20261010
CANDIDATE_HEAD=f7bf8828c72f2df9fe497c05c4a2b4557d3f695b
CANDIDATE_TREE=a3595a1ea67b648c399eb24f9913be36ed13a6af
HANDOFF_TO_REVIEW_DELTA=IDENTICAL
PR_541=OPEN_DRAFT_UNMERGED
PR_MERGEABLE=true
CURRENT_HEAD_WORKFLOWS=27
CURRENT_HEAD_WORKFLOWS_SUCCESS=27
CURRENT_HEAD_WORKFLOWS_FAILURE=0
CURRENT_HEAD_WORKFLOWS_PENDING=0
```

`f7bf8828c72f2df9fe497c05c4a2b4557d3f695b` 相对前一 source authority `7736ddcef5fb28947048f0a7a4ae367a63c94ab3`
只有 F0 handoff/current-state 的 documentation-only advance，没有新的产品源码漂移。

当前 exact fresh deployable workflow run `38513418270` 通过，artifact：

```text
ARTIFACT_ID=11870783999
ARTIFACT_DIGEST=sha256:3d85fbf2259672caa265b1944d229d50b9117d5db79f99cdeb3366000dc7b3eb
PAYLOAD_ARCHIVE_SHA256=b82e3caeba7bd7563616d422b11e2f7c514577e8b1a4c4f5b284349065bdd2e7
PAYLOAD_MANIFEST_SHA256=962514e5380d4a207dfa618c2d89e6c575ed633f6d6170c6c894911a9f517e10
```

该 artifact 只作为 F0 source/evidence 输入；它仍使用旧 transport /1，不得直接提升为新路线
F3 deployable authority。

## 3. Active source seam 盘点

### 3.1 可直接复用或小改复用

```text
REUSE:
- host/.../bootstrap/fresh_installer.py
  preflight -> authorization boundary -> image stage -> identity/state/broker/dynsec/runtime
  -> commit -> stopped postcheck；现有 cleanup/rollback 结构保留。
- tools/n3w_t1_fresh_product_bootstrap.py
  fresh identity/state/Broker/DynSec/runtime/postcheck adapters 可复用；
  image delivery 与 manifest coupling 需要 F1 解耦。
- tools/n3w_t1_fresh_product_state_prepare.py
- greenhouse_manager.bootstrap.fresh_product_state
- greenhouse_manager.bootstrap.fresh_broker
- device provisioning lock / durable transaction / marker-last / resume / verify
- device_provisioning_cli.py 的显式 status/start authority
- device_provisioning_runtime.py 的 UNPROVISIONED NOOP / INITIALIZING RESUME /
  DEVICE_READY VERIFY_ONLY 语义
- tools/n3w_t1_clean_product_deployment_gate.py
- tools/n3w_t1_broker_authenticated_readiness.py
- HA MQTT bootstrap component + isolated runtime tests
- ingress guard
- docker-compose.fresh.yml 的 stopped/staged product topology
```

### 3.2 F1 必须修复的 active gaps

#### G1 — fresh Armbian 到 Docker baseline 缺口

现有 minimal-baseline inventory/normalize 和 fresh installer 都把 Docker Engine +
Compose 当成已经存在并 active 的前提。repository 中没有当前产品路线可用的
fresh-Armbian Docker/Compose 安装步骤。

ADR-0010 的正式起点允许：

```text
DOCKER_ENGINE_AND_COMPOSE=PRESENT_OR_INSTALLABLE_BY_APPROVED_STEP
```

因此 F1 必须补一个 repository-owned、版本/来源明确、可测试、幂等的 Docker/Compose
baseline step，或明确把它封装在新 installer 中；不得退回人工零散安装。

#### G2 — 旧 transport /1 同时 materialize 三个 image tar

当前 host wrapper 仍执行：

```text
complete payload archive
-> full remote extraction
-> all three image tars present
-> sequential docker load
```

历史精确证据：

```text
AVAILABLE_BYTES=9229160448
OLD_REQUIRED_FREE_BYTES=12671384447
OLD_MARGIN_BYTES=-3442223999
```

该 transport 已不允许进入新路线。

#### G3 — fresh active artifact 仍夹带 Golden Master 路线

当前 fresh deployable workflow 仍：

- trigger/copy `n3w_t1_golden_master_common.py`、`n3w_t1_golden_master_build.py`；
- 把 Golden Master build helper 放进 fresh payload；
- 在 fresh payload CI 中运行 `ci-golden-master` self-check。

这些源码可以保留为历史参考，但 ADR-0010 生效后不得继续作为 per-device fresh
deployment active dependency。

#### G4 — explicit provisioning 仍有 clone-only preflight 语义

`device_firstboot.py` 的当前 preflight 仍要求：

```text
sealed_image=true
clone_readback_verified=true
```

这与逐台 official fresh Armbian 路线不一致。F1 必须替换为：

```text
fresh_host_readiness
+ exact public deployment/release binding
+ product state absent/classified
+ OS host identity ready/stable
```

保留 single initializer、durable transaction、resume、marker-last 和 live-host binding，
删除 active path 中 clone/seal/readback authority。

#### G5 — F3 stopped boundary 与 systemd enable 逻辑冲突

`infra/n3w-t1/install-systemd-persistence.sh` 当前一次性 enable：

```text
guard
broker activation
services activation
certificate timer
```

而 F3 的冻结结束条件是“公共程序/身份/状态部署完成，但生产服务仍未激活”。

F1 必须拆开：

```text
install/stage units != enable production activation
```

F3 最多安装并验证 unit/guard material；Broker/Manager/HA activation unit 的 enable/start
属于 F4。

另外，`n3wfc4-provision-resume.service` 当前调用
`n3w-t1-provision resume-if-needed`，而当前 CLI source 只暴露 `status` 和 `start`。
F1 必须把 boot-resume adapter/entrypoint 做成真实可安装、可测试的产品入口，不能只靠
source-only unit 存在。

## 4. Exact image authority

### Home Assistant

```text
SOURCE_REF=ghcr.io/home-assistant/home-assistant:2026.10.0
ARM64_MANIFEST_DIGEST=sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4
EXPECTED_IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
AUTHORITY=EXACT_EXTERNAL_DIGEST_AVAILABLE
```

### Broker

```text
SOURCE_REF=m.daocloud.io/docker.io/library/eclipse-mosquitto:2.1.2-alpine
ARM64_MANIFEST_DIGEST=sha256:3184566df484a083411a0e70e92c87a264b8f0648df632f10eb23d54d99f4549
EXPECTED_IMAGE_ID=sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b
AUTHORITY=EXACT_EXTERNAL_DIGEST_AVAILABLE
```

### greenhouse-manager

当前 exact-head CI 从 repository source 直接 build ARM64 image：

```text
SOURCE_HEAD=f7bf8828c72f2df9fe497c05c4a2b4557d3f695b
IMAGE=local/greenhouse-manager:fresh-f7bf8828c72f
IMAGE_ID=sha256:2539efba0229acfff3b9598826cf8bb63a43b90fcfcaa3f122529fc5b8eba16a
AUTHORITY=EXACT_SOURCE_BUILD_PLUS_BOUND_ARTIFACT
EXTERNAL_REGISTRY_DIGEST_AUTHORITY=ABSENT
```

因此“三镜像全部由 T1 按 registry digest 直接 pull”当前**不能作为最小默认路线**。
要选择该方案，必须新增 Manager registry publication/digest lifecycle，这会扩大 F1 范围。

## 5. F0 选择的镜像交付合同

```text
SELECTED_IMAGE_DELIVERY_CONTRACT=MAC_ONE_IMAGE_AT_A_TIME_VERIFIED_STAGE_LOAD_V2
TARGET_REGISTRY_PULL_DEFAULT=false
ALL_THREE_IMAGE_TARS_MATERIALIZED_TOGETHER=false
FULL_PAYLOAD_ARCHIVE_ON_T1=false
IMAGE_ORDER=HOMEASSISTANT_THEN_MANAGER_THEN_BROKER
REMOTE_STAGED_IMAGE_COUNT_MAX=1
REMOTE_IMAGE_TAR_SHA256_REQUIRED=true
RUNTIME_IMAGE_BINDING_AFTER_EACH_LOAD=true
DELETE_STAGED_TAR_AFTER_VERIFIED_LOAD=true
FREE_SPACE_RECHECK_BEFORE_EACH_IMAGE=true
FREE_SPACE_RECHECK_AFTER_EACH_IMAGE=true
MIN_POST_PEAK_FREE_BYTES_POLICY=KEEP_EXISTING_5_GIB_UNTIL_SEPARATE_EVIDENCE_CHANGES_IT
PRODUCTION_SERVICE_START=false
```

推荐流程：

```text
Mac obtains exact current artifact
-> verifies artifact/source/manifest
-> sends small non-image runtime package
-> fresh read-only preflight
-> one-shot F3 authorization claim
-> send exactly one image tar
-> verify remote tar SHA
-> docker load
-> verify image ID/platform/RootFS/config binding
-> delete that tar
-> re-read free space
-> repeat next image
-> continue product staging/provisioning
-> stopped postcheck
```

这样不要求 T1 持有完整 compressed payload + 三个 image tar，也不引入 Manager registry
publication 这一条新产品依赖。

## 6. 容量合同重算

旧模型把“完整 payload、三个 materialized image tar、container content/snapshot 和固定
5 GiB reserve”合在一个静态峰值中。新模型改为**逐镜像动态 admission**：

```text
for image i:
    free_before_i = fresh df on the shared staging/docker/containerd filesystem
    require free_before_i >=
        one_staged_tar_i
        + conservative_import_growth_i
        + 5_GiB_reserve

    transfer only image i
    verify exact SHA
    load and verify exact runtime binding
    delete image i staging tar
    free_after_i = fresh df
    require free_after_i >= 5_GiB_reserve
```

这里的 `conservative_import_growth_i` 必须由 exact artifact 中已经存在的
`tar_size_bytes` / `loaded_size_bytes` 生成，不允许手工估算。

F0 不把历史 `9229160448` bytes 冒充当前 fresh T1 free space。它来自旧 R3 场景且当时
仍有约 2.4 GiB retained payload。F2 必须重新读取 fresh host 实际 free bytes。

同时，当前 artifact 只把 per-image size 放在大 payload 内部 manifest；F0 不制造一个
无法从 public-safe小证据独立复算的“current-head 单一数字”。F1 必须新增一个小型、
machine-readable capacity sidecar，并让 CI/host wrapper 校验：

```text
transport schema
source head
each image tar_size_bytes
each image loaded_size_bytes
image order
5 GiB reserve
per-step required-free envelope
```

因此 F0 冻结的是**capacity algorithm + exact input authority + fail-closed threshold**，而不是
把旧静态 12.67 GB 数字平移到新 transport。

参考旧证据仍保留：

```text
LEGACY_R8_IMAGE_LOAD_PEAK_BYTES=7302675327
LEGACY_R8_REQUIRED_FREE_BYTES=12671384447
OBSERVED_CAPACITY_REFERENCE_BYTES=9229160448
LEGACY_R8_CAPACITY_MARGIN_BYTES=-3442223999
CURRENT_HEAD_DYNAMIC_CAPACITY_MARGIN=F2_REQUIRED:NO_LIVE_CAPACITY_PROMOTION_IN_F0
```

这符合 ADR-0010：F0 选择容量更低、可逐步校验的 transport；F1 使 exact numeric envelope
成为 artifact 的公开安全一部分；F2 再用 fresh T1 的真实 free bytes 作最终 admission。

## 7. F1 最小源码修改清单

```text
F1_MINIMAL_CHANGE_LIST=
1. add repository-owned fresh-Armbian Docker Engine + Compose baseline installer/checker
2. bump fresh transport contract and artifact layout; split non-image runtime from image tar delivery
3. host wrapper transfers/loads exactly one image at a time and deletes staging copy after verification
4. emit/verify small exact capacity sidecar with per-image tar/loaded sizes and 5 GiB reserve
5. preserve one-shot claim before first Docker mutation and consumed/no-replay semantics
6. decouple bootstrap manifest validation from simultaneous presence of all three image tar files
7. remove Golden Master helpers/self-checks from active fresh payload/workflow path
8. replace sealed-image/clone-readback provisioning preflight with fresh-host/release readiness
9. provide real installable boot-resume provisioning entrypoint matching systemd unit
10. split unit installation from Broker/Manager/HA activation enable/start
11. preserve ingress guard, exact image binding, rollback, stopped F3 boundary and public/private evidence rules
```

明确不进入 F1 的范围：

```text
NO_MANAGER_REGISTRY_PUBLICATION
NO_R2C
NO_FINAL_SEAL
NO_DISK_CAPTURE
NO_CLONE_BOOT
NO_BOARD_ACCESS
NO_PRODUCTION_SERVICE_ACTIVATION
NO_LOWERING_5_GIB_RESERVE
```

## 8. F1 tests / workflows

Focused tests 至少包括：

```text
tests/tools/test_n3w_t1_fresh_product_staging_host.py
tests/tools/test_n3w_t1_fresh_product_bootstrap.py
host/greenhouse-manager/tests/bootstrap/test_fresh_installer.py
host/greenhouse-manager/tests/bootstrap/test_device_firstboot.py
host/greenhouse-manager/tests/bootstrap/test_device_provisioning_cli.py
host/greenhouse-manager/tests/bootstrap/test_device_provisioning_runtime.py
tests/tools/test_n3w_t1_clean_product_deployment_gate.py
tests/tools/test_n3w_t1_broker_authenticated_readiness.py
tests/tools/test_n3w_ha_mqtt_bootstrap_component.py
tests/tools/test_n3w_ha_mqtt_bootstrap_isolated_runtime.py
minimal baseline installer/checker new focused tests
systemd stopped-boundary / activation-separation tests
```

Required workflows：

```text
N3W T1 fresh bootstrap deployable payload CI
N3W T1 fresh install host-only CI
N3W T1 fresh install exact ARM64 CI
N3W T1 explicit provisioning source CI
N3W T1 deployment gate CI
N3W T1 HA bootstrap isolated CI
N3W Broker ingress guard CI
Public repository safety CI
greenhouse-manager CI
```

新增 transport tests 必须至少证明：

- 三个 tar 永远不同时 materialize 到 T1 staging；
- remote staged image count <= 1；
- remote SHA 不匹配在 docker mutation 前失败；
- authorization claim 严格早于第一次 docker load；
- 每个 image load 后立即 runtime binding + staging delete + free-space recheck；
- dynamic capacity failure fail-closed；
- postclaim failure consumed/no-replay + transaction-owned cleanup；
- F3 结束时 Broker/Manager/HA 仍未启动且 activation units 未越权 enable；
- reboot helper 只 resume existing transaction，不从 UNPROVISIONED 自动开始；
- clone/seal/golden-master source 不再进入 active fresh artifact。

## 9. Rollback / stop boundary

```text
PRECLAIM_FAILURE=no mutation; no authorization claim
POSTCLAIM_IMAGE_FAILURE=authorization consumed; no replay; remove transaction-owned staged tar/images when source contract proves ownership
PROVISIONING_FAILURE=keep durable transaction; source-defined resume/rollback only
F3_STOP=DEVICE_READY/STAGED_WITH_PRODUCT_SERVICES_STOPPED
F4_NOT_ENTERED=true
BOARD_ACCESS=false
MERGE=false
```

## 10. KF-113 guard update

本轮没有证明新的独立 failure class，因此不新增 KF 编号。扩展现有 KF-113：

- 退役 clone/GMS source 可以保留，但不得进入 active fresh payload/import/call graph；
- per-device fresh provisioning 不得要求 sealed image / clone readback；
- F3 不得 enable/start Broker/Manager/HA activation units；
- 5 GiB reserve 继续保留，除非未来有独立证据和单独决策修改。

## 11. Closure

```text
=== N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F0_SOURCE_REBIND_AND_GAP_REVIEW_20261014_01 CLOSURE ===

EXECUTION_ID=N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F0_SOURCE_REBIND_AND_GAP_REVIEW_20261014_01
AUTHORIZATION=NOT_REQUIRED:REPOSITORY_ONLY_F0
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false

SOURCE_HEAD=f7bf8828c72f2df9fe497c05c4a2b4557d3f695b
SOURCE_TREE=a3595a1ea67b648c399eb24f9913be36ed13a6af
PR_STATE=OPEN_DRAFT_UNMERGED
SOURCE_CI=27_SUCCESS_0_FAILURE_0_PENDING
ACTIVE_SOURCE_SEAMS=FRESH_INSTALLER+FRESH_BOOTSTRAP+MINIMAL_BASELINE+EXPLICIT_PROVISIONING+DEPLOYMENT_GATE+INGRESS_GUARD+HA_BOOTSTRAP+ACTIVATION
CLONE_ONLY_BRANCH_DISPOSITION=RETAIN_HISTORY_BUT_REMOVE_FROM_ACTIVE_FRESH_PAYLOAD_AND_PROVISIONING_PRECHECK
SELECTED_IMAGE_DELIVERY_CONTRACT=MAC_ONE_IMAGE_AT_A_TIME_VERIFIED_STAGE_LOAD_V2
EXACT_IMAGE_AUTHORITIES=HA_EXACT_DIGEST+BROKER_EXACT_DIGEST+MANAGER_EXACT_SOURCE_BUILD_BOUND_ARTIFACT
RECALCULATED_PEAK_REQUIRED_BYTES=DYNAMIC_PER_IMAGE_EXACT_ENVELOPE;F1_CAPACITY_SIDECAR_REQUIRED
OBSERVED_CAPACITY_REFERENCE_BYTES=9229160448
CAPACITY_MARGIN_BYTES=F2_REQUIRED;NO_LIVE_CAPACITY_PROMOTION_IN_F0
F1_MINIMAL_CHANGE_LIST=11_BOUNDED_ITEMS_FROZEN
F1_REQUIRED_TESTS_AND_WORKFLOWS=FOCUSED_TRANSPORT+BOOTSTRAP+PROVISIONING+SYSTEMD+HOST_ONLY+EXACT_ARM64+DEPLOYMENT_GATE+HA_ISOLATED+INGRESS_GUARD+PUBLIC_SAFETY

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

F0_RESULT=CLOSED_PASS_SOURCE_DESIGN
NEXT_ROUTE=F1_INSTALLER_AND_TRANSPORT_SOURCE_REPAIR_DECISION
STOP=true

=== END ===
```
