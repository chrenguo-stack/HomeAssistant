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

Rules:

- never store credentials, private host paths, private addresses, authorization
  strings, or raw production evidence in this directory;
- update the source baseline only after the corresponding repository revision
  and evidence have been accepted;
- a completed lab gate does not imply `FIELD_ACCEPTED` for H3 or N2;
- `ready_for_live_apply` and `ready_for_anonymous_closure` remain false until a
  separate production stage explicitly changes their evidence-backed state;
- this state file is descriptive and cannot authorize or execute mutations.
