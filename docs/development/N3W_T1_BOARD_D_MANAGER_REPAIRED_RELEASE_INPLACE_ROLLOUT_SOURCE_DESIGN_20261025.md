# N3W T1 Board D Manager repaired-release in-place rollout source design

Date: 2026-10-25

## 1. Gate

```text
TASK=N3W_T1_BOARD_D_MANAGER_REPAIRED_RELEASE_INPLACE_ROLLOUT_SOURCE_DESIGN_20261025_01
REPOSITORY=chrenguo-stack/HomeAssistant
SOURCE_HEAD=03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6
SOURCE_TREE=279914967d0368254e6c56283d59b182a0b8537a
LIVE_T1_ACCESS=false
LIVE_T1_MUTATION=false
BOARD_ACCESS=false
```

This gate designs a repository-owned in-place rollout for only the greenhouse-manager
container on the already-running T1 used by Board D first-pair acceptance.

It does not authorize rollout execution.

## 2. Exact repaired-release authority

```text
FINAL_WORKFLOW_RUN_ID=40196818619
FINAL_WORKFLOW_RUN_ATTEMPT=1
FINAL_ARTIFACT_ID=12600666626
FINAL_ARTIFACT_NAME=n3w-t1-f5-v2-exact-production-release-03dab2bd04e7e8cb71faa1bd13a027ace8cecdf6
FINAL_ARTIFACT_ZIP_SHA256=c5a324940cfcad25d3cbc70d13adc988bbfa1a9994732a55daab460399845822
RELEASE_ID=c4df6f80d779f4091de6dc17df9e7c82131fe4c43da1f2e46df884b541e58b83
RELEASE_SHA256=47afb04dd9b518218cc03fbbec47e21efb8599957f728e353a83010dff9d1a1b
LOCAL_EXACT_RELEASE_VALIDATION=PASS
```

The F3 exact-main Manager image is source-derived and must be loaded under the
artifact-owned tag:

```text
local/greenhouse-manager:fresh-03dab2bd04e7
```

The rollout must derive and verify the exact Manager tar SHA/config identity/rootfs
identity from the locally verified release. No historical image identity is deployment
authority.

## 3. Why the normal production paths are rejected

### 3.1 Full F5 production executor

The V2 production executor begins with fresh-Armbian qualification. That qualification
requires Docker and all product material to be absent.

The current T1 is an already-running product host, so the normal executor would correctly
return `FAIL_REFLASH_REQUIRED`. It is not an in-place update mechanism.

### 3.2 Fresh product staging

Fresh staging also owns first installation of instance state and requires product paths,
containers and runtime material to be absent. It must not be used against the existing
Board D T1 because it would cross the preservation boundary for pairing history.

### 3.3 Historical KF-098 live cutover

The KF-098 cutover is historical, root-cause-specific and topology-specific. Its exact
paths, mount counts, environment assumptions and advertised-host migration semantics are
not current execution authority.

Its safety pattern may be reused conceptually:
- freeze old runtime identity;
- preserve an old-image rollback route;
- verify exact new image before cutover;
- mutate only Manager;
- prove rollback or success explicitly.

## 4. Required execution model

The rollout has two independent commands:

```text
manager-rollout-inspect
manager-rollout-apply
```

`manager-rollout-inspect` is strictly read-only and does not consume an authorization.

`manager-rollout-apply` requires a new explicit one-shot authorization. The authorization
is durably claimed before the first target mutation and is never reusable.

The existing consumed first-pair authorization, successor-recovery authorization, or any
later Gate-B first-pair authorization must not be accepted as the rollout authorization.

## 5. Host-side authority

The host wrapper must reuse `n3w_t1_ssh_transport.py` and exact known-host binding.

It must consume:
- exact locally verified production release ZIP;
- run metadata;
- artifact metadata;
- local binding JSON;
- exact repository checkout at SOURCE_HEAD;
- exact target SSH known-host identity.

Before opening an SSH mutation path, it must re-run the same local release bundle
verification or an equivalent strict binding that proves:
- final workflow/run/artifact identity;
- ZIP SHA-256;
- release ID and release SHA-256;
- source head/tree;
- exact required artifact set;
- nested F3/F4 bindings;
- exact `v2_mac_tools` bytes.

The wrapper must safely extract only the exact Manager image tar and its image identity
record required by the rollout.

## 6. Read-only T1 preflight

The inspect gate must capture, without secrets or raw private locator output:

### 6.1 Host/product identity
- current host_instance_id and system_id fingerprints;
- exact production Compose path and SHA-256;
- exact compose environment path metadata;
- rendered Manager service contract;
- Manager network mode, user, read-only state, tmpfs, security options and mount binding hash.

The installed fresh-product Compose must resolve Manager image through
`GH_MANAGER_IMAGE`. A hard-coded/unknown image contract is STOP.

### 6.2 Runtime baseline
Capture exact:
- Broker container ID, image ID/ref, restart count, StartedAt;
- Manager container ID, image ID/ref, restart count, StartedAt;
- Home Assistant container ID, image ID/ref, restart count, StartedAt;
- current `GH_MANAGER_IMAGE` tag from the compose environment;
- current Manager image content identity.

Broker and Home Assistant are immutable continuity anchors for this rollout.

### 6.3 Pairing exposure
Require:
- dynamic pairing window CLOSED;
- pairing UDP/47111 listener absent;
- pairing HTTP/47112 listener absent;
- setup-secret pairing socket absent;
- Manager pairing-control socket healthy.

### 6.4 Pairing/security logical state
Require the Board D successor-recovery candidate shape:
- registrations = 1;
- current registration has no node_id and no logical_location_id;
- current session belongs to that registration;
- current session is pending but expired-by-clock, or already expired/expired;
- all sessions belong to one hardware identity;
- no session approved;
- no node_id lease;
- no registration-node history;
- no retirement outbox;
- no registration event with assigned node/logical-location identity;
- credential assignments = 0;
- peer trust records = 0;
- application-key active nodes = 0;
- application-key epochs = 0.

Only SHA-256 identities are emitted publicly.

### 6.5 Startup mutation boundary
Current Manager startup does not automatically call `expire_pending()` while the
dynamic pairing window is CLOSED. Therefore the rollout postcondition is exact logical
pairing/security state continuity. The later successor-recovery gate alone owns
`pending -> expired -> abandoned`.

## 7. Apply transaction

After the new rollout authorization is durably claimed:

1. Re-read and compare the complete inspect baseline.
2. Create a private remote transaction record containing only safe bindings/hashes and
   runtime IDs; authorization is consumed/non-replayable.
3. Create a private temporary staging directory.
4. Transfer only the exact Manager image tar.
5. Verify remote tar SHA-256 before `docker load`.
6. Load the new Manager image without deleting or retagging the old image.
7. Verify the exact new tag resolves to the expected config/rootfs identity.
8. Re-check Broker/Manager/HA baseline and pairing/security state before cutover.
9. Freeze a private backup of the compose environment file.
10. Atomically replace only the `GH_MANAGER_IMAGE` value. All other bytes/values must be
    proven unchanged by a normalized-excluding-image hash.
11. Render Compose and prove only Manager image changes; topology, mounts, environment,
    network mode, user and security settings remain unchanged.
12. Recreate only Manager with no dependency recreation.
13. Wait for the new Manager to be running and MQTT-connected.
14. Prove the new Manager exposes `greenhouse-manager-pairing recover-expired-first`
    with hash-only arguments.
15. Prove pairing window remains CLOSED and no 47111/47112 exposure is present.
16. Prove pairing/security DB logical state is exactly unchanged from pre-cutover.
17. Prove Broker and Home Assistant container IDs/restart counts/StartedAt are unchanged.
18. Close the rollout transaction `CLOSED_PASS`.

Expected Manager container ID changes. That is not failure.

## 8. Rollback

If failure occurs after the environment switch or Manager recreation and rollback remains
safe:

1. Restore the exact previous compose environment bytes atomically.
2. Render Compose and prove old Manager image binding restored.
3. Recreate only Manager.
4. Prove old Manager image/runtime contract restored.
5. Prove Broker and Home Assistant continuity.
6. Prove pairing/security logical state did not change.
7. Prove pairing exposure CLOSED.
8. Close transaction as terminal rollback PASS/failure; authorization remains consumed.

If rollback cannot be proven, stop with explicit UNKNOWN/unsafe state and do not proceed to
successor recovery.

The executor must never delete either old or new Manager image during this gate.

## 9. Successor gate ordering

Only this order is valid:

```text
LOCAL_EXACT_RELEASE_VALIDATION=PASS
-> MANAGER_ROLLOUT_INSPECT=PASS
-> NEW_EXPLICIT_MANAGER_ROLLOUT_AUTHORIZATION
-> MANAGER_ROLLOUT_APPLY=CLOSED_PASS
-> stage exact-reviewed n3w_t1_first_pairing_onboarding.py
-> successor-inspect=PASS
-> NEW_EXPLICIT_SUCCESSOR_RECOVERY_AUTHORIZATION
-> successor-recover=CLOSED_PASS
-> NEW_EXPLICIT_FIRST_PAIR_AUTHORIZATION
-> fresh pairing window
```

No authorization from one gate may be reused by another.

## 10. Tests required before live use

Focused source tests must prove:
- inspect is read-only;
- private locator/secret values never appear in reports;
- exact release / Manager image binding failures stop before SSH mutation;
- non-fresh Compose contract stops;
- active pairing window/listener stops;
- security material or prior node identity stops;
- authorization is claimed before first target mutation;
- image tar SHA mismatch stops before load;
- new image identity mismatch stops before env mutation;
- env edit changes only `GH_MANAGER_IMAGE`;
- Compose rendered delta is Manager-image-only;
- only Manager recreate is permitted;
- Broker/HA continuity violation triggers failure;
- DB logical drift triggers rollback/failure;
- missing recovery capability triggers rollback;
- rollback restores old env/image/runtime and remains terminal/no-replay;
- success leaves old image available and records CLOSED_PASS;
- source/tool/release binding rejects drift.

## 11. Current classification

```text
SOURCE_DESIGN=FROZEN_FOR_IMPLEMENTATION
FULL_F5_EXECUTOR_FOR_CURRENT_T1=REJECTED
FRESH_STAGING_FOR_CURRENT_T1=REJECTED
KF098_EXECUTOR_REPLAY=REJECTED
DEDICATED_MANAGER_INPLACE_ROLLOUT_REQUIRED=true
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
LIVE_ROLLOUT_AUTHORIZED=false
```
