# 温室环境监测系统（ESP32-C6）
## N3-W Phase 5-C 收口与 Phase 5-D 启动前开发交接文档

**版本：** V1.0  
**日期：** 2026-08-18  
**仓库：** `chrenguo-stack/HomeAssistant`  
**PR：** #324 `refactor(n3w): simplify security and adopt long-lived peer trust`  
**用途：** 结束当前长上下文会话，在新会话中以最小重复验证成本继续 P5-D。

> 本文档归档的是 **P5-C 源码边界**。归档前 PR exact HEAD 为 `910ac90edc293369fda9f8aed74fdb269afdf612`、tree 为 `fcb0d405e57fb8e474f648bab085fe187fc6db3e`。将本文档提交到同一分支会产生一个新的 **docs-only archive HEAD**；新会话应把该文档提交视为允许的纯文档 delta，而不是重新审查 P5-C 技术实现。

---

# 0. 交接结论

```text
PHASE4_CLEAN_ISOLATED_TWO_BOARD_E2E=PASS/FROZEN
P5_A_SIMPLIFIED_MANAGER_RUNTIME_PROMOTION=PASS/FROZEN
P5_B_FIRMWARE_RADIO_SLIMMING=PASS/FROZEN

P5_C_CREDENTIAL_DECOUPLING=PASS
P5_C_LEGACY_PRODUCT_AUTHORITY_QUARANTINE=IMPLEMENTED
P5_C_MANAGER_PATH_OWNERSHIP_QUARANTINE=IMPLEMENTED

SOURCE_IMPLEMENTATION_FAILURE=false
LEGACY_CI_SCOPE_CONTRACT_BLOCKER=true

P5_C=SOURCE_COMPLETE_PENDING_LEGACY_CI_RETIREMENT

NEXT_GATE=
P5_D_LEGACY_TEST_CI_CONFIG_ADMIN_CLEANUP
```

当前不应再在旧会话继续 P5-D。新会话只需做一次当前边界只读复核，然后进入 P5-D。

---

# 1. 开发纪律：ONE_BOUNDARY_ONE_VALIDATION

后续必须遵循：

```text
ONE_BOUNDARY_ONE_VALIDATION
```

规则：

1. 一个状态边界只做一次必要验证；
2. Phase 4、P5-A、P5-B 已冻结，不因进入 P5-D 而重新验证；
3. 不重复检查已明确 PASS 的 exact SHA、artifact SHA、旧 CI、旧 physical evidence；
4. 仅在 branch/HEAD 真实漂移、新 exact-head CI、新矛盾输出或用户明确要求时重新检查；
5. 不 rerun 历史失败 workflow 来“确认”已知失败；
6. 对可信 executor / GitHub CI 的 terminal result 直接判定，不附加无意义二次验证。

---

# 2. PR #324 源码边界

归档前 PR 状态：

```text
STATE=OPEN
DRAFT=true
MERGED=false
MERGEABLE=true

BASE_BRANCH=
feature/n3w-product-completion-s5-r7-private-telemetry-stimulus-20260815-v1

BASE_SHA=
ab0adabe7d66c389f0496cf6d8386832c67debfe

HEAD_BRANCH=
feature/n3w-security-simplification-long-lived-peer-trust-20260816-v1

SOURCE_BOUNDARY_HEAD=
910ac90edc293369fda9f8aed74fdb269afdf612

SOURCE_BOUNDARY_TREE=
fcb0d405e57fb8e474f648bab085fe187fc6db3e
```

未经单独授权：

```text
DO_NOT_MARK_READY=true
DO_NOT_MERGE=true
```

## 2.1 1230e8c → 910ac90 的 net-zero bookkeeping

P5-C 第二部分核心提交：

```text
1230e8c0ad8379bebd601557f52b737264319d57
refactor(n3w): quarantine legacy product authority
```

随后出现：

```text
589ad9885177af31e69d6d82009ac077ed417e44
chore(n3w): reserve p5c change
```

仅增加临时文件：

```text
host/greenhouse-manager/tests/runtime/.p5c-placeholder
```

之后：

```text
910ac90edc293369fda9f8aed74fdb269afdf612
chore(n3w): remove temporary p5c placeholder
```

再次删除该文件。

因此：

```text
TREE(1230e8c)=fcb0d405e57fb8e474f648bab085fe187fc6db3e
TREE(910ac90)=fcb0d405e57fb8e474f648bab085fe187fc6db3e
NET_SOURCE_CHANGE_FROM_1230e8c_TO_910ac90=ZERO
```

新会话不得把这两个 bookkeeping commit 当成新的技术实现重新审查。

---

# 3. Phase 4：PASS / FROZEN

授权：

```text
D1-N3W-PHASE4-CLEAN-ISOLATED-TWO-BOARD-E2E-PHYSICAL-EXECUTION-SUCCESSOR-R5-20260818-01
```

终态：

```text
R5=CONSUMED_PASS
R5_REPLAY_ALLOWED=false
PHASE4_CLEAN_ISOLATED_TWO_BOARD_E2E=PASS
TERMINAL=PASS
```

冻结绑定：

```text
PHASE4_EXACT_HEAD=d5ccf7f53e450eb46a2285b0c6d8f41403ea0df7
TREE=6c0e0eedefb701e8f9ad0cc1214c2e95cd78febb
FACTORY_SHA256=604f090d6f8009f93270f3c8907bbb2faa3738ae92bc9d31e4ad10f1f871adcf
```

R5 已物理证明：同一通用 factory image、目标 NVS erase、独立 first-use pairing、不同 NODE_ID、Direct MQTT、B Direct 失效后通过 A Relay、Relay→MQTT→Manager canonical ingress、Direct 恢复、同一 boot session `SEQ 2 → 6 → 8`，且：

```text
PEER_TRUST_GENERATION=1
FINITE_GATEWAY_GRANT_USED=false
PATH_OWNERSHIP_USED=false
```

未访问/修改生产网络、Broker、Manager、HA；未进入 N3-L；未复用旧 S5 R8 private state。R3/R4 均为 `CONSUMED_FAILED / NON_REPLAYABLE`，不得重放。

---

# 4. P5-A：PASS / FROZEN

提交：

```text
8c30c86db945c3d874550fceec76bfa5c7d595cf
refactor(n3w): promote simplified manager runtime
```

结果：

```text
P5_A=PASS/FROZEN
TOTAL=17
SUCCESS=16
SKIPPED=1
FAILED=0
```

正常 Manager runtime 已切到 simplified N3-W service；active runtime 不再实例化旧 `N3wPathLeaseCoordinator`、`PathLeasePolicy`、finite gateway grant authority、legacy relay authorization runtime。`SqliteNodeApplicationKeyProvider` 仅作为 transitional read-only application-key adapter。不得重验。

---

# 5. P5-B：PASS / FROZEN

最终提交：

```text
2ad471608b259774b44f4cc97de4a4f4bc28e99a
fix(n3w): isolate legacy radio in opt-in component
```

结果：

```text
P5_B=PASS/FROZEN
TOTAL=20
SUCCESS=16
SKIPPED=4
FAILED=0
```

active radio 已删除 fragmentation / receipt ACK / retry / cache / reassembly / resend-reorder machinery；保留 `MacAddress`、`LinkKey`、`ChannelScanPlan`、`LocalPathState/Policy/Controller` 等必要基础能力。

legacy radio 最终隔离为独立 opt-in component：

```text
greenhouse_n3w_core
  ├─ active simplified radio
  └─ n3w_radio_legacy.h

greenhouse_n3w_legacy_radio
  ├─ __init__.py
  ├─ n3w_radio.h
  └─ n3w_radio_legacy_impl.cpp
```

旧 implementation exact blob：

```text
04fe60f7b2a79962c28c3a5e0705cbd81e4a825a
```

不得重验。

---

# 6. P5-C 第一部分：credential contract 解耦 PASS

提交：

```text
d19668e089a6fcc22d575f7bdb73d2227f5a81f1
refactor(n3w): decouple simplified credential contract
```

exact-head CI：

```text
TOTAL=20
SUCCESS=16
SKIPPED=4
FAILED=0
```

新增中立：

```text
host/greenhouse-manager/src/greenhouse_manager/runtime/n3w_credential_contract.py
ProductCredentialSource
```

`n3w_simplified_credentials.py` 已取消对 `n3w_product_pairing.ProductCredentialBundle` 的依赖，改为 `ProductCredentialSource`；Setup Secret、`SYSTEM_PEER_KEY`、`PEER_TRUST_GENERATION`、per-node MQTT/application credential、AES-GCM delivery 保持不变。Generic H3 pairing primitives 不删除。

---

# 7. P5-C 第二部分：legacy authority / PATH ownership quarantine

核心提交：

```text
1230e8c0ad8379bebd601557f52b737264319d57
refactor(n3w): quarantine legacy product authority
```

7 个旧 authority/runtime 模块实现迁入 `*_legacy.py`：

```text
n3w_ingress_router.py              -> n3w_ingress_router_legacy.py
n3w_path_lease.py                  -> n3w_path_lease_legacy.py
n3w_product_manager_adapter.py     -> n3w_product_manager_adapter_legacy.py
n3w_product_mqtt_service.py        -> n3w_product_mqtt_service_legacy.py
n3w_product_pairing.py             -> n3w_product_pairing_legacy.py
n3w_product_peer_authorization.py  -> n3w_product_peer_authorization_legacy.py
n3w_runtime_wiring.py              -> n3w_runtime_wiring_legacy.py
```

原 canonical module path 仅留兼容 shim，等待 P5-D 清理旧 tests/workflows。迁移语义：

```text
LEGACY_IMPLEMENTATION_REWRITTEN=false
```

被隔离的旧 authority 包括 `ProductSecurePairingCoordinator`、`PeerAuthorizationService`、`N3wPathLeaseCoordinator`、`PathLeasePolicy`、`N3wManagerIngressRouter`、`ReplayRegistryPathAuthority`、finite peer authorization、old Manager PATH ownership/runtime wiring。

新增 regression：

```text
host/greenhouse-manager/tests/runtime/test_n3w_phase5c_legacy_authority_quarantine.py
```

---

# 8. 当前 active Manager 架构边界

```text
app.py
  -> n3w_manager_runtime_wiring.py
  -> N3wSimplifiedManagerMqttService
  -> N3wSimplifiedIsolatedMqttService
  -> Phase4IsolatedManagerHarness
  -> N3wMultiIngressRouter
  -> N3wCanonicalIngressCoordinator
  -> CompactRelayIngressCore
```

必须保持：

```text
MANAGER_PATH_LEASE_AUTHORITY=false
MANAGER_FINITE_GATEWAY_GRANT_AUTHORITY=false
MANAGER_PATH_OWNER_STATE=false
TRANSPORT_INDEPENDENT_CANONICAL_CURSOR=true
```

Direct / Relay 是 ingress source，不再拥有 Manager current path。

---

# 9. P5-C 边界的 legacy CI 分类

在源码边界 `910ac90...` 已确认以下 4 条 legacy workflow failure：

1. `N3-W Manager persistent path lease CI`
   - run `32135476258`
   - failure step：`Verify exact authorized base and changed-file boundary`
   - syntax/Ruff/tests 均 SKIPPED
2. `N3-W Manager runtime wiring isolated CI`
   - run `32135476277`
   - failure step：`Exact base and scope gate`
   - Compile/Ruff/tests 均 SKIPPED
3. `N3-W Product Completion S4 Manager Registration CI`
   - run `32135476400`
   - failure step：`Exact base and S4 scope gate`
   - 后续核心 tests SKIPPED
4. `N3-W Manager relay authorization lifecycle CI`
   - run `32135476384`
   - failure step：`Exact base and scope gate`
   - Compile/Ruff/tests 均 SKIPPED

当前 PR 是 stacked PR，base 为 `ab0adabe...`；这些历史 workflow 绑定旧阶段 exact-base / narrow changed-file universe。因此冻结判断：

```text
SOURCE_IMPLEMENTATION_FAILURE=false
LEGACY_CI_SCOPE_CONTRACT_BLOCKER=true
```

**不得 rerun 这 4 条 workflow。** 它们本身就是 P5-D 的 deletion/modernization target。

源码边界同时已有多项 PASS，包括 Public repository safety、Manager unified ingress router、H3 pairing、C-07 retirement、ESP32-C6 frame core、S3 disconnected runtime、S5 board integration 等。S5 board integration PASS 继续证明 P5-B legacy radio quarantine 有效。

---

# 10. P5-C 最终分类

```text
P5_C_CREDENTIAL_DECOUPLING=PASS
P5_C_LEGACY_PRODUCT_AUTHORITY_QUARANTINE=IMPLEMENTED
P5_C_MANAGER_PATH_OWNERSHIP_QUARANTINE=IMPLEMENTED
SOURCE_IMPLEMENTATION_FAILURE=false
LEGACY_CI_SCOPE_CONTRACT_BLOCKER=true
P5_C=SOURCE_COMPLETE_PENDING_LEGACY_CI_RETIREMENT
```

不要因上述 legacy workflow failure 回滚 P5-C。

---

# 11. P5-D 准确范围

下一 gate：

```text
P5_D_LEGACY_TEST_CI_CONFIG_ADMIN_CLEANUP
```

P5-D 不重新设计 N3-W，只清理退出 active architecture 的外围遗留面。

## P5-D1 — legacy workflow inventory

分类哪些 workflow：

```text
DELETE
MIGRATE_TO_SIMPLIFIED_CONTRACT
KEEP_AS_VALID_CROSS_PRODUCT_REGRESSION
```

重点处理 old PATH lease、relay authorization、runtime wiring、S4 product authorization、旧 exact-main/exact-base gates。不得通过无条件放宽 scope 让红 CI 变绿。

## P5-D2 — legacy tests

优先删除只证明以下退休设计的测试：

- finite gateway grants；
- Manager PATH current-owner；
- PATH lease TTL/switch authority；
- N3-W product-specific X25519 wrapper；
- old peer authorization request/grant lifetime；
- old relay receipt/cache/reassembly。

通用 replay / registration / H3 secure pairing tests 不得误删。

## P5-D3 — config surface

在 active reference scan 证明无使用后，清理 PATH lease timing/window/grace、finite grant lifetime、legacy relay authorization paths、old isolated-product selectors、retired authority storage/config entries。

## P5-D4 — admin / CLI surface

清理 PATH ownership command、grant issue/revoke flow、old relay authorization inspection、old N3-W product-pair X25519 administration。

保留 registration、node retirement、MQTT credential lifecycle、generic H3 secure pairing、security-compromise-triggered `SYSTEM_PEER_KEY` rotation。

## P5-D5 — shim / quarantine 收敛

P5-C 的 canonical shim + `*_legacy.py` 只是迁移桥。P5-D 应逐项决定：

```text
DELETE
or
KEEP_QUARANTINED_AS_EXPLICIT_HISTORICAL_REGRESSION_REFERENCE
```

不得让 shim 长期伪装成 active product API。

---

# 12. P5-D 禁止事项

```text
NO_PRODUCTION_BROKER_MUTATION
NO_PRODUCTION_MANAGER_MUTATION
NO_HOME_ASSISTANT_MUTATION
NO_N3_L
NO_BOARD_ACCESS
NO_SERIAL_ACCESS
NO_FLASH
NO_ERASE
NO_RF_PHYSICAL_EXECUTION
NO_OLD_S5_PRIVATE_STATE_REUSE
NO_PR_READY
NO_PR_MERGE
NO_DESTRUCTIVE_DEPLOY
```

“删除 legacy source”不等于授权删除现场数据、Manager state DB、Broker state 或生产 credential。

---

# 13. Generic H3 pairing/X25519 边界

P5-C/P5-D 删除目标是：

```text
N3-W PRODUCT-SPECIFIC X25519 WRAPPER
```

不是整个项目的 generic H3 pairing security。`pairing_secure_transport`、generic X25519 primitives、H3/N2 secure pairing infrastructure 不得因 N3-W 简化而全局删除。

---

# 14. KNOWN_FAILURES / P5-E 待办

文件：

```text
docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md
```

P5-E/最终 closure 统一处理：

- KF-014 / KF-017：Phase 4 R5 已证明相关 repair 生效；不要重新物理验证，只依据冻结 evidence 更新状态；
- KF-020：P5-B source-contract slicing false failure，最终 guard 为精确剥离 final legacy include gate；目标 `GUARDED`；
- KF-021：ESPHome build flag + `.inc/.h` packaging 泄漏问题，最终由独立 opt-in legacy component 解决；目标 `GUARDED`。

P5-D 完成后进入：

```text
P5_E_REGRESSION_GUARDS_AND_KNOWN_FAILURES_CLOSURE
```

P5-E 再统一处理 active-source absence guards、PR body/documentation closure、legacy naming residue、config/CI/docs 一致性与 Phase 5 总收口。

---

# 15. 新会话只读复核规则

新会话只检查当前边界：

1. PR #324 仍为 Open / Draft / Unmerged；
2. current PR HEAD / tree；
3. stacked base 仍为 `ab0adabe7d66c389f0496cf6d8386832c67debfe`；
4. 对比当前 HEAD 与本文 `SOURCE_BOUNDARY_HEAD=910ac90...`：允许存在**仅本文档归档造成的 docs-only delta**；
5. 若还有 exact-head 非 terminal CI，只读取 terminal result 一次；
6. 只确认 legacy CI 是否仍是已知 exact-base/scope failure class；
7. 不重验 Phase 4、P5-A、P5-B；
8. 不重新读取/验证 R5 physical evidence；
9. 不 rerun 旧 failure；
10. 若发现超出本文档提交之外的真实 source drift，只分析该 delta。

---

# 16. 新会话启动提示词

```text
阅读 docs/development/温室环境监测系统_N3W_Phase5C收口与Phase5D启动前开发交接文档_V1.0_20260818.md，继续“温室环境监测系统（ESP32-C6）”项目的 N3-W Phase 5。

本轮只处理 P5-D：LEGACY TEST / CI / CONFIG / ADMIN CLEANUP，不处理 N3-L，不执行任何板卡、串口、Flash、RF 或生产 Broker/Manager/Home Assistant 操作。

严格遵循 ONE_BOUNDARY_ONE_VALIDATION。

先只读复核：
1. PR #324 是否仍为 Open / Draft / Unmerged；
2. current PR exact HEAD / tree；
3. stacked base 是否仍为 ab0adabe7d66c389f0496cf6d8386832c67debfe；
4. 本文 SOURCE_BOUNDARY_HEAD=910ac90edc293369fda9f8aed74fdb269afdf612；其后的本文档归档 commit 是允许的 docs-only delta，不要重新审查 P5-C 技术源码；
5. 只读取当前 exact-head 尚未 terminal 的 CI 终态；
6. 已知 legacy failures 为 persistent path lease / runtime wiring isolated / S4 Manager Registration / relay authorization lifecycle，均停在 exact-base/scope gate；不得 rerun，只确认没有新的 failure class。

不要重验 Phase 4、P5-A、P5-B，也不要重新检查既有 artifact/physical evidence。

冻结状态：
PHASE4=PASS/FROZEN
P5_A=PASS/FROZEN
P5_B=PASS/FROZEN
P5_C_CREDENTIAL_DECOUPLING=PASS
P5_C_LEGACY_PRODUCT_AUTHORITY_QUARANTINE=IMPLEMENTED
P5_C_MANAGER_PATH_OWNERSHIP_QUARANTINE=IMPLEMENTED
P5_C=SOURCE_COMPLETE_PENDING_LEGACY_CI_RETIREMENT

P5-C 核心源码提交：
d19668e089a6fcc22d575f7bdb73d2227f5a81f1
1230e8c0ad8379bebd601557f52b737264319d57

只读复核无新的 source drift 后，报告 P5_D_READY=true/false，并给出需要 DELETE / MIGRATE / KEEP 的 legacy workflow/test/config/admin 清单。

未经我明确授权，不 mark PR Ready，不 merge，不修改生产环境。
```

---

# 17. 最终交接状态

```text
PROJECT=温室环境监测系统（ESP32-C6）
PRODUCT_LINE=N3-W
PR=324
PR_STATE=OPEN_DRAFT_UNMERGED

SOURCE_BOUNDARY_HEAD=910ac90edc293369fda9f8aed74fdb269afdf612
SOURCE_BOUNDARY_TREE=fcb0d405e57fb8e474f648bab085fe187fc6db3e
STACKED_BASE_SHA=ab0adabe7d66c389f0496cf6d8386832c67debfe

PHASE4=PASS_FROZEN
P5_A=PASS_FROZEN
P5_B=PASS_FROZEN

P5_C_CREDENTIAL_DECOUPLING=PASS
P5_C_AUTHORITY_QUARANTINE=IMPLEMENTED
P5_C_PATH_OWNERSHIP_QUARANTINE=IMPLEMENTED
SOURCE_IMPLEMENTATION_FAILURE=false
LEGACY_CI_SCOPE_CONTRACT_BLOCKER=true
P5_C=SOURCE_COMPLETE_PENDING_LEGACY_CI_RETIREMENT

NEXT_GATE=P5_D_LEGACY_TEST_CI_CONFIG_ADMIN_CLEANUP
```
