# N3-W Auto Safe Fallback Gate F Credential Recovery Postcheck — 2026-10-04

Status: `CREDENTIAL_RECOVERY_PASS_RUNTIME_CONNECTIVITY_FAIL_DIAGNOSIS_OPEN`

## Scope

This record freezes the Gate F paired-baseline prerequisite recovery evidence after Board B entered Gate F carrying the previously intentional KF-099 repair-wait state.

The formal T1-address-mutation portion of Gate F has not started.

## Stable identities

```text
BOARD_B_ROM_IDENTITY_SHA256=3603345fb73de6f9286dc66db9f246ff73c42382b553af63b8d5813a933b69ee
PAIRING_PROTOCOL_HARDWARE_ID_SHA256=cd90494824273fb6050c29989370690984487f7cdaea89ac4ff8b5eebc4371b0
NODE_ID_SHA256=dad9009b72b0c58a45d9041072d99eb3f1b8db9e520e1b844ff30cac2c8a0a59
```

## Setup Secret validation

Board B NVS `gh_n3w_v2/setup` was read in read-only mode. The production `PersistedSetupSecret` record was validated before use.

```text
SETUP_RECORD_BYTES=72
SETUP_MAGIC_VALID=true
SETUP_VERSION=1
SETUP_RESERVED=0
SETUP_RECORD_CHECK_VALID=true
SETUP_SECRET_BYTES=32
SETUP_SECRET_NONZERO=true
SETUP_SECRET_SHA256=9f82618077f22f64d467fe8080457b9c16cf2e9647cae6299218dba19f1f366d
SETUP_RECORD_DECODE=PASS
```

The raw Setup Secret is intentionally not stored in GitHub or chat.

## First recovery attempt and expiry

The first live repair transaction had public-safe hash:

```text
PAIRING_ID_SHA256=142d1e0c9fc035645ce38e4681add39ba3ed5b3b0d60e14a4a1dfa398ab2472e
```

`authorize-credential-recovery` was accepted and the Board consumed the authorization. Registration advanced from pairing epoch 7 to 8, but a test-script defect omitted `-i` from a `docker exec` heredoc probe. The probe falsely reported that the live pairing had not been accepted, Setup Secret import was therefore withheld, and the 120-second session expired.

Post-expiry reconciliation proved:

```text
CURRENT_PAIRING_EQUALS_AUTHORIZED=true
PAIRING_EPOCH=8
PAIRING_SESSION_STATE=expired
PAIRING_SESSION_REASON=expired
NODE_ID_PRESERVED=true
ACTIVE_GENERATION=2
PENDING_GENERATION=None
CREDENTIAL_STATE=active
```

No broker credential mutation occurred during the aborted attempt.

## Automatic pairing transaction renewal

Production firmware correctly treated terminal `expired`/`replay_detected` as a pairing-intent renewal trigger and generated a new persisted pairing transaction without manual NVS mutation.

```text
OLD_EXPIRED_PAIRING_ID_SHA256=142d1e0c9fc035645ce38e4681add39ba3ed5b3b0d60e14a4a1dfa398ab2472e
NEW_LIVE_PAIRING_ID_SHA256=470bb405ee9bca1db201be35802cfa8b0cdcbf093ddfb3d436856ece71da10ae
PAIRING_CHANGED_FROM_EXPIRED=true
PAIRING_RENEWAL_AUDIT=PASS
```

## Successful existing-identity credential recovery

The second recovery used the new live pairing transaction and the previously validated Setup Secret.

```text
PRECHECK_HARDWARE_ID_MATCH=true
PRECHECK_NEW_PAIRING_ID_MATCH=true
PRECHECK_SETUP_SECRET_MATCH=true
CREDENTIAL_RECOVERY_AUTHORIZE_RESULT=accepted
NEW_PAIRING_PENDING=true
SETUP_SECRET_IMPORT_RESULT=accepted
NEW_TRANSACTION_RECOVERY_AUTH_AND_IMPORT=PASS
```

The durable postcheck then proved:

```text
MANAGER_RUNNING=true
MANAGER_RESTART_COUNT=1
NODE_ID_PRESERVED=true
CURRENT_PAIRING_ID_SHA256=470bb405ee9bca1db201be35802cfa8b0cdcbf093ddfb3d436856ece71da10ae
CURRENT_PAIRING_IS_NEW=true
PAIRING_EPOCH=9
PAIRING_SESSION_STATE=approved
PAIRING_SESSION_REASON=operator_approved
REGISTRATION_ACTIVE=true
CREDENTIAL_NODE_MATCH=true
ACTIVE_GENERATION=3
PENDING_GENERATION=None
CREDENTIAL_STATE=active
RECOVERY_DURABLE_STATE_PASS=true
```

Therefore the existing node identity was preserved and the MQTT credential lifecycle completed generation 2 -> 3 successfully.

## Remaining runtime failure

Despite durable recovery success, the Board did not return to Manager-visible runtime telemetry in the 90-second postcheck.

```text
BOOT_SESSION_BEFORE=dc40c82e1467cf88
SEQ_BEFORE=112
SOURCE_BEFORE=direct
UPDATED_AT_BEFORE=2026-09-24T13:28:35.713Z
BOOT_SESSION_AFTER=dc40c82e1467cf88
SEQ_AFTER=112
SOURCE_AFTER=direct
UPDATED_AT_AFTER=2026-09-24T13:28:35.713Z
SEQ_ADVANCED_90S=false
BOARD_B_8883_ESTABLISHED_COUNT=0
POST_RECOVERY_TELEMETRY_PASS=false
```

This is now classified as a post-recovery runtime MQTT-connectivity problem, not a pairing or credential-lifecycle failure.

## Source boundary relevant to diagnosis

At validated exact source `b2419d17c198a85b7b50d9c1771544c2e3a0ab6b`, once the pairing client reports provisioned, `SimpleProductComponent::loop()` immediately loads persisted peer/broker state and calls `configure_mqtt_()`; `configure_mqtt_()` applies broker host, broker port, username, password, client ID, TLS server name, and CA, then enables MQTT. A Board reboot is not a required normal step after successful pairing.

Manager configuration keeps pairing discovery advertisement and node Broker address as separate settings:

```text
GH_N3W_PAIRING_ADVERTISED_HOST
GH_N3W_NODE_BROKER_HOST
GH_N3W_NODE_BROKER_PORT
GH_N3W_NODE_BROKER_TLS_SERVER_NAME
```

Therefore the next read-only diagnosis must verify the actual node Broker host/TLS configuration currently present in the running Manager and compare it with Board/T1 current LAN reachability and Board MQTT/TLS logs.

## Current disposition

```text
CREDENTIAL_RECOVERY=PASS
NODE_ID_PRESERVATION=PASS
CREDENTIAL_GENERATION_ROTATION=PASS
POST_RECOVERY_MQTT_8883=FAIL
POST_RECOVERY_TELEMETRY=FAIL
GATE_F_PAIRED_HEALTHY_BASELINE=FAIL
T1_ADDRESS_MUTATION_NOT_STARTED=true
GATE_F_PHYSICAL_ACCEPTANCE_COMPLETE=false
MERGE=false
```

## Next boundary

Read-only only:

1. inspect running Manager non-secret environment for node Broker host/port/TLS server name and pairing advertised-host mode;
2. capture Board B serial MQTT/TLS diagnostics without changing Flash/NVS;
3. do not start the formal T1 address-change experiment until Board B has a healthy Direct MQTT/telemetry baseline.
