# N3-W T1 Core Stack semantic version and release-upgrade architecture

Date: 2026-11-05

## 1. Gate

```text
TASK=N3W_T1_CORE_STACK_SEMANTIC_VERSION_AND_RELEASE_UPGRADE_MODEL
STATE=ARCHITECTURE_DESIGN

BASE_MAIN=5cabdcb50656851f9912685c2f7044cdba3eb774
UPSTREAM_HA_PREPARATION_HEAD=2631729ec77045695424ce6bacb1fd0fa6685437

DESIGN_ONLY=true
T1_CORE_STACK_1_1_0_BUILD=false
LIVE_T1_MUTATION=false
SERVICE_RESTART=false
IMAGE_LOAD=false
UPDATER_APPLY=false
UPDATER_ROLLBACK=false
CREDENTIAL_MUTATION=false
BOARD_ACCESS=false
MERGE=false
```

This gate defines the version/archive/update architecture only. It does not perform a 1.0.0 ->
1.1.0 field upgrade and does not create a final 1.1.0 release.

## 2. Product definition

T1_Core_Stack is the production software stack composed of:

- greenhouse-manager;
- Home Assistant;
- Mosquitto Broker;
- the runtime contract needed to run those three components together.

Each product release has two identities:

```text
stack_version = human/product semantic version
release_id    = exact content-addressed release identity
```

A semantic version is not an exact artifact identity. A release ID is not a user-facing product
version. Both are required.

## 3. Version policy

The product version format is strict:

```text
MAJOR.MINOR.PATCH
```

Policy:

- PATCH: bounded compatible repair with no intended product capability expansion;
- MINOR: compatible component update, feature addition, or compatible runtime-contract change;
- MAJOR: incompatible product contract, persistent-state migration model, deployment architecture,
  or another change that cannot be accepted as a normal compatible successor.

A Stack version changes when the accepted product combination changes. The three components do not
all need to change in the same release.

## 4. Independent immutable release archive

Every published T1_Core_Stack version is a separate immutable object.

Freeze:

```text
RELEASE_STORAGE_MODEL=APPEND_ONLY
OLD_RELEASE_MUTATION_FORBIDDEN=true
SAME_STACK_VERSION_REPUBLISH_FORBIDDEN=true
NEW_RELEASE_OVERWRITES_OLD_RELEASE=false
```

Repository layout:

```text
infra/n3w-t1/releases/
  1.0.0/
    release.json
  1.1.0/
    release.json
  1.2.0/
    release.json
```

A future 1.1.0 release is added beside 1.0.0. It must never replace, edit, or delete 1.0.0.

The current accepted 1.0.0 authority is stored at:

`infra/n3w-t1/releases/1.0.0/release.json`

The archive contract is documented in:

`infra/n3w-t1/releases/README.md`

The versioned archive is not a live deployment directory.

## 5. Current accepted release

The already accepted live stack is assigned:

```text
T1_CORE_STACK_VERSION=1.0.0
T1_CORE_STACK_RELEASE_ID=5debfbe23356d67ea5ff095f7ffc3e5443d771ddb4241589fa496b901ff2b7d9
```

This assignment changes no T1 runtime bytes.

Current composition:

```text
Manager        local/greenhouse-manager:fresh-5b32e1ae8210
Home Assistant local/n3w-homeassistant:2026.10.0-0c73235a
Broker         local/n3w-mosquitto:2.1.2-3184566d

Manager binding        dynamic
Home Assistant binding legacy_static
Broker binding         legacy_static
```

The release binds exact image identities using the strongest existing repository authority.

## 6. Release contract

The pure source contract is implemented in:

`tools/n3w_t1_core_stack_release.py`

Schema:

```text
gh.n3w-t1-core-stack-release/1
```

A release binds:

- `stack_version`;
- exact `release_id`;
- product source head;
- all three component image references;
- all three component immutable identities;
- linux/arm64 platform;
- live Compose path;
- per-component image-binding mode;
- Manager/HA shared service owner;
- Broker independent service owner.

The `release_id` is derived from canonical release material. Any exact product-contract change
therefore produces a different release identity.

This module is declarative/pure. It is not a privileged field-upgrade executor.

## 7. One execution owner: T1_Core_Updater

There is no second Stack deployment engine and no whole-stack overwrite installer.

Freeze:

```text
FIELD_UPGRADE_EXECUTOR=T1_Core_Updater
STACK_RELEASE_ROLE=DECLARATIVE_TARGET_AUTHORITY
WHOLE_STACK_OVERWRITE_DEPLOYMENT=false
SECOND_PRIVILEGED_UPGRADE_ENGINE=false
```

The updater is extended to consume:

1. current accepted Stack release;
2. requested target Stack release;
3. exact target component artifact(s);
4. component compatibility evidence;
5. one-shot authorization.

The updater computes the release delta and mutates only the required portions.

Example future relationship:

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

Expected updater change set:

```text
Manager        KEEP
Home Assistant UPGRADE
Broker         KEEP
Runtime        UPDATE only if required by the target release
```

The release model tells the updater what exact product state is requested. The updater remains
responsible for how that state is safely reached.

## 8. No "copy 1.1.0 over 1.0.0"

A T1_Core_Stack upgrade is not:

```text
copy complete 1.1.0 tree over running 1.0.0
```

It is:

```text
read current 1.0.0 authority
-> read target 1.1.0 authority
-> compute exact delta
-> T1_Core_Updater verifies predecessor
-> T1_Core_Updater applies only required mutations
-> whole-stack health/identity acceptance
-> commit current-version authority to 1.1.0
```

The old 1.0.0 release remains intact in the repository and remains available as rollback authority.

## 9. Current-version authority is separate from release archive

The version archive and the current pointer/state are different things.

```text
release archive
= immutable history of all supported product releases

current authority
= which exact release the running T1 has successfully accepted
```

After a successful field upgrade, only the current authority advances from 1.0.0 to 1.1.0.
The 1.0.0 release does not change.

If the updater fails before final acceptance, current authority remains 1.0.0 or enters an explicit
recoverable in-progress state. It must never silently claim 1.1.0 merely because one component was
already changed.

## 10. Updater-owned Stack transaction

The product may need multiple lower-level mutations to reach a target release. Those mutations are
owned by one updater transaction context.

The Stack release itself does not execute anything.

Future updater transaction model:

```text
CURRENT_RELEASE=1.0.0
TARGET_RELEASE=1.1.0

T1_Core_Updater:
  verify current release
  verify target release
  verify exact artifacts
  create bounded change set
  apply required runtime-contract migration
  apply required component update(s)
  restore/verify peer services
  verify complete target release
  commit current authority
```

Temporary intermediate runtime states may exist only inside this explicit updater transaction.
They are not published as standalone Stack releases.

## 11. Rollback model

Rollback also belongs to T1_Core_Updater.

Freeze:

```text
ROLLBACK_EXECUTOR=T1_Core_Updater
ROLLBACK_AUTHORITY=PREDECESSOR_RELEASE
ROLLBACK_BY_WHOLE_STACK_OVERWRITE=false
```

For a failed 1.0.0 -> 1.1.0 attempt, the preserved 1.0.0 release provides the exact desired
predecessor state.

The updater computes the inverse delta and restores only what changed, then verifies that the full
running product matches exact 1.0.0 again.

Example:

```text
HA image       2026.10.4 -> 2026.10.0
HA binding     dynamic   -> legacy_static
Manager        verify unchanged
Broker         verify unchanged
```

A rollback is PASS only when the complete predecessor release is restored, not merely when the
changed container starts.

## 12. Relationship to current Home Assistant work

The current development program remains a T1_Core_Updater validation program.

The HA 2026.10.0 -> 2026.10.4 work is useful as a future first example of a Stack-version delta, but
this architecture gate does not turn it into a real 1.1.0 deployment.

The previously prepared HA binding read-only inspector may still be used to prove that a future
updater-controlled runtime-contract migration is safe.

However:

```text
HA_TEMPLATE_READONLY_PREFLIGHT_ALLOWED=true
HA_TEMPLATE_LIVE_MUTATION_IN_THIS_GATE=false
STACK_1_1_0_BUILD_IN_THIS_GATE=false
STACK_1_1_0_DEPLOY_IN_THIS_GATE=false
```

If/when the project later publishes T1_Core_Stack 1.1.0, the final exact release will be created as
a new immutable directory beside 1.0.0.

## 13. Updater capabilities required by this architecture

The architecture establishes requirements for T1_Core_Updater rather than a new executor.

Future updater source must be able to:

- load and validate current/target Stack release manifests;
- reject target version/release identity ambiguity;
- compute per-component KEEP/UPGRADE plus runtime-contract delta;
- prove exact predecessor before first mutation;
- use exact component artifacts;
- sequence runtime-contract and component mutations safely;
- keep unchanged peer components identity-stable;
- maintain one updater-owned transaction/recovery record;
- accept only after complete target Stack verification;
- rollback against the preserved predecessor release;
- update current Stack authority only after acceptance;
- never delete predecessor release authority as part of normal upgrade.

These are the design outputs that should guide the continuing updater work.

## 14. Current boundary

```text
ARCHITECTURE_MODEL_DEFINED=true
CURRENT_RELEASE_1_0_0_PRESERVED=true
RELEASE_ARCHIVE_APPEND_ONLY=true

STACK_1_1_0_VERSION_EXAMPLE_ONLY=true
STACK_1_1_0_RELEASE_READY=false
STACK_1_1_0_BUILD=false
STACK_1_1_0_DEPLOY=false

FIELD_UPGRADE_EXECUTOR=T1_Core_Updater
LIVE_T1_MUTATION=false

NEXT_WORKSTREAM=T1_CORE_UPDATER_PRODUCT_GRADE_HOMEASSISTANT_VALIDATION
MERGE=false
```

The next engineering work stays on T1_Core_Updater. The Stack release architecture remains the
version/target/rollback contract that the updater consumes.

## 15. T1_Core_Updater has its own independent version

T1_Core_Updater is an independently versioned software product. Its version MUST NOT reuse or
mirror the T1_Core_Stack version.

Freeze:

```text
UPDATER_VERSION_AXIS=INDEPENDENT
STACK_VERSION_AXIS=INDEPENDENT
UPDATER_VERSION_EQ_STACK_VERSION_REQUIRED=false
CURRENT_UPDATER_DEVELOPMENT_LINE=0.x
CURRENT_UPDATER_DEVELOPMENT_VERSION=0.1.0
CURRENT_UPDATER_PRODUCTION_1_0_RELEASED=false
```

Examples that are all valid:

```text
T1_Core_Stack 1.0.0 + T1_Core_Updater 0.1.0
T1_Core_Stack 1.0.0 + T1_Core_Updater 0.2.0
T1_Core_Stack 1.1.0 + T1_Core_Updater 1.0.0
```

The updater reaches `1.0.0` only after the production-grade Manager, Home Assistant and Broker
upgrade paths, rollback, interruption/recovery behavior and Stack-release consumption are all
accepted. The current `0.1.0` value identifies the development line; this gate does not publish a
production updater release artifact.

Updater semantic-version policy:

- PATCH: bounded compatible bug fix with no intended contract/capability expansion;
- MINOR: compatible new upgrade capability, validation or recovery capability;
- MAJOR: incompatible updater behavior/contract that cannot safely remain on the same major line;
- versions below 1.0.0 remain development/pre-production.

## 16. Four different updater identities

Updater product version, source identity, binary identity and schema identity answer different
questions and MUST remain separate.

```text
updater_version
= human/product software version

control_plane_head
= exact Git source authority

updater_pyz_sha256
= exact executable-byte identity

schema versions
= target / transaction / status / inspect / plan data-contract versions
```

Therefore none of the following may be used as a substitute for `updater_version`:

```text
gh.n3w-t1-core-updater-target/2
gh.n3w-t1-core-updater-transaction/2
<git commit>
<pyz sha256>
```

Conversely, a human-readable updater version is never sufficient for execution authority. A real
execution must continue to bind exact source/package bytes.

Future updater execution evidence should carry all applicable identities:

```text
updater_version
control_plane_head
updater_pyz_sha256
target_schema
transaction_schema
```

Historical V2 transactions and closed Manager U1 evidence remain immutable. They are not rewritten
merely to backfill the new product-version field. Introducing the field into runtime transaction
documents later requires an explicit backward-compatible envelope or a reviewed successor schema.

## 17. Independent immutable updater release archive

Formal updater releases use their own append-only archive and do not overwrite older updater
versions.

Repository contract:

`infra/n3w-t1/updater-releases/README.md`

Future layout:

```text
infra/n3w-t1/updater-releases/
  0.1.0/
    manifest.json
  0.2.0/
    manifest.json
  1.0.0/
    manifest.json
```

The exact executable may remain a GitHub artifact rather than being committed as a binary to the
repository. The release manifest binds the artifact identity instead.

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

Freeze:

```text
UPDATER_RELEASE_STORAGE_MODEL=APPEND_ONLY
OLD_UPDATER_RELEASE_MUTATION_FORBIDDEN=true
SAME_UPDATER_VERSION_REPUBLISH_FORBIDDEN=true
LATEST_MUTABLE_UPDATER_BINARY_AUTHORITY=false
```

Existing historical updater artifacts keep their current SHA/artifact/commit provenance. This gate
does not retroactively manufacture semantic releases for all historical pyz files.

## 18. Stack-to-updater compatibility

A Stack release and an Updater release are related by compatibility requirements, not by matching
version numbers.

Preferred model:

```text
required_updater_capabilities
= primary compatibility authority

minimum_updater_version
= optional human/operator guard
```

Example future target requirements:

```text
STACK_RELEASE_V1
HA_IMAGE_UPGRADE_V1
HA_RUNTIME_BINDING_MIGRATION_V1
STACK_ROLLBACK_V1
```

Capability requirements are preferred over relying only on a numeric comparison such as
`updater >= 1.2.0`, because they state exactly which execution abilities the target release needs.

Updater compatibility metadata is deployment/execution metadata, not runtime product identity.
Therefore it must not force unrelated changes to the immutable component/runtime identity of an
already published Stack release.

## 19. Updated boundary

```text
ARCHITECTURE_MODEL_DEFINED=true

STACK_RELEASE_VERSIONING=DEFINED
STACK_RELEASE_ARCHIVE=APPEND_ONLY
UPDATER_VERSIONING=DEFINED
UPDATER_RELEASE_ARCHIVE=APPEND_ONLY

CURRENT_UPDATER_DEVELOPMENT_VERSION=0.1.0
CURRENT_UPDATER_PRODUCTION_1_0_RELEASED=false

UPDATER_PACKAGE_REBUILD_IN_THIS_GATE=false
UPDATER_RUNTIME_SCHEMA_MIGRATION_IN_THIS_GATE=false
HISTORICAL_TRANSACTION_REWRITE=false
LIVE_T1_MUTATION=false

NEXT_WORKSTREAM=T1_CORE_UPDATER_PRODUCT_GRADE_HOMEASSISTANT_VALIDATION
MERGE=false
```

The semantic version makes the updater understandable as a product; exact source head, pyz SHA256
and artifact digest remain the execution-grade identity.