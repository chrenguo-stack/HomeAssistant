# T1 Core Updater release archive contract

This directory defines the immutable release-archive model for T1_Core_Updater.

The updater is independently versioned from T1_Core_Stack.

```text
UPDATER_VERSION_AXIS=INDEPENDENT
STACK_VERSION_AXIS=INDEPENDENT
```

## Version policy

Updater versions use strict semantic versioning:

```text
MAJOR.MINOR.PATCH
```

The current development line is:

```text
CURRENT_UPDATER_DEVELOPMENT_VERSION=0.1.0
CURRENT_UPDATER_PRODUCTION_1_0_RELEASED=false
```

The project does not declare production `1.0.0` until Manager, Home Assistant and Broker
upgrade paths, rollback, interruption/recovery behavior, and Stack-release consumption have all
closed product-grade acceptance.

## Immutable archive

Formal releases are append-only:

```text
infra/n3w-t1/updater-releases/
  0.1.0/
    manifest.json
  0.2.0/
    manifest.json
  1.0.0/
    manifest.json
```

Freeze:

```text
UPDATER_RELEASE_STORAGE_MODEL=APPEND_ONLY
OLD_UPDATER_RELEASE_MUTATION_FORBIDDEN=true
SAME_UPDATER_VERSION_REPUBLISH_FORBIDDEN=true
LATEST_MUTABLE_UPDATER_BINARY_AUTHORITY=false
```

A newer updater release MUST NOT overwrite, replace, edit, or delete an older formal release.

The exact pyz binary does not need to be committed to Git. A release manifest may bind the
corresponding GitHub artifact and exact executable digest.

## Required release identity

A formal updater release manifest should bind at least:

```text
updater_version
source_head
updater_pyz_sha256
artifact_id
artifact_digest_sha256
artifact_name
supported_target_schemas
supported_transaction_schemas
supported_stack_release_schemas
capabilities
release_state
```

These identities are intentionally distinct:

```text
updater_version      = product/human version
source_head          = exact source authority
updater_pyz_sha256   = exact executable-byte identity
schema versions      = data-contract versions
```

None substitutes for another.

## Historical artifacts

Existing historical updater packages and closed Manager U1 evidence keep their current provenance:
artifact ID/digest, source head and pyz SHA256.

This architecture gate does not retroactively mint semantic versions for every historical updater
artifact and does not rewrite historical transaction records.

## Stack compatibility

T1_Core_Stack releases do not share the updater version number.

Compatibility is expressed primarily through required capabilities, for example:

```text
STACK_RELEASE_V1
HA_IMAGE_UPGRADE_V1
HA_RUNTIME_BINDING_MIGRATION_V1
STACK_ROLLBACK_V1
```

A minimum updater version may additionally be recorded for operator-facing checks, but capability
requirements remain the preferred compatibility authority.

## Current boundary

This directory currently defines the archive contract only.

No production updater release manifest or new pyz package is created by the semantic Stack
architecture gate.
