# N3-W Current State Index

Current authority: `docs/development/N3W_CURRENT_STATE.md`  
Latest physical evidence addendum: `docs/development/N3W_KF089_BOARD_A_DURABLE_DIAG_BASELINE_PASS_20260907.md`  
Previous remote-T1 contract-stop addendum: `docs/development/N3W_KF089_REMOTE_T1_WINDOW_CONTRACT_STOP_20260907.md`  
Previous harness addendum: `docs/development/N3W_KF089_OBSERVABILITY_BASELINE_HARNESS_BLOCKER_20260907.md`  
Detailed 2026-09-07 reconciliation archive: `docs/development/N3W_KF089_LOCAL_CHAT_GITHUB_ALIGNMENT_ARCHIVE_20260907.md`  
Post-merge archive correction: `docs/development/N3W_KF089_ALIGNMENT_ARCHIVE_POSTMERGE_CORRECTION_20260907.md`  
Dated progress pointer: `docs/development/N3W_CURRENT_DEVELOPMENT_PROGRESS_ALIGNMENT_20260907.md`

The latest physical evidence addendum supersedes earlier next-gate wording where those records differ. Board A now has a fully closed serial-free Direct baseline: remote T1 canonical acceptance is PASS, the schema-v3 durable diagnostic snapshot is bound to the same boot session, Direct channel 11 is proven, scan activity is zero, and gateway advertisement/broadcast completion is 1304/1304 with zero failures. Board A remains in ROM Download Mode; app1 is exact observability firmware and app0 still requires separately authorized normalization.

Current next gate:

```text
NEXT_GATE=KF089_BOARD_A_APP0_NORMALIZATION_AND_POSTCHECK
```

This index exists to make the current N3-W state easy to locate from repository search without relying on historical handoff filenames.
