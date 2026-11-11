# N3-W T1 KF-147 CI Exact Artifact Rerun Design Repair Progress
# 2026-11-11

## Evidence

Manager A-to-B run `43038325461` failed twice at the same step.

Attempt 2 again completed exact package generation and upload, then the immediate exact-ID download
reported that one artifact was visible but still rejected the newly emitted artifact ID. Therefore
the earlier "single propagation race" classification is superseded.

## Repair

```text
BASE_HEAD=8cbf63f3af4c2a904770842a3a223c97b56c1630
CI_REPAIR_HEAD=8d6024ae889951eab1ff2427ad60e4a5598c8065
WORKFLOW_BLOB=999143c92602fe5750d8d622bc8051e78885c421
CONTRACT_TEST_BLOB=57de39107aca458ac86b794150a145a1d3f6c02e
```

The two Manager package exact-ID download steps now include:

```text
github-token: github.token
repository: github.repository
run-id: github.run_id
```

The exact artifact ID remains the selector. No name-based fallback was introduced.

This follows the current download-artifact contract: supplying a GitHub token selects the public
GitHub API path and permits explicit repository/run binding. This also avoids relying on the
rerun-sensitive internal current-run artifact lookup behavior.

## New CI at polling stop

```text
MANAGER_A_TO_B_RUN=43039728250
MANAGER_SOURCE=IN_PROGRESS
TARGET_BINDING_RUN=43039727825
TARGET_BINDING_SOURCE=IN_PROGRESS
FAST_CONTRACT_RUN=43039728013
FAST_CONTRACT=SUCCESS
PUBLIC_SAFETY_RUN=43039728077
PUBLIC_SAFETY=IN_PROGRESS
CI_POLL_LIMIT_REACHED=true
FULL_CI_PASS=false
```

Run links:
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43039728250
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43039727825
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43039728013
- https://github.com/chrenguo-stack/HomeAssistant/actions/runs/43039728077

No T1 access is allowed until this exact source head reaches terminal applicable CI success.
