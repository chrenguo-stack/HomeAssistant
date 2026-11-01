# N3-W Current Development Progress Alignment — 2026-09-06

Status: `CURRENT_PROGRESS_AUTHORITY`

This document records the repository/test-progress alignment performed on 2026-09-06. It exists to keep current development status, official ESP-NOW reference evidence, KF-089 disposition, and R1R4 diagnostic evidence on one consistent route.

## 1. Repository authority

At the start of this alignment:

- repository: `chrenguo-stack/HomeAssistant`
- `main`: `0be04aa0ca0c9bbce569da9518e38fd3cbd8db9f`
- active product-direction authority: `docs/development/N3W_OFFICIAL_ESPNOW_REFERENCE_PRODUCT_DIRECTION_DECISION_20260906.md`

The active product direction is therefore:

1. Fix the provisioned cold-boot startup architecture.
2. Prefer Espressif official low-level channel-control APIs.
3. Keep only a small N3-W application-level discovery/path-selection policy layer.
4. Do not implement a full custom Wi-Fi/ESP-NOW radio-ownership state machine unless later evidence proves it necessary.
5. Continue validating `current-channel peer + official controlled channel operation` as an N3-W candidate; do not describe it as an Espressif-recommended architecture.
6. Treat cross-channel operation as a bounded fallback discovery capability; current/last-known channel comes first.

## 2. Product / physical progress

The latest real-world Board B route remains consistent with the repository record:

- normal Direct operation had previously been proven;
- provisioned cold boot with Direct Wi-Fi unavailable failed to acquire Relay;
- the product-source blocker is KF-089: current runtime startup requires live Wi-Fi before the Relay-capable N3-W runtime can start;
- this is a product bootstrap/runtime defect and is considered deterministically repairable in software;
- live Direct-to-Relay failover remains a separate acceptance question and must not be inferred from the cold-boot failure.

KF-089 implementation remains deferred until the remaining official-reference lifecycle evidence is sufficiently closed.

## 3. Official ESP-NOW reference progress

Exact official authorities used by the current reference route:

- Espressif ESP-IDF: `735507283d5b2f9fb363a1901172dbd9e847945d`
- pioarduino framework: `8de41af2dbb81bc443a8d7986ebd152f82e10bba`

Already established on ESP32-C6:

- two-board basic ESP-NOW communication works;
- home-channel ESP-NOW communication works;
- a Wi-Fi-connected DUT can perform the official controlled off-channel transmit operation;
- a control node can remain on the target channel for a bounded interval;
- an ESP-NOW frame can actually be delivered on that target channel.

Still requiring reliable physical evidence before product implementation is finalized:

- reverse reception during the bounded off-channel operation;
- ending/cancelling the bounded operation;
- reliable return to the original home channel;
- Wi-Fi association recovery where applicable;
- resumption of normal home-channel ESP-NOW operation.

These unresolved items are evidence gaps. They are not evidence that Espressif ESP-NOW is insufficient.

## 4. R1R3 / R1R4 diagnostic progress

R1R3 physical attempts did not establish an RF failure. The diagnostic firmware executed and both boards were restored safely, but the serial evidence channel produced zero-byte captures. Therefore the official off-channel lifecycle result remained unadjudicated.

R1R4 is an evidence-harness hardening successor, not a product-source repair.

Frozen R1R4 diagnostic authority:

- source commit: `1b89639f9454ea725da1fef32564f5cdfa006289`
- tree: `b2b815283deb1cbc976eab74c38ca096dd23b90d`
- branch: `diag/n3w-r1r4-usb-console-evidence-20260905`

The diagnostic branch later advanced to `b99f7600378fe4c66744bfce19796e399cb469bc`; the only delta from the frozen R1R4 source authority is documentation, so the build-relevant surface remains equivalent.

### Historical R1R4 CI

Original run/job:

- run `33957392009`
- job `101283085978`
- failed step: `Build CONTROL diagnostic image`
- observed step exit annotation: exit code `2`

The historical forensic route is closed by decision. The Step 8 runtime body and exact first failing internal command were not recovered with sufficient authority, so the historical root cause remains unadjudicated. No further historical CI archaeology is required for forward progress.

### Current successor CI

Successor run/job:

- run `33972172414`
- job `101322504129`
- head `b99f7600378fe4c66744bfce19796e399cb469bc`
- result: failure at the same Step 8
- observed step exit annotation: exit code `2`

Structured metadata proves that the multi-command Step 8 failed. It does **not**, by itself, prove that `idf.py build` was the failing internal command or that the USB-console configuration oracle was reached.

Therefore the current R1R4 blocker is the CONTROL diagnostic Step 8/evidence harness. It is not yet a proven product defect and not a proven Espressif ESP-NOW failure.

An unchanged CI rerun is not recommended merely to repeat the same failure.

## 5. Evidence quarantine discovered by this alignment

A separate historical evidence branch exists:

`evidence/n3w-r1r4-key-test-logs-20260905`

It contains:

`docs/development/evidence/n3w_r1r4_20260905/CI_JOB_101283085978_FAILURE_EXCERPT.log`

That file describes the claimed Step 8 failure using a `pio run` command surface and an `esp_app_desc.h` compile error.

However, the exact workflow at the frozen R1R4 commit for the same claimed Step 8 uses the `idf.py set-target` / `idf.py reconfigure` / `idf.py build` command sequence followed by sdkconfig assertions. The two command surfaces cannot both be the exact runtime Step 8 for the same job authority.

Because the original raw job log body has not been independently rebound, this evidence file is quarantined:

- it is historical material only;
- it must not be used to claim the original R1R4 root cause;
- it must not be used to authorize a product/source repair;
- exact workflow/run/job evidence takes precedence.

This quarantine does not reopen the historical CI forensic route.

## 6. Known-failure index alignment

`docs/development/KNOWN_FAILURES_AND_REGRESSION_GUARDS.md` currently centralizes entries through KF-086. The 2026-09-04 Board B real-world route introduced KF-087, KF-088 and KF-089 in the dedicated disposition document:

`docs/development/N3W_BOARD_B_REAL_WORLD_FAILOVER_KF087_KF089_DISPOSITION_20260904.md`

For current development authority, those three IDs and their dedicated disposition remain valid. The central index should be backfilled without renumbering or redefining them. The evidence-misbinding risk identified in Section 5 is a separate CI/evidence-authority guard and must not change the meaning of KF-087 through KF-089.

## 7. Current forward route

The development route after this alignment is:

1. Keep the historical R1R4 CI forensic route closed.
2. Resolve the current R1R4 evidence-harness blocker only to the extent needed to obtain reliable physical evidence; do not repeat broad historical root-cause archaeology.
3. Complete the remaining official bounded off-channel lifecycle evidence on ESP32-C6.
4. Re-evaluate KF-089 against the official-reference results.
5. Implement the smallest product repair consistent with the active direction document.
6. Run host regression and bounded physical validation.
7. Return to the three-board/T1 real-world Direct → Relay → Direct acceptance route.

## 8. Authority order after alignment

When records disagree, use this order:

1. fresh exact repository / GitHub Actions / physical evidence;
2. active product-direction decision;
3. this current-progress alignment;
4. dedicated failure/disposition documents;
5. older handoffs and historical evidence branches;
6. inference.

No historical evidence branch may override an exact workflow/run/job binding merely because it contains a copied log excerpt.

## 9. Alignment conclusion

The main product route and official ESP-NOW reference route are aligned with current development intent.

Two repository-record issues were identified:

1. the R1R4 historical evidence branch contains a root-cause excerpt whose command surface conflicts with the exact frozen workflow and is therefore non-authoritative;
2. KF-087/KF-088/KF-089 are valid in their dedicated disposition but are not yet mirrored in the central known-failure index.

The first issue is quarantined by this authority document. The second is an index-backfill task only and does not change current product/test state.
