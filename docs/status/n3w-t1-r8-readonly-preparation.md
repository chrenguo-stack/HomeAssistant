# N3-W T1 OTA V1.2 R8 只读准备

2026-11-22（新加坡时间）。范围限备用 T1，固定验收 Home Assistant `2026.10.0 → 2026.10.4`。当前停在只读准备，实机取证由操作人在 Mac 执行。

## 已核对的来源

- `main` 为 `4fde1b7c5cc0aa224fa3574b8b4cc638edd93647`。[PR #815](https://github.com/chrenguo-stack/HomeAssistant/pull/815) 仍为草稿，候选 `741a1463e7de065401749e47e59d30b295d5d6e8` 返回 25 项已完成且成功的工作流。依据 [R7 交接](https://github.com/chrenguo-stack/HomeAssistant/blob/82f738dd37a5ad99f66e9e69679027fa843d0ca0/docs/development/N3W_T1_OTA_V1_2_R7_BASELINE_PASS_TO_R8_NEW_CHAT_HANDOFF_V1.0_20261122.md) 和 `main` 的 [V1.2 方案及 R8 路线](https://github.com/chrenguo-stack/HomeAssistant/blob/4fde1b7c5cc0aa224fa3574b8b4cc638edd93647/docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md)。
- [R7 恢复包 14715501376](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44924757335/artifacts/14715501376) 和 [候选恢复包 14717720726](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44930275032/artifacts/14717720726) 已下载并核验 ZIP、清单所列 11 个文件和包内 `ha-recovery.pyz`。11 个文件的字节一致，两份清单分别绑定 `84da7cd68e2f` 和 `741a1463e7de`。候选清单 SHA-256 `55d188d61dec4f55540b20a32155e00fa11d3f7582581da9b9817b652859cdcb`。
- [出厂镜像 13070404405](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/41275979177/artifacts/13070404405) 和 [目标镜像 13391983948](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/41976542377/artifacts/13391983948) 的任务均成功，工件的 ID、源码、摘要及有效性与交接一致。本会话下载接口每件上限为 512 MiB，原出厂工件 13070404405 留作历史来源，R8 本地镜像校验使用已在 Mac 回读的 14716899788 和 13391983948。目标与前代标签、平台和压缩归档摘要见 [冻结清单](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/infra/n3w-t1/upgrades/homeassistant-2026.10.4.json)。
- R7 回执的运行 Manager `fresh-44e7d7472714` 对应源码没有 `_publish_ota_monitoring_self_test`。冻结候选的 `check-candidate-activation` 明确检查运行 Manager 的此能力。若新鲜观测仍为该镜像，须先资格确认并在独立授权下建立兼容 Manager 基线，然后在两条 R8 实机用例中固定 Manager 和 Broker。 [候选运行检查](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/tools/n3w_t1_core_updater_ha_recovery_startup.py#L215) · [同候选 ARM64 Manager 的构建来源](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44930275030/artifacts/14716899788)

## 备用 T1 只读取证

从 Mac 通过已单独核对的 R7 备用机 SSH 目标运行 [`r8_prepare_mac.py`](../../tools/execution_packages/n3w/t1_ota_spare_readonly/r8_prepare_mac.py)。`--ssh` 使用原 R7 观察器，在宿主内存中读取运行身份、启动方式、健康、存储及事务，并补充 USB 文件系统与可见挂载命名空间计数。分区未挂载时，介质资格和可用空间继续待验。`--verify-images` 单独在 Mac 校验两个 ZIP 及各自的 HA 镜像归档，接受用工件 ID 命名的本地 ZIP 缓存。工具已做已知 ZIP、错误摘要拒绝、模拟 SSH 调用和 USB 输出验证。Mac 只读回执已取得，见下文。R8 所需两个 ZIP 的 Mac 本地回读通过，见下文。

## 需要准备的两个独立恢复点

1. **前代 `2026.10.0`。** 使用出厂工件内精确 ARM64 HA 镜像，寻找同一备用 T1、在新版首次写入前取得的数据备份。用版本、镜像 ID、备份时间、事务或快照来源、加密归档及清单摘要绑定。在隔离的副本上做认证、解密回读和 SQLite 一致性验证，保留所需伴随文件和原元数据。旧 P3 的数据备份若绑定 `2026.10.4` 前代，只能作为该版本材料的线索。工厂构建及历史运行回执均不提供可恢复的数据副本。找不到匹配数据时，另行决定是否使用隔离构建的 `2026.10.0` 测试数据，其证据仅覆盖该数据集。禁止让旧版打开当前 HA 数据目录。
2. **当前 `2026.10.4`。** 核对实际运行镜像 ID、启动配置及受保护挂载，将 HA `/config`、Recorder 数据库及伴随文件、配置和注册表纳入一致性备份。若部署路径还要改变 Manager，保护其状态和回放数据，保存当前 Manager 镜像和绑定；保存所需的宿主配置、事务摘要和密钥可用性证明。备份置于有足够空间的独立受控介质，静止时制作认证加密归档，并以隔离副本校验清单、解密和数据库可读。密钥、备份内容及现场位置留在私有现场。现有 USB 文件及历史事务保留。未找到足够新的已验证副本时，单独确认停写与备份授权。
3. **回到当前版本。** 保存经验证的 `2026.10.4` 镜像/启动绑定及必要的正常挂载配置。恢复前代失败时，停止可能接触过前代数据的写入者，恢复独立保存的 `2026.10.4` 数据和标准 Compose 启动绑定。静止核对清单后再启动，验明 HA/Manager 的实际版本和运行身份、业务收数、受保护的历史或配置样本，以及 Broker 在验收期间的连续性。计算两个方向的峰值空间。若需更新 Manager，回退材料须能恢复此次更新前的组合。

## 2026-11-22 备用 T1 实机只读回执

- `RUNNING_BASELINE_PASS`，`clean_reference_records_match=true`，`errors={}`，`diagnostic_only=false`。HA `2026.10.4-5881590f`，Manager `fresh-44e7d7472714`，Broker `2.1.2-3184566d`，三个实例均为 ARM64 且重启计数为 0。HA 返回 401，HA 和 Manager 的 MQTT 认证均通过。实际 Manager 仍为已确认缺少收数自检入口的旧镜像。恢复组件和三个恢复单元尚未启用。
- Stack 事务维持 `COMMITTED`，HA USB 事务维持 `ROLLED_BACK`，两次取证之间事务稳定。宿主和 Docker 的报告可用空间均为 4,758,110,208 字节。U 盘为 ext4，设备容量 32,015,122,432 字节，扫描未发现挂载且没有报告不可读的挂载命名空间。U 盘可用空间和恢复材料资格未测。取证未停服、未挂载、未写入。
- 找到 [2026-11-15 R32 实机备份成功回执](https://github.com/chrenguo-stack/HomeAssistant/commit/51186e69b1885a9f1b98c4713558c41767e19d79) 及 [明确绑定 HA 2026.10.0 的恢复依据](https://github.com/chrenguo-stack/HomeAssistant/blob/7811b6bc2fc3cdc5b1cecb45549cb81b6d80784c/tools/execution_packages/n3w/r7a/u13a_live_commit_authorized/manifest.json#L58-L89)。加密数据包 `homeassistant-preupgrade.tar.gz.enc` 为 2,178,281 字节，SHA-256 `9473d5d199fd16c185425f5f0a0676d6cfab1888db28617f5ac4c9e4fa9e1c4c`，清单 SHA-256 `fd9a2f279a6e9fed99c2af6c2d4502227cafebe4d0ea5d5bb0a467e34415a704`。前代 HA 运行镜像 ID `sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306`。旧 U13A 介质随后完成 [11 月 18 日重置](https://github.com/chrenguo-stack/HomeAssistant/commit/f725bbc7) 及 [P3 新建 ext4 恢复](https://github.com/chrenguo-stack/HomeAssistant/blob/7811b6bc2fc3cdc5b1cecb45549cb81b6d80784c/docs/development/N3W_T1_U13B_P3_U4_RECOVERY_PASS_TO_U5_NEW_CHAT_HANDOFF_V1.0_20261118.md)。前代数据副本可得性待查。若找到副本，另找配套认证元数据，并核验同机密钥能打开归档及隔离恢复结果。大小和 SHA-256 仅用于候选定位。

R8 的正常升级、真实故障后自动回滚及关键边界断电续办均待实机。当前没有 R8 写入授权。

## R32 副本搜索与 R8 备选准备

- Mac 和备用 T1 的指定本地路径按原归档大小和 SHA-256 搜索，结果为 `R32_T1_SEARCH_EXIT=0` / `R32_BACKUP_MATCH=NOT_FOUND_IN_CHECKED_PATHS`。搜索结论限于已查路径，其他介质和离线副本状态未知。
- [精确 ARM64 三镜像产物 14716899788](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44930275030/artifacts/14716899788) 绑定 `741a1463e7de065401749e47e59d30b295d5d6e8`，包含冻结的 `2026.10.0-0c73235a` HA 镜像和具备自检的 `fresh-741a1463e7de` Manager。[独立容器验证步骤](https://github.com/chrenguo-stack/HomeAssistant/actions/runs/44930275030/job/136925172766#step:13)通过了确切 ARM64 组合的 MQTT 引导、自然收数和自检回执，上传后工件回读核验亦成功。Mac 工具的 `--verify-images … --candidate-bundle` 仅在 Mac 校验该 ZIP、其中两项镜像及冻结 `2026.10.4` 目标 ZIP。脚本的选择逻辑和篡改摘要拒绝已用本地测试样本验证，两份 R8 镜像包在 Mac 的回读已通过，见下文。
- 若采用独立测试数据，先准备一份由精确 `2026.10.0` 自行初始化的干净 HA 数据目录，使用受控收数和历史样本作为前代基线。CI 测试凭据和身份仅用于 CI，备用机仍使用本机 MQTT 引导与认证。此路线覆盖受控数据的正常升级、回滚及断电续办。R32 历史数据的迁移作为一项未覆盖范围单独记录。
- 保留 `2026.10.4` 当前数据、镜像、现有应用启动绑定及将要调整的 Manager 状态。定向源码核对表明 OTA 运行态要求实际受保护路径为产品的 `/var/lib/n3wfc4-homeassistant`，并绑定目录与文件系统身份。实机只能在独立授权后先静止写入、验证当前版本备份和回退，随后把测试副本切入标准路径，且回退到原目录后重验 `2026.10.4` 与业务样本。禁止用改代码放宽路径检查的方式通过验收。应用管理单元可能同时停 HA 与 Manager，Broker 保持服务的条件要以执行前预检和实测确认。
- 当前仅完成方案、定位和模拟验证。未停止服务、未生成新实机备份、未应用 Manager 候选，也未用测试数据替代历史数据。

## Mac 本地镜像回读通过

2026-11-22（新加坡时间），操作者返回三项通过结果。使用 [修正版 Mac 校验脚本](https://github.com/chrenguo-stack/HomeAssistant/blob/0229ce69c5988fe690c0251a9853efb7bd92474d/tools/execution_packages/n3w/t1_ota_spare_readonly/r8_prepare_mac.py)。首次误报来自把备用机历史运行时镜像 ID 与下载包的构建镜像 ID 作等值比较。修正版按冻结构建记录核对下载包的构建 ID，并保留 ZIP 与包内归档的 SHA-256 校验。

| 项目 | 工件 ID | Mac 回执 | 包内归档字节数 | 包内归档 SHA-256 |
| --- | --- | --- | ---: | --- |
| HA 前代 `2026.10.0-0c73235a` | 14716899788 | `factory_ha_archive_verified=true` | 2448553472 | `755ae190b0f9c7cc89b0b9d9b2153ea3a81c3cf5c9dd5bc71ab9471603861acb` |
| Manager `fresh-741a1463e7de` | 14716899788 | `manager_archive_verified=true` | 62950400 | `259f6dacd92cfb96b178e0afd61a1c04d8fee52a217822e66bf43b6c9ed3196e` |
| HA 目标 `2026.10.4-5881590f` | 13391983948 | `target_ha_archive_verified=true` | 835309535 | `eba1da958fc9c759c30d1cb34445c364e895bcd8d5e6c0d8392ab6849ece9973` |

- 前代构建镜像 ID 为 `sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879`，ARM64 manifest 摘要为 `sha256:0c73235a9140a9b02e4bf618d06d8c496b12ae70656ecddb0e02ad31ad122be4`，与 [冻结前代构建步骤](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/.github/workflows/n3w-t1-fresh-install-exact-arm64-ci.yml#L54-L55) 一致。
- Manager 构建镜像 ID 为 `sha256:7e7447f081cb2168720121a70137b30cd3ec502446be63ca0306a92c011400fb`。目标归档的配置摘要为 `sha256:59160fc724d82aa83186f577f46aa8c8abe40af4052502eb32b621943582a5f6`，归档 SHA-256 与冻结清单一致。这两项身份来自归档回读，备用 T1 的实际运行身份须在实机阶段另行核对。
- 镜像准备完成。用户已确认独立 `2026.10.0` 测试数据范围，见下文。备用机当前 `2026.10.4` 环境的一致性备份、隔离恢复验证和后续实机阶段仍待执行。此回执只覆盖 Mac 本地文件，无 T1 停服、装载或写入授权。

## 独立测试数据已确认，当前版本备份前预检

2026-11-22（新加坡时间），操作者确认使用由精确 HA `2026.10.0` 自行初始化的独立数据。用本机 MQTT 引导建立已知输入和可查询的 Recorder 历史，为正常升级、故障回滚和断电续办分别留证。R32 历史数据迁移继续列为未覆盖。镜像归档与候选绑定沿用上节通过的证据。该确认涉及测试数据范围，当前停服备份、介质写入、装载候选、切换数据路径和 OTA 执行仍待相应授权。

先从 Mac 实测标准应用单元、Broker 单元、现有运行镜像、读写挂载、Docker 与数据路径所在文件系统空间、HA 和 Manager 数据大小，以及 U 盘可见情况。本命令读取配置和密钥文件的元数据，不打印其内容。HA 数据大小是运行中测量，只用于估算容量；未挂载 U 盘的可用空间仍未知。命令已通过 Bash 语法和替身命令模拟验证，备用 T1 实际回执已收集，见下文。

```bash
printf '输入上一轮核验过的备用 T1 SSH 目标：'
IFS= read -r r8_t1 </dev/tty
if [ -n "$r8_t1" ]; then
  ssh -o StrictHostKeyChecking=yes -o ForwardAgent=no -o ClearAllForwardings=yes -o ConnectTimeout=10 -T -- "$r8_t1" 'if [ "$(id -u)" -eq 0 ]; then exec /bin/bash -s; else exec sudo -n /bin/bash -s; fi' <<'R8_REMOTE'
set -eu
unset DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY
export DOCKER_HOST=unix:///var/run/docker.sock
systemctl show n3wfc4-services-activation.service n3wfc4-broker-activation.service n3w-t1-ha-ota.service -p Id -p ActiveState -p SubState -p NeedDaemonReload --no-pager
for service in broker manager homeassistant; do
  container=$(docker ps --filter label=com.docker.compose.project=n3wfc4 --filter "label=com.docker.compose.service=$service" -q)
  printf '%s ' "$service"
  docker inspect --type container --format '{{.Config.Image}} {{.Image}} {{.State.Status}} restarts={{.RestartCount}}{{range .Mounts}}{{if .RW}} {{.Type}}:{{.Source}}:{{.Destination}}{{end}}{{end}}' "$container"
done
docker_root=$(docker info --format '{{.DockerRootDir}}')
df -P -B1 -- "$docker_root" /var/lib/n3wfc4-homeassistant /var/lib/greenhouse-manager
du -sbx -- /var/lib/n3wfc4-homeassistant /var/lib/greenhouse-manager/manager /var/lib/greenhouse-manager/n3w
stat -c '%F mode=%a uid=%u size=%s links=%h %n' -- /etc/n3wfc4/docker-compose.yml /etc/n3wfc4/docker-compose.env /var/lib/greenhouse-manager/identity/system-root.key
if [ -f /var/lib/n3wfc4-homeassistant/home-assistant_v2.db ]; then
  stat -c 'RECORDER_DB_BYTES=%s' -- /var/lib/n3wfc4-homeassistant/home-assistant_v2.db
else
  printf 'RECORDER_DB_NOT_FOUND_AT_DEFAULT_PATH\n'
fi
lsblk -b -o NAME,TYPE,TRAN,FSTYPE,SIZE,FSAVAIL,MOUNTPOINTS
R8_REMOTE
fi
```

预检结束后把备份执行单绑定已核验的备用机、当前运行镜像、标准启动配置及备份目的地。停服备份范围拟为由同一应用单元管理的 HA 和 Manager，先根据实际单位依赖与容器状态证明写入已停止，并观察 Broker 的运行连续性。保留本机密钥与对应的私有恢复路径；备份覆盖 HA 数据、Recorder 数据库及伴随文件、Manager 数据与回放目录及恢复所需启动绑定。HA 复用产品的 [ProtectedHaDataBackup](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/tools/n3w_t1_core_updater_ha_backup.py)，在隔离路径认证、解密、比对并检查 SQLite。Manager 回退也须有一致性副本及可恢复证明。先恢复并验证原 `2026.10.4` 组合的健康，再考虑切入 `2026.10.0` 独立环境。任何大小与峰值容量判断使用本轮回执；现场不格式化介质或覆盖既有事务。

## 备用 T1 备份前实机预检回执

2026-11-22（新加坡时间），操作者完成只读预检。三项运行身份与此前 R7 基线一致，容器均为 `running`，重启计数为 0。标准应用单元和 Broker 单元均为 `active/running`，旧 HA OTA 单元为 `inactive/dead`，三个单元均无待重载。Compose 文件为 root 所有、权限 0644；其环境文件和 32 字节系统根密钥均为 root 所有、权限 0600、单链接。预检没有读取密钥内容。

| 检查项 | 实测 |
| --- | --- |
| HA 现运行版本 | `2026.10.4-5881590f`，镜像 ID `sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365` |
| 现运行 Manager | `fresh-44e7d7472714`，镜像 ID `sha256:1471828ab07cf9b71c01a6e78994711a5954f0a178b8be087a28bb65a967c7d2` |
| Broker | `2.1.2-3184566d`，镜像 ID `sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563` |
| 内部文件系统 | Docker、HA 与 Manager 数据都在 `/dev/mmcblk2p2`，可用 `4756230144` 字节 |
| HA 数据 | `8441227` 字节，Recorder 主文件 `3194880` 字节 |
| Manager 数据和回放 | 分别 `131072`、`208960` 字节 |
| 三个数据目录合计 | `8781259` 字节，运行中用 `du -sbx` 观察，仅供容量估算 |
| USB | `sda1`，ext4，容量 `32015122432` 字节。此回执的宿主挂载点与 `FSAVAIL` 均为空。USB 可用空间和本次 OTA 介质资格仍待验证 |

### 已授权的停服备份执行范围

- 目的为创建备用 T1 当前 `2026.10.4` 环境的可恢复副本。使用 T1 上新建的 root 私有临时目录处理数据。在 Mac 私有目录保留独立副本。现场密钥留在 T1，应用数据及可能含凭据的启动配置只以认证加密形式传到 Mac。这个恢复点仅适用于同一备用 T1 及其现存密钥，不覆盖设备本身或根密钥丢失。目的地写入前检查 Mac 和 T1 容量。本次停服备份不依赖 USB 已通过资格检查。
- 再核对 SSH 主机身份、现运行镜像、写入挂载和启动配置，记录 Broker 当前容器和启动时间。短暂停用标准应用单元以内的 HA、Manager。坚持按实际容器状态、残余写入者和 PID 确认静止，在此之前不制作一致性副本。Broker 连续运行由实测证明。
- 备份包括 HA `/config`、Recorder 及伴随文件、Manager 状态与回放数据、原有 Compose 和环境绑定。验证加密归档可解密、能隔离恢复、清单和权限匹配、相关 SQLite 可读。无论备份成功或出现可恢复错误，尽快按原绑定恢复标准应用服务。随后核对容器实际镜像、运行状态和业务收数，并比较 Broker 是否仍是同一实例。
- 停服数据备份与镜像导出分开。当前 HA 和 Manager 镜像在备用 T1 保留；在允许清理或切换现有环境之前，通过适用的 Docker 镜像导出和离机校验证明其可恢复。Mac 上已经验证的 R8 三个镜像留作各自的输入，其身份用途与当前运行组合分别核对。
- 本执行单不包括装载候选镜像、介质写入、修改正式数据路径、重新初始化或执行 OTA。执行前按下文的固定执行器核对容量、失败恢复和回执。当前只读预检合格，真实停服、备份和验证已经完成，见下文回执。

## 当前环境停服备份执行入口

2026-11-22（新加坡时间），操作者明确同意备用 T1 当前 HA 和 Manager 的停服备份、隔离恢复验证及原应用恢复。Broker 保持运行并验证同一实例。原环境仍在使用 `2026.10.4`。停服授权仅覆盖本执行单，切入独立前代环境仍另行处理。

- [固定执行器](https://github.com/chrenguo-stack/HomeAssistant/blob/3484d5a095c09678b3d1b2ee02f9cdfa9add8396/tools/execution_packages/n3w/t1_ota_spare_readonly/r8_current_backup.py) SHA-256 `442a25af06e75b29bf8e3b7c6f5d97b1672aa20f90538be419203484b35afcff`。操作 ID `n3w-r8-current-backup-20261122-01`，重复传输使用 `--collect`，主流程以备用 T1 上独占目录防止重跑。使用既有恢复包 14717720726 内 SHA-256 为 `f39629268ffeab9906f9de8cb60362d604d5b9150ef4c13571926b00921e6b84` 的 `ha-recovery.pyz`，只在临时工作目录调用备份原语。
- 瞬态服务核对当前运行镜像、标准服务、旧 OTA 状态、挂载和容量。进程静止后备份三个数据目录及相关启动绑定，恢复演练在受限临时目录进行。输出只含认证加密归档、加密归档元数据和无凭据的回执。Mac 复核归档和元数据摘要后保存至 `~/.n3w-r8-private/n3w-r8-current-backup-20261122-01`。断开 SSH 时，备用机服务管理器继续处理备份和恢复。恢复标记支持异常退出时补启原应用。
- 编译与本地集成模拟通过：真实认证加密、隔离恢复和三个 SQLite 样例检查通过。模拟停机不成立后拒绝备份并恢复原服务。模拟 Mac 接收、摘要校验和目标防覆盖通过。实机备份和隔离恢复已通过，Mac 已验证离机副本。实机回执应报告原 HA HTTP、两项 MQTT 认证、Broker 连续性和 Manager 收数游标观察。没有新自然样本时，保留业务收数证据待补。

## 当前 `2026.10.4` 数据保护实机回执

2026-11-22（新加坡时间），操作 `n3w-r8-current-backup-20261122-01` 返回 `R8_CURRENT_BACKUP_PASS`，systemd 结果为 `success`、退出码 0。整项工作用时 `1min 28.794s`，包含校验等工作，回执没有单独测量实际停服时长。

| 项目 | 证据 |
| --- | --- |
| 认证加密归档 | `2107619` 字节，SHA-256 `951e03aa715f44f41bededc9beb1e5ff8efd15e6fc57f6a2e798b851a8481f46` |
| 归档清单 | SHA-256 `4388f46c98e7ca28c55c679aa7a937895e773d32e98f7fe6fb8b8acbc46ce6f1` |
| 加密归档元数据 | SHA-256 `caef1c8b8859ebeb4a27c7e56bfccb4a403d75dd9c70012ab0eb62cf8059b68b` |
| 备份事务绑定 | `8be09b0864a68b864cab4cbdf94e7e68e662b298c950422b8fed36d601fec625` |
| 隔离恢复 | 认证、解密还原通过，6 个 SQLite 数据库校验通过 |
| 离机副本 | `R8_MAC_ENCRYPTED_COPY_VERIFIED=true`，私人备份目录只留在操作端 |
| 原环境服务恢复 | `original_stack_healthy=true`，HA HTTP 401，HA 与 Manager 的 MQTT 认证均通过 |
| Broker 连续性与 OTA 事务 | `broker_same_instance=true`，`transactions_unchanged=true` |
| 自然业务收数 | `NO_FRESH_CURSOR_OBSERVED`，本次观察未取得新游标，仍需补证 |

这份数据恢复点用于同一备用机的现存密钥。回执证明当前环境的数据保护和服务恢复，尚未覆盖真实升级、OTA 回滚或断电续办。切入 `2026.10.0` 独立测试环境之前，先保全当前 HA 与 Manager 的镜像，并验证导出归档的可携带镜像身份。此前下载的 R8 镜像仍作为测试输入。

## 现运行镜像的离机保全与收数补证

- [固定导出执行器](https://github.com/chrenguo-stack/HomeAssistant/blob/9a5b7af02453610add5d2fd25c9e94fa3504f31c/tools/execution_packages/n3w/t1_ota_spare_readonly/r8_original_images.py) SHA-256 `1c4f6db33c80d7034dac43d9e3ad6abb28e92732de6e4999c2762080807f7c9a`。执行器复核离机数据备份及元数据，读取正在运行的 HA 和 Manager 镜像身份，并以只读查询观察 Manager 收数游标，最长约 30 秒。期间无新样本时记为待补证。
- 绑定并流式导出当前两项镜像到 Mac 私有备份目录下的 `original-images`。检查 T1 Docker 临时空间和 Mac 容量。通过固定恢复包的归档解析器，验证归档大小、SHA-256、唯一镜像标签、平台、配置与各镜像层。复跑重新验证已有归档，发现异常即停止并保留现有文件。过程不需停服务，不装载镜像，不挂载或写入 USB。
- Python 编译和三组离线模拟通过，覆盖导出、归档核验、复跑、损坏归档和数据元数据拒绝，精确导出命令、容量不足拒绝，以及收数推进、无样本、读证异常。实机导出已返回成功标记，见下文。

### 实机导出回执

2026-11-22（新加坡时间），操作者返回 `R8_ORIGINAL_IMAGE_EXPORT_PASS=true`。固定执行器仅在两项镜像都通过归档及运行身份校验并保存至 Mac 后打印该标记。两份归档及本次收数观察均已取得完整回执。

| 原运行组件 | 运行镜像 ID | Mac 归档 |
| --- | --- | --- |
| HA `2026.10.4-5881590f` | `sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365` | `2447090176` 字节，SHA-256 `6502b8cdbf706d746e32311fdaa39ffc5ca703d76f766806bbb21d3c71278d1f`，`portable_identity_verified=true` |
| Manager `fresh-44e7d7472714` | `sha256:1471828ab07cf9b71c01a6e78994711a5954f0a178b8be087a28bb65a967c7d2` | `62957568` 字节，SHA-256 `4c1dbbc999aa678057da96da1d8161907ce9e8c25ef004e88c7fb725ac3db9fe`，`portable_identity_verified=true` |

本次观察返回 `R8_MANAGER_RECEIVE=NO_FRESH_CURSOR_OBSERVED`。观察窗口内未取得新的 Manager 游标，只有自然收数证据仍待补。该结果不影响镜像校验结论，也不据此判定业务故障。HA 的 SHA-256 对应从备用机运行镜像导出的原环境回退归档，正式 OTA 目标仍使用工件 13391983948 的冻结归档。

### 建立前代基线和返回原环境的顺序

状态为方案复核，待冻结实机执行器及其离线验证结果，实机写入授权待确认。用同一台备用 T1、同一 Broker 和本机现有的 MQTT 认证材料。独立前代环境使用 `2026.10.0-0c73235a`、`fresh-741a1463e7de` 和由精确前代初始化的数据。准备 R8 测试基线时必须防止试验样本污染原有历史或触发现场控制，R32 真实旧数据的升级仍未覆盖。

1. **先验证退出路径。** 核验 Mac 上的 HA、Manager 原运行归档和数据备份，复核现场原启动文件、镜像引用、三个写入目录、Broker 容器身份、密钥可用性和事务记录。为受保护目录保留同文件系统内的独占保存位置，并记录每一步及恢复标记。加密副本是独立保障，恢复需同一备用机的系统根密钥。使用实际镜像层、内置盘可用空间和导入临时开销估算峰值，另按 [产品介质容量公式](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/tools/n3w_t1_core_updater_ha_mounted_media.py#L534-L571)核对 OTA 阶段可用空间。在未取得实测空间证据时保持容量待核。
2. **获准后切入前代。** 确认 HA 和 Manager 静止并保留 Broker。把原 HA 数据及两个 Manager 数据目录留在同盘受保护位置，把独立测试内容接到产品标准路径。保留标准启动配置和运行绑定的可恢复副本。镜像装载、应用停启和目录切换归属前代环境建立授权。先核对运行角色、应用版本、本机 MQTT 认证、可重复的测试收数和历史样本。
3. **为下阶段 OTA 的目标装入留出真实路径。** 固定候选要求第一次释放前代时目标引用尚未存在，或该事务已经持有目标装入证明。备用机现有 `2026.10.4-5881590f` 恰占用该引用。进入 OTA 前须确认它不再占用目标引用，再由正式流程从精确 USB 归档装入目标。优先保留原镜像的本地回退引用并校验占用空间，有空间冲突时以 Mac 已验证归档作为恢复来源并核对回装空间。变更目标引用前确认容器依赖、有无其他引用、离机归档和回退入口，按单独授权执行。 [源码检查](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/tools/n3w_t1_core_updater_ha_recovery_startup.py#L678-L693)
4. **准备前代失败或 R8 结束时回到原环境。** 未启动正式 OTA 时按切换恢复标记停止测试应用、回接原目录和启动配置。正式 OTA 开始后先通过产品恢复路径处理该事务，取得稳定终态后再恢复原环境。使用本地保留的原镜像或 Mac 上已核验的两份归档恢复原启动引用。原目录不可用时，将加密副本认证解密到隔离暂存区，核验权限、配置和 SQLite 后再恢复。恢复启动后核对标准单元、实际 HA 与 Manager 身份、HTTP、MQTT、历史样本及当时可用的收数证据。核对连续运行阶段的 Broker 实例和事务稳定性。
5. **授权边界。** 之前的授权覆盖原环境数据备份和恢复。前代环境切换、V1.2 恢复组件部署、USB 写入、正式 OTA 或断电均需对应实机授权。USB 已见 ext4 分区，实际可用空间和独占访问资格待核。

