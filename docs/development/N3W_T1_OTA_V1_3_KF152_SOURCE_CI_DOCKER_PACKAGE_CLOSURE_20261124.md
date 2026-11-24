# N3-W T1 OTA V1.3 KF-152 source / CI / real-Docker / package closure

`KF=KF-152`
`CLOSURE_DATE=2026-11-24`
`STATUS=GUARDED`

## 1. Historical physical evidence

R8V13-07 Attempt A used transaction `463c8065eea5ada915074194058ee45880ddab2c94d06715c82f09fb84481969`.

Observed terminal state:

```text
STATUS=ROLLED_BACK
PHASE=U8_RECOVERY_ADMISSION_COMPLETE
FAILURE_CODE=ha_usb_pre_cutover_interrupted
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
RECOVERY_REQUIRED=false
PRE_CUTOVER_PREDECESSOR_RESTORED=true
PREDECESSOR_RELEASE_INTENT=false
PREDECESSOR_RELEASE_OBSERVED=false
TARGET_LOAD_IDENTITY=false
HA_DATA_RESTORE=false
```

The predecessor HA 2026.10.4 and Manager were automatically restarted; Broker remained running. This proves pre-cutover automatic recovery. It does not prove full U13B rollback because no predecessor release or target import occurred.

The live predecessor image had one exact RepoTag and one same-repository RepoDigest. The old source rejected every nonempty RepoDigests list. That incompatibility is confirmed and exactly overlaps the U8→U9 release gate. The historical worker did not preserve the original first exception, so KF-152 is not claimed as the uniquely proven historical trigger.

## 2. Repair

Product source repair:

```text
PRODUCT_SOURCE_HEAD=6b6c735ae12a253a62dd64b0adedb90b6c5ad03f
```

The shared image-reference predicate now:

- requires the exact expected tag for predecessor release;
- allows valid same-repository SHA256 digest aliases;
- rejects extra tags, foreign/mixed repository digests, malformed/scalar digest metadata;
- keeps runtime image identity, protected mounts, other-container-user checks and non-force image removal;
- applies the same ownership semantics to target release during rollback, with the already-bound rollback target permitted to be untagged;
- checks incompatible predecessor metadata before application stop;
- preserves bounded safe failure diagnostics during pre-cutover recovery.

## 3. Regression and real Docker proof

Integration/test head:

```text
DOCKER_INTEGRATION_HEAD=71260221ebcbc1e4f461dc7f3cea842e0406616a
```

Evidence:

- HA focused regression: 327 passed, 1 skipped.
- Install and rollback fixtures both use nonempty same-repository RepoDigests.
- Parameterized ownership regression covers exact/empty/same/multiple-same/foreign/mixed/malformed/scalar/extra-tag/untagged cases.
- Shared-user negative path rejects release before authorization consumption / image deletion.
- Real Docker Engine integration pulls a real image with one RepoTag and nonempty same-repository RepoDigest, verifies no users, executes exact product semantics `docker image rm --no-prune <image-id>`, and verifies image ID/tag absence: PASS.

## 4. Exact CI and package closure

Final CI closure head:

```text
CI_CLOSURE_HEAD=9339ab22fc29ddd14d2e147d13e616ccebed945b
CI=22/22 SUCCESS
FAILURE=0
PENDING=0
```

HA target-binding run:

```text
RUN_ID=45317562079
RESULT=SUCCESS
RECOVERY_ARTIFACT_ID=14885876408
RECOVERY_ARTIFACT_NAME=n3w-t1-ha-recovery-install-9339ab22fc29ddd14d2e147d13e616ccebed945b
RECOVERY_ARTIFACT_DIGEST_SHA256=23289a67fd60051ac60d4392f690917134c3076d3d8aeb9226eae9a37d52407c
RECOVERY_INSTALL_MANIFEST_SHA256=6792c681b61404d7a6a31e1bd78f25e6332d89a147d2639f2c4b6a1b705bdd89
RECOVERY_PYZ_SHA256=d3e844a05571e94ef384aa62fd4763f2d53c253f281cb94f30dd37ca19743b30
```

Fresh exact ARM64 run:

```text
RUN_ID=45317562014
RESULT=SUCCESS
ARTIFACT_ID=14886237329
ARTIFACT_DIGEST_SHA256=ed70e7e2fc9a010cca20ae128c2f4afc030f3bc3a60716aee683a69860574287
POST_UPLOAD_EXACT_BINDING=PASS
```

The preceding same-job artifact download race was reproduced twice and repaired by moving post-upload download/binding verification into a dependent job. That CI defect was separate from KF-152 product logic.

## 5. Closure boundary

```text
KF152=GUARDED
SOURCE_REPAIR=PASS
BIDIRECTIONAL_REGRESSION=PASS
REAL_DOCKER_RELEASE=PASS
EXACT_PACKAGE=PASS
FINAL_CI=PASS

HISTORICAL_TRANSACTION_REPLAY=false
LIVE_KF152_REPAIR_DEPLOYED=false
R8V13_07=FRESH_PHYSICAL_REACCEPTANCE_PENDING
R8V13_08=BLOCKED
BROKER_OTA=DEFERRED
T1_MUTATION_AUTHORIZED=false
```

KF-152 is closed as a guarded defect. The next physical attempt is not a replay of the historical transaction and is not part of this closure. It must fresh-rebind the spare T1, verify the live predecessor/control plane/USB state, bind this exact recovery package, then obtain a new explicit live authorization before any updater patch, fresh transaction, INSTALL/cutover or recovery mutation. A distinct failure in the fresh physical attempt must be classified independently and, if necessary, assigned a new KF.
