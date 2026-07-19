# H3 Manager legacy bootstrap preflight v1

## Purpose

This gate is used only when the H3 field preflight finds no reusable
`greenhouse-manager-legacy-review-bridge-*` directory. It inventories the private
static evidence required by the existing legacy review bridge and reports whether
exactly one transaction/rollback pair can be selected safely.

It does not inspect Docker, MQTT, `/proc`, Home Assistant, or any production
endpoint. It does not create a bridge, record an operator decision, read credential
material, generate or claim authorization, or modify private evidence.

## Static validation

For every candidate pair, the command reuses the repository-owned postrollback
static validator and requires:

- private non-symlink transaction and execution directories;
- private `journal.json`, `fresh-rollback-manifest.json`, and rollback archive;
- the exact manager transaction and fresh rollback schemas;
- `preserve_anonymous=true` and `anonymous_closure_enabled=false`;
- a manager-only rollback;
- an archive SHA-256 bound by the transaction journal;
- byte-valid archive contents whose embedded manifest equals the external manifest;
- absolute, non-symlink Compose and manager-secret paths, with the password target
  contained by the secret root.

The report contains only content digests and a pair fingerprint. It never contains
private paths or document values.

## CLI

```bash
ghctl m2 legacy-bootstrap-preflight \
  --repository REPOSITORY \
  --search-root PRIVATE_EVIDENCE_ROOT \
  --require-baseline-ancestor \
  --require-clean \
  --pretty
```

The scan does not follow directory symlinks, visits at most 4096 directories, and
accepts at most 32 transaction and 32 execution candidate directories.

## Result semantics

Exactly one valid pair reports:

```text
ready_for_read_only_legacy_rollback_audit_scope_review=true
next_action=REVIEW_READ_ONLY_LEGACY_ROLLBACK_AUDIT_SCOPE
```

This result is not permission to inspect live services. Before the next gate, the
operator must review the exact read-only Docker/MQTT scope and separately decide
whether that environment is non-production and in scope.

Zero or multiple pairs remain blocked and require evidence location or ambiguity
resolution. Every result keeps production probing, production execution,
authorization, credential access, service mutation, node credential delivery, and
anonymous closure disabled.
