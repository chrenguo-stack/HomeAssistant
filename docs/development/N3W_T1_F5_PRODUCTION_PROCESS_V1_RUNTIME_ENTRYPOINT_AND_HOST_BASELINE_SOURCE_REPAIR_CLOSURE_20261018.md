# N3W T1 F5 Production Process V1 — Runtime Entrypoint / HOST_BASELINE Source Repair Closure

Date: 2026-10-18

## Gate

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_RUNTIME_ENTRYPOINT_AND_HOST_BASELINE_SOURCE_REPAIR_20261017_01
RESULT=CLOSED_PASS

PR=612
PR_STATE=OPEN_DRAFT
BASE_MAIN=9c81b889d97ed896b80d27af15069d16af0e0bdb
SOURCE_HEAD=1d56d785c017b5e847b0734268863ac78ca2d1dd
MAIN_DRIFT=NONE
PR_HEAD_DRIFT=NONE

CI_RESULT=PASS:20/20
CI_FAILURE=0
CI_PENDING=0

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
EXACT_PRODUCTION_RELEASE_BUILT=false
~~~

## Closure conclusion

The runtime-entrypoint / HOST_BASELINE repair is closed. The reviewed implementation from
`f36e0d6842ce5a0e421e31141fc75019ded822a3` through
`d2bac9b029a9c01d187dd125c6806f27ee9d1462` remains accepted, and the only discovered
post-review defect — stale F2 source-authority blob bindings — is repaired by
`1d56d785c017b5e847b0734268863ac78ca2d1dd`.

No rollback is required.

## Closed blockers

~~~text
B1_NORMAL_RUNTIME_BACKEND=CLOSED_PASS
B2_HOST_BASELINE_PHASE_AND_APPROVED_VERSION_BINDING=CLOSED_PASS
B3_UNIFIED_F2_F3_SSH_ORCHESTRATION=CLOSED_PASS
B4_ACTUAL_PACKAGED_ENTRYPOINT_CI=CLOSED_PASS
F2_STALE_BLOB_BINDING=CLOSED_PASS
~~~

### B1 — normal production runtime backend

Normal `n3w-t1-production run` now constructs the concrete runtime backend without an external
test-only `backend_factory` injection. Runtime dispatch continues to reuse the target production
authority and the accepted F3 / provisioning / F4 / reboot primitives.

### B2 — HOST_BASELINE exact release binding

The production HOST_BASELINE path validates the approved production release, writes its durable
one-shot claim before mutation, and installs only the exact Docker / Compose package versions
approved by that release. A later APT candidate is not silently substituted.

### B3 — unified managed SSH path

The normal F2/F3 production path requires the F5-managed SSH transport. The accepted connection
epoch, host-key and no-fallback behavior remains owned by the unified SSH adapter.

### B4 — actual packaged/runtime entrypoint coverage

The F5 runtime / actual-entrypoint tests exercise the concrete backend path rather than only a
fake injected backend. Existing F3/provision/F4 and repository safety regressions also remain green.

## Reboot ordering retained

The accepted production ordering remains:

~~~text
durable reboot-actuation claim
-> REBOOT_CONTROL completion
-> fixed sudo -n systemctl reboot
~~~

If the durable actuation claim fails, no reboot command is sent.

## F2 source-authority repair

The final repair changes only the two reviewed source-blob bindings used by the F2 read-only
preflight executor:

~~~text
tools/n3w_t1_fresh_product_staging_host.py
blob=e60c61133924d318bb005307f4df618f15fe77d5

tools/n3w_t1_fresh_host_baseline.py
blob=59d00226232e2dd73d0540c9be503c70af31501b
~~~

Product behavior was not changed by this final repair.

## CI closure evidence

All 20 pull-request-triggered workflow runs associated with the closure source head completed
successfully. Important gate-specific runs include:

~~~text
N3W T1 F2 read-only preflight source CI          39137060290 PASS
N3W T1 F5 production process V1 source CI        39137060346 PASS
N3W T1 F4 activation source CI                   39137060228 PASS
N3W T1 F4 exact control package                  39137060200 PASS
N3W T1 explicit provisioning source CI           39137060355 PASS
N3W T1 golden master source CI                   39137060348 PASS
N3W T1 production stack staging payload CI       39137060265 PASS
N3W T1 fresh bootstrap deployable payload CI     39137060229 PASS
N3W T1 fresh install host-only CI                39137060268 PASS
Public repository safety CI                      39137060375 PASS
greenhouse-manager CI                            39137060271 PASS
~~~

The remaining regression workflows in the same 20-run set are also PASS; there are no failures
and no pending runs.

## Next boundary

The previous whole-source closure review explicitly reserved exact production release construction
for F5-7 and allowed it only after B1-B4 were closed. That prerequisite is now satisfied.

~~~text
F5_1_THROUGH_F5_6_SOURCE_STATUS=CLOSED_PASS
F5_7_EXACT_PRODUCTION_RELEASE_STATUS=READY_TO_START

NEXT_ONE_GATE=N3W_T1_F5_PRODUCTION_PROCESS_V1_EXACT_PRODUCTION_RELEASE_BUILD_AND_BINDING_20261018_01

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
STOP=true
~~~
