# N3-W T1 Broker Certificate Lifecycle Runtime Baseline — 2026-09-29

Status: `READ_ONLY_RUNTIME_BASELINE_ARCHIVED`  
Scope: production T1 Broker/Manager certificate inventory and expiry evidence  
Repository baseline: `main=60c05ada52c48a58243f666b3e631fd228c53df4`  
Repair branch: `fix/n3w-t1-broker-certificate-lifecycle-20260929`

This document archives public-safe evidence collected by read-only inspection of the current production T1. It does not authorize or record a live certificate mutation. Raw private host paths, private network locators, private key material, credential bodies, and system-private identifiers are intentionally omitted.

## 1. Current runtime authority

Read-only Docker inspection established:

```text
MANAGER_CONTAINER=greenhouse-manager
MANAGER_RUNNING=true

BROKER_COMPOSE_PROJECT=n3wfc4
BROKER_COMPOSE_SERVICE=broker
BROKER_RUNNING=true
BROKER_HOST_TCP_8883_PUBLICATION=0.0.0.0:8883
```

The active Broker configuration binds one TLS listener on TCP/8883 and references the in-container logical paths:

```text
cafile=/mosquitto/tls/ca.pem
certfile=/mosquitto/tls/server.pem
keyfile=/mosquitto/tls/server.key
```

Docker mount inspection proved that those active paths are backed by the production Broker TLS material and are mounted read-only into the Broker.

The current Manager mounts the same Broker CA as a read-only secret for its MQTT TLS client path. The Manager N3-W runtime directory also contains the node-facing CA copy used for node credential materialization.

## 2. Production Broker server certificate

Read-only OpenSSL inspection and chain verification established:

```text
BROKER_SERVER_CERT_PRESENT=true
BROKER_SERVER_CERT_PARSEABLE=true
BROKER_SERVER_CERT_CHAIN_VERIFY=PASS
BROKER_SERVER_CERT_SAN_MATCHES_CURRENT_TLS_NAME=true

BROKER_SERVER_CERT_NOT_BEFORE=2026-08-20T04:18:40Z
BROKER_SERVER_CERT_NOT_AFTER=2028-11-22T04:18:40Z
BROKER_SERVER_CERT_VALIDITY_DAYS=825

BROKER_SERVER_CERT_FILE_SHA256=299a4cbece174692ecc9d82b92f1a98699847fece79543c8f8e565c04a07e917
BROKER_SERVER_CERT_SHA256_FINGERPRINT=8272aa061d70bf0b5ed41a94a1b6fdc5065bd6b51f6751aa7b7a2059803d74cb
```

This is the earliest confirmed production X.509 certificate expiry in the current system.

## 3. FC4 private CA

The Broker CA and the Manager/node CA copies were inspected independently.

The production Broker CA and the active Manager N3-W `node-ca.pem` copy are byte-identical:

```text
BROKER_CA_EQUALS_ACTIVE_MANAGER_NODE_CA=true

FC4_PRIVATE_CA_NOT_BEFORE=2026-08-20T04:18:39Z
FC4_PRIVATE_CA_NOT_AFTER=2036-08-17T04:18:39Z
FC4_PRIVATE_CA_VALIDITY_DAYS=3650

FC4_PRIVATE_CA_FILE_SHA256=11ff133cdab8bf5f3093f6b488f8fa7e2579a1b5e383d066b1a1da56ad5dae9f
FC4_PRIVATE_CA_SHA256_FINGERPRINT=b305f61656a0e795bc5dcc5388ba63bc77d824dc3329cf07b744ad9c91c66351
```

A second historical manager-side copy under the FC4 persistent tree also matched the same SHA-256. These are copies of one logical CA, not separate certificate authorities.

Current online TLS dependence:

```text
BROKER_DEPENDS_ON_FC4_PRIVATE_CA=true
MANAGER_MQTT_TLS_DEPENDS_ON_FC4_PRIVATE_CA=true
NODE_TRUST_MATERIAL_USES_SAME_FC4_PRIVATE_CA=true
```

## 4. Greenhouse System CA

A distinct H0/H1 system identity CA is present in the persistent identity/backup material:

```text
SYSTEM_CA_PRESENT=true
SYSTEM_CA_DISTINCT_FROM_FC4_PRIVATE_CA=true

SYSTEM_CA_NOT_BEFORE=2026-08-02T15:32:24Z
SYSTEM_CA_NOT_AFTER=2036-07-30T15:32:24Z
SYSTEM_CA_VALIDITY_DAYS=3650

SYSTEM_CA_FILE_SHA256=bdf15c4170393885237a7408a490724fa18997de565fd24a501b7268357771d1
SYSTEM_CA_SHA256_FINGERPRINT=745c29f156b35cdb222bb7150aa814ff4aa0c57f20c9bd23af9ee3b51e23ddf7
```

Read-only scan found multiple backup/test/cutover copies of this same certificate. All sampled copies were byte-identical to the persistent System CA.

Current running-container mount inventory showed no direct `system-ca.pem` mount into the active Manager, Broker, or Home Assistant containers. Therefore:

```text
SYSTEM_CA_CURRENT_ONLINE_BROKER_TLS_DEPENDENCY=false
SYSTEM_CA_CURRENT_MANAGER_MQTT_TLS_DEPENDENCY=false
SYSTEM_CA_CURRENT_HA_TLS_DEPENDENCY=false
SYSTEM_CA_BACKUP_RECOVERY_IDENTITY_ROLE=true
```

This conclusion is limited to the inspected current runtime mounts and source/runtime authority; it does not classify the System CA as disposable.

## 5. Other certificate inventory

A bounded scan of greenhouse-owned persistent/runtime roots plus the Manager's active N3-W bind source found no fourth independent production X.509 certificate.

No current running-container mount or current product-source search established any of the following as production certificate authorities:

```text
NODE_CLIENT_X509_CERTIFICATE=NOT_FOUND
MANAGER_CLIENT_X509_CERTIFICATE=NOT_FOUND
HOME_ASSISTANT_CLIENT_X509_CERTIFICATE=NOT_FOUND
LETS_ENCRYPT_CERTIFICATE=NOT_FOUND
CERTBOT_MANAGED_CERTIFICATE=NOT_FOUND
SECOND_BROKER_SERVER_CERTIFICATE=NOT_FOUND
```

MQTT Dynamic Security passwords, N3-W application keys, SYSTEM_PEER_KEY material, pairing ephemeral keys, and other symmetric/ephemeral credentials are separate lifecycle domains and are not X.509 certificate expiry objects.

## 6. Source-level lifecycle gap

Default-branch source inspection at the baseline SHA found:

- the H0/H1 `system-ca.pem` generator gives that CA a 3650-day validity;
- current node credential material carries a CA PEM trust anchor rather than a per-node client certificate;
- Manager MQTT TLS validates the Broker through a configured CA file;
- no current source implementation of Broker server-certificate automatic renewal was found;
- no current source implementation of X.509 expiry warning/threshold monitoring was found;
- no Certbot or Let's Encrypt integration was found.

This baseline therefore classifies the current issue as a lifecycle completeness gap, not an active certificate failure:

```text
CURRENT_TLS_RUNTIME=HEALTHY
CURRENT_CERTIFICATE_EXPIRY_INCIDENT=false
BROKER_SERVER_CERTIFICATE_RENEWAL_AUTOMATION=NOT_IMPLEMENTED
CERTIFICATE_EXPIRY_ALERTING=NOT_IMPLEMENTED
CA_ROLLOVER_AUTOMATION=NOT_IMPLEMENTED

REPAIR_REQUIRED=true
LIVE_MUTATION_REQUIRED_FOR_SOURCE_REPAIR=false
```

## 7. Repair boundary

The repair design must preserve the already-accepted runtime/security boundaries:

- do not replace the active FC4 private CA as part of ordinary Broker server-certificate renewal;
- do not require node re-pairing for ordinary server-certificate renewal;
- do not weaken TLS hostname verification;
- do not broaden Broker TCP/8883 publication or firewall authority;
- do not expose private CA keys, certificate bodies, MQTT credentials, private host paths, or private network locators in public evidence;
- source/host tests must be completed before any future live certificate rotation is considered;
- CA rollover is a separate long-horizon trust-migration problem and must not be silently conflated with server-certificate renewal.

## 8. Current disposition

```text
RUNTIME_CERTIFICATE_INVENTORY=PASS
BROKER_SERVER_CERTIFICATE_EXPIRY=2028-11-22T04:18:40Z
FC4_PRIVATE_CA_EXPIRY=2036-08-17T04:18:39Z
SYSTEM_CA_EXPIRY=2036-07-30T15:32:24Z

EARLIEST_CONFIRMED_PRODUCTION_X509_EXPIRY=BROKER_SERVER_CERTIFICATE
IMMEDIATE_EXPIRY_EMERGENCY=false
SOURCE_LIFECYCLE_GAP=true

NEXT_ONE_GATE=N3W_T1_BROKER_CERTIFICATE_LIFECYCLE_REPAIR_DESIGN_20260929_01
```
