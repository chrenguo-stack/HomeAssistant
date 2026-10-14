# S20 Home Assistant automatic MQTT bootstrap independent review

Date: 2026-10-10
Status: REVIEW_ONLY / REPAIR_REQUIRED
Repository: chrenguo-stack/HomeAssistant
PR: 541, OPEN DRAFT
REVIEW_BASE=d423211b6196c2f2f0f01dff072c4f877fbe58ee
REVIEW_HEAD=74ef475a266b9fdfde3cb019163a624c6fb7e443
FAILED_RUN=38035240496
FAILED_JOB=114164201333
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
SOURCE_MUTATION=false
TEST_MUTATION=false
MERGE=false

## Summary

最新 30.71 秒失败发生在 TCP preflight，MQTT auth 和 HA 主进程尚未启动，不能归因于 HA config-flow。

首要根因方向是 Broker 测试文件权限，而不是已经证实的 GitHub host networking 限制。同时，独立确认了两个后续缺陷：
1. 产品 _entry_matches 只接受 dict，而真实 HA ConfigEntry.data 是 MappingProxyType，因此匹配的既有配置也会被拒绝。
2. 重建测试在新容器完成启动前，就可以从旧 storage 文件返回成功，无法证明本次 bootstrap 已执行。

继续自动配置路线；无需改生产 localhost/1883 或 TLS/8883 拓扑。先做小范围 source/test 修补，再运行真实隔离 CI。

## A1. Broker failure classification

Current test:
tests/tools/test_n3w_ha_mqtt_bootstrap_isolated_runtime.py
- line 351 creates broker_dir with mode 0700, owned by the runner.
- mosquitto_passwd runs through an overridden entrypoint and writes the password file; no subsequent owner binding is performed for the Broker directory/password file.
- only mosquitto.conf mode is changed to 0644.
- broker_dir is mounted read-only at /mosquitto/config.
- Broker starts without a custom user/PUID/PGID override.

Official image recipe mapping inspected:
docker-library/official-images library/eclipse-mosquitto
GitCommit=5b74cce8a4fe2a73b57df6c703bfde2cfd535d60
Directory=docker/2.1-alpine
Tag=2.1.2-alpine

That Dockerfile defines mosquitto UID/GID 1883. Its entrypoint only fixes /mosquitto/data ownership; it does not fix mounted /mosquitto/config.
Mosquitto v2.1.2 src/mosquitto.c drops privileges after config parsing, then loads security/password material before starting listeners. The runner-owned 0700 directory prevents the broker user traversing it to read passwords.

Classification:
BROKER_FILE_PERMISSION_HARNESS_DEFECT=SOURCE_IDENTIFIED
MOST_LIKELY_RUNTIME_FAILURE=BROKER_EXIT_DURING_STARTUP
EXACT_FAILED_CONTAINER_EXIT_AND_LOG=NOT_CAPTURED
GITHUB_HOST_NETWORK_NAMESPACE_LIMITATION=NOT_PROVEN

Do not claim the exact failure log or exit code was observed. The failed job deletes the containers without collecting Broker evidence. The image source recipe is additional evidence, not a substitute for checking the exact pulled image's runtime UID, mounts and filesystem permissions.

## A2. Minimal forensic repair

Reuse the existing _container_state() and _safe_logs() for the Broker, not only HA.

Before cleanup, preserve a bounded, sanitized diagnostic:
- container ID, image ID/digest;
- State.Status/Running/ExitCode/Error/OOMKilled, RestartCount;
- HostConfig.NetworkMode and effective runtime UID/GID;
- configuration/password path mode, UID/GID, directory traversal/readability, mount read-only flag;
- final Broker log tail and sanitized probe stderr;
- last completed phase: started, TCP ready, auth passed, HA started, flow created, recreated.

Never dump password contents, full inspect environment, credential files, or full HA flow data.

A broker that has exited must fail immediately, rather than consume the full TCP timeout. All subprocess operations also need bounded wall-clock timeouts.
Keep cleanup in finally, but diagnostics must run before removal.

## A3. Host networking assessment

Docker Engine on Linux documents host mode as sharing the daemon host network namespace:
https://docs.docker.com/engine/network/drivers/host/

The workflow is a normal ubuntu-24.04 job without a job-level container declaration. Current evidence does not show a remote daemon, rootless daemon, or different network namespaces. Host mode is not intrinsically unsuitable for Linux GitHub runners.

Runner TCP success alone does not prove the intended Broker accepted MQTT; a published port/proxy or a different listener can accept TCP. Do not infer namespace differences from the currently incomplete evidence.

If host networking still fails after Broker readiness is proven, inspect daemon/context, security options, actual listener ownership and /proc network namespace identifiers for live processes. Check Docker daemon host identity rather than assuming Docker CLI locality.

## A4. Recommended isolated topology

For bootstrap testing:
- start Broker in its own ordinary bridge network namespace;
- bind its test MQTT listener to 127.0.0.1:1883;
- publish no host ports;
- run both probes and HA with --network container:<broker-container>;
- keep Broker alive across HA recreation.

Docker explicitly supports this localhost-sharing pattern:
https://docs.docker.com/engine/network/#container-networks

This validates real localhost TCP, MQTT v5 authentication and official HA config-flow. It does not validate T1 host publication, firewall, Docker network membership or external exposure. Label these as separate gates.

Do not change production Compose to this topology.
Production bridge Broker must listen on the appropriate container interface for published ports to reach it. Do not copy the isolated test's container-loopback-only listener into production Broker configuration.

Changing namespace does not fix unreadable Broker files; permission correction and readiness remain mandatory.

## A5. Official HA source contract and confirmed product defect

HA exact source:
https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/mqtt/config_flow.py
blob=9181013edc6686b6ac482b4061b3f5e48ba4ff77

For HA Container (without Supervisor):
source=user -> async_step_broker
The supplied broker, port, protocol="5" and other_settings fields agree with the reviewed source. async_validate_broker_settings flattens other_settings, handles set_ca_cert="off", and tries the actual connection before creating the entry.
No evidence presently justifies replacing protocol "5" or bypassing config-flow.

Confirmed product defect:
infra/n3w-t1/homeassistant/custom_components/n3w_mqtt_bootstrap/__init__.py
_entry_matches(), line 196:
if not isinstance(data, dict): return False

HA source:
https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/config_entries.py
blob=a1848f3dceab65aa07198deb72232af4d3271434
ConfigEntry constructor wraps data with MappingProxyType(data) at line 488.

Therefore a perfectly matching real entry is rejected after reboot/recreation.
The unit test uses SimpleNamespace(data=<ordinary dict>), masking the incompatibility.

Minimal patch:
from collections.abc import Mapping
Use isinstance(data, Mapping), retain all value/password comparisons.
Unit tests must use MappingProxyType, and include both exact-match and mismatch cases.

Additional bounded contract repairs:
- A matching entry should check effective TCP/no-TLS transport settings and reject a disabled entry; current matching only checks a subset of the declared connection contract.
- bootstrap currently tries once and returns False on connection failure. A clean install must either mechanically wait for authenticated Broker readiness before starting HA, or define bounded retry for transient availability. Do not use unlimited retries or manual password changes. This is a deployment/start-order requirement, not evidence that the latest TCP failure was caused by HA.
- flow initialization/submission failures remain fail closed and produce only safe diagnostics.

## A6. Recreate false-positive and minimal repair sequence

_wait_config_entry(), line 238, returns an on-disk entry before checking container state or logs.
After recreation the previous storage file still exists, so the test can immediately return the old entry; _container_running() only proves a process exists.

Required sequence:
1. Bind Broker directory/password ownership to the actual Broker UID/GID before read-only mounting. Recommended restrictive modes: directory 0700 and password 0600 owned by Broker. Read-test as that UID; do not solve with 0777, anonymous access, or root Broker.
2. Add Broker state/log collection and bounded readiness.
3. Use shared-container networking for the bootstrap gate, clearly separated from the production topology gate.
4. Apply Mapping fix and strengthen its real-type unit regression.
5. Require a fresh outcome from each HA process: bootstrap created/already-matches, MQTT entry loaded/connected, and actual authenticated Broker connection. Retained disk data alone is insufficient.
6. On recreate, verify new container/process identity, completion of current startup, same entry_id, exactly one MQTT entry and no mismatch. Keep the original config volume; do not clear .storage to pass.
7. Add failure controls: unreadable Broker password produces a startup-class diagnostic; wrong MQTT password produces authentication failure; changed existing entry is rejected; old storage plus failed current bootstrap cannot pass.
8. Run exact-image isolated CI once after this coherent patch; diagnose the first failed stage if it still fails.

Read-only inspection of HA's storage file for evidence is not direct editing. Prefer read checks inside the HA container when host UID cannot read the file. Never loosen HA secret owner/mode requirements to make the test runner read them.

## Local validation performed

Actual reviewed Python methods were imported without modification.

Results:
MATCH_DICT=True
MATCH_REAL_HA_MAPPING=False
RECREATE_PRODUCT_RESULT=existing_entry_mismatch
OLD_STORAGE_RETURNED=True
NEW_BOOT_CHECKS_BEFORE_RETURN=0

A proposed Mapping-only correction was evaluated in memory, without modifying repository source:
PROPOSED_MAPPING_FIX_EXACT_ENTRY=PASS
PROPOSED_MAPPING_FIX_WRONG_PASSWORD_REJECTED=PASS

These are targeted host checks, not a Home Assistant runtime or Docker acceptance.
Docker is unavailable in this review environment; the failed CI was read, not rerun.
An attempted OS ownership probe could not set an arbitrary UID in this environment (EINVAL); no permission-runtime PASS is claimed. Broker permission classification rests on reviewed test/source semantics pending captured container logs.

## A7. Automatic bootstrap decision

AUTOMATIC_BOOTSTRAP_ROUTE=RETAIN
MANUAL_UI_AS_DEFAULT_REPLACEMENT=NOT_RECOMMENDED

The official config flow exists and the submitted shape matches the pinned version. The network preflight failure and small data-type bug do not prove the architecture infeasible.
Manual official UI remains a separately controlled fallback/diagnostic route; using it does not satisfy automatic clean-install acceptance.
Do not edit .storage or automate UI as a shortcut.

## A8. Before T1 S20 preflight / deployment

Before marking source ready for T1 read-only preflight:
- close the confirmed product and test defects;
- real HA isolated first-start and recreate acceptance passes with corrected oracles;
- relevant unit/security/deployment gates pass;
- bind reviewed source, HA/Mosquitto image digests and target ARM64 availability;
- freeze automatic install order, three-identity secret handoff and failure diagnostics.

T1 read-only preflight then collects:
- actual Compose: HA/Manager host networking, no published ports; Broker correct dual networks;
- host 1883 exclusively IPv4 loopback, 8883 expected guarded TLS publication;
- actual consumers' UID/GID and read-only secret mounts;
- three independent service credentials and distinct roles; no real node credential pre-created;
- exact Dynamic Security/ACL candidate and positive/negative test evidence;
- clear fresh-state paths/ownership, rollback and later deployment authorization.

The password_file bootstrap test is not production Dynamic Security or ACL validation. Use isolated test service accounts for positive/negative ACL checks. Real T1 network runtime, listener exposure and actual HA connection remain live acceptance requirements after separately authorized deployment.

No test pass itself authorizes production account creation, starting Broker, opening host ports, changing HA, accessing boards or merging PR.

## Sources

Project files at review head:
- tests/tools/test_n3w_ha_mqtt_bootstrap_isolated_runtime.py
- tests/tools/test_n3w_ha_mqtt_bootstrap_component.py
- infra/n3w-t1/homeassistant/custom_components/n3w_mqtt_bootstrap/__init__.py
- .github/workflows/n3w-t1-ha-bootstrap-isolated-ci.yml
- tools/n3w_t1_clean_product_deployment_gate.py

Upstream:
- https://github.com/eclipse-mosquitto/mosquitto/blob/5b74cce8a4fe2a73b57df6c703bfde2cfd535d60/docker/2.1-alpine/docker-entrypoint.sh
- https://github.com/eclipse-mosquitto/mosquitto/blob/5b74cce8a4fe2a73b57df6c703bfde2cfd535d60/docker/2.1-alpine/Dockerfile
- https://github.com/eclipse-mosquitto/mosquitto/blob/v2.1.2/src/mosquitto.c
- https://github.com/eclipse-mosquitto/mosquitto/blob/v2.1.2/src/password_file.c
- https://www.mosquitto.org/documentation/authentication-methods/
- HA exact files and Docker documentation linked above.

## Closure

REVIEW_RESULT=REPAIR_REQUIRED
LATEST_TCP_FAILURE_CAUSE=FILE_PERMISSION_DEFECT_PRIMARY_SUSPECT_PENDING_BROKER_LOG
CONFIRMED_PRODUCT_DEFECT=CONFIG_ENTRY_MAPPING_TYPE_REJECTION
CONFIRMED_TEST_DEFECT=STALE_STORAGE_RECREATE_FALSE_POSITIVE
T1_PRODUCTION_TOPOLOGY_CHANGE_REQUIRED=false
READY_FOR_PRODUCTION_DEPLOYMENT=false
NEXT_ONE_GATE=N3W_T1_S20_HA_BOOTSTRAP_PERMISSION_MAPPING_AND_RUNTIME_ORACLE_REPAIR_20261010_01
