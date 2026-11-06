# N3-W T1 Core Stack OTA product architecture V1.0 — 2026-11-06

## 1. Purpose

This document defines the product-level OTA architecture for the complete N3-W T1 core software stack.

The public/product concept is:

```text
T1_Core_Stack OTA
```

The privileged execution engine remains:

```text
T1_Core_Updater
```

The relationship is intentionally hierarchical:

```text
T1_Core_Stack OTA
= product OTA system / release orchestration / user experience

T1_Core_Updater
= privileged local execution engine
```

This design does not rename or retire the existing updater implementation. Existing Generic V2 Manager upgrade evidence and the mandatory-USB Home Assistant successor work remain reusable execution primitives.

## 2. Status and boundaries

```text
DOCUMENT_STATUS=ARCHITECTURE_DESIGN
EXECUTABLE_SOURCE_MUTATION=false
LIVE_T1_MUTATION=false
PRODUCTION_COMPOSE_MUTATION=false
REAL_USB_MUTATION=false
REAL_DOCKER_MUTATION=false
BOARD_ACCESS=false
MERGE=false

CURRENT_R4_EXECUTABLE_AUTHORITY=
506136a8f1fc42bb8788f8a3c0fae9220d689af4

CURRENT_R4_SCOPE_UNCHANGED=true
R4_SCOPE_EXPANSION=false
```

This document is a successor architecture authority only. It must not be interpreted as permission to activate stack OTA on the real T1 or to expand the current Home Assistant R4 gate.

## 3. Product goal

The delivered product must allow a normal user to update the complete T1 core stack without requiring knowledge of:

- SSH;
- SCP;
- Docker;
- GitHub Actions;
- artifact IDs;
- image tar files;
- MQTT internals;
- filesystem or block-device paths.

The user-facing model is one system update surface:

```text
T1 Core Stack
current stack release -> approved newer stack release
PREPARE
READY_TO_INSTALL
INSTALL
SUCCESS / ROLLED_BACK / ACTION_REQUIRED
```

The user may optionally see component detail, but does not manage component dependencies manually.

## 4. Components in the core stack

The product core stack consists of exactly these three software components:

```text
MANAGER=greenhouse-manager
BROKER=Mosquitto
HOMEASSISTANT=Home Assistant
```

A stack release may change one, two, or all three components.

A component marked unchanged is not reinstalled merely because a new stack release exists.

## 5. Architecture layers

### 5.1 User/control plane

Owner:

```text
greenhouse-manager + Home Assistant
```

Responsibilities:

- display current and available stack release;
- publish the user-facing update entity/state;
- expose bounded PREPARE and INSTALL intents;
- show public progress and bounded failure status;
- never receive Docker socket access, block-device access, root, arbitrary shell, or host-path authority.

The Manager remains a control-plane process. It does not become the privileged updater.

### 5.2 T1 Core Stack OTA orchestrator

`T1_Core_Stack OTA` is the logical host-side product orchestration layer.

Responsibilities:

- check the approved release source;
- verify release metadata and signature;
- resolve the current local stack release;
- determine which components actually require change;
- determine whether removable USB is required;
- download/stage approved packages;
- maintain the durable stack-level transaction;
- coordinate component execution;
- perform stack-level acceptance;
- choose the locally allowed rollback route.

The physical implementation may share a host package/process with updater code, but the logical authority boundary must remain explicit. No fourth Docker service is required by this design.

### 5.3 Privileged execution engine

`T1_Core_Updater` remains the sole privileged execution engine.

Responsibilities include bounded execution primitives such as:

- inspect;
- plan;
- apply;
- rollback;
- status;
- exact image/archive verification;
- service stop/start;
- Docker image load and binding;
- host-side USB/media operations;
- Home Assistant data backup/restore;
- durable component transaction handling.

It does not trust user/MQTT supplied device paths, Docker arguments, shell commands, mount paths or backup paths.

### 5.4 Component strategies

```text
Manager:
  Generic V2 successor strategy

Broker:
  Generic V2 successor strategy

Home Assistant:
  mandatory-USB successor strategy
```

The common product UX does not require identical component execution algorithms.

## 6. Product naming decision

```text
PUBLIC_PRODUCT_CONCEPT=T1_Core_Stack_OTA
PRIVILEGED_ENGINE=T1_Core_Updater

T1_CORE_STACK_OTA_REPLACES_T1_CORE_UPDATER=false
T1_CORE_STACK_OTA_SUPERSEDES_UPDATER_AS_PRODUCT_CONCEPT=true
T1_CORE_UPDATER_REMAINS_PRIVILEGED_ENGINE=true
```

Existing source filenames, schemas and CI containing `T1_Core_Updater` are not renamed merely for terminology consistency.

## 7. Release source

### 7.1 Development/factory source

GitHub Actions artifacts remain valid for:

- CI;
- source closure;
- factory validation;
- exact artifact evidence;
- engineering recovery.

They are not the long-term end-user OTA distribution contract.

### 7.2 Product release source

The final end-user OTA source must be a stable HTTPS release service exposing:

1. a signed release index or channel manifest;
2. a signed T1 Core Stack release manifest;
3. exact component packages referenced by that manifest.

Conceptually:

```text
HTTPS release index
  -> signed T1 Core Stack manifest
      -> Manager package
      -> Broker package
      -> Home Assistant package
```

HTTPS transport security is necessary but is not sufficient authority. Release authenticity must also be established cryptographically.

### 7.3 Release signing

The device must verify a signed release manifest against a locally trusted release-signing key or keyring.

Key rotation must be an explicit product contract. A remotely supplied key may not silently replace the local trust root.

Unsigned or incorrectly signed releases fail closed before package preparation.

## 8. Stack release manifest

A stack release manifest is the top-level product release authority.

It must identify at least:

```text
schema
stack_release_id
stack_version
release_channel
published_at
minimum_supported_updater_version
component set
compatibility contract
package identities
package digests
package sizes
signature metadata
```

Each component entry binds exact identity. Conceptual fields include:

```text
component
changed / unchanged
component_release_id
display_version
target image ref
target platform
component target manifest identity
archive SHA256
archive size
predecessor compatibility
rollback compatibility
```

The remote manifest may describe dependencies and compatibility, but it must not become an arbitrary command program. Local code decides the allowed execution sequence.

## 9. Current-stack identity

The device must maintain a local accepted stack authority that can answer:

```text
What stack release is installed?
Which Manager image is accepted?
Which Broker image is accepted?
Which Home Assistant image is accepted?
What component transaction schemas are current?
Is recovery required?
```

The existing:

```text
infra/n3w-t1/production/t1-core-stack-current.json
```

is the current repository-side authority precedent.

Future product runtime identity may use a durable host-side projection derived from the accepted release and completed transactions. Repository files alone must not be treated as live runtime proof.

## 10. Update discovery

The product must support:

- automatic bounded update checks;
- user-requested manual check;
- no update result;
- update available result;
- source unavailable result;
- signature/manifest rejection result.

The exact automatic polling cadence is not frozen by this document.

A failed update check does not interrupt the currently running stack.

## 11. User-facing update model

Normal Home Assistant UI should expose one stack-level product update surface:

```text
T1 Core Stack
Installed: <stack version>
Latest approved: <stack version>
State: up to date / update available / preparing / ready / installing / complete / failed
```

Component versions may be shown as details:

```text
Manager
Broker
Home Assistant
```

but the user does not manually select dependency order.

The existing R3/R4 Home Assistant-specific Update entity is a reusable control-plane primitive. A later Stack OTA successor may supersede the user-facing HA-only surface without invalidating its bounded PREPARE / INSTALL / STATUS design.

## 12. USB rule

USB requirement is release-content dependent.

```text
Manager-only release -> USB not required
Broker-only release -> USB not required
Manager+Broker release -> USB not required
Any release containing Home Assistant image update -> mandatory USB
```

For Home Assistant updates, all existing mandatory-USB rules remain authoritative, including:

- measured usable capacity >= 14 GiB;
- market recommendation 16GB or larger;
- label `N3W-UPDATE`;
- target preparation on USB while current HA keeps running;
- predecessor image recovery material;
- pre-upgrade HA data backup;
- destructive boundary only after READY_TO_INSTALL;
- rollback requires both image and HA data restore;
- same filesystem UUID continuity after the destructive boundary.

Stack OTA does not weaken these rules.

## 13. Prepare flow

Conceptual flow:

```text
IDLE
-> UPDATE_AVAILABLE
-> PREPARE_REQUESTED
-> RELEASE_AUTHORITY_VERIFIED
-> REQUIRED_MEDIA_ADMITTED
-> PACKAGES_DOWNLOADING
-> PACKAGES_VERIFIED
-> ROLLBACK_MATERIAL_READY
-> READY_TO_INSTALL
```

PREPARE must not itself perform the destructive component cutover.

Manager/Broker packages may be staged on host storage subject to capacity policy.

Home Assistant target/recovery/data material follows the mandatory-USB storage contract.

## 14. Install flow

INSTALL is accepted only for the exact release identity that reached READY_TO_INSTALL.

Conceptual flow:

```text
READY_TO_INSTALL
-> INSTALL_REQUESTED
-> PRE_INSTALL_REVALIDATION
-> COMPONENT_EXECUTION
-> COMPONENT_ACCEPTANCE
-> STACK_ACCEPTANCE
-> COMMITTED
```

If admission identity changes between READY and INSTALL, installation fails closed and requires a new preparation cycle.

## 15. Component execution rules

### 15.1 Manager

The already validated Generic V2 Manager A-to-B path remains the execution basis.

Required properties remain:

- exact target manifest;
- exact predecessor binding;
- exact ARM64 archive;
- SHA256 verification;
- persistent-state continuity;
- Manager acceptance;
- rollback compatibility.

End-user Stack OTA adds discovery/download/orchestration in front of this engine; it does not rewrite the proven Manager switching primitive.

### 15.2 Broker

Broker is added as a first-class Generic V2 successor component.

Broker acceptance must prove at least:

- expected Broker image identity;
- TLS listener contract;
- Manager authenticated connection;
- Home Assistant authenticated connection;
- DynSec continuity;
- ACL/credential continuity;
- expected retained/persistent state continuity;
- telemetry path recovers;
- no unauthorized listener expansion.

The exact Broker source implementation remains a later gate.

### 15.3 Home Assistant

Home Assistant keeps the mandatory-USB transaction already being implemented.

Stack OTA invokes that strategy as a component adapter. It does not replace it with the simpler Generic V2 image-only path.

## 16. Multi-component execution order

A stack release may update multiple components, but components must not be destructively replaced as one unobservable batch.

The orchestrator executes one bounded component stage at a time and records durable acceptance before advancing.

The exact final order is not frozen globally in this architecture document because compatibility may vary by release.

However:

- remote manifests cannot inject arbitrary execution order;
- local policy must permit the proposed dependency path;
- each component must reach its required acceptance point before the next destructive component stage;
- a release must not be reported COMMITTED until stack-level acceptance succeeds.

## 17. Stack transaction

Stack OTA adds a durable transaction above component transactions.

Conceptual stack phases:

```text
S0 CURRENT
S1 UPDATE_AVAILABLE
S2 PREPARE_REQUESTED
S3 RELEASE_VERIFIED
S4 MEDIA_AND_CAPACITY_ADMITTED
S5 PACKAGES_PREPARED
S6 READY_TO_INSTALL
S7 INSTALL_REQUESTED
S8 COMPONENTS_EXECUTING
S9 STACK_ACCEPTANCE
S10 COMMITTED
S11 ROLLBACK_IN_PROGRESS
S12 ROLLED_BACK
S13 RECOVERY_REQUIRED
```

Component transactions retain their own detailed phases, including the Home Assistant U0-U13 transaction.

The stack transaction references component transaction identities instead of duplicating their internal state machines.

## 18. Rollback semantics

For the first production Stack OTA version, a multi-component release should be treated as one compatible release unit.

If a later component fails after an earlier component has already passed, the default requirement is:

```text
restore the previous accepted stack release
```

unless a later explicitly reviewed policy proves a safe partial-release state.

Therefore a multi-component release must prepare sufficient rollback material before the first irreversible cutover.

A mixed-version state caused by failure may exist temporarily during recovery, but it cannot be declared COMMITTED merely because some components are healthy.

## 19. Power-loss semantics

The stack transaction and each component transaction must be durable.

After reboot/power loss, the system must classify the transaction deterministically into one of:

- safe resume;
- safe rollback;
- already committed;
- already rolled back;
- recovery required.

A normal boot must not silently start a new update transaction.

## 20. IPC and privilege boundary

The R4 local Unix-socket design remains a valid precedent.

Manager-to-host requests must remain bounded intent, for example:

```json
{
  "operation": "submit",
  "action": "PREPARE",
  "target_release_id": "stack-release-id"
}
```

or:

```json
{
  "operation": "submit",
  "action": "INSTALL",
  "target_release_id": "stack-release-id"
}
```

Forbidden Manager authority includes:

```text
device path
mount path
filesystem path
Docker image argument
Docker command
shell command
authorization ID
credential
backup path
USB serial used as direct authority
```

The host side independently resolves all privileged resources.

## 21. Network boundary

The privileged execution engine should not accept arbitrary remote URLs from MQTT or Home Assistant.

The Stack OTA orchestrator resolves only the configured product release service and exact release identities allowed by local policy.

Package URLs, if present in a signed manifest, must still be constrained by release policy and exact digest verification.

## 22. Manager baseline compatibility

The current production Manager baseline remains:

```text
local/greenhouse-manager:fresh-5b32e1ae8210
```

The Stack OTA design does not mutate that baseline.

R4 default-off behavior must continue to preserve the pre-R4 Manager runtime call shape until a later deployment gate explicitly enables OTA runtime integration.

## 23. Production stack compatibility

Current accepted production authority remains:

```text
Manager:
local/greenhouse-manager:fresh-5b32e1ae8210

Home Assistant:
local/n3w-homeassistant:2026.10.0-0c73235a

Broker:
local/n3w-mosquitto:2.1.2-3184566d
```

This architecture document changes no image binding and authorizes no service restart.

## 24. End-user requirements

The final product route must satisfy:

```text
SSH_REQUIRED_FOR_END_USER=false
MAC_REQUIRED_FOR_END_USER=false
GITHUB_KNOWLEDGE_REQUIRED_FOR_END_USER=false
DOCKER_KNOWLEDGE_REQUIRED_FOR_END_USER=false
MQTT_KNOWLEDGE_REQUIRED_FOR_END_USER=false
```

If physical USB is required by a release, the user may be asked only for product-level physical actions such as inserting the USB device and approving formatting/install.

## 25. Observability

Public status may expose:

- installed stack version;
- latest approved stack version;
- update available;
- USB required;
- prepare progress;
- download/verify progress;
- READY_TO_INSTALL;
- current component stage by friendly name;
- rollback in progress;
- success;
- bounded recovery-required code.

It must not expose:

- credentials;
- private paths;
- raw authorization material;
- unrestricted host errors;
- shell commands;
- private key material.

## 26. Release publication pipeline

A future product release pipeline should follow:

```text
source review
-> component CI
-> exact ARM64 artifacts
-> compatibility review
-> stack manifest generation
-> signature
-> release publication
-> independent download/revalidation
-> release authority promotion
```

Publishing a component artifact alone does not make it an end-user approved Stack OTA release.

## 27. Backward compatibility with engineering tools

Existing engineering workflows remain valid for controlled development:

- GitHub Actions exact artifacts;
- Mac-side execution packages;
- SSH/SCP staging where explicitly authorized;
- direct updater inspect/plan/apply for controlled engineering gates.

These are not the final end-user path but remain useful for development, factory acceptance and recovery.

## 28. Acceptance gates for future implementation

The successor program should be split into bounded gates.

### SOTA-R1 — release schema and signature verification

- stack manifest schema;
- signed release verifier;
- current-stack resolver;
- no live mutation.

### SOTA-R2 — stack transaction and simulated orchestration

- durable stack state;
- multi-component simulated prepare/install/rollback;
- power-loss classification;
- no real Docker/USB mutation.

### SOTA-R3 — Manager product OTA integration

- autonomous approved package discovery/download;
- reuse Generic V2;
- unified user control;
- current Manager A-to-B regression remains green.

### SOTA-R4 — Broker Generic V2 implementation

- Broker target/rollback contracts;
- persistent-state and DynSec acceptance;
- simulated then controlled live proof.

### SOTA-R5 — Home Assistant adapter integration

- reuse mandatory-USB successor transaction;
- no weakening of USB/data rollback rules.

### SOTA-R6 — unified Home Assistant product surface

- one stack-level update entity;
- component detail;
- PREPARE/INSTALL/status;
- no privileged Manager expansion.

### SOTA-R7 — real T1 end-to-end product acceptance

- Manager-only release;
- Broker-only release;
- HA-containing release;
- multi-component release;
- failure and rollback;
- power-loss recovery.

Each gate requires its own authorization and STOP boundary.

## 29. Relationship to current Home Assistant R4/R5

The current HA line remains authoritative and continues independently:

```text
R4=
HOST_INTEGRATION_PACKAGE_AND_NARROW_VALIDATED_MANAGER_TO_PRIVILEGED_UPDATER_IPC

R5=
REAL_T1_READONLY_PREFLIGHT
```

This Stack OTA design must not cause R4 scope expansion.

R5 remains a separate real-T1 access boundary and requires explicit authorization.

## 30. Frozen architecture decisions

```text
PRODUCT_OTA_TARGET=T1_CORE_STACK_OTA

PUBLIC_PRODUCT_CONCEPT=T1_Core_Stack_OTA
PRIVILEGED_EXECUTION_ENGINE=T1_Core_Updater

COMPONENTS=
Manager
Broker
HomeAssistant

MANAGER_STRATEGY=GENERIC_V2_SUCCESSOR
BROKER_STRATEGY=GENERIC_V2_SUCCESSOR
HOMEASSISTANT_STRATEGY=MANDATORY_USB_SUCCESSOR

ONE_USER_FACING_STACK_UPDATE=true
STACK_RELEASE_MANIFEST=true
SIGNED_RELEASE_AUTHORITY_REQUIRED=true
STACK_TRANSACTION_REQUIRED=true
COMPONENT_TRANSACTION_REQUIRED=true

GITHUB_ACTIONS_ARTIFACT_AS_FINAL_END_USER_CDN=false

GREENHOUSE_MANAGER_PRIVILEGED=false
GREENHOUSE_MANAGER_DOCKER_SOCKET=false
GREENHOUSE_MANAGER_BLOCK_DEVICE=false
GREENHOUSE_MANAGER_ROOT=false

T1_CORE_UPDATER_REWRITE_REQUIRED=false
T1_CORE_UPDATER_RENAME_REQUIRED=false

CURRENT_R4_SCOPE_CHANGED=false
CURRENT_PRODUCTION_AUTHORITY_CHANGED=false
```

## 31. Items deliberately deferred

This design does not yet freeze:

- public release service domain/vendor;
- release-signing key storage implementation;
- signing-key rotation mechanics;
- automatic check cadence;
- final stack version numbering policy;
- final multi-component execution order rules;
- exact Broker migration/rollback source implementation;
- host daemon/process packaging;
- UI wording and localization;
- download bandwidth/rate policy.

These require later source and product gates and must not be invented by R4.

## 32. Conclusion

`T1_Core_Stack OTA` becomes the product-level OTA architecture for the complete T1 core stack.

It does not replace `T1_Core_Updater` as the privileged execution engine.

The design preserves the already validated Manager Generic V2 upgrade route, adds Broker as a future Generic V2 component, preserves the mandatory-USB Home Assistant strategy, and places all three under one signed release, one user-facing product surface and one durable stack-level transaction.

Current R4 remains unchanged and may close independently on its exact executable source evidence.
