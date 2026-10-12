# N3-W T1 fresh bootstrap R6 Astra R2 blockers source repair progress（2026-10-12）

## Review result

~~~text
ASTRA_R2_REVIEW_SOURCE_HEAD=dec88fdc19daf50185d09acf4a38db8c18816ef2
F1=CLOSED
F2=CLOSED
F3=CLOSED
F4=CLOSED
F5=OPEN_BLOCKER
F6=CLOSED
A8=OPEN_NONBLOCKER
DOWNSTREAM_SOURCE_BLOCKER=YES
NEW_BLOCKER=D1_POSTCHECK_STATE_OWNER_MISMATCH
R6_PRELIVE_RECOMMENDATION=BLOCK
~~~

## Repaired product source

~~~text
PRODUCT_SOURCE_HEAD=41d05b99813ae5ea3887b4f2b80b75164f35dda4
PREDECESSOR_AUTHORIZATION=_06
PREDECESSOR_GRANTED=false
PREDECESSOR_STATUS=SUPERSEDED_UNGRANTED
SUCCESSOR_AUTHORIZATION=N3W_T1_MINIMAL_HOST_FRESH_PRODUCT_BOOTSTRAP_LIVE_APPLY_20261012_07
SUCCESSOR_GRANTED=false
SUCCESSOR_CLAIMED=false
SUCCESSOR_CONSUMED=false
~~~

## F5 repair

The host wrapper no longer treats DockerRootDir/containerd as an authority and no longer silently falls back to DockerRootDir.

It first identifies the active Docker image-store mode from Docker DriverStatus:

~~~text
classic
external containerd snapshotter
embedded containerd
~~~

For external containerd it reads the active containerd service process arguments and effective config, resolves --root or config root or the documented default /var/lib/containerd, and verifies Docker's containerd socket matches the active containerd service address.

For embedded containerd it uses the Docker data-root containerd/daemon location.

If image-store authority cannot be identified, the preflight stops.

Capacity checks now use:

~~~text
/var/tmp
DockerRootDir
actual image_store_root
~~~

and require the same filesystem plus positive free-space readings before calculating the conservative transport reserve.

## D1 repair

The stopped postcheck is split.

State audit:

~~~text
user=999:999
src=/var/lib/greenhouse-manager/manager -> /manager readonly
src=/var/lib/greenhouse-manager/n3w -> /n3w readonly
audit_fresh_state()
~~~

The state directories are mounted directly so UID 999 does not need to traverse the root-owned parent.

Root-only audit remains separate for:

~~~text
system identity
DynSec document
service credential bundle
~~~

The exact deployable workflow also executes the state audit with the exact Manager image and UID 999 against the staged state before archive freeze.

A contract test forces a postcheck failure and proves cleanup runs with failed_stage=postcheck and cleanup_result=PASS.

## A8 reliability repair

The normal gh run download timeout and OS transport errors now enter the same integrity-preserving fallback as ordinary FreshHostTransportError.

The fallback test proves a synthetic gh timeout reaches the REST redirect/curl path and only succeeds after the artifact ZIP SHA and exact outer file set validate.

## Stop condition

~~~text
EXACT_HEAD_CI=PENDING
REPLACEMENT_ARTIFACT=NOT_AUTHORITY
T1_ACCESS=false
LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false
PRODUCTION_SERVICE_START=false
LIVE_AUTHORIZATION=_07_NOT_GRANTED
MERGE=false
~~~

After CI convergence, perform another focused closure review before artifact binding or T1 preflight.
