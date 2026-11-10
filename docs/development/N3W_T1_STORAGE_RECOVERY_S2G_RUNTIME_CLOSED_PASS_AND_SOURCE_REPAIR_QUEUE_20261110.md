# N3-W T1 storage recovery S2G runtime CLOSED_PASS and source-repair queue — 2026-11-10

## 1. Closure

```text
RESULT=CLOSED_PASS_RUNTIME_RECOVERY
PR=800
PRE_ALIGNMENT_HEAD=961eb4b7ee4c08be2e7246c3949835f53659edab

T1_BROKER_MANAGER_HA_RUNTIME_RECOVERY=CLOSED_PASS

BROKER_RUNNING=true
MANAGER_RUNNING=true
HOMEASSISTANT_RUNNING=true

MANAGER_MQTT_SOCKET_COUNT_8883=1
HOMEASSISTANT_MQTT_SOCKET_COUNT_1883=1
HOMEASSISTANT_BROKER_CURRENT_AUTHENTICATED=true
HOMEASSISTANT_HTTP_STATUS=401

LAST_PROVEN_ROOT_FREE_BYTES=592859136
LAST_PROVEN_ROOT_FREE_MIB_APPROX=565.39

PREPARE_REPLAY=false
CONFIRM_USB_ERASE=false
USB_MUTATION=false
U2_PLUS=false
BOARD_ACCESS=false
MERGE=false
```

This closes the emergency T1 runtime-recovery sequence that began after the root filesystem reached ENOSPC during KF-147 Manager V3 staging. The primary outage root cause is proven as root-filesystem ENOSPC. Broker persistence failed first; the application stack then stopped. The later Docker/Compose control-plane versus real containerd-task divergence is separately proven, but ENOSPC as its direct causal mechanism remains unproven.

The final recovery did not require Docker daemon restart, containerd restart, container recreation, broad prune, image deletion, USB mutation, U2+, KF-147 live apply or merge.

## 2. Storage recovery and exact runtime reconciliation

S1 deleted only exact historical Manager images already classified as unused and the failed KF-147 staging residue. Broad prune remained forbidden. The cleanup recovered about 562 MiB, sufficient for emergency recovery but not a healthy long-term OTA/update headroom policy.

S2/S2A proved that systemd/Compose could report Broker `Running` while no real Broker process/containerd task existed. Exact `docker start` of the existing Broker container reconciled the runtime without recreation.

S2D reproduced the same false-running class for Manager and Home Assistant: application systemd/Compose owner active, but Manager/HA had no real containerd tasks and no application listeners.

S2E then performed only exact starts of the already-existing Manager and Home Assistant containers. Their identities/config hashes remained unchanged, all three containerd tasks appeared, and the listener contract recovered.

## 3. S2F/S2G Home Assistant MQTT classification

S2F stopped on `homeassistant_mqtt_current_authentication_missing`. That STOP did not prove a product outage.

S2G read-only classification proved:

```text
IDENTITY_MATCH=true
MANAGER_MQTT_SOCKET_COUNT_8883=1
HOMEASSISTANT_MQTT_SOCKET_COUNT_1883=1
HOMEASSISTANT_BROKER_CURRENT_AUTHENTICATED=true
HOMEASSISTANT_HTTP_STATUS=401
CLASSIFICATION=HA_MQTT_CURRENT_AUTHENTICATED
```

The Broker event sequence also proved that the authenticated-readiness helper can steal the live Home Assistant session when invoked after HA is already running:

```text
HA_NORMAL_SESSION_KEEPALIVE=60
READINESS_SHORT_SESSION_KEEPALIVE=10
BROKER_EVENT=disconnected: session taken over
```

Source review shows `tools/n3w_t1_broker_authenticated_readiness.py` reads the production Home Assistant metadata and sends CONNECT with the production HA `client_id`. That behavior is valid as a pre-application startup credential probe, because HA is not yet running. It is not safe as a runtime health probe after HA is live.

Do not repair this by simply inventing a second client ID: the current DynSec service-identity contract binds service credentials to the required unique client ID. The repair direction is to preserve startup-probe semantics and remove runtime/post-start misuse.

## 4. Deployed Core Updater asset gap

S2E final strict verification attempted:

```text
/opt/HomeAssistant/tools/n3w_t1_core_updater.py
```

The file is absent on the deployed T1.

This is an independently proven deployed-asset integrity gap, not evidence that the currently running Broker/Manager/HA stack is unhealthy. The exact packaging/install root cause is not yet proven and must be classified in source/deployment review before any repair.

## 5. Image lifecycle / storage headroom

The frozen image lifecycle policy remains in force:

- T1 internal Docker storage is runtime storage, not a long-term release archive.
- steady-state target is one accepted generation per component;
- Manager/Broker predecessor retention lasts only through independent acceptance;
- Home Assistant recovery assets follow the mandatory-USB transaction lifecycle;
- broad Docker prune remains forbidden;
- final cleanup must use exact component/generation authority.

Current root free space is emergency headroom only. KF-147 live retry stays blocked until long-term headroom and exact image-lifecycle closure are complete.

## 6. KF-147 disposition

The prior KF-147 Manager V3 package/binding cannot be replayed after the storage incident and the capacity-source repair. The next live attempt requires:

```text
fresh rebind
-> fresh capacity gate
-> new package/manifest binding
-> live retry
```

The old live authorization/package must not be treated as reusable authority.

## 7. Next source queue

The user froze the following order for the next conversation:

```text
NEXT_1=BROKER_READINESS_RUNTIME_SESSION_TAKEOVER_SOURCE_REPAIR_DESIGN
NEXT_2=CORE_UPDATER_DEPLOYED_ASSET_INTEGRITY_REPAIR
NEXT_3=T1_STORAGE_HEADROOM_AND_IMAGE_LIFECYCLE_CLOSURE

THEN=
KF147 fresh rebind
-> fresh capacity gate
-> new package/manifest binding
-> live retry
```

Only NEXT_1 is the next-one-gate in the formal handoff. NEXT_2/NEXT_3 are queued and must not be auto-entered before NEXT_1 closure.

## 8. GitHub evidence anchors

The PR #800 conversation contains the detailed gate-by-gate evidence. Important late-stage comments include:

```text
S2G_SOURCE_REVIEW_REFINEMENT_COMMENT=6754315038
S2G_RUNTIME_CLOSED_PASS_COMMENT=6754582192
S2G_FINAL_SOURCE_ROOT_CAUSE_REFINEMENT_COMMENT=6754597413
```

No private SSH locator, host key, password, raw device identity or private target address is included in this public closure document.
