# N3-W T1 Broker OTA V1.0 — B1 设计冻结与 B2 动态镜像绑定实施说明

DATE=2026-11-21  
PROJECT=温室环境监测系统（ESP32-C6）/ N3-W  
STATUS=REVIEW_ONLY  
PRODUCT_AUTHORITY=T1_Core_Stack_OTA_V1.2  
STACKED_BASE_PR=815  
STACKED_BASE_HEAD=9dc2eed89cfb3ccdb9d08c3d3555b61668dcbb1d  
LIVE_T1_AUTHORITY=false  
PRODUCTION_MUTATION=false  

## 1. B1 冻结结论

Broker OTA 复用宿主 `T1_Core_Updater` 和 Generic V2，不建立 Broker 专用 OTA daemon、第二套事务账本或第二套状态机。

首版范围冻结为：

```text
BROKER_OTA_PROFILE=IMAGE_ONLY_V1
BROKER_IMAGE_BINDING=GH_BROKER_IMAGE
USB_REQUIRED=false
BROKER_RECOVERY_POINT_REQUIRED=true
TLS_CA_MUTATION=false
DYNSEC_MIGRATION=false
FINAL_RESULTS=SUCCESS|FAILURE
```

Broker 新版一旦启动，后续失败回滚按“Broker 持久状态可能已被写入”处理；B3 以后必须恢复升级前静止恢复点，而不是尝试推断 `mosquitto.db` 是否真的发生变化。

## 2. 与 V1.2 的关系

V1.2 继续是产品级上位合同：

- 唯一特权执行器为 `T1_Core_Updater`；
- Broker 走 Generic V2 方向并单独验证持久状态；
- 仅 Manager/Broker 变化时优先本机恢复，容量不足则停服前拒绝准入；
- 最终只有 `SUCCESS` 或 `FAILURE`；
- status/checker/UI 不得成为恢复引擎上游依赖；
- 客户现场验收回答“装对了吗、受影响功能恢复了吗、触及的数据还在吗”三个问题。

本阶段不改变这些合同。

## 3. 当前源码事实

当前 fresh product template 已使用三组件动态绑定：

```text
GH_MANAGER_IMAGE
GH_HOMEASSISTANT_IMAGE
GH_BROKER_IMAGE
```

fresh bootstrap 也已经把三条 image binding 写入独立的 `/etc/n3wfc4/docker-compose.env`。

但是历史/当前实机兼容路径仍可能看到 Broker：

```text
image_binding_mode=legacy_static
```

现有 Generic V2 host 只允许 Home Assistant 从 `legacy_static` 原子收敛到 dynamic；Broker 会被 `broker_runtime_template_convergence_required` 拦截。因此 B2 的真实缺口不是重新设计 Compose，而是让当前 legacy-static Broker 能在同一事务内安全进入已经冻结的 `GH_BROKER_IMAGE` 模式。

## 4. B2 修改边界

B2 只负责 runtime-template binding convergence：

```text
legacy Broker literal image
+ no GH_BROKER_IMAGE env line
        |
        v
atomic convergence preserving same predecessor image
        |
        v
dynamic Broker template
+ GH_BROKER_IMAGE=<predecessor>
        |
        v
Generic V2 changes GH_BROKER_IMAGE predecessor -> target
```

必须满足：

1. 收敛前后，在写 target binding 之前，Broker 的有效 image 不变；
2. 只能改 Broker image source 和对应 env line；
3. Manager/HA image、ports、mounts、TLS、DynSec、networks 和 security contract 不得变化；
4. Compose/env 两个文件中任一写入失败时恢复原始 exact bytes；
5. 回滚到 legacy predecessor 时恢复原 literal Compose 和删除事务引入的 `GH_BROKER_IMAGE`；
6. 重复或歧义的 Broker env binding fail closed；
7. 已经 dynamic 的 Broker 沿用现有 Generic V2 原子单行替换，不走 convergence；
8. 不访问 T1、不停止服务、不加载镜像、不修改 Broker state。

## 5. 源码落点

B2 复用并泛化已有 HA convergence，不新建版本化重复模块：

- `tools/n3w_t1_core_updater_v2_common.py`
  - 把 legacy-static Compose/env convergence/restore 泛化到 component；
  - 保留已评审 HA wrapper，避免 HA 路径回归。
- `tools/n3w_t1_core_updater_host.py`
  - Broker `legacy_static` 成为可规划状态；
  - Generic host convergence 支持 HA/Broker；
  - rollback 能恢复 Broker legacy-static predecessor。
- `tools/n3w_t1_core_updater_v2.py`
  - plan 输出真实组件名，例如 `converge_broker_runtime_template`。
- `tests/tools/test_n3w_t1_core_updater_a2.py`
  - Broker legacy-static 准入；
  - static -> dynamic -> exact static round trip；
  - 第二文件写失败 exact-byte 恢复；
  - duplicate env fail closed；
  - Broker plan action contract。

## 6. 非本阶段范围

```text
BROKER_STATE_SNAPSHOT=false
BROKER_STATE_RESTORE=false
BROKER_TARGET_RELEASE=false
BROKER_LIVE_APPLY=false
BROKER_T1_PREFLIGHT=false
BROKER_CERT_ROTATION=false
BROKER_DYNSEC_MIGRATION=false
MULTI_COMPONENT_COMMIT=false
MERGE_TO_MAIN=false
```

这些分别属于 B3/B4/B5 以后。

## 7. B2 完成条件

```text
B1_DESIGN_ARCHIVED=true
BROKER_LEGACY_STATIC_CONVERGENCE_IMPLEMENTED=true
HA_EXISTING_CONVERGENCE_COMPATIBILITY_PRESERVED=true
BROKER_BINDING_ROUNDTRIP_TEST_ADDED=true
BROKER_AMBIGUOUS_BINDING_FAIL_CLOSED_TEST_ADDED=true
BROKER_PARTIAL_WRITE_ROLLBACK_TEST_ADDED=true
BROKER_PLAN_CONVERGENCE_TEST_ADDED=true
PUBLIC_REPOSITORY_SAFETY_REQUIRED=true
GITHUB_CI_REQUIRED=true
LIVE_T1_REQUIRED=false
```

B2 通过只代表“Broker 动态镜像绑定源码准备完成”，不代表 Broker OTA 已经完成。B3 必须建立并验证 Broker 持久状态恢复点。
