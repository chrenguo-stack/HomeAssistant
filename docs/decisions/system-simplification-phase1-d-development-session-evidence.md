# Phase 1 Decision D: development session / claim / evidence simplification

- Status: **ACCEPTED / ARCHITECTURE CONTRACT FREEZE**
- Date: 2026-08-16
- Scope: development execution governance and private evidence custody
- Phase boundary: contract + host simulation only; historical evidence is immutable

## 1. Decision

Normal source editing, lint, unit tests, host simulation, documentation and compile work SHALL be governed by Git/PR/CI and do not require a new single-use product execution authorization for every tooling failure.

A development session has one plan and one evidence root:

```text
evidence/<session_id>/
    plan.json
    environment.json
    result.json
    hashes.json
    logs/
```

The execution flow is:

```text
plan
-> approval when a protected action is in scope
-> precheck
-> claim
-> execute
-> verify
-> terminal
```

## 2. Protected claim boundary

An explicit claim remains required immediately before operations whose effects are physical, security-sensitive, production-mutating or otherwise not safely undone by reverting source code.

Examples:

- Flash/erase;
- Reset/power state operations when they affect a bound physical test;
- one-shot RF/control stimuli;
- production Broker/Manager/Home Assistant mutation;
- production T1 deployment;
- credential issuance/revocation against a live environment;
- canonical secret-store mutation;
- eFuse or security-key rotation.

## 3. Pre-claim failure

Examples:

- path typo;
- missing file;
- import error;
- checksum mismatch;
- Docker unavailable;
- static contract failure;
- host compiler/linter failure.

Frozen result:

```text
CLAIM=false
MUTATION=false
SESSION_CONSUMED=false
```

The executor may be corrected and the same session/approval may retry precheck. No successor PR/package/authorization is created solely because of such a host-tooling failure.

## 4. Post-claim failure

If the protected operation has already been claimed and executed or materially begun:

```text
CLAIM=true
SESSION_CONSUMED=true
```

A repeat protected attempt requires a new claim/approval boundary as appropriate.

Silent replay remains prohibited.

## 5. Evidence rules

KEEP:

- exact source/target binding for protected actions;
- private secret/evidence exclusion from public Git;
- immutable raw evidence after protected execution;
- terminal PASS/FAIL classification;
- auditability of who/what/when was executed.

SIMPLIFY:

- one session root instead of parallel package/sidecar/closure roots;
- execution package becomes derived material, not a second authority;
- ordinary host failure remains inside the same session before claim.

Historical R8 and prior immutable evidence remain frozen. R8 tester credential repair remains retired and cannot be restored or replayed.

## 6. Required host cases

- failed precheck leaves session reusable and unconsumed;
- successful precheck permits a claim;
- claim is single-use for a protected attempt;
- failure after claim leaves the session consumed;
- an unclaimed host-only workflow can be retried without creating a successor identity.

The Phase 1 host simulation freezes these state transitions without creating a new execution framework yet.
