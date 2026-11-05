# T1 Core Stack release archive

This directory stores immutable product-release manifests for T1_Core_Stack.

## Rules

Each published Stack version has its own directory:

```text
infra/n3w-t1/releases/
  1.0.0/
    release.json
  1.1.0/
    release.json
  1.2.0/
    release.json
```

A newer version MUST NOT overwrite, replace, or edit an older published release.

Freeze:

```text
RELEASE_STORAGE_MODEL=APPEND_ONLY
OLD_RELEASE_MUTATION_FORBIDDEN=true
SAME_STACK_VERSION_REPUBLISH_FORBIDDEN=true
ROLLBACK_REQUIRES_PREDECESSOR_RELEASE=true
```

The versioned release archive is not the live T1 deployment directory and is not copied wholesale
onto a running T1.

A release manifest is declarative authority describing an exact product version. It binds:

- Stack semantic version;
- exact content-derived release ID;
- Manager image identity;
- Home Assistant image identity;
- Broker image identity;
- runtime contract.

The live current-version authority is a pointer/state record separate from this archive. Advancing
that pointer does not delete or modify predecessor releases.

## Upgrade execution ownership

`T1_Core_Updater` is the only planned privileged execution engine for field upgrades.

The updater consumes:

1. the currently accepted Stack release;
2. the requested target Stack release;
3. exact component artifacts and component targets;
4. an explicit one-shot authorization.

It computes the delta and changes only what differs. It MUST NOT perform a whole-stack overwrite
deployment merely because a newer Stack release exists.

Example:

```text
1.0.0
  Manager A
  HA 2026.10.0
  Broker 2.1.2

1.1.0
  Manager A
  HA 2026.10.4
  Broker 2.1.2
```

Expected updater plan:

```text
Manager        KEEP
Home Assistant UPGRADE
Broker         KEEP
Runtime        UPDATE only if the target release requires it
```

Rollback uses the preserved predecessor release as exact authority and is also executed by
`T1_Core_Updater`.

## Current development boundary

The semantic-release work defines storage and execution contracts only.

No T1_Core_Stack 1.1.0 release is produced by this gate, and no live T1 is upgraded by this gate.
