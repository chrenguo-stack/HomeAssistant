# N3-W T1 Home Assistant mandatory-USB OTA R4 host integration source design — 2026-11-06

## 1. Gate

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_SOURCE_IMPLEMENTATION_R4_20261106_01
R4_SCOPE=HOST_INTEGRATION_PACKAGE_AND_NARROW_VALIDATED_MANAGER_TO_PRIVILEGED_UPDATER_IPC
R3_AUTHORITY=f30b7cf154abdbfed1863074ed855949aaecaf3b
R3_FINAL_DOCS_HEAD=753442ce2302d471cae833210000ac984984a9c4

LIVE_T1_ACCESS=false
REAL_USB_FORMAT=false
REAL_DOCKER_MUTATION=false
PRODUCTION_DEPLOYMENT=false
BOARD_ACCESS=false
MERGE=false
```

## 2. IPC selection

R4 freezes a local Unix domain stream socket as the Manager-to-host boundary.

Future production locator:

```text
HOST_RUNTIME_DIR=/run/n3w-t1-ota
MANAGER_SOCKET=/run/n3w/t1-ota/ha-ota.sock
HOST_SOCKET=/run/n3w-t1-ota/ha-ota.sock
TRANSPORT=AF_UNIX/SOCK_STREAM
MANAGER_MOUNT=host runtime directory read-only
PRODUCTION_MANAGER_UID=999
```

The container receives only a read-only runtime-directory view containing the socket and approved-manifest projection. It does not receive the Docker socket, block devices, root, host filesystem roots, shell access or an executable host command channel.

R4 does not modify production Compose or install a real host service. Those activation assets remain subject to later review/read-only preflight.

## 3. Request contract

```json
{"schema":"gh.n3w-t1-ha-ota-ipc-request/1","operation":"status"}
```

or:

```json
{
  "schema":"gh.n3w-t1-ha-ota-ipc-request/1",
  "operation":"submit",
  "action":"PREPARE | INSTALL",
  "target_release_id":"<validated approved-manifest release identity>"
}
```

Exact keys are mandatory. Unknown keys fail closed.

Forbidden request authority includes:

```text
device path
mount path
filesystem path
Docker image argument
Docker command
shell command
authorization ID
SSH target
credential
backup path
raw USB serial
```

STATUS remains read-only and is not sent through the mutation sink.

## 4. Host-side independent authority

The host dispatcher treats the Manager request as intent only.

Before PREPARE or INSTALL it independently resolves, through an injected privileged-side authority adapter:

- approved release identity;
- current Home Assistant image identity;
- exact target image/archive identity;
- target manifest identity;
- current durable HA-USB transaction.

PREPARE may create U0 and advance only to U1 PREPARE_REQUESTED at this IPC boundary.

INSTALL requires an existing transaction whose current/target admission record still exactly matches the independently resolved host authority; it then advances only from U4 READY_TO_INSTALL to U5 INSTALL_REQUESTED_REVALIDATING.

The IPC layer does not format media, download targets, export images, stop Home Assistant, create backups, delete images, load images or claim live authorization.

## 5. Peer boundary

The host Unix socket server requires an explicit expected peer UID and uses Linux SO_PEERCRED before dispatch.

Future production value is UID 999, matching the existing greenhouse-manager container user. Socket parent ownership and path are validated; pre-existing socket/path replacement is refused.

This supplements, rather than replaces, read-only directory mounting and exact JSON validation.

## 6. Manager integration

R4 adds opt-in settings:

```text
GH_N3W_T1_OTA_ENABLED=false by default
GH_N3W_T1_OTA_INSTALLED_VERSION
GH_N3W_T1_OTA_MANIFEST_PATH=/run/n3w/t1-ota/approved-homeassistant.json
GH_N3W_T1_OTA_SOCKET_PATH=/run/n3w/t1-ota/ha-ota.sock
```

When disabled, current production behavior is unchanged.

When enabled in a later deployment gate, greenhouse-manager builds:

- ApprovedManifestFileProvider from the fixed read-only manifest path;
- UnixSocketOtaBridge as both OtaIntentSink and OtaRuntimeStateProvider;
- the existing T1OtaManager;
- the existing single Manager MQTT client.

No second MQTT client or fourth Docker service is introduced.

## 7. State refresh

The existing Manager 5-second maintenance loop republishes the OTA surface when the OTA manager is enabled. This allows later asynchronous host progress to become visible in Home Assistant without requiring a second MQTT client or host-to-MQTT credential path.

Only public phase/progress/error projection is returned over IPC.

## 8. R4 source acceptance

```text
UNIX_SOCKET_IPC_ONLY=true
EXACT_REQUEST_KEYS=true
UNKNOWN_FIELD_FAIL_CLOSED=true
PATH_DOCKER_SHELL_INJECTION=false
HOST_INDEPENDENT_ADMISSION_RESOLUTION=true
INSTALL_ADMISSION_DRIFT_FAIL_CLOSED=true
SO_PEERCRED_UID_CHECK=true
SECOND_MANAGER_MQTT_CLIENT=false
FOURTH_DOCKER_SERVICE=false
PRODUCTION_COMPOSE_CHANGED=false
LIVE_T1_MUTATION=false
REAL_USB_FORMAT=false
REAL_DOCKER_MUTATION=false
```

R4 source/CI closure must bind both Manager-side IPC and host-side IPC source into exact-source CI.

## 9. Next boundary

After R4 source and CI close, the next gate is the already frozen R5 real-T1 read-only preflight.

```text
NEXT_ONE_GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_P5_R5_REAL_T1_READONLY_PREFLIGHT_20261106_01
R5_MUTATION=false
USB_FORMAT=false
SERVICE_STOP=false
MERGE=false
```

Real USB format/install remains separately authorized after R5.
