# H3 RC2 Shared Package Compatibility CI — source repair and independent gate

## Purpose

Preserve the old H3 Stage 2D-2 / 2D-3 / 2D-4 experiment-target compile regression when a shared RC2 package changes, while leaving the historical stage-specific exact source boundary gates untouched.

\`\`\`text
TASK=N3W_PR524_H3_RC2_SHARED_PACKAGE_COMPATIBILITY_CI_SOURCE_DESIGN_AND_PREEXECUTION_20261008_01
SOURCE_BASE_PR=474
SOURCE_BASE_SHA=d3c158b4376ca0577e4a3a45a18a6c5c6e994e75
INDEPENDENT_BRANCH=fix/n3w-h3-rc2-shared-packages-compatibility-ci-20261008
ORIGINAL_H3_BOUNDARY_GATES_MODIFIED=false
ORIGINAL_H3_WORKFLOWS_MODIFIED=false
FIRMWARE_AND_MANAGER_MODIFIED=false
H3_HISTORICAL_SCOPE_EXCEPTION=NOT_APPROVED
P4_NORMAL_BOOT_AUTHORIZED=false
MERGE=false
STOP=true
\`\`\`

## Source design

New workflow: \`.github/workflows/h3-rc2-shared-packages-compatibility-ci.yml\`.
New stage runner: \`tools/h3_rc2_shared_packages_compatibility.py\`.
New source-contract tests: \`tests/h3_compat/test_h3_rc2_shared_packages_compatibility.py\`.

Trigger: exactly the five shared RC2 configs \`core.yml\`, \`control.yml\`, \`buses.yml\`, \`sensors.yml\`, \`display.yml\`, plus the new workflow/runner/test paths for self-regression. This job does not run on changes to \`n3w_product_transport.yml\` alone; that path remains monitored by the dedicated N3-W product convergence workflow.

For each matrix stage \`d2\`, \`d3\`, \`d4\`, run the exact legacy C++ host fault-matrix sources with the original compiler strictness and \`-lcrypto\` on D4. Then generate short-lived random test-only Wi-Fi credentials in the corresponding \`board_lab/h3_*/secrets.yaml\` directory; refuse to overwrite any preexisting file. Run the original minimal ESPHome configuration and compile and original full RC2 product-PCB lab configuration and compile. Pin \`esphome==2026.4.3\`. Verify both outputs contain the stage component, lab component, and \`INFO Successfully compiled program.\` marker. Delete ephemeral secrets in \`finally\`, and capture all compiler/config logs to temporary paths; never print unredacted compile output or credential values. Sanitized excerpts are only printed on failure.

Existing H3 exact changed-path source gates are NOT invoked because they are stage-development source-boundary gates, not present-day RC2 package compatibility checks. Their files and original workflows remain unchanged, preserving independent historical acceptance evidence. The new compatibility job does not claim original H3 source-boundary acceptance.

CI architecture: fast source-only contract job, followed by 3 stage jobs (\`max-parallel=2\`, \`fail-fast=false\`, bounded timeout). Workflow \`concurrency\` isolates different PRs/events and uses PR-only supersession on newer commits. No firmware artifacts are published and no real device/host connection or Setup Secret is used.

## Acceptance and explicit caveats

- Each H3 stage needs both actual ESP32-C6 compilations and its host fault matrix to report success.
- Synthetic/source-contract PASS alone is insufficient. If package downloads yield HTTP 403, the job is still FAIL and must be classified as an external dependency download blocker instead of product compile PASS.
- A GitHub Actions new workflow run on the PR #474 upstream base alone does not establish compatibility with the *modified P4 packages in PR #522*. A separately verified integration against the exact P4 HEAD must take place before treating this as the successor protection for the H3 scope exception.
- Some historical H3 ESP32-C6 lab targets include their own component setup. Firmware compilation regression is not equivalent to full device runtime pairing acceptance.
- Public safety, secrets handling, F1.0-RC2, N3-W product CI and the three original H3 source gates remain in force.

\`\`\`text
CURRENT_STAGE=SOURCE_REPAIR
SOURCE_CONTRACT_CI=PENDING
H3_D2_MINIMAL_AND_FULL_COMPILE=PENDING
H3_D3_MINIMAL_AND_FULL_COMPILE=PENDING
H3_D4_MINIMAL_AND_FULL_COMPILE=PENDING
NEXT_ONE_GATE=N3W_H3_SHARED_RC2_COMPATIBILITY_CI_REAL_RUN_AND_PR522_INTEGRATION_SOURCE_REVIEW_20261008_01
H3_EXCEPTION=HOLD
MERGE=false
STOP=true
\`\`\`
