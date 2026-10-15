# N3-W T1 F4 Runtime Acceptance Manager Socket Probe Source Repair Progress — 2026-10-15

~~~text
TASK=N3W_T1_F4_RUNTIME_ACCEPTANCE_MANAGER_SOCKET_PROBE_SOURCE_REPAIR_20261015_01
STATUS=IMPLEMENTED_PENDING_CI_AND_REVIEW

BASE_SOURCE_HEAD=ffcbb1a890e42ac776c6d90000bf3f25195da01d
FAILED_LIVE_GATE=N3W_T1_F4_RUNTIME_ACCEPTANCE_LIVE_20261015_01
FAILED_ERROR_CODE=manager_mqtt_socket_count_invalid
FAILED_POST_STAGE=STOPPED_RUNTIME_ACCEPTANCE
FAILED_ROLLBACK_PROVEN=true
FAILED_ACCEPTANCE_AUTHORIZATION=CONSUMED_NO_REPLAY

LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
MERGE=false
~~~

## Evidence closure

The real T1 runtime acceptance failed while the source required exactly one established Manager MQTT TCP socket to
remote port 8883.

Stopped-state forensics then established:

- Manager runtime user is exactly `999:999`;
- Manager `CapDrop=["ALL"]`;
- Manager `SecurityOpt=["no-new-privileges:true"]`;
- Manager has a private PID namespace and host network mode;
- Broker retained logs prove the authenticated Manager client stayed connected from
  `2026-10-15T14:32:15.264549180Z` until the fail-closed stop at
  `2026-10-15T15:30:36.082122041Z`;
- Manager container finished at `2026-10-15T15:30:36.088141749Z`, with restart_count=0 and OOMKilled=false;
- therefore the Broker-side Manager session remained alive through the acceptance failure and only disconnected when
  rollback stopped the container.

The source-side socket probe ran:

~~~text
docker exec --user 0:0 <manager-container> python3 ...
~~~

Inside the container it filtered `/proc/net/tcp*` candidate inodes by walking `/proc/<pid>/fd/*`. That forced the
probe to UID 0 even though the target Manager process runs as UID/GID 999:999 with all capabilities dropped.

The live evidence and runtime security contract therefore contradict the probe's forced-root ownership walk, not the
Manager MQTT session itself.

## Repair

The repair is deliberately narrow:

1. remove the forced `--user 0:0` from `_container_established_socket_count()`;
2. let `docker exec` inherit each container's configured runtime user;
3. preserve the existing inode ownership filtering and exact socket-count contract;
4. preserve the exact Manager requirement of one established remote-8883 socket over the full stability window;
5. include the observed bad count in the error code:
   `manager_mqtt_socket_count_invalid:<count>`.

This keeps Manager probing aligned with UID/GID 999:999 while Home Assistant continues to use its own configured
container user. No capability is added and the Manager container security boundary is not weakened.

## Tests

Added source-level regression tests proving:

- the socket probe no longer injects a Docker `--user` override;
- the configured container user is therefore used;
- an observed bad socket count remains fail-closed and the count is preserved in the error code.

The existing Manager stability test still requires exactly one socket and unchanged container identity/StartedAt.

## Safety boundary

~~~text
FAILED_ACCEPTANCE_AUTHORIZATION_REPLAY=false
RUNTIME_RESTART_AUTHORIZED=false
PERSISTENCE_AUTHORIZED=false
CERTIFICATE_LIFECYCLE_AUTHORIZED=false
REBOOT_AUTHORIZED=false
BOARD_ACCESS=false
~~~

No live retry is allowed from this source-repair gate. A later exact artifact, stopped-state repair/recovery design and
new distinct live authorization are required before touching the real T1 again.
