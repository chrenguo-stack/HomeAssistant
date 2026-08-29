# N3-W / FC4 Board C P9 Executor / Oracle Incident Supplement

- 日期：2026-08-29
- 性质：public-safe known-failure supplement
- 目标：记录本轮实际发生、但不属于产品故障的 executor/oracle false negatives，供后续合并进 `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`。

## 1. 事故集合

本轮 P9 / Board C current-authority rebaseline 中实际发生过 4 个执行器/诊断 oracle 问题：

1. `ss` UDP listener 解析时使用了错误字段，曾把真实 listener 判成 0；修正 local-address field 后立即 PASS。
2. P3 首次查询错误使用 Mac local Docker，而不是已经冻结的 T1 remote Docker authority；重新绑定执行目标后 PASS。
3. SQLite inventory 的 `docker exec` heredoc 缺少 stdin attachment（`-i`），导致 intended Python body 没有进入容器；修正后 inventory PASS。
4. Broker discovery 使用 Docker format `.Labels` 当作 map 索引；当前 `docker ps --format` surface 中应使用 `.Label "com.docker.compose.service"`；修正后唯一 Broker discovery PASS。

这些结果均满足：

```text
PRODUCT_BLOCKER_PROVEN=false
SECURITY_PRODUCT_REGRESSION_PROVEN=false
FAIL_CLASS=EXECUTOR_OR_ORACLE_DEFECT
```

纠正后 P2、P3、P3-D0、P3-D1、P3-D2A/B/C、P4、P5、physical recapture 与后续 preclaim 均继续通过，因此没有证据支持把上述 false negatives 归因于 Board C、Manager、Broker 或 DynSec product regression。

## 2. 共同根因

共同模式不是单一产品 defect，而是 ad-hoc diagnostic executor 在调用真实 authority 前没有把以下边界全部机器绑定：

- execution target（local vs remote）
- process/container stdin transport
- Docker template surface
- command-output schema / field position

因此 shell/tooling 自身的假设可以产生“看似产品状态”的假阴性。

## 3. 回归/闪避规则

后续所有 runtime/preclaim executor：

1. 第一屏必须输出并验证 `EXECUTION_TARGET`；T1 runtime 查询不得默认使用 local Docker socket。
2. 需要通过 stdin 向 container Python 传脚本时，必须使用 `docker exec -i ... python -`，并有执行体确实运行的 sentinel/output contract。
3. Docker Compose service discriminator 使用 `.Label "com.docker.compose.service"` 或等价经过 smoke-test 的 surface；禁止假设 `.Labels` 是可索引 map。
4. `ss`/`netstat` 等 positional parser 必须先以当前平台真实输出做 smoke test，或改用更结构化的 owner/endpoint oracle；禁止未经验证硬编码 field number。
5. executor/oracle failure 只允许分类为 `EXECUTOR_OR_ORACLE_DEFECT` / `NOT_EVALUATED`，不得自动序列化业务字段为 `false`。
6. 连续两次 executor/preclaim failure 后，第三次前必须 route audit；成功 route audit reset fuse。

## 4. 建议 central index 条目

在合并该 documentation lineage 时，应先读取 `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` 的最新编号。如果 `KF-075` 仍未被占用，可使用：

```text
| KF-075 | FC4 Board-C P9 diagnostic executor authority/transport | P2/P3/DynSec discovery 多次出现 listener false-negative、误用 local Docker、container stdin 未连接、Docker label template 不兼容；纠正 executor 后相同产品状态立即 PASS | ad-hoc diagnostic executor 未在运行前机器绑定 execution target、stdin transport、Docker template surface 与 positional output schema，导致 tooling 假阴性被表现成业务状态 | runtime/preclaim 第一屏绑定 execution target；container heredoc 使用 `docker exec -i ... python -` 并验证 body sentinel；Compose service 使用已验证 `.Label` surface；positional parser 必须平台 smoke-test；未执行 authority 时保持 UNKNOWN/NOT_EVALUATED；两次连续 executor failure 触发 route audit | GUARDED |
```

如果编号已被占用，必须重新读取 central index 后选择下一个真实空号，禁止直接复用 `KF-075`。

## 5. 路线影响

```text
NORTH_STAR=FC4_FINAL_PHYSICAL_ACCEPTANCE
CURRENT_ROUTE_NODE=BOARD_C_FIRST_REGISTRATION
ACTIVE_DETOUR=NONE
PRODUCT_ROUTE_VALID=true
CURRENT_EXECUTOR_FAILURE_STREAK=0
ROUTE_AUDIT_REQUIRED=false
```

本补充记录不新增 product route branch，也不授权任何 mutation。
