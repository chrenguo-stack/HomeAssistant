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

| KF-027 | FC4 S4A local CI parity | 3 个 T1 CLI 子进程测试本地 full pytest 报 `ModuleNotFoundError: greenhouse_manager` | 主 pytest 使用 validation venv，但继承 PATH 中 `python3` 落到系统解释器 | 本地 CI parity 将 validation venv/bin 置于 PATH 首位；targeted + full pytest 共同保护 | GUARDED |
| KF-028 | FC4 S4A / node MQTT isolated lab | macOS 上 `/tmp` safety test 错误落到 `workspace must be empty` | `/tmp` resolve 为 `/private/tmp` 后与未 canonicalize 的 `Path("/tmp")` 比较 | 安全 guard 两侧统一 canonicalize，Linux/macOS 保持相同拒绝语义 | GUARDED |
| KF-029 | FC4 S4A / N3-W Manager selector | 旧 Phase5A selector test 触发 `AttributeError: n3w_product_pairing_enabled` | successor Settings 新增字段，旧 SimpleNamespace test double 未同步默认 false 合同 | test double 显式加入 `n3w_product_pairing_enabled=False`；production selector 不静默 getattr 降级 | GUARDED |
| KF-030 | FC4 S4A / pytest | `PytestReturnNotNoneWarning`，`test_settings` 返回 `PairingRuntimeSettings` | 测试 helper 使用 `test_` 名称，被 pytest 误收集为独立测试 | 重命名 `_pairing_runtime_settings`；full pytest 不得再出现该 warning | GUARDED |
| KF-031 | Assistant / FC4 S4A executor | repair executor 曾因 stdin collision 与 literal precondition mismatch 在写入前停止 | stdin 同时承载脚本/Ruff JSON；整段字符串匹配对源码 空白结构过敏 | 工具输出独立 subprocess capture；源码转换优先 AST/source-bound；写前 fail-closed | GUARDED |
| KF-032 | Assistant / FC4 S4B version archive | `VERSION_OCCURRENCE_SCOPE_DRIFT` 在 mutation 前停止 | 执行器把所有 `0.4.98` 字面量误当成当前 package version，未区分 H0/H1 冻结迁移合同和 provenance | 版本 bump 使用语义 allowlist：仅 package declaration 和 package-version regression 更新；历史合同版本必须精确保留 | GUARDED |
| KF-033 | FC4 Final Physical Acceptance / Manager startup | production-equivalent 配置启用 N3-W product pairing 时，simplified Manager 构造阶段触发 `GH_N3W_PRODUCT_PAIRING_ENABLED requires GH_N3W_RUNTIME_ENABLED` | 基类内部 `source_settings` projection 关闭 `n3w_runtime_enabled` 后，未同步关闭仅由外层 final-product composition 管理的 `n3w_product_pairing_enabled`，导致内部配置自相矛盾 | 保留 Phase 4 one-line runtime-disable source marker；对内部 projection 独立关闭 `n3w_product_pairing_enabled` 和 legacy `pairing_intake_enabled`；增加真实 constructor regression，断言三项内部标志均为 false | GUARDED |
| KF-034 | FC4 final-product pairing / Docker UDP publication | 实板已连接 LAN，但 registration 始终为空；同一 Manager `47111/udp` 单播发现成功、`255.255.255.255` limited broadcast 超时；把 publication 从单一 LAN IP 改为 `0.0.0.0` 后仍超时 | 设备固定发送 limited broadcast；Docker bridge / port-publication path 未把该广播传递给 Manager | 禁止用 Docker `ports` publication 承载 host-network Manager；当前部署门禁要求 Manager 使用 host network 且完全没有任何 `ports` 映射。进入 live 修复前还必须单独证明 Broker/TLS 连续性；也可后续实现并审计专用 host-side broadcast relay。部署前必须用 `tools/n3w_pairing_deployment_gate.py` 校验 rendered Compose JSON；失败的物理授权不得重放 | OPEN |
| KF-035 | FC4 host-network Manager / Broker TLS continuity | Manager 切换 host network 后持续以 `Network is unreachable` 重启；宿主机 `armbian` 解析为 `127.0.0.1`，但同一 Manager image 的 host-network runtime 实际优先解析为 `127.0.1.1`，仅发布 `127.0.0.1:8883` 不足 | 把宿主机解析结果错误当作容器内 host-network 解析 authority，没有在同一 image/network namespace 中做 `getaddrinfo()` binding | 切换前必须用 exact Manager image + host network 解析 Broker hostname，并把实际 loopback address 传给 deployment gate；Broker publication 必须同时精确满足 `host_ip=<resolved loopback>`、`target=8883`、`published=8883` 和 `protocol=tcp`，再以相同 image 验证 TCP+TLS server-name 后启动 Manager。禁止假定所有 loopback hostname 都落到 `127.0.0.1` | OPEN |
| KF-036 | FC4 first registration / expired pairing recovery | 广播链修复后 Manager 已有同一 hardware/pairing ID 的 `expired` session，重复 hello 被 replay guard 拒绝；仅重置板卡又会因 Manager current registration 保留相同 epoch 而触发 `generation_rollback` | pending TTL 已过、节点仍持有原 Setup Secret/派生 pairing ID；同时原 registration API/CLI 缺少“放弃 expired 且从未批准的首次注册”这一安全恢复操作 | 新增 `abandon-expired-first`：除人工确认外，还必须通过 Docker inspect 机器证明 exact Manager 容器为 exited/PID 0，且 registration/credential 两个宿主机数据库参数与容器 bind mount 精确对应；随后使用只读 credential history fail-closed 校验，只解除 expired/unapproved/no-credential registration 的 current 指针，永久保留旧 session/event 为 replay tombstone。拒绝运行中/身份不符的 Manager、数据库 binding 不符、pending、历史 NODE_ID/lease、任何凭据历史和缺失/不安全数据库。回归证明旧 identity 仍被拒绝，而同硬件的新 pairing identity/同 epoch 可重新进入 pending。板卡 pairing-state reset 与 live E2E 仍须新的物理授权 | OPEN |
| KF-037 | FC4 private-state materialization / host ownership | 容器内已证明运行身份为 `999:999`，但宿主机 `install -o 999 -g 999` 报 `invalid user: '999'`，授权在创建 private root 后消费失败 | 当前宿主 `install` 把 numeric owner 参数交给 NSS 名称解析；UID 999 没有 passwd entry，且容器 numeric UID/GID 本来就不等于宿主账户名 | 宿主目录先以 root owner 和精确 mode 创建，再使用 numeric `chown 999:999`；preclaim 分开验证容器运行 UID/GID 与宿主 NSS，不得把两者混为同一 identity authority。旧授权永久不可重放；后继授权显式接纳 partial state | OPEN |
| KF-038 | FC4 simplified pairing / health preclaim | P2B3D preclaim 把健康的 simplified endpoint 误判为失败：执行器期待 `gh.pair.health/1`，实际返回 `gh.pair.simple-health/1` | 执行器沿用 legacy/base pairing endpoint 的 schema，没有按 final-product endpoint composition 选择 health contract | simplified endpoint 必须精确返回 `gh.pair.simple-health/1`；legacy endpoint 保持 `gh.pair.health/1`。新增真实 simplified endpoint HTTP regression，live preclaim 必须绑定所部署 composition 的精确 schema | GUARDED |
| KF-039 | Development artifact archive / handoff | 多个有价值的 FC4 现场结果、临时 helper、私有 evidence hash 和板卡 readback 只留在临时目录或会话；下一物理边界前审计发现 6 组关键知识未归档 | 归档被推迟到开发/现场链结束后，且缺少每个 boundary 的强制 local sweep、公开/私有分类和 remote exact-binding 闭环 | 新增 repository-wide development artifact archive rules、AGENTS 强制入口、机器可读 sanitized manifest 和 manifest regression；`UNARCHIVED_CRITICAL_RESULT_COUNT != 0` 时只允许 archive recovery，不得开始新开发或物理边界 | GUARDED |
| KF-040 | FC4 KF-036 live executor / container stdin and DB path binding | 授权 claim、Manager 停止和私有 DB 备份完成后，isolated Manager-image recovery 返回 exit 0 但 result 为 0 bytes，JSON oracle 失败；postfail audit 证明两个 DB hash 均未变化、expired current pointer 仍在、Manager 已恢复健康 | executor 用 `python -` 从 stdin 读取程序，却漏加 `docker run -i/--interactive`，容器 stdin 被关闭后 Python 读取 EOF 并空执行；同时首次 preclaim 误用通用 registration DB 默认路径，而 FC4 实际路径多一层 `manager/` | 原授权永久禁止重放。successor 必须接纳 unchanged DB hashes 和 partial private evidence，使用 fresh evidence namespace；精确传入 FC4 registration/credential container paths；stdin 程序必须以 `--interactive` 传输；result 非空检查必须先于 JSON parse。机器可读 archive manifest regression 固定上述合同 | GUARDED |

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
