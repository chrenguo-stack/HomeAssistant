# N3W T1 F5 V1 Durable Release Archive — Preparation

Date: 2026-10-19

## Gate

~~~text
TASK=N3W_T1_F5_PRODUCTION_PROCESS_V1_DURABLE_RELEASE_ARCHIVE_20261019_01
STATE=CLOSED_PASS_CURRENT_REPAIRED_RELEASE

PARENT_PR=613
EXACT_RELEASE_BUILD=PASS
CURRENT_RELEASE_DURABLE_ARCHIVE_CLOSED=true

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~

## Exact release authority

~~~text
SOURCE_HEAD=6e228a4b2c7c4ff78918571abb7b583e416615ee
SOURCE_TREE=6c07b6f9c3d528b630a96cf16b4efdbaef3ff5e5
BUILDER_HEAD=51c7eaf3d285c4b604b0261021ce9ceac061a445

RELEASE_ID=b89c9e227e53fcac2ef2717d7b11cd6b64536ce27c9b6b16c2429980049c8a69
RELEASE_SHA256=5291042f87686aecbd6b7e52641c10f69cdae0d56abbf675b8eab8c9bfeb8804
FILE_INDEX_SHA256=1398556003c05695d966593bf6a171f4a628cbf46d36c68d774db05972f9461c

WORKFLOW_RUN_ID=39188343164
ARTIFACT_ID=12158903271
ARTIFACT_NAME=n3w-t1-f5-approved-release-6e228a4b2c7c4ff78918571abb7b583e416615ee
ARTIFACT_ZIP_SHA256=5732093e9d94bff99b22ed935a54a187a224d29a5ec77e964dfec5cfe2487013
ARTIFACT_SIZE_BYTES=2536414947
ARTIFACT_EXPIRES_AT=2026-11-18T02:06:46Z
~~~

The exact release CI independently built the release, verified it locally, uploaded it, re-downloaded it, and verified the same release ID and SHA-256 after upload.

The current authority above supersedes the previous F5-7 release for F5-8/F5-9 onward because the F5-8 preexecution review repaired the packaged production preflight confirmation string at source head `6e228a4...`. The earlier release/archive acceptance remains valid historical evidence, but it cannot authorize T1-B execution after this source change.


The Actions artifact is temporary. It therefore does not by itself close the F5-7 durable archive requirement.

## First Mac acceptance failure and superseded artifact

The first real Mac archive attempt against artifact `12156115228` stopped before durable publication with:

~~~text
ERROR=release_index_file_set_mismatch
ARCHIVE_PUBLISHED=false
T1_ACCESS=false
~~~

This exposed a release-builder defect rather than a workstation defect. PR #613 repair
`8770e17f096fa9eb035ec32bbe32731abed62bfd` now suppresses post-index Python bytecode,
runs the packaged entrypoint with `python -B`, and enforces exact index-to-file-set equality.

The repaired exact-release CI passed and produced artifact `12157105538`. Artifact
`12156115228` is superseded and must not be used for F5-7 durable acceptance.

## Durable workstation store

V1 uses the same design principle already accepted for the F3 exact-artifact cache: the production workstation keeps exact bytes under a user-visible durable Documents path rather than a temporary cache.

Default location:

~~~text
~/Documents/N3W/approved-releases/
  <release_id>/
    <artifact_id>/
      <artifact_zip_sha256>/
        artifact.zip
        binding.json
~~~

The store is a transport/recovery copy. It does not create a new release authority.

## Archive verifier

`tools/n3w_t1_f5_release_archive.py` must fail closed unless all of the following match:

1. GitHub artifact metadata: repository, workflow run, name, artifact ID, unexpired state and ZIP digest;
2. downloaded ZIP SHA-256;
3. `approved-release.json` SHA-256 and release ID;
4. release file-index SHA-256 and sidecar;
5. every indexed file size and SHA-256 across the complete release;
6. exact source head/tree and builder head in release provenance;
7. existing archive entry exact binding and file set.

A valid existing entry is never silently replaced. A corrupted entry is a hard stop.

The `verify` subcommand performs no GitHub metadata lookup and no network download. It proves that the workstation copy remains independently recoverable after initial population.

## Real Mac acceptance boundary

Source CI cannot close the durable-workstation requirement. Closure requires one real Mac execution:

~~~text
FIRST_ARCHIVE=MISS_POPULATED
SECOND_VERIFY=VERIFY_ONLY
ARTIFACT_ZIP_SHA256=PASS
FULL_RELEASE_FILE_INDEX=PASS
PERSISTENT_STORE=true
~~~

The real acceptance must use the exact authority above. It does not access T1.

## Stop rule

~~~text
CURRENT_STOP_POINT=AFTER_REPAIRED_RELEASE_DURABLE_ARCHIVE_BEFORE_T1B_READONLY_PREFLIGHT
F5_8_BLOCKED_BY_CURRENT_RELEASE_DURABILITY=false
F5_8_T1_ACCESS_AUTHORIZED=true
T1B_READONLY_AUTHORIZATION=GRANTED_NOT_CONSUMED

T1_ACCESS=false
T1_MUTATION=false
LIVE_REBOOT=false
BOARD_ACCESS=false
MERGE=false
~~~


## Historical Real Mac acceptance closure — superseded current-release authority

The repaired artifact was then accepted on the real production Mac in two independent steps.

~~~text
FIRST_ARCHIVE=MISS_POPULATED
FIRST_ARCHIVE_STATUS=PASS
PERSISTENT_STORE=true

SECOND_VERIFY=VERIFY_ONLY
SECOND_VERIFY_STATUS=PASS
SECOND_VERIFY_GITHUB_ACCESS=false

RELEASE_ID=4eae02a0ef306b82771d6a40dfcb44266457a42ae8d3eaace587c4a094225fa9
RELEASE_SHA256=1b046c95ab612ad63fbe911be4b1d7a38e17456906e63edf8ab70aa35164296e
FILE_INDEX_SHA256=005f1594d62c300af5452d86f837f9d2a8fe292d45826e4a33b2b57748a3e7ac
ARTIFACT_ID=12157105538
ARTIFACT_ZIP_SHA256=62b76cb69bafb18adf5f6e3d48008a8cf8e567e00e7a68a8f19606e1c2e5dd1c
BUILDER_HEAD=8770e17f096fa9eb035ec32bbe32731abed62bfd
SOURCE_HEAD=55e499f28d4b1a79da0c5c1fbd21b513f24644e6
SOURCE_TREE=4212298609fbb80557984fdc350cb6d336c41f53

T1_ACCESS=false
BOARD_ACCESS=false
~~~

For the second verification, the operator replaced both `gh` and `curl` in `PATH` with hard-fail
sentinels. `VERIFY_ONLY` still passed, proving the durable workstation copy is independently usable
without GitHub metadata lookup or artifact download.

The durable store is now accepted at:

~~~text
~/Documents/N3W/approved-releases/
  4eae02a0ef306b82771d6a40dfcb44266457a42ae8d3eaace587c4a094225fa9/
    12157105538/
      62b76cb69bafb18adf5f6e3d48008a8cf8e567e00e7a68a8f19606e1c2e5dd1c/
        artifact.zip
        binding.json
~~~

This historical release passed durable archive acceptance, but it is superseded for current F5-8/F5-9 execution by the source repair at `6e228a4...`. The current release must repeat `MISS_POPULATED` and `VERIFY_ONLY` before the already-granted T1-B read-only authorization can be consumed.


## Repaired release real Mac acceptance closure

~~~text
FIRST_ARCHIVE=MISS_POPULATED
FIRST_ARCHIVE_STATUS=PASS
SECOND_VERIFY=VERIFY_ONLY
SECOND_VERIFY_STATUS=PASS
SECOND_VERIFY_GITHUB_ACCESS=false
CURRENT_RELEASE_DURABLE_ARCHIVE_CLOSED=true
T1B_READONLY_AUTHORIZATION=GRANTED_NOT_CONSUMED
T1_ACCESS=false
BOARD_ACCESS=false
~~~

The current repaired release is durably accepted. F5-8 may now consume the already-granted T1-B read-only authorization.

Authority: `docs/development/N3W_T1_F5_REPAIRED_RELEASE_DURABLE_MAC_ARCHIVE_ACCEPTANCE_CLOSURE_20261019.md`.
