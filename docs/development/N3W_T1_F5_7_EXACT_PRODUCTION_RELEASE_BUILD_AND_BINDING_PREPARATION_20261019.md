# N3W T1 F5-7 Exact Production Release Build and Binding — Preparation

Date: 2026-10-19

## Gate

~~~text
TASK=N3W_T1_F5_7_EXACT_PRODUCTION_RELEASE_BUILD_AND_BINDING_20261019_01
STATE=STARTED_WAITING_EXACT_RELEASE_CI

PARENT_CLOSURE_HEAD=3da36301d3b53be49bccc3cdb85370478929adbe
PARENT_CLOSURE=KF123_UNKNOWN_RUN_BLOCKER_CLEARED_CLOSED_PASS

FROZEN_PRODUCT_SOURCE_PR=618
FROZEN_PRODUCT_SOURCE_HEAD=4afd89b56e9925d7330b27f3f734ebcefc09182c
FROZEN_PRODUCT_SOURCE_TREE=da864ffb6c44de3efccb93516e5e786f16219cd9
FROZEN_PRODUCT_SOURCE_CI=PASS:15/15

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
AUTO_EXECUTE_NEXT_GATE=false
~~~

The historical KF-123 UNKNOWN-state blocker is closed by the independent real-T1
postexecution read-only verification. This gate therefore returns to the normal F5
release path and builds a new exact release from the repaired PR #618 product source.

The release must not reuse the older source authority `9048dd7...` or its release
`31c8a8cd...` as the current candidate.

## Exact F3 input

The repaired PR #618 exact-head fresh-bootstrap workflow already produced the
source-bound reusable production F3 payload:

~~~text
F3_WORKFLOW_RUN_ID=39213902773
F3_ARTIFACT_ID=12169550382
F3_ARTIFACT_SHA256=6c227fc9b1d45a289791439a8374825a8bd6d62178ea2123d3b292cd5b36fe9c
F3_SOURCE_HEAD=4afd89b56e9925d7330b27f3f734ebcefc09182c
F3_ARTIFACT_EXPIRED=false
~~~

The exact-release workflow must verify this ZIP digest before inspecting or using
the payload.

## F4 and reboot inputs

No F4 exact-control workflow run exists at the repaired PR #618 source head because
the KF-123 source delta did not touch the normal F4 workflow trigger paths.

The release builder requires F4 and reboot manifests to bind to the same frozen
product source. Reusing the older `9048dd7...` F4/reboot artifacts would therefore
be an invalid mixed-source release.

For this gate, the exact-release CI builds the F4 control package and reboot successor
package directly from an exact checkout of the frozen PR #618 source, uploads both as
source-bound intermediate artifacts, re-downloads their GitHub ZIP bytes, verifies
their exact ZIP digests, and only then supplies them to the existing release builder.

This changes release orchestration only. It does not change F4 product behavior or
the frozen product-source tree.

## Frozen host environment policy

~~~text
OS_ID=ubuntu
OS_VERSION=26.04
OS_CODENAME=resolute
ARCHITECTURE=aarch64
PACKAGE_SOURCE=ubuntu_apt
DOCKER_IO_PACKAGE_VERSION=29.1.3-0ubuntu4.1
DOCKER_COMPOSE_V2_PACKAGE_VERSION=2.40.3+ds1-0ubuntu1
PRODUCTION_OVERRIDE_ALLOWLIST=EMPTY
~~~

The environment authority remains:

`docs/development/N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_R2_LIVE_APPLY_PREEXECUTION_NEW_CHAT_HANDOFF_V1.0_20261014.md`.

## Required exact-release checks

The candidate is acceptable only if the focused workflow proves all of the following:

1. exact source HEAD and tree equal the frozen PR #618 authority;
2. F3 ZIP digest is exact and its internal source/image/capacity bindings pass;
3. F4 and reboot packages are built from the same frozen source, uploaded, downloaded
   again, and their GitHub artifact ZIP digests match;
4. Mac and target file-set manifests are rebuilt from the frozen source;
5. `approved-release.json`, provenance and full file index validate;
6. packaged normal production entrypoint is runnable from the assembled release;
7. the final release artifact is uploaded, re-downloaded, and independently verified
   byte-for-byte against the release contract.

## Closure boundary

A passing GitHub Actions build closes exact construction and post-upload binding only.

The 30-day Actions artifact is not, by itself, the durable recoverable production
archive. The final candidate must still be preserved and reverified through the
existing durable Mac archive route before any later T1 production execution is
authorized.

Therefore:

~~~text
F5_7_BUILD_BINDING_CLOSED_PASS=false
DURABLE_ARCHIVE_CLOSED_PASS=false
NEW_F5_9_PRODUCTION_AUTHORIZATION=false
T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

## Stop rule

~~~text
CURRENT_STOP_POINT=WAIT_EXACT_RELEASE_CI
NEXT_IF_CI_PASS=REVIEW_FINAL_ARTIFACT_BINDING_AND_ENTER_DURABLE_ARCHIVE_SUBGATE
NEXT_IF_CI_FAIL=CLASSIFY_FIRST_DETERMINISTIC_BUILD_OR_BINDING_FAILURE
AUTO_EXECUTE_NEXT_GATE=false
STOP=true
~~~
