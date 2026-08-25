# N3-W pairing/recovery simplification V2 — source closure

- Date: 2026-08-25
- Baseline: `40a21db73158ae65f789d246e076a6e3ae0324da`
- Baseline tree: `d8221762a34a62c718fdc68d995086d5ddb60d56`
- Scope: source, host tests, source contracts and source-only ESP32-C6 compile
- Physical execution: false
- Legacy epoch recovery executed: false

## Complexity Delta

| Authority / flow | Before | After |
|---|---:|---:|
| device product pairing correctness epochs | 1 | 0 |
| distributed monotonic pairing generations | 1 | 0 |
| pairing -> MQTT credential coupling | 1 | 0 |
| pairing -> N3-W application-key coupling | 1 | 0 |
| normal retry credential rotations | possible | 0 |
| normal retry N3-W key rotations | possible | 0 |
| normal retry SYSTEM_PEER_KEY rotations | 0 | 0 |
| formal product Setup Secret handoff mechanisms | filesystem inbox | Manager-owned UDS |
| product filesystem handoff states | create/write/chmod/rename/watch/consume/unlink | 0 |
| business timing authorities | registration TTL + handoff TTL/floors | one pairing transaction expiry |
| product helper/app swap recovery flows | 1 legacy path | 0 product path |
| physical preclaim/successor states caused by host failure | multiple legacy states | 0 product states |
| live product imports of pairing-epoch successor helper | 0 | 0 |

The retained `pairing_epoch` SQLite columns are backward-compatible audit
storage. New product hello messages do not send an epoch, and Manager assigns a
local attempt sequence without using it in security or lifecycle decisions.

## Source result

- the device persists a CSPRNG 128-bit UUID for the pending transaction and
  removes it only after the final delivery receipt commits;
- terminal Manager transaction IDs remain replay tombstones;
- first registration uses MQTT credential generation 1;
- application-key staging advances its own key store and need not equal the
  MQTT generation;
- ordinary product pairing never calls `SystemPeerTrustStore.rotate()`;
- product composition owns a bounded, permissioned, local Unix socket;
- the filesystem inbox remains a directly testable `LAB_ONLY` adapter but is
  not constructed or started by product composition;
- the pairing CLI calls the Manager socket and never writes SQLite;
- boot-session/sequence canonical replay guards and the final delivery digest
  receipt remain unchanged;
- pairing-epoch recovery helpers remain only under `board_lab` and are marked
  legacy/engineering/board-lab migration-only.

## Final C1-C7 architecture hardening

后续独立 architecture review 完成了剩余 product correctness boundary 的收口：

- **C1**：只有 `status == "rejected"` 且
  `reason in {"expired", "replay_detected"}` 的精确 terminal response 才生成
  fresh pairing ID；transient、timeout、malformed 及其他 non-terminal outcome
  均保留当前 ID；fresh ID 必须 durable persist 成功后才生效。
- **C1 residual risk**：pre-PoP terminal-response spoofing 最多造成 pairing-ID churn、
  NVS wear 或 pairing availability / DoS；不能取得 credential，也不能触发 MQTT、
  N3-W application 或 system peer key rotation。
- **C2**：已有 stable `NODE_ID` 的 registered identity 不得重新进入 first-registration
  credential staging；首次注册仍从 MQTT generation 1 开始，ordinary repair 不隐式创建
  新 generation。
- **C3/C7**：repair authority 使用内存态、one-shot、`TTL <= 120s`、
  hardware/pairing 精确绑定且 Manager restart 失效的 `RepairIntent`；
  durable `repair_authorized` residue 不再是 correctness authority。
- **C4**：T1 保持 Manager root filesystem read-only；Manager-owned local RPC 使用
  tmpfs 中的 `/tmp/greenhouse-manager/pairing.sock`，private runtime directory 为
  0700、socket 为 0600；non-Compose 安装可以继续采用 `/run` 默认路径。
- **C5**：MQTT credential 与 N3-W application key 由独立 lifecycle owner 管理；
  first-registration issuer 仅为 composer，不是 rotation API。
- **C6/C7**：Unix-domain RPC 的 request/response 最大均为 4096 bytes，使用首个 LF
  作为 frame boundary，继续读取至 EOF 并检查 trailing data，client 使用 `SHUT_WR`；
  response schema 按 operation 严格区分，repair downstream failure 仍返回 repair schema。

filesystem Setup Secret inbox 继续保持 `LAB_ONLY`。上述修正均不得重新引入
pairing epoch 作为 product authority。

## Earlier local validation

- Manager focused suites: `48 passed`;
- pairing simplification and UDS contracts: `10 passed`;
- Manager full pytest: `1172 passed, 1 skipped`;
- Phase3/Phase4/boot-recovery source contracts: `23 passed`;
- schema/public-safety pytest: `8 passed`;
- Ruff: passed;
- public repository safety scan: passed;
- ESPHome Phase4 generic configuration: passed;
- ESP32-C6 Phase4 generic compile: passed, image size `1108110` bytes,
  firmware SHA-256 `a8936fd0d81ef9e166aa5bb4bd335b4945a90c6088779f7f754038ca7605387c`.

The first local compile attempt stopped before compilation because the sandbox
could not write the existing PlatformIO cache lock. Re-running the same exact
source with permission to use that cache passed. This is an infrastructure
precheck result, not a product regression and not a protected claim.

## Final correction validation

C1-C7 hardening 完成后的最终 source/build validation checkpoint：

- Manager full pytest：`1203 passed, 1 skipped`；
- Manager full Ruff：PASS；
- public repository safety tests：`9 passed`；
- public repository safety scan：PASS；
- N3-W source contracts：`13 passed`；
- Compose static contract：PASS；
- Phase3 cross-language host vector：PASS；
- Phase4 runtime host validation：PASS；
- ESP32-C6 Child configuration/compile：PASS；
- ESP32-C6 Relay configuration/compile：PASS；
- ESP32-C6 Phase4 generic configuration/compile：PASS；
- post-build generated-artifact cleanup：PASS；
- pre-documentation source/worktree integrity checkpoint：PASS
  （`26` tracked changes，`0` untracked files）。

上述 ESP32-C6 compile 均未执行 upload、Flash、reset、serial、board 或 RF 操作。

以下现象统一归类为 local validation/tooling issue，不属于 product defect：

- Python subprocess `ModuleNotFoundError`：本地 validation environment/import mismatch；
- Apple Clang unused-internal-helper warning：本地 compiler portability warning；
- zsh interactive `#` parsing：本地 shell behavior；
- zsh scalar linker-flag word splitting：本地 shell/tooling behavior；
- ESPHome 生成的 `.esphome/` tree 与临时 `.gitignore`：local build artifacts，
  已通过 exact-path cleanup 删除。

这些现象不得作为 credential/key compromise 或 N3-W product regression 的证据。

## Safety boundary

No board, USB, serial, Flash, NVS, reset, RF, Spare T1, production T1, live
Manager, Broker, Home Assistant, DynSec, credential, or key mutation occurred.
No real Setup Secret or private credential was accessed. The generated build
tree is ignored reproducible cache material and is not public evidence.
