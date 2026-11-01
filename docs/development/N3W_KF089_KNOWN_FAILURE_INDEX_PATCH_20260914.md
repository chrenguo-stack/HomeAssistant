# KF-089 Known-Failure Index Closeout Patch

Status: `PUBLIC_SAFE_EXACT_EDIT_MERGE_READY`
Date: `2026-09-14`

This file freezes the exact semantic update applied to `docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` in the PR #409 closeout candidate after the clean KF-089 code/package stack was integrated into `main`. It preserves the accepted 2026-09-14 live result and the exact edit provenance. PR #409 merge completion itself must be read from GitHub history rather than inferred from this file.

## Domain table replacement

The KF-089 description is updated to:

```text
| KF-089 | PRODUCT | provisioned cold-boot Relay runtime blocked by Wi-Fi startup gate; downstream Manager Relay receive ACL contract missing |
```

## Quick-index replacement

The KF-089 quick-index row is updated to:

```text
| KF-089 | N3-W provisioned cold-boot Relay / Manager Relay ingress | 已配网节点在 Wi-Fi 不可用条件下冷启动时最初无法启动 Relay-capable runtime；修复 startup gate 后，板侧 Relay 链已证明，但 T1 Manager 仍未接受 Relay telemetry | 同一产品路线存在两个已证明的顺序缺陷：① startup gate 在 ESP-NOW/runtime 启动前要求 `wifi_connected()`；② Manager Dynamic Security source/live role 在 default subscribe/client-receive deny 下缺少 exact Relay ingress 的 `subscribePattern`、`publishClientReceive`、`unsubscribePattern` allow | startup-gate source repair 已合并并物理证明；PR #400 exact least-privilege ACL source contract + ID24 live ACL repair PASS；ID25 单次 Manager restart 后 Direct/Relay subscription request 均观察到且 DynSec 不变；ID26 以 10s Board-B-off 零基线 + 384s 单次 fresh Relay window 得到 38 accepted / 0 rejected / 0 duplicate / 1 unique route，`KF089_END_TO_END_RELAY_TELEMETRY=PROVEN`。禁止 broad `ingress/gateway/#` grant；full custom radio ownership 继续 deferred | GUARDED |
```

## Regression-rule additions

The fixed regression section now adds:

```text
- **Relay receive ACL least privilege**：Manager service identity role 对 Relay ingress 只允许 exact `gh/v1/<sid>/ingress/gateway/+/+/frame` 的 `subscribePattern` / `publishClientReceive` / `unsubscribePattern`；default deny 必须保持，禁止用 `ingress/gateway/#` broad allow 规避。
- **Relay end-to-end attribution**：不能用历史 Manager 日志或仅有 board-side submit 作为 E2E PASS。fresh revalidation 必须使用 clean pre-window baseline + bounded single-sender Relay window，或等强度 attribution oracle，并同时证明 Manager/Broker runtime 与 repaired DynSec contract 在窗口前后稳定。
```

## Exact-base application provenance

The central index edit was prepared from a fresh complete read of the exact `main` blob after PR #406 → #407 → #408 integration:

```text
CENTRAL_INDEX_BASE_MAIN=1bbd4f3f1cfbccaa383d326a28bc972ed4ee202b
CENTRAL_INDEX_EXACT_BASE_BLOB=42370e7fcdab7388e444f78523989f0a720fb289
CENTRAL_INDEX_EDIT_PRESENT_IN_PR409=true
CENTRAL_INDEX_FOCUSED_DIFF_REVIEW=PASS
```

The fixed SHA above is the exact base used to prepare the central-index edit. It is not a permanent claim about the repository tip after PR #409 or later descendants.

The focused diff review proves that the central-index candidate changes are limited to the KF-089 domain row, the KF-089 quick-index row, and the two Relay regression rules. No unrelated hunk remains.

A separate explicit PR #409 merge-closeout authorization was granted on 2026-09-14. That authorization permits merge only after fresh exact-head/diff/CI revalidation; it does not itself prove that merge has completed.

```text
KNOWN_FAILURE_CURRENT_STATUS=GUARDED
KF089_END_TO_END_RELAY_TELEMETRY=PROVEN
CENTRAL_INDEX_EDIT_PENDING=false
CENTRAL_INDEX_EDIT_PRESENT_IN_PR409=true
PR409_MERGE_CLOSEOUT_AUTHORIZATION=GRANTED_2026-09-14
```
