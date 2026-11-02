# N3-W T1 Core Stack Clean Reference R3 current-product registration readiness authority realignment closure

Date: 2026-11-02

~~~text
TASK=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_CURRENT_PRODUCT_REGISTRATION_READINESS_AUTHORITY_REALIGNMENT_20261102_01
RESULT=CLOSED_PASS

PRODUCT_SOURCE_HEAD=24382caae4a1f5d459297f86e8d18f10a848ca64
R2_REFERENCE_SHA256=89da2a2b2cc1ce0fa024c3c45e24a71f09ba05e0e0cadbd67dd6387291239747

FINAL_CONTROL_HEAD=f8a55c77c002163386b8f911c5048ced109a5154
FINAL_BRIDGE_BLOB=711a17d7b71b1810b5f5df647c379bbfc8588674
FINAL_TEST_BLOB=28183fe1db373455567e8c99f06a5941ad2c456a
WORKFLOW_BLOB=d80eb970cd77ad1dc22144ef0e3ddfa3dab7e73e

FINAL_CI_RUN=41377034111
FINAL_CI_RESULT=SUCCESS
FINAL_TEST_COUNT=26
FINAL_BUILD_BRIDGE_PACKAGE=SUCCESS
FINAL_ARTIFACT_ID=13111538346
FINAL_ARTIFACT_DIGEST=sha256:9baad380e01fe28d4b20c0b72b98c45f74b0ea70f6c1477e77dd5241fdfe6d31
FINAL_PACKAGE_MANIFEST_SHA256=01d7cc2ec76d268a426e3a399611529684369312cb34709837479d7eb355aa5d

REGISTRATION_GUARD_BLOB=ef5077b6bc80c73bc8d3f35cf7a33a198ce918c7
BROKER_GUARD_BLOB=795903b06c7ee93a0602649e478bc070723ab8c0

READINESS_MODEL=current_product_registration_runtime
TCP_47110_EXPECTED=1
UDP_47111_EXPECTED=1
TCP_47112_EXPECTED=0
PAIRING_CONTROL_EXPECTED=CLOSED
FACTORY_ACCEPTED_REQUIRED=false
LEGACY_FIRST_PAIRING_ONBOARDING_REQUIRED=false

CLI_COMMANDS=inspect,status
MUTATION_ENTRY_PRESENT=false
FACTORY_MARKER_WRITE_PATH_PRESENT=false
BOARD_PATH_PRESENT=false

T1_MUTATION=false
FACTORY_ACCEPTED_CREATED=false
PAIRING_WINDOW_OPENED=false
BOARD_ACCESS=false
MERGE=false

NEXT_ONE_GATE=N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_CURRENT_PRODUCT_REGISTRATION_READINESS_EXACT_READONLY_PREFLIGHT_20261102_01
AUTO_EXECUTE_NEXT_GATE=false
~~~

## 1. Closure decision

The original Option-A bridge premise is retired for R3 readiness.

The frozen product source defines the normal first-registration runtime as:

- TCP/47110: always-on low-privilege registration bootstrap;
- UDP/47111: always-on low-privilege registration discovery;
- TCP/47112: privileged pairing HTTP, closed while idle.

This explicitly supersedes the older engineering-onboarding assumption that UDP/47111 must
also be absent whenever the pairing window is closed.

The normal current-product Manager first-registration runtime does not consume
`FACTORY_ACCEPTED.json` as its startup readiness authority. That marker remains associated with
the older device-provisioning / engineering-onboarding route and must not be synthesized merely
to make the old onboarding observer pass.

## 2. Frozen R3 readiness authority

The exact readonly readiness observer now requires all of the following:

1. R2 common-reference and R2A/R2B transaction continuity remain exact.
2. Current runtime health and stable contracts remain equal to the R2 reference.
3. First-pair business/security state remains clean.
4. Exactly one Manager container exists and uses host networking.
5. `GH_N3W_RUNTIME_ENABLED` is enabled.
6. Legacy `GH_N3W_PRODUCT_PAIRING_ENABLED` is not enabled.
7. Manager pairing control returns accepted status with `pairing_window_state=CLOSED`.
8. TCP/47110 listener count is exactly one.
9. UDP/47111 listener count is exactly one.
10. TCP/47112 listener count is zero.
11. The trusted-product-LAN state is available on `eth0`, with the current global IPv4 bound
    to the exact trusted subnet.
12. The exact registration/broker ingress guard source blobs match the frozen product source.
13. The live registration iptables guard validates against the same trusted subnet and owns the
    expected INPUT positions 2/3/4.

The public report exposes only hashed trusted-LAN authority values; it does not expose customer
subnet text.

## 3. Readonly hardening

After the authority realignment, an independent source review removed the now-dead mutation
surface completely:

- no `apply` CLI command;
- no `apply()` implementation;
- no bridge claim writer;
- no factory-marker writer;
- no marker rollback helper;
- CLI commands are exactly `inspect` and `status`.

Therefore the exact R3 readiness package is structurally readonly with respect to the product
state targeted by the retired bridge route.

## 4. CI history

Run `41375905905` proved the initial authority realignment with 28 passing tests.

The subsequent readonly-hardening run `41376447127` failed only because three obsolete tests
still referenced deleted mutation helpers. Production source did not fail. The stale tests were
removed in test-only repair `f8a55c77c002163386b8f911c5048ced109a5154`.

Final run `41377034111` is the closure authority:

- source-test SUCCESS;
- 26 tests PASS;
- build-bridge-package SUCCESS;
- package independent verification PASS;
- exact artifact and manifest digest recorded above.

The test count decreased from 28 to 26 because obsolete factory-marker mutation tests were
removed after that mutation path was deleted.

## 5. Live boundary

No live product mutation occurred in this gate. No authorization was claimed or consumed, no
factory marker was created, no pairing window was opened, and no Board was accessed.

A later documentation-only PR synchronize must not redefine the executable authority recorded
above. The exact executable authority for the next live readonly preflight remains
`f8a55c77c002163386b8f911c5048ced109a5154` and artifact `13111538346`.

## 6. Next gate

~~~text
NEXT_ONE_GATE=
N3W_T1_CORE_STACK_CLEAN_REFERENCE_R3_CURRENT_PRODUCT_REGISTRATION_READINESS_EXACT_READONLY_PREFLIGHT_20261102_01
~~~

The next gate may use the exact artifact on the real T1 only in readonly `inspect` mode.
No pairing transaction, Board access, pairing-window open, marker creation, service restart or
product mutation is authorized.
