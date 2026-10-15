# N3-W T1 Mac 本地 exact artifact cache V1 Mac acceptance 预执行
# 2026-10-15

## 0. Gate

```text
TASK=N3W_T1_MAC_LOCAL_EXACT_ARTIFACT_CACHE_V1_MAC_ACCEPTANCE_20261015_01
AUTHORIZED=true

PR=545
PR_HEAD_AT_ENTRY=c814f6accffba90f7d81cb3f7b88e2a986d6a334
EXECUTABLE_SOURCE_HEAD=d1a7847c1e0612ac80b31b85262011110f329794
SOURCE_CI=14_SUCCESS_0_FAILURE_0_PENDING

T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
EXPLICIT_DEVICE_PROVISIONING=false
F4=false
BOARD_ACCESS=false
MERGE=false
```

Fresh rebind at Gate entry proves that the commits after executable source head are docs-only:
`N3W_CURRENT_STATE.md`, `N3W_CURRENT_STATE_INDEX.md`, and the source-closure document.
No executable source drift exists after the accepted CI head.

## 1. Exact artifact authority

```text
WORKFLOW_RUN_ID=38694709028
ARTIFACT_ID=11953163662
ARTIFACT_NAME=n3w-t1-fresh-bootstrap-deployable-d1a7847c1e0612ac80b31b85262011110f329794
ARTIFACT_ZIP_SHA256=6f0ec341494bc6ba2a9b9d03a2c3968b708241dd069408a3dc72f63f3e79a89c
RUNTIME_PAYLOAD_SHA256=4d7e07abc95797730a591c51a011a262c2955d07547f25c37953a20c1ee826f2
PAYLOAD_MANIFEST_SHA256=a20e3ea0eec383e4373f4d2500a9763e26c8c8c041b686f167c1117368863cef
```

GitHub reports this artifact unexpired and exact post-upload binding PASS.

The artifact embeds the already-consumed R4 authorization identity. That identity is evidence only in this Gate.
No T1 apply may be invoked, and R4 replay remains forbidden.

## 2. Mac target

Default persistent store:

```text
~/Documents/N3W/exact-artifacts
```

The acceptance command does not checkout or modify the local repository. It obtains the exact host-wrapper
file from commit `d1a7847...` with `git show`, then invokes only local artifact/cache functions.

## 3. Acceptance contract

One Mac command must prove:

1. the exact source commit is available;
2. the exact host wrapper is extracted without checkout;
3. the first cache acquisition is either:
   - `MISS_POPULATED`, meaning GitHub large artifact was downloaded once and atomically persisted; or
   - `HIT`, meaning a pre-existing exact entry already passed strict binding and ZIP re-hash;
4. after extraction, runtime payload, manifest, capacity, and all three image artifact bindings PASS;
5. a second acquisition returns exactly `HIT`;
6. during the second acquisition, GitHub metadata and large-download functions are replaced by hard-fail sentinels, proving the verified cache-hit path does not call GitHub;
7. the final cache entry contains exactly `artifact.zip` and `binding.json`;
8. the persisted ZIP SHA-256 equals the exact GitHub digest.

## 4. Failure boundary

Any exception or SHA/binding mismatch is STOP.

Do not delete or overwrite an existing invalid cache entry automatically.
Do not access T1 as part of recovery.

## 5. Expected public-safe result

Successful output must include a single final JSON document containing at least:

```text
status=PASS
first_acquisition=HIT|MISS_POPULATED
second_acquisition=HIT
cache_entry=~/Documents/N3W/exact-artifacts/<artifact_id>/<sha256>
artifact_zip_sha256=<exact sha256>
source_head=d1a7847...
manifest_source_head=d1a7847...
second_hit_github_access=false
t1_access=false
production_service_start=false
explicit_device_provisioning=false
f4=false
board_access=false
```

## 6. STOP

This Gate now stops for the physical Mac operator to run the exact Terminal command.
No T1 or board action is authorized.
