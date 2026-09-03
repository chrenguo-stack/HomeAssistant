# KNOWN_FAILURES_AND_REGRESSION_GUARDS — R2B Addendum 2026-09-04

This public-safe addendum records the new known-failure item discovered during the
Board B R2 Broker-observability detour. It is intentionally narrow and does not
replace `KNOWN_FAILURES_AND_REGRESSION_GUARDS.md`.

## Primary-domain addition

| ID | DOMAIN | 说明 |
|---|---|---|
| KF-085 | PHYSICAL_HARNESS | running Broker single-file bind-mount live authority / writeability oracle |

## Quick-index addition

| ID | 阶段 / 模块 | 现象 | 根因 | 修复 / 闪避规则 | 状态 |
|---|---|---|---|---|---|
| KF-085 | R2B Board B Broker observability | host-side candidate config could be visible at Docker-inspect source pathname while the running Broker still saw another bound inode; a later exact-container write was rejected even though `test -w` returned success | executor treated Docker inspect source pathname identity and pathname permission tests as sufficient mutation authority for a running single-file bind mount; read-only audit proved host pathname vs live mount inode split and `Mounts[].RW=false` / live `ro` mount | classify authority with Docker inspect + running process mount namespace + container-visible dev/inode/hash; never rename/replace a host pathname already bind-mounted into a running container; require mount `RW=true` and live mount options before write; `test -w` is auxiliary only; if live mount is RO, use read-only evidence or separately authorized staging/recreate; observability failure must not be promoted to product failure | RESOLVED |

## Fixed regression-rule addition

- **Single-file bind-mount live authority**: Docker inspect `Mounts[].Source` pathname
  does not by itself prove the object currently bound into a running container.
  Where a single-file bind mount has been subject to host-side rename/replacement,
  compare the host pathname with `/proc/<pid>/root/...` and the container-visible
  object using dev/inode and byte hash where safe. Before any mounted-file mutation,
  require Docker `Mounts[].RW=true` and live mount options that permit writing;
  `test -w` alone is never write authority. A read-only live mount must stop
  observability mutation and fall back to read-only evidence or a separately
  authorized staging/recreate design.

## Related incident mappings

The same R2B closeout revalidated these existing records without assigning duplicate
KF numbers:

- KF-010: stronger diagnostic/log oracle must not masquerade as product failure.
- KF-072: incomplete/UNKNOWN evidence and execution-result serialization.
- KF-078: executor materialization/transport preflight discipline.
- KF-082: R2B recovery normalization and post-closure serial-quiescence oracle.

Detailed evidence and the seven-incident audit are in
`N3W_R2B_BOARD_B_TEST_INCIDENTS_AND_REGRESSION_GUARDS_20260904.md`.
