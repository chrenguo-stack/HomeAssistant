# N3-W T1 explicit per-device provisioning read-only preauth closure
# 2026-10-15

## 0. Result

```text
TASK=N3W_T1_EXPLICIT_PER_DEVICE_PROVISIONING_READONLY_PREAUTH_20261015_01
RESULT=CLOSED_PASS

DEPLOYED_RELEASE_SOURCE_HEAD=6ac82ae0872b05644e59470ffef7307dad14d359
PROVISION_COMMAND_PRESENT=PASS
PROVISIONING_STATE=UNPROVISIONED
PROVISIONING_STATUS=PASS

INSTANCE_MATERIAL_ABSENT=true
EXPLICIT_PROVISIONING_REQUIRED=true

TRANSACTION_JSON=ABSENT
FIRSTBOOT_COMPLETE_JSON=ABSENT

BROKER_INGRESS_GUARD_ENABLED=true
PROVISION_RESUME_ENABLED=true
BROKER_ACTIVATION_UNIT=NOT_FOUND_IN_STAGED_BOUNDARY
SERVICES_ACTIVATION_UNIT=NOT_FOUND_IN_STAGED_BOUNDARY
CERTIFICATE_LIFECYCLE_TIMER=NOT_FOUND_IN_STAGED_BOUNDARY

BROKER_ACTIVATION_ACTIVE=false
SERVICES_ACTIVATION_ACTIVE=false
CERTIFICATE_LIFECYCLE_TIMER_ACTIVE=false

T1_MUTATION=false
PROVISIONING_START_EXECUTED=false
PRODUCT_IDENTITY_CREATED=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
```

## 1. Interpretation

The target remains at the exact post-R4 public-staging boundary. The installed provisioning CLI reports
`UNPROVISIONED`, and both durable provisioning records are absent.

The activation units reporting `not-found` are expected at this stage: the fresh public-staging source explicitly
keeps the Broker activation, services activation, and certificate lifecycle unit files absent until the later
activation package. This is therefore not a preauth blocker.

The only enabled staged units are the Broker ingress guard and the provisioning resume/verify helper.

## 2. Stop point

```text
CURRENT_STOP_POINT=AFTER_READONLY_PREAUTH_BEFORE_EXPLICIT_PROVISIONING_START
NEXT_ONE_GATE=N3W_T1_EXPLICIT_PER_DEVICE_PROVISIONING_LIVE_START_20261015_01
LIVE_MUTATION_AUTHORIZATION_REQUIRED=true
AUTO_EXECUTE_NEXT_GATE=false
```

The next Gate may create the durable provisioning transaction, per-device product identity, CA/TLS/MQTT
credentials, DynSec state, and empty instance state. Provisioning completion must still leave production services
stopped and must not enter F4 activation.
