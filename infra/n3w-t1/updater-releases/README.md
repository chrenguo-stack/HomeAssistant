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

## HA recovery installation candidate

The HA target-binding workflow builds the recovery installer from the exact checked-out
commit. Its source job publishes the candidate artifact and reports the SHA-256 of
`manifest.json`. The artifact binds the isolated recovery executable, boot service,
retry service and timer, application start condition, host IPC units and the staged
Compose candidate. A candidate is a source-level
installation artifact. Formal updater releases still follow the archive contract above.

The authorized host installer entry is `ha-recovery.pyz install --manifest-sha256 <digest>`
under the host Python interpreter. Obtain the digest from the trusted workflow record.
The installer enables persistence and reloads systemd definitions without starting units.
The first quiesce requires the boot service to be enabled and the retry timer to be
enabled and active. Initial installation and byte-identical retries use the same artifact.

The package builder derives `ha-ota-candidate.compose.yml` from the exact fresh
stack template. The installer stages it under `/opt/n3w-t1-core-updater`.
The candidate enables OTA in Manager and binds the host's `/run/n3w/t1-ota`
directory read-only. Mounting the directory lets Manager see socket recreation
and atomic replacement of the approved manifest. The mount requires the host
directory to exist. The candidate also requires
`GH_N3W_T1_OTA_INSTALLED_VERSION` to be supplied from the observed predecessor.
During an OTA transaction, the host status is the version authority for Manager.
Trial startup and acceptance keep the predecessor version visible until commit.
A rollback keeps the predecessor version, and a committed transaction reports
the accepted target even if its approved manifest is later removed.
The verified recovery bundle exposes `check-candidate-activation --manifest-sha256
<digest>`. It checks the installed bundle, the idle transaction store, the
running predecessor, the armed recovery timer and the Manager socket. It
compares rendered Compose using the host environment file and accepts only the
Manager OTA settings and the read-only OTA directory mount. A successful check
is evidence for a separate activation. The recovery installer stages the file.

The recovery bundle exposes the root-only `materialize-candidate` command for
an externally approved engineering candidate. It takes absolute paths via
`--approved-manifest` and `--target-archive`, an independently supplied
`--approved-manifest-sha256`, and `--expires-at-unix`. The host checks the
approved bytes, the running predecessor and the archive size, digest, tag
and ARM64 image format. It retains the incoming file and stages a mode-0600
copy in the private updater state directory, so allow disk space for that
copy. The result includes the verified `target_source` for a later preparation
approval. A retry reuses the exact staged copy.

The host writes the private release pin and then publishes the exact
approved manifest to Manager. Both operations share the transaction lock
used by new OTA requests. After an interruption, a mismatched pin and
manifest block new requests until the command is retried. This operation
stages engineering inputs only. Signed distribution and separate transaction
approvals apply at their respective stages.

### Signed HA-only distribution check

The recovery bundle exposes `check-signed-release --trust-policy ABSOLUTE_PATH`.
Provision the local policy independently of the release server. It has schema
`gh.n3w-t1-ota-release-trust/1` and fields `base_url`, `minimum_index_sequence`,
and `public_key_der_base64` (an Ed25519 public key in SubjectPublicKeyInfo DER).
The updater uses normal HTTPS certificate verification, one configured origin
and relative paths, with redirects and compressed metadata responses rejected.

`index.json` and its referenced release document each have a detached raw
64-byte signature in a sibling `.sig` file. Sign the exact file bytes.
The index schema `gh.n3w-t1-ota-release-index/1` carries `sequence`,
`expires_at_unix`, `release_id`, `release_path` and `release_sha256`. The
distribution schema `gh.n3w-t1-ota-ha-release-distribution/1` carries
`expires_at_unix`, `predecessor`, `target`, `minimum_updater_version`,
`required_updater_capabilities`, `ha_candidate` and `archive_path`.
The predecessor and target use the existing Stack release schema. For this
HA-only contract, Manager, Broker and the runtime contract must have identical
signed declarations. The target HA Stack identity uses the archive SHA-256.
The embedded HA candidate retains the Manager approval-manifest schema and
binds the same Stack release ID, HA predecessor, target image and archive.

This command checks signed metadata and reports the exact identities it verified.
The local sequence floor comes from policy. Product consumption still needs
durable replay protection, archive download, live predecessor verification and
binding to the private candidate materialization step. Production key
provisioning and release publication follow separate approvals.

For the controlled candidate, the root-owned recovery entry also exposes
`--issue-prepare-authority PRIVATE_REQUEST` and
`--issue-install-authority PRIVATE_REQUEST`. The two inputs are separate absolute
paths to host-owned mode-0600 files. Each input names the observed transaction
with `transaction_id_sha256` and supplies `expires_at_unix`. Preparation also
requires `usb_filesystem_uuid`, `target_source`, `max_predecessor_bytes` and
`usb_reserve_bytes`. Installation requires the approved `binding_sha256`,
one-use `authorization_id` and `space` budgets. The host revalidates the pinned
release and derives the launch identity. The issuer saves only the selected
private grant. The existing worker separately processes the durable request.
Keep candidate requests and grants out of the exported Manager directory.
