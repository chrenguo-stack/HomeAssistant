# N3-W T1 storage headroom and image lifecycle source implementation progress — 2026-11-10

## 1. Gate

```text
GATE=T1_STORAGE_HEADROOM_AND_IMAGE_LIFECYCLE_CLOSURE
PR=800
LIVE_T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false
BROAD_DOCKER_PRUNE=false
KF147_LIVE_RETRY=false
```

This gate follows the accepted design in
`N3W_T1_CORE_STACK_IMAGE_LIFECYCLE_AND_POST_ACCEPTANCE_CLEANUP_POLICY_20261109.md`
and the accepted Home Assistant storage-policy evidence in
`N3W_T1_CORE_UPDATER_HOMEASSISTANT_STORAGE_POLICY_REVIEW_CLOSURE_20261105.md`.

It does not delete any live T1 image and does not claim the current T1 is already at the
steady-state image inventory.

## 2. Root-cause boundary

The 2026-11-10 runtime outage already proved root-filesystem ENOSPC as the primary service
outage cause. The source closure therefore addresses two independent recurrence paths:

1. component predecessor images remained indefinitely after successful product acceptance;
2. a future large artifact could be streamed to T1 before a fresh capacity calculation had
   proven staging + image import + reserve fit together.

The secondary Docker/Compose versus containerd-task divergence remains proven as a separate
runtime fact. This gate does not claim ENOSPC directly caused that secondary divergence.

## 3. Image lifecycle implementation

Generic V2 remains rollback-capable through `COMMITTED`. Apply does not automatically remove
the predecessor image.

A new explicit `finalize` operation is available only after an independent product acceptance
authority binds the exact committed transaction:

```text
t1-core-updater finalize
  --acceptance-authority <exact acceptance JSON>
  --confirmation T1_CORE_UPDATER_FINALIZE
```

The acceptance record binds:

- component;
- exact committed-transaction SHA-256;
- accepted target image ref;
- acceptance authority ID;
- acceptance timestamp;
- result PASS.

The committed-transaction digest is calculated from the stable pre-cleanup transaction authority,
so adding cleanup metadata does not invalidate the acceptance binding.

### Exact cleanup guards

For Manager and Broker, finalize requires all of the following before image deletion:

1. V2 transaction is `COMMITTED`;
2. component is Manager or Broker;
3. independent acceptance exactly matches component, target and transaction digest;
4. no active unresolved legacy transaction;
5. no active unresolved HA-USB transaction;
6. mutation-safety guard passes;
7. current target runtime is still the exact target runtime image ID;
8. peer runtime and A1 policy remain valid;
9. predecessor ref still resolves to the exact predecessor image ID recorded by the transaction;
10. predecessor is not a current product image binding;
11. no Docker container, including stopped/non-product containers, references the predecessor image ID.

Deletion is then exactly:

```text
docker image rm sha256:<exact-predecessor-image-id>
```

No `--force`, wildcard deletion, age-based deletion, `docker system prune`, or
`docker image prune -a` is used.

After deletion the target, peer runtime and A1 health are revalidated. Transaction metadata is
retained and records one of:

```text
ACCEPTED_CLEANUP_PENDING
ACCEPTED_CLEANUP_COMPLETE
CLEANUP_STOPPED
```

Once accepted cleanup begins, the rollback window is closed. A cleanup failure is fail-closed and
does not silently recreate or broadly prune storage.

Home Assistant is intentionally excluded from Generic V2 finalize. Its predecessor lifecycle remains
owned by the mandatory-USB transaction, including the U10 predecessor-capacity-release boundary.

## 4. Cross-transaction accumulation guard

A committed Manager/Broker transaction without
`cleanup_state=ACCEPTED_CLEANUP_COMPLETE` blocks the next Generic V2 apply.

The existing Home Assistant mandatory-USB transaction source is historical exact-source authority for the
accepted R7A activation package and is intentionally not modified by this gate. A future HA-USB package or
preflight must apply the shared pre-transfer capacity policy before large staging; this source gate does not
claim a new HA-USB cross-transaction blocker.

## 5. Pre-transfer storage admission policy

Repository authority:

`infra/n3w-t1/updater-releases/storage-image-lifecycle-policy.json`

The policy freezes:

```text
STEADY_STATE_INTERNAL_GENERATIONS_PER_COMPONENT=1
BROAD_DOCKER_PRUNE_ALLOWED=false
RUNTIME_MIN_FREE_REQUIREMENT=UNFROZEN_LONGITUDINAL_EVIDENCE_REQUIRED
MAINTENANCE_RESERVE_IS_RUNTIME_MINIMUM=false
```

The reusable pre-transfer capacity contract is:

```text
FREE_BYTES
>=
EXACT_STAGED_TRANSPORT_BYTES
+ EXACT_IMAGE_IMPORT_WORST_CASE_BYTES
+ DERIVED_POST_PEAK_RESERVE_BYTES
```

The reserve is derived from fresh evidence:

```text
RAW_RESERVE =
max(
  1 GiB,
  10% of measured filesystem total,
  8 * measured mutable allocated bytes
)

DERIVED_POST_PEAK_RESERVE =
round RAW_RESERVE upward to the next 256 MiB
```

The accepted 2026-11-05 evidence reproduces 1,610,612,736 bytes (1.5 GiB). That value remains
maintenance-admission evidence, not a permanent product-runtime minimum.

Image import worst case is derived from the exact Docker-save archive by summing regular-file
member sizes. It is not guessed from compressed archive size.

Zero free bytes and zero mutable allocation are valid observations: zero free produces a normal
capacity STOP rather than a malformed-evidence result.

## 6. Storage-topology authority

Before the capacity arithmetic is trusted, the reusable policy validates that:

- staging is not tmpfs/ramfs;
- image store backend is resolved as classic Docker or containerd;
- image-store root authority is resolved;
- staging, Docker root and actual image-store root are on the same device;
- free-byte observations are non-negative.

If the three storage locations are on different devices, the shared-device formula is rejected
rather than silently applying one filesystem's free bytes to another.

## 7. Source implementation

```text
tools/n3w_t1_core_updater.py
tools/n3w_t1_core_updater_finalize.py
tools/n3w_t1_core_updater_host.py
tools/n3w_t1_core_updater_v2.py
tools/n3w_t1_storage_image_lifecycle.py
infra/n3w-t1/updater-releases/storage-image-lifecycle-policy.json
tests/tools/test_n3w_t1_core_updater_a2.py
tests/tools/test_n3w_t1_storage_image_lifecycle.py
.github/workflows/n3w-t1-storage-image-lifecycle-ci.yml
```

## 8. Validation matrix

Focused regression coverage includes:

1. Manager exact predecessor finalize PASS;
2. Broker exact predecessor finalize PASS;
3. Generic HA finalize rejected;
4. wrong acceptance transaction digest rejected;
5. any container reference blocks deletion;
6. exact Docker image-ID deletion only;
7. no `--force` / prune path;
8. cleanup completion closes rollback;
9. new Generic V2 apply blocked before Manager/Broker cleanup;
10. historical R7A HA-USB exact-source blobs remain unchanged;
11. accepted 1.5 GiB reserve evidence reproduced;
12. zero mutable allocation handled;
13. zero free space yields capacity STOP;
14. staged transport + import + reserve are all counted;
15. Docker-save import worst case is computed from exact regular members;
16. unsafe archive link members rejected;
17. split storage devices rejected;
18. memory-backed staging rejected;
19. broad-prune policy cannot be enabled.

## 9. CI state at this archive point

```text
SOURCE_IMPLEMENTATION=COMPLETE
FOCUSED_CI_FINAL_RESULT=PENDING
LIVE_T1_MUTATION=false
CURRENT_T1_IMAGE_CLEANUP_EXECUTED=false
KF147_CAPACITY_GATE_EXECUTED=false
KF147_LIVE_RETRY=false
```

The final gate may be promoted to CLOSED_PASS only after the exact final source head completes the
focused storage/image-lifecycle CI successfully.

## 10. Next boundary

After this gate closes, KF-147 must restart from fresh authority:

```text
KF147_FRESH_REBIND
-> FRESH_CAPACITY_GATE
-> NEW_PACKAGE_MANIFEST_BINDING
-> LIVE_RETRY
```

The fresh capacity gate must use the new policy before streaming a large payload. A failed capacity
gate is a STOP. It does not authorize broad Docker cleanup.
