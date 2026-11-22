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
| 自然业务收数 | `NO_FRESH_CURSOR_OBSERVED`。操作者确认观察期间没有节点连接，现象符合预期 |

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

本次观察返回 `R8_MANAGER_RECEIVE=NO_FRESH_CURSOR_OBSERVED`。操作者确认观察期间没有测试节点连接备用 T1，因此原环境这一轮未看到新游标符合预期，镜像校验通过。R8 测试环境仍须取得受控收数和历史样本，供升级及回滚验收使用。HA 的 SHA-256 对应从备用机运行镜像导出的原环境回退归档，正式 OTA 目标仍使用工件 13391983948 的冻结归档。

### 建立前代基线和返回原环境的顺序

状态为方案复核，待冻结实机执行器及其离线验证结果，实机写入授权待确认。用同一台备用 T1、同一 Broker 和本机现有的 MQTT 认证材料。独立前代环境使用 `2026.10.0-0c73235a`、`fresh-741a1463e7de` 和由精确前代初始化的数据。准备 R8 测试基线时必须防止试验样本污染原有历史或触发现场控制，R32 真实旧数据的升级仍未覆盖。

1. **先验证退出路径。** 核验 Mac 上的 HA、Manager 原运行归档和数据备份，复核现场原启动文件、镜像引用、三个写入目录、Broker 容器身份、密钥可用性和事务记录。为受保护目录保留同文件系统内的独占保存位置，并记录每一步及恢复标记。加密副本是独立保障，恢复需同一备用机的系统根密钥。使用实际镜像层、内置盘可用空间和导入临时开销估算峰值，另按 [产品介质容量公式](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/tools/n3w_t1_core_updater_ha_mounted_media.py#L534-L571)核对 OTA 阶段可用空间。在未取得实测空间证据时保持容量待核。
2. **获准后切入前代。** 确认 HA 和 Manager 静止并保留 Broker。把原 HA 数据及两个 Manager 数据目录留在同盘受保护位置，把独立测试内容接到产品标准路径。保留标准启动配置和运行绑定的可恢复副本。镜像装载、应用停启和目录切换归属前代环境建立授权。先核对运行角色、应用版本、本机 MQTT 认证、可重复的测试收数和历史样本。
3. **为下阶段 OTA 的目标装入留出真实路径。** 固定候选要求第一次释放前代时目标引用尚未存在，或该事务已经持有目标装入证明。备用机现有 `2026.10.4-5881590f` 恰占用该引用。进入 OTA 前须确认它不再占用目标引用，再由正式流程从精确 USB 归档装入目标。原镜像退出现行运行组合后，按下文的存放原则使用已验证的离机归档作为回退来源，核对回装空间。变更目标引用前确认容器依赖、有无其他引用、离机归档和回退入口，按单独授权执行。 [源码检查](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/tools/n3w_t1_core_updater_ha_recovery_startup.py#L678-L693)
4. **准备前代失败或 R8 结束时回到原环境。** 未启动正式 OTA 时按切换恢复标记停止测试应用、回接原目录和启动配置。正式 OTA 开始后先通过产品恢复路径处理该事务，取得稳定终态后再恢复原环境。使用本地保留的原镜像或 Mac 上已核验的两份归档恢复原启动引用。原目录不可用时，将加密副本认证解密到隔离暂存区，核验权限、配置和 SQLite 后再恢复。恢复启动后核对标准单元、实际 HA 与 Manager 身份、HTTP、MQTT、历史样本及当时可用的收数证据。核对连续运行阶段的 Broker 实例和事务稳定性。
5. **授权边界。** 之前的授权覆盖原环境数据备份和恢复。前代环境切换、V1.2 恢复组件部署、USB 写入、正式 OTA 或断电均需对应实机授权。USB 已见 ext4 分区，实际可用空间和独占访问资格待核。

## 切换和回退容量取证

PR #815 仍为草稿，候选 `741a1463e7de065401749e47e59d30b295d5d6e8` 与原记录一致，base SHA `4fde1b7c5cc0aa224fa3574b8b4cc638edd93647`。使用 [固定取证脚本](https://github.com/chrenguo-stack/HomeAssistant/blob/9984b567eca3e72d0640c490fe8307f4098d90c3/tools/execution_packages/n3w/t1_ota_spare_readonly/r8_space_evidence.py)，SHA-256 `ba9b81a4b9787e498c9ed4e2c0085f0c46cfdeb0963cd51d4921f7c669ebce85`。

- T1 端绑定既有备份回执和三项运行镜像，只读取文件系统可用空间、候选镜像标签是否已存在，以及 USB 介质和挂载状态。已绑定的 ext4 分区在未发现挂载且超级块显示干净时读出扣除保留块的估算余量。最终以正式预检的实测容量为准。
- Mac 端复用原有两个 ZIP 缓存，只读出三个已固定摘要的成员。临时文件一次保留一件，用原候选恢复包中的解析器校验并测量镜像层展开字节数。结合 T1 实测用于比较切换、回退与 [OTA 容量计算](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/tools/n3w_t1_core_updater_ha_mounted_media.py#L534-L571)。镜像层展开值和 Docker 实际峰值空间有差别，需结合存储驱动、镜像共用层与临时写入预算。
- 本地编译与离线样例通过，覆盖普通及 gzip 镜像包、摘要不符、干净 ext4 估算、待回放日志、介质身份变化和其他命名空间挂载。实机容量和镜像层测量已完成，见下文。本脚本不在 T1 写入文件、不装载镜像、不停服、不挂载 U 盘。实机切换、镜像标签变更及 OTA 各按相应授权执行。

### 容量实测与内置盘阻塞

2026-11-22（新加坡时间），操作者完成 `R8_SPACE_EVIDENCE_COLLECTED=true`。Docker 存储驱动为 `overlayfs`，内置盘系统、Docker、HA、Manager 和回放数据共用同一文件系统。前代 HA 和候选 Manager 的标签均未出现在镜像列表，目标标签仍绑定原运行 `2026.10.4` 镜像。

| 项目 | 实测字节 |
| --- | ---: |
| 内置盘当前可用 | 4755894272 |
| USB 设备容量 | 32015122432 |
| USB 未挂载时估计可用（扣除保留块） | 28148965376 |
| 前代 HA 展开层（22 层） | 2448486400 |
| 候选 Manager 展开层（9 层） | 212973056 |
| 正式目标 HA 展开层（22 层） | 2447053824 |

- 冻结候选的安装前材料检查要求内置盘可用空间至少为 `max(签发的内部安装预算, 目标展开层) + 前代展开层 + HA 恢复工作区 + 签发的恢复附加预算`。两份 HA 镜像展开层之和为 `4895540224` 字节，现测已经少 `139645952` 字节，尚未计入恢复工作区和预算。检查发生在正式 OTA 释放前代之前，因此不能把预期释放的前代空间计入这项准入。以固定恢复包真实公式及实测数运行离线模拟得到拒绝结论。 [公式](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/tools/n3w_t1_core_updater_ha_mounted_media.py#L534-L565) · [调用时序](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/tools/n3w_t1_core_updater_ha_usb.py#L211-L251)
- 两项前代启动镜像的展开层另计 `2661459456` 字节。若按不复用层且暂不回收任何资源作粗算，装入后余量为 `2094434816` 字节，距离两份 HA 展开层之和约差 `2801105408` 字节。共享层、本地快照、Docker 暂存和实际可回收块尚未量化，粗算用于确定诊断方向。仅将原 HA 改为回退标签不会释放镜像层。按下文的存放原则，把无需常驻运行的镜像作为 U 盘归档候选，先盘点实际可回收空间和依赖。
- U 盘估计余量超过目标归档与前代原始 tar 合计 `3283863007` 字节。正式资格仍需核对绑定介质、实际可用空间与本笔签发的 USB 安装/恢复预算。当前不改产品容量规则、不释放任何资源、不装入前代、不写 USB。
- 下一步是 [只读盘点](https://github.com/chrenguo-stack/HomeAssistant/blob/d5cfa408225def2b0bb365ee8b09a6a0c65eca0e/tools/execution_packages/n3w/t1_ota_spare_readonly/r8_space_evidence.py)，SHA-256 `5b1b6f109c054f39579dcf3590ddc6d6fa8c91858bd169814adbc9ecbcf3df9d`，用 `--inventory` 跳过 Mac 镜像读取。它采集 Docker 整体统计、包括停止容器在内的镜像引用，以及同盘缓存和日志的占用，只列候选，不把镜像标称大小算成可释放空间。编译及模拟通过，验证停止容器仍保护其镜像、原环境镜像排除以及模式不会下载或读取大包。实机结果见下文。

### 内置盘与 U 盘的存放原则

2026-11-22（新加坡时间），操作者明确指定：内置盘只长期保留 T1 运行和本机恢复所需内容，其余需要留存的材料归档到 U 盘。R8 优先沿用这一安排。

| 位置 | 保留内容 |
| --- | --- |
| T1 内置盘 | 系统和启动文件、当前运行的镜像与配置、HA 活跃数据库、Manager 状态和待补传队列、Broker 持久数据及本机密钥、用于断电接管的最小持久事务账本。镜像装入、恢复和切换的临时工作区仍按产品路径及容量公式核对 |
| U 盘 | OTA 下载包、退出现行运行组合且需保留的旧镜像归档、受保护数据的加密备份、历史日志和诊断等归档。产品 OTA 材料按既有协议写入 `N3W-OTA/<事务标识>/`，普通归档使用另设的独立目录，避免混入事务。本轮保全的 Mac 副本仍作为独立恢复来源 |
 
下一步沿用已发布的只读盘点，结合容器引用、启动配置、回退引用和文件用途确定归档对象。停止的容器和未运行的回退方案也可能依赖某个镜像，不能按 Docker 当前容器列表直接删除。可重建的软件包缓存按需管理，盘点不会将其自动列为历史保留内容。对确定需迁出的材料，先绑定 U 盘并确认空间，把文件复制到新目录并从 U 盘回读、比对摘要及必要的恢复身份，再按实际授权释放内置副本。原运行数据、现行镜像和已绑定事务在迁移前继续保留。保留盘上已有资料及事务目录，不格式化、不全局清理、不用 U 盘空间抵扣内置盘安装与恢复余量。分置原则、候选盘点与实机迁移是三个独立结果，本轮只记录了原则。

### 内置盘归档候选盘点回执

2026-11-22（新加坡时间），操作者返回 `R8_T1_STORAGE_INVENTORY`。内置盘可用 `4755783680` 字节，比两份 HA 镜像展开层之和少 `139756544` 字节，恢复工作区和恢复附加预算另计。

| 候选 | 只读观察 |
| --- | --- |
| Manager `fresh-bf38e388497b` | 容器引用数为 0，标称 `62936949` 字节，ID `sha256:e88a22b29b93b0db0d3b4f592cb0fd773169d1dc0f043219f14d5247ed859dff`。对应 [R7A 兼容性验证提交](https://github.com/chrenguo-stack/HomeAssistant/commit/bf38e388497b0d480f4bd322426e32a98652cf6c) |
| Manager `fresh-7807271e4c48` | 容器引用数为 0，标称 `62936651` 字节，ID `sha256:7e3f09ed47010a18de215faa426113b7faba4e220b41bb9dcafd8ee1d4acf20b`。对应 [R7A 兼容性修复提交](https://github.com/chrenguo-stack/HomeAssistant/commit/7807271e4c48161f2fad96a7886fa4c24b038321) |
| `/var/tmp` | `383590400` 字节，同一文件系统，尚未分项。已核验的 R8 备份回执和恢复工具也在此目录之下，按文件分类，不整目录迁移 |
| 其他 | apt 下载缓存 `12288` 字节、日志 `995328` 字节，Docker 构建缓存和本地卷报告为 0 |

Docker 汇总报告 5 个镜像、3 个活跃，显示 `5.536GB` 可回收。该汇总无法与两项具体候选的标称合计 `125873600` 字节相对应，当前没有证据可将汇总数字作为实际可释放预算。即使把两项候选的标称值全部计入，距离两份 HA 展开层之和仍少 `13882944` 字节。原 HA 仍有 1 个容器引用，归档副本已验证，现场镜像继续承担运行。

[固定盘点脚本](https://github.com/chrenguo-stack/HomeAssistant/blob/3f79becbf696c96f76a27ec9a86b86ba6874409c/tools/execution_packages/n3w/t1_ota_spare_readonly/r8_space_evidence.py) SHA-256 `066f4877d4b78e1bc28a774c015c446642560fb199ab5ef81da2d85bd055aac9`，新增 `--archive-review` 模式。它列出同盘重点目录的大项，并只输出两项旧镜像在 Compose 和现有事务索引中命中的引用类别，配置内容和事务正文只在 T1 上读取。没有命中仅限检查范围，不能据此删除。已验证编译、引用类别、路径空格、目录分项及不下载大包。取证后确定可复制到 USB 新目录的对象和需在主机保留的引用，再按授权执行归档与释放。内置盘准入仍阻塞，USB 和内置盘原有文件尚未改动。

### 归档对象细查与 V1.2 设计修订

2026-11-22（新加坡时间），操作者返回 `R8_T1_ARCHIVE_REVIEW`，内置盘可用 `4755718144` 字节，距离两份 HA 镜像层基线少 `139822080` 字节，另计恢复工作区及附加预算。

- 两个旧 Manager 镜像均命中现有事务状态记录，`fresh-bf38e388497b` 同时命中事务历史。命中表示需按实际字段判定状态与回退用途；没有推定这些镜像仍为活动事务所需，当前也未批准释放。
- `/var/tmp` 下六个旧执行目录的已分配量合计 `378527744` 字节，`/root` 下两个旧执行目录合计 `142393344` 字节。先核对内容和原流程引用，再决定可留存资料迁出清单。目录大小不是可释放预算。
- `/var/lib/n3w-t1-core-updater` 的目录总量为 `839032832` 字节。该目录包含本机事务主记录，目录本身留在内置盘。后续只能按文件识别已结束事务的大归档和可重新取得的工件。Docker 数据、系统包管理元数据和活动数据库保持按其运行用途管理。
- 将操作者指定的 USB 优先原则写入 [V1.2 设计第 4 节](https://github.com/chrenguo-stack/HomeAssistant/blob/a22ba8e7eeec03847a05521928fcc03e5fd8b9b6/docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.2_20261119.md#4-u-盘容量与数据写入)，明确运行数据、离线归档、受保护备份及独立容量预算的位置。此次提交为文档修订。归档或释放须另核对来源用途与回读结果，本次无设备写入。

### 迁出候选与容量情景

优先逐文件核对六个 `/var/tmp` 历史执行目录和两个 `/root` 历史执行目录。目录合计分配量 `520921088` 字节。已从 [U1 历史执行器](https://github.com/chrenguo-stack/HomeAssistant/blob/82f738dd37a5ad99f66e9e69679027fa843d0ca0/tools/execution_packages/n3w/u1/manager_a_to_b_v2_live_apply/executor.py#L45-L51) 确认其中一处使用 `greenhouse-manager-arm64.tar` 作为上传输入，但当前盘点只有目录分配量，现场文件是否仍存在及有无恢复引用待核。主机事务账本目录的 `839032832` 字节整体不列入迁出预算。两个旧 Manager 镜像命中事务文件，名义大小不计入可释放量。已验证的当前运行镜像与活动数据库继续承担运行。

| 场景 | 内置盘可用（字节） | 相对两个 HA 镜像展开层下限 `4895540224` 的差额 |
| --- | ---: | ---: |
| 实测 | 4755718144 | −139822080 |
| 假设八个目录均可核验迁出且释放全部分配量，装入前 | 5276639232 | +381099008 |
| 上一行再按无层复用估算装入前代 HA 与候选 Manager，原镜像还在盘上 | 2615179776 | −2280360448 |

下限还未包括 HA 恢复工作区、恢复附加预算及可能高于目标展开层的安装预算。共享层、导入暂存与原镜像退出测试运行后的实际可回收量会改变装入后余量。归档候选合计不足以证明 R8 准入；应在文件核对、经批准的迁出和容量实测后，按冻结候选公式复核。此次仅作估算，实际未迁出或释放文件。

### V1.0 同版本实机容量对照

[Core Stack V1.0 第 12–13 节](https://github.com/chrenguo-stack/HomeAssistant/blob/09722741020004ba9b89c93fbe8ab33d150faed7/docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.0_20261106.md#L321-L366) 要求涉及 HA 镜像更新时使用 USB。在前代仍运行时准备目标包，USB 保存前代恢复镜像与升级前数据。U13A 实机路线在恢复材料校验通过后，由 R38/U10 释放精确的已停 HA 容器及其前代镜像，Broker 不释放。R39 再核内置盘导入预算，之后读得目标已装入时的内置盘余量。 [R38 实机回执](https://github.com/chrenguo-stack/HomeAssistant/commit/d2bc4fcd1bd9d6466f403b3f4155872ac2bac230)

| 实测阶段 | 容量 |
| --- | --- |
| 2026-11-05 早期内置盘基线 | 总 `14453903360` 字节，已用 `8651415552`，可用 `5785710592`。[基线](https://github.com/chrenguo-stack/HomeAssistant/blob/38cf7df4c38d1c6260a562b8d8f6ddadfeff5c37/docs/development/N3W_T1_CORE_UPDATER_HOMEASSISTANT_STORAGE_POLICY_REVIEW_CLOSURE_20261105.md#L33-L65) |
| 2026-11-16 U13A U10 完成后的 R39 | 内置盘可用 `10887344128` 字节。门槛 `4950401057` 由目标导入预算 `3339788321` 与余量 `1610612736` 构成。[实机回执](https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6907345808) · [预算清单](https://github.com/chrenguo-stack/HomeAssistant/blob/d81c6de0a25fd9d4ae662f55e8cffc5c4a7036c4/tools/execution_packages/n3w/r7a/u11_target_install_readonly_preflight_r39/manifest.json#L124-L131) |
| 同日目标装入后的 R41 | 内置盘可用 `5665595392` 字节。相对 R39 的差为 `5221748736` 字节，属于前后快照差，不能据此归因到单个镜像或推断整个过程的峰值。[实机回执](https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6918937368) |
| 同笔 U13A 的 USB | 目标包 `835309535`、前代包 `743074537`、加密数据备份 `2178281` 字节，三笔材料合计 `1580562353` 字节（不含目录和元数据），当时盘上实测可用 `28132077568` 字节。[USB 回执](https://github.com/chrenguo-stack/HomeAssistant/pull/807#issuecomment-6906029215) · [加密备份](https://github.com/chrenguo-stack/HomeAssistant/commit/51186e69b1885a9f1b98c4713558c41767e19d79) |

早期基线与 U10 释放前不是同一时点，未从这两项证据推算旧镜像释放字节。R8 当前冻结候选在释放前代前就核验目标导入与整个前代恢复预算之和，导入前还会重核。V1.0 实机余量和准入时点不用于本次放行；本次仅作历史对照。

### 两项预算相加的源码原因

新版导入和旧镜像恢复按分支顺序发生。当前冻结候选在已导入目标之后回滚时，会停止应用写入，按写入边界恢复原数据，然后装回前代镜像；装回前代之前没有针对本笔失败目标的镜像释放步骤。因此，新版的磁盘占用可能与恢复前代所需空间重叠。加法是当前实现对重叠占用的预留，不表示两次 Docker 导入会并发。候选还在释放前代之前执行该容量判定，因而低空间设备可能在可以回收前代占用之前被拒绝。 [回滚调度](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/tools/n3w_t1_core_updater_ha_usb.py#L748-L788) · [前代装回及启动](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/tools/n3w_t1_core_updater_ha_recovery_startup.py#L939-L988) · [预算公式](https://github.com/chrenguo-stack/HomeAssistant/blob/741a1463e7de065401749e47e59d30b295d5d6e8/tools/n3w_t1_core_updater_ha_mounted_media.py#L534-L565)

低空间改进需在确认两个回退材料已可用之后，明确失败目标的事务身份、写入已静止、精确释放及断电后的续办，再按目标安装与前代恢复的阶段预算和实际可回收空间核算。仅修改加法会让当前回滚继续保留失败目标的占用。本次为只读源码核对，冻结候选和实机状态未变。
