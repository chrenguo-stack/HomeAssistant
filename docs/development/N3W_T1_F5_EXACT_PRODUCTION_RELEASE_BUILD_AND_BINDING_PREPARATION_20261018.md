# N3W T1 F5 V1 Exact Production Release Build and Binding — Preparation

Date: 2026-10-18

## Gate

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_EXACT_PRODUCTION_RELEASE_BUILD_AND_BINDING_20261018_01
STATE=REBUILD_PREPARED_AFTER_SOURCE_REPAIR

PARENT_PR=612
PARENT_SOURCE_HEAD=55e499f28d4b1a79da0c5c1fbd21b513f24644e6
PARENT_SOURCE_TREE=4212298609fbb80557984fdc350cb6d336c41f53
PARENT_SOURCE_CI=PASS:20/20

BUILD_BRANCH=build/n3w-t1-f5-exact-production-release-v1-20261018
T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

The F5-1 through F5-6 product source remains frozen at the accepted product-source head above.
F5-7 build tooling is deliberately separated from that product-source identity. The approved release
must continue to declare the frozen product source, not the later build-tooling branch head.

## Source repair triggered by first F5-7 build

The first exact-release build attempt on PR #613 stopped before upload with
`source_file_invalid:tools/execution_packages/n3w/f2/t1_fresh_readonly_identity/executor.py`.
That path does not exist in the product source. The production F2 executor actually streams
`tools/n3w_t1_os_identity_readonly_probe.py`.

PR #612 repaired the packaged Mac file set and added a regression test. The repaired product source is:

~~~text
REPAIRED_SOURCE_HEAD=55e499f28d4b1a79da0c5c1fbd21b513f24644e6
REPAIRED_SOURCE_TREE=4212298609fbb80557984fdc350cb6d336c41f53
REPAIRED_SOURCE_CI=PASS:20/20
FIRST_F5_7_BUILD_RELEASE_CREATED=false
~~~

F5-7 therefore restarts from source-bound artifacts produced by this repaired head. The previous
`1d56d...` artifacts are superseded for F5-7 and must not be mixed with the repaired source.

## Exact input authorities

~~~text
F3_WORKFLOW_RUN_ID=39145347331
F3_ARTIFACT_ID=12143496615
F3_ARTIFACT_SHA256=5aff87f7f878fec0af23f21b3e953f7a59daa4413b261392de1cbdf1ea154e04

F4_WORKFLOW_RUN_ID=39145347300
F4_ARTIFACT_ID=12143346463
F4_ARTIFACT_SHA256=fa10e771a4caa4a242a9c133d161b6a421bf1c61db55befbbf6aa1104e7f8462

REBOOT_ARTIFACT_ID=12143007656
REBOOT_ARTIFACT_SHA256=f20fb07c4cab6696fa442589943a539bfca3a4ea6f868c9660d7dff0a94b06a6
~~~

All three inputs are source-bound to
`55e499f28d4b1a79da0c5c1fbd21b513f24644e6`.

The F3 production artifact is the reusable production form with no historical live authorization
embedded. The F4 and reboot inputs are the exact control artifacts produced from the same source head.

## Frozen environment policy

The approved V1 host environment is taken from the real fresh-T1 baseline already recorded before the
accepted F3 live path:

~~~text
OS_ID=ubuntu
OS_VERSION=26.04
OS_CODENAME=resolute
ARCHITECTURE=aarch64

PACKAGE_SOURCE=ubuntu_apt
DOCKER_IO_PACKAGE_VERSION=29.1.3-0ubuntu4.1
DOCKER_COMPOSE_V2_PACKAGE_VERSION=2.40.3+ds1-0ubuntu1
~~~

Authority:
`docs/development/N3W_T1_PER_DEVICE_FRESH_ARMBIAN_AUTOMATED_DEPLOYMENT_F3_R2_LIVE_APPLY_PREEXECUTION_NEW_CHAT_HANDOFF_V1.0_20261014.md`.

F5 production must install these exact package versions when the host baseline is missing. If either
approved version cannot be obtained, the production path stops instead of selecting a newer APT
candidate.

## Builder responsibilities

`tools/n3w_t1_f5_release_builder.py` is restricted to release assembly and verification. It does not
access a T1 and does not create production authority.

It must:

1. verify the frozen source commit and tree;
2. verify the exact GitHub artifact ZIP digests before trusting their contents;
3. verify the F3 payload, capacity contract and all three ARM64 image tar hashes;
4. derive each image-content binding from the complete source-bound image record;
5. extract and verify the exact F4 and reboot control package manifests and file hashes;
6. construct exact Mac-orchestrator and target-authority file-set manifests from the frozen source;
7. generate `approved-release.json` using the existing production release schema and empty override allowlist;
8. verify the resulting release using the packaged frozen runtime validators;
9. generate a complete file index and provenance record;
10. prove the packaged normal entrypoint is runnable from the release directory.

## Candidate CI

The new focused workflow downloads the three already accepted source-bound artifacts by exact artifact
ID, builds the release candidate, uploads it as one GitHub Actions artifact, re-downloads that artifact,
and verifies the exact release again after upload.

This closes byte construction and post-upload binding only if CI passes.

## Durable archive boundary

A 30-day GitHub Actions artifact is not sufficient by itself for the F5-7 long-term release requirement.

Therefore:

~~~text
ACTIONS_ARTIFACT_CAN_CLOSE_BUILD_BINDING=true
ACTIONS_ARTIFACT_ALONE_CAN_CLOSE_DURABLE_ARCHIVE=false
F5_7_CLOSED_PASS=false
~~~

After the exact candidate exists and its final artifact ID/digest are known, a separate bounded archive
step must preserve the same bytes in a controlled recoverable location or equivalent durable release
store. No T1-B access starts before that durability requirement is closed.

## Stop rule

~~~text
CURRENT_STOP_POINT=WAIT_F5_EXACT_RELEASE_REBUILD_CI
NEXT_IF_CI_PASS=RECORD_EXACT_RELEASE_ID_AND_ARTIFACT_BINDING_THEN_CLOSE_DURABLE_ARCHIVE_GAP
NEXT_IF_CI_FAIL=FIX_FIRST_DETERMINISTIC_BUILD_OR_BINDING_DEFECT_ONLY

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~
