# H3/N2 Stage2D-9R G3R D2-11 Python bytecode self-contamination repair

Decision:
`D1-H3N2-STAGE2D9R-G3R-D2-11-PYTHON-BYTECODE-SELF-CONTAMINATION-REPAIR-20260729-01`.

## Scope

This add-only source repair is stacked on Draft PR #208 at exact HEAD
`34286f73e710dca63c6348f0fc6457496cb1c493`. It fixes only:

- Python bytecode generation before the frozen-package contract check;
- loss of the stable leaf code from `ContractError`;
- the missing real writable-package shell integration test.

It does not modify any PR #208 file, firmware payload, immutable payload,
recovery payload, request, authorization, execution package or closure.

## Failed D2-11 private package

The attempted D2-11 package stopped during `AUTHORIZATION_CONTRACT_CHECK`.
Its authorization was neither claimed nor consumed. No USB/serial enumeration,
esptool, Flash, network, PREPARE, VERIFY or recovery operation occurred.

The root cause is:

```text
D2_11_CONTRACT_CHECK_SELF_CONTAMINATES_FROZEN_PACKAGE_WITH_PYTHON_BYTECODE
```

The old inner launcher started Python without disabling `.pyc` writes. Importing
the frozen package modules created `__pycache__`; the package contract then
correctly rejected the unexpected directory. The old private package and its
authorization are fixed as `PRECLAIM_CONTRACT_FAILED` and must not be retried,
replayed or reused even though claim did not occur.

## Repaired launch contract

The repaired inner launcher must:

1. assign `PYTHONDONTWRITEBYTECODE=1`;
2. export it before selecting or invoking any Python executable;
3. inherit the setting into the wrapper and every imported module;
4. never reset the setting before `exec`.

A future private outer runner must independently export the same setting before
it starts any Python process or invokes the inner launcher. The future D2-12
binding must test both layers.

The wrapper refuses direct operation when Python was not started with bytecode
writes disabled. This source-only wrapper also rejects `execute` with
`D2_12_EXECUTION_BINDING_REQUIRED`; it permits only status and pre-claim
`contract-check`.

## Failure-code contract

For the upstream contract exception, a single argument matching
`^[A-Z][A-Z0-9_]{0,127}$` is returned as the public failure code. Any other
contract text is reduced to `ContractError`. Non-contract errors retain the
existing class-only mapping. Raw exception text and host paths are never
returned or persisted.

## Real writable-package test

The shell integration test uses the exact PR #208 Artifact
`8726419477` (`60dc9f3c...b8583`) in two disposable writable lanes:

- the unrepaired entrypoint creates `__pycache__` and returns the old generic
  `ContractError`;
- the repaired entrypoint checks a fresh copy without adding or changing any
  package member and returns `AUTHORIZATION_SCHEMA_MISMATCH`.

The second lane uses only `{}` as a deliberately invalid, non-authorizing
fixture. It must report claim/consume/board/serial/Flash/network flags as false.
Neither lane calls `execute`.

## Next physical identity

This repair creates no D2-12 request, execution package or authorization.
Any later physical attempt must use a new D2-12 identity and independently bind
the repair into a new execution-bound wrapper and inner launcher together with
the private outer runner, exact source HEAD, exact board identity and
then-current artifacts. This source-only wrapper is not a physical entrypoint.

All D2-10 and earlier identities remain permanently non-replayable. The failed
D2-11 private package and authorization also remain non-reusable.
