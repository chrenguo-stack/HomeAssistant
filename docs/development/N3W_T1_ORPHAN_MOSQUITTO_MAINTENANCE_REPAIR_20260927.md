# N3-W T1 maintenance: Compose orphan ownership and Mosquitto 2.1 deprecation repair

Updated: 2026-09-27

## Live evidence

```text
COMPOSE_ORPHAN_ROOT_CAUSE=PROVEN
N3WFC4_BROKER_PROJECT=n3wfc4
FC4_HOMEASSISTANT_PROJECT=n3wfc4
BROKER_COMPOSE_DECLARED_SERVICES=broker,manager
FC4_HOMEASSISTANT_DECLARED_IN_BROKER_COMPOSE=false

FC4_HOMEASSISTANT_RUNNING=true
FC4_HOMEASSISTANT_RESTART_COUNT=0
FC4_HOMEASSISTANT_NETWORK=n3wfc4-private

INDEPENDENT_HOMEASSISTANT_RUNNING=true
INDEPENDENT_HOMEASSISTANT_PROJECT=homeassistant
INDEPENDENT_HOMEASSISTANT_NETWORK_MODE=host

MOSQUITTO_RUNNING_VERSION=2.1.2
MOSQUITTO_PER_LISTENER_SETTINGS=false
MOSQUITTO_LISTENER=8883
MOSQUITTO_ALLOW_ANONYMOUS=false
MOSQUITTO_DYNAMIC_SECURITY_PLUGIN=legacy_plugin_directive
```

The orphan warning is caused by intentionally split Compose authority inside project `n3wfc4`. The observed `fc4-homeassistant` must not be treated as disposable orphan state.

## Compose repair

Use Docker Compose's explicit split-ownership control:

```text
COMPOSE_IGNORE_ORPHANS=true
```

The setting belongs to the Broker activation systemd environment. It preserves project identity and does not remove, stop, recreate, or absorb the separately managed Home Assistant service.

Forbidden:

```text
--remove-orphans
COMPOSE_REMOVE_ORPHANS=true
automatic Home Assistant retirement
project identity rename
```

## Mosquitto repair

The running Broker is Mosquitto 2.1.2. The production config uses `per_listener_settings false`, so the current security semantics are global.

The minimum semantics-preserving migration is:

```text
remove: per_listener_settings false
replace: plugin /usr/lib/mosquitto_dynamic_security.so
with: global_plugin /usr/lib/mosquitto_dynamic_security.so
keep: allow_anonymous false
```

This keeps Dynamic Security global across listeners and keeps anonymous access globally disabled. The repair tool fails closed unless the exact known legacy state is present.

Before live apply:

```text
fresh config SHA-256
rollback copy
candidate diff review
Mosquitto 2.1 --test-config
live connection baseline
```

After live apply:

```text
Broker running
restart count bounded
TCP 8883 listener exactly one
Manager loopback TLS connectivity PASS
authenticated client path PASS
deprecated warning absent on Broker start
R5 firewall policy unchanged
```

## Boundaries

```text
HOMEASSISTANT_MUTATION=false
REMOVE_ORPHANS=false
R5_FIREWALL_REDESIGN=false
B2_EXECUTION=false
B3_EXECUTION=false
BOARD_ACCESS=false
```
