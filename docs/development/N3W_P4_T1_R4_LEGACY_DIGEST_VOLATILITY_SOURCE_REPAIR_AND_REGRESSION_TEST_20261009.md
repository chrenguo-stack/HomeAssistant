# N3-W P4 T1 R4 — legacy digest volatility source repair and regression gate (2026-10-09)

## Authority and latest reviewed evidence

User explicitly approved `N3W_P4_T1_R4_LEGACY_DIGEST_VOLATILITY_SOURCE_REPAIR_AND_REGRESSION_TEST` immediately after the R4 independent review concluded `A1=OPEN_BLOCKER`. Approval covers GitHub source repair, synthetic tests, review and progress synchronization. **Not** R4 T1 cutover, deletion of R2/R3 forensic evidence, Broker/network change, board boot, Setup Secret import or PR merge.

Pre-repair review authority: `docs/development/N3W_P4_T1_R4_EXACT_SOURCE_INDEPENDENT_REVIEW_AND_PRELIVE_GATE_20261009.md`. Review was against exact eleven-source ref `2d9ee7999d525e0812774a106863e2e6bf55d5ec`; previous 132 tests passed but **did not test the mismatch-flag flip**.

## Root cause and single-field correction

R4 source `r4_shadow_stable_fingerprint.py` has two separate contracts.

1. `verify_legacy_r3_seal_readonly(private)` verifies R5 original rollback authority and full R2 Manager/Broker/rollback/shadow contracts. It reads immutable R3 private seal and requires **the only allowed difference** in saved-versus-live R3 forensic evidence be the R2 shadow's legacy `r2_shadow_inspect_sha256` (the SHA of Docker's **entire** inspect JSON). It rejects all other changes and validates the legacy SHA format. It may return `legacy_full_inspect_digest_mismatch` as a *transient forensic classification*.
2. `r4_authority_document(private)` constructs the durable SHA-protected R4 security identity from the R3 seal's unmodified bytes SHA, original Manager/Broker/shadow IDs, R2 journal SHA, and a **stable protected-state** shadow SHA over identity/config/environment/labels/mount/log/network/security/restart controls. Pre-repair it incorrectly included `r3_legacy_digest_mismatch_classified=review['legacy_full_inspect_digest_mismatch']` as a persistent field. The transient boolean can switch True/False on later reads of whole Docker inspect even if protected security is unchanged, resulting in a spurious `R4_SEAL_PROTECTED_STATE_DRIFT`.

**Repair:** remove only `r3_legacy_digest_mismatch_classified` from the durable R4 equality document. Retain legacy comparison/classification and every original R2/R3 strict authority verification. Preserve historical R2/R3 files, their original digest values and the immutable SHA of saved R3 seal bytes. No change to live Manager/Broker, mounts, original RW, R5 or systemd. No relaxation of any allowed-difference policy.

## Test contract and result

Added executable synthetic regression for **both directions**:

- A previously differing whole-inspect legacy SHA becomes equal on next read (**True→False**).
- A previously equal whole-inspect legacy SHA becomes different on next read (**False→True**).

Both tests go through `seal_r3_for_r4` then `require_r4_seal` using mock `r3._private_json`, two distinct `r3.verify_r2` snapshots and a fixed actual protected-shadow fixture. They assert the new sealed JSON **does not contain** `r3_legacy_digest_mismatch_classified`, and file bytes stay unchanged. Separate regression switches the legacy mismatch boolean *and* changes original Manager identity, proving an unrelated protected-state drift is still rejected. Existing tests also reject R3 non-SHA evidence mismatch, different IDs/journal/rollback, Docker mount/env/log/network/security drift, R4 seal replay, and R3 cutover residue.

```text
TASK=N3W_P4_T1_R4_LEGACY_DIGEST_VOLATILITY_SOURCE_REPAIR_AND_REGRESSION_TEST
CODE_REPAIR_COMMIT=cf878f7f5228756f8b9ff822eeeb262486d63ae9
CODE_REPAIR_BLOB_SHA1=8e4a6f5505c01b655ce991a46947485c791b0598
REGRESSION_TEST_COMMIT=938ff0686a02e3633f96d6e421789ecdd4cabefd
FIRST_REPAIR_SYNTHETIC_CI_RUN=37949198269
FIRST_REPAIR_SYNTHETIC_CI_RESULT=134_PASS
R4_REPAIRED_ELEVEN_SOURCE_REF=938ff0686a02e3633f96d6e421789ecdd4cabefd
R4_EXACT_MAC_LAUNCHER_REBIND_COMMIT=8f7c5fdc5a7a3b91b4bc546ff6b3b1fa22d49033
R4_EXACT_MAC_LAUNCHER_REBIND_BLOB_SHA1=bde632153e9f0223bf5675a1f6889505f18b215d
R4_LAUNCHER_TEST_COMMIT=251126d94de737aa8ac0acaa81a98e1fa48948b1
LATEST_LAUNCHER_TEST_CI_RUN=37949312185
LATEST_MANAGER_CI_RUN=37949312047
LATEST_MANAGER_CI_STATUS=PASS
LATEST_PUBLIC_SAFETY_CI_RUN=37949311925
LATEST_PUBLIC_SAFETY_CI_STATUS=PASS
LATEST_LAUNCHER_TEST_CI_STATUS=134_PASS
R4_LIVE_T1_ACCESS_THIS_GATE=false
R4_LIVE_REPLACEMENT_AUTHORIZATION=false
R4_PRODUCTION_EXECUTION=false
AUTO_RETRY=false
```

The exact Mac launcher continues to pin eleven reviewed scripts from one immutable source commit and uses the same independent R4 stage, transaction filename, authorization ID, systemd unit, R4 forensic seal and bounded fail-closed behavior. **This gate does not publish a runnable T1 replacement command.**

## STOP and handoff

```text
A1_STATUS=SOURCE_REPAIR_CI_PASS_PENDING_INDEPENDENT_CLOSURE
A2_R4_TRANSACTION_ISOLATION=UNCHANGED
A3_IDENTITY_BOUND_SUPERVISED_ROLLBACK=UNCHANGED
A4_SIX_MOUNTS_BROKER_LOGGING=UNCHANGED
A5_ELEVEN_SOURCE_EXACT_BINDING=UPDATED
A6_SYSTEMD_300S_VS_OPERATOR_430S=OPEN_NONBLOCKING_NOTE
NEXT_ONE_GATE=N3W_P4_T1_R4_A1_REPAIR_EXACT_SOURCE_INDEPENDENT_CLOSURE_AND_PRELIVE_DECISION
R4_LIVE_AUTHORIZATION=false
NO_T1_MUTATION=true
R2_R3_HISTORY_AND_R5_OLD_DATA=KEEP
BOARD_BOOT=false
SETUP_SECRET_IMPORT=false
BROKER_MUTATION=false
MERGE=false
```

Final protected-source and launcher test head CI completed with 134 PASS, Manager CI PASS and Public safety CI PASS. Source repair Gate now PASS, but a later independent review should confirm the A1 boolean cannot re-enter the durable authority through any alternate caller. An independent prelive decision, and then a **separate explicit R4 production authorization**, remain mandatory before any T1 cutover.
