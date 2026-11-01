# N3-W KF-096 PR #431 Exact Artifact Build and Binding Preparation — 2026-09-18

Status: `ARTIFACT_BUILD_PREPARATION_AUTHORITY`

Fresh repository/build/physical evidence takes precedence if later evidence proves drift.

## Scope

This record closes only the **preparation** gate for building and binding a new exact artifact from the merged PR #431 source.

No artifact build, artifact upload, Board A/B access, serial open, flash write, T1 mutation, Broker/Manager/DynSec mutation, credential mutation, or physical validation occurs in this preparation gate.

## Exact product-source authority

```text
REPOSITORY=chrenguo-stack/HomeAssistant

PRODUCT_SOURCE_AUTHORITY=d1b5c3acbd32cca95483743ffe2edba9aa3f904f
PRODUCT_SOURCE_TREE=3f161c1550e1df48db7cd5a5970db1b11932bef0

FINAL_REVIEW_HEAD=137303c7b08fff36920d05e77c2f1bcc20b38d1f
MERGE_PARENT_MAIN=0f9c64d9e2c5953dbb93c162e08e6601ea0e7d33
MERGE_PARENT_REVIEW_HEAD=137303c7b08fff36920d05e77c2f1bcc20b38d1f

CURRENT_DOCUMENTATION_MAIN_AT_PREPARATION=
8989450b179f5f0f7d64d909bd84477c8b0785f9
```

The candidate firmware must be built from the PR #431 merge commit above, not from the later documentation-only repository main tip.

## Exact build target

```text
TARGET_CONFIG=
firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml

TARGET_GIT_BLOB_SHA=
3d13e2197520c375b56d682b37773ef28e194421

TARGET_DEVICE=ESP32-C6
TARGET_FLASH_SIZE=8MB
TARGET_FRAMEWORK=ESP-IDF
```

The full product-source tree already binds all local component sources imported by this target.

## Toolchain contract

```text
PYTHON_VERSION=3.11
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
```

The execution workflow must verify the installed ESP-IDF package from its `version.cmake` and fail closed if major/minor/patch are not exactly 5.5.4.

## Proven mechanism reused

The PR #428 artifact route proved the following build-only mechanism:

- a non-product branch contains only one workflow;
- the workflow checks out the exact product-source commit rather than the workflow branch tip;
- HEAD and tree are asserted before compile;
- ESPHome is pinned to 2026.4.3;
- the generic Phase 4 physical harness is compiled;
- only `firmware.bin`, `ota_data_initial.bin`, and a public-safe manifest are frozen;
- the uploaded archive is later independently downloaded and hash-bound;
- the build-only branch is never merged into `main`.

PR #431 will reuse this mechanism with stronger target-blob and ESP-IDF-version assertions.

Historical PR #428 build-only authority:

```text
PR428_BUILD_BRANCH=build/n3w-pr428-boardb-artifact-20260918
PR428_WORKFLOW_SOURCE_COMMIT=ec256e8b219942d61ecf583ae558e9aef31b0482
PR428_WORKFLOW_RUN_ID=35309484471
PR428_ARTIFACT_ID=10533235759
```

The PR #428 artifact itself remains historical/non-deployable and must not be reused.

## Frozen execution identifiers

The following identifiers are reserved for the later build execution:

```text
PROPOSED_BUILD_BRANCH=
build/n3w-pr431-boardb-artifact-20260918

PROPOSED_WORKFLOW_PATH=
.github/workflows/n3w-pr431-boardb-artifact-build.yml

PROPOSED_ARTIFACT_NAME=
n3w-pr431-boardb-exact-source

ARTIFACT_RETENTION_DAYS=7
```

Creating that build branch will trigger the artifact build, so the branch must **not** be created during this preparation gate.

## Frozen build-only workflow template

The SHA-256 below is over the exact UTF-8 YAML bytes in the following code block, using LF line endings and including the final newline:

```text
WORKFLOW_TEMPLATE_SHA256=
5c5313bb627d50ca8337ebea310c588fefc3b32c5eedd08f99d09fa03b6f6bfc
WORKFLOW_TEMPLATE_SIZE_BYTES=3423
```

```yaml
name: N3W PR431 Board B exact-source artifact build

on:
  push:
    branches:
      - build/n3w-pr431-boardb-artifact-20260918

permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout exact PR431 merge source
        uses: actions/checkout@v4
        with:
          ref: d1b5c3acbd32cca95483743ffe2edba9aa3f904f
          fetch-depth: 1

      - name: Bind exact source and target
        shell: bash
        run: |
          set -euo pipefail
          TARGET="firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml"
          test "$(git rev-parse HEAD)" = "d1b5c3acbd32cca95483743ffe2edba9aa3f904f"
          test "$(git rev-parse HEAD^{tree})" = "3f161c1550e1df48db7cd5a5970db1b11932bef0"
          test "$(git hash-object "$TARGET")" = "3d13e2197520c375b56d682b37773ef28e194421"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install exact ESPHome
        run: python -m pip install --disable-pip-version-check 'esphome==2026.4.3'

      - name: Compile exact-source physical harness
        shell: bash
        run: |
          set -euo pipefail
          cd firmware/esphome_rc/board_lab/n3w_phase4_physical
          python -m esphome compile generic.yml

      - name: Verify ESP-IDF toolchain
        shell: bash
        run: |
          set -euo pipefail
          VERSION_FILE="$HOME/.platformio/packages/framework-espidf/tools/cmake/version.cmake"
          test -f "$VERSION_FILE"
          grep -Eq 'set\(IDF_VERSION_MAJOR[[:space:]]+5\)' "$VERSION_FILE"
          grep -Eq 'set\(IDF_VERSION_MINOR[[:space:]]+5\)' "$VERSION_FILE"
          grep -Eq 'set\(IDF_VERSION_PATCH[[:space:]]+4\)' "$VERSION_FILE"

      - name: Freeze Board B write artifacts
        shell: bash
        run: |
          set -euo pipefail
          ROOT="$GITHUB_WORKSPACE/firmware/esphome_rc/board_lab/n3w_phase4_physical/.esphome/build/gh-n3w-phase4-generic"
          ENV="$ROOT/.pioenvs/gh-n3w-phase4-generic"
          APP="$ENV/firmware.bin"
          OTA="$ENV/ota_data_initial.bin"
          test -f "$APP"
          test -f "$OTA"
          mkdir -p "$GITHUB_WORKSPACE/boardb-artifact"
          cp "$APP" "$GITHUB_WORKSPACE/boardb-artifact/firmware.bin"
          cp "$OTA" "$GITHUB_WORKSPACE/boardb-artifact/ota_data_initial.bin"
          {
            echo 'SOURCE_HEAD=d1b5c3acbd32cca95483743ffe2edba9aa3f904f'
            echo 'SOURCE_TREE=3f161c1550e1df48db7cd5a5970db1b11932bef0'
            echo 'TARGET_CONFIG=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml'
            echo 'TARGET_BLOB_SHA=3d13e2197520c375b56d682b37773ef28e194421'
            echo 'PYTHON_VERSION=3.11'
            echo 'ESPHOME_VERSION=2026.4.3'
            echo 'ESP_IDF_VERSION=5.5.4'
            echo "WORKFLOW_TRIGGER_SHA=$GITHUB_SHA"
            stat -c 'APPLICATION_SIZE=%s' "$APP"
            stat -c 'OTADATA_SIZE=%s' "$OTA"
            sha256sum "$APP" | awk '{print "APPLICATION_SHA256=" $1}'
            sha256sum "$OTA" | awk '{print "OTADATA_SHA256=" $1}'
          } | tee "$GITHUB_WORKSPACE/boardb-artifact/MANIFEST.txt"

      - name: Upload exact-source Board B artifacts
        uses: actions/upload-artifact@v4
        with:
          name: n3w-pr431-boardb-exact-source
          path: boardb-artifact/
          if-no-files-found: error
          retention-days: 7
```

## Expected artifact members

A successful execution must upload exactly the expected candidate material:

```text
firmware.bin
ota_data_initial.bin
MANIFEST.txt
```

No current hash is predicted. The PR #431 artifact hashes must be measured from the new build and must not inherit PR #428 or PR #425 hashes.

## Required source-to-artifact binding procedure

After the build-only workflow completes successfully, the binding gate must independently verify all of the following before declaring `PASS`:

1. workflow branch tip is a build-only commit and does not alter product source;
2. workflow file content matches the frozen template SHA-256 above;
3. workflow run checked out `SOURCE_HEAD=d1b5c3ac...`;
4. runner reported `SOURCE_TREE=3f161c...`;
5. target blob equals `3d13e219...`;
6. Python / ESPHome / ESP-IDF versions satisfy the frozen toolchain contract;
7. uploaded artifact name is exactly `n3w-pr431-boardb-exact-source`;
8. artifact metadata captures run ID, artifact ID, creation/expiry times, and archive size;
9. artifact archive is downloaded and its archive SHA-256 is frozen;
10. inner `firmware.bin` and `ota_data_initial.bin` sizes and SHA-256 values match `MANIFEST.txt`;
11. `MANIFEST.txt` binds source head, source tree, target path/blob, toolchain versions, and workflow trigger SHA;
12. the final binding record explicitly states that no board runs the artifact yet.

Any mismatch is fail-closed. A rebuild is a new artifact authority and must receive new hashes and a new binding record.

## KF-084 / artifact identity guard

A binary rebuilt later from the same source is not automatically the same artifact. Once a PR #431 artifact is bound, its application, otadata, and archive hashes become the candidate identity for the later physical route.

A documentation-only advancement of repository `main` does not change `PRODUCT_SOURCE_AUTHORITY=d1b5c3ac...`.

## Physical boundary

```text
ARTIFACT_BUILD=NOT_EXECUTED
ARTIFACT_UPLOAD=NOT_EXECUTED
ARTIFACT_BINDING=NOT_EXECUTED

BOARD_ACCESS=false
SERIAL_OPEN=false
FLASH_WRITE=false
T1_MUTATION=false

KF096_STATUS=OPEN
OVERALL_N3W_FAILOVER_ACCEPTANCE=NOT_CLOSED
```

## Next ONE gate

Preparation completion permits only a later, separately authorized GitHub/host artifact execution:

```text
NEXT_ONE_GATE=
N3W_KF096_PR431_EXACT_ARTIFACT_BUILD_AND_BINDING_EXECUTION_20260918_01

PRODUCT_SOURCE_AUTHORITY=
d1b5c3acbd32cca95483743ffe2edba9aa3f904f

ARTIFACT_BUILD_AUTHORIZATION_REQUIRED=true
BOARD_ACCESS_REQUIRED=false
FLASH_WRITE=false
T1_MUTATION=false
```

The execution gate may create the reserved build-only branch, install the frozen workflow, run the build, download/hash-bind the artifact, and write the public-safe binding record. It must not access or mutate Board B or T1.

## Public/private evidence boundary

Public GitHub may store source/tree/blob identifiers, build workflow/run/artifact IDs, public-safe hashes, toolchain versions, and sanitized build facts. Raw credentials, setup secrets, private keys, raw NVS, private host addresses, and private board identity material remain outside the public repository.
