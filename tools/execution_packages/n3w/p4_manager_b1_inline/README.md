# B1I1 — inline Manager fresh-state transaction (SOURCE-ONLY)

This package implements the isolated **transaction core and simulated safety guards** for N3-W P4 B1 fresh Manager deployment. It is **not a production deployer**. There is no Mac launcher, T1 live Docker adapter, deployed systemd unit, or CLI entry point.

## Implemented in this source-only gate

- `b1i1_contract.py`: independent B1I1 journal/containers/6-mount/health intent and fail-closed operation interface; 40-hex Git source ref.
- `b1i1_journal.py`: 0700 private root, 0600 exclusive first journal, fsync + atomic updates, durable phase intent, independent B1I1 names, no replay, phase/commit state validation.
- `b1i1_transaction.py`: explicit preparation and durable old-stop/old-park/candidate-create/start/postflight/commit phases, candidate ownership re-inspected before start, known-exception same-process rollback, independent committed final read-only check and unknown-freeze.
- `b1i1_recovery.py`: exact original/Broker/candidate authority, recovery of candidate created before candidate ID was durably written only after operation-provided ownership proof; on unknown foreign container freeze with no quarantine; committed never auto-rolls back.
- `b1i1_supervisor.py`: finite deadline/reserved rollback calculations and host-owned/no-SSH transaction plan validation; **does not install or configure a real host service**.
- `b1i1_host_runner.py`: source-only injected host ownership/authorization and one-shot durable marker; **does not invoke Docker**.
- `b1i1_preflight.py`: pure live Manager/Broker/R5/HA/TLS and exact six-bind snapshot guard, no host access.
- `b1i1_fresh_state.py`: fresh 3 RW source overlap rejection, exact same 3 RO authorities and 10 required business tables zero + relay keys empty; **does not open real SQLite databases**.
- `test_b1i1_transaction.py`, `test_b1i1_recovery.py`, `test_b1i1_guards.py`, `test_b1i1_host_runner.py`: all runtime actions are simulated; failure injections, kill/SSH ambiguity, recovery and no replay.
- `.github/workflows/n3w-p4-b1i1-inline-synthetic-ci.yml`: self-contained compileall and Python unittest suite, no production or board access.

## Security / prelive STOP boundary

The `Operations` protocol is an **injected adapter interface**, not a proof of a real T1 operation. Its future implementation must enforce exact trusted image hash, environment, UID/GID, source mounts, live Broker/TLS/R5/HA and Board-off constraints, strict transaction-owned candidate labels/image/mount identity, actual `/healthz` and UDP47111/TCP47112/IPC/TLS8883 readiness and actual SQLite table schemas/zero state. It must preserve the original Manager container *by the same ID* and original three RW sources.

The host-owned plan currently accepts a `host_unit_verified` boolean supplied by a caller; the **actual versioned systemd owner, independent complete budget including rollback, crash supervisor and verified source/artifact launcher do not yet exist**. The source has no invocation path for live T1. No exit value from this simulated package is accepted as real deployment evidence.

**Known risks requiring independent review**: source snapshot lifetime/TOCTOU, candidate create→journal-ID crash and label/token provenance, unknown collision handling, committed-vs-finalized outcome on SSH loss, failure of journal fsync, exact no-replay guarantee, rollback full health and R5, complex runtime timeouts, externally supplied status attestations, old Manager unexpected auto-restart, Broker/DynSec residual node accounts. Source smoke CI cannot prove real Docker/systemd/HA behavior.

No R2/R3/R4 historical forensic record, R5 private backup, old data or production service is altered by this repository code.

```text
LIVE_DEPLOYABLE=false
REAL_T1_ADAPTER=false
REAL_HOST_SERVICE=false
EXACT_RELEASE_ARTIFACT=false
T1_LIVE_AUTHORIZATION=false
AUTO_REPLAY=false
```
