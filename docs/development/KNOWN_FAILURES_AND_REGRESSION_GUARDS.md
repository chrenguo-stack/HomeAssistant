# KNOWN_FAILURES_AND_REGRESSION_GUARDS

> 目的：快速定位并闪避本项目已经实际发生过的问题。  
> 本文件是索引，不替代交接文档、CI、decision/status 文档或 private evidence。

## 使用规则

1. 新会话、新 successor、重要诊断或物理执行前，先阅读本文件。
2. 后续遇到新的实际问题时，除完成对应代码/文档归档提交外，必须在本文件追加一条“现象—根因—修复/闪避”记录。
3. 根因尚未确认时写 `TBD`，不得把推测写成已知根因。
4. 相同根因的重复失败合并到同一条，不按每次 authorization/timeout 机械新增。
5. 能转成 CI、单元测试、执行器断言或 preflight gate 的问题，必须优先形成机器可检查的 regression guard。
6. `CONSUMED_FAILED` 的物理授权永久不可重放；新物理执行必须使用新的唯一授权。

状态：`OPEN` = 尚未根治；`GUARDED` = 已修复且有回归保护；`RESOLVED` = 已修复，但主要依靠流程/环境约束。

## 快速索引

| ID | 阶段 / 模块 | 现象 | 根因 | 修复 / 闪避规则 | 状态 |
|---|---|---|---|---|---|
| KF-001 | H3/N2 Stage 2D-1 | ESPHome 实验主机名过长导致完整 RC2 配置失败 | 名称长度超过 ESPHome 约束 | 编译前做节点名长度门禁；测试名保持短且确定 | GUARDED |
| KF-002 | H3/N2 Stage 2C-2 | RAM-only 门禁把后继 NVS 代码误判为当前阶段越界 | 扫描整个共享组件目录，scope 过宽 | 阶段门禁必须使用明确 source allowlist，不得递归扫描共享目录全部内容 | GUARDED |
| KF-003 | H3/N2 Stage 2D-9R | `IMMUTABLE_PAYLOAD_INVALID`，物理授权被消费失败 | shell launcher 与 Python wrapper 对 immutable payload handoff 语义不一致 | shell→wrapper 必须做真实集成测试；冻结 payload 合同只保留一个 authority | GUARDED |
| KF-004 | M2 source fetch | 出现 `bound_repository_fetch_failed`，无法取得 exact commit | 临时网络/仓库获取失败，不是 source regression | fetch failure 与代码故障分开分类；先独立验证 exact SHA 可获取，禁止为网络失败修改源码 | RESOLVED |
| KF-005 | M2 Manager runtime probe | 健康 Manager 被 probe 误判并触发回滚 | 节点约 60s 上报，而 probe 只等待约 35s | telemetry probe 窗口必须覆盖真实发布周期并留裕量；当前采用更长观察窗 | GUARDED |
| KF-006 | M2 V60 tooling | `base_patch_binding_invalid` | 工具假定源码包固定目录布局 | 基础源码按内容 / blob 定位，不依赖归档目录名称或层级 | GUARDED |
| KF-007 | M2 V66 tooling | `embedded_patch_set_invalid` | 脚本硬编码 patch 数量，与实际冻结集合不一致 | 禁止 magic count；从冻结 patch 集合本身计算并精确比较 | GUARDED |
| KF-008 | H0/H1 backup V1 | secret-output guard 假阳性 | 使用过宽 substring 匹配 | secret guard 使用结构化字段/精确模式；禁止无边界字符串搜索 | GUARDED |
| KF-009 | H0/H1 backup V2 | 找不到 / 误定位 `dynamic-security.json` | 按 Mosquitto config mount 推测路径，实际文件位于 data mount | 运行时路径必须从实际 container mounts/bindings 解析，不凭经验推断 | GUARDED |
| KF-010 | N3-W P5 M01 | physical/test oracle 报失败，但后续证据证明 Direct 产品路径正常 | 测试 oracle 假阴性 | oracle failure 与 product failure 分离；使用 canonical/live evidence 交叉验证后再归因 | GUARDED |
| KF-011 | N3-W P5 M02 | Relay ingress 全部 `aead_backend_unavailable` | production Manager runtime 缺少 `cryptography` | 依赖必须在最终 production image/runtime 内验证；不能仅依赖开发环境或普通 CI | GUARDED |
| KF-012 | N3-W P5 Broker | Broker 实际可运行却被 healthcheck 判 unhealthy | Compose healthcheck shell quoting 错误 | healthcheck 必须有实际容器 runtime regression；复杂 quoting 不靠静态目测 | GUARDED |
| KF-013 | N3-W P5 Manager state | Manager 无法正常访问 `/state` | state tree 为 root/0700，与容器 uid/gid=999 不匹配 | Manager 启动前校验 state tree owner/mode 与容器运行 UID/GID | GUARDED |
| KF-014 | Phase 4 R3/R4 firmware | A 配对后两次 `MANAGER_INGRESS_TIMEOUT`；R4 serial 明确 `Simplified N3-W runtime start failed error=3`，runtime/telemetry 均未 active | connected STA channel mutation 未被 R3 修复完整消除；R4 证明 `runtime_.start -> port_->set_radio_channel -> radio_.set_channel -> esp_wifi_set_channel` 的间接路径仍存在，`error=3` 对应 `RADIO_FAILED` | connected STA 下，相同已占用 channel 的请求必须视为 no-op success；不同 channel 必须拒绝；仅 STA 未连接时允许 driver 改 channel。该修复已由后继 Phase 4 R5 冻结 evidence 验证，并由 source/runtime regression 覆盖；不得重放 R3/R4 | GUARDED |
| KF-015 | Phase 4 CI | M2 board-lab 首次 full RC2 compile 失败，相同 exact HEAD rerun PASS | 瞬态 runner/dependency failure | identical-head rerun PASS 后归类 transient；禁止无依据做 speculative source change | GUARDED |
| KF-016 | Assistant / diagnostic tooling | R4 postfail triage 扫描 1131 个文件，混入 `.venv/`、`source/`、`.pyc`，污染 runtime evidence | 使用宽泛 recursive scan，而非 runtime evidence allowlist | runtime triage 只读明确 evidence allowlist；永久排除 `.venv/`、`source/`、`build/`、`.git/`、`__pycache__/`、`*.pyc`；异常文件数直接 STOP | GUARDED |
| KF-017 | Phase 4 R4 physical E2E | A clean/pairing 后再次 `MANAGER_INGRESS_TIMEOUT`，B 尚未进入 | 已确认属于 KF-014：间接 connected-STA channel mutation 使 `SimpleProductRuntime::start()` 返回 `RADIO_FAILED`；Broker TLS/node session 已成功，不是当前阻塞点 | R4=`CONSUMED_FAILED`、永久禁止重放；后继 R5 已在新授权/新 exact-head 下完成 clean two-board E2E，原阻塞链关闭；继续由 KF-014 regression guard 防回退 | GUARDED |
| KF-018 | F1.0 / RS485 soil hardware | 土壤传感器一度无读数 | PCB 电阻虚焊，非固件问题 | 通讯异常先做供电/焊点/电阻/物理链路检查；硬件缺陷未排除前不得过早改协议代码 | RESOLVED |
| KF-019 | Assistant / GitHub source editing | source-only 修复时曾用不完整文件视图做整文件替换，短暂引入与目标无关的 HTTP/pairing source drift；随后通过 exact-base compare 检出并恢复 | 将局部修复错误实现为整文件替换，且未先验证 replacement 内容与 exact base 的完整差异 | 修改前读取 exact-base blob；提交后立即执行 `base..head` changed-file/hunk allowlist；出现任何非目标 hunk 立即恢复。禁止用截断/局部视图重建整个源码文件 | GUARDED |
| KF-020 | N3-W Phase 5-B source contract | active-header slicing 出现 false failure | 用第一个 legacy `#ifdef` 作为 active/legacy 分界，实际命中了错误的条件编译块 | source contract 必须精确定位最终 legacy include gate，再切分 active surface；禁止依赖“第一个 `#ifdef`”之类位置假设 | GUARDED |
| KF-021 | N3-W Phase 5-B legacy radio packaging | frozen S5 legacy radio compile/package boundary 多次因 build flag / external-component packaging 规则失配而失败 | ESPHome 2026.4.3 不支持 `esphome.build_flags`；正确入口为 `platformio_options.build_flags`；`.inc` 不随 external component source packaging 携带，而普通 `.h` 又会泄漏到 active compile | legacy radio 只允许通过独立 opt-in legacy component / explicit build gate 注入；normal RC2 不得定义 legacy radio macro | GUARDED |
| KF-022 | N3-W Phase 5-D/E CI | source authority 已退休后，仓库仍残留绑定旧 exact-base / finite grant / S5 successor 的 live workflows，产生无意义 skip/failure 并继续宣示旧架构 | CI 生命周期未与产品架构退休同步；历史验证 workflow 被长期当成当前 CI | P5-E 仅保留当前产品 regression CI；旧 successor/S2/S3/S5/P5 live workflows 已统一退休，历史事实由 Git history/交接/evidence 保留；P5-E absence guard 阻止重新引入 | GUARDED |
| KF-023 | N3-W Phase 5-D/E firmware | normal RC2 已不使用旧 product runtime，但 `greenhouse_n3w_product_core` / `greenhouse_n3w_product_runtime` 仍以 canonical-looking 名称存在，并被旧 CI 消费 | P5-C/P5-D 为迁移和旧测试保留了实现，live CI 退休晚于 active runtime promotion | exact-current reference scan 后已删除 canonical-looking retired product runtime 及其 S2/S3 tests；P5-E absence guard 要求 normal RC2/current runtime 不得重新引用或恢复这些目录 | GUARDED |
| KF-024 | N3-W Phase 5-D registration | 简化后仍曾保留 operator-supplied `registration approve --node-id`，与自动 NODE_ID 产品合同冲突 | registration CLI 沿用了旧管理员指定 NODE_ID 接口 | `approve` 改为 `AutomaticNodeIdApprover` 自动生成 opaque NODE_ID；P5-E regression guard 明确断言 approve 无 `--node-id` 并拒绝该参数 | GUARDED |
| KF-025 | C-06 regression CI | 有用的 C-06 host regression 曾被旧 lineage/exact-main gate 阻塞，导致当前代码变化时产生与功能无关的失败 | regression coverage 与一次性历史 lineage/evidence 合同耦合 | C06-B1/B2B/history workflow 已收敛为 current host regression，移除旧 lineage authority / 重复 isolated evidence workflow | GUARDED |
| KF-026 | N3-W Phase 5-E regression guard | 新增 simplification guard 后，greenhouse-manager CI 连续在 Ruff `I001`/`SIM300` 停止，pytest 未执行 | 手写新测试未先完全匹配仓库 Ruff import-block 与 SIM 规则；第一次修正又误解了 Ruff 对 import block 后空行的要求 | 以 exact CI Ruff 输出为唯一格式 authority，逐项修正且每个新 HEAD 只做一次 focused validation；最终 `greenhouse-manager CI/test` 的 Lint+Test 已 PASS | GUARDED |

## 固定回归规则

以下规则适用于所有后续阶段：

- **Evidence scope**：运行时结论只来自明确 runtime evidence；源码、CI、venv、build 输出不能冒充现场证据。
- **Exact binding**：物理执行前必须重新绑定 exact HEAD / tree / artifact hash；文档提交导致 HEAD 改变时，不得自动继承旧 artifact 的 exact-head 资格。
- **Claim boundary**：`AUTHORIZATION_CLAIMED=true` 后任何失败都 fail-closed；同一 authorization 永久不可重放。
- **Failure classification**：网络获取失败、CI 瞬态失败、测试 oracle 失败、产品真实故障必须分别分类。
- **Single authority**：文件路径、payload、credential、canonical state 等关键事实不得由多个位置各自猜测。
- **Host-first diagnosis**：能够通过 host-only/private evidence 定位的问题，不先增加板卡写操作或新的物理授权。
- **No speculative fix**：根因未证实前，不以“试试看”的方式修改生产路径或物理固件。
- **Exact-base source edit**：源码局部修复必须以 exact-base blob 为输入；提交后必须做 changed-file/hunk allowlist，禁止由截断视图重建整文件。
- **Architecture retirement**：产品 authority 退休时，source / test / workflow / admin / config 必须同阶段收口；禁止 live CI 长期宣示已退休产品语义。
- **Historical quarantine**：历史兼容实现若必须保留，名称和引用必须显式表明 `_legacy` / `s5` / lab / historical 身份；normal product runtime 不得导入。
- **Automatic NODE_ID**：正常 registration approve 不允许操作者输入 NODE_ID；NODE_ID 由 Manager 自动分配且退役后不复用。

## 维护模板

新增问题时复制下面 1 条即可，不需要长篇事故报告：

```text
| KF-XXX | 阶段/模块 | 现象 | 根因（未知写 TBD） | 修复 / 闪避 / regression guard | OPEN/GUARDED/RESOLVED |
```

详细证据继续放在对应 PR、交接文档、decision/status 文档、CI 或 private evidence 中。