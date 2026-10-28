# N3-W R10 T1 candidate production-software upgrade package freeze

Date: 2026-10-28

## 1. Gate

```text
TASK=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_UPGRADE_PACKAGE_FREEZE_20261028_01

BASE_READONLY_PREFLIGHT_HEAD=d7ceb4562ab14d0b7a8f725e1e918c7735f7b482
PREDECESSOR_SOURCE=03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6
TARGET_PRODUCT_SOURCE=e299c937a7b89bb8a7b9a7432186ba46a416cd44

T1_ACCESS=false
T1_MUTATION=false
SERVICE_STOP_START=false
BOARD_ACCESS=false
LIVE_UPGRADE=false
MERGE=false
```

This gate freezes the exact executable package for the later separately authorized live T1 production-software upgrade.

It does not execute the upgrade.

## 2. Live predecessor evidence

The real T1 read-only preflight passed with:

```text
CURRENT_MANAGER_SOURCE=03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6
TARGET_MANAGER_SOURCE=e299c937a7b89bb8a7b9a7432186ba46a416cd44
CURRENT_MANAGER_IMAGE=local/greenhouse-manager:fresh-03dab2bd04e7
TARGET_MANAGER_IMAGE=local/greenhouse-manager:fresh-e299c937a7b8
NETWORKMANAGER_TRUSTED_LAN_SOURCE=PASS
DATABASE_INTEGRITY=PASS
FIRST_REGISTRATION_TABLE_PRESENT=false
CURRENT_REGISTRATION_COUNT=1
CANDIDATE_IMAGE_PREEXISTING=false
ROOT_FREE_BYTES=6241112064
```

The live installed F4 services unit is the expected predecessor F4 unit, while the generic runtime-source unit remains separately present.

## 3. Package scope

Routine fresh-install three-image transport is forbidden for this upgrade.

The package contains only:

1. exact ARM64 greenhouse-manager image built from `TARGET_PRODUCT_SOURCE`;
2. exact public runtime files required to add scan-triggered first-registration host support;
3. source-owned live-upgrade executor;
4. exact manifest containing source, file, image, size and rollback bindings.

Home Assistant and Mosquitto images are not included.

## 4. Exact runtime material

### 4.1 F4-bound material that changes

These paths are already covered by the durable F4 `installed_files` authority and therefore require a successor rebind after byte replacement:

```text
/etc/n3wfc4/docker-compose.yml
/etc/systemd/system/n3wfc4-services-activation.service
/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
/usr/local/sbin/n3w-t1-f4-activation
```

Target source authorities:

```text
compose_source=infra/n3w-t1/production/docker-compose.fresh.yml
compose_git_blob=c9038251d9ba1b05a472edda14b287470690815a

services_f4_source=infra/n3w-t1/f4/n3wfc4-services-activation.service
services_f4_git_blob=3485b6c2f9341fda2fcbd2c82c83077ad78cf42c

dispatcher_source=infra/n3w-t1/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
dispatcher_git_blob=3d6f32455fffd6f604f83a6c12e298bc395945e0

f4_launcher_source=tools/n3w_t1_f4_activation_host.py
f4_launcher_git_blob=08889200fe9663d223016a3cb3e1b4af0a9ffcd2
```

### 4.2 New live material

```text
/etc/systemd/system/n3wfc4-registration-ingress-guard.service
/usr/local/sbin/n3w-registration-ingress-guard
/usr/local/sbin/n3w-trusted-product-lan-authority
/etc/n3wfc4/registration-tls/bootstrap.pem
/etc/n3wfc4/registration-tls/bootstrap.key
```

The registration TLS key/certificate are device-instance material and are never included in the public artifact. They are generated locally from the exact candidate Manager image and remain T1-private.

### 4.3 Runtime-source overlay

The package also updates the corresponding public source copies under `/opt/HomeAssistant` so live installed material is not detached from the source tree used for later forensics.

Required overlay:

```text
infra/n3w-t1/production/docker-compose.yml
    <- exact bytes of target docker-compose.fresh.yml
infra/n3w-t1/f4/n3wfc4-services-activation.service
infra/n3w-t1/systemd/n3wfc4-services-activation.service
infra/n3w-t1/systemd/n3wfc4-registration-ingress-guard.service
infra/n3w-t1/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
tools/n3w_t1_f4_activation_host.py
tools/n3w_registration_ingress_guard.py
tools/n3w_trusted_product_lan_authority.py
```

The rest of `/opt/HomeAssistant` is not replaced by this bounded upgrade.

## 5. F4 successor binding

### 5.1 Problem

The production services unit executes:

```text
/usr/local/sbin/n3w-t1-f4-activation eligibility --phase services
```

F4 eligibility validates every F4-bound live path against the durable `installed_files` map.

Blindly replacing the compose/unit/dispatcher/launcher would therefore make a legitimate upgrade look like unauthorized drift and prevent Manager/Home Assistant restart.

### 5.2 Frozen solution

The R10 upgrade owns one explicit successor transition.

It MUST preserve byte-for-byte historical F4 identity fields:

```text
schema
authorization_id/history
release_id
host_instance_id
system_id/system_id_sha256
package_source_head
package_manifest_sha256
runtime_acceptance_report_sha256
certificate_status_sha256
all historical authorization fields
```

It may update only:

```text
installed_files
r10_candidate_upgrade_*
```

The successor metadata must include at minimum:

```text
r10_candidate_upgrade_authorization_id
r10_candidate_upgrade_authorization_claimed=true
r10_candidate_upgrade_authorization_consumed=true
r10_candidate_upgrade_replay_allowed=false
r10_candidate_upgrade_predecessor_source
r10_candidate_upgrade_target_source
r10_candidate_upgrade_manifest_sha256
r10_candidate_upgrade_predecessor_installed_files_sha256
r10_candidate_upgrade_successor_installed_files_sha256
r10_candidate_upgrade_committed=false/true
```

The successor rebind is written only after every F4-bound target file has been installed and independently hash/mode/owner verified.

After rebind, the exact target F4 launcher must pass `eligibility --phase services` before product services are started.

Any failure after successor rebind restores the exact pre-upgrade F4 transaction bytes before old services are restarted.

## 6. Instance state and rollback

Before product-state mutation the live executor creates a root-owned mode-0700 rollback root.

It privately binds/captures:

- exact F4 transaction bytes;
- exact live files that will be replaced;
- exact runtime-source overlay predecessor bytes or predecessor absence;
- `docker-compose.env`;
- registration-TLS predecessor absence/state;
- registration-guard enablement/load state;
- target Manager image predecessor absence;
- current Broker/Manager/HA container image IDs and start/restart state;
- exact filter-table evidence required to prove registration-chain predecessor absence.

After Manager/HA are stopped, it captures quiescent copies of:

```text
/var/lib/greenhouse-manager/manager
/var/lib/greenhouse-manager/n3w
```

The rollback snapshot is private and must never be committed or pasted into chat.

Home Assistant data is not rolled back because the HA image/config are unchanged and ordinary stop/start is part of the controlled maintenance window.

Broker data/image/config are not mutated.

## 7. Mutation order

The later live executor uses this order:

```text
A. exact package + live-predecessor preclaim validation
B. one-shot authorization claim
C. private static/F4 rollback snapshot
D. docker load exact target Manager image
E. generate dedicated registration TLS into private staging
F. stop n3wfc4-services-activation.service only
G. prove Broker continuity
H. quiescent Manager/N3W state backup
I. install runtime-source overlay and live public files
J. atomically update GH_MANAGER_IMAGE in existing compose env only
K. install registration TLS with exact owner/mode
L. daemon-reload + enable/start registration guard
M. successor-rebind F4 installed_files
N. target F4 eligibility --phase services PASS
O. start n3wfc4-services-activation.service
P. strict postcheck
Q. commit upgrade transaction
```

No Compose override and no `--force-recreate` are allowed.

## 8. Postcheck

PASS requires:

```text
TARGET_MANAGER_IMAGE_RUNNING=true
BROKER_IMAGE_UNCHANGED=true
BROKER_CONTAINER_CONTINUITY=true
HOMEASSISTANT_IMAGE_UNCHANGED=true
REGISTRATION_GUARD_ACTIVE=true
REGISTRATION_GUARD_ENABLED=true
TRUSTED_PRODUCT_LAN_READY=true
TCP_47110_LISTENERS=1
UDP_47111_LISTENERS=1
TCP_47112_LISTENERS=0
PAIRING_WINDOW=CLOSED
DATABASE_INTEGRITY=PASS
FIRST_REGISTRATION_TABLE_PRESENT=true
UNRESOLVED_FIRST_REGISTRATION=0
CURRENT_REGISTRATION_COUNT=1
F4_SERVICES_ELIGIBILITY=PASS
F4_HISTORICAL_PACKAGE_BINDING_UNCHANGED=true
F4_SUCCESSOR_INSTALLED_FILES_BOUND=true
```

The existing registered node count must remain one. The upgrade is not allowed to delete/recreate that registration.

## 9. Rollback order

If any post-claim step fails:

```text
stop new services if started
stop/disable registration guard
remove only exact owned registration firewall anchors/chain
restore Manager/N3W quiescent state snapshot if Manager may have started
restore compose env
restore runtime-source overlay
restore all predecessor live files / remove predecessor-absent files
restore predecessor registration-TLS absence/state
restore exact predecessor F4 transaction bytes
daemon-reload
start predecessor services unit
verify old Manager image + HA + Broker runtime
remove target Manager image tag if safe
record rollback result
STOP
```

A rollback that cannot prove the old runtime healthy is terminal and requires manual/high-level recovery. No automatic second upgrade attempt is allowed.

## 10. Capacity contract

The old fixed fresh-install 5 GiB staging reserve is not reused as a product runtime minimum.

The upgrade package records:

```text
manager_tar_size_bytes
manager_image_size_bytes
runtime_bundle_size_bytes
```

Live admission additionally measures the actual private rollback size before critical mutation.

The bounded engineering transaction requires:

```text
free_after_package_staging
  >= manager_image_size_bytes
   + rollback_snapshot_bytes
   + UPGRADE_EMERGENCY_RESERVE_BYTES
```

`UPGRADE_EMERGENCY_RESERVE_BYTES` is an upgrade-transaction safety reserve only, not a permanent product runtime free-space requirement. This gate initially freezes it at 2 GiB; later OTA work may replace it with a measured product policy.

## 11. Artifact security

The artifact contains no:

- SYSTEM_ID raw value;
- MQTT passwords;
- Setup Secret;
- TLS private keys;
- registration TLS instance key;
- raw Manager database;
- customer LAN subnet/address;
- board identity.

All public artifact files are exact-source or generated public manifest/executor material.

## 12. Authorization boundary

Package build/CI does not authorize live use.

The later live upgrade requires a new explicit authorization distinct from the still-unconsumed R10 board-write authorization.

```text
T1_UPGRADE_AUTHORIZATION_GRANTED=false
R10_BOARD_WRITE_AUTHORIZATION_CONSUMED=false
```

## 13. Next steps in this gate

1. implement package builder / exact manager-only artifact workflow;
2. implement source-owned live executor without executing it;
3. add failure-matrix tests, especially F4 successor rebind and rollback;
4. build and independently re-download/verify the exact artifact;
5. freeze artifact ID/digest/member hashes and exact package head;
6. stop before T1 mutation.
