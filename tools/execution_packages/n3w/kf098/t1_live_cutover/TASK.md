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
5. binds the old Manager image to a deterministic local rollback tag.

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

Rollback:

1. removes only the candidate Manager container;
2. restores the exact pre-cutover `manager.env`;
3. rebinds the exact old Manager image by immutable image ID;
4. recreates only Manager through the same live Compose authority plus a
   Manager-only rollback overlay;
5. requires the old image ID, host networking, six-mount fingerprint and
   simplified health endpoint to recover;
6. requires Broker identity/restart count to remain unchanged.

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
