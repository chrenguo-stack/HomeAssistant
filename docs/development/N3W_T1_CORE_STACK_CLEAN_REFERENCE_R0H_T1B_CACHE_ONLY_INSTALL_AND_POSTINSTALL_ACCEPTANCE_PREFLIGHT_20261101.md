# N3-W T1_Core_Stack Clean Reference — R0H T1_B cache-only install and post-install acceptance preflight

Date: 2026-11-01

## 0. Gate

```text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R0H_T1B_CACHE_ONLY_INSTALL_AND_POSTINSTALL_ACCEPTANCE_20261101_01

SOURCE_AUTHORITY_HEAD=c4984baf274d74d1459175153b62bed9a2b7626e
BUNDLE_ID=26bc7f78615a0ed3f1240ddfb2ecded5ef7df1da50e9969a52dffb1010185163
TARGET=T1_B

CACHE_ONLY_INSTALL=true
NETWORK_PACKAGE_FALLBACK=false
T1_CORE_STACK_DEPLOYMENT=false
PRODUCT_SERVICE_START=false
T1_A_MUTATION=false
BOARD_ACCESS=false
```

This gate may install only the exact previously verified host-runtime bundle and may enable/start
Docker as a host prerequisite. It must not deploy or start greenhouse-manager, Home Assistant
or Mosquitto.

## 1. Exact inputs

```text
docker.io=29.1.3-0ubuntu4.1
docker-compose-v2=2.40.3+ds1-0ubuntu1
package_count=5
total_bytes=79391752
bundle_id=26bc7f78615a0ed3f1240ddfb2ecded5ef7df1da50e9969a52dffb1010185163
```

The verified T1 staging cache and durable Mac archive must both retain this same bundle ID.

## 2. Installation authority

The only authorized installation entry is:

```text
python3 n3w_t1_host_runtime_cache.py --phase install --cache-dir <exact verified T1 cache>
```

The repository-owned install path first runs strict `verify`, then invokes APT with:

```text
apt-get --no-download --no-remove install -y <exact local .deb members>
```

No `apt-get update`, download-only acquisition, online dependency repair or fallback package
source is allowed during this gate.

## 3. Docker host-runtime boundary

After exact package installation, the tool may:

- enable `docker.service`;
- start `docker.service`.

It may not:

- pull or load application images;
- create application containers;
- create product volumes or product networks;
- run `docker compose up`;
- create N3-W product paths, secrets or systemd units;
- listen on T1_Core_Stack product ports.

## 4. Post-install acceptance

Required exact package/runtime checks:

```text
INSTALL_STATUS=PASS
CACHE_ONLY_INSTALL=true
NETWORK_DOWNLOAD_PERFORMED=false
BUNDLE_ID_EXACT_MATCH=true
DOCKER_IO_PACKAGE_VERSION=29.1.3-0ubuntu4.1
DOCKER_COMPOSE_V2_PACKAGE_VERSION=2.40.3+ds1-0ubuntu1
DOCKER_SERVICE_ACTIVE=true
DOCKER_SERVICE_ENABLED=true
```

Required empty-Docker checks:

```text
TOTAL_CONTAINER_COUNT=0
TOTAL_IMAGE_COUNT=0
TOTAL_VOLUME_COUNT=0
ONLY_DEFAULT_DOCKER_NETWORKS=true
```

Default Docker networks are exactly:

```text
bridge
host
none
```

Required product-absence checks use the existing minimal-baseline product boundary:

```text
/var/lib/greenhouse-manager
/var/lib/n3wfc4-homeassistant
/var/lib/n3wfc4-broker
/var/lib/n3wfc4-certificate-lifecycle
/opt/greenhouse-secrets
/opt/HomeAssistant
/etc/n3wfc4
/usr/local/sbin/n3w-broker-ingress-guard
/usr/local/sbin/n3w-t1-broker-authenticated-readiness
/usr/local/sbin/n3w-broker-certificate-lifecycle
/etc/NetworkManager/dispatcher.d/90-n3wfc4-broker-ingress-guard
/etc/systemd/system/n3wfc4-broker-ingress-guard.service
/etc/systemd/system/n3wfc4-broker-activation.service
/etc/systemd/system/n3wfc4-services-activation.service
/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.service
/etc/systemd/system/n3wfc4-broker-certificate-lifecycle.timer
```

Expected product listener ports remain absent:

```text
1883
8883
18883
8123
47110
47111
47112
```

## 5. Stop point

```text
STOP_AFTER=R0H_POSTINSTALL_ACCEPTANCE_PASS
AUTO_T1_CORE_STACK_DEPLOYMENT=false
```

On PASS, R0H host runtime is complete and the next route is S0 exact T1_Core_Stack source/version
freeze. No application artifact acquisition or deployment is included in this gate.
