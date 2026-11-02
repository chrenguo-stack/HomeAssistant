# N3-W T1_Core_Stack Clean Reference — R0H minimum host runtime establishment design and preflight

Date: 2026-11-01

## 0. Gate

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0H_HOST_RUNTIME_ESTABLISHMENT_DESIGN_AND_PREFLIGHT_20261101_01

INPUT_R0=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0_T1B_FRESH_ARMBIAN_READONLY_BASELINE_20261101_01
R0_RESULT=PASS
TARGET=T1_B

T1_A_MUTATION=false
BOARD_ACCESS=false
T1_CORE_STACK_DEPLOYMENT=false
PRODUCT_PROVISIONING=false
PR745_MERGE=false
PR705_UPWARD_MERGE=false
```

R0H establishes only the minimum container host runtime required by later clean-reference
deployment. It does not deploy any T1_Core_Stack component.

## 1. Host/product boundary

```text
HOST_LAYER=
Armbian
+ systemd
+ SSH
+ NetworkManager
+ time synchronization
+ Docker Engine
+ Docker Compose plugin

T1_CORE_STACK=
greenhouse-manager
+ Home Assistant
+ Mosquitto Broker
```

Docker Engine and Compose are host/runtime prerequisites. They are outside the canonical
T1_Core_Stack product identity.

Therefore:

```text
DOCKER_PACKAGE_VERSION_IS_T1_CORE_STACK_PRODUCT_IDENTITY=false
COMPOSE_PACKAGE_VERSION_IS_T1_CORE_STACK_PRODUCT_IDENTITY=false

R0H_PACKAGE_VERSION_MUST_BE_EXACT_FOR_THIS_INSTALL=true
FUTURE_HEALTHY_HOST_VERSION_DRIFT_DEFAULT_CLASS=SOFT_RUNTIME_CHECK
PRODUCT_COMPATIBILITY_MINIMUMS_MAY_LATER_BECOME_HARD_INVARIANTS=true
```

A concrete Docker/Compose version becomes a future hard upgrade gate only if A1/A2 proves
that a compatibility or safety requirement needs it.

## 2. Existing repository primitive selected for reuse

Current source authority:

```text
HOST_BASELINE_TOOL=tools/n3w_t1_fresh_host_baseline.py
HOST_BASELINE_TOOL_BLOB=ae7d114bd54825114f462b4f7034ed6009f80f6f
HOST_BASELINE_TEST=tests/tools/test_n3w_t1_fresh_host_baseline.py
HOST_BASELINE_TEST_BLOB=efb01bb512e83eec3aa1d75e0a05da1a9a21ec70

PACKAGE_NAMES=docker.io,docker-compose-v2
PACKAGE_SOURCE=ubuntu_apt
```

The existing implementation already provides the required safety semantics:

- target OS must be Ubuntu 26.04 / resolute and ARM64;
- the caller must provide explicit package versions;
- `apt-get update` resolves current repository candidates;
- each candidate must exactly equal the approved version before installation;
- installation uses `package=version`, not unbounded latest;
- Docker is enabled and started;
- no Broker/Manager/Home Assistant activation authority exists;
- tests cover candidate drift, wrong installed versions, idempotent ready state and
  absence of product activation.

No product-source change is required for R0H.

## 3. R0H package-version policy

Old F5 V2 bound host package versions into an exact production release. That was appropriate
for the old all-in-one production-run contract but is not the new Clean Reference authority.

R0H freezes versions at the installation transaction boundary:

```text
apt-get update
-> resolve docker.io Candidate
-> resolve docker-compose-v2 Candidate
-> require both candidates are concrete
-> record exact candidate strings
-> install docker.io=<candidate>
-> install docker-compose-v2=<candidate>
-> verify installed versions exactly equal recorded candidates
```

No alternate install route is allowed in the same gate.

Forbidden fallbacks:

```text
get.docker.com=false
Docker CE third-party repository=false
snap=false
manual .deb=false
unversioned apt install=false
apt upgrade=false
dist-upgrade=false
```

APT may install the normal dependency closure required by the two selected Ubuntu packages.
Those dependency packages are host implementation detail unless later A1 evidence proves a
specific dependency must be a stable invariant.

## 4. Pre-mutation guards

Immediately before the first R0H mutation, T1_B must still satisfy:

- Ubuntu 26.04 / resolute / aarch64;
- Armbian 26.05.0 / S912-Phicomm-T1;
- NetworkManager active and default route present;
- systemd running with no failed units;
- Docker/Compose absent;
- no Docker data root;
- no T1_Core_Stack product paths/units/listeners;
- no product containers/images/volumes/networks.

APT source must visibly provide the frozen host source policy:

```text
APT_HOST=ports.ubuntu.com
APT_SUITE=resolute
APT_COMPONENT=universe
APT_ARCH=arm64
```

A mismatch stops before package installation. Do not repair APT sources ad hoc inside R0H.

## 5. Authorized R0H mutation

The bounded host mutation is exactly:

```text
apt-get update
apt-get install exact docker.io candidate
apt-get install exact docker-compose-v2 candidate
systemctl enable docker
systemctl start docker
```

The install may occur in one `apt-get install` transaction for both exact package versions.

R0H does not:

- deploy or load product images;
- create product containers;
- create product volumes;
- write product configuration;
- create N3W systemd units;
- open product listeners;
- create product credentials or secrets;
- access T1_A;
- access boards.

## 6. Post-install acceptance

R0H PASS requires all of:

```text
DOCKER_PACKAGE_INSTALLED=true
COMPOSE_PACKAGE_INSTALLED=true
DOCKER_SERVICE_ACTIVE=true
DOCKER_SERVICE_ENABLED=true
DOCKER_SERVER_VERSION_READABLE=true
DOCKER_COMPOSE_VERSION_READABLE=true
INSTALLED_PACKAGE_VERSIONS_EQUAL_RECORDED_CANDIDATES=true

TOTAL_CONTAINER_COUNT=0
TOTAL_IMAGE_COUNT=0
TOTAL_VOLUME_COUNT=0
PRODUCT_NETWORK_COUNT=0
ONLY_DEFAULT_DOCKER_NETWORKS=true

PRODUCT_PATH_RESIDUAL_COUNT=0
PRODUCT_UNIT_RESIDUAL_COUNT=0
PRODUCT_LISTENER_RESIDUAL_COUNT=0
T1_CORE_STACK_DEPLOYED=false
```

Docker's standard `bridge`, `host` and `none` networks are expected host-runtime
objects and are not product residue.

## 7. Failure policy

If package candidates are missing, APT source policy is wrong, exact install fails, Docker
does not become active, Compose is unreadable, or product residue appears:

```text
R0H_RESULT=FAIL_STOP
AUTO_ALTERNATE_INSTALL=false
AUTO_PRODUCT_DEPLOY=false
AUTO_ENTER_S0=false
```

Do not add third-party Docker repositories or perform target-local workaround commands.
Classify the failure first.

## 8. R0H closure fields

```text
R0H_OS_RELEASE=
R0H_ARCH=
R0H_APT_SOURCE_POLICY=
R0H_DOCKER_IO_CANDIDATE=
R0H_DOCKER_COMPOSE_V2_CANDIDATE=
R0H_DOCKER_IO_INSTALLED=
R0H_DOCKER_COMPOSE_V2_INSTALLED=
R0H_DOCKER_SERVER_VERSION=
R0H_COMPOSE_VERSION=
R0H_DOCKER_SERVICE_ACTIVE=
R0H_DOCKER_SERVICE_ENABLED=
R0H_TOTAL_CONTAINER_COUNT=
R0H_TOTAL_IMAGE_COUNT=
R0H_TOTAL_VOLUME_COUNT=
R0H_DOCKER_NETWORK_NAMES=
R0H_PRODUCT_RESIDUAL_COUNT=
R0H_T1_CORE_STACK_DEPLOYED=false
T1_A_MUTATION=false
BOARD_ACCESS=false
R0H_HOST_RUNTIME_BASELINE=PASS|FAIL
```

## 9. Next route

After R0H PASS:

```text
NEXT_STAGE=S0_FREEZE_NEW_EXACT_T1_CORE_STACK_SOURCE_VERSION_SET
S0_IS_REPOSITORY_READONLY_FREEZE=true
S0_PRODUCT_DEPLOYMENT=false
```

R0H PASS does not itself authorize R1 deployment or provisioning.
