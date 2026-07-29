# H3/N2 Stage2D-9R G3R D2-12 Python-bytecode-repaired execution binding

Decision:
`D1-H3N2-STAGE2D9R-G3R-D2-12-PYTHON-BYTECODE-REPAIRED-SUCCESSOR-EXECUTION-BINDING-20260729-01`.

## Scope

This add-only successor is stacked on Draft PR #209 at exact HEAD
`bd339afb29aa1c12e2db0c8766f80e776d1435d7`. It creates a new D2-12
unauthorized request, execution closure and execution package. It creates no
physical authorization and performs no board operation.

The successor composes:

- the unchanged firmware payload, terminalization guard and paced transport
  already reviewed in PR #208;
- the bytecode guard and controlled leaf-code repair reviewed in PR #209;
- a new D2-12 launcher, wrapper, contract, closure, package and request identity.

No D2-11 request, private package, authorization, closure or package identity is
reused.

## D2-11 disposition

D2-11 stopped during its first authorization contract check:

```text
status=PRECLAIM_CONTRACT_FAILED
authorization_claimed=false
authorization_consumed=false
board_operation=false
usb_enumeration=false
serial_operation=false
esptool_operation=false
flash_operation=false
network_operation=false
```

The old D2-11 request, public execution identity, private package and
authorization remain non-retryable and non-reusable. The last operation that
actually touched the board remains D2-10, whose locked-recovery outcome stays
`UNKNOWN`.

## Python launch contract

The D2-12 inner launcher must set and export
`PYTHONDONTWRITEBYTECODE=1` before selecting or invoking Python. The wrapper
must confirm `sys.dont_write_bytecode` before contract-check or execute.

A later private outer runner must independently set and export the same
variable before its first Python process. The future authorization must bind
the exact private runner and declare its bytecode guard. This public source
gate does not create that runner or authorization.

The D2-12 wrapper binds PR #209's repaired error adapter so controlled contract
leaves remain stable. Uncontrolled exception text and private host paths remain
excluded.

## Package and request contract

The public packager verifies exact PR #208 and PR #209 Artifact digests,
root manifests and review bindings. It then:

1. validates the PR #208 execution package;
2. copies its non-control files without any old launcher;
3. copies the exact PR #209 repair contract and wrapper;
4. adds the D2-12 launcher, wrapper and contract;
5. creates a new policy-v4 execution closure and package binding;
6. creates request D2-12 with `authorized=false`.

The new package and closure digests must differ from D2-11. The immutable and
locked-recovery payload TAR bytes remain unchanged.

## Live boundary

Source inspection, unit tests, shell integration, packaging and
`contract-check` are host-only. They do not enumerate USB, open serial, invoke
esptool, modify Flash/NVS, start a Broker, send PREPARE/VERIFY, run recovery,
claim or consume authorization.

A later independent decision may create an exact private package and one-shot
D2-12 authorization. This gate does not authorize that action.
