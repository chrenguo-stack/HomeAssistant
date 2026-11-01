# Stage2D8 G2 V64 U1 本机 Artifact 校验包 V1.0

## 1. 更正说明

此前提到的《Stage2D8 G2 专用测试板单次执行授权包 V1.0》并未实际作为可下载文件提供。U1 只是本机只读 Artifact 校验，不需要 D2 实板授权，因此现单独提供本校验包。

本校验包不会连接测试板，不会擦除、烧录、verify-flash、回读或启动实板，也不会连接 Wi-Fi、MQTT、Broker、Home Assistant 或生产环境。

## 2. 需要下载的两个文件

将下列两个文件都保存到 Mac 的“下载”目录：

1. `stage2d8-g2-immutable-locked-v64-6cf37c29.zip`
2. `stage2d8_g2_v64_u1_verify_20260722_v1.sh`

冻结 ZIP SHA-256：

```text
662d9d4d850eea603d5defafb2b3c84a8bc07fae3a4b51229479b2a0a71e8ea9
```

## 3. 完整执行命令

打开 Mac“终端”，一次性粘贴执行：

```bash
set -euo pipefail

ZIP="$HOME/Downloads/stage2d8-g2-immutable-locked-v64-6cf37c29.zip"
SCRIPT="$HOME/Downloads/stage2d8_g2_v64_u1_verify_20260722_v1.sh"
LOG="$HOME/Desktop/stage2d8-g2-v64-u1-verification-$(date -u +%Y%m%dT%H%M%SZ).log"

chmod 700 "$SCRIPT"
"$SCRIPT" "$ZIP" 2>&1 | tee "$LOG"

printf 'U1_LOG=%s\n' "$LOG"
```

## 4. 成功标志

完整输出最后必须包含：

```text
ZIP_SHA256_MATCH=true
SHA256SUMS_CHECKED=18
SHA256SUMS_ALL_MATCH=true
MANIFEST_SOURCE_SHA_MATCH=true
MANIFEST_GATE_LOCKED=true
CLEAN_BUILDS_BYTE_IDENTICAL=true
REPRODUCIBILITY_STATUS=pass
TEST_PARTITION_READONLY=true
STAGE2D8_G2_V64_HOST_ARTIFACT_VERIFICATION=PASS
```

## 5. 停止条件

出现以下任一情况即停止，不执行任何实板命令：

- 输出包含 `ERROR=`；
- 脚本退出码非 0；
- 最终没有出现 `STAGE2D8_G2_V64_HOST_ARTIFACT_VERIFICATION=PASS`；
- ZIP 名称或 SHA-256 不匹配；
- `SHA256SUMS_CHECKED` 不是 18；
- 任一执行授权不是 `false`；
- manifest 不是 `gate=LOCKED`。

## 6. 回传内容

请将终端从 `BATCH_PACKAGE_ID=` 开始到最后一行的完整输出粘贴到对话中。也可以上传桌面生成的 `.log` 文件。

不要连接测试板，不要执行擦除、烧录、verify-flash、Flash 回读或启动测试固件。U1 通过后才进入 D2 精确单次授权门。
