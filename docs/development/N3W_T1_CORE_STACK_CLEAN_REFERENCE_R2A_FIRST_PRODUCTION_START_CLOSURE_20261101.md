# N3-W T1 Core Stack Clean Reference — R2A first production start closure

Date: 2026-11-01

## 0. Closure

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R2A_PRODUCTION_ACTIVATION_START_20261101_01
RESULT=CLOSED_PASS

PRODUCT_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
R2A_CONTROL_HEAD=abeb6c31147bcf249361dcec7e9536eaed6106a6

CI_RUN=41307906081
CI_RESULT=SUCCESS
SOURCE_TEST_COUNT=12

R2A_ARTIFACT_ID=13084461803
R2A_ARTIFACT_DIGEST=sha256:f6acacb0ed92defe4b46a34c27c12c13fe2f4c27cb85f81b88a6fb4d1d728bc0
PACKAGE_MANIFEST_SHA256=a0bb9977314a7e4a3f9d051004c0bdcfe0410f2780f185d8aa68500d8919a76b

R2A_APPLY_RC=0
R2A_POSTCHECK_RC=0
R2A_FINAL=PASS
R2B_REBOOT_EXECUTED=false
```

## 1. Exact package authority

The R2A control package was independently bound before T1 mutation.

```text
ARTIFACT_AUTHORITY=PASS
LOCAL_EXACT_PACKAGE=PASS
REMOTE_EXACT_PACKAGE=PASS
FILE_COUNT=8
PRODUCT_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
CONTROL_PLANE_HEAD=abeb6c31147bcf249361dcec7e9536eaed6106a6
PACKAGE_MANIFEST_SHA256=a0bb9977314a7e4a3f9d051004c0bdcfe0410f2780f185d8aa68500d8919a76b
```

The first attempted transfer used macOS `scp .../.` and stopped before R2A apply with:

```text
scp: error: unexpected filename: .
```

That attempt created only an empty transport directory. The retry proved the directory was empty and
removed only that transport residue. Product mutation and production service start were false.

The accepted transfer used a tar stream over the existing SSH ControlMaster session.

## 2. R1 stopped-state preflight

Immediately before authorization claim:

```text
R1_PREFLIGHT=PASS
IMAGE_COUNT=3
CONTAINER_COUNT=0
VOLUME_COUNT=0
PRODUCT_LISTENER_COUNT=0
STAGED_UNITS_ENABLED=true
STAGED_UNITS_ACTIVE=false
T1_MUTATION=false
PRODUCTION_SERVICE_START=false
```

## 3. One-shot R2A activation

Authorization:

`N3W_T1_CORE_STACK_CLEAN_REFERENCE_R2A_PRODUCTION_ACTIVATION_START_20261101_01`

Final transaction state:

```text
TRANSACTION_STAGE=RUNTIME_STARTED
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
AUTHORIZATION_REPLAY_ALLOWED=false
PRODUCTION_SERVICE_START=true
PERSISTENCE_ENABLED=true
CERTIFICATE_TIMER_ENABLED=true
PRE_REBOOT_READY=true
```

No replay of the R2A authorization is allowed.

## 4. First production start acceptance

The R2A executor returned PASS with:

```text
BROKER_READY=true
RUNTIME_SERVICES=broker,homeassistant,manager
PRODUCTION_SERVICE_START=true
PERSISTENCE_ENABLED=true
CERTIFICATE_TIMER_ENABLED=true
CERTIFICATE_TIMER_ACTIVE_BEFORE_REBOOT=false
PRE_REBOOT_READY=true
BOARD_ACCESS=false
```

Independent read-only postcheck:

```text
STATUS=PASS
RUNNING_CONTAINER_COUNT=3
CONTAINER_STABILITY_SECONDS=30

BROKER_AUTHENTICATED_READINESS=true
BROKER_PORT_BINDING_EXACT=true

HOMEASSISTANT_HTTP_READY=true
HOMEASSISTANT_HTTP_STATUS=401

PRODUCTION_UNITS_ENABLED=true
PRODUCTION_UNITS_ACTIVE=true

CERTIFICATE_TIMER_ENABLED=true
CERTIFICATE_TIMER_ACTIVE_BEFORE_REBOOT=false

SAME_BOOT_AS_R2A_START=true
REBOOT_EXECUTED=false
```

Observed stable containers:

- Broker: `927aea04a062caf57c8d75d73ba8902f35eef035214e85ce7e8b1c066903d963`, restart count 0.
- Home Assistant: `26b095e1ba8aa3a009f02a2460234eae45764debf61d878b965761ce75212676`, restart count 0.
- Manager: `6b16cc967685bdf499aa3eeb59f116216e85150297cf3948364c090f847c5de3`, restart count 0.

Docker network set:

```text
bridge
host
none
n3wfc4-private
n3wfc4-services
```

The HA `/api/` readiness response of HTTP 401 is accepted because it proves the HTTP service is
listening and enforcing authentication.

## 5. R2A boot boundary

R2A boot ID before activation:

`8e649419-3243-4e23-973d-b53f2a626b82`

The postcheck proved the same boot remained active through the stability window.

```text
UNEXPECTED_REBOOT=false
R2B_REBOOT_EXECUTED=false
```

## 6. Next gate

R2A is CLOSED_PASS.

R2B is the controlled reboot and post-reboot persistence acceptance. It must prove that the enabled
production units restore the three-service runtime after a real host reboot, without board access
and without using the R2A one-shot authorization again.

```text
R2A=CLOSED_PASS
R2B=AUTHORIZED_NOT_EXECUTED
R3=NOT_EXECUTED
BOARD_ACCESS=false
MERGE=false
```
