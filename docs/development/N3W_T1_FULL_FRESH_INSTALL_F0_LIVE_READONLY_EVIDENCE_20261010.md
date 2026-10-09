# N3-W T1 full-fresh install — F0 actual read-only host/storage evidence (2026-10-10)

## Source and limits

A user-supplied real T1 SSH read-only transcript was inspected in this conversation: `N3W_T1_F0_20261010_075407.txt`, captured 2026-10-10 07:54:11 +08:00. It contains only system observation and makes no host mutation (`T1_MUTATION=false`, `DISK_ERASE=false`, `SERVICE_RESTART=false`). The raw file has NOT been uploaded to this public GitHub branch; host machine ID, MAC, local IP and storage serial are deliberately omitted from this sanitized summary.

```text
F0_LIVE_READONLY_EVIDENCE=COLLECTED
T1_HOSTNAME=armbian
OS=Armbian_OS_26.05.0_resolute
KERNEL=6.18.26-ophub
ARCH=arm64
LINUX_BASE=ubuntu_26.04
PRIMARY_VISIBLE_DISK=/dev/mmcblk2
DISK_SIZE=14.6G
DISK_MMC_STABLE_BY_ID_PRESENT=true
ROOT=/dev/mmcblk2p2_ext4_13.8G
BOOT=/dev/mmcblk2p1_vfat_511M
MMC_HARDWARE_BOOT_AREAS=mmcblk2boot0_and_mmcblk2boot1_4M_each
ADDITIONAL_USER_DATA_DISK_SEEN_IN_LSBLK=false
PRIMARY_NETDEV=eth0_UP
NETWORK=DHCP_IPv4_WITH_DEFAULT_GATEWAY
DOCKER_SERVER_VERSION=29.7.1
T1_CURRENT_MANAGER=running
T1_CURRENT_BROKER=running
T1_CURRENT_HOME_ASSISTANT_CONTAINERS=2_running
T1_OLD_SHADOW=created
BROKER_ACTIVATION_SYSTEMD=active_running
SSH_SYSTEMD=active_running
NETWORKMANAGER=active_running
F0_HOST_MUTATION=false
```

## Decisive conclusion

Both the live root filesystem and `/boot` are partitions on **the same 14.6-GiB-class device `/dev/mmcblk2`**. An in-place destructive wipe of `/dev/mmcblk2` over the running SSH session would destroy the OS currently executing the command, without a proven recovery/alternate boot route. The separate `mmcblk2boot0` and `mmcblk2boot1` hardware areas must not be treated as ordinary partitions or touched without model-specific bootloader verification.

Therefore F0 establishes the likely target storage topology, **not** permission or technical readiness for live disk erasure. The user wants whole-T1 clean installation rather than R4 rollback design. Proceed by confirming device-tree model/compatible, hardware and storage type, boot parameters and external microSD/USB/serial console recovery/install path, and then select a board-compatible verifiable OS image.

## Next F0 read-only command family

Run (on T1 via Mac SSH) only system information reads:

```text
/proc/device-tree/model
/proc/device-tree/compatible
/proc/cpuinfo non-secret model fields
/proc/cmdline
/etc/armbian-release non-secret board fields
/sys/class/block/mmcblk2/device/{type,name}
lsblk -o NAME,PATH,TYPE,RM,SIZE,MODEL,FSTYPE,MOUNTPOINTS
/boot filenames and selected boot configuration keys
lsusb (when available)
```

Never publish machine ID, MACs, actual serial numbers, private CA/keys, env/SSH secrets, DynSec credentials or complete Docker inspect in public GitHub. The next user result is expected as `N3W_T1_BOOT_PREFLIGHT_*.txt`; do not claim it has already been executed.

```text
DEVICE_MODEL=UNKNOWN
DEVICE_SOC=UNKNOWN
MMC_DEVICE_TYPE=NOT_YET_VALIDATED
EXTERNAL_BOOT_SUPPORTED=NOT_YET_PROVEN
INSTALL_IMAGE_AND_SHA256=NOT_YET_SELECTED
EXTERNAL_CONSOLE_BOOT_MEDIUM_ACCESS=NOT_YET_PROVEN
TARGET_WIPE_AUTHORIZED=false
F0_DEVICE_ID_AND_REINSTALL_CHANNEL_STATUS=OPEN
NEXT_ONE_GATE=N3W_T1_FULL_FRESH_INSTALL_F0_BOOT_MEDIA_PREFLIGHT
NO_R4_B1I1_ROLLBACK_WORK=true
```
