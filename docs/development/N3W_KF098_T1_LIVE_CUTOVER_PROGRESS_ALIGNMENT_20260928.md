# N3-W KF-098 T1 Live Cutover Progress Alignment — 2026-09-28

Status: `CUTOVER_PASS_REAL_BOARD_ACCEPTANCE_PENDING`

## Scope

This document records the public-safe repository/runtime alignment after the KF-098 Manager source repair and exact T1 live cutover. It does not claim final Board discovery acceptance.

```text
MAIN_AT_CUTOVER=88e9d140e5baddba543a961f003d12f7ce563ed2
KF098_SOURCE_REPAIR=PASS
KF098_T1_LIVE_CUTOVER=PASS
KF098_MANAGER_RUNTIME=PASS
KF098_REAL_BOARD_ACCEPTANCE=PENDING
KF098_STATUS=OPEN
```

## Original live defect

The live T1 had a durable concrete IPv4 in `GH_N3W_PAIRING_ADVERTISED_HOST`. After the T1 LAN changed, simplified pairing discovery still returned that predecessor address. UDP/47111 request/response worked, but the Board did not open HTTP/TCP 47112 to the current T1.

The accepted product design is `GH_N3W_PAIRING_ADVERTISED_HOST=auto`: for every accepted discovery request, Manager derives the route-selected local IPv4 for that request source and returns it without caching a predecessor LAN address.

## Exact Manager authority

```text
SOURCE_SHA=575ce642e372961e21de14a36eba5877082de3cf
SOURCE_TREE=7f1641827b75668aa220832b7663bf81d98633ba

ARTIFACT_RUN_ID=36329597775
ARTIFACT_ID=10935052471
ARTIFACT_NAME=n3w-kf098-manager-exact-source-575ce642
IMAGE_TAR_SHA256=6392b8c9bb87d95404346583d6f44967bd4e20fcc092be393c45f75a4ca7a5b2

IMAGE_CONFIG_DIGEST=sha256:49c9fcc0a17d47678b0667c48a06f9a9475609a757e510ca148983b53ed537e3
IMAGE_MANIFEST_DIGEST=sha256:b806e7c8b97cc757965161a989f954df09427aa7d2700a6503e56e49cc8f9e4f
ROOTFS_LAYERS_SHA256=97dd9fb029f1678a4589148d1874c95cd1d26439efa89ee833d5d734b70d42d6
```

The historical first artifact remains non-deployment authority.

## Executor repair chain

PR #493 changed Manager recreation from current Compose reconstruction to the actual running Manager container contract. Live evidence had proved six Manager bind mounts while the current Compose Manager definition represented only three; using Compose as recreate authority would therefore lose runtime state/secret bindings.

A later pre-mutation attempt exposed old-shadow runtime/security drift caused only by Docker default representations:

```text
HostConfig.Dns:
  live=[]
  shadow=null

HostConfig.OomKillDisable:
  live=null
  shadow=false
```

PR #495 added narrow normalization for these proven-equivalent defaults while continuing to reject non-default DNS or OOM changes.

The first PR #495 live apply then crossed the live-mutation boundary and failed during candidate postcheck:

```text
FAILURE=TCP 47112 listener did not recover
RESULT=FAIL_ROLLED_BACK
ROLLBACK_RESULT=PASS
```

Automatic rollback restored:

```text
OLD_MANAGER_IMAGE_RESTORED=true
MANAGER_ENV_RESTORED=true
MANAGER_PAIRING_RUNTIME_RESTORED=true
MANAGER_RUNTIME_SECURITY_RESTORED=true
BROKER_PRESERVED=true
R5_PRESERVED=true
```

Read-only post-rollback evidence showed the old Manager healthy, exact original manager.env restored, exact six-mount fingerprint restored, all environment/runtime-security fingerprints matching the saved snapshot, Broker restart count still zero, R5 exact, and one listener on each required port. Only Manager lifecycle fields and the already-understood Docker default representation changed across rollback recreation.

PR #496 then repaired the acceptance/reacquire contract:

- base preflight accepts the expected old or rollback-created Manager restart count;
- verified post-rollback reacquire allows only the proven lifecycle/default-representation differences and requires all other frozen state to match;
- candidate postcheck waits for bounded simplified health before asserting TCP/47112 and UDP/47111 listeners;
- unexpected Broker/runtime/security drift remains fail-closed.

PR #496 merged as:

```text
MERGE_COMMIT=88e9d140e5baddba543a961f003d12f7ce563ed2
POSTMERGE_PUBLIC_SAFETY_CI=PASS
POSTMERGE_PUBLIC_SAFETY_RUN_ID=36377968076
```

## Final exact execution

The post-merge package was restaged with:

```text
PACKAGE_REF=88e9d140e5baddba543a961f003d12f7ce563ed2
REMOTE_EXECUTOR_SHA256=c7ad3052dfbbda59513bb87f3ce8bceec0f11062c54eec839d7c58f9ef77ef86
```

Fresh remote preflight passed with the rollback-created old Manager:

```text
MANAGER_IMAGE_ID=sha256:271cd87c88c041f0ef7fa55f6c223615edf42388b8e05a7445862e2b700cdfb5
MANAGER_RESTART_COUNT=0
MANAGER_MOUNT_COUNT=6
MANAGER_MOUNT_HASH=6cb94ab6b78e0a68df458e5dc4d9240cc91c225a1b44bc7eba9454325821bffc
BROKER_RESTART_COUNT=0
R5_FIREWALL_CONTINUITY=PASS
```

The final live apply passed:

```text
FINAL_APPLY_RESULT=PASS
T1_RUNTIME_MUTATION=true
ROLLBACK_ATTEMPTED=false

SNAPSHOT=upgraded_verified_pretransaction
SNAPSHOT_MIGRATION=post-rollback-live-reacquire
OLD_SHADOW_REPRODUCTION=true
NEW_SHADOW_CONTRACT=true

MANAGER_EXACT_IMAGE=true
MANAGER_PAIRING_AUTO=true
MANAGER_MOUNTS_PRESERVED=true
MANAGER_HEALTH=PASS
BROKER_PRESERVED=true
R5_PRESERVED=true

MANAGER_RUNTIME_IMAGE_ID=sha256:b806e7c8b97cc757965161a989f954df09427aa7d2700a6503e56e49cc8f9e4f
```

Therefore the T1 cutover itself is closed PASS. No second cutover or automatic retry is required.

## Post-cutover real-traffic boundary

KF-098 still requires physical acceptance:

```text
1. Board discovery request reaches T1 UDP/47111
2. response candidate.host equals current route-selected T1 IPv4
3. response candidate.host no longer equals predecessor address
4. Board initiates TCP/47112 to current T1
5. expected next pairing disposition is observed
```

A T1 packet-capture self-test proved the read-only capture method and local simplified endpoint:

```text
HEALTH_SELFTEST=PASS
LOCAL_TCP47112_CAPTURE=PASS
EXTERNAL_UDP47111_COUNT=0
EXTERNAL_TCP47112_COUNT=0
```

The target historical registration is still approved, but its pairing activity is old. A fresh 30 s canonical durable-state observation showed:

```text
CANONICAL_SEQ_BEFORE=112
CANONICAL_SEQ_AFTER=112
CANONICAL_SEQ_ADVANCED=false
CANONICAL_LAST_SOURCE=direct
CANONICAL_LAST_UPDATED_AT=2026-09-24T13:28:35.713Z
BOARD_B_CURRENT_RUNTIME_LIVENESS=NOT_PROVEN
```

This absence of traffic is not evidence of a new T1, Board, Broker, or PR #474 product defect. Current Board B liveness must be established independently before deciding whether a new physical pairing-state transition is required.

## Known-failure disposition

KF-098 remains `OPEN`, but its open boundary is now only real Board discovery/HTTP acceptance. Older text saying source repair/live cutover are pending is obsolete.

KF-070 is extended with the live recreate/readiness lessons from this execution: running-container contract is the recreate authority when Compose is incomplete; only proven Docker default representations may be normalized; cross-recreate lifecycle fields are not strict same-container oracles; and bounded health readiness precedes listener acceptance.

KF-078 remains separate. The final execution used the repository-versioned bootstrap/package path successfully; no new stdin/TTY/shell transport root cause is assigned to KF-098.

## Next gate

```text
NEXT_ONE_GATE=N3W_KF098_DYNAMIC_DISCOVERY_REAL_TRAFFIC_ACCEPTANCE_20260928_01
LIVE_T1_RECUTOVER_REQUIRED=false
BOARD_MUTATION_AUTHORIZED=false
T1_RUNTIME_MUTATION_AUTHORIZED=false
PAIRING_REPAIR_AUTHORIZATION=false
```
