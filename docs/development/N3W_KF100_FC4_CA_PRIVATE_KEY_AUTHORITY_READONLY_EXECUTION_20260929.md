# N3-W KF-100 FC4 CA Private-Key Authority Read-Only Execution — 2026-09-29

Status: `CLOSED_PASS`  
Repair PR: `#506`  
Repair branch: `fix/n3w-t1-broker-certificate-lifecycle-20260929`  
Probe/test verified head: `14ed473b49c2b926fea7b2c56607febb6bd39ae3`  
Focused CI: `N3W Broker ingress guard CI` run `36517861607` = `PASS`

## Purpose

Resolve the remaining live prerequisite:

```text
CURRENT_FC4_CA_PRIVATE_KEY_RUNTIME_AUTHORITY=UNPROVEN
```

without writing T1 state, restarting services, changing Docker, modifying certificates, or printing private-key/path material.

## Exact public-safe result

The schema-v2 read-only probe completed successfully with:

```text
READ_ONLY=true
T1_MUTATION=false
BROKER_MUTATION=false
MANAGER_MUTATION=false
HOMEASSISTANT_MUTATION=false
PROBE_RC=0

BROKER_CONTAINER_UNIQUE=true
BROKER_RUNNING=true
BROKER_CA_MOUNT_UNIQUE=true
BROKER_CA_MOUNT_READ_ONLY=true
BROKER_CA_CERTIFICATE_PARSEABLE=true
BROKER_CA_CERTIFICATE_IS_CA=true
BROKER_CA_SHA256_FINGERPRINT=b305f61656a0e795bc5dcc5388ba63bc77d824dc3329cf07b744ad9c91c66351

SEARCH_ROOT_COUNT=2
SEARCH_FILE_COUNT=2101
SEARCH_SKIPPED_LARGE_FILE_COUNT=21
PRIVATE_KEY_CANDIDATE_COUNT=17
PARSEABLE_PRIVATE_KEY_COUNT=3

CA_PRIVATE_KEY_MATCH_COUNT=1
CA_PRIVATE_KEY_SAFE_PERMISSION_MATCH_COUNT=1
CA_PRIVATE_KEY_ROOT_OWNED_MATCH_COUNT=1
CA_PRIVATE_KEY_ACTIVE_TLS_TREE_MATCH_COUNT=1
CA_PRIVATE_KEY_MATCH_MODE=0600
CA_PRIVATE_KEY_AUTHORITY_EXACT_UNIQUE=true

CA_PRIVATE_KEY_PATH_TOKEN=cdb208b8dc60893545103e08e6dd2e272c418f1ae6dc1c747e56900a3ef381f5
RESULT=PASS
```

The path token is a one-way public-safe continuity token. The real private-key path and key body remain outside the public repository.

## Interpretation

The active Broker CA was rebound from the currently running Compose Broker object and matched the already archived FC4 CA fingerprint.

Within the bounded current production authority roots:

- exactly one parseable private key matched the active FC4 CA public key;
- that matching key was root-owned;
- that matching key had mode `0600`;
- no second matching key existed in the bounded authority scope;
- the matching key was inside the active FC4 TLS authority tree.

Therefore the prior unknown can be closed:

```text
CURRENT_FC4_CA_CERTIFICATE_RUNTIME_AUTHORITY=PROVEN
CURRENT_FC4_CA_PRIVATE_KEY_RUNTIME_AUTHORITY=PROVEN
CURRENT_FC4_CA_CERT_KEY_MATCH=PASS
CURRENT_FC4_CA_PRIVATE_KEY_PERMISSION_AUTHORITY=PASS
CURRENT_FC4_CA_PRIVATE_KEY_UNIQUE_MATCH=PASS
```

## Scope boundary

This PASS proves authority and suitability for future signing preflight. It does not prove a live renewal transaction and does not install or enable the new lifecycle timer.

No certificate, key, service, container, Manager state, Home Assistant state, firewall state, or node trust state was mutated.

```text
LIVE_CERTIFICATE_MUTATION=false
LIVE_TIMER_ENABLEMENT=false
BROKER_RESTART=false
MANAGER_RESTART=false
HOMEASSISTANT_RESTART=false
NODE_REPAIRING=false
```

## Next gate

The source repair, source tests, source review, and the production CA cert/private-key authority prerequisite are now complete.

The next engineering step is controlled production deployment preparation for PR #506. That step must bind the exact merged/source authority, install the lifecycle tool/unit/timer configuration without immediately triggering renewal, run an audit-only production check first, and then separately decide whether to enable the daily timer.

```text
NEXT_ONE_GATE=N3W_KF100_BROKER_CERTIFICATE_LIFECYCLE_PRODUCTION_DEPLOYMENT_PREPARATION_20260929_01
```
