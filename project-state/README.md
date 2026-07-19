# Project state

`current-baseline.json` is the single public, secret-free, machine-readable
handoff for the active H3/N2 development line. It records only approved source
bindings, completed gates, blocking gates, the final private-board matrix
summary, and safety flags.

Use the fixed read-only entry point instead of copying fields between temporary
scripts:

```bash
ghctl m2 status --repository . --pretty
```

For a clean exact-baseline check:

```bash
ghctl m2 status --repository . --require-baseline-ancestor --require-clean --pretty
```

Audit the complete public H3 implementation chain before any private field
preflight:

```bash
ghctl m2 readiness --repository . --require-baseline-ancestor --require-clean --pretty
```

The readiness command validates 14 source/test/protocol capability bindings and
their content fingerprints. A successful report means the offline implementation
chain is complete; it deliberately reports `h3_field_accepted=false`,
`ready_for_live_apply=false`, and `live_action_authorized=false`.

After readiness passes, inventory only the local private legacy-review bridge
evidence needed by the existing fresh-chain discover-only gate:

```bash
ghctl m2 field-preflight \
  --repository . \
  --search-root PRIVATE_EVIDENCE_ROOT \
  --require-baseline-ancestor \
  --require-clean \
  --pretty
```

Add `--expected-retained-topic` only from an operator-controlled local variable.
The value is hashed for comparison and is never included in the report.

If no bridge exists, inventory legacy transaction/rollback static evidence before
considering any live read-only audit:

```bash
ghctl m2 legacy-bootstrap-preflight \
  --repository . \
  --search-root PRIVATE_EVIDENCE_ROOT \
  --require-baseline-ancestor \
  --require-clean \
  --pretty
```

This command reports only content fingerprints. It does not inspect Docker, MQTT,
`/proc`, credentials, or production endpoints.

Rules:

- never store credentials, private host paths, private addresses, authorization
  strings, or raw production evidence in this directory;
- update the source baseline only after the corresponding repository revision
  and evidence have been accepted;
- a completed lab gate does not imply `FIELD_ACCEPTED` for H3 or N2;
- `ready_for_live_apply` and `ready_for_anonymous_closure` remain false until a
  separate production stage explicitly changes their evidence-backed state;
- this state file is descriptive and cannot authorize or execute mutations.
- `h3-readiness.json` contains only public repository paths and source markers;
  it must never point to private evidence or credential material.
