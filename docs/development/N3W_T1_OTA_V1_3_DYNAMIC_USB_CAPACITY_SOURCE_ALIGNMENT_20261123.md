# N3W T1 Core Stack OTA V1.3 dynamic USB capacity source alignment

Date: 2026-11-23

## Architecture authority

`docs/development/N3W_T1_CORE_STACK_OTA_PRODUCT_ARCHITECTURE_V1.3_20261123.md`

Architecture blob: `4f2a2a269ca492f5787b25a869a5a38889ae6aaa`.

V1.3 supersedes V1.2 for future implementation and acceptance. V1.2 remains historical evidence.

## Frozen product rule

```text
USB_PRODUCT_MIN_CAPACITY_GB=16
USB_MEASURED_USABLE_CAPACITY_MIN_BYTES=15032385536
STATIC_GENERIC_USB_RESERVE=REJECTED
PER_OPERATION_DYNAMIC_CAPACITY=true
```

The product requires a 16GB-or-larger USB. Runtime does not trust a marketed capacity label or mechanically require 16,000,000,000 raw bytes; the machine-verifiable media gate remains at least 14 GiB measured usable filesystem capacity. This media gate does not prove a particular OTA operation has sufficient remaining space.

Every variable-size write performs a fresh current-free-space check immediately before the write:

1. target: approved exact archive size;
2. predecessor: read-only exact `docker image save` byte measurement, then current free-space check, then formal export;
3. protected HA data: after quiesce, use the same tar/gzip/encryption pipeline in count-only mode, then current free-space check, then formal backup.

Fixed constants are allowed only for bounded metadata/filesystem atomic-write overhead. They must not stand in for future variable payloads.

If protected-data capacity is insufficient after first stop, the existing pre-cutover recovery responsibility restarts and verifies the predecessor. The capacity cause remains visible through the durable transaction/status path.

## Source implementation

Executable code head:

`5b45e893181d09deed1f47d588bb1099964e0667`

Exact source/test head:

`51bd2ce8baab2ca0cff4d227765de4583e0f5121`

Implemented changes:

- `USB_PRODUCT_MIN_CAPACITY_GB=16` records the product requirement;
- runtime uses the existing `USB_MEASURED_USABLE_CAPACITY_MIN_BYTES=14*1024**3` machine-verifiable filesystem gate rather than relying on marketing labels or an over-strict raw-byte comparison;
- prepare-authority schema advanced to `gh.n3w-t1-ha-prepare-authority/2` and no longer accepts caller-supplied `max_predecessor_bytes` or `usb_reserve_bytes`;
- install-authority schema advanced to `gh.n3w-t1-ha-install-authority/2`; caller-supplied static USB install/recovery budgets were removed;
- target writes re-read current USB free bytes immediately before the exact-size write;
- predecessor exact archive size is measured from the real export stream after target preparation and immediately before the predecessor write;
- protected-data backup gains same-pipeline count-only measurement and current-free-space admission before the actual removable-media write;
- target/predecessor capacity failures are durable U3 failure codes;
- post-stop protected-data capacity failure is preserved through automatic predecessor restoration;
- status exposes the stable capacity cause rather than reducing it to a generic observation failure;
- automatic retry does not repeat target/predecessor writes while current free space remains insufficient; it performs only a fresh free-space check and returns a stable waiting result;
- pre-stop U3 capacity-blocked transactions are the only active HA transactions replaceable by a fresh PREPARE, enabling a larger USB without weakening later transaction ownership;
- the old blocked transaction is archived and old USB transaction contents remain untouched;
- Manager treats the two pre-stop capacity codes as retryable preparation state and republishes the PREPARE control;
- Home Assistant OTA attributes publish a Chinese `status_message_or_null` explaining that USB free space is insufficient and how to retry;
- each variable USB write persists `operation / required_bytes / available_bytes_before / capacity_pass / actual_written_bytes / available_bytes_after` in the durable HA transaction;
- V1.3 regression tests prevent reintroduction of generic static prepare reserves and prove no write begins when the corresponding current-space gate fails;
- a blocked U3 does not replay writes on timer wake; it only rechecks current free space;
- a larger replacement USB is supported through a fresh PREPARE only for a pre-stop capacity-blocked U3; all later active transactions remain non-replaceable;
- stale prepare authority from the archived transaction is treated as `PREPARE_WAITING_FOR_AUTHORITY`, not as a false failure; only a fresh authority bound to the new transaction can resume writes.
- independent review removed the dead V1.1/R1 static-capacity production API (`UsbCapacityInputs`, `assess_capacity`, predecessor/data worst-case fields and removable-media reserve) because it had no runtime callers and contradicted V1.3; R1/R2 fixtures now construct `UsbCapacityReport` directly and the V1.3 suite forbids those legacy symbols from returning.

## Test evidence

Independent review after the long implementation chain found and repaired one real source-consistency issue: the old V1.1/R1 static whole-transaction capacity API remained as dead production code even though the V1.3 runtime path no longer called it. It was removed and guarded against regression.

Exact source/test head:

`51bd2ce8baab2ca0cff4d227765de4583e0f5121`

Final workflow state for that head:

```text
CI_SUCCESS=19
CI_FAILURE=0
CI_CANCELLED=0
CI_IN_PROGRESS=0
CI_EXPECTED_SKIPPED=2
```

Key exact evidence:

- Manager A-to-B source: `253 passed`, including `tests/tools/test_n3w_t1_ota_v1_3_dynamic_usb_capacity.py`;
- Home Assistant target-binding source: `301 passed, 1 skipped`;
- Home Assistant exact-binding job: `1 passed`;
- greenhouse-manager: Ruff PASS, `1541 passed, 1 skipped`, plus `8 passed`;
- T1 R8 spare preflight, current authority, Public repository safety, Broker ingress guard and the remaining applicable workflows all completed SUCCESS.

The two cancelled jobs seen on an earlier intermediate head were superseded PR runs, not failures. Both workflows use PR-scoped `concurrency` with `cancel-in-progress: true`; the current exact head reran both same-name workflows to SUCCESS.

Exact V1.3 recovery-updater install artifact produced by the successful HA target-binding workflow:

```text
RECOVERY_UPDATER_SOURCE_HEAD=51bd2ce8baab2ca0cff4d227765de4583e0f5121
RECOVERY_UPDATER_RUN_ID=45110450673
RECOVERY_UPDATER_ARTIFACT_ID=14789063554
RECOVERY_UPDATER_ARTIFACT_NAME=n3w-t1-ha-recovery-install-51bd2ce8baab2ca0cff4d227765de4583e0f5121
RECOVERY_UPDATER_ARTIFACT_ZIP_SHA256=f7f4c9e874df799e320d823abe89355a4af117de5a686d6fe96398ddf6a964e1
RECOVERY_INSTALL_MANIFEST_SHA256=d0f98dcaa2bdd2747e33b973bf01af622b1fdab1f0d99143a8ee76b3e387d3fc
RECOVERY_UPDATER_ARTIFACT_SIZE_BYTES=101709
```

The artifact is CI-produced and exact-source-bound. It has not been deployed to the spare T1.

One non-blocking R8 robustness item remains: explicit near-full/ext4 ENOSPC fault injection should verify that any mid-stream space exhaustion stays pre-cutover or restores the predecessor, does not retry-storm, leaves partial files safely recoverable and produces useful user-facing classification.

## Live R8 boundary

The spare T1 remains at the already-proven fresh transaction stop:

```text
CURRENT_LIVE_PHASE=U1_PREPARE_REQUESTED
CURRENT_U1_VALID=true
RECREATE_U1=false
LIVE_UPDATER_ALIGNED_TO_V1_3=false
U1_TO_U4_ALLOWED=false
```

The T1 still runs the previously installed updater artifact. No V1.3 updater has been deployed in this source/document work.

The previously proposed static-reserve U1→U4 operator command is retired and must not be executed.

Exact V1.3 CI/package closure is now complete and the recovery-updater artifact is identified above.

The existing live authorization in PR #824 comment `7087966758` was source-bound to `044ba31ddeefe7ad7c3e5ed5aedbb409acfd3801`. The V1.3 artifact is bound to `51bd2ce8...`; therefore the old live authorization must not be reused for V1.3 deployment without a fresh explicit authorization/rebind.

Next live sequence:

1. fresh read-only rebind of spare T1 health, installed updater, existing U1, candidate spool and bound USB;
2. obtain a new bounded authorization explicitly binding the V1.3 recovery-updater artifact/source;
3. deploy/rebind only the exact V1.3 recovery updater without advancing the HA transaction;
4. read-only verify the existing U1 is still exact and unchanged;
5. use the existing U1 as compatibility/takeover evidence and continue through V1.3 dynamic target/predecessor preparation to U4; stop before INSTALL/U5;
6. under the appropriate existing/newly rebound predecessor-preparation authority, complete the maintenance 10.4 -> 10.0 transaction only when all gates pass; failure remains U13B recovery to exact 10.4;
7. R5-R7 are not fully rerun. Only V1.3-affected targeted regression/read-only checks are required;
8. final R8 acceptance must be a separate fresh V1.3 product-path 10.0 -> 10.4 transaction, covering normal success, substantive-fault automatic rollback, critical-boundary power-loss resume, dynamic USB capacity cases and near-full/ENOSPC fault injection.

The current old U1 is compatibility evidence, not the sole final V1.3 R8 acceptance transaction.

USB format, reboot/power-cycle, Broker mutation/OTA, PR merge and production release remain outside this source-alignment work unless separately authorized.
