> **2026-10-10 当前决策已覆盖本文件的整机擦盘建议。** 状态：`SUPERSEDED_DISK_ERASE_PREFLIGHT`。用户明确决定**保留现有 Armbian、网络、SSH 与 Docker**，仅重建核实属于温室系统的旧软件和数据。现行权威文档：`docs/development/N3W_T1_SOFTWARE_CLEAN_REDEPLOY_PRESERVE_ARMBIAN_AUTHORITY_20261010.md`。原记录保留供历史追溯，不得作为擦盘、清系统或删除无关 Home Assistant 的授权。

# N3-W T1 全新部署 F0：整机目标、安装介质与清盘范围只读确认（2026-10-10）

## 本门定义

```text
TASK=N3W_T1_FULL_FRESH_INSTALL_F0_HOST_TARGET_MEDIA_AND_DESTRUCTION_SCOPE_READONLY
MODE=READ_ONLY
T1_ERASE=false
T1_REINSTALL=false
T1_SERVICE_MUTATION=false
BOARD_MUTATION=false
GITHUB_PRIVATE_SECRET_UPLOAD=false
STOP_AFTER=F0_TARGET_SCOPE_REPORT
```

本记录是**下一阶段操作前检查清单**，不是声称 T1 已被访问。只允许检查，不可执行 `docker system prune`、`docker compose down -v`、`rm -rf`、`wipefs`、`dd`、`mkfs`、`parted`、`sgdisk`、`shred`、停容器、关闭防火墙或重启 T1。

## 1. 要确认的六个问题

1. **是正确的 T1 吗？** 实际物理/虚拟机身份、CPU 架构、主机型号、目前 OS、宿主 MAC、安装介质/本地控制台是否可用。
2. **要擦哪块盘？** 从实际系统启动分区、挂载点、盘型号/容量/序列确认系统盘；是否包含另一个挂载的 HDD/SSD、外部盘或 NAS。不可因为设备名看起来像 `/dev/sda` 就猜。安装器中以稳定物理 ID 和当前启动分区交叉验证。
3. **重装后怎样找回 T1？** 有线网口、DHCP 分配、网关、DNS、SSH 公钥、安装镜像/USB/显示器键盘或经确认的带外管理通道；不能仅靠当前 SSH 会话运行擦盘命令。
4. **会同时消失什么？** Manager 注册/凭据/replay/relay-key 数据、Broker DynSec/retained/持久会话/CA/keys、HA 数据和集成、其他与温室无关服务、Docker 镜像/数据卷、日志、系统账户、SSH 主机密钥、TLS 证书、手工网络/防火墙。对本机所有数据一概按**不可迁移丢失**理解。
5. **重建材料够吗？** 可验证 OS 安装介质 hash、GitHub 受信源码/精确镜像、Docker/Compose 安装源、受控的离线新 CA 生成方式、Manager/HA 配置模板、配对 Setup Secret 的安全交付渠道、硬件板卡可用物理操作。
6. **会影响哪些设备？** 所有需要 T1 的旧节点 MQTT 认证/证书信任将不再有效；板卡 NVS 的旧配对不是因为 T1 重装就自动清除。每个板卡都需单独清洁首次配对计划。

## 2. 推荐在 T1 Linux 本机只读收集的证据

macOS Terminal 可以经现有、明确指向 T1 的 SSH 登录后执行以下**只读信息命令**（不包含远端删盘命令）。若系统不支持其中某个命令，记录 `NOT_AVAILABLE`，不要安装工具或修改配置以满足 F0。

```sh
hostnamectl
uname -a
lsblk -o NAME,PATH,TYPE,SIZE,MODEL,SERIAL,FSTYPE,MOUNTPOINTS
findmnt /
findmnt /boot
ip -br address
ip route
docker ps -a --format '{{.Names}}|{{.Image}}|{{.Status}}'
docker volume ls --format '{{.Name}}'
systemctl list-units --type=service --state=running --no-pager
```

不要将完整 `docker inspect`、容器环境变量、`/etc/n3wfc4` 中私有 env、证书私钥、Setup Secret、SSH private key、数据库或 DynSec 凭据粘贴到公开 PR。可提炼脱敏的系统盘、操作系统类别、网卡名、服务名/影响范围供决策。以上列举的是建议执行的命令，不是已经运行的证据。

## 3. 删除边界确认页（必须根据真实 F0 填写）

```text
T1_HOST_ID=UNVERIFIED
T1_MACHINE_TYPE=UNVERIFIED
T1_OS_AND_ARCH=UNVERIFIED
TARGET_OS_DISK_STABLE_ID=UNVERIFIED
TARGET_DISK_MODEL_SIZE=UNVERIFIED
ROOT_AND_BOOT_BELONG_TO_TARGET_DISK=UNVERIFIED
OTHER_DATA_DISKS_AND_MOUNTS=UNVERIFIED
CONSOLE_OR_BOOTABLE_INSTALLER_AVAILABLE=UNVERIFIED
POST_WIPE_MANAGEMENT_ACCESS_PATH=UNVERIFIED
INSTALL_OS_IMAGE_SHA256=UNVERIFIED
NETWORK_DHCP_DNS_GATEWAY=UNVERIFIED
HA_LOCAL_DATA_TO_DISCARD=ACKNOWLEDGEMENT_PENDING
BROKER_OLD_CA_CREDENTIALS_TO_DISCARD=ACKNOWLEDGEMENT_PENDING
OTHER_T1_SERVICES_TO_DISCARD=UNVERIFIED
NODE_REPAIRING_REQUIRED=true
DATA_MIGRATION=false
ROLLBACK_DEVELOPMENT=false
ERASE_PERMITTED=false
```

F0 可通过后再设计 **F1 安装介质启动与 clean OS 安装**。清盘属于不可逆的高影响行为：需一次明确的最终范围确认，列出设备身份、**唯一系统盘**、Home Assistant 与其他服务数据是否销毁。确认后可连续执行安装，不必再围绕已放弃的旧 Manager 回退逐步请示。

## 4. 验收与 STOP

```text
F0_PASS_REQUIREMENTS=EXACT_MACHINE_AND_DISK_AND_BOOT_PATH_AND_LOSS_SCOPE_AND_INSTALL_MEDIA
F0_RESULT=NOT_EXECUTED
NEXT_ONE_GATE=N3W_T1_FULL_FRESH_INSTALL_F0_READONLY_EVIDENCE_AND_F1_INSTALL_PACKAGE_PREPARATION
```
