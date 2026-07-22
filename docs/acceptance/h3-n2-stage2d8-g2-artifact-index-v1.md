# H3/N2 Stage 2D-8 G2 V64 Artifact 脱敏索引

## 来源

- Repository: `chrenguo-stack/HomeAssistant`
- Frozen source: `6cf37c29311601f4f83238cc8401c81ea7b9a1f0`
- Draft source PR: `#168`
- Workflow run: `29900632869`
- Artifact ID: `8521935706`
- Artifact name: `stage2d8-g2-immutable-locked-v64`
- Artifact expires: `2026-08-21T07:42:27Z`

本索引不包含原始 MAC、USB 序列号、本机串口、用户路径、私有目标指纹或完整实板日志。

## 外层 ZIP

| 对象 | SHA-256 |
|---|---|
| GitHub Artifact ZIP | `662d9d4d850eea603d5defafb2b3c84a8bc07fae3a4b51229479b2a0a71e8ea9` |

## 关键制品

| 路径 | 字节数 | SHA-256 |
|---|---:|---|
| `g2/bootloader.bin` | 22368 | `653f065985af23ab0c8281ba87c88ead45c082b6259b0b867627b7b564851bd8` |
| `g2/firmware.bin` | 513264 | `e5a707753117819f7e2a71d78d7c5813f6a5932f52b6d92047bc36c525eb92df` |
| `g2/partitions.bin` | 3072 | `d59f8cff987dee266d2df9340867ff56369c2dfd28c93e12d5a93b10277c2a72` |
| `g2/gh2d8_nvs_seed.bin` | 65536 | `1f7016fe98cf69ca879a72069e63869863d1a4c8580ba0c8931aef133de3c928` |
| `g2/stage2d8-g2-merged-v64.bin` | 4259840 | `a3ff73ddc11115849e160637cd63e2f44c699e595c5c6aa43575f9d7626ed47d` |
| `recovery/firmware.bin` | 192048 | `3c8165e03077213c5f0f64ac66fecec0a964bdb8761f785b1409ffff66e97fa2` |
| `recovery/stage2d8-recovery-merged-v64.bin` | 4259840 | `5f6ca3024d35dea9b48679a3882a55a20ec2bc67137d6dd58cbf19c2474994ed` |

## 结构化证据

| 路径 | SHA-256 | 结果 |
|---|---|---|
| `stage2d8-g2-artifact-manifest-v64.json` | `bd0b138710c178cc6d166e2eb8ab2e5b419bf167a5ad19c0aaebc9940c6e2561` | `gate=LOCKED` |
| `stage2d8-g2-host-fault-matrix-v64.json` | `b78fb1a7eafff9867fa97341adb17bdb034cf24c5f9825893115c42e76db2f1d` | pass |
| `stage2d8-g2-source-boundary-v64.json` | `e038e88441c1f0c09b6974b39fc3e496ba26530dc6d04892f2ebbb67dfb20b92` | pass |
| `stage2d8-g2-reproducibility-v64.json` | `325580af692416f3e16c29bee7f14135ce4eaa04026c6441f4e8b794033a3bd1` | pass |
| `stage2d8-nvsgen-runtime-v64.json` | `e5fd32642537d3cf4c190d7ff53cd573a19d60b9ab78d7f517a15010d2da98f1` | recorded |

## 冻结分区合同

| Label | Offset | Size | Flags |
|---|---:|---:|---:|
| `nvs` | `0x9000` | `0x6000` | `0x00000000` |
| `phy_init` | `0xF000` | `0x1000` | `0x00000000` |
| `factory` | `0x10000` | `0x3F0000` | `0x00000000` |
| `gh2d8_nvs` | `0x400000` | `0x10000` | `0x00000002` (`readonly`) |

NVS seed 仅包含 `gh2d8_seed/format_version=1`，目标 namespace `gh2d8_state` 必须不存在。

## 独立复核状态

- 外层 ZIP SHA-256：匹配；
- `SHA256SUMS` 18 项：全部匹配；
- manifest source SHA：匹配；
- manifest execution authorizations：全部 `false`；
- 两次 clean build：逐字节一致；
- G2 与 recovery 的 bootloader、partition：一致；
- 固定 build time：存在；
- 当前结论：Artifact 可进入用户本机 U1 校验，但不构成实板执行授权。
