# KF-098 — T1 live Manager cutover execution package

Status: `PREPARATION_ONLY`

## Gate

```text
N3W_KF098_PAIRING_ADVERTISED_HOST_DYNAMIC_T1_LIVE_CUTOVER_PREPARATION_20260928_01
```

This package prepares the exact live cutover for KF-098. Preparation itself
does not access or mutate T1.

## Proven live root cause

The live preflight proved:

```text
GH_N3W_PAIRING_ADVERTISED_HOST=durable predecessor IPv4 literal
manager.env pairing value != current eth0 IPv4
running Manager Config.Env == manager.env pairing value
UDP/47111 listener=1
TCP/47112 listener=1
Manager network_mode=host
Broker running=true
Broker restart_count=0
R5 guard/lifecycle/firewall anchors=PASS
```

Therefore the live defect remains the stale Manager pairing advertised-host
authority. It is not a PR #474 RF defect, Broker failure, R5 failure, or missing
pairing listener.

## Exact new Manager authority

```text
SOURCE_SHA=575ce642e372961e21de14a36eba5877082de3cf
SOURCE_TREE=7f1641827b75668aa220832b7663bf81d98633ba
ARTIFACT_RUN_ID=36329597775
ARTIFACT_ID=10935052471
ARTIFACT_DIGEST=sha256:41dde2129aa64623746257814e7568f8a8d6948ad299766d7a1b1ea7f3bdf9a5
IMAGE_ID=sha256:49c9fcc0a17d47678b0667c48a06f9a9475609a757e510ca148983b53ed537e3
IMAGE_TAR_SHA256=6392b8c9bb87d95404346583d6f44967bd4e20fcc092be393c45f75a4ca7a5b2
IMAGE_ARCHITECTURE=arm64
ENTRYPOINT=greenhouse-manager
RUNTIME_UID=999
RUNTIME_GID=999
```

The historical first build artifact is not deployment authority.

## Live authority frozen by preflight

```text
COMPOSE=/opt/greenhouse-fc4-95c42fa5/runtime/docker-compose.yml
COMPOSE_SHA256=2c9c28c582a9c01e18a2e54a4c0b2bbddc75192ed377a701ed2f661f15cd5a8a

MANAGER_ENV=/opt/greenhouse-fc4-95c42fa5/runtime/manager/manager.env
MANAGER_ENV_SHA256=f454c6e886ee286192a3c3683a87c33d98e79428de0a6d0c9d2a6e0a19a9d6a6
MANAGER_ENV_EXCLUDING_PAIRING_SHA256=568c4302f2986e5f52b030ccd9cd96862213bfdfa65f31f5da54a20296bce89e

OLD_MANAGER_IMAGE_ID=sha256:271cd87c88c041f0ef7fa55f6c223615edf42388b8e05a7445862e2b700cdfb5
MANAGER_NETWORK_MODE=host
MANAGER_MOUNT_COUNT=6
MANAGER_MOUNT_BINDING_SHA256=6cb94ab6b78e0a68df458e5dc4d9240cc91c225a1b44bc7eba9454325821bffc
MANAGER_RESTART_COUNT=1
BROKER_RESTART_COUNT=0
```

The current PR #480 activation unit blob is
`5033b7475f4fafb1409ed277425197a93fd0d5a5`. The older PR #478 blob must not
be used as the live preflight oracle.

## Cross-image-store exact image identity

The exact artifact carries two immutable OCI identities for the same image:

```text
IMAGE_CONFIG_DIGEST=sha256:49c9fcc0a17d47678b0667c48a06f9a9475609a757e510ca148983b53ed537e3
IMAGE_MANIFEST_DIGEST=sha256:b806e7c8b97cc757965161a989f954df09427aa7d2700a6503e56e49cc8f9e4f
ROOTFS_LAYERS_SHA256=97dd9fb029f1678a4589148d1874c95cd1d26439efa89ee833d5d734b70d42d6
```

The Docker-tar `manifest.json` points its Config field at the config digest.
The OCI `index.json` points at the manifest digest, and that manifest points
back to the exact config digest.

Docker's classic image store may expose the config digest as image `.Id`.
Docker with the containerd image store may expose the OCI manifest digest as
image `.Id`. Therefore the live executor must not assume one representation
is universal.

After `docker load`, the executor inspects the exact tag and accepts only one
of the two artifact-owned runtime IDs above. It then requires ARM64/Linux,
the frozen entrypoint/user contract and the exact RootFS-layer fingerprint.
Shadow and post-cutover container validation accept only the two
artifact-owned identities above. This avoids assuming that image-inspect and
container-inspect must expose the same identity representation on every Docker
image store.

The Docker API `Config` object is not used as a cross-image-store byte
oracle; different stores may synthesize that API object differently even when
the underlying OCI config and RootFS are the same.

## Interrupted pretransaction resume

A failed attempt before `manager.env` mutation may leave only the private
rollback snapshot. That state is resumable only when all of the following are
true:

- the rollback directory is root-owned mode 0700;
- it contains exactly `manager.env.before` and `manager-prestate.json`;
- the manager.env backup has the exact frozen prestate SHA-256;
- no live, rollback or shadow overlay exists;
- a fresh base preflight produces exactly the same private prestate.

The stage classifier may preserve this exact pretransaction snapshot while
refreshing the execution package. Any other rollback/overlay shape fails
closed. No manual deletion is required or permitted.

## Cutover design

The current live Compose file is not edited.

The executor creates a private overlay that changes only the Manager image
selection and explicitly keeps the container name:

```yaml
services:
  manager:
    image: local/greenhouse-manager:kf098-575ce642
    container_name: greenhouse-manager
    pull_policy: never
```

All mounts, `network_mode=host`, env-file binding, database/state paths and
other service configuration continue to come from the frozen live Compose
authority.

The only durable environment mutation is:

```text
GH_N3W_PAIRING_ADVERTISED_HOST:
prestate = exact stale IPv4 hash already frozen
poststate = auto
```

The executor verifies the hash of the environment file with this one key
removed before and after mutation. Any other line drift stops the transaction.

`service-identities.env` contains the same stale value but is not referenced
by the current live Manager Compose service. It is read-only authority in this
gate and is intentionally not mutated. That avoids expanding this cutover into
a second deployment-authority migration.

## Mac bootstrap authority

The live execution entrypoint must not assume that the current Terminal
directory is a Git worktree and must not depend on an existing local clone.

`bootstrap_runner.py` is the only supported Mac entrypoint for this gate. It
requires an exact 40-character package commit SHA, verifies that commit through
GitHub, downloads the exact execution-package files from that commit, records
their SHA-256 values in a private local authority file, downloads the already
bound exact Manager artifact by workflow run/name, and then invokes the cached
`executor.py` by absolute path.

The private work root is:

```text
~/.local/share/n3w-kf098-20260928
```

It must be mode `0700`. Package, artifact and evidence files are kept private.
The bootstrap works from any Mac Terminal working directory and does not issue
`git status`, `git fetch`, `git checkout` or `git rev-parse`.

A cached package is reusable only when its recorded repository, exact package
SHA and every file SHA-256 still match. A cached artifact is reusable only when
the exact image tar and portable manifest checks still pass.

## Artifact transport

T1 must not depend on GitHub connectivity.

The Mac obtains the already-built exact artifact and verifies locally:

```text
manifest.sha256
manifest source SHA
manifest image ID
ARM64 architecture
greenhouse-manager-arm64.tar SHA256
```

The Mac then stages only:

```text
greenhouse-manager-arm64.tar
manifest.json
manifest.sha256
remote_cutover.py
```

to:

```text
/root/n3w-kf098-manager-cutover-20260928-01
```

The package uses `ssh -n` and `scp -B`; no nested heredoc owns SSH stdin.
Unknown non-empty staging state fails closed.

## Transport timeout contract

Host-side transport failures must fail closed before they are confused with a
product/runtime failure.

- T1 host/architecture preflight has a 30 second outer SSH budget.
- The Docker daemon probe inside that preflight has its own 10 second timeout.
- SSH uses bounded server-alive detection.
- A host subprocess timeout is recorded into private evidence as
  `timed_out=true` and converted to a structured STOP instead of escaping as a
  Python traceback.
- Remote phase budgets are phase-specific: preflight 180 seconds, apply 900
  seconds, rollback 600 seconds. Apply and rollback are intentionally larger
  than the old shared 240 second budget so the bounded remote transaction and
  rollback path are not cut off by the Mac wrapper.

## Phases

### local-preflight

Mac only.

Validates exact artifact and execution package. No T1 access.

### stage

T1 file staging only.

Creates the root-owned mode-0700 durable staging directory, copies into an
incoming directory, verifies hashes remotely and atomically promotes the
files. It does not load an image, change Manager state, modify Broker/R5, or
touch a board.

### remote-preflight

Read-only T1 rebind immediately before cutover.

It re-proves:

- exact live Compose and manager.env hashes;
- exact stale pairing value and mismatch with current eth0 IPv4;
- exact old Manager image, host networking, entrypoint, user, six-mount
  fingerprint and restart count;
- exactly one Broker, restart count zero and TCP/8883 listener;
- UDP/47111 and TCP/47112 listeners;
- current PR #480 R5 files and enabled/active units;
- DOCKER-USER and INPUT anchors both at position 1;
- three exact project-owned R5 chain rules;
- exact staged image/manifest authority.

Any drift stops before runtime mutation.

### apply

This phase requires a separate explicit live authorization.

Before stopping Manager it:

1. creates an exact mode-0600 backup of `manager.env`;
2. records private Manager/Broker/R5 prestate;
3. loads the exact ARM64 image tar;
4. verifies the exact immutable image ID;
5. binds the old Manager image to a deterministic local rollback tag;
6. creates a stopped old-image shadow Manager from the frozen live Compose and
   proves mounts, non-target GH environment and runtime/security settings match
   the current live Manager;
7. creates a stopped new-image shadow Manager with only the pairing host
   overridden to `auto` and proves the same runtime/security contract;
8. removes both stopped shadow containers.

The live Manager remains running throughout the shadow proof. Only after both
shadow contracts pass does the transaction begin.

It then starts the transaction:

1. atomically changes only the pairing advertised-host value to `auto`;
2. writes the private Manager-only Compose overlay;
3. stops and removes only the old Manager container;
4. recreates only the Manager service using `--no-deps --force-recreate`.

No Broker Compose command is issued.

PASS requires:

```text
new Manager running exact IMAGE_ID
network_mode=host
entrypoint=greenhouse-manager
user=greenhouse
six-mount fingerprint unchanged
all non-target GH_* runtime environment unchanged
GH_N3W_PAIRING_ADVERTISED_HOST=auto in file and runtime
UDP/47111 listener=1
TCP/47112 listener=1
GET 127.0.0.1:47112/healthz = gh.pair.simple-health/1 + ok
Broker container identity unchanged
Broker restart_count unchanged
TCP/8883 listener=1
R5 firewall state unchanged
```

This local postcheck proves a safe Manager cutover. It does not yet prove the
Board receives the new dynamic discovery response.

## Automatic rollback

After the transaction begins, any failed postcondition triggers rollback.

Rollback is valid only while the live state still belongs to this exact
transaction. Before removing anything it requires the frozen live Compose and
service-identity authorities, a recognized `manager.env` state (the exact
prestate or this transaction's `auto` state), and—if a Manager container
exists—either the exact old or exact new image ID. Any later/unknown Manager
revision is refused.

Rollback then:

1. removes only the transaction-owned candidate/old Manager container;
2. restores the exact pre-cutover `manager.env`;
3. rebinds the exact old Manager image by immutable image ID;
4. recreates only Manager through the same live Compose authority plus a
   Manager-only rollback overlay;
5. requires the old image ID, host networking, entrypoint, user, six-mount
   fingerprint, non-target GH environment and runtime/security fingerprint to
   recover;
6. requires the stale pairing runtime to match the restored env authority;
7. requires UDP/47111, TCP/47112 and simplified health to recover;
8. requires Broker identity/restart count and TCP/8883 to remain unchanged;
9. requires the R5 firewall snapshot to remain unchanged.

Manual rollback additionally requires the private pre-cutover transaction
snapshot. Missing or incomplete prestate fails closed.

If rollback cannot be proven, the result is fail-closed and no automatic retry
is permitted.

## Explicit non-actions

```text
LIVE_COMPOSE_FILE_MUTATION=false
SERVICE_IDENTITIES_ENV_MUTATION=false
BROKER_RESTART=false
BROKER_CONFIG_MUTATION=false
R5_MUTATION=false
HOME_ASSISTANT_MUTATION=false
BOARD_ACCESS=false
BOARD_REFLASH=false
PR474_SOURCE_CHANGE=false
PAIRING_REPAIR_AUTHORIZATION=false
REGISTRATION_DB_MUTATION=false
```

The in-memory identity-preserving repair authorization is deliberately later.
Manager restart invalidates such authorization, so it must not be created
before this cutover.

## Next acceptance boundary

After a successful live cutover, the next gate must prove over real traffic:

```text
Board UDP discovery request reaches T1
Manager discovery response candidate.host == current route-selected T1 IPv4
candidate.host != predecessor stale IPv4
Board begins TCP/47112 toward current T1
```

Only after that may the existing Board identity enter the separate
identity-preserving repair flow.

Preparation of this package does not authorize `stage`, `remote-preflight`,
`apply` or `rollback`.
