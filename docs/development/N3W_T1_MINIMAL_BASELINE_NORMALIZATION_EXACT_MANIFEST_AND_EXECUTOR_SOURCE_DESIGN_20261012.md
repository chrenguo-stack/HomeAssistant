# N3-W T1 minimal-baseline normalization exact manifest / executor source design（2026-10-12）

## 0. Gate

```text
NEXT_ONE_GATE=
N3W_T1_MINIMAL_BASELINE_NORMALIZATION_EXACT_MANIFEST_AND_EXECUTOR_SOURCE_20261012_01

SCOPE=GITHUB_SOURCE_AND_CI_ONLY
LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
```

## 1. Exact manifest

正式 manifest：

```text
infra/n3w-t1/production/minimal-baseline-normalization-manifest.json
```

绑定 fresh live inventory：

```text
SOURCE_INVENTORY_SHA256=0ad246ee33dcddf70555fcf23551c7b106f8b0edad8eb0523a24421d674f4814
VOLUME_COUNT=45
VOLUME_SET_SHA256=20fc845741d31da34f1d1e563e5057c78ec5dc7c4cfd3a495a5f3a4f2bfd011b
PRODUCT_NETWORK_COUNT=5
CONTAINERS=0
IMAGES=0
PRODUCTION_LISTENERS=0
```

45 个 Docker volume 逐名列出；5 个 product/historical Docker network 逐名并绑定 observed ID prefix；product paths、guard unit 和 firewall ownership 逐项列出。

public manifest 不保存 raw T1 locator 或客户 LAN subnet。firewall 通过固定 chain/comment/port/anchor count 和 foreign-reference absence 证明 ownership，而不是把 LAN 地址写入 GitHub。

## 2. Preserve contract

必须保留：

- Armbian OS / systemd；
- SSH；
- NetworkManager 与当前网络配置；
- Docker Engine + Compose；
- Docker 默认 network：`bridge` / `host` / `none`；
- Docker `DOCKER-USER` framework 和 `FORWARD -> DOCKER-USER` jump；
- Docker root 本身。

禁止使用 Docker prune、volume prune、network prune、全局 firewall flush 或 broad filesystem glob。

## 3. Apply order

正式 executor 只能按 manifest 顺序：

1. 完整 read-only preflight，一次性证明所有 delete/preserve 条件；
2. 用户未来明确授权后，停止并 disable exact guard unit；
3. 删除 exact N3W firewall INPUT / DOCKER-USER anchors，再 flush/delete exact N3W custom chain；
4. 删除 5 个 exact product networks；
5. 删除 45 个 exact volumes；
6. 删除 8 个 exact product paths；
7. `systemctl daemon-reload`；
8. minimal-host postcheck。

任何 preflight drift 都在第一项停止，不能进入 mutation。

## 4. One-shot / replay

计划中的 live authorization：

```text
N3W_T1_MINIMAL_BASELINE_NORMALIZATION_LIVE_APPLY_20261012_01
```

当前状态：

```text
AUTHORIZATION_STATE=NOT_GRANTED
```

executor 一旦进入第一条 mutation，该 authorization 在流程语义上即视为 consumed。若中途失败，由于 exact initial prestate 已被改变，同一 executor 的完整 preflight 将无法再次通过，因此禁止原 authorization replay；必须 fresh read-only forensic 后重新设计 successor。

## 5. 当前停止点

本 gate 只提交 manifest / executor / tests / CI。CI PASS 前后都不得自动执行真实 T1 删除。
