# FC4 R2C4E R6 Pre-Authorization Authority Regressions — 2026-08-28

> Public-safe engineering archive. Raw hardware identifiers, pairing IDs, Setup Secret, Wi-Fi/MQTT credentials, private host addresses, private evidence paths, private keys and credential bodies are intentionally excluded.

## Scope

This note archives the authority and execution-oracle failures discovered while preparing the N3-W / FC4 R2C4E consolidated SQLite directory-bind repair (`R6`) on Spare T1. These failures were discovered before R6 mutation authorization. No Board C access, flash/NVS operation, Broker/DynSec mutation, Manager restart/recreate, SQLite write or Compose mutation was performed in the diagnostic sequence recorded here.

The product acceptance goal is unchanged: restore the minimum production-equivalent runtime authority required to resume Board C first registration, then return to the original R6 SQLite repair and subsequent FC4 physical acceptance path.

## 1. Repository-main authority versus frozen product-source authority

During FC4 physical acceptance, repository `main` advanced through a documentation-only merge while the deployed/frozen FC4 Manager and firmware product source remained bound to an earlier commit.

Frozen facts at this archive boundary:

- repository documentation `main` tip: `7b043114633c826a9e8a6c0a6584c07f73ac4305`;
- FC4 frozen product-source authority: `1f80d54ff5f84056e0559a7d8cc80427c5e0bb14`;
- the frozen product-source commit remains an ancestor of repository `main`;
- the intervening `main` advancement is documentation-only;
- product source content drift was not observed.

Therefore repository tip and physical-acceptance product-source authority are separate facts. A documentation-only `main` advancement must not silently redefine the exact product revision under acceptance. Conversely, the frozen product-source authority must not be presented as the current repository `main` tip.

## 2. Cross-session exact-target recovery gap

The first R6 preclaim could not recover the exact Spare T1 target authority from the narrow R5/R5R1 private recovery corpus because the previously proven machine binding was not present there. The executor correctly failed closed and did not scan the LAN or inspect alternate targets.

A later read-only recovery used the pre-existing historic machine-binding evidence together with the already unique SSH locator and host-key evidence. The exact Spare T1 was then rebound successfully without broad discovery.

Regression requirement:

- cross-session target authority should preserve an exact locator provenance, host-key binding and public-safe machine-binding hash in controlled private evidence;
- if that descriptor is unavailable, recovery may use previously frozen evidence but must remain exact-target-only and fail closed on ambiguity;
- broad network discovery is not a substitute for missing target authority.

## 3. Current-runtime authority classifier selected a preserved rollback artifact

A later R6 read-only pass incorrectly treated a stopped historical `fc4-manager` rollback artifact as the current Manager because the classifier relied too heavily on the container name. That produced false apparent drift in Manager revision, registration topology and SQLite mount topology.

The corrected read-only discriminator proved the actual current Manager by correlating the exact successor service, running state, frozen source revision, read-only rootfs, Compose service identity and current pairing-port ownership. The actual current Manager remained the previously proven `0.4.99` runtime at source revision `1f80d54ff5f84056e0559a7d8cc80427c5e0bb14` with zero restarts.

The stopped historical rollback artifact must remain excluded from current-runtime authority unless an explicit disaster-recovery gate authorizes its use.

Regression requirement:

- container name alone is never sufficient current-runtime authority when preserved rollback artifacts coexist;
- current Manager classification must bind to the active successor/runtime contract and observable running identity;
- optional listener evidence must be resolved to PID/cgroup/container ownership rather than inferred from an open port alone;
- a preserved rollback artifact must be explicitly classified and excluded from current authority.

## 4. UNKNOWN propagation defect

When exact target authority was unavailable, one early closure serialized several unobserved runtime facts as `false`. Those values were not actual negative observations; they represented missing evidence.

This was corrected in subsequent closures by enforcing a three-state evidence contract:

```text
observed positive / observed negative / UNKNOWN-or-UNPROVEN
```

Regression requirement:

- inaccessible or uninspected authority must yield `UNKNOWN`, `UNPROVEN` or `NOT_OBSERVED`;
- boolean `false` is only valid when the corresponding negative state was actually observed or derived from an authoritative read;
- an `UNKNOWN` value cannot satisfy a PASS gate.

## 5. Active DynSec authority regressed to a stale predecessor snapshot

R6 runtime-authority rebind independently proved a unique running FC4 Broker and resolved its active Dynamic Security configuration through the Broker's effective Mosquitto configuration and mount.

The active persisted DynSec object was not the R5R1 security baseline. Its SHA-256 matched a known 2026-08-24 predecessor snapshot:

- current active persisted DynSec SHA-256: `55ef89aed1561138cccd6be5aad4df88fe70719832de0a4a12fda56cbcbb3cfe`;
- current persisted `changeIndex`: `18`;
- later previously proven production baselines existed after this snapshot, including the R5R1 baseline at `changeIndex=19`.

The current persisted object contained four clients and five roles, but read-only identity inspection proved that neither the current Manager identity nor the current Provisioning identity existed in that active persisted state.

At the same time, the current Manager runtime configuration still carried the expected Manager username/client-id binding. Passive Broker evidence showed the most recent observable event for that Manager client-id was `Not authorized`, and no current established Manager-to-Broker MQTT session was observed.

This closes the product-level failure chain:

```text
running Broker
  -> active persisted DynSec is a known stale predecessor snapshot
  -> current Manager identity absent
  -> current Provisioning identity absent
  -> current Manager configuration still uses the newer identity
  -> Broker rejects the Manager as Not authorized
```

The exact lower-level mechanism is intentionally left unresolved here: the evidence does not yet prove whether the Broker was rebound to an older host object or whether the intended host object was overwritten with older bytes. That distinction belongs to the bounded repair preclaim and must not be guessed.

This is not harmless `changeIndex` metadata drift. The active authorization state itself is stale and is already affecting the product runtime.

## 6. Repair constraints frozen before mutation

No direct edit or blind whole-file restoration of `dynamic-security.json` is authorized by this archive.

The next DynSec repair preclaim must:

1. bind the running Broker to the exact active DynSec source object;
2. classify source-locator regression versus persisted-content rollback when possible without unbounded historical searching;
3. preserve unrelated current DynSec identities/roles/ACLs;
4. restore only the current Manager and Provisioning identities/role bindings required by the frozen credential authority, using bounded production DynSec semantics rather than an unaudited whole-file rewind;
5. prove Manager MQTT authentication and Provisioning MQTT authentication after repair;
6. freeze a new active DynSec baseline;
7. only then return to the original R6 consolidated four-SQLite directory-bind preclaim.

A historical `changeIndex` value must not be manually rewound as a goal by itself.

## 7. Continuation point

At archive time:

```text
R6_MUTATION_PRECLAIM_READY=false
R6_AUTHORIZATION_ELIGIBLE=false
R6_AUTHORIZATION_GRANTED=false
R6_AUTHORIZATION_CLAIMED=false
R6_AUTHORIZATION_CONSUMED=false
CLAIM_BOUNDARY_PAIRING_REBIND_EXECUTED=false
```

No Board C reset/reconfiguration/flash/NVS action is required or authorized.

The next intended gate is a bounded DynSec authority repair preclaim. After DynSec authority is reconciled and a new authenticated baseline is proven, execution returns to the existing R6 SQLite repair path rather than opening a new product-development branch.
