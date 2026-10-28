# N3-W R10 T1 candidate production-software upgrade artifact freeze closure

Date: 2026-10-28

## 1. Closure status

```text
TASK=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_UPGRADE_PACKAGE_FREEZE_20261028_01

PACKAGE_SOURCE_FREEZE=PASS
EXACT_ARTIFACT_FREEZE=PASS
REDOWNLOAD_VERIFY=PASS
LIVE_T1_UPGRADE=NOT_STARTED

PACKAGE_HEAD=81546685bbb7d9d6aad9cf574d871277ca4b44b1
PACKAGE_PR=715

T1_ACCESS=false
T1_MUTATION=false
SERVICE_STOP_START=false
BOARD_ACCESS=false
T1_UPGRADE_AUTHORIZATION_GRANTED=false
UPGRADE_AUTHORIZATION_CONSUMED=false
R10_BOARD_WRITE_AUTHORIZATION_CONSUMED=false
```

PR #715 is intentionally left at the exact package head above. No docs commit may be appended to that branch after artifact freeze, because doing so would change the package head without rebuilding the artifact.

This closure document lives on a separate docs-only stacked branch.

## 2. Exact workflow authority

```text
WORKFLOW_NAME=N3W R10 T1 candidate upgrade package CI
WORKFLOW_RUN_ID=40634208155
WORKFLOW_HEAD=81546685bbb7d9d6aad9cf574d871277ca4b44b1
SOURCE_CONTRACT=SUCCESS
BUILD_CANDIDATE=SUCCESS
REDOWNLOAD_VERIFY=SUCCESS
```

The workflow independently redownloaded the uploaded artifact and re-verified the package manifest, Manager tar SHA/size, Manager image ID, base image digest/ID and package policy.

## 3. GitHub artifact authority

```text
ARTIFACT_ID=12792592683
ARTIFACT_NAME=n3w-r10-t1-upgrade-81546685bbb7
ARTIFACT_SIZE_BYTES=61540313
ARTIFACT_DIGEST=sha256:e4f236387c67a2ac88623bb2166201fcc44589dc99504aded4b9df688ad5dc9c
ARTIFACT_CREATED_AT=2026-10-28T04:48:58Z
ARTIFACT_EXPIRES_AT=2026-11-27T04:48:56Z
ARTIFACT_EXPIRED=false
```

Artifact metadata was independently rebound from the workflow-run artifact list after CI completion.

## 4. Package manifest authority

```text
MANIFEST_SHA256=4c9eca65c535cc7c5fd1f48891844f381338719d2d422d0f5464cc8f7a660664
PACKAGE_SCHEMA=gh.n3w.r10-t1-candidate-upgrade-package/1

PREDECESSOR_SOURCE=03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6
TARGET_SOURCE=e299c937a7b89bb8a7b9a7432186ba46a416cd44

PREDECESSOR_MANAGER_IMAGE=local/greenhouse-manager:fresh-03dab2bd04e7
TARGET_MANAGER_IMAGE=local/greenhouse-manager:fresh-e299c937a7b8
```

## 5. Manager candidate authority

```text
MANAGER_TAR_SHA256=de0a5de5f0922dafc3485414ad7add1e31ecdd61c1cf8e473e00c5350eb83e1e
MANAGER_TAR_SIZE_BYTES=61439488

MANAGER_IMAGE_ID=sha256:bf5a1f7def35849dec43c232f2caad9e429723b5ce86878a73b3b7a7e5a50169
MANAGER_IMAGE_SIZE_BYTES=201686995
MANAGER_PLATFORM=linux/arm64

BASE_IMAGE_REF=python:3.11-slim
BASE_ARM64_MANIFEST_DIGEST=sha256:97ac71919bb9718e0706271fd45337d6fc9e42303e0b67c454ff8e90eed26329
BASE_IMAGE_ID=sha256:88a84dd9a9cfc9cf46c1b438c63362bb5df5179748f0421dee6f466302a5a515

PYTHON_DISTRIBUTION_COUNT=17
PYTHON_DISTRIBUTIONS_SHA256=c29bbdd603c74aa7c36f33a32f22d86e5dacb6c34ec2266fc55eb8660cac0ae6
```

The artifact does not claim historical e299 Manager byte continuity and does not claim that a future rebuild will be byte-identical.

The frozen authority is the actual built artifact:
exact target source + frozen ARM64 base manifest digest + installed Python distribution inventory + output image ID + Manager tar SHA/size.

## 6. Upgrade executor authority

```text
EXECUTOR_ARTIFACT_PATH=upgrade-executor.py
EXECUTOR_SHA256=214fef4a1feb6c446aad25847d7615a6f48cca054f6d09ce8b5c7b3825d5d1a4
EXECUTOR_SIZE_BYTES=65222
```

The live executor self-checks that the currently running executor bytes match this manifest binding before any live mutation.

## 7. Runtime bundle authority

```text
RUNTIME_BUNDLE_SIZE_BYTES=27122
UPGRADE_EMERGENCY_RESERVE_BYTES=2147483648
DYNAMIC_ROLLBACK_MEASUREMENT_REQUIRED=true
```

Frozen live file targets:

```text
/etc/n3wfc4/docker-compose.yml
/etc/systemd/system/n3wfc4-services-activation.service
/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
/etc/systemd/system/n3wfc4-registration-ingress-guard.service
/usr/local/sbin/n3w-registration-ingress-guard
/usr/local/sbin/n3w-trusted-product-lan-authority
```

Target SHA-256 values:

```text
compose=9ea58161d5f8e24233bacbfe1f31edd5f6f6c62c272271823788c0c5b59e8357
services_unit=ea8c038a7a81deba279e9e3a2ad3abe91f125d7a5712cf56b106d7dfa78112ed
dispatcher=ff3c202b0a1a08049f4946a8eea701242e03f33fe336863ba0cb6d0074c50aed
registration_unit=b66b0c0503f11721da94445cc4de9940a733c6fc1c6f0b90537817dcdfa952fb
registration_guard=321c86efcebec5515f890f996e03211f1350aac6f60d2e84e66a51e2be57358c
trusted_lan_authority=4d503ca52d9291937d049bd352f948432955db37c1ddc5d741ac88e26e7d7046
```

## 8. Preserved historical authority

The live upgrade intentionally does not mutate:

```text
/opt/HomeAssistant
/usr/local/sbin/n3w-t1-f4-activation
Broker image
Broker container lifecycle
Broker Dynamic Security file
Home Assistant image
board flash/NVS
```

The original predecessor Manager image is retained after success because the existing provisioning/F4 historical release checks still reference the original release image set.

## 9. Live admission rules already frozen

Before one-shot authorization claim, the live executor must freshly prove:

- predecessor Manager image is exact;
- Broker and Home Assistant images are exact expected predecessor images;
- Broker activation and Broker ingress guard are active/loaded;
- 47110/TCP, 47111/UDP and 47112/TCP are all closed;
- registration guard/TLS/trusted-LAN successor material is absent;
- pairing window is CLOSED;
- Manager database integrity is PASS;
- current active registration count remains one;
- first-registration table is still absent;
- target Manager image is not already present;
- F4 services eligibility is PASS;
- all predecessor live file bytes match manifest predecessor bindings;
- Broker DynSec durable file is regular and its SHA-256 is captured;
- actual disk free space satisfies candidate image + measured rollback estimate + 2 GiB emergency reserve.

Any failure occurs before authorization claim and before production mutation.

## 10. Rollback contract already frozen

The later live executor:

- keeps Broker running;
- stops Manager/Home Assistant through the production services unit;
- requires Manager=0 and Home Assistant=0 running containers before state backup or rollback restore;
- captures a private numeric-owner archive of the complete `/var/lib/greenhouse-manager` state root;
- keeps exact pre-upgrade F4 transaction bytes and live-file/config backups;
- rebinds only the three changed historical F4 installed-file entries;
- preserves all historical F4 package/runtime-acceptance identity;
- verifies all six successor live files after startup;
- verifies Broker container continuity and Broker DynSec SHA continuity;
- uses bounded readiness for successor and predecessor startup;
- fails rollback without restoring state if application quiescence cannot be proven.

## 11. Exact artifact expiry rule

The current artifact is retained by GitHub until approximately:

```text
2026-11-27T04:48:56Z
```

If live execution does not occur before artifact expiry, this exact artifact must be treated as unavailable.

Do not rebuild and silently substitute another candidate under the same authority.

A replacement requires a new package head, new workflow run, new artifact ID/digest, new manifest SHA and a new artifact-freeze closure.

## 12. Next gate

```text
NEXT_ONE_GATE=N3W_SCAN_TRIGGERED_FIRST_PAIRING_R10_T1_CANDIDATE_LIVE_UPGRADE_PREEXECUTION_AND_AUTHORIZATION_20261028_01
```

The next gate is a preexecution/authorization gate.

Allowed before explicit live-upgrade authorization:

- read-only repository rebind;
- exact artifact metadata rebind;
- local Mac artifact download and local-only digest verification if kept outside the T1;
- generation/review of the exact operator command package.

Not allowed before explicit live-upgrade authorization:

- copying/staging the artifact onto T1;
- loading the target Manager image on T1;
- creating registration TLS on T1;
- stopping/restarting services;
- installing files;
- changing systemd/iptables/Compose env;
- changing Manager database/state;
- claiming the one-shot upgrade authorization.

The existing R10 board-write authorization remains separate and unconsumed.
