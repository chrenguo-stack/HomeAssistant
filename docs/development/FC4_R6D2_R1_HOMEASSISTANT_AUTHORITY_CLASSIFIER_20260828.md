# FC4 R6D2-R1 Home Assistant Authority Classifier — 2026-08-28

> Public-safe archive. No credentials, private host addresses, private paths, hardware identifiers, pairing IDs or Setup Secret are included.

## Context

`R6D2-DYNSEC-AUTHORITY-REPAIR-20260828-01` was authorized, but the first repair executor stopped before authorization CLAIM because its Home Assistant invariant selector assumed that exactly one running container on the host could carry `com.docker.compose.service=homeassistant`.

No DynSec mutation, Broker stop/restart, Manager mutation, Home Assistant mutation, SQLite mutation or Board C access occurred before the stop.

Frozen authorization state after the stop:

```text
AUTHORIZATION_GRANTED=true
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
REPLAY_PERMITTED=false
```

## Observed topology

Read-only discrimination found two simultaneously running Home Assistant service containers:

1. FC4 Home Assistant candidate
   - container name: `fc4-homeassistant`
   - Compose project: `n3wfc4`
   - Compose service: `homeassistant`
   - network mode: `n3wfc4-private`
   - restart count: `0`
   - shares the exact running FC4 Broker Compose project (`n3wfc4`)

2. Independent/legacy Home Assistant runtime
   - container name: `homeassistant`
   - Compose project: `homeassistant`
   - Compose service: `homeassistant`
   - network mode: `host`
   - restart count: `0`
   - does not share the FC4 Broker Compose project

The current FC4 Broker remains `com.docker.compose.project=n3wfc4`, service `broker`. The current Manager is a later corrected successor service in a different Compose project, so Manager-project equality is not a valid Home Assistant selector.

## Classification

The failure is another manifestation of `KF-071` (current-runtime authority discriminator): a globally broad service-name query was treated as unique authority.

For the R6D2 successor, the FC4 Home Assistant invariant authority is the unique running container satisfying all of:

```text
com.docker.compose.project = n3wfc4
com.docker.compose.service = homeassistant
container name = fc4-homeassistant
running = true
oneoff = false
```

The independent `homeassistant` project is excluded from FC4 mutation invariants and must not be restarted, recreated, stopped or otherwise touched.

## Executor correction

The successor must replace the host-global `service=homeassistant` selector with the exact FC4 authority discriminator above. It must snapshot the selected FC4 Home Assistant container ID, image ID and restart count before CLAIM and require the same values after the DynSec transaction.

If the exact FC4 selector yields zero or more than one result, fail closed before CLAIM.

The original authorization remains unconsumed because the failure occurred before the CLAIM marker and before any live mutation.
