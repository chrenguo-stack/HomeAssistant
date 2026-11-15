## 2026-11-15 — R30 STOP_RECOVERED forensic closure / no R30 USB partial mirror write / source repair / focused journal next

- The consumed R30 authorization remains permanently non-replayable; no R30 live command was re-executed.
- Real-T1 read-only forensic proved the USB transaction mirror still reports `U6_PREDECESSOR_RECOVERY_PREPARING`, with predecessor-recovery identity and HA-backup identity still null.
- `n3w-update/ha-data` and `homeassistant-preupgrade.*` are absent.
- All four USB transaction-mirror files retain pre-R30 mtimes from 2026-11-14, while R30 claim/failure state is from 2026-11-15. Therefore R30 left no persistent partial USB mirror write.
- The mirror manifest fingerprint `4014f1fb36f2c2bdff9d1af4f918a8324506c3df4e7d0720977ad9421a9de021` differs from local transaction fingerprint `e45fba0ad3e9997be2738c7a8f25d5c342ebba66ddbf822b1f6bf6a016c2ed93`; the old mirror mtime proves this drift predates R30 and is a separate continuity finding.
- The physical R30 operation failure is now bounded to the quiesce path or the first U7 metadata persistence before any mirror-file replacement.
- Source review found an internal contract mismatch: `stop_services()` accepts systemd owner states `inactive` or `failed` after verified container shutdown, while `quiesce_homeassistant_for_backup()` previously accepted only `inactive`.
- Bounded source repair aligns the quiesce predicate with the stop contract and adds a regression case for a `failed` owner with Manager/HA stopped and Broker preserved. Repair/test head: `f96ca9c7eb9f50796e8c22dcb7cd0a5d3943bccc`.
- This source defect is highly relevant but is not yet claimed as the physically proven R30 root cause. The remaining evidence gate is a focused read-only journal window around the R30 stop/recovery event.
- Manager, Home Assistant and Broker were observed running after recovery; owner units were active/running with Result=success and NRestarts=0.
- Next gate: `N3W_T1_R30_FOCUSED_TIME_WINDOW_JOURNAL_READONLY`. No live mutation, authorization replay, U7 retry or U8+ action is authorized.
