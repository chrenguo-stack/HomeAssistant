# N3-W PR #523 CI 独立源码复核与 PR #522 四项失败归类（2026-10-08）
```text
TASK=N3W_PR523_SOURCE_REVIEW_AND_PR522_CI_FAILURE_TARGETED_REPAIR_20261008_01
PR523_REVIEW_HEAD=4c943f072230a47de9f7a7a535a7b5ccacfd91e3
PR523_REVIEW_RESULT=SOURCE_SCOPE_PASS
PR523_CI=13_OF_13_SUCCESS
PR523_MERGED=false
PR522_PRE_REPAIR_HEAD=2b236d2a2e58d907c906abbadbe5910162b251b8
PR522_OLD_HEAD_CI=24_SUCCESS_4_FAILURE
PR522_R3_PRIVATE_QR_SYNTHETIC_CI=SUCCESS
PR522_NEW_HEAD_CI=UNVERIFIED_AFTER_FIX
BOARD_ACCESS=false
T1_ACCESS=false
MANAGER_MUTATION=false
REAL_SETUP_SECRET_IMPORT=false
MERGE=false
STOP=true
```

## PR #523 source-only final review

PR #523 targets `fix/n3w-production-relay-discovery-full-channel-fallback-v1-source-repair-20260924` (the direct upstream branch of PR #522), not main. Three diff files: exactly two N3-W non-artifact radio-contract CI workflow files plus one CI triage document. Both YAML diffs each add exactly the four-line top-level policy:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

All other workflow content is byte-for-byte identical to the prior branch. This cancels superseded jobs only for the **same workflow and the same PR**; distinct PRs do not share groups, and push events use a run-unique ID and do not cancel each other. It does not control existing old runs retroactively. Exact artifact release and physical acceptance workflows are not modified. Source scope accepted, 13/13 CI success; **no merge or application of the rule to PR #522 yet**.

## PR #522 latest old-head CI forensic classification

- `N3W P4 private pairing binder R3 synthetic regression` run `37773627791`: SUCCESS; Python compile and synthetic tests successful. This is not physical pairing acceptance.
- `Public repository safety CI` run `37773627853` failed in `Scan tracked files without echoing matches`: seven matches of `private-network-address` in two *synthetic test files*: `test_bridge_handoff.py` lines 170,171 and `test_host_readonly.py` lines 66,75,82,88,105. The scanner itself is working correctly.
- `H3 N2 Stage2D2 Candidate MQTT Validator CI` run `37773627820`: `Verify Stage 2D-2 source and production boundaries` failed. Exact diagnostic artifact `stage2d2-candidate-mqtt-boundary-v50` ID `11551555622` shows 140 PR-changed files outside the permitted Stage2D2 scope.
- `H3 N2 Stage2D3 Activation Transaction CI` run `37773627796`: `Verify Stage 2D-3 source and production boundaries` failed. Diagnostic artifact `stage2d3-activation-boundary-v51` ID `11551000231` lists unexpected paths and explicitly protected production `core.yml`/`display.yml`.
- `H3 N2 Stage2D4 Profile Lifecycle Integration CI` run `37773627711`: `Verify Stage 2D-4 source and production boundaries` failed. Diagnostic artifact `stage2d4-profile-lifecycle-boundary-v52` ID `11550272101` likewise lists unexpected paths and protected reviewed `core.yml`/`display.yml`.

The H3 failures are **intentional scope-guard failures for a broad, stacked PR**, not execution traces proving an ESP32-C6 or Manager functional bug. Do not weaken, skip, delete or globally ignore the scope guards. Because source scopes are legitimately broad in PR #522, closing those failures requires a separate review of PR topology and the protected-file boundary; a cosmetic test change cannot close them.

## Public safety targeted repair

Change exactly two **test-only** source files from an arbitrary local/private IP literal to documentation-only `192.0.2.10` (RFC 5737 TEST-NET-1). The actual SSH target binding logic, Manager, firmware, source-only secret importer, TLS trust and CLI remain unchanged. Python `ipaddress` classifies that synthetic address as non-loopback and `is_private=true` for the unit test, while the repository private-network literal scanner does not match it. The seven reported scanner occurrences are replaced; do not change `tools/check_public_repository_safety.py` or its scan policy.

```text
PUBLIC_SAFETY_FIX_FILES=2_SYNTHETIC_TESTS_ONLY
ACTUAL_PRIVATE_NETWORK_ADDRESS_EXPORTED=false
SCAN_RULE_WEAKENED=false
PUBLIC_SAFETY_NEW_CI=AWAIT_NEW_HEAD_RESULT
PREVIOUS_522_HEAD_FAILS_RETAINED_AS_HISTORICAL_EVIDENCE
```

## Next authorized engineering step

```text
NEXT_ONE_GATE=N3W_PR522_POST_PUBLIC_SAFETY_FIX_CI_REVIEW_AND_H3_PROTECTED_SCOPE_DISPOSITION_DESIGN_20261008_01
PR523_MERGE_AUTHORIZED=false
PR522_MERGE_AUTHORIZED=false
P4_FIRST_NORMAL_BOOT_AUTHORIZED=false
P4_SETUP_SECRET_IMPORT_AUTHORIZED=false
STOP=true
```
