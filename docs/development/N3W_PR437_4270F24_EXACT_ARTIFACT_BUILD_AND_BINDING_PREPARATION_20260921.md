# N3-W PR #437 4270f24 Exact Artifact Build and Binding Preparation — 2026-09-21

Status: `ARTIFACT_BUILD_PREPARATION_AUTHORITY`

Fresh exact repository/build evidence takes precedence if later evidence proves drift.

## Scope

This gate prepares the exact-source build route for PR #437 HEAD
`4270f24a92a87dd5239d781ebba624c2f34b7fc2`.

It does **not** create the reserved build branch, trigger GitHub Actions, upload an
artifact, access Board B, open serial, flash, reset, write NVS/OTA data, mutate T1,
Broker, Manager, Home Assistant, credentials, or merge PR #437.

## Fresh repository/source binding

```text
REPOSITORY=chrenguo-stack/HomeAssistant
DOCUMENTATION_MAIN_AT_PREPARATION=67fda83c8d0d5dd425cd4f82453e750b16f7e99e
DOCUMENTATION_MAIN_TREE_AT_PREPARATION=20ec2c898a5a5787d3939e2aed3f664babc8980d

PR437_STATE=OPEN_DRAFT
PR437_MERGEABLE=true
PR437_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
PR437_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f
PR437_HEAD_CI=11_OF_11_PASS
```

The product build source is the exact PR #437 head above. Later documentation-only
`main` commits do not replace that product-source authority.

## Exact build target

```text
TARGET_CONFIG=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
TARGET_GIT_BLOB_SHA=37654481747b21ca51ccecc246bf84ca437ab7a9
TARGET_DEVICE=ESP32-C6
TARGET_FLASH_SIZE=8MB
TARGET_FRAMEWORK=ESP-IDF
```

The target itself declares `min_version: 2026.4.3`, board
`esp32-c6-devkitm-1`, variant `ESP32C6`, flash size `8MB`, and ESP-IDF framework.

## Toolchain contract

```text
PYTHON_VERSION=3.11
ESPHOME_VERSION=2026.4.3
ESP_IDF_VERSION=5.5.4
```

The later build must fail closed unless the installed ESP-IDF version file reports
exactly 5.5.4.

## Reserved execution identifiers

```text
BUILD_BRANCH=build/n3w-pr437-4270f24-boardb-artifact-20260921
BUILD_BRANCH_CREATED=false

WORKFLOW_PATH=.github/workflows/n3w-pr437-4270f24-boardb-artifact-build.yml
WORKFLOW_CREATED=false

ARTIFACT_NAME=n3w-pr437-4270f24-boardb-exact-source
ARTIFACT_RETENTION_DAYS=7
```

The branch is intentionally **not created in this preparation gate**. The frozen
workflow below triggers on a push to that exact branch, so materializing it belongs
to the next build-execution gate.

## Frozen build-only workflow

Exact UTF-8 bytes, LF line endings, final newline included:

```text
WORKFLOW_TEMPLATE_SHA256=d4d708036c1eb47323186770bf8c7fa6a756dedd8f967a08eff436424c83455d
WORKFLOW_TEMPLATE_SIZE_BYTES=3441
```

```yaml
name: N3W PR437 4270f24 Board B exact-source artifact build

on:
  push:
    branches:
      - build/n3w-pr437-4270f24-boardb-artifact-20260921

permissions:
  contents: read

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout exact PR437 source
        uses: actions/checkout@v4
        with:
          ref: 4270f24a92a87dd5239d781ebba624c2f34b7fc2
          fetch-depth: 1

      - name: Bind exact source and target
        shell: bash
        run: |
          set -euo pipefail
          TARGET="firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml"
          test "$(git rev-parse HEAD)" = "4270f24a92a87dd5239d781ebba624c2f34b7fc2"
          test "$(git rev-parse HEAD^{tree})" = "a2f445bf2ea60ba9994a7a467f6492975d399c4f"
          test "$(git hash-object "$TARGET")" = "37654481747b21ca51ccecc246bf84ca437ab7a9"

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
            echo 'SOURCE_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2'
            echo 'SOURCE_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f'
            echo 'TARGET_CONFIG=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml'
            echo 'TARGET_BLOB_SHA=37654481747b21ca51ccecc246bf84ca437ab7a9'
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
          name: n3w-pr437-4270f24-boardb-exact-source
          path: boardb-artifact/
          if-no-files-found: error
          retention-days: 7
```

## Expected artifact members

A successful build must upload exactly the candidate material:

```text
firmware.bin
ota_data_initial.bin
MANIFEST.txt
```

No binary hash is predicted in advance. A rebuilt binary is a new artifact authority
and must receive newly measured application, OTA-data and archive hashes.

## Binding procedure required after build

The build-and-binding execution gate must independently prove:

1. reserved build branch parent is exact PR #437 head `4270f24...`;
2. the build-only commit changes only the frozen workflow file;
3. workflow file bytes match the frozen SHA-256 and size above;
4. workflow checks out exact `SOURCE_HEAD=4270f24...`;
5. runner observes `SOURCE_TREE=a2f445...`;
6. target path/blob equals `generic.yml` / `376544817...`;
7. Python / ESPHome / ESP-IDF versions equal the frozen toolchain contract;
8. artifact name is exactly `n3w-pr437-4270f24-boardb-exact-source`;
9. artifact metadata records run ID, artifact ID, timestamps and archive size;
10. downloaded archive SHA-256 is frozen independently;
11. inner file sizes/hashes agree with `MANIFEST.txt`;
12. `MANIFEST.txt` binds source head/tree, target path/blob, toolchain and workflow trigger SHA;
13. final binding record explicitly states that no Board runs this new artifact yet.

Any mismatch is `FAIL_CLOSED`.

## Product-source / public-safety boundary

```text
PRODUCT_SOURCE_CHANGED=false
PR437_REBASE=false
PR437_MERGE=false

BOARD_ACCESS=false
APPLICATION_SERIAL_OPEN=false
BOARD_RESET=false
FLASH_WRITE=false
NVS_WRITE=false
T1_RUNTIME_MUTATION=false
CREDENTIAL_MUTATION=false
```

Only public-safe source/tree/blob identifiers, toolchain versions, workflow/run/artifact
metadata and cryptographic hashes may be stored in GitHub. Secrets, private host
locators, raw private identities and private runtime evidence remain outside the
public repository.

## Preparation closure

```text
=== N3W_PR437_4270F24_EXACT_ARTIFACT_BUILD_AND_BINDING_PREPARATION_20260921_01 CLOSURE ===

AUTHORIZATION=GITHUB_BUILD_PREPARATION_ONLY
AUTHORIZATION_CLAIMED=NOT_APPLICABLE
AUTHORIZATION_CONSUMED=NOT_APPLICABLE

FRESH_MAIN=67fda83c8d0d5dd425cd4f82453e750b16f7e99e
PR437_HEAD=4270f24a92a87dd5239d781ebba624c2f34b7fc2
PR437_TREE=a2f445bf2ea60ba9994a7a467f6492975d399c4f
TARGET_CONFIG=firmware/esphome_rc/board_lab/n3w_phase4_physical/generic.yml
TARGET_CONFIG_BLOB=37654481747b21ca51ccecc246bf84ca437ab7a9
CURRENT_HEAD_CI=11_OF_11_PASS

BUILD_BRANCH=build/n3w-pr437-4270f24-boardb-artifact-20260921
BUILD_BRANCH_CREATED=false
BUILD_WORKFLOW_OR_EXECUTOR=.github/workflows/n3w-pr437-4270f24-boardb-artifact-build.yml
WORKFLOW_TEMPLATE_SHA256=d4d708036c1eb47323186770bf8c7fa6a756dedd8f967a08eff436424c83455d

PRODUCT_SOURCE_CHANGED=false
PUBLIC_SAFETY_CHECK=SOURCE_REVIEW_PASS; CI_REQUIRED_BEFORE_MERGE_OF_THIS_DOCS_PR

LIVE_RUNTIME_MUTATION=false
BOARD_ACCESS=false

PREPARATION_RESULT=PASS
NEXT_ROUTE=N3W_PR437_4270F24_EXACT_ARTIFACT_BUILD_AND_BINDING_EXECUTION_20260921_01
STOP=true

=== END ===
```

The next gate may materialize the reserved branch/workflow, run the exact-source build,
download and hash-bind the artifact, and write a public-safe binding record. It must
still stop before any Board/T1 mutation.
