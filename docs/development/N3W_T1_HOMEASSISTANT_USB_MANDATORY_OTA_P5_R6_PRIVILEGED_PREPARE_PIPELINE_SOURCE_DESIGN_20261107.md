# N3-W T1 Home Assistant mandatory-USB OTA R6 privileged PREPARE pipeline source design — 2026-11-07

## 1. Gate

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R6_PRIVILEGED_PREPARE_PIPELINE_SOURCE_DESIGN_20261107_01
RESULT=CLOSED_PASS_SOURCE_DESIGN
R6_SCOPE=REPOSITORY_SOURCE_DESIGN_ONLY

LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
REAL_USB_MUTATION=false
SERVICE_MUTATION=false
DOCKER_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

R6 freezes the next implementation boundary after the R5 real-T1 read-only PASS. It deliberately does not activate R4 on production and does not implement the destructive INSTALL half of the Home Assistant transaction.

## 2. Why direct activation is rejected

R4 correctly provides a narrow Manager-to-host IPC boundary, but its executor intentionally stops at intent admission:

```text
PREPARE: U0 -> U1 only
INSTALL: U4 -> U5 only
```

Missing production behavior includes:

- host-owned removable-media discovery and fail-closed target selection;
- displayable device model/capacity evidence before destructive confirmation;
- explicit transaction-bound confirmation that all USB contents may be erased;
- real GPT/ext4 format, UUID binding and measured-capacity/self-test;
- direct-to-USB target download and exact verification;
- a long-running privileged host worker/service;
- concrete host release/admission resolver;
- production runtime directory/socket/manifest publication;
- dynamic installed-version authority after a later successful HA commit;
- U5 -> U13 predecessor export, HA-data backup, cutover, health acceptance and rollback.

Turning on the R4 Manager settings now would expose a product surface that cannot complete PREPARE and therefore would be a false activation.

## 3. Program split

The successor is split at the existing user stop point:

```text
R7A = PREPARE pipeline source implementation
      U1 -> U4
      no production HA stop
      no predecessor deletion
      no live install authorization claim

R7B = INSTALL / recovery pipeline source design + implementation
      U5 -> U13A/U13B
      predecessor export
      HA data protected backup
      service quiesce
      internal cutover
      acceptance / rollback
```

This prevents unresolved backup-confidentiality and destructive-cutover design from contaminating the already well-defined preparation path.

## 4. R7A production ownership model

R7A source must preserve the three-container product architecture.

```text
DOCKER_PRODUCT_SERVICES=3
FOURTH_DOCKER_SERVICE=false

MANAGER=non_privileged_control_plane
PRIVILEGED_OWNER=host_side_T1_Core_Updater
HOST_DAEMON=systemd_managed

MANAGER_UID=999
MANAGER_GID=999
MANAGER_DOCKER_SOCKET_ACCESS=false
MANAGER_BLOCK_DEVICE_ACCESS=false
MANAGER_ROOT_PRIVILEGE=false
```

A repository-owned host service may run with effective UID 0 for bounded block/media operations while using primary GID 999 so a `0660` Unix socket is `root:999`. The runtime directory is host-owned and non-world-writable.

Frozen production locator:

```text
HOST_RUNTIME_DIR=/run/n3w-t1-ota
HOST_SOCKET=/run/n3w-t1-ota/ha-ota.sock
MANAGER_RUNTIME_MOUNT=/run/n3w/t1-ota
MANAGER_SOCKET=/run/n3w/t1-ota/ha-ota.sock
MANAGER_MANIFEST=/run/n3w/t1-ota/approved-homeassistant.json
SOCKET_MODE=0660
EXPECTED_PEER_UID=999
```

The Manager receives the runtime directory read-only. Connecting to the Unix socket must not grant filesystem-write authority.

## 5. Host daemon and resolver

R7A must add a repository-owned executable host entrypoint around the existing `UnixSocketHaOtaServer` and `HaUsbIpcExecutor` instead of inventing a second updater framework.

The concrete `HostOtaAdmissionResolver` must:

- accept only a release identity, never caller-supplied paths/devices/Docker arguments;
- read one host-owned approved Home Assistant release envelope from a fixed root-owned path;
- validate exact schema, approval/signature state, target manifest identity and release binding;
- derive current Home Assistant runtime identity from the existing updater host observation primitives;
- reject current/target drift and unexpected component/platform;
- never trust Manager/MQTT to choose block devices or mount paths.

If no approved release is present, the service is healthy but reports no actionable update. Repository files by themselves are not live approval authority.

## 6. PREPARE interaction contract

The existing PREPARE button is retained as the non-destructive start of preparation:

```text
PREPARE
-> create/bind transaction U1
-> inspect removable media read-only
-> publish exactly one eligible candidate's public model/capacity/fingerprint
-> state=USB_REQUIRED_CONFIRMATION
```

PREPARE alone MUST NOT format media. The mandatory-USB architecture requires the user to see the selected device identity/capacity and explicitly confirm erasure.

R7A therefore adds one bounded confirmation intent:

```text
ACTION=CONFIRM_USB_ERASE
AUTHORITY=existing U1 transaction + host-observed single candidate
CALLER_SUPPLIED_DEVICE_PATH=false
CALLER_SUPPLIED_MOUNT_PATH=false
```

The confirmation must be transaction-bound. Host code re-enumerates and proves that the same single eligible removable device still matches before any write. Candidate ambiguity, disappearance or identity drift returns to a non-mutating stop state.

The Home Assistant control surface may expose a dedicated confirmation button whose visible text clearly states that all contents on the displayed USB device will be erased. The exact button label is presentation detail; the two-step semantic boundary is not optional.

## 7. USB target-selection contract

Before any format, source must prove:

- exactly one eligible removable USB mass-storage device;
- target is not the root/internal device or an ancestor of any production mount;
- target is not read-only;
- no target partition backs a current production mount;
- stable public fingerprint/model/capacity are available for user confirmation;
- post-confirmation re-enumeration matches the frozen candidate.

Use `/sys`, `lsblk --json`/equivalent structured host facts and exact major/minor ancestry. String matching on `/dev/sdX` names is not sufficient authority.

All ambiguous cases fail closed.

## 8. Format and capacity contract

After valid confirmation only:

```text
wipe old signatures only on the bound whole device
-> create GPT
-> create one data partition
-> format ext4
-> obtain filesystem UUID
-> mount under a fixed host-owned transaction mount root
-> bounded write/fsync/read/hash self-test
-> measure usable filesystem bytes
-> require usable >= 15032385536
-> run complete transaction-capacity formula
-> persist U2 only after durable success
```

Formatting must never occur from PREPARE without the separate confirmation boundary.

## 9. Direct-to-USB target preparation

R7A advances U2 -> U4 while production Home Assistant remains running:

```text
U2 USB_QUALIFIED_FORMATTED_BOUND
-> U3 TARGET_DOWNLOADING_VERIFYING
-> HTTPS/download adapter streams exact compressed target directly to USB
-> verify archive size + SHA256 + approved release/target identity
-> fsync artifact and transaction metadata
-> U4 READY_TO_INSTALL
```

No full target archive may first be staged on the internal root filesystem.

R7A ends at U4. It must not export the predecessor image, stop Home Assistant, create HA-data backup, delete/load production images, claim install authorization or enter U5.

## 10. Durable state and power-loss behavior

The host-side active transaction remains `/var/lib/n3w-t1-core-updater/homeassistant-usb-upgrade.json`.

USB transaction metadata under the mounted filesystem must be fsync-durable before accepting each phase advance. On process restart:

- U1 may re-enumerate read-only and require a new destructive confirmation if no durable confirmation claim exists;
- U2/U3 must require the same filesystem UUID and bound public device identity;
- a partially downloaded target is never promoted without full re-verification;
- U4 is reusable only when the target artifact and bound filesystem still verify exactly;
- missing/wrong media produces a recoverable waiting state, not automatic formatting of another device.

## 11. Manager/runtime version authority

The current R4 Manager stores `installed_version` as startup configuration. That is sufficient before activation but is not a durable post-upgrade version authority.

R7A must not introduce a false fix by hard-coding `2026.10.0`. Source must separate:

```text
CURRENT_INSTALLED_HA_VERSION = host-observed / accepted current stack authority
LATEST_APPROVED_HA_VERSION = approved release manifest
```

The IPC/status contract may be extended in a backward-compatible versioned response so Manager projection can use host-observed installed version. A later successful U13A commit must not require a stale Manager restart merely to display the new installed version correctly.

## 12. Production wiring is prepared but remains disabled

R7A source may add reviewed assets for later activation:

- a host systemd unit for the HA OTA daemon;
- runtime-directory ownership/mode contract;
- Manager read-only runtime bind mount in the fresh production Compose template;
- opt-in OTA environment wiring;
- deployment/source tests proving no Docker socket/block/root privilege reaches Manager.

Default production activation remains OFF. Repository source presence does not authorize installation or service enable/start on a real T1.

## 13. Security / failure guards

R7A must preserve:

- KF-133 confirmation-before-mutation semantics;
- KF-142 production SSH transport contract for later physical gates;
- no credentials/private backup material in public evidence;
- no unbounded shell or caller-supplied command path;
- no automatic use of a second/remapped USB after identity drift;
- no replay of historical P5/Attempt03 authorizations;
- no Generic V2 Manager/Broker regression.

## 14. Required source/tests for R7A

Minimum implementation set:

1. concrete host daemon/entrypoint;
2. concrete fixed-authority admission resolver;
3. removable-device inventory and root/production-device exclusion;
4. transaction-bound USB candidate/confirmation state;
5. ext4 format + UUID + measured-capacity host adapter behind an injectable interface;
6. direct-to-USB target stream/download verifier;
7. U1 -> U4 orchestrator with restart/reinsert behavior;
8. versioned IPC/status extension for candidate/confirmation/version projection;
9. Manager MQTT presentation for USB confirmation and READY_TO_INSTALL;
10. systemd/Compose activation assets default-OFF;
11. pure unit tests plus synthetic block-device/command-runner tests;
12. negative tests for internal disk, multiple USBs, read-only media, capacity edge, identity drift, corrupt target and power-loss checkpoints;
13. existing R3/R4 Manager A-to-B and host IPC regressions remain green.

Real block-device writes are not required or allowed in this source-implementation gate.

## 15. Deferred R7B decisions

R7A must not silently choose these yet:

- exact HA-data backup authenticated-encryption/key-recovery design;
- exact predecessor image export encoding beyond the already frozen artifact-family constraints;
- U5+ one-shot install authorization packaging;
- production service-stop/cutover/rollback live procedure.

Those are destructive-install concerns and will be frozen before U5+ source implementation.

## 16. Next ONE gate

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R7A_PREPARE_PIPELINE_SOURCE_IMPLEMENTATION_20261107_01
R7A_SCOPE=SOURCE_IMPLEMENTATION_AND_SYNTHETIC_VALIDATION_ONLY
REPOSITORY_MUTATION=true
LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
REAL_USB_MUTATION=false
SERVICE_MUTATION=false
DOCKER_RUNTIME_MUTATION=false
BOARD_ACCESS=false
MERGE=false
AUTO_EXECUTE_PHYSICAL_VALIDATION=false
```

R7A may proceed through source implementation, local/synthetic tests, CI and public-safe repository archiving. It must stop before any real-T1 activation or real USB write.
