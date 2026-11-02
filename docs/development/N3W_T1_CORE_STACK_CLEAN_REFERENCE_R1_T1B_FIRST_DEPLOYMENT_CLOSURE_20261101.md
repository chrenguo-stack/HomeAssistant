# N3-W T1_Core_Stack Clean Reference — R1 T1_B first deployment closure

Date: 2026-11-01

## 0. Closure

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R1_T1B_FIRST_DEPLOYMENT_20261101_01
RESULT=CLOSED_PASS

TARGET=T1_B

S0_SOURCE_AUTHORITY_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
CONTROL_PLANE_AUTHORITY=ee0aaf71ddc71bba5f121e25f09a1f0189f5e6e8

RUNTIME_PAYLOAD_SHA256=7c1fbc29bfcb5597f2736a9a6ce39192cd8c6bb317df6db37c9581df7efcdcfd
PAYLOAD_MANIFEST_SHA256=b5570c7e97965d5afa593721849571d62ab67a67888fb2c2ace6d4d043147fa3

FRESH_PRODUCT_STAGED=true
NODE_CREDENTIAL_COUNT=0

IMAGE_COUNT=3
CONTAINER_COUNT=0
VOLUME_COUNT=0
PRODUCT_LISTENER_COUNT=0
DOCKER_NETWORKS=bridge,host,none

STAGED_UNITS_ENABLED=true
STAGED_UNITS_ACTIVE=false
PRODUCTION_ACTIVATION_UNITS_ENABLED=false
PRODUCTION_ACTIVATION_UNITS_ACTIVE=false

TRANSPORT_RESIDUAL_COUNT=0
CANDIDATE_RESIDUAL_COUNT=0

PRODUCTION_V2_AUTHORITY_USED=false
PRODUCTION_SERVICE_START=false
ACTIVATION_AUTHORIZED=false
BOARD_ACCESS=false

R2_AUTHORIZED=false
AUTO_EXECUTE_NEXT_GATE=false
```

R1 establishes the clean stopped-state product reference on T1_B. It does not start production
services and does not enter the controlled reboot/start or bounded workload gates.

## 1. Final live apply

The final Clean Reference executor and host reports both returned PASS.

```text
EXECUTOR_STATUS=PASS
EXECUTOR_PHASE=apply
HOST_STATUS=PASS
HOST_PHASE=apply
SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64

IMAGE_REQUEST_SEQUENCE=homeassistant,manager,broker
IMAGE_LOAD_SEQUENCE=homeassistant,manager,broker

FRESH_PRODUCT_STAGED=true
NODE_CREDENTIAL_COUNT=0

PRODUCTION_V2_AUTHORITY_USED=false
PRODUCTION_SERVICE_START=false
ACTIVATION_AUTHORIZED=false
BOARD_ACCESS=false
```

All three exact local S1 image tars were transferred one at a time and loaded offline. No registry
pull or image rebuild was used.

## 2. Final portable runtime identity acceptance

A post-deployment read-only verifier re-bound the T1 runtime to the frozen local payload using the
same cross-Docker-store identity contract already established by the project.

Local authority verification:

```text
LOCAL_PORTABLE_RUNTIME_AUTHORITY=PASS
SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
RUNTIME_PAYLOAD_SHA256=7c1fbc29bfcb5597f2736a9a6ce39192cd8c6bb317df6db37c9581df7efcdcfd
PAYLOAD_MANIFEST_SHA256=b5570c7e97965d5afa593721849571d62ab67a67888fb2c2ace6d4d043147fa3
```

T1 read-only portable verifier:

```text
PORTABLE_RUNTIME_POSTCHECK=PASS
T1_ACCESS=READ_ONLY
T1_MUTATION=false

MANAGER_ROOTFS_BINDING=PASS
MANAGER_CONFIG_CONTRACT_BINDING=PASS
HOMEASSISTANT_ROOTFS_BINDING=PASS
HOMEASSISTANT_CONFIG_CONTRACT_BINDING=PASS
BROKER_ROOTFS_BINDING=PASS
BROKER_CONFIG_CONTRACT_BINDING=PASS
```

Observed runtime IDs:

```text
MANAGER_BUILD_IMAGE_ID=sha256:4ca9f21534f3557038a50746bce9ff1343ce708a644f2ae299165369eac118f8
MANAGER_RUNTIME_ID=sha256:2bfead7d72535aecae943277a70715811ad29d089d7fb45ba6bd0d3dc68bc286

HOMEASSISTANT_BUILD_IMAGE_ID=sha256:b0e1ee82adfb19fa1ff3049034535633b1c4f0df6606721c0e77383854b99879
HOMEASSISTANT_RUNTIME_ID=sha256:c261fa53f30508951833492ba2a19af6cfbb6aa8f2806b531d8f5c6599265306

BROKER_BUILD_IMAGE_ID=sha256:4c199d7c9d377d018313a2199f6839978f6fd2219c405ad664d0a830c14b9c7b
BROKER_RUNTIME_ID=sha256:df265f1e2b2e3dc35d5eb194e698c598e01c5ebca370da307b34332f9bf0a563
```

All three runtime IDs differ from the CI/build image IDs. This is accepted by the existing project
Docker 29 cross-store rule: runtime `.Id` syntax is validated, but equality with the build/config
digest is not a portable cross-store oracle. Exact tar SHA binding, tag, arm64/linux platform,
RootFS layer fingerprint and config-contract fingerprint are the portable identity authorities.

Authority:
`docs/development/N3W_T1_FRESH_BOOTSTRAP_R3_DOCKER29_CROSS_STORE_IMAGE_IDENTITY_SOURCE_REPAIR_20261012.md`.

## 3. Final stopped-state acceptance

Independent read-only state:

```text
IMAGE_COUNT=3
CONTAINER_COUNT=0
VOLUME_COUNT=0
DOCKER_NETWORK_NAMES=bridge,host,none
PRODUCT_LISTENER_COUNT=0

REQUIRED_PRODUCT_PATHS=PASS
FORBIDDEN_PRODUCT_PATHS=ABSENT

n3wfc4-broker-ingress-guard.service=enabled,inactive
n3wfc4-registration-ingress-guard.service=enabled,inactive
n3wfc4-provision-resume.service=enabled,inactive

n3wfc4-broker-activation.service=not-found,inactive
n3wfc4-services-activation.service=not-found,inactive
n3wfc4-broker-certificate-lifecycle.timer=not-found,inactive

TRANSPORT_RESIDUAL_COUNT=0
CANDIDATE_RESIDUAL_COUNT=0

PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
```

This is the intended R1 stopped-state boundary.

## 4. Blocker and repair history

### 4.1 Strict payload file-set false stop

Initial live execution stopped before `run_fresh_staging()` because the Clean Reference executor
was copied inside the strict manifest-validated payload directory.

Repair moved the executor to a sibling path.

```text
FAILURE_CODE=payload_file_set_invalid
RUN_FRESH_STAGING_ENTERED=false
IMAGE_LOAD=false
PRODUCT_COMMIT=false
```

### 4.2 Python bytecode mutation

Read-only recovery evidence showed dynamic module loading had also created payload-local
`__pycache__/*.pyc` files. The Clean Reference executor was repaired to temporarily set
`sys.dont_write_bytecode=True` while loading payload modules.

The strict payload file-set validator was not weakened.

### 4.3 Missing staged-unit transition

A deeper live run loaded all three images and reached stopped postcheck, then stopped on
`postcheck_staged_units_not_enabled`.

Source review proved the frozen full fresh-staging primitive omitted the staged-unit transition
while its postcheck required the units to be enabled.

The final repair was deliberately converged into the Clean Reference control plane rather than
changing frozen S0/runtime component source:

- immediately before the frozen stopped postcheck, the Clean Reference adapter bridge calls the
  existing `enable_staged_units()`;
- if a later failure enters cleanup, the bridge first disables the three staged units and then
  delegates to the frozen cleanup;
- frozen S0/runtime source blobs remain byte-identical to the previous valid authority.

Final control-plane repair authority:

```text
CONTROL_PLANE_AUTHORITY=ee0aaf71ddc71bba5f121e25f09a1f0189f5e6e8
CLEAN_REFERENCE_RUNTIME_PAYLOAD_CI_RUN=41301614166
CLEAN_REFERENCE_RUNTIME_PAYLOAD_CI=SUCCESS
```

No runtime-only artifact or S1 image rebuild was required.

### 4.4 Ad-hoc exact runtime-ID false stop

After the successful R1 apply, an additional ad-hoc acceptance script incorrectly required
T1 runtime image `.Id` equality with the S1 build image ID and emitted:

```text
STOP=image_id_mismatch:manager
```

This was classified FALSE_STOP. The condition contradicted the existing Docker 29 cross-store
identity authority. The subsequent portable read-only verifier used the correct RootFS/config
contract and returned PASS for all three images.

No cleanup or deployment retry was performed after this false stop.

## 5. SSH authentication improvement

The original Mac host execution created many independent SSH/SCP sessions and required repeated
password entry. The final route used a temporary Mac-side OpenSSH ControlMaster connection.

```text
T1_AUTHORIZED_KEYS_MODIFIED=false
MAC_PERSISTENT_SSH_CONFIG_MODIFIED=false
EXPECTED_PASSWORD_PROMPTS=1
```

A first attempt used an overlong Unix socket path and stopped locally before T1 access. The socket
was then moved to a short `/tmp/n3w-cm-<pid>` path. The final execution required one password
entry.

## 6. zsh post-reporting issue

The final read-only verifier emitted its complete PASS JSON, then the outer zsh wrapper attempted
to read bash-only `PIPESTATUS[0]` and reported:

```text
zsh: PIPESTATUS[0]: parameter not set
```

This occurred after the verifier had completed and printed `status=PASS`. It affects only the
outer shell's final return-code reporting. It did not alter T1 state or invalidate the complete
semantic PASS report.

```text
PORTABLE_POSTCHECK_SEMANTIC_RESULT=PASS
OUTER_ZSH_RC_REPORT=UNAVAILABLE_DUE_TO_SHELL_VARIABLE_BUG
T1_MUTATION_DURING_POSTCHECK=false
```

Future zsh wrappers should use `pipestatus` or avoid a pipeline when an exact child exit code is
required.

## 7. Gate boundary

R1 is CLOSED_PASS.

The next architectural route is R2 controlled reboot/start validation, followed later by R3
bounded workload and A1 stable-invariant extraction. None of those gates is authorized by this
closure.

```text
R1=CLOSED_PASS
R2=NOT_AUTHORIZED
R3=NOT_EXECUTED
A1=NOT_EXECUTED
MERGE=false
AUTO_EXECUTE_NEXT_GATE=false
```
