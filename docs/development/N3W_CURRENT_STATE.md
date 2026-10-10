> **2026-10-10 最新新会话交接 authority**：`docs/development/N3W_T1_S20_PRODUCTION_SERVICE_CREDENTIAL_HANDOFF_READONLY_PREFLIGHT_NEW_CHAT_HANDOFF_V1.0_20261010.md`（PR #541 OPEN DRAFT）。**S19 isolated ACL = CLOSED_PASS；S20 production three-service secret handoff = READONLY PENDING。** 以下文件所含早期 S0/S14 或其他历史 NEXT_ONE_GATE 快照已被本条 supersede，不得作为当前下一执行门。只允许在新会话执行 `N3W_T1_S20_PRODUCTION_THREE_SERVICE_CREDENTIAL_HANDOFF_AND_DEPLOYMENT_PREFLIGHT`；生产 mutation、Broker 启动、端口开放与板卡访问均禁止。

## 2026-10-10 PR #541 S19 isolated permissions CLOSED_PASS; S20 source/runtime read-only next

Latest **branch** authority (does not imply merged main): `docs/development/N3W_T1_S19_ISOLATED_SERVICE_IDENTITY_INIT_PREEXECUTION_20261010.md` and `docs/development/N3W_T1_S20_PRODUCTION_SERVICE_CREDENTIAL_HANDOFF_READONLY_PREFLIGHT_20261010.md`. Exact main `d423211b6196c2f2f0f01dff072c4f877fbe58ee`; PR #541 `OPEN_DRAFT`, software-only fresh T1 rebuild preserves Armbian/SSH/NetworkManager/Docker, 45 pre-existing Docker volumes, and the two currently empty `n3wfc4` networks. Early OS disk wipe plan is SUPERSEDED. Product shall have a single Home Assistant instance.

```text
CURRENT_ROUTE=T1_SOFTWARE_ONLY_CLEAN_REDEPLOY_PRESERVE_ARMBIAN
S19_R1_STATIC_SERVICE_ACLS=PASS
S19_R3_PROVISIONING_CONTROL_RUNTIME=PASS
S19_R5_NODE_MANAGER_HA_POSITIVE_DELIVERY=PASS
S19_R6A_CORRECT_WRONG_CLIENT_ID_ANONYMOUS=PASS
S19_R6B_CROSS_TOPIC_AND_DEFAULT_RECEIVE_DENY=PASS
S19_ISOLATED_IDENTITY_AND_ACL_ACCEPTANCE=CLOSED_PASS
S19_R2_R4_HISTORICAL_FAILURES=RETAINED
S19_R4_TEST_FIXTURE_ADMIN_UNAUTHORIZED_INGRESS_PUBLISH=PROVEN
S19_R4_EXACT_RUNTIME_ACK_REASON=NOT_OBSERVED
S20_PRODUCTION_HANDOFF=OPEN_PREFLIGHT
S20_PRODUCTION_CLIENTS_CREATED=false
T1_PRODUCTION_BROKER_STARTED=false
T1_HOST_TCP8883_PUBLISHED=false
T1_LAST_REPORTED_DYNSEC_SHA256=94f3c0a3dbed90f3d2a3e96696dba8bed8093194903aeed106559090764d1ad5
T1_LAST_REPORTED_S18_BACKUP_SHA256=93c751a788200498869de39a3218a82de53e5cd3d29170360ea55959d0af85da
NEXT_ONE_GATE=N3W_T1_S20_PRODUCTION_THREE_SERVICE_CREDENTIAL_HANDOFF_AND_DEPLOYMENT_PREFLIGHT
S20_READONLY_SOURCE_RUNTIME_REBIND_REQUIRED=true
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

S20 high-value blocker: verify **real Manager/Provisioning/HA consumers and their separate private password-file ownership/mounts** before provisioning any production accounts. Manager supports `GH_MQTT_PASSWORD_FILE`, Provisioning supports `GH_N3W_PROVISIONING_PASSWORD_FILE`; Home Assistant fresh runtime secret consumption is not yet exact-bound. Historical migration package auto-generates a node account and MUST NOT be used for first-pair clean-product production (node credentials created only per actual Gate F pairing). Host state is only the latest operator report from S19-R6B on 2026-10-10, not a new SSH runtime observation; S20 must refresh read-only host evidence.

New chat authority to be generated using `NEW_CHAT_HANDOFF_STANDARD.md` + `templates/NEW_CHAT_HANDOFF_TEMPLATE.md`, frozen at `4300890dff0ce63d5a547df21426e287d084d9ee`. This top-of-file snapshot supersedes older same-file NEXT_ONE_GATE records. PR remains draft; no merge authorized.

## 2026-10-10 T1 S0 R1 real evidence classified; inspect failed 6/6, S0 R2 exact mounts next

```text
CURRENT_ROUTE=SOFTWARE_STACK_CLEAN_REINSTALL_ON_EXISTING_ARMBIAN
CURRENT_GATE=N3W_T1_SOFTWARE_OWNERSHIP_S0_R1_EVIDENCE_CLASSIFICATION_AND_NEW_CHAT_HANDOFF
S0_R1_EVIDENCE_TIMESTAMP_LOCAL=2026-10-10T08:09:13+08:00
S0_R1_RAW_REPORT_SHA256=74127af80fec997a51717cf08c72879813e7885b6a9ff99a76c999783121132f
S0_R1_CONTAINER_COUNT=6
S0_R1_CONTAINER_INSPECT_FAILURE=6_OF_6
S0_R1_NETWORK_MEMBERSHIP=PASS
S0_R1_SYSTEMD_UNIT_NAMES=PASS
S0_R1_DOCKER_ANONYMOUS_VOLUME_COUNT=46
S0_R1_EXACT_HOST_MOUNT_SOURCES=UNVERIFIED
S0_R1_EXACT_CONTAINER_FULL_ID_NAME_BINDING=UNVERIFIED
DELETE_CONTAINERS_APPROVED=false
DELETE_VOLUMES_APPROVED=false
DELETE_HOST_DIRECTORIES_APPROVED=false
N3W_MANAGER_AND_BROKER=REDEPLOY_CANDIDATES_ONLY
FC4_HOMEASSISTANT=HOLD_OWNERSHIP_UNVERIFIED
HOMEASSISTANT_AND_RECIPES_BROKER=PRESERVE_BY_DEFAULT
N3W_PRIVATE_AND_SERVICES_NETWORK=RUNNING_PRODUCTION_KEEP
KF101=OPEN_HARNESS_METADATA_CAPTURE_NO_PRODUCT_DEFECT_PROVEN
OS_REINSTALL=false
SYSTEM_DISK_ERASE=false
T1_RUNTIME_MUTATION=false
PR540=CLOSED_UNMERGED_SUPERSEDED
PR541=OPEN_DRAFT
NEW_CHAT_HANDOFF=docs/development/N3W_T1_SOFTWARE_OWNERSHIP_S0_R1_FAILED_INSPECT_NEW_CHAT_HANDOFF_V1.0_20261010.md
S0_R1_AUTHORITY=docs/development/N3W_T1_SOFTWARE_OWNERSHIP_S0_R1_EVIDENCE_CLASSIFICATION_AND_CLEAN_MANIFEST_20261010.md
S0_R2_RUNBOOK=docs/development/N3W_T1_SOFTWARE_OWNERSHIP_S0_R2_EXACT_DOCKER_JSON_AND_MOUNT_READONLY_RUNBOOK_20261010.md
NEXT_ONE_GATE=N3W_T1_SOFTWARE_OWNERSHIP_S0_R2_EXACT_CONTAINER_AND_DATA_BINDING_READONLY
LIVE_MUTATION_DEFAULT=false
BOARD_ACCESS_DEFAULT=false
```

The real uploaded evidence establishes six container names and states, six failed Go-template inspect metadata probes, 46 anonymous volume names, N3-W Docker network memberships, related unit names and listening ports. **No exact host data directory path or Docker volume belongs to an approved delete target.** Corrected S0 R2 read-only Docker JSON whitelist runbook is GitHub archived and must be executed next in a fresh conversation. Preserve Armbian, Docker, SSH, NetworkManager and both ambiguous HA/Broker resources until ownership proven. No T1 deletion or runtime action executed.

---

## 2026-10-10 T1 software clean redeploy S0 exact ownership inventory — preserve Armbian

```text
CURRENT_ONE_GATE=N3W_T1_SOFTWARE_OWNERSHIP_READONLY_EVIDENCE_AND_CLEAN_TARGET_DRY_RUN
CURRENT_ROUTE=SOFTWARE_STACK_CLEAN_REINSTALL_ON_EXISTING_ARMBIAN
PR541=OPEN_DRAFT_SOFTWARE_CLEAN_REDEPLOY
PR540=CLOSED_SUPERSEDED_UNMERGED
OS_REINSTALL=false
SYSTEM_DISK_ERASE=false
PRESERVE=ARMBIAN_KERNEL_NETWORKMANAGER_SSH_DOCKER_ENGINE
NEXT_T1_ACTION=READONLY_CONTAINER_MOUNT_PROJECT_NETWORK_SYSTEMD_INVENTORY
LAST_KNOWN_MANAGER_BROKER=UP
LAST_KNOWN_FC4_HOMEASSISTANT=UP
LAST_KNOWN_HOMEASSISTANT=UP
LAST_KNOWN_RECIPES_BROKER=EXITED
HA_INSTANCE_OWNERSHIP=UNKNOWN
RECIPES_BROKER_OWNERSHIP=UNKNOWN_PRESERVE
DELETE_TARGET_SET=NOT_YET_PROVEN
DESTRUCTIVE_CLEARANCE=false
HOST_MUTATION_THIS_GATE=false
NEXT_INPUT=N3W_T1_SOFTWARE_OWNERSHIP_*.txt
AUTHORITY_DOC=docs/development/N3W_T1_SOFTWARE_CLEAN_REDEPLOY_PRESERVE_ARMBIAN_AUTHORITY_20261010.md
S0_RUNBOOK=docs/development/N3W_T1_SOFTWARE_OWNERSHIP_S0_READONLY_INVENTORY_AND_CLEAN_TARGET_GATE_20261010.md
NEXT_ONE_GATE=N3W_T1_SOFTWARE_OWNERSHIP_EVIDENCE_CLASSIFICATION_AND_EXACT_CLEAN_MANIFEST
```

The user's corrected decision is to preserve existing Armbian, boot disk, SSH, Ethernet, network management and Docker, while rebuilding the exact greenhouse software stack and its application data. No host wipe or old R4/B1I1 rollback source work. Two live HA containers and a recipes Broker require accurate Compose mount attribution before any scoped deletion. Exact read-only command has been versioned in PR541. No T1 deletion, stop or restart occurred in this gate.

---

## 2026-10-10 T1 software-only clean redeploy — Armbian preserved; OS wipe superseded

```text
CURRENT_ONE_GATE=N3W_T1_SOFTWARE_OWNERSHIP_READONLY_EVIDENCE_AND_CLEAN_TARGET_DRY_RUN
CURRENT_USER_DECISION=PRESERVE_EXISTING_ARMBIAN_FRESH_DEPLOY_GREENHOUSE_SOFTWARE
OS_REINSTALL=false
MMCBLK2_ERASE=false
PRESERVE_HOST=ARMBIAN_SSH_NETWORKMANAGER_DOCKER_AND_UNRELATED_SERVICES
CLEAN_TARGET_SCOPE=TO_BE_IDENTIFIED_EXACT_GREENHOUSE_OWNERSHIP_ONLY
KNOWN_GREENHOUSE_MANAGER=running
KNOWN_N3W_BROKER=running
KNOWN_HOME_ASSISTANT_CONTAINERS=fc4-homeassistant_AND_homeassistant_BOTH_RUNNING
KNOWN_RECIPES_BROKER=exited_OWNERSHIP_UNVERIFIED
NO_AUTOMATIC_DELETE=HA_OR_RECIPES_OR_SHARED_DOCKER_VOLUMES
N3W_BROKER_CA_DYNSEC_RESET=PLANNED_AFTER_SCOPE_EVIDENCE
NEW_MANAGER=FRESH_3_RW_ZERO_BUSINESS_STATE
R4_B1I1_ROLLBACK=ABANDONED
PR540=CLOSED_UNMERGED
PR541=OPEN_DRAFT
LIVE_T1_MUTATION_THIS_GATE=false
NEXT_USER_REPORT=N3W_T1_SOFTWARE_OWNERSHIP_*.txt
NEXT_ONE_GATE=N3W_T1_SOFTWARE_OWNERSHIP_READONLY_EVIDENCE_AND_CLEAN_TARGET_DRY_RUN
AUTHORITY_DOC=docs/development/N3W_T1_SOFTWARE_CLEAN_REDEPLOY_PRESERVE_ARMBIAN_AUTHORITY_20261010.md
```

Prior whole-host clean installation was a superseded interpretation. Armbian, SSH, network, boot partition and Docker engine remain; inventory actual Compose ownership, mounts, HA dual-instance and recipes broker before preparing a precise greenhouse-only deletion and installation manifest. Do not restart or delete any live service in the read-only inventory.

---

## 2026-10-10 Full-clean T1 F0 real host read-only evidence — board boot-media check next

```text
CURRENT_ONE_GATE=N3W_T1_FULL_FRESH_INSTALL_F0_BOOT_MEDIA_PREFLIGHT
F0_USER_UPLOADED_REPORT=2026-10-10_075411+0800_READ_ONLY
T1_OS=ARMbian_26.05.0_resolute
T1_ARCH=ARM64
T1_BOOT_DEVICE=/dev/mmcblk2p1_vfat
T1_ROOT_DEVICE=/dev/mmcblk2p2_ext4
T1_DISK=/dev/mmcblk2_14.6G
T1_VISIBLE_EXTRA_DATA_DISKS=NONE_IN_LSBLK
T1_MANAGER_BROKER_AND_HOME_ASSISTANT=RUNNING_AT_F0_OBSERVATION
T1_SSH_REMOTE_WIPE_OF_RUNNING_ROOT=FORBIDDEN
T1_EXACT_SOC_BOARD_MODEL=UNKNOWN
MMC_STORAGE_TYPE=NEEDS_SYSFS_CONFIRMATION
EXTERNAL_BOOT_REINSTALL_ACCESS=NOT_YET_VERIFIED
NEXT_USER_BOOT_REPORT=N3W_T1_BOOT_PREFLIGHT_*.txt
OLD_PR540=CLOSED_UNMERGED_SUPERSEDED
NEW_PR541=OPEN_DRAFT
T1_DISK_ERASE=false
T1_SERVICE_RESTART=false
NEXT_ONE_GATE=N3W_T1_FULL_FRESH_INSTALL_F0_BOOT_MEDIA_PREFLIGHT
AUTHORITY_DOC=docs/development/N3W_T1_FULL_FRESH_INSTALL_F0_LIVE_READONLY_EVIDENCE_20261010.md
```

F0 output shows active OS and /boot on partitions of the same ~14.6G MMC device /dev/mmcblk2. Machine model, supported external installer/console and reliable post-reinstall access remain unknown; continue read-only board-compatibility checks before any system-disk erase. User is to execute Mac Terminal SSH boot media preflight and upload the report; no service mutations or T1 wipe performed.

---

## 2026-10-10 T1 deployment direction changed to full clean OS installation

```text
CURRENT_ONE_GATE=N3W_T1_FULL_FRESH_INSTALL_PREPARATION_AND_INSTALLATION_BLUEPRINT
USER_DIRECTION=STOP_ROLLBACK_ENGINEERING_DEPLOY_T1_FROM_ZERO
PR540_R4_B1I1=SUPERSEDED_STOP_SOURCE_WORK
NEW_BRANCH=plan/n3w-t1-full-fresh-install-from-zero-20261010
DEPLOY_TARGET=COMPLETE_FRESH_T1_OS_AND_N3W_STACK
OLD_OS_DOCKER_BROKER_MANAGER_HA_BUSINESS_DATA_MIGRATION=false
OLD_CA_DYNSEC_SESSION_TRUST_STATE_REUSE=false
HOME_ASSISTANT_REINSTALL=true
BROKER_FRESH_CA_TLS_DYNSEC=true
MANAGER_FRESH_DB_0_0_0_AND_EMPTY_RELAY_KEYS=true
N3W_BOARD_PAIRING_AFTER_T1_ACCEPTANCE=true
ROLLBACK_MODEL=NOT_IN_NEW_PLAN
T1_HOST_DISK_IDENTIFICATION=NOT_YET_PERFORMED
T1_MUTATION=false
TARGET_DISK_WIPE_AUTHORIZED=false
F0_PRECHECK=READ_ONLY_PENDING
CURRENT_DIRECTION_DOC=docs/development/N3W_T1_FULL_FRESH_INSTALL_DIRECTION_AND_EXECUTION_PLAN_20261010.md
F0_SCOPE_DOC=docs/development/N3W_T1_FULL_FRESH_INSTALL_F0_READONLY_HOST_INVENTORY_AND_ERASE_SCOPE_20261010.md
NEXT_ONE_GATE=N3W_T1_FULL_FRESH_INSTALL_F0_READONLY_EVIDENCE_AND_F1_INSTALL_PACKAGE_PREPARATION
```

User explicitly abandoned the old Manager rollback R4/B1I1 direction. All new engineering effort goes toward installing a verified clean T1 OS and then fresh Broker TLS/DynSec, Manager with zero business state, independent Home Assistant, persistence, and board first pairing. No T1 host or disk has been examined in this GitHub planning turn, no wiping has occurred, and no irreversible operation will be attempted without identifying the exact target device/disk and acknowledging full host data loss. Historical GitHub design records remain archived rather than being used as new deployment prerequisites.

---

# N3-W Current State

Updated: 2026-09-30  
Status: `CURRENT_STATE_AUTHORITY`

Fresh exact repository/runtime/physical evidence takes precedence if later evidence proves drift.


## 2026-09-30 FC4 CA rollover workstream CLOSED_NOT_PLANNED

The FC4 CA rollover / dual-trust migration workstream is intentionally closed for this product generation.

```text
FC4_PRIVATE_CA_NOT_BEFORE=2026-08-20T04:18:39Z
FC4_PRIVATE_CA_NOT_AFTER=2036-08-17T04:18:39Z
FC4_PRIVATE_CA_VALIDITY_DAYS=3650

PRODUCT_EXPECTED_RETIREMENT_BEFORE_FC4_CA_EXPIRY=true

FC4_CA_ROLLOVER_WORKSTREAM=CLOSED_NOT_PLANNED
FC4_CA_DUAL_TRUST_MIGRATION=NOT_IMPLEMENTED
FC4_CA_AGE_BASED_ROLLOVER_TESTING=NOT_PLANNED

FC4_CA_EXPIRY_MONITORING=ENABLED
KF100_ROUTE_STATUS=CLOSED_PASS
KF100_REOPEN=false
```

Reopen only if product service life is extended, units are intentionally reused beyond the current service life, the FC4 CA private key is lost/exposed/suspected compromised, security policy requires earlier replacement, or another non-age-related event forces CA replacement.

Authority: `docs/development/N3W_FC4_CA_ROLLOVER_PRODUCT_LIFECYCLE_DECISION_20260930.md`.



## 2026-09-30 KF-100 short-lived automatic renewal lab R2 CLOSED_PASS

The post-closure production-fidelity lab completed both the real renewal path and the forced rollback path using the exact installed production lifecycle executable against isolated temporary TLS material.

```text
SHORT_LIVED_CERTIFICATE_AUTO_RENEW_LAB_R2=PASS
RENEWAL_LAB_R2_RC=0

SUCCESSFUL_REAL_RENEWAL_PATH=PASS
LIFECYCLE_RESULT_SUCCESS=renewed
CERTIFICATE_REPLACED=true
CERTIFICATE_FINGERPRINT_CHANGED=true
SERVER_KEY_UNCHANGED=true
CA_CERTIFICATE_UNCHANGED=true
LIVE_TLS_USES_NEW_CERTIFICATE=true
ACTIVATION_RECREATE_COUNT_SUCCESS=1

FORCED_ROLLBACK_PATH=PASS
LIFECYCLE_RESULT_ROLLBACK=renewal_failed_rolled_back
ROLLBACK_ATTEMPTED=true
ORIGINAL_CERTIFICATE_RESTORED=true
LIVE_TLS_RESTORED_TO_ORIGINAL_CERTIFICATE=true
ACTIVATION_RECREATE_COUNT_ROLLBACK=2

PRODUCTION_CERTIFICATE_MUTATION=false
PRODUCTION_BROKER_RESTART=false
PRODUCTION_STATUS_UNCHANGED=true
PRODUCTION_TIMER_PRESERVED=true
LAB_CLEANUP=true

KF100_ROUTE_STATUS=CLOSED_PASS
KF100_REOPEN=false
```

Authority: `docs/development/N3W_KF100_SHORT_LIVED_CERTIFICATE_AUTO_RENEW_LAB_R2_EXECUTION_RESULT_20260930.md`.



## 2026-09-30 KF-100 short-lived renewal lab R1 stopped; R2 source prepared

The first live isolated renewal lab stopped in the success-path case with `tls_probe_failed`. Production continuity remained proven and KF-100 stays CLOSED_PASS.

```text
R1_RESULT=STOP
R1_REASON=tls_probe_failed
R1_PRODUCTION_PRESERVED=true
R1_PRODUCT_DEFECT_CONFIRMED=false
R1_REPLAY=false

R2_BRANCH=fix/n3w-kf100-short-lived-renewal-lab-r2-20260930
R2_EXECUTOR_BLOB=c9b156f0f0f51d9a22fb3902fff2ee7c7a0acb22

R2_FIX_1=REPORT_LIFECYCLE_RESULT_BEFORE_FINAL_TLS_ACCEPTANCE
R2_FIX_2=RECREATE_ISOLATED_BROKER_FOR_SINGLE_FILE_BIND_REBIND
R2_FIX_3=WAIT_FOR_TLS_FINGERPRINT_MATCH_NOT_ONLY_TCP_READY

PRODUCTION_CERTIFICATE_MUTATION=false
PRODUCTION_BROKER_RESTART=false
PRODUCTION_TIMER_MUTATION=false

NEXT_ONE_GATE=N3W_KF100_SHORT_LIVED_CERTIFICATE_AUTO_RENEW_LAB_R2_EXECUTION_20260930_01
```

Authority: `docs/development/N3W_KF100_SHORT_LIVED_CERTIFICATE_AUTO_RENEW_LAB_R2_SOURCE_REVIEW_20260930.md`.



## 2026-09-30 KF-100 short-lived automatic renewal lab prepared

KF-100 remains CLOSED_PASS. This is a post-closure production-fidelity lab to exercise the real renewal and rollback paths without touching production TLS material.

```text
KF100_ROUTE_STATUS=CLOSED_PASS
KF100_REOPEN=false

SHORT_LIVED_RENEWAL_LAB_BRANCH=lab/n3w-kf100-short-lived-certificate-auto-renew-20260930
SHORT_LIVED_RENEWAL_LAB_SOURCE_TEST_HEAD=49497128e451a5d1648cabba4427227a8bb087fb
SHORT_LIVED_RENEWAL_LAB_EXECUTOR_BLOB=16c1d1f3afedf18580a1096e92357f62380f2a53

LAB_CASE_A=SUCCESSFUL_AUTO_RENEW
LAB_CASE_B=FORCED_POSTRENEW_MISMATCH_AND_ROLLBACK

PRODUCTION_CERTIFICATE_MUTATION=false
PRODUCTION_BROKER_RESTART=false
PRODUCTION_TIMER_MUTATION=false
LIVE_LAB=false

SOURCE_REVIEW=PASS_PENDING_CI

NEXT_ONE_GATE=N3W_KF100_SHORT_LIVED_CERTIFICATE_AUTO_RENEW_LAB_EXECUTION_20260930_01
```

Authority: `docs/development/N3W_KF100_SHORT_LIVED_CERTIFICATE_AUTO_RENEW_LAB_SOURCE_REVIEW_20260930.md`.



## 2026-09-30 KF-100 Broker certificate lifecycle CLOSED_PASS

The first real scheduled lifecycle timer firing completed successfully and refreshed the durable status without renewal or Broker/TLS disruption.

```text
KF100_ROUTE_STATUS=CLOSED_PASS
KF100_KNOWN_FAILURE_STATUS=GUARDED

FIRST_SCHEDULED_TRIGGER=PASS
TIMER_ENABLED=enabled
TIMER_ACTIVE=active
TIMER_RESULT=success

LAST_TRIGGER_USEC=Wed 2026-09-30 00:51:14 CST
STATUS_CHECKED_AT=2026-09-29T16:51:15Z
NEXT_ELAPSE_US_REALTIME=Thu 2026-10-01 00:15:17 CST
LIFECYCLE_SERVICE_ACTIVE=inactive

SERVER_STATE=HEALTHY
CA_STATE=HEALTHY
SYSTEM_CA_STATE=HEALTHY
RENEWAL_ATTEMPTED=false
ROLLBACK_ATTEMPTED=false

BROKER_RUNNING=true
BROKER_STARTED_AT=2026-09-28T01:01:04.972986724Z
SERVER_CERT_SHA256=299a4cbece174692ecc9d82b92f1a98699847fece79543c8f8e565c04a07e917
SERVER_KEY_SHA256=e01403140603d0281661cc6103ff6df791ebadacce128e8a27bf093f6b27ac43
CA_CERT_SHA256=11ff133cdab8bf5f3093f6b488f8fa7e2579a1b5e383d066b1a1da56ad5dae9f
LIVE_TLS_VERIFIED=true

CERTIFICATE_MUTATION=false
BROKER_RESTART=false
```

The production path is now proven from source repair through installation, first audit, timer enablement, current-boot timer activation, and the first autonomous scheduled firing. FC4 CA age-based rollover is now CLOSED_NOT_PLANNED by product-lifecycle decision; the H0/H1 System CA remains a separate authority. The real server-certificate renewal path has already been proven in the isolated T1 short-lived-certificate lab.

Authority: `docs/development/N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_FIRST_SCHEDULED_TRIGGER_ACCEPTANCE_CLOSURE_20260930.md`.



## 2026-09-29 KF-100 timer runtime activation CLOSED_PASS

Timer enablement is CLOSED_PASS and the already-enabled timer has now entered the current-boot runtime schedule successfully.

```text
KF100_TIMER_RUNTIME_ACTIVATION_BRANCH=exec/n3w-kf100-broker-certificate-lifecycle-timer-runtime-activation-preparation-20260929
KF100_TIMER_RUNTIME_ACTIVATION_SOURCE_TEST_HEAD=1d2f6ee2bc6c4f027583cdb8fddc7066077f083c
KF100_TIMER_RUNTIME_ACTIVATION_EXECUTOR_BLOB=61e54cd3d27a615b56db913ef7b4ac0916c6a9ab

EXPECTED_MUTATION=systemctl_start_timer
PERSISTENT_TIMER=true
RANDOMIZED_DELAY=1h
PERSISTENT_CATCHUP_POSSIBLE=true

BROKER_RESTART=false
DIRECT_AUTO_RENEW_INVOCATION=false
CERTIFICATE_MUTATION=false

LIVE_TIMER_RUNTIME_ACTIVATION=true
TIMER_RUNTIME_ACTIVATION_RESULT=PASS
TIMER_ACTIVATION_RC=0

TIMER_ENABLED=enabled
TIMER_ACTIVE=active
LIFECYCLE_SERVICE_ACTIVE=inactive
NEXT_ELAPSE_REALTIME=Wed 2026-09-30 00:51:06 CST
LAST_TRIGGER_USEC=<empty>

PERSISTENT_CATCHUP_OBSERVED=false
STATUS_CHANGED_DURING_ACTIVATION=false
STATUS_HEALTH_VALID=true
RENEWAL_ATTEMPTED=false
ROLLBACK_ATTEMPTED=false

BROKER_CONTAINER_CONTINUITY=true
BROKER_STARTED_AT_CONTINUITY=true
SERVER_CERTIFICATE_UNCHANGED=true
SERVER_PRIVATE_KEY_UNCHANGED=true
CA_CERTIFICATE_UNCHANGED=true
LIVE_TLS_VERIFIED=true

BROKER_RESTART=false
CERTIFICATE_MUTATION=false

NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_FIRST_SCHEDULED_TRIGGER_ACCEPTANCE_PREPARATION_20260929_01
```

Authority: `docs/development/N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_TIMER_RUNTIME_ACTIVATION_EXECUTION_RESULT_20260929.md`.



## 2026-09-29 KF-100 timer enablement CLOSED_PASS

The first production audit is CLOSED_PASS and persistence-only timer enablement has now completed successfully.

```text
KF100_TIMER_ENABLEMENT_BRANCH=exec/n3w-kf100-broker-certificate-lifecycle-timer-enablement-preparation-20260929
KF100_TIMER_ENABLEMENT_SOURCE_TEST_HEAD=e39f5e908843477b4880f727b9acc6058c3578a8
KF100_TIMER_ENABLEMENT_EXECUTOR_BLOB=c39fe418642e12d5b0c8bc7994cd06a443086d33

EXPECTED_MUTATION=systemctl_enable_timer_only
ENABLE_NOW=false
TIMER_START=false
LIFECYCLE_SERVICE_START=false
AUTO_RENEW_INVOCATION=false
BROKER_RESTART=false
CERTIFICATE_MUTATION=false

FIRST_AUDIT_STATUS_REQUIRED=HEALTHY_HEALTHY_HEALTHY
FIRST_AUDIT_STATUS_HASH_MUST_REMAIN_UNCHANGED=true

LIVE_TIMER_ENABLEMENT=true
TIMER_ENABLEMENT_RESULT=PASS
TIMER_ENABLE_RC=0

TIMER_ENABLED=enabled
TIMER_ACTIVE=inactive
LIFECYCLE_SERVICE_ACTIVE=inactive

ENABLE_NOW_USED=false
TIMER_START=false
AUTO_RENEW_INVOCATION=false
STATUS_UNCHANGED=true

BROKER_CONTAINER_CONTINUITY=true
BROKER_STARTED_AT_CONTINUITY=true
SERVER_CERTIFICATE_UNCHANGED=true
SERVER_PRIVATE_KEY_UNCHANGED=true
CA_CERTIFICATE_UNCHANGED=true
LIVE_TLS_VERIFIED=true

BROKER_RESTART=false
CERTIFICATE_MUTATION=false

NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_TIMER_RUNTIME_ACTIVATION_PREPARATION_20260929_01
```

Authority: `docs/development/N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_TIMER_ENABLEMENT_EXECUTION_RESULT_20260929.md`.



## 2026-09-29 KF-100 first audit CLOSED_PASS

PR #510 prepared and merged the first-audit executor. The production first lifecycle audit has now completed successfully.

```text
KF100_FIRST_AUDIT_PR=510
KF100_FIRST_AUDIT_BRANCH=exec/n3w-kf100-broker-certificate-lifecycle-first-audit-preparation-20260929
KF100_FIRST_AUDIT_SOURCE_TEST_HEAD=f185018e333107e24a368339cfd06a62be8d6a3f
KF100_FIRST_AUDIT_EXECUTOR_BLOB=3c800633b557c0b1b22eb3ee5be129b69500c4df

FIRST_AUDIT_MODE=audit
PRIVATE_KEY_ARGUMENTS_USED=false
AUTO_RENEW_INVOCATION=false
LIFECYCLE_SERVICE_START=false
TIMER_ENABLEMENT=false
TIMER_START=false
BROKER_RESTART=false
CERTIFICATE_MUTATION=false

FIRST_AUDIT_STATUS_PRESTATE=ABSENT
FIRST_AUDIT_LOCK_PRESTATE=ABSENT
FIRST_AUDIT_STATUS_DIRECTORY_EXPECTED_EMPTY=true

EXPECTED_SERVER_STATE=HEALTHY
EXPECTED_CA_STATE=HEALTHY
EXPECTED_SYSTEM_CA_STATE=HEALTHY
EXPECTED_AUDIT_RESULT=ok

PR510_MERGED=true
PR510_MERGE_COMMIT=6c50ccb7b3f10da4a13fed28dbdfe6418b700ef4
PR510_POSTMERGE_N3W_CI_RUN=36530750854
PR510_POSTMERGE_N3W_CI=PASS
PR510_POSTMERGE_PUBLIC_SAFETY_RUN=36530750851
PR510_POSTMERGE_PUBLIC_SAFETY_CI=PASS

LIVE_FIRST_AUDIT=true
FIRST_AUDIT_RESULT=PASS
FIRST_AUDIT_RC=0
AUDIT_ACTION=audit
AUDIT_RESULT=ok

SERVER_STATE=HEALTHY
CA_STATE=HEALTHY
SYSTEM_CA_STATE=HEALTHY

STATUS_WRITTEN=true
LOCK_CREATED=true
STATUS_MODE=0600
LOCK_MODE=0600

PRIVATE_KEY_ARGUMENTS_USED=false
RENEWAL_ATTEMPTED=false
ROLLBACK_ATTEMPTED=false
AUTO_RENEW_INVOCATION=false
CERTIFICATE_MUTATION=false
BROKER_RESTART=false
TIMER_ENABLEMENT=false
TIMER_START=false

BROKER_CONTAINER_CONTINUITY=true
BROKER_STARTED_AT_CONTINUITY=true
SERVER_CERTIFICATE_UNCHANGED=true
SERVER_PRIVATE_KEY_UNCHANGED=true
CA_CERTIFICATE_UNCHANGED=true
LIVE_TLS_VERIFIED=true

NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_TIMER_ENABLEMENT_PREPARATION_20260929_01
```

The first-audit executor invokes the installed lifecycle CLI directly in `audit` mode, deliberately omits both private-key arguments, creates only the lifecycle lock/status authority, and requires Broker/TLS/certificate continuity after the audit.

Authority: `docs/development/N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_FIRST_AUDIT_EXECUTION_RESULT_20260929.md`.



## 2026-09-29 KF-100 production installation CLOSED_PASS

PR #508 prepared and merged the installation-only executor. The production T1 installation-only execution has now completed successfully.

```text
KF100_INSTALLATION_PR=508
KF100_INSTALLATION_BRANCH=exec/n3w-kf100-broker-certificate-lifecycle-production-installation-20260929
KF100_INSTALLATION_SOURCE_TEST_HEAD=c88034a7ec957610552841794f39cedcbc22dd38

INSTALLATION_ONLY=true
FRESH_PREMUTATION_PREFLIGHT_REQUIRED=true
EXACT_MERGED_SOURCE_BLOB_BINDING=true
PRIVATE_ENV_MATERIALIZATION_ON_T1=true
STATUS_DIRECTORY_CREATE_ONLY=true

SYSTEMD_DAEMON_RELOAD_ALLOWED=true
TIMER_ENABLEMENT=false
TIMER_START=false
LIFECYCLE_SERVICE_START=false
BROKER_RESTART=false
CERTIFICATE_MUTATION=false
AUTO_RENEW_START=false

PR508_MERGED=true
PR508_MERGE_COMMIT=d066ddbd00fa7efbfcf677f1630c6a73bc8cf4e8
PR508_POSTMERGE_N3W_CI_RUN=36528019139
PR508_POSTMERGE_N3W_CI=PASS
PR508_POSTMERGE_PUBLIC_SAFETY_RUN=36528019137
PR508_POSTMERGE_PUBLIC_SAFETY_CI=PASS

LIVE_INSTALLATION=true
INSTALLATION_RESULT=PASS
PREINSTALL_PREFLIGHT_RC=0
INSTALL_RC=0
INSTALL_PIPELINE_RC=0

LIFECYCLE_TOOL_INSTALLED=true
LIFECYCLE_SERVICE_INSTALLED=true
LIFECYCLE_TIMER_INSTALLED=true
LIFECYCLE_ENVIRONMENT_INSTALLED=true
STATUS_AUTHORITY_CREATED=true

LIFECYCLE_SERVICE_ACTIVE=inactive
LIFECYCLE_TIMER_ACTIVE=inactive
LIFECYCLE_TIMER_ENABLED=disabled

BROKER_CONTAINER_CONTINUITY=true
BROKER_STARTED_AT_CONTINUITY=true
SERVER_CERTIFICATE_UNCHANGED=true
SERVER_PRIVATE_KEY_UNCHANGED=true
CA_CERTIFICATE_UNCHANGED=true
LIVE_TLS_VERIFIED=true

CERTIFICATE_MUTATION=false
BROKER_RESTART=false
TIMER_ENABLEMENT=false
TIMER_START=false
AUTO_RENEW_START=false

NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_FIRST_AUDIT_PREPARATION_20260929_01
```

The executor re-runs the exact production deployment preflight immediately before the first write, installs only the lifecycle executable/unit/env/status authority, keeps the timer and service dormant, proves Broker/TLS continuity after installation, and rolls back newly created lifecycle files on failure.

Authority: `docs/development/N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_PRODUCTION_INSTALLATION_EXECUTION_RESULT_20260929.md`.



## 2026-09-29 KF-100 production deployment preparation source PASS; live read-only preflight pending

PR #507 prepares the production deployment route for the already-merged PR #506 lifecycle source. No T1 mutation has occurred in this gate.

```text
KF100_DEPLOYMENT_PREPARATION_PR=507
KF100_DEPLOYMENT_PREPARATION_BRANCH=exec/n3w-kf100-broker-certificate-lifecycle-production-deployment-preparation-20260929
KF100_DEPLOYMENT_PREFLIGHT_SOURCE_TEST_HEAD=4b3d77e83f16c91cd73eabf543c02e1a40158c44
KF100_DEPLOYMENT_PREFLIGHT_GIT_BLOB_SHA1=5740c6e30a867e8f32f8745e20b5135f23fb5a1e

KF100_DEPLOYMENT_PREFLIGHT_SOURCE_REVIEW=PASS
KF100_DEPLOYMENT_PREFLIGHT_TESTS=PASS
KF100_DEPLOYMENT_PREFLIGHT_SOURCE_CI=12_OF_12_PASS
N3W_BROKER_INGRESS_GUARD_CI_RUN=36521261740
PUBLIC_REPOSITORY_SAFETY_CI_RUN=36521261775

T1_MUTATION=false
CERTIFICATE_MUTATION=false
TIMER_ENABLEMENT=false
LIFECYCLE_INSTALLATION=false

KF100_DEPLOYMENT_READONLY_PREFLIGHT=PASS
BROKER_EFFECTIVE_UID_GID=1883:1883
SERVER_KEY_UID_GID=1883:1883
SERVER_KEY_MODE=0600
SERVER_KEY_OWNER_MATCHES_BROKER=true
SERVER_CERTIFICATE_KEY_MATCH=PASS
LIVE_TLS_VERIFIED=true
CA_PRIVATE_KEY_CONTINUITY_TOKEN_MATCH=true
LIFECYCLE_TIMER_ACTIVE=inactive
LIFECYCLE_TIMER_ENABLED=not-found
DEPLOYMENT_TARGET_PRESENT_COUNT=0

NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_PRODUCTION_INSTALLATION_20260929_01
```

The read-only preflight rebinds the active Broker CA/server certificate/server key from the running Compose Broker, proves server cert/key equality and the live TLS/8883 endpoint, re-proves the unique FC4 CA private-key authority, checks System CA identity, confirms ingress guard and Broker activation readiness, requires the lifecycle timer to remain not enabled, and stops if any lifecycle deployment target already exists.

Authority: `docs/development/N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_PRODUCTION_DEPLOYMENT_READONLY_PREFLIGHT_20260929.md`.



## 2026-09-29 KF-100 T1 Broker certificate lifecycle source repair PASS

Read-only production inventory established the current X.509 lifecycle authority, then PR #506 implemented and reviewed the source-only repair. Full baseline, design and source review are archived in:

- `docs/development/N3W_T1_BROKER_CERTIFICATE_LIFECYCLE_RUNTIME_BASELINE_20260929.md`
- `docs/development/N3W_T1_BROKER_CERTIFICATE_LIFECYCLE_REPAIR_DESIGN_20260929.md`
- `docs/development/N3W_T1_BROKER_CERTIFICATE_LIFECYCLE_REPAIR_DESIGN_REVIEW_20260929.md`
- `docs/development/N3W_T1_BROKER_CERTIFICATE_LIFECYCLE_SOURCE_REPAIR_REVIEW_20260929.md`

```text
KF100_REPAIR_PR=506
KF100_PR_STATE=OPEN_DRAFT
KF100_BRANCH=fix/n3w-t1-broker-certificate-lifecycle-20260929
KF100_SOURCE_TEST_HEAD=e3d51c7de58e66c772443202e7bd290a047302c3

CURRENT_TLS_RUNTIME=HEALTHY
BROKER_SERVER_CERT_NOT_AFTER=2028-11-22T04:18:40Z
FC4_PRIVATE_CA_NOT_AFTER=2036-08-17T04:18:39Z
SYSTEM_CA_NOT_AFTER=2036-07-30T15:32:24Z

ACTIVE_MANAGER_NODE_CA_EQUALS_BROKER_CA=true
FOURTH_INDEPENDENT_PRODUCTION_X509_CERTIFICATE_FOUND=false

BROKER_SERVER_CERTIFICATE_RENEWAL_SOURCE=IMPLEMENTED
CERTIFICATE_EXPIRY_STATUS_SOURCE=IMPLEMENTED
DAILY_CERTIFICATE_LIFECYCLE_TIMER_SOURCE=IMPLEMENTED
FC4_CA_AUTO_REPLACEMENT=false
SYSTEM_CA_AUTO_REPLACEMENT=false
NODE_REPAIRING_REQUIRED_FOR_SERVER_RENEWAL=false

N3W_BROKER_INGRESS_GUARD_CI_RUN=36516146163
N3W_BROKER_INGRESS_GUARD_CI=PASS
PUBLIC_REPOSITORY_SAFETY_CI_RUN=36516146186
PUBLIC_REPOSITORY_SAFETY_CI=PASS
SOURCE_REVIEW_HEAD_PR_WORKFLOWS=12_OF_12_PASS

CURRENT_FC4_CA_PRIVATE_KEY_RUNTIME_AUTHORITY=PROVEN
CURRENT_FC4_CA_CERT_KEY_MATCH=PASS
CURRENT_FC4_CA_PRIVATE_KEY_PERMISSION_AUTHORITY=PASS
CURRENT_FC4_CA_PRIVATE_KEY_UNIQUE_MATCH=PASS
KF100_CA_KEY_READONLY_PREFLIGHT=PASS
KF100_CA_KEY_PROBE_SCHEMA=gh.n3w-broker-ca-private-key-authority-probe/2
KF100_CA_KEY_PROBE_RC=0
LIVE_CERTIFICATE_MUTATION=false
LIVE_TIMER_ENABLEMENT=false
KF100_KNOWN_FAILURE_STATUS=OPEN
```

The source repair keeps the current FC4 CA and Broker server private key for ordinary V1 server-certificate renewal, validates certificate/key authority fail-closed, performs an atomic certificate replacement, then restarts only the existing Broker activation owner because the current TLS files are single-file bind mounts. The new endpoint must present the expected new certificate under normal CA/hostname/time verification; failure triggers restoration of the old certificate and a second Broker activation check. FC4 CA and H0/H1 System CA remain monitoring-only in KF-100. FC4 CA age-based rollover is now CLOSED_NOT_PLANNED by product-lifecycle decision; H0/H1 System CA remains separate.

The source/test review is complete. A fresh read-only T1 preflight subsequently proved one exact root-owned mode-0600 FC4 CA private-key match for the active Broker CA, with no second matching key in the bounded production authority roots. Production activation is still intentionally not claimed: no certificate mutation or timer enablement has occurred.

Authority: `docs/development/N3W_KF100_FC4_CA_PRIVATE_KEY_AUTHORITY_READONLY_EXECUTION_20260929.md`.

```text
NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_PRODUCTION_DEPLOYMENT_PREPARATION_20260929_01
```


## 2026-09-28 KF-099 exact repaired firmware physical validation CLOSED_PASS

This section supersedes the earlier KF-099 physical-validation-pending state. Full public-safe closure evidence is in `docs/development/N3W_KF099_PHYSICAL_VALIDATION_CLOSURE_20260928.md`.

```text
REPOSITORY_MAIN_BEFORE_CLOSURE=3c51f60ef7ddcd8ad4ea7c984e01bf5886ed159d

KF099_SOURCE_DEFECT_CONFIRMED=true
KF099_SOURCE_REPAIR=PASS
KF099_REPAIR_PR=500
KF099_REPAIR_MERGE_COMMIT=c578bcb2e31f50771b6b08c231704da6bf36b729
KF099_SOURCE_CI=14_OF_14_PASS

KF099_EXACT_ARTIFACT_BUILD=PASS
KF099_EXACT_ARTIFACT_BINDING=PASS
KF099_ARTIFACT_ID=10959875986
KF099_APPLICATION_SHA256=d0875ca692f7bd4349fd7d8bcdab69318e6c8b737b69a48f667b6e72cb89cb60
KF099_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
BOARD_B_WRITE=PASS
BOARD_B_ROM_IDENTITY_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee

KF099_PHYSICAL_VALIDATION=PASS
TARGET_HELLO_COUNT=18
TARGET_HELLO_DISTINCT_NONCE_COUNT=18
TARGET_HELLO_PAIRING_ID_UNIQUE_COUNT=1
PAIRING_ID_SHA256=142d1e0c9fc035645ce38e4681add39ba3ed5b3b0d60e14a4a1dfa398ab2472e
REPAIR_INTENT_REQUIRED_RESULT_COUNT=18
OTHER_TARGET_HELLO_RESULT_COUNT=0

TARGET_BEGIN_COUNT=0
GLOBAL_BEGIN_PATH_COUNT=0
RAW_BEGIN_STREAM_COUNT=0
CLIENT_CAPTURE_COMPLETE=true

MANAGER_RUNNING=true
MANAGER_CONTINUITY=true
MANAGER_EXACT_IMAGE=true
REGISTRATION_TARGET_UNCHANGED=true
CREDENTIAL_TARGET_UNCHANGED=true

PAIRING_REPAIR_AUTHORIZATION=false
T1_RUNTIME_MUTATION=false
OBSERVATION_BOARD_MUTATION=false

KF099_ROUTE_STATUS=CLOSED_PASS
KF099_KNOWN_FAILURE_STATUS=GUARDED

KF098_REOPEN=false
KF098_ROUTE_STATUS=CLOSED_PASS
```

The repaired Board remained on one pairing transaction across 18 rejected hello retries, used a fresh nonce on every hello, received `repair_intent_required` 18 times, and issued no `/v2/pairing/begin`. The 90-second capture had no client stream gaps or incomplete requests. Read-only before/after Manager database snapshots showed no target registration or credential change.

This closes only the rejected-hello control-flow defect. No repair authorization was granted and no authorized identity-repair transaction was exercised.

Authority: `docs/development/N3W_KF099_PHYSICAL_VALIDATION_CLOSURE_20260928.md`.


## 2026-09-28 KF-098 independent Astra review PASS

Astra independently reviewed the current KF-098 source, deployment executor, tests and archived live evidence at `main=5e695213866258457096f3b1a584997e1ffb3aa0`. The review did not access T1 or rerun the physical flow.

```text
KF098_SOURCE_REVIEW=PASS
KF098_DEPLOYMENT_REVIEW=PASS
KF098_LIVE_EVIDENCE_REVIEW=PASS
KF098_INDEPENDENT_REVIEW=PASS
KF098_BLOCKER_COUNT=0

KF098_ROUTE_STATUS=CLOSED_PASS
KF098_KNOWN_FAILURE_STATUS=GUARDED
KF098_REOPEN=false
```

The review also recorded three non-blocking follow-ups: formalize the route-change/readiness isolated checks as repository regressions, clean stale cutover-manifest wording, and improve private raw-capture/begin-rejection traceability. None changes the KF-098 closure disposition.

Authority: `docs/development/N3W_KF098_ASTRA_INDEPENDENT_REVIEW_ALIGNMENT_20260928.md`.


## 2026-09-28 KF-098 real Board discovery/HTTP acceptance CLOSED_PASS

This section supersedes the earlier 2026-09-28 KF-098 `real Board acceptance pending` state. Full public-safe closure evidence is in `docs/development/N3W_KF098_DYNAMIC_DISCOVERY_REAL_TRAFFIC_ACCEPTANCE_CLOSURE_20260928.md`.

```text
REPOSITORY_MAIN_BEFORE_CLOSURE_DOC=5344b93df5cf259dfd93a63e7a1e0af1e1586c4f

KF098_SOURCE_REPAIR=PASS
KF098_T1_LIVE_CUTOVER=PASS
KF098_MANAGER_RUNTIME=PASS
KF098_REAL_BOARD_DISCOVERY_ACCEPTANCE=PASS
KF098_REAL_BOARD_HTTP47112_ACCEPTANCE=PASS
KF098_EXPECTED_NEXT_PAIRING_DISPOSITION=PASS

DISCOVERY_QUERY_OBSERVED=true
DISCOVERY_RESPONSE_OBSERVED=true
CANDIDATE_HOST_EQUALS_ROUTE_SELECTED_T1_IPV4=true
CANDIDATE_HOST_DIFFERS_FROM_PREDECESSOR=true
BOARD_TO_CURRENT_T1_TCP47112_OBSERVED=true
TCP47112_HANDSHAKE_OBSERVED=true

PAIRING_HELLO_HTTP_STATUS=200
PAIRING_HELLO_SCHEMA=gh.pair.simple-hello-result/1
PAIRING_HELLO_STATUS=rejected
PAIRING_HELLO_REASON=repair_intent_required
PAIRING_HELLO_TRANSACTION_DISPOSITION=continue
PAIRING_BEGIN_HTTP_STATUS=403

PAIRING_REPAIR_AUTHORIZATION=false
REGISTRATION_DATABASE_MUTATION=false
BOARD_FLASH_MUTATION=false
BOARD_NVS_MUTATION=false

KF098_ROUTE_STATUS=CLOSED_PASS
KF098_KNOWN_FAILURE_STATUS=GUARDED
```

The prior zero-traffic observation was explained by Board B being powered off. After Board B was powered by USB, a fresh passive observation saw repeated UDP discovery requests and matching Manager responses, with the advertised candidate host equal to the route-selected current T1 IPv4. The Board then opened TCP/47112 to that same current T1 and completed the TCP connection.

The final pairing disposition also matched the existing-identity safety boundary. The Manager accepted the HTTP transport, returned a simplified hello result with `repair_intent_required`, and did not authorize identity replacement. The subsequent begin request was rejected with HTTP 403. This closes KF-098 because the discovery/HTTP target path is now correct; any identity-preserving repair is a separate later gate and is not required for KF-098 closure.


## 2026-09-28 KF-098 source repair + T1 exact live cutover PASS; real Board acceptance pending

This section supersedes older KF-098 statements that source repair or live cutover are still pending. Full public-safe alignment is in `docs/development/N3W_KF098_T1_LIVE_CUTOVER_PROGRESS_ALIGNMENT_20260928.md`.

```text
REPOSITORY_MAIN_AT_CUTOVER=88e9d140e5baddba543a961f003d12f7ce563ed2

KF098_SOURCE_REPAIR=PASS
KF098_T1_LIVE_CUTOVER=PASS
KF098_MANAGER_RUNTIME=PASS
PRE_CLOSURE_KF098_STATUS=OPEN

PR493_MERGED=true
PR494_MERGED=true
PR495_MERGED=true
PR496_MERGED=true
PR495_MAIN_AFTER_MERGE=0e043fd50204b2200b80ea6fe9171a15b0061c22
PR496_MERGE_COMMIT=88e9d140e5baddba543a961f003d12f7ce563ed2
PR496_POSTMERGE_PUBLIC_SAFETY_CI=PASS
PR496_POSTMERGE_PUBLIC_SAFETY_RUN_ID=36377968076

MANAGER_PRODUCT_SOURCE=575ce642e372961e21de14a36eba5877082de3cf
MANAGER_ARTIFACT_ID=10935052471
MANAGER_ARTIFACT_RUN_ID=36329597775
MANAGER_IMAGE_TAR_SHA256=6392b8c9bb87d95404346583d6f44967bd4e20fcc092be393c45f75a4ca7a5b2
CUTOVER_REMOTE_EXECUTOR_SHA256=c7ad3052dfbbda59513bb87f3ce8bceec0f11062c54eec839d7c58f9ef77ef86

FINAL_APPLY_RESULT=PASS
ROLLBACK_ATTEMPTED=false
MANAGER_EXACT_IMAGE=true
MANAGER_PAIRING_AUTO=true
MANAGER_MOUNTS_PRESERVED=true
MANAGER_HEALTH=PASS
BROKER_PRESERVED=true
R5_PRESERVED=true

PRE_CLOSURE_KF098_REAL_BOARD_DISCOVERY_ACCEPTANCE=PENDING
PRE_CLOSURE_KF098_REAL_BOARD_HTTP47112_ACCEPTANCE=PENDING
PRE_CLOSURE_BOARD_B_CURRENT_RUNTIME_LIVENESS=NOT_PROVEN

PRE_CLOSURE_NEXT_ONE_GATE=N3W_KF098_DYNAMIC_DISCOVERY_REAL_TRAFFIC_ACCEPTANCE_20260928_01
```

The first PR #495 live apply did cross the live-mutation boundary and then failed at the candidate TCP/47112 readiness check. Automatic rollback completed successfully and restored the old Manager contract, original manager.env authority, Broker continuity and R5 state. This was not a no-mutation failure.

Read-only post-rollback forensics and PR #496 then repaired the executor contract: verified post-rollback snapshot reacquire, Docker default normalization limited to proven-equivalent fields, acceptance of the rollback-created Manager lifecycle state, and health-before-listener postcheck ordering. The next exact apply passed without rollback.

The remaining KF-098 boundary is physical traffic acceptance, not another T1 cutover. A post-cutover packet-capture self-test proved T1 capture and local TCP/47112 health, while the observation window contained zero external UDP/47111 and zero external TCP/47112. The target registration remains historically approved, but its canonical cursor did not advance during a fresh 30 s read-only window and its last durable update predates this cutover. Therefore current Board B liveness is `NOT_PROVEN`; the absence of pairing traffic is not classified as a new T1, Board, Broker, or PR #474 failure.


## 2026-09-27 PR #480 T1 maintenance live closure

This section supersedes the earlier open-maintenance status for the Compose orphan warning and Mosquitto `per_listener_settings` deprecation. Full public-safe evidence is in `docs/development/N3W_PR480_T1_MAINTENANCE_LIVE_CLOSURE_20260927.md`.

```text
PR480_STATE=MERGED
PR480_SOURCE_HEAD=1749800677f8c5ecb846edb3bad2550382de78d5
PR480_SOURCE_CI=12_OF_12_PASS
PR480_MERGE_COMMIT=20153019301e323c71b861b46f3f818a8fe3f1c2
MAIN_AFTER_PR480=20153019301e323c71b861b46f3f818a8fe3f1c2
PR480_POSTMERGE_PUSH_CI=NOT_OBSERVED_BY_AVAILABLE_WORKFLOW_RUN_QUERY

COMPOSE_FC4_HOMEASSISTANT_ORPHAN_OWNERSHIP=CLOSED_PASS
MOSQUITTO_PER_LISTENER_SETTINGS_DEPRECATION=CLOSED_PASS
PR480_LIVE_REPAIR=CLOSED_PASS
FINAL_LIVE_ACCEPTANCE=PASS

COMPOSE_IGNORE_ORPHANS_EFFECTIVE=true
COMPOSE_ORPHAN_WARNING=ABSENT
PER_LISTENER_SETTINGS_WARNING=ABSENT

BROKER_RUNNING=true
TCP_8883_LISTEN_COUNT=1
MANAGER_LOOPBACK_TLS_MQTT_CONTINUITY=PASS
AUTHENTICATED_MQTT_RUNTIME_PATH=PASS
DYNAMIC_SECURITY_CONTINUITY=PASS
HOMEASSISTANT_CONTINUITY=PASS
R5_FIREWALL_CONTINUITY=PASS
AUTOMATIC_ROLLBACK_TRIGGERED=false

EXTERNAL_UNTRUSTED_ETH0_PHYSICAL_NEGATIVE=NOT_PROVEN
B2_STABLE_T1_HOSTNAME_TLS_IDENTITY=OPEN_OUT_OF_SCOPE
B3_ALREADY_PROVISIONED_NODE_LITERAL_BROKER_IP_MIGRATION=OPEN_OUT_OF_SCOPE

NEXT_ONE_GATE=N3W_PR474_POST_INFRA_CLOSURE_DISPOSITION_READONLY_REVIEW_20260927_01
```

The two maintenance warnings are now closed by fresh live evidence. The repair preserved the Dynamic Security state, one Broker/TCP-8883 listener, Manager authenticated loopback continuity, both Home Assistant runtimes, and the accepted R5 firewall anchors/policy. No `--remove-orphans`, firewall redesign, board access, B2 execution, or B3 execution occurred.

## 2026-09-27 PR #478 Broker ingress guard source/live closure

This section supersedes older PR #478 / KF-097 live-pending statements below wherever they conflict. Full public-safe evidence is in `docs/development/N3W_PR478_FINAL_SOURCE_LIVE_CLOSURE_PROGRESS_ALIGNMENT_20260927.md`.

```text
PR475_STATE=MERGED
PR475_HEAD=c070cc50c72cbbd261e8e8ba6e70d00aa4ef5fd6
PR475_MERGED=true
PR475_MERGE_COMMIT=5eb1279660abf934300b281d2b589c2ad7e14486
PR475_POSTMERGE_PUSH_CI=2_OF_2_PASS

PR478_STATE=MERGED
PR478_SOURCE_HEAD=c80202632f9799149df9d1f6641a39441647e7c5
PR478_BASE_AT_MERGE=main
PR478_BASE_SHA_AT_MERGE=5eb1279660abf934300b281d2b589c2ad7e14486
PR478_FINAL_REVIEW_HEAD=7cd007c99677a772cf2874b4a776fcc34f2d24d6
PR478_MERGED=true
PR478_MERGE_COMMIT=525513e4501a242fa8f8b2ed1a83e92ac6345105
PR478_POSTMERGE_PUSH_CI=3_OF_3_PASS
MAIN_AFTER_PR478=525513e4501a242fa8f8b2ed1a83e92ac6345105

R5_R2_SOURCE_REVIEW=PASS
R5_SOURCE_BLOCKER_COUNT=0
R5_LIVE_FIREWALL_ACCEPTANCE=PASS
R5_RELOAD_IDEMPOTENCE=PASS
R5_REAL_NM_REAPPLY_ACCEPTANCE=PASS
R5_REAL_LINK_DOWN_UP_ACCEPTANCE=PASS
R5_FAIL_CLOSED_ON_LINK_LOSS=PASS
R5_TRUSTED_POLICY_RESTORE_ON_LINK_RECOVERY=PASS
R5_SYSTEMD_PERSISTENCE_INSTALL_CONTRACT=PASS
R5_REBOOT_PERSISTENCE_ACCEPTANCE=PASS
PR478_FINAL_SOURCE_LIVE_CLOSURE=PASS
FINAL_SOURCE_LIVE_BLOCKER_COUNT=0

KF097_STATUS=GUARDED

EXTERNAL_UNTRUSTED_ETH0_PHYSICAL_NEGATIVE=NOT_PROVEN
B2_STABLE_T1_HOSTNAME_TLS_IDENTITY=OPEN_OUT_OF_SCOPE
B3_ALREADY_PROVISIONED_NODE_LITERAL_BROKER_IP_MIGRATION=OPEN_OUT_OF_SCOPE

COMPOSE_FC4_HOMEASSISTANT_ORPHAN_WARNING=OPEN_MAINTENANCE
MOSQUITTO_PER_LISTENER_SETTINGS_DEPRECATION=OPEN_MAINTENANCE
```

Reboot preparation exposed one real deployment-contract defect: the guard and activation units were active but not enabled. The live T1 was repaired with `systemctl enable` only, and the repository now contains a persistence installer plus regression coverage that requires both services to be enabled without using `enable --now` or restarting live services.

A real host reboot then proved a changed boot identity, correct Docker -> guard -> activation ordering, NetworkManager dispatcher execution, R5 policy restoration, Broker/Manager recovery, and one TCP/8883 listener. The Manager restart counter changed across the host reboot and is not treated as a cross-reboot continuity oracle.

The Compose orphan warning for the existing Home Assistant container and the Mosquitto `per_listener_settings` deprecation are maintenance items, not R5 acceptance blockers. Do not use `--remove-orphans` blindly.

PR #475 and PR #478 were subsequently merged in dependency order with exact-head guards and merge commits. PR #475 post-merge push CI passed 2/2, PR #478 post-merge push CI passed 3/3, and current main is `525513e4501a242fa8f8b2ed1a83e92ac6345105`. This repository merge closure does not change the already accepted R5 live evidence or close the explicit remaining scopes above.

```text
TEAM_SHARED_WORKSPACE=GITHUB
IMPORTANT_CHAT_ONLY_ARTIFACT_COUNT=0
TEAM_SHARE_COMPLETENESS=PASS
```

## 2026-09-21 production successor de-harness and exact-artifact closure

This section supersedes older current-successor / next-route fields below wherever they conflict. PR #437 remains the latest merged and physically validated product source; the production successor described here is still unmerged and has not been flashed to Board B.

```text
REPOSITORY_MAIN_AT_ALIGNMENT_START=8165cc441abd45f4d46f7439fa57edee1470c917

MERGED_PRODUCT_SOURCE_AUTHORITY=PR437
PR437_SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
PR437_SOURCE_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f

PRODUCTION_SUCCESSOR_MERGED=false
PRODUCTION_SUCCESSOR_SOURCE_BRANCH=feature/n3w-production-telemetry-bridge-20260921
PRODUCTION_SUCCESSOR_SOURCE_HEAD=c1b3d9d016d06c21c9ff7070c0043163739565ca
PRODUCTION_SUCCESSOR_SOURCE_TREE=0c857fb0f830239717a2e937d176903a6acae8ac

PRODUCT_CORE_DEHARNESS=PASS
FROZEN_PR437_COMPONENT_MODIFIED=false
F1RC2_PRODUCTION_TARGET=PASS
REAL_SENSOR_TELEMETRY_BRIDGE=PASS
FULL_PRODUCTION_FIRMWARE_COMPILE=PASS
BINARY_DEHARNESS_PROOF=PASS

PR463_DUAL_CORE_COMPILE=12_OF_12_SUCCESS
PR464_F1RC2_TARGET_CONFIG=12_OF_12_SUCCESS
PR465_TELEMETRY_BRIDGE_CONFIG=12_OF_12_SUCCESS
PR466_FULL_FIRMWARE_COMPILE=12_OF_12_SUCCESS
PR467_BINARY_DEHARNESS=12_OF_12_SUCCESS

EXACT_ARTIFACT_BUILD_BRANCH_HEAD=433b91c19bf436a832021d821bda53261b7e3532
EXACT_ARTIFACT_RUN_ID=35612622035
EXACT_ARTIFACT_BUILD=PASS
EXACT_ARTIFACT_BINDING=PASS

PRODUCTION_ARTIFACT_ID=10644667734
PRODUCTION_ARTIFACT_NAME=n3w-production-f1rc2-c1b3d9d-exact-source
GITHUB_ARTIFACT_SHA256=02fbe69f78511f33dec150dee635925dd4decf81048de3adfc6db8af4acc7a72

PRODUCTION_RELEASE_BUNDLE=n3w-production-f1rc2-c1b3d9d-exact-source.zip
PRODUCTION_RELEASE_BUNDLE_SHA256=93d830368b74e0dae904a9f5c4450378694575c68b917e749b480455662ff065
PRODUCTION_FIRMWARE_BIN_SHA256=8bcd89aaf0be64188f8f98a64795fe78d573ae82dd2dd360c7ff459f80e58efa
PRODUCTION_FACTORY_BIN_SHA256=434a3996ea8dc74c4a356f54d8a9405202f17b500680a66f5d49a2089cf67774

PHASE4_HARNESS_PRESENT=false
LAB_DIAGNOSTICS_PRESENT=false
RTC_BREADCRUMB_PRESENT=false

PRODUCTION_SUCCESSOR_BOARD_B_DEPLOYMENT=NOT_EXECUTED
PRODUCTION_SUCCESSOR_PHYSICAL_ACCEPTANCE=NOT_EXECUTED
CURRENTLY_DEPLOYED_BOARD_B_SOURCE=4270f24a92a87dd5239d781ebba624c2f34b7fc2
CURRENTLY_DEPLOYED_BOARD_B_ARTIFACT_ID=10619047221

NEXT_CANDIDATE_GATE=N3W_PRODUCTION_BOARD_B_WRITE_TARGET_PREFLIGHT_20260921_01
NEXT_GATE_AUTHORIZED=false
```

The production candidate must be referred to by artifact ID and frozen release-bundle SHA, not by a same-source rebuild. Three same-source CI builds produced different application SHA-256 values, so KF-084 remains an active reproducibility guard.

The flat release bundle also contains an ESPHome-generated `flash_args` whose paths still refer to the original build-tree layout. A later physical write gate must not execute it blindly; it must use a separately reviewed `firmware.factory.bin` procedure or independently normalize and verify the multi-image mapping before any flash write.

Current production alignment authority: `docs/development/N3W_PRODUCTION_DEHARNESS_AND_EXACT_ARTIFACT_PROGRESS_ALIGNMENT_20260921.md`.

## 2026-09-21 PR #437 post-merge closure

This section supersedes all older PR #437 candidate/merge-state fields below wherever they conflict.

```text
PR437_STATE=MERGED
PR437_DRAFT=false
PR437_MERGED=true
PR437_SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
PR437_SOURCE_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f
PR437_MERGE_COMMIT=b9acaaad50b17c9cdb51c219330e612c383628f0
MAIN_AFTER_PR437=b9acaaad50b17c9cdb51c219330e612c383628f0

PR437_CURRENT_HEAD_CI=11_OF_11_PASS
PR437_EXACT_ARTIFACT_BINDING=PASS
PR437_BOARD_B_DEPLOYMENT=PASS
PR437_TWO_RUN_PHYSICAL_REVALIDATION=PASS
KF096_STATUS=CLOSED_PASS
KNOWN_FAILURE_KF096=GUARDED

DIRECT_TO_RELAY_FUNCTIONAL_SWITCH=REPEATABLE_PASS
DIRECT_TO_RELAY_ZERO_LOSS=NOT_GUARANTEED
DIRECT_TO_RELAY_BOUNDARY_LOSS=REPEATABLE
RELAY_CONTINUITY_600S=REPEATABLE_PASS
RELAY_TO_DIRECT_FAILBACK=REPEATABLE_PASS
SAME_BOOT_FULL_ROUND_TRIP=REPEATABLE_PASS

POSTMERGE_SOURCE_INTEGRITY=PASS
POSTMERGE_PUSH_CI=NOT_OBSERVED_BY_PR_ONLY_WORKFLOW_WRAPPER
```

The merge used an exact-head guard against `4270f24...`. Fresh comparison from the frozen physical source head to the merge commit shows only the already-existing main-side repository/documentation/execution-package changes; none of the PR #437 product-source or PR-owned test files changed relative to the physically validated source head. Therefore the merged product source remains exactly attributable to the tested `4270f24...` revision.

The available workflow-run wrapper is PR-event-only and returns no merge-SHA push runs; this is an observability limitation, not evidence that post-merge CI did not run.

## 2026-09-21 two-run final alignment and merge authorization

This section supersedes all older PR #437 / KF-096 current-state fields below wherever they conflict.

```text
REPOSITORY_MAIN_AT_FINAL_REVIEW=3fa4cbe05b74847e6998bd43f4ffe062eb5ae4ee
CURRENT_CANDIDATE_PR=437
CURRENT_CANDIDATE_STATE=OPEN_DRAFT
CURRENT_CANDIDATE_MERGED=false
CURRENT_CANDIDATE_SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
CURRENT_CANDIDATE_SOURCE_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f
CURRENT_CANDIDATE_SOURCE_REVIEW=PASS
CURRENT_CANDIDATE_CI=11_OF_11_PASS
CURRENT_CANDIDATE_EXACT_ARTIFACT_BINDING=PASS
CURRENT_CANDIDATE_BOARD_B_WRITE=PASS

PHYSICAL_RUN_1_FULL_ROUND_TRIP=PASS
PHYSICAL_RUN_1_D2R_MISSING=1
PHYSICAL_RUN_1_D2R_MISSING_RANGE=73
PHYSICAL_RUN_1_RELAY_600S=PASS
PHYSICAL_RUN_1_RELAY_MISSING=0
PHYSICAL_RUN_1_R2D_MISSING=0

PHYSICAL_RUN_2_FULL_ROUND_TRIP=PASS
PHYSICAL_RUN_2_D2R_MISSING=3
PHYSICAL_RUN_2_D2R_MISSING_RANGE=815-817
PHYSICAL_RUN_2_RELAY_600S=PASS
PHYSICAL_RUN_2_RELAY_MISSING=0
PHYSICAL_RUN_2_R2D_MISSING=0

DIRECT_TO_RELAY_FUNCTIONAL_SWITCH=REPEATABLE_PASS
DIRECT_TO_RELAY_ZERO_LOSS=NOT_GUARANTEED
DIRECT_TO_RELAY_BOUNDARY_LOSS=REPEATABLE
RELAY_CONTINUITY_600S=REPEATABLE_PASS
RELAY_TO_DIRECT_FAILBACK=REPEATABLE_PASS
SAME_BOOT_FULL_ROUND_TRIP=REPEATABLE_PASS
MANAGER_RUNTIME_STABILITY=REPEATABLE_PASS

KF096_STATUS=CLOSED_PASS
PR437_MERGE_CONDITION_REVIEW=PASS
PR437_MERGE_READY=true
PR437_MERGE_AUTHORIZED=true
NEXT_ACTION=MERGE_PR437_WITH_EXACT_HEAD_GUARD
```

Two independent current-head physical routes now show the same product boundary: Direct -> Relay switching is functionally reliable but not zero-loss under the accepted Option-B latest-state contract, while Relay steady-state continuity and Relay -> Direct failback were lossless in both measured routes. The repeated Direct-boundary loss is retained as an explicit product characteristic, not hidden as an anomaly and not reclassified as an Option-B contract failure.

Final authority: `docs/development/N3W_PR437_4270F24_TWO_RUN_FINAL_ALIGNMENT_AND_MERGE_REVIEW_20260921.md`.

## 2026-09-21 current-head physical closure and pre-merge review

This section supersedes all older PR #437 / KF-096 current-state fields below wherever they conflict.

```text
REPOSITORY_MAIN_AT_REVIEW=327b833de9e933efa0cbe8e6963cd63b9c69587d

CURRENT_CANDIDATE_PR=437
CURRENT_CANDIDATE_STATE=OPEN_DRAFT
CURRENT_CANDIDATE_MERGED=false
CURRENT_CANDIDATE_SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
CURRENT_CANDIDATE_SOURCE_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f
CURRENT_CANDIDATE_SOURCE_REVIEW=PASS
CURRENT_CANDIDATE_CI=11_OF_11_PASS

CURRENT_CANDIDATE_EXACT_ARTIFACT_BUILD=PASS
CURRENT_CANDIDATE_EXACT_ARTIFACT_BINDING=PASS
CURRENT_CANDIDATE_BOARD_B_WRITE=PASS
CURRENT_CANDIDATE_PHYSICAL_ROUTE=PASS

DIRECT_LONG_BASELINE=PASS
DIRECT_LONG_BASELINE_SECONDS=5601
DIRECT_LONG_BASELINE_SEQUENCE_COUNT=1120
DIRECT_LONG_BASELINE_MISSING_SEQUENCE_COUNT=0

DIRECT_TO_RELAY_FUNCTIONAL=PASS
DIRECT_TO_RELAY_MANAGER_VISIBLE_GAP_MS=21414
DIRECT_TO_RELAY_MOVE_START_TO_FIRST_RELAY_MS=50721
DIRECT_TO_RELAY_MISSING_SEQUENCE_COUNT=1
DIRECT_TO_RELAY_MISSING_SEQUENCE_RANGE=73

RELAY_CONTINUITY_600S=PASS
RELAY_CONTINUITY_SEQUENCE_RANGE=100-221
RELAY_CONTINUITY_EXPECTED_ROW_COUNT=122
RELAY_CONTINUITY_ACCEPTED_ROW_COUNT=122
RELAY_CONTINUITY_MISSING_SEQUENCE_COUNT=0
RELAY_MAX_MANAGER_INTERARRIVAL_MS=32584
ORDERED_BACKLOG_CATCHUP=PASS

RELAY_TO_DIRECT_FAILBACK=PASS
RELAY_TO_DIRECT_MANAGER_VISIBLE_GAP_MS=21519
RELAY_TO_DIRECT_MOVE_START_TO_FIRST_DIRECT_MS=76031
RELAY_TO_DIRECT_MISSING_SEQUENCE_COUNT=0
SAME_BOOT_ROUND_TRIP=PASS

MANAGER_RUNTIME_STABILITY=PASS
TRANSITION_HOLD_BUFFER_PHYSICAL_EFFECTIVENESS=PASS

KF096_STATUS=CLOSED_PASS
PR437_MERGE_READY=true
PR437_MERGE_AUTHORIZED=false
NEXT_ONE_GATE=N3W_PR437_EXPLICIT_MERGE_DECISION_20260921_01
```

Seq 73 remains a recorded Direct-loss-boundary diagnostic. Under the accepted Option-B latest-state contract, it does not fail the route: samples without a real transport opportunity are held, while a sample that has received a real Direct/Relay transport attempt is not application-resubmitted after failure. End-to-end every-sample delivery remains outside PR #437.

The exact current-artifact physical closure and final source/main-integration review are recorded in `docs/development/N3W_PR437_4270F24_FINAL_PHYSICAL_CLOSURE_AND_PREMERGE_REVIEW_20260921.md`. PR #437 remains draft/open/unmerged pending a separate explicit merge decision.


## 2026-09-21 exact artifact independent binding closure

This section supersedes earlier current-artifact binding fields below wherever they conflict.

```text
REPOSITORY_MAIN_AT_BINDING=d0ec0520d251035cf03e710418d92e5dfc7e1690
REPOSITORY_MAIN_TREE_AT_BINDING=3c5e587d7a7ddae8d1e64dbb9be9851b889094ae

CURRENT_CANDIDATE_PR=437
CURRENT_CANDIDATE_STATE=OPEN_DRAFT
CURRENT_CANDIDATE_SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
CURRENT_CANDIDATE_SOURCE_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f
CURRENT_CANDIDATE_CI=11_OF_11_PASS

CURRENT_CANDIDATE_EXACT_ARTIFACT_BUILD=PASS
CURRENT_CANDIDATE_EXACT_ARTIFACT_BINDING=PASS
ARTIFACT_RUN_ID=35553142523
ARTIFACT_ID=10619047221
ARTIFACT_NAME=n3w-pr437-4270f24-boardb-exact-source
INDEPENDENT_ARCHIVE_SHA256=33895089cf861a211f3f5569cd8f3e6729b0938787cda0d4a30d498ce0264895
GITHUB_ARTIFACT_DIGEST_SHA256=33895089cf861a211f3f5569cd8f3e6729b0938787cda0d4a30d498ce0264895
MANIFEST_SHA256=485ca57b6dd718afd004c71952ade4e21b9dfa1f65a30a488414d9c1d3e598a3
APPLICATION_SIZE=1145984
APPLICATION_SHA256=b7836f041e8b0f68809980d516a9d9cd5c4a94f862f7d3a27515ae85d55d6843
OTADATA_SIZE=8192
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

ARTIFACT_MEMBER_SET_MATCH=PASS
MANIFEST_MATCH=PASS
PRODUCT_SOURCE_CHANGED=false
BOARD_ACCESS_DURING_BINDING=false
LIVE_RUNTIME_MUTATION_DURING_BINDING=false

PR437_MERGE_READY=false
KF096_STATUS=OPEN
NEXT_ROUTE=N3W_PR437_4270F24_BOARD_B_WRITE_TARGET_PREFLIGHT_20260921_01
AUTO_EXECUTE_NEXT_GATE=false
NEW_PHYSICAL_AUTHORIZATION_REQUIRED=true
```

The independently downloaded ZIP contains exactly `MANIFEST.txt`, `firmware.bin`, and `ota_data_initial.bin`. Its SHA-256 matches GitHub artifact metadata exactly; the manifest source/tree/target/toolchain/trigger fields and both inner file size/hash values all match. The artifact is now bound for a later Board B target-preflight, but no Board access or physical validation was performed.

Binding authority: `docs/development/N3W_PR437_4270F24_EXACT_ARTIFACT_BUILD_AND_BINDING_EXECUTION_20260921.md`.


## 2026-09-21 post-convergence exact artifact build update

This section supersedes the repository-main and current-artifact fields in the older 2026-09-21 source-repair header below.

```text
REPOSITORY_MAIN=0f712709bff98b9288cb1b8425605a875f45d241
REPOSITORY_MAIN_TREE=592a359e0c7655c2a80318dc8bd283a4811a2760
REPOSITORY_CONVERGENCE=CLOSED_PASS
OPEN_PR_COUNT=2
WORKFLOW_FILE_COUNT=37

CURRENT_CANDIDATE_PR=437
CURRENT_CANDIDATE_STATE=OPEN_DRAFT
CURRENT_CANDIDATE_SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
CURRENT_CANDIDATE_SOURCE_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f
CURRENT_CANDIDATE_CI=11_OF_11_PASS
CURRENT_CANDIDATE_SOURCE_REVIEW=PASS

CURRENT_CANDIDATE_EXACT_ARTIFACT_BUILD=PASS
CURRENT_CANDIDATE_EXACT_ARTIFACT_BINDING=PARTIAL_PENDING_INDEPENDENT_VERIFY
ARTIFACT_RUN_ID=35553142523
ARTIFACT_ID=10619047221
ARTIFACT_NAME=n3w-pr437-4270f24-boardb-exact-source
GITHUB_ARTIFACT_DIGEST_SHA256=33895089cf861a211f3f5569cd8f3e6729b0938787cda0d4a30d498ce0264895
APPLICATION_SIZE=1145984
APPLICATION_SHA256=b7836f041e8b0f68809980d516a9d9cd5c4a94f862f7d3a27515ae85d55d6843
OTADATA_SIZE=8192
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

PR437_MERGE_READY=false
KF096_STATUS=OPEN

NEXT_ROUTE=N3W_PR437_4270F24_EXACT_ARTIFACT_BUILD_AND_BINDING_EXECUTION_20260921_01
RESUME_POINT=INDEPENDENT_ARTIFACT_DOWNLOAD_AND_BINDING
BOARD_B_REFLASH=false
```

Run `35553142523` checked out exact PR #437 source, matched source tree and target blob, compiled with ESPHome 2026.4.3 / ESP-IDF 5.5.4, froze the application/OTA-data files, and uploaded artifact `10619047221`. Independent archive/member/hash verification is still required before this artifact becomes the bound candidate for any Board preflight.

Board B remains on the earlier deployed artifact/source recorded below. Artifact-build success is not physical validation.

## 2026-09-21 PR #437 superseding alignment

This section supersedes older PR #437 / KF-096 values later in this file wherever they conflict. Historical sections remain for chronology only.

```text
REPOSITORY_MAIN=a5a4dc06e86374287348bb8718e7f7fb7d6c42d2
REPOSITORY_MAIN_TREE=291cd078000d82e811a65d44ae782aa0b044bda9

CURRENT_CANDIDATE_PR=437
CURRENT_CANDIDATE_STATE=OPEN_DRAFT
CURRENT_CANDIDATE_SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
CURRENT_CANDIDATE_SOURCE_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f
CURRENT_CANDIDATE_CI=11_OF_11_PASS
CURRENT_CANDIDATE_SOURCE_REVIEW=PASS

CURRENT_CANDIDATE_EXACT_ARTIFACT=NOT_BUILT
EXACT_ARTIFACT_READY=true
PR437_MERGE_READY=false
KF096_STATUS=OPEN
```

The current exact source repaired the newly isolated Wi-Fi recovery-window defect:

```text
NO_RELAY_WIFI_RECOVERY_BUDGET_MS=85000
NO_RELAY_ABSOLUTE_RECOVERY_BUDGET_MS=120000
HEALTHY_RELAY_ABSOLUTE_RECOVERY_BUDGET_MS=30000
MQTT_RECOVERY_BUDGET_MS=25000
DIRECT_CONFIRM_BUDGET_MS=5000
```

Source review found and closed two blockers before this exact head:

- `SR-B1`: a 50 s Wi-Fi phase did not cover ESPHome 2026.4.3's sequential 31 s scan fallback plus 46 s connection fallback;
- `SR-B2`: an earlier 90 s healthy-Relay absolute window unnecessarily widened single-radio ownership away from an already-working Relay path.

The exact-head host regression now models Wi-Fi becoming ready only after the sequential 77 s fallback path, while healthy Relay retains the pre-existing 30 s hard ownership ceiling.

Current deployed Board B is still bound to the earlier exact artifact/source, not to `4270f24...`:

```text
DEPLOYED_SOURCE_HEAD=177468e290a207f2fb7f6c554aedf60b61373b4d
DEPLOYED_SOURCE_TREE=a50ff98887b14b70cf9d278c6f8b7edf536eae88
DEPLOYED_ARTIFACT_ID=10607030747
DEPLOYED_APPLICATION_SHA256=74f6b111d3af3b1247e6f367d3da10957846dbe6103e74fc507bc26e43065093
DEPLOYED_APPLICATION_READBACK=PASS
```

Post-write runtime evidence on that deployed artifact remains a FAIL baseline:

```text
POSTWRITE_DIRECT_BASELINE=FAIL
LAST_MANAGER_CANONICAL_SEQ=49
LAST_MANAGER_CANONICAL_SOURCE=direct
EXACT_BOARD_B_MQTT_DISCONNECT=PROVEN
LATE_BROKER_RECONNECT_OBSERVED=false

DIRECT_RECOVERY_WINDOW_SECONDS=150
DIRECT_RECOVERY_PING_SAMPLE_COUNT=25
DIRECT_RECOVERY_PING_SUCCESS_COUNT=0
DIRECT_RECOVERY_NEIGHBOR_STATE=INCOMPLETE_FOR_ALL_25_SAMPLES

BOARD_B_USB_ENUMERATION_LAST_OBSERVED=PASS
LOCAL_SERIAL_OWNER_LAST_OBSERVED=0
MANAGER_CONTINUITY_DURING_FORENSIC=PASS
BROKER_CONTINUITY_DURING_FORENSIC=PASS
```

The physical symptom is consistent with the confirmed source integration defect, but unique causation is not yet proven because `4270f24...` has not been built, flashed, or physically revalidated.

```text
NEXT_ROUTE=N3W_PR437_4270F24_EXACT_ARTIFACT_BUILD_AND_BINDING
BOARD_B_REFLASH=false
PR437_MERGE=false
```

## Historical repository / product source snapshot (superseded by 2026-09-21 header)

```text
REPOSITORY=chrenguo-stack/HomeAssistant
PRIMARY_TASK=N3W_MULTI_NODE_RELAY_AND_RUNTIME_FAILOVER_ACCEPTANCE

ALIGNMENT_BASE_MAIN=d9afc55b04042806ed8b6e1b1ae3553742aba2be
PRODUCT_SOURCE_AUTHORITY=d1b5c3acbd32cca95483743ffe2edba9aa3f904f
REPOSITORY_MAIN_AT_ALIGNMENT_START=d9afc55b04042806ed8b6e1b1ae3553742aba2be
REPOSITORY_MAIN_AFTER_PR439=02efd64312c4b01c19c0a18e6db543145a16ad9c
REPOSITORY_MAIN_AT_POSTWRITE_ALIGNMENT_START=0ea13c9f9f76fdf7fb79ec82393408ab144b4e18

PR431_REVIEW_HEAD=137303c7b08fff36920d05e77c2f1bcc20b38d1f
PR431_MERGE=d1b5c3acbd32cca95483743ffe2edba9aa3f904f

CURRENT_CANDIDATE_PR=437
CURRENT_CANDIDATE_SOURCE_HEAD=cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
CURRENT_CANDIDATE_SOURCE_TREE=b459fae0a054d45b0d09e60bffae9769e060a5c0
CURRENT_CANDIDATE_ARTIFACT_ID=10575077512

FROZEN_DEPLOYED_PRODUCT_SOURCE_HEAD=cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
FROZEN_DEPLOYED_PRODUCT_SOURCE_TREE=b459fae0a054d45b0d09e60bffae9769e060a5c0
```

PR #431 remains the latest merged product-source authority at `d1b5c3acbd32cca95483743ffe2edba9aa3f904f`. PR #437 remains the current unmerged draft successor candidate at exact HEAD `cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c`; its final source review, CI, and exact-artifact binding passed. Board B now runs the exact PR #437 artifact after an operator-confirmed target override of the automated identity mismatch. Repository main, merged product source, PR #437 candidate source, and deployed physical source remain separate authorities.

## Recent integrated route

```text
PR420=MERGED   # documentation alignment after PR416 deployment
PR421=MERGED   # retained RTC watchdog breadcrumb
PR422=MERGED   # Relay unicast channel observability
PR423=MERGED   # async MQTT / disable MQTT log forwarding in physical harness
PR424=MERGED   # explicit single-radio ownership / bounded Direct probes
PR425=MERGED   # transactional Direct failback + Relay channel fixation
PR426=MERGED   # documentation alignment through PR425 artifact preparation
PR427=MERGED   # documentation alignment after PR425 physical validation
PR428=MERGED   # KF-096 Direct recovery continuity source repair
PR431=MERGED   # finite successor: recovery-exit / teardown lifecycle closure
PR436=CLOSED_SUPERSEDED   # historical PR431-bound Board B executor, not valid for PR437
PR437=OPEN_DRAFT   # current Direct recovery liveness / deadline successor candidate
PR439=MERGED   # PR437-bound Board B preflight/write executor
```

Exact product repair merges:

```text
PR421_MERGE=fb762e2ccb54393e7610339d05d164b7ea975bba
PR422_MERGE=a01725644d9b0b4ee0a461c1579211829f1aa69e
PR423_MERGE=35944fa928bb1fcf5527e476fb5dbfcfcdc11ead
PR424_MERGE=664fcbe88bae76bc9fc6e5e240067e3cbae7c649
PR425_MERGE=096528fbf61948d6c69197f1c8994ce8e7d672f4
PR427_MERGE=58b6679c5cb8da5c935d581b66ba129b02db4b8a
PR428_SOURCE_HEAD=6cae8ea1a75096aab0e625ae56828d13931f7c57
PR428_MERGE=f357db25390ffd097e9b8608293870772f9cb16c
```

## Frozen accepted baselines

```text
FC4_FINAL_PHYSICAL_ACCEPTANCE=FROZEN_PASS
N3W_THREE_BOARD_R2_RUNTIME_LIVENESS=FROZEN_PASS
KF089_RELAY_END_TO_END_CLOSEOUT=PASS
KF092_STATUS=CLOSED_PASS
```

KF-092 remains closed and is not reopened by later radio-ownership or failback work.

## Physical defect / repair sequence

### Task watchdog

PR #423 repaired the synchronous MQTT/log-forwarding watchdog hazard. Fresh physical retest proved:

```text
TASK_WDT_REPRODUCED=false
UNCOMMANDED_REBOOT=false
PR423_TASK_WDT_REPAIR_PHYSICAL_VALIDATION=PASS
MANAGER_RESTART_COUNT=0
```

### Historical single-radio channel conflict

After the watchdog repair, a same-boot run still had approximately 110.061 s Manager-visible blackout and captured:

```text
CURRENT_CHANNEL=5
PEER_CHANNEL=11
RAW_ERROR=12397
RAW_ERROR_12397=ESP_ERR_ESPNOW_CHAN
```

PR #424 introduced explicit `DIRECT_WIFI / RELAY_ESPNOW / DIRECT_PROBE` ownership. PR #425 then made Direct failback commit ordering transactional and fixed Relay channel before encrypted-peer / RelayActive commit.

## PR #425 exact Board B artifact

```text
ARTIFACT_RUN_ID=35294123841
ARTIFACT_ID=10528055066
ARTIFACT_NAME=n3w-pr425-boardb-exact-main
ESPHOME_VERSION=2026.4.3

APPLICATION_SIZE=1128720
APPLICATION_SHA256=bf3af5490745f1279a4e90d57a8e96b46525ae8debaf6f806ed2ae72180836c0

OTADATA_SIZE=8192
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
```

## PR #425 Board B deployment

The exact artifact was written to the intended ESP32-C6 target.

```text
BOARD_B_PR425_DEPLOYMENT=PASS
APPLICATION_WRITE=PASS
OTADATA_WRITE=PASS
APPLICATION_HASH_VERIFY=PASS
OTADATA_HASH_VERIFY=PASS

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false

AUTHORIZED_WRITE_CONSUMED=true
REPLAY_PERMITTED=false
```

## Post-flash and battery Direct baselines

```text
BOARD_B_PR425_POSTFLASH_DIRECT_BASELINE=PASS
BOARD_B_BATTERY_DIRECT_BASELINE=PASS
DIRECT_TELEMETRY_CONTINUOUS=true
MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=0
```

The battery reboot established a new boot session; the later Direct -> Relay transition was performed without another power cycle.

## PR #425 same-boot Direct -> Relay physical result

```text
SAME_BOOT_DIRECT_TO_RELAY=PASS
MANAGER_RELAY_ACCEPTANCE=PASS
BOARD_A_RELAY_GATEWAY_STABLE=true
UNCOMMANDED_REBOOT=false
MANAGER_RESTART_COUNT=0

INITIAL_MANAGER_VISIBLE_GAP_MS=30034
INITIAL_MISSING_SEQUENCE_COUNT=5
```

This is materially shorter than the earlier approximately 110.061 s blackout.

The physical window did not include the low-level `n3w_u` / current-channel / peer-channel diagnostic oracle, so it does not prove the historical `ESP_ERR_ESPNOW_CHAN` class impossible. KF-094 therefore remains open conservatively pending stronger low-level confirmation / complete round-trip acceptance.

## KF-096: periodic Relay blackout during Direct recovery probes

Fresh physical evidence after Relay activation repeatedly showed:

```text
~60 s Relay telemetry
-> ~15 s telemetry suppression
-> Relay resumes
-> repeat
```

At the current ~5 s telemetry cadence this drops about three business samples per probe window.

Exact deployed source contains:

```text
kRecoveryProbeIntervalMs=60000
kRecoveryProbeWindowMs=15000
kRecoveryProbeMs=2000
```

and rejects telemetry while ownership is `DIRECT_PROBE`.

Therefore:

```text
KF096_DOMAIN=PRODUCT
KF096_STATUS=OPEN
KF096_ROOT_CAUSE=SOURCE_CONFIRMED_AND_PHYSICAL_TIMING_CONFIRMED
```

This is not classified as random RF loss, Board A instability, or Manager restart.

## PR #428 KF-096 source repair

PR #428 repaired the source-level continuity defect but has not yet been physically deployed or accepted.

```text
PR428_SOURCE_HEAD=6cae8ea1a75096aab0e625ae56828d13931f7c57
PR428_SOURCE_TREE=3fae2b22b5537e0229b0f7eeacf9f0f3b3aa9a64
PR428_MERGE=f357db25390ffd097e9b8608293870772f9cb16c
MAIN_AFTER_PR428=f357db25390ffd097e9b8608293870772f9cb16c

PR428_PREMERGE_CI=13_OF_13_PASS
PR428_POSTMERGE_PUBLIC_REPOSITORY_SAFETY_CI=PASS
PR428_POSTMERGE_PUBLIC_REPOSITORY_SAFETY_RUN=35308124872
PR428_POSTMERGE_GREENHOUSE_MANAGER_CI=PASS
PR428_POSTMERGE_GREENHOUSE_MANAGER_RUN=35308124851

PR428_EXACT_ARTIFACT_BUILD=PASS
PR428_EXACT_ARTIFACT_BINDING=PASS
PR428_ARTIFACT_RUN_ID=35309484471
PR428_ARTIFACT_ID=10533235759
PR428_ARTIFACT_NAME=n3w-pr428-boardb-exact-source
PR428_APPLICATION_SHA256=b3e2311818d539c2abf98e4fa9ff431069b414da6f9993f350e4a7c427929f3a
PR428_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
PR428_ARTIFACT_ZIP_SHA256=ce5f2de1a152bceb746b22b1aaca7364374ed9f91656230359fed4079776a55e

PR428_PHYSICAL_DEPLOYMENT=NOT_EXECUTED
PR428_PHYSICAL_VALIDATION=NOT_EXECUTED
KF096_STATUS=OPEN
```

The merged repair keeps Relay telemetry in ordered bounded buffering during full Direct verification / Relay restore, uses single-flight ESP-NOW unicast completion ordering, probes the remembered AP BSSID before opening a full Direct verification window, applies 60/120/240/480 s recovery backoff while Relay remains healthy, restores and verifies the concrete Relay channel after presence scanning, and keeps the diagnostic current-channel oracle tied to real Wi-Fi readback rather than logical working-channel state.

This source/CI result does not close KF-096. The deployed Board B remains on PR #425, the historical post-fix `ESP_ERR_ESPNOW_CHAN` elimination still lacks a fresh physical low-level oracle, and Relay -> Direct failback has still not been physically executed on PR #428.

## PR #428 exact artifact binding

```text
BUILD_BRANCH=build/n3w-pr428-boardb-artifact-20260918
WORKFLOW_SOURCE_COMMIT=ec256e8b219942d61ecf583ae558e9aef31b0482
ARTIFACT_RUN_ID=35309484471
ARTIFACT_ID=10533235759
ARTIFACT_NAME=n3w-pr428-boardb-exact-source
ARTIFACT_EXPIRES_AT=2026-09-25T05:09:29Z

SOURCE_HEAD=f357db25390ffd097e9b8608293870772f9cb16c
SOURCE_TREE=3fae2b22b5537e0229b0f7eeacf9f0f3b3aa9a64
ESPHOME_VERSION=2026.4.3
ESP_IDF=5.5.4

APPLICATION_SIZE=1133424
APPLICATION_SHA256=b3e2311818d539c2abf98e4fa9ff431069b414da6f9993f350e4a7c427929f3a

OTADATA_SIZE=8192
OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f

ARTIFACT_ZIP_SIZE=723298
ARTIFACT_ZIP_SHA256=ce5f2de1a152bceb746b22b1aaca7364374ed9f91656230359fed4079776a55e

RAM_USED=50648/327680
FLASH_USED=1133068/3932160

PR428_EXACT_ARTIFACT_BUILD=PASS
PR428_EXACT_ARTIFACT_BINDING=PASS
```

This artifact is not a deployed state. It is now frozen historical evidence and is not deployment-eligible after the PR #431 successor repair. KF-084 remains applicable: a later rebuild from the same source must not silently replace the frozen hashes above.



## PR #431 merged successor / source authority

PR #431 completed three Astra review rounds and is merged.

```text
PR431_STATE=MERGED
PR431_REVIEW_HEAD=137303c7b08fff36920d05e77c2f1bcc20b38d1f
PR431_MERGE=d1b5c3acbd32cca95483743ffe2edba9aa3f904f

PR431_PREMERGE_CI=11_OF_11_PASS
PR431_POSTMERGE_PUBLIC_REPOSITORY_SAFETY_CI=PASS
PR431_POSTMERGE_PUBLIC_REPOSITORY_SAFETY_RUN=35321513253
PR431_POSTMERGE_GREENHOUSE_MANAGER_CI=PASS
PR431_POSTMERGE_GREENHOUSE_MANAGER_RUN=35321513207

PR431_POSTMERGE_PHASE4_SIMPLIFIED_PRODUCT_RUNTIME=PASS
PR431_POSTMERGE_ESP32_C6_CHILD_COMPILE=PASS
PR431_POSTMERGE_ESP32_C6_RELAY_COMPILE=PASS
PR431_POSTMERGE_ESP32_C6_PHYSICAL_HARNESS_COMPILE=PASS

ASTRA_FINAL_REVIEW=PASS
A1_PARTIAL_INIT_TEARDOWN=CLOSED
A2_STARTUP_UNCONFIRMED_EXIT=CLOSED
REAL_DRIVER_FAULT_INJECTION_COVERAGE=SUFFICIENT
NO_NEW_MERGE_BLOCKER=true
```

The merged finite repair preserves the existing radio architecture. It fixes BSSID configuration provenance, bounds unicast/restore exits, uses a fresh-boot boundary for abnormal missing completion, tracks partial ESP-NOW initialization with an independent SDK-started state, and reboots rather than indefinitely retrying startup when teardown is unconfirmed.

Source/CI success does not close KF-096 and does not authorize Board B access or flashing. PR #431 remains the latest merged product-source authority, but its artifact is historical for the current validation route because the newer unmerged PR #437 candidate now has its own exact artifact.

## Historical PR #437 successor snapshot (`cc9ed5ee...`)

Local source review, repair, CI, repository cleanup, and exact-artifact binding are now aligned to GitHub.

```text
PR437_STATE=OPEN_DRAFT
PR437_HEAD=cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
PR437_SOURCE_TREE=b459fae0a054d45b0d09e60bffae9769e060a5c0
PR437_BASE_MAIN_AT_REPAIR=d9afc55b04042806ed8b6e1b1ae3553742aba2be

PR437_FINAL_SOURCE_REVIEW=PASS
PR437_NEW_SOURCE_BLOCKER_FOUND=false
A1_PHASE_DEADLINE_LATE_PROGRESS_BYPASS=CLOSED
A2_ABSOLUTE_DEADLINE_SUCCESS_PATH_BYPASS=CLOSED
A3_BSSID_WALLCLOCK_EXPIRY_INTEGRATION_GAP=CLOSED
DIRECT_COMMIT_AFTER_ABSOLUTE_DEADLINE=CLOSED

PR437_FINAL_GREENHOUSE_MANAGER_CI_RUN=35373202121
PR437_HEAD_WORKFLOW_COUNT=11
PR437_HEAD_WORKFLOW_SUCCESS_COUNT=11

PR437_EXACT_ARTIFACT_BUILD=PASS
PR437_EXACT_ARTIFACT_BINDING=PASS
PR437_ARTIFACT_RUN_ID=35414060819
PR437_ARTIFACT_ID=10575077512
PR437_ARTIFACT_NAME=n3w-pr437-boardb-exact-source
PR437_ARTIFACT_ZIP_SIZE=727532
PR437_ARTIFACT_ZIP_SHA256=b06de88b561968627b17bbda45d5d8fd9e53d774a5227237a71343ebc39a3814
PR437_APPLICATION_SIZE=1139600
PR437_APPLICATION_SHA256=407767b3e1593f4237f650abecd7d29b3873b7b08bf8b5d9fc85a972119725bb
PR437_OTADATA_SIZE=8192
PR437_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
PR437_MANIFEST_SHA256=98a6dec323e8057a30d6b1e332d549fe54288f3b45fcbbbf460292871f7a91a0

PR437_BOARD_B_DEPLOYMENT=PASS
PR437_POSTWRITE_DIRECT_BASELINE=PASS
PR437_PHYSICAL_VALIDATION=PASS

PR439_STATE=MERGED
PR439_REVIEW_HEAD=da6b1e7e364a0125c832e27c62b6c9741bdbfa17
PR439_MERGE=02efd64312c4b01c19c0a18e6db543145a16ad9c
PR439_FINAL_SOURCE_REVIEW=PASS
PR439_CI=12_OF_12_PASS
PR439_FOCUSED_TESTS=12_PASS
PR439_A1_SINGLE_USE_WRITE_AUTHORIZATION=CLOSED
PR439_A2_PARTITION_TABLE_FRESH_BINDING=CLOSED
```

Repository hygiene was also aligned: 18 merged recent N3-W branches were deleted, PR #436 was closed as superseded, the PR #437 branch was preserved, and historical artifact build branches were preserved.

The exact PR #437 artifact is the current Board B validation candidate. Artifact binding proves source-to-binary identity only; KF-096 remains OPEN until fresh physical evidence closes the required runtime route.

## PR #439 merged Board B preflight/write executor

PR #439 merged the PR #437-specific fail-closed Board B preflight/write executor after the final post-repair source review.

```text
PR439_STATE=MERGED
PR439_REVIEW_HEAD=da6b1e7e364a0125c832e27c62b6c9741bdbfa17
PR439_MERGE=02efd64312c4b01c19c0a18e6db543145a16ad9c

PR439_FINAL_SOURCE_REVIEW=PASS
PR439_NEW_SOURCE_BLOCKER_FOUND=false
PR439_CI=12_OF_12_PASS
PR439_FOCUSED_CI_RUN=35433539838
PR439_FOCUSED_TESTS=12_PASS

A1_SINGLE_USE_WRITE_AUTHORIZATION=CLOSED
A2_PARTITION_TABLE_FRESH_BINDING=CLOSED

BOARD_IDENTITY_GUARD=PASS
SECURITY_STATE_GUARD=PASS
PARTITION_TABLE_PREFLIGHT_BINDING=PASS
PARTITION_TABLE_PREWRITE_REBIND=PASS
PREFLIGHT_FRESHNESS_GUARD=PASS
AUTHORIZATION_CLAIM_BEFORE_MUTATION=PASS
AUTHORIZATION_REPLAY_GUARD=PASS
MINIMAL_WRITE_SCOPE=PASS
```

The executor is bound to PR #437 artifact `10575077512`. It performs a fresh read-only partition-table binding at `0x8000` over `0xC00` bytes and requires SHA-256 `6664b08a14a9cdc170e322823db29fbe485d87db9c4ec42759d9372028953dca`. The write scope remains otadata at `0x9000` plus application at `0x10000`; bootloader, partition table, product NVS, and full-chip erase remain forbidden.

PR #439 merge does not authorize Board B Flash mutation. A bounded read-only Board B preflight is the next gate; any later Flash write requires a separate explicit one-shot authorization.

## Historical PR #437 Board B deployment and post-write Direct baseline

The exact PR #437 artifact was written to the operator-confirmed Board B target. The automated frozen Board B hardware-identity comparison failed before write; the operator explicitly confirmed the physical target and authorized a one-time override. Raw identity material is not public evidence, the automated identity check must not be rewritten as PASS, and this override does not carry forward to future board mutations.

```text
PR437_BOARD_B_DEPLOYMENT=PASS

AUTOMATED_BOARD_IDENTITY_MATCH=FAIL
OPERATOR_TARGET_CONFIRMATION=PASS
OPERATOR_IDENTITY_OVERRIDE=true
RAW_BOARD_IDENTITY_PUBLIC=false
IDENTITY_OVERRIDE_REUSABLE=false

ARTIFACT_DOWNLOAD=PASS
ARTIFACT_INNER_BINDING=PASS
SECURITY_STATE=PASS
FLASH_SIZE=8MB
PARTITION_TABLE_BINDING=PASS

APPLICATION_WRITE=PASS
OTADATA_WRITE=PASS
APPLICATION_READBACK_HASH_VERIFY=NOT_EXECUTED
OTADATA_READBACK_HASH_VERIFY=NOT_EXECUTED

BOOTLOADER_WRITE=false
PARTITION_TABLE_WRITE=false
PRODUCT_NVS_WRITE=false
FULL_FLASH_ERASE=false

WRITE_AUTHORIZATION_CLAIMED=true
WRITE_AUTHORIZATION_CONSUMED=true
WRITE_AUTHORIZATION_REPLAY_PERMITTED=false
```

A fresh T1/Manager canonical-cursor observation then proved the written firmware is live on Direct without opening application serial:

```text
PR437_POSTWRITE_DIRECT_BASELINE=PASS
OBSERVATION_SECONDS=90

BOARD_B_CANONICAL_CURSOR_BEFORE=FOUND
BOARD_B_CANONICAL_CURSOR_AFTER=FOUND
BOARD_B_SOURCE_BEFORE=direct
BOARD_B_SOURCE_AFTER=direct

BOARD_B_SEQ_BEFORE=1370
BOARD_B_SEQ_AFTER=1388
BOARD_B_SEQ_DELTA=18

BOARD_B_SAME_BOOT=true
BOARD_B_CANONICAL_ADVANCED=true
BOARD_B_LAST_SOURCE_DIRECT=true

T1_MANAGER_RUNNING=true
MANAGER_RESTART_COUNT_BEFORE=0
MANAGER_RESTART_COUNT_AFTER=0
MANAGER_STARTED_AT_UNCHANGED=true
MANAGER_RESTART_COUNT_UNCHANGED=true
```

The earlier bounded Manager log query returned zero matching Direct acceptance INFO lines. Canonical durable state advanced cleanly during the same period, so this is classified under the existing KF-010 logging-oracle guard:

```text
MANAGER_INFO_LOG_ORACLE=FALSE_NEGATIVE
PRODUCT_DIRECT_PATH_FAILURE=false
CANONICAL_DURABLE_EVIDENCE=PASS
```

PR #437 physical validation is now complete for the KF-096 route. The same deployed Board B boot completed Direct -> Relay, a 600 s Relay steady-state window, and Relay -> Direct failback without board or T1 runtime mutation.

### PR #437 final physical closure

```text
PR437_SAME_BOOT_DIRECT_TO_RELAY=PASS
DIRECT_TO_RELAY_MANAGER_VISIBLE_GAP_MS=35087
DIRECT_TO_RELAY_MISSING_SEQUENCE_COUNT=6
DIRECT_TO_RELAY_MISSING_SEQUENCE_RANGE=897-902

PR437_RELAY_DATA_CONTINUITY_600S=PASS
RELAY_STEADY_STATE_SEQ_START=996
RELAY_STEADY_STATE_SEQ_END=1116
RELAY_STEADY_STATE_ACCEPTED_ROW_COUNT=121
RELAY_STEADY_STATE_MISSING_SEQUENCE_COUNT=0
RELAY_SOURCE_NON_RELAY_OBSERVED=false
RELAY_BOARD_B_SAME_BOOT=true
RELAY_MAX_MANAGER_INTERARRIVAL_GAP_MS=20589
ORDERED_CATCHUP_OBSERVED=true
BOARD_B_PROBE_FIFO_CAUSE=STRONGLY_SUPPORTED_NOT_YET_CONFIRMED

PR437_RELAY_TO_DIRECT_FAILBACK=PASS
RELAY_TO_DIRECT_MANAGER_VISIBLE_GAP_MS=10689
RELAY_TO_DIRECT_MISSING_SEQUENCE_COUNT=0
RELAY_TO_DIRECT_DATA_CONTINUITY=PASS
SAME_BOOT_RELAY_TO_DIRECT=true
RELAY_AFTER_FIRST_DIRECT_OBSERVED=false

MANAGER_RESTART_COUNT_UNCHANGED=true
BOARD_A_MUTATION=false
BOARD_B_FLASH_MUTATION=false
T1_RUNTIME_MUTATION=false
APPLICATION_SERIAL_OPEN=false
PR437_MERGE=false

KF096_STATUS=CLOSED_PASS
OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED
```

The 20.589 s Relay Manager interarrival gap is retained as a delivery-latency observation, not reclassified as data loss: all 121 durable tuples in seq 996..1116 were present, and the gap was followed by ordered catch-up at 202 ms, 50 ms, and 51 ms intervals before the normal cadence resumed. A follow-up read-only attempt to recover payload `uptime_ms` found no persisted payload history for this target range, so the exact buffering location remains unproven.

KF-096 is closed because the historical periodic Direct-recovery-probe behavior that discarded Relay business telemetry was not reproduced in the 600 s Relay window. This closure does not erase the six missing sequences during the initial Direct -> Relay transition. That transition-loss fact remains open for later N3-W acceptance work and keeps `OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED`.

## Historical acceptance matrix snapshot

```text
KF092_STATUS=CLOSED_PASS
KF093_TASK_WDT=GUARDED
KF094_SINGLE_RADIO_CHANNEL_OWNERSHIP=OPEN
KF095_FAILBACK_COMMIT_ORDER=GUARDED
KF096_DIRECT_PROBE_TELEMETRY_BLACKOUT=CLOSED_PASS

PR428_SOURCE_REPAIR=MERGED
PR428_SOURCE_HEAD=6cae8ea1a75096aab0e625ae56828d13931f7c57
PR428_MERGE=f357db25390ffd097e9b8608293870772f9cb16c
PR428_PREMERGE_CI=13_OF_13_PASS
PR428_POSTMERGE_CI=PASS
PR428_EXACT_ARTIFACT_BUILD=PASS
PR428_EXACT_ARTIFACT_BINDING=PASS
PR428_ARTIFACT_RUN_ID=35309484471
PR428_ARTIFACT_ID=10533235759
PR428_BOARD_B_DEPLOYMENT=NOT_EXECUTED
PR428_PHYSICAL_VALIDATION=NOT_EXECUTED
PR428_ARTIFACT_DISPOSITION=FROZEN_HISTORICAL_NOT_FOR_DEPLOYMENT

PR431_SOURCE_REPAIR=MERGED
PR431_REVIEW_HEAD=137303c7b08fff36920d05e77c2f1bcc20b38d1f
PR431_MERGE=d1b5c3acbd32cca95483743ffe2edba9aa3f904f
PR431_PREMERGE_CI=11_OF_11_PASS
PR431_POSTMERGE_CI=PASS
PR431_ASTRA_FINAL_REVIEW=PASS
PR431_EXACT_ARTIFACT_PREPARATION=PASS
PR431_EXACT_ARTIFACT_BUILD=PASS
PR431_EXACT_ARTIFACT_BINDING=PASS
PR431_ARTIFACT_RUN_ID=35339630187
PR431_ARTIFACT_ID=10544254111
PR431_APPLICATION_SHA256=c6cdab938a58ac1bc29f3a04a69d157acc23625ab239f8a644841de241af3730
PR431_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
PR431_ARCHIVE_SHA256=94ff922ce50314ed6f3275376eb5b1e71ae27f27f6edd16f9dd0743259dd13b6
PR431_BOARD_B_DEPLOYMENT=NOT_EXECUTED
PR431_PHYSICAL_VALIDATION=NOT_EXECUTED
PR431_ARTIFACT_DISPOSITION=FROZEN_HISTORICAL_NOT_FOR_CURRENT_PR437_VALIDATION

PR437_SOURCE_REPAIR=OPEN_DRAFT
PR437_HEAD=cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
PR437_FINAL_SOURCE_REVIEW=PASS
PR437_HEAD_CI=11_OF_11_PASS
PR437_EXACT_ARTIFACT_BUILD=PASS
PR437_EXACT_ARTIFACT_BINDING=PASS
PR437_ARTIFACT_RUN_ID=35414060819
PR437_ARTIFACT_ID=10575077512
PR437_APPLICATION_SHA256=407767b3e1593f4237f650abecd7d29b3873b7b08bf8b5d9fc85a972119725bb
PR437_OTADATA_SHA256=7d2c7ac4888bfd75cd5f56e8d61f69595121183afc81556c876732fd3782c62f
PR437_ARCHIVE_SHA256=b06de88b561968627b17bbda45d5d8fd9e53d774a5227237a71343ebc39a3814
PR437_BOARD_B_DEPLOYMENT=PASS
PR437_POSTWRITE_DIRECT_BASELINE=PASS
PR437_PHYSICAL_VALIDATION=PASS

PR425_POST_MERGE_CI=PASS
PR425_EXACT_ARTIFACT_BINDING=PASS
PR425_BOARD_B_DEPLOYMENT=PASS
PR425_POSTFLASH_DIRECT_BASELINE=PASS
PR425_BATTERY_DIRECT_BASELINE=PASS

PR425_SAME_BOOT_DIRECT_TO_RELAY_FUNCTIONAL_RESULT=PASS
PR425_INITIAL_MANAGER_VISIBLE_GAP_MS=30034

PR425_RELAY_STEADY_STATE_CONTINUITY=FAIL
PR425_RELAY_TO_DIRECT_FAILBACK_VALIDATION=NOT_EXECUTED

OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED
```

## Required guards

- USB path is only a locator; board-targeted write authorization remains explicit and single-use.
- Do not open application serial as a passive oracle; it can reset the board.
- Do not mutate Board A, T1 Manager/Broker, DynSec, credentials, or TLS merely to diagnose the current source defect.
- Keep repository-main authority separate from frozen deployed product-source authority.
- Do not attribute the entire historical ~110 s or current ~30 s Direct -> Relay gap to a single phase without phase-specific evidence.
- Do not claim historical `ESP_ERR_ESPNOW_CHAN` eliminated unless post-fix low-level channel/error diagnostics prove it.
- `ESP_OK` from ESP-NOW submit is not async RF delivery proof.
- Direct recovery must not achieve failback responsiveness by silently discarding periodic Relay business telemetry.
- PR #428 and PR #431 artifacts are historical evidence for the current route. The exact PR #437 artifact `10575077512` is now deployed on the operator-confirmed Board B target and has a PASS post-write Direct baseline; full physical acceptance still requires Direct -> Relay, Relay steady-state continuity, and Relay -> Direct failback evidence.
- Consumed physical authorizations are never replayable.
- The one-time operator override of the automated Board B identity mismatch is frozen as historical execution evidence only. It does not change the repository identity guard and must not be inherited by any future board mutation.

## Historical ONE gate snapshot

```text
NEXT_ONE_GATE=N3W_KF096_PR437_PREMERGE_FINAL_REVIEW_20260919_01

MERGED_PRODUCT_SOURCE_AUTHORITY=d1b5c3acbd32cca95483743ffe2edba9aa3f904f
CURRENT_CANDIDATE_SOURCE_HEAD=cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
CURRENT_CANDIDATE_SOURCE_TREE=b459fae0a054d45b0d09e60bffae9769e060a5c0
DEPLOYED_BOARD_B_SOURCE_HEAD=cc9ed5ee568a4b6c4a2454fd38bafa8f6e3a527c
DEPLOYED_BOARD_B_SOURCE_TREE=b459fae0a054d45b0d09e60bffae9769e060a5c0

PR437_BOARD_B_DEPLOYMENT=PASS
PR437_POSTWRITE_DIRECT_BASELINE=PASS
PR437_PHYSICAL_VALIDATION=PASS
KF096_STATUS=CLOSED_PASS

DIRECT_TO_RELAY_MISSING_SEQUENCE_COUNT=6
OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED

BOARD_B_FIRMWARE_FLASH=false
BOARD_A_MUTATION=false
APPLICATION_SERIAL_OPEN=false
T1_RUNTIME_MUTATION=false
PR437_MERGE=false
```

The next gate is repository-only final review of PR #437 merge readiness. It must preserve the six Direct -> Relay transition losses as an unresolved N3-W acceptance fact, verify the exact PR head/CI/mergeability and documentation alignment, and must not merge PR #437 without a separate explicit merge authorization.

## Public/private evidence boundary

Public GitHub may store source, tests, artifact hashes, sanitized timing/acceptance results, and architecture decisions. Do not commit raw credentials, setup secrets, private keys, raw NVS, private host addresses, raw Manager/Broker logs, or raw board identity material.
