# N3-W R10 T1 candidate upgrade — source design and read-only preflight

Date: 2026-10-28

## 1. Task / boundary

```text
TASK=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_UPGRADE_DESIGN_AND_READONLY_PREFLIGHT_20261028_01
BASE_R10_READONLY_HEAD=44a3faefff70b89032fd7b2bfbf64733b175b123
CURRENT_DEPLOYED_MANAGER_SOURCE=03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6
TARGET_PRODUCT_SOURCE=e299c937a7b89bb8a7b9a7432186ba46a416cd44
TARGET_MANAGER_IMAGE=local/greenhouse-manager:fresh-e299c937a7b8

T1_ACCESS=READ_ONLY_ONLY
T1_MUTATION=false
SERVICE_STOP_START=false
CONTAINER_RECREATE=false
BOARD_ACCESS=false
BOARD_MUTATION=false
MERGE=false
```

This gate exists because the first R10 physical acceptance preflight proved that the live T1 runtime is older than the scan-triggered first-registration product source.

The purpose of this gate is to freeze the exact candidate upgrade delta and perform a fail-closed live read-only deployment preflight. It does not authorize applying the upgrade.

## 2. Physical evidence that opened this gate

The R10 T1 preflight reached the real host and stopped before board access.

Public-safe observations:

```text
CURRENT_MANAGER_IMAGE=local/greenhouse-manager:fresh-03dab2bd04e7
REGISTRATION_GUARD=not-found/inactive
TRUSTED_PRODUCT_LAN_READY=false
TCP_47110_LISTENERS=0
UDP_47111_LISTENERS=0
TCP_47112_LISTENERS=0
SCAN_FIRST_REGISTRATION_CAPABILITY=false
FIRST_REGISTRATION_DATABASE_SCHEMA_READY=false
PAIRING_WINDOW=CLOSED
```

The Manager continues to have the already expected baseline runtime flags:
- product durable pairing disabled;
- N3-W runtime enabled;
- advertised host set to auto.

Therefore the stop is a host deployment-generation mismatch, not evidence of a board defect.

No board flash/NVS access occurred and the R10 write authorization remains unconsumed.

## 3. Source-line conclusion

The deployed image naming contract binds:

```text
local/greenhouse-manager:fresh-<source_head[0:12]>
```

Therefore the observed live image binds to:

```text
03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6
```

The frozen R9/R10 product source is:

```text
e299c937a7b89bb8a7b9a7432186ba46a416cd44
```

The target is intentionally not mutable `main`. Host and board acceptance must use the same reviewed product source line.

The source delta contains the missing first-registration host pieces, including:
- Manager first-registration transaction/runtime modules;
- first-registration ledger/database schema;
- low-privilege TCP 47110 bootstrap and UDP 47111 discovery;
- identity-bound product 47112 opening;
- trusted-product-LAN parser;
- host trusted-LAN authority;
- registration ingress guard;
- registration TLS Compose mounts/env;
- systemd/NetworkManager lifecycle binding.

## 4. Minimal upgrade unit

The upgrade MUST NOT be implemented as only a Manager image swap.

The exact minimal unit is:

1. exact ARM64 Manager image built from `e299c937...`;
2. updated production Compose binding;
3. `n3w-trusted-product-lan-authority`;
4. `n3w-registration-ingress-guard`;
5. `n3wfc4-registration-ingress-guard.service`;
6. updated `n3wfc4-services-activation.service`;
7. updated NetworkManager dispatcher integration;
8. dedicated registration TLS certificate/key;
9. updated public runtime source needed by these components.

The Broker image and Home Assistant image are not candidate-upgrade targets.

## 5. Registration TLS rule

The candidate source uses a dedicated self-signed EC registration certificate, separate from the Broker transport CA/server certificate.

Upgrade rules:
- do not rotate the existing Broker CA/server keypair;
- generate a new dedicated registration key/certificate only if the exact candidate preparation proves no prior valid registration pair exists;
- private key remains T1-local;
- target ownership/mode must match the Manager runtime contract;
- rollback must restore the exact prior state, including prior absence.

No registration private key or certificate body may enter public GitHub evidence.

## 6. Database migration rule

The target Manager initializes `first_registration_attempts` with `CREATE TABLE IF NOT EXISTS` through normal Manager runtime construction.

Rules:
- no manual SQL table fabrication;
- no database deletion/reset;
- capture and verify a private prechange Manager database backup before candidate startup;
- candidate startup may perform only source-defined initialization/migration;
- postcheck requires the new table/schema and zero unresolved predecessor attempts;
- pre-existing registrations/node identity/credential state must remain unchanged;
- any post-claim failure after database mutation requires exact rollback to the private prechange database snapshot before the old Manager is restarted.

## 7. Service lifecycle

Production Manager and Home Assistant are owned together by:

```text
n3wfc4-services-activation.service
```

Therefore the mutation gate must use the product lifecycle rather than bypass it.

Forbidden:
- `docker compose --force-recreate`;
- Compose override files;
- direct normal-pairing style Manager replacement;
- Broker recreation;
- Home Assistant image change.

Expected controlled upgrade lifecycle:

```text
read-only preclaim
-> private rollback capture
-> authorization claim
-> stop n3wfc4-services-activation.service
-> Broker remains running
-> install/load exact candidate inputs
-> systemctl daemon-reload
-> registration guard/trusted-LAN readiness
-> start n3wfc4-services-activation.service
-> strict postcheck
```

A bounded Manager + Home Assistant restart is therefore expected for this software upgrade. It is not part of normal pairing behavior.

## 8. Rollback authority

The existing generic T1 backup tool is useful for Manager/Broker data, but it does not by itself bind every file changed by this candidate upgrade.

Before claim, the mutation package must privately bind at minimum:
- current Manager image ref + image ID;
- current Manager/HA container identities, restart counts and start times;
- current Compose file and Compose env;
- relevant `/opt/HomeAssistant` runtime files;
- current services-activation unit;
- registration-guard unit presence/absence and content;
- trusted-LAN/registration guard tools presence/absence and content;
- NetworkManager dispatcher file;
- registration TLS presence/absence and any prior exact private pair;
- Manager SQLite backup + integrity result;
- current service/listener state.

Rollback must restore the exact predecessor inventory, not merely restart the old image.

## 9. Candidate artifact authority

The existing repository workflow can build an exact ARM64 Manager image tagged from the source head and can package the fresh runtime source.

For this in-place upgrade, the fresh bootstrap apply path itself MUST NOT be reused as the live mutation mechanism.

The candidate upgrade package must bind only the exact needed material from:

```text
TARGET_PRODUCT_SOURCE=e299c937a7b89bb8a7b9a7432186ba46a416cd44
```

Required artifact evidence before live mutation:
- workflow run ID;
- artifact ID/name;
- artifact digest;
- candidate Manager tar SHA-256;
- candidate Manager image ID;
- arm64/linux identity;
- exact public runtime file hashes;
- exact source head.

## 10. Read-only T1 preflight

The new preflight must not stop/start services, load images, create files on T1, modify firewall, generate TLS, or run database migrations.

It must collect public-safe evidence for:

### Runtime identity
- exactly one Broker/Manager/Home Assistant container;
- current image refs and hashed IDs;
- restart counts/start times;
- expected current Manager image is the `03dab2bd04e7` predecessor;
- Broker and HA image refs match the target source's unchanged bindings.

### Lifecycle files
- current Compose and env path resolution;
- hashes/modes/ownership for Compose, services unit and dispatcher;
- presence/absence and hashes for registration guard/trusted-LAN tools and unit;
- no unexpected override/alternate lifecycle file.

### Registration prerequisites
- registration TLS current presence/absence without exposing key material;
- trusted-LAN runtime current presence/absence;
- 47110=0, 47111=0 and 47112=0 are accepted as the expected predecessor baseline;
- pairing window remains CLOSED.

### Database
- Manager DB exists, is regular/private, and passes read-only integrity check;
- current business tables are inventoried by names only;
- current registration count and other non-secret state counts are recorded;
- missing `first_registration_attempts` is accepted only as predecessor evidence;
- no manual schema mutation is performed.

### Host readiness
- NetworkManager controls `eth0`;
- one valid product-LAN IPv4 subnet exists, surfaced only as a SHA-256 hash;
- sufficient disk space for candidate image + rollback reserve;
- systemd/Docker/Compose versions are captured;
- current activation units are healthy.

## 11. Mutation gate postconditions

A later separately authorized upgrade is PASS only if all are true:

```text
MANAGER_IMAGE=local/greenhouse-manager:fresh-e299c937a7b8
REGISTRATION_GUARD=active/loaded
TRUSTED_PRODUCT_LAN_READY=true
TCP_47110_LISTENERS=1
UDP_47111_LISTENERS=1
TCP_47112_LISTENERS=0
SCAN_FIRST_REGISTRATION_CAPABILITY=true
FIRST_REGISTRATION_DATABASE_SCHEMA_READY=true
UNRESOLVED_FIRST_REGISTRATION=0
PAIRING_WINDOW=CLOSED
BROKER_IMAGE_UNCHANGED=true
HOMEASSISTANT_IMAGE_UNCHANGED=true
MQTT_CONTINUITY=PASS
```

Only after this host closure may the original R10 board read-only preflight be rerun.

## 12. Stop conditions

STOP before mutation if any of the following is observed:
- live Manager is not the expected predecessor;
- Broker/HA image drift;
- nonzero/open 47112;
- unknown/pending pairing state;
- Manager DB integrity failure;
- unexpected existing registration TLS state;
- unexpected systemd/Compose override;
- insufficient storage;
- target candidate artifact/source mismatch;
- rollback inventory cannot be captured exactly;
- source requires a broader product-stack replacement than this gate freezes.

## 13. Next one gate

```text
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_UPGRADE_READONLY_PREFLIGHT_EXECUTOR_20261028_01
```

The next gate may add a repository-owned read-only executor and CI only.

It may access the T1 only read-only after source/CI closure.

It may not stop services, load images, install files, generate registration TLS, modify firewall/systemd/Compose, mutate SQLite, access the board, or consume the existing R10 board write authorization.
