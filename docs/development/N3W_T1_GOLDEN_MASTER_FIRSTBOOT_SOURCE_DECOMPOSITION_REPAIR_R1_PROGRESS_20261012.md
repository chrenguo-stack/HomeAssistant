# N3-W T1 golden-master / firstboot source decomposition repair R1 progress

Date: 2026-10-12

TASK=
`N3W_T1_GOLDEN_MASTER_FIRSTBOOT_SOURCE_DECOMPOSITION_REPAIR_R1`

## 0. Current status

~~~text
R1_SOURCE_HEAD=90275626aafd2bcbc724cfcececc3911234dd23e
R1_IMPLEMENTATION=COMPLETE
FOCUSED_CI=PASS
EXTENDED_IMAGE_ARTIFACT_CI=PENDING
T1_ACCESS=false
T1_MUTATION=false
R3_CLEANUP=false
LIVE_RUNTIME_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
AUTHORIZATION_08_GRANTED=false
MERGE=false
~~~

This is not yet a final source-review closure. R1 stops after source implementation and CI; an independent source review is required before R2.

## 1. Exact delta

Compared with the pre-R1 documentation head `0b8ac67bf44c81a31a097a93f53ef1d871c068b1`, R1 source head changes exactly six source/test files:

~~~text
ADD host/greenhouse-manager/src/greenhouse_manager/bootstrap/golden_master_installer.py
ADD host/greenhouse-manager/src/greenhouse_manager/bootstrap/device_firstboot.py
ADD host/greenhouse-manager/tests/bootstrap/test_golden_master_installer.py
ADD host/greenhouse-manager/tests/bootstrap/test_device_firstboot.py
MOD tests/tools/test_n3w_t1_fresh_product_bootstrap.py
MOD tools/n3w_t1_fresh_product_bootstrap.py
~~~

No firmware, pairing, N3-W radio, Compose topology, production systemd activation unit, staging host transport, or live executor authorization source was changed.

## 2. Legacy R8 compatibility preserved by construction

The exact R8 orchestration contract file remains byte-identical to source authority `5ed613...`:

~~~text
host/greenhouse-manager/src/greenhouse_manager/bootstrap/fresh_installer.py
blob=015998dc8ba7c2d8cf32a12c2d695bfdf2fb1c32
UNCHANGED=true
~~~

The R8 host transport wrapper also remains outside the R1 source delta:

~~~text
tools/n3w_t1_fresh_product_staging_host.py
UNCHANGED=true
~~~

Therefore R1 does not redefine:

- `run_fresh_staging()` stage order or report schema;
- R8 `_08` authorization semantics;
- F5 storage-authority/imports contract;
- transport/capacity policy;
- live T1 host-wrapper semantics.

The existing R8 bootstrap adapter still exposes the legacy methods expected by `run_fresh_staging()`; those wrappers now delegate to split public/instance ownership methods.

## 3. Ownership split implemented

`tools/n3w_t1_fresh_product_bootstrap.py` now exposes:

~~~text
PUBLIC_FINAL_DIRS / PUBLIC_FINAL_FILES
INSTANCE_FINAL_DIRS / INSTANCE_FINAL_FILES

stage_public_runtime()
stage_instance_runtime()

commit_public_candidate()
commit_instance_candidate()

master_postcheck()
instance_stopped_postcheck()

cleanup_master_candidate()
cleanup_instance_candidate()
~~~

The legacy wrappers remain:

~~~text
stage_runtime()
commit_candidate()
stopped_postcheck()
cleanup()
~~~

### Public ownership

Current R1 public targets:

~~~text
/opt/HomeAssistant
/usr/local/sbin/n3w-broker-ingress-guard
/etc/systemd/system/n3wfc4-broker-ingress-guard.service
~~~

Public cleanup may remove transaction-created public paths and transaction-loaded images.

### Instance ownership

Current R1 instance targets:

~~~text
/var/lib/greenhouse-manager
/var/lib/n3wfc4-broker
/var/lib/n3wfc4-homeassistant
/opt/greenhouse-secrets
/etc/n3wfc4
~~~

Instance cleanup does not reference or remove the preloaded image set or public final targets.

## 4. Pure golden-master orchestration contract

New:

~~~text
greenhouse_manager.bootstrap.golden_master_installer
schema=gh.n3w.t1-golden-master-build/1
~~~

Stages:

~~~text
preflight_master
→ load_images
→ stage_public_runtime
→ commit_public_candidate
→ master_postcheck
~~~

It has no identity/state/Broker-secret/DynSec constructor methods in its adapter contract.

Mutation failure uses a master-only cleanup contract.

This module contains no Docker/subprocess/socket implementation; host mutation remains adapter-owned.

## 5. Pure device-firstboot transaction contract

New:

~~~text
greenhouse_manager.bootstrap.device_firstboot
schema=gh.n3w.t1-device-firstboot/1
transaction=gh.n3w.t1-device-firstboot-transaction/1
complete=gh.n3w.t1-device-firstboot-complete/1
~~~

Durable stages:

~~~text
PRECHECK
→ OS_IDENTITY
→ PRODUCT_IDENTITY
→ STATE
→ BROKER
→ DYNSEC
→ INSTANCE_STAGE
→ COMMIT
→ VERIFY
→ FIRSTBOOT_COMPLETE.json written last
~~~

Properties implemented in R1 contract layer:

- exact release binding;
- durable stage record;
- host-instance binding after OS identity becomes available;
- SYSTEM_ID SHA binding;
- completed firstboot idempotence;
- completed-marker / transaction consistency check;
- host-binding drift fail-closed;
- release-binding drift fail-closed;
- no dependency on R8 `AUTHORIZATION_ID` or `_08`;
- no Docker/subprocess/socket operation in the pure bootstrap module.

R1 deliberately does not yet implement the real Armbian machine-id/SSH-host-key adapter or production firstboot systemd unit.

## 6. Current focused CI evidence

Exact R1 source head:

~~~text
90275626aafd2bcbc724cfcececc3911234dd23e
~~~

PASS:

~~~text
H0 H1 initialization and portable restore CI
run=38269727540
conclusion=success

greenhouse-manager CI
run=38269727642
conclusion=success

N3W T1 deployment gate CI
run=38269727440
conclusion=success

Public repository safety CI
run=38269727657
conclusion=success
~~~

The exact-head `N3W T1 fresh bootstrap deployable payload CI` run `38269727681` has already completed its **Run source contract tests** step successfully; its later ARM64 image/artifact build steps are still running at this checkpoint.

Extended workflows still pending at this checkpoint include:

~~~text
N3W T1 fresh bootstrap deployable payload CI
N3W T1 fresh install exact ARM64 CI
N3W T1 fresh install host-only CI
~~~

No failure has been observed on the exact R1 source head.

## 7. Blocker disposition

R1 closes implementation seams:

~~~text
SB1_MIXED_PUBLIC_INSTANCE_STAGE=CLOSED_SOURCE
SB2_MIXED_COMMIT_AND_CLEANUP_OWNERSHIP=CLOSED_SOURCE
SB3_MIXED_POSTCHECK=CLOSED_SOURCE
SB4_DURABLE_FIRSTBOOT_TRANSACTION=PARTIAL_CONTRACT_IMPLEMENTED
~~~

Still open:

~~~text
SB4_REAL_HOST_FIRSTBOOT_ADAPTER=OPEN
SB5_NO_SEAL_IMPLEMENTATION=OPEN
SB6_NO_OS_IDENTITY_ADAPTER=OPEN
SB7_NO_FACTORY_CLONE_UNIQUENESS_HARNESS=OPEN
~~~

No claim is made that golden-master production or clone firstboot is live-ready.

## 8. STOP boundary

~~~text
R1_SOURCE_IMPLEMENTED=true
FOCUSED_CI=PASS
EXTENDED_CI=PENDING
INDEPENDENT_SOURCE_REVIEW=PENDING

T1_ACCESS=false
T1_MUTATION=false
R3_CLEANUP=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
AUTHORIZATION_08_GRANTED=false
MERGE=false
~~~

After extended CI reaches terminal state, the next gate should be an independent focused source review of R1 before any R2 master-build/Seal implementation.
