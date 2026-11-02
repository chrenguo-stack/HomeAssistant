# N3-W T1_Core_Stack Clean Reference — R0H T1_B host runtime establishment final closure

Date: 2026-11-01

## 0. Final result

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0H_T1B_HOST_RUNTIME_ESTABLISHMENT_FINAL_CLOSURE_20261101_01

TARGET=T1_B

ACQUISITION_SOURCE_AUTHORITY=c4984baf274d74d1459175153b62bed9a2b7626e
INSTALL_SOURCE_AUTHORITY=24382caae4a1f5d459297f86e8d18f10a848ca64

BUNDLE_ID=26bc7f78615a0ed3f1240ddfb2ecded5ef7df1da50e9969a52dffb1010185163
PACKAGE_COUNT=5
TOTAL_BYTES=79391752

CACHE_ONLY_INSTALL=true
NETWORK_DOWNLOAD_PERFORMED=false
DPKG_AUDIT_CLEAN=true

R0H_POSTINSTALL_ACCEPTANCE=PASS
R0H_FINAL_RESULT=CLOSED_PASS

T1_CORE_STACK_DEPLOYED=false
T1_A_MUTATION=false
BOARD_ACCESS=false
```

R0H is now complete. T1_B has the exact host runtime prerequisite installed while the
canonical T1_Core_Stack remains absent.

## 1. Exact installed package set

```text
docker.io=29.1.3-0ubuntu4.1
docker-compose-v2=2.40.3+ds1-0ubuntu1
containerd=2.2.2-0ubuntu1.2
runc=1.4.0-0ubuntu1
libnftables1=1.1.6-1
```

Runtime checks:

```text
DOCKER_SERVER_VERSION=29.1.3
COMPOSE_RUNTIME_VERSION=2.40.3+ds1-0ubuntu1
DOCKER_SERVICE_ACTIVE=active
DOCKER_SERVICE_ENABLED=enabled
```

## 2. Empty Docker state

Post-install evidence:

```text
TOTAL_CONTAINER_COUNT=0
TOTAL_IMAGE_COUNT=0
TOTAL_VOLUME_COUNT=0
DOCKER_NETWORK_NAMES=bridge,host,none,
ONLY_DEFAULT_DOCKER_NETWORKS=true
```

No application image, container, named volume or product network exists at R0H closure.

## 3. Product absence preserved

```text
INSTALL_STAGING_RESIDUAL_COUNT=0
PRODUCT_PATH_RESIDUAL_COUNT=0
PRODUCT_UNIT_RESIDUAL_COUNT=0
PRODUCT_LISTENER_RESIDUAL_COUNT=0
T1_CORE_STACK_DEPLOYED=false
```

Therefore installing the host runtime did not cross into greenhouse-manager, Home Assistant
or Mosquitto deployment.

## 4. Cache identity and offline install proof

The exact reusable host-runtime bundle remains:

```text
BUNDLE_ID=26bc7f78615a0ed3f1240ddfb2ecded5ef7df1da50e9969a52dffb1010185163
PACKAGE_COUNT=5
TOTAL_BYTES=79391752
```

The bundle was previously:

1. acquired on the R0-qualified ARM64 T1_B;
2. strictly verified on T1_B;
3. copied to the durable Mac cache;
4. independently verified on macOS.

The successful physical install reported:

```text
phase=install
status=PASS
installed=true
cache_only_install=true
network_download_performed=false
```

This is the required proof that the installation transaction used the verified local bundle
without downloading package payloads during install.

## 5. Installation-path repair history

Two failed install attempts produced no partial package installation.

The final R3 implementation established the correct APT cache-only model:

```text
verified bundle
-> temporary APT archive cache under /var/tmp
-> exact package=version requests for every manifest member
-> apt-get --no-download --no-remove
-> staging cleanup
```

The final exact installation source authority is:

```text
24382caae4a1f5d459297f86e8d18f10a848ca64
```

Its required CI set closed SUCCESS before the physical retry.

## 6. Architecture boundary

At R0H closure:

```text
HOST_RUNTIME_ESTABLISHED=true
T1_CORE_STACK_ESTABLISHED=false

HOST_RUNTIME_INCLUDES=
docker.io
docker-compose-v2
containerd
runc
libnftables1

T1_CORE_STACK=
greenhouse-manager
Home Assistant
Mosquitto Broker
```

Docker Engine and Docker Compose remain host/runtime prerequisites outside canonical
T1_Core_Stack identity.

## 7. Next route

```text
NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_S0_EXACT_SOURCE_AND_VERSION_FREEZE_20261101_01
```

S0 is a source/version authority gate. It must not deploy application images to T1_B and must
not start production services.
