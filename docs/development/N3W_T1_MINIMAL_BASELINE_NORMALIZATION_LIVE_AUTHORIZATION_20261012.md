# N3-W T1 minimal-baseline normalization live authorization（2026-10-12）

## 0. Authorization

User explicitly approved:

```text
N3W_T1_MINIMAL_BASELINE_NORMALIZATION_LIVE_APPLY_20261012_01
```

Current state before any live apply invocation:

```text
AUTHORIZATION_STATE=GRANTED_PENDING_CLAIM
AUTHORIZATION_CLAIMED=false
AUTHORIZATION_CONSUMED=false
SOURCE_AUTHORITY=43207da98bc0e116af2845b690b3f0ee230637ab
LIVE_PREFLIGHT=PASS
LIVE_MUTATION=false
PRODUCTION_SERVICE_START=false
BOARD_ACCESS=false
PR541=OPEN_DRAFT
MERGE=false
```

## 1. Exact allowed scope

The one-shot live apply is limited to the frozen manifest and repository-owned executor at source authority `43207da98bc0e116af2845b690b3f0ee230637ab`.

Allowed mutation scope:

1. stop + disable exact `n3wfc4-broker-ingress-guard.service`;
2. remove exact N3W firewall INPUT / DOCKER-USER anchors and exact `N3WFC4-BROKER-INGRESS` chain;
3. remove five exact product/historical Docker networks;
4. remove the exact frozen 45-volume set;
5. remove eight exact product paths;
6. run `systemctl daemon-reload`;
7. perform minimal-host postcheck.

Must preserve:

- Armbian;
- SSH;
- NetworkManager and current network configuration;
- Docker Engine + Compose;
- Docker `bridge` / `host` / `none`;
- Docker `DOCKER-USER` framework and `FORWARD -> DOCKER-USER`.

## 2. Claim / consume boundary

The executor performs a complete fresh preflight immediately before mutation.

If preflight fails, authorization remains unclaimed.

If preflight passes and the executor emits:

```text
"event":"authorization_claimed"
```

then the authorization is permanently claimed and consumed. Any later partial failure is no-replay and requires fresh read-only forensic plus a new successor authorization.

## 3. Explicitly not authorized

- production Broker / Manager / Home Assistant start;
- board / NVS access;
- OS reinstall;
- system disk erase;
- Docker prune operations;
- PR #541 merge.

Raw T1 locator and customer LAN addressing remain outside the public repository.
