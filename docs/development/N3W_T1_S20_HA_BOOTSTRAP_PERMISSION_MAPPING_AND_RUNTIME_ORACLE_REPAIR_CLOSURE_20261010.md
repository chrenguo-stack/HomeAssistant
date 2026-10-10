# N3-W T1 S20 Home Assistant MQTT bootstrap repair closure

Date: 2026-10-10
Status: CLOSED_PASS
Repository: chrenguo-stack/HomeAssistant
PR: #541, OPEN DRAFT
REPAIR_HEAD=0412d6009c963bf80eb7ce2e21e3fefac69e09a2
HA_ISOLATED_RUNTIME_RUN=38039664411
HA_ISOLATED_RUNTIME_JOB=114177209128
T1_ACCESS=false
T1_MUTATION=false
BOARD_ACCESS=false
MERGE=false

## Closure summary

The exact Home Assistant 2026.10.0 isolated automatic MQTT bootstrap acceptance is now PASS after the S20 repair sequence.

The repair closed three classes of issues:

1. Broker test fixture ownership/readability and bounded readiness evidence.
2. Product compatibility with real Home Assistant ConfigEntry.data MappingProxyType, including disabled-entry fail-closed handling.
3. Runtime acceptance oracle defects that could either hide success or falsely pass recreate from stale storage.

No production T1 network topology change was required.

## Exact passing runtime acceptance

Workflow:
N3W T1 HA bootstrap isolated CI

Run:
38039664411

Exact source:
0412d6009c963bf80eb7ce2e21e3fefac69e09a2

Result:
PASS

Pytest:
1 passed in 20.62s

The passing test requires all of the following in one exact-image run:

- Broker private configuration/password material is readable only by the intended Broker runtime identity.
- Broker reaches authenticated MQTT v5 readiness.
- TCP connectivity succeeds in the isolated localhost-sharing namespace.
- Valid MQTT v5 credentials are accepted.
- Wrong password is rejected.
- Home Assistant 2026.10.0 starts with the custom bootstrap integration.
- First boot reports bootstrap outcome `created`.
- Exactly one MQTT config entry is observed.
- Home Assistant establishes an authenticated MQTT connection to Broker.
- Home Assistant container is removed and recreated while retaining the original config/.storage.
- Recreated Home Assistant reports bootstrap outcome `existing_match`.
- The MQTT entry_id remains unchanged.
- No duplicate MQTT entry is created.
- Recreated Home Assistant establishes a new authenticated MQTT connection to Broker.

The test does not directly edit Home Assistant .storage.

## Product repair closed

`infra/n3w-t1/homeassistant/custom_components/n3w_mqtt_bootstrap/__init__.py`

- Existing ConfigEntry.data now accepts `collections.abc.Mapping`, matching real Home Assistant MappingProxyType behavior.
- Matching existing MQTT entries remain no-op success.
- Disabled existing entries fail closed.
- Effective TCP/no-TLS fields are checked.
- Bootstrap emits safe outcome classes `created` and `existing_match` at INFO level.
- Blocking metadata/password file reads remain off the Home Assistant event loop.
- Flow failure diagnostics remain sanitized.

## Harness repair closed

`tests/tools/test_n3w_ha_mqtt_bootstrap_isolated_runtime.py`

- mosquitto_passwd creates the password file under the runner identity before controlled ownership transfer.
- Broker config/password files use restrictive permissions and are rebound to the actual Broker UID/GID.
- Parent-directory ownership is transferred last so the runner does not lose traversal before child handoff finishes.
- Broker startup/readiness failures preserve bounded sanitized state/log evidence.
- Probe and HA runtime use `--network container:<broker>` for this bootstrap-only isolation gate.
- The isolated HA config explicitly enables INFO only for the bootstrap integration so current-process outcome markers are observable.
- Recreate acceptance cannot pass from pre-existing storage alone.
- Broker connection oracle counts only real `New client connected` events for the expected HA client.

## Important scope boundary

This CLOSED_PASS proves the automatic bootstrap design and exact-image isolated runtime behavior.

It does not by itself prove the production T1 Compose network topology, firewall behavior, host publication, Dynamic Security roles/ACLs, ARM64 image binding, or real production credential deployment.

Production topology remains unchanged:

- Home Assistant: host network
- Manager: host network
- Broker: Docker networks
- host `127.0.0.1:1883` publication for local HA path
- guarded TLS `0.0.0.0:8883` publication for formal external/runtime traffic

Do not copy the isolated CI `container:<broker>` network mode into production Compose.

## Related CI at repair head

- N3W T1 HA bootstrap isolated CI: PASS, run 38039664411
- N3W T1 deployment gate CI: PASS, run 38039664397
- Public repository safety CI: PASS, run 38039664398
- greenhouse-manager CI: PASS, run 38039664426

## Current boundary

S19 isolated service identity and ACL acceptance remains CLOSED_PASS.

S20 automatic Home Assistant bootstrap source/runtime isolation is CLOSED_PASS.

Still not authorized or completed:

- production three-service credential creation
- production Broker start
- production host 1883/8883 publication
- production Home Assistant mutation
- T1 fresh runtime read-only rebind after this repair
- final image digest / ARM64 binding
- production Dynamic Security deployment
- board access
- PR merge

READY_FOR_REAL_SERVICE_IDENTITY_AUTHORIZATION=false

## Next gate

NEXT_ONE_GATE=N3W_T1_S20_PRODUCTION_THREE_SERVICE_CREDENTIAL_HANDOFF_AND_DEPLOYMENT_PREFLIGHT_R2_20261010_01

Scope:
- source plus T1 read-only fresh rebind only;
- bind final Manager/Provisioning/HA runtime secret consumers;
- bind exact image digests and ARM64 availability;
- verify intended production Compose topology and startup ordering;
- no production identity creation, no service mutation, no port opening, no board access.

STOP=true
