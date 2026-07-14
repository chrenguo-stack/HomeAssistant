# greenhouse-manager 身份迁移回滚后只读审计 V1

- 阶段：M2.4g-6t
- 状态：Draft
- 范围：manager-only 生产事务完成标准 rollback 后的正式闭环
- 关联：Issue #17；6i fresh rollback、6l orchestrator、6n runtime probe、6o execution packet

## 1. 目的

本协议把回滚后的判断从一次性诊断脚本收敛为可复用、可测试、只读且脱敏的审计合同。审计只判断 rollback 是否把 `greenhouse-manager` 恢复到 claim 前状态，不授权再次执行迁移、创建授权、修改服务或清理不明目录。

## 2. 基线

新生成的 migration preparation 和 fresh rollback 必须保存三个认证变量的脱敏状态：

- `GH_MQTT_USERNAME`
- `GH_MQTT_PASSWORD`
- `GH_MQTT_PASSWORD_FILE`

每项只保存：

```json
{"present": true, "nonempty": false}
```

不得保存实际值。键不存在、键存在但为空、键存在且非空是三个不同状态。

优先从 transaction snapshot 或 fresh rollback 读取该基线；也可使用绑定的 preclaim diagnostic 或 migration preparation。缺少基线时必须输出：

```text
baseline_unavailable=true
rollback_audit_passed=false
manual_recovery_required=false
manual_review_required=true
```

“基线不可用”本身不是运行状态漂移，也不得自动解释为必须手工恢复。

## 3. 精确事务目标

审计只检查本事务可能创建的精确目标：

- manager auth Compose overlay；
- manager auth environment file；
- manager password target；
- manager password bind mount；
- directory contract 明确列出的 created directory targets。

Compose working directory、项目根目录或其他正常业务目录不得作为“应为空/应删除”的目标。报告必须固定输出 `broad_compose_directory_considered=false`。

## 4. 通过条件

`rollback_audit_passed=true` 至少要求：

1. journal phase 为 `rollback_completed`；
2. `rollback_completed=true` 且 `rollback_failed=false`；
3. 三个认证变量的 present/nonempty 状态均与 preclaim 基线一致；
4. auth overlay、auth environment 和 password target 不存在；
5. password mount count 为 0；
6. exact created directory targets 已清理或与基线一致；
7. manager 运行、restart count 为 0、存在稳定 MQTT socket；
8. manager 镜像保持不变；
9. Mosquitto 与 Home Assistant 身份保持不变；
10. anonymous retained compatibility path 可读。

只有全部条件和基线都可证明时才允许正式闭环。

## 5. 恢复与补证判定

- 已观察到 journal/服务/目标/环境漂移：`manual_recovery_required=true`。
- 唯一缺口是没有 preclaim 基线：`manual_recovery_required=false`、`manual_review_required=true`，先补充只读证据。
- 审计模块不得执行删除、重建、Compose、MQTT publish、授权 claim 或凭据写入。
- 普通报告不得包含 secret、完整 Client ID、环境值或路径。

## 6. 当前生产事故的使用方式

针对 2026-07-14 已完成标准 rollback 的事务，先用修正版只读工具取得保存的 transaction snapshot、preclaim/migration preparation 基线和当前运行观察，再调用本合同。不得重跑旧 6Q/6R/6S，不得复用已消费授权。只有审计正式通过后，才允许从新 `main` SHA 重新生成整条证据链。
