# T1 Home Assistant MQTT Legacy Evidence Bridge v1

## Purpose

This bridge normalizes the already-completed Home Assistant MQTT UI retry evidence into the strict input shape required by the current read-only postactivation handoff.

It exists because the real T1 evidence was produced before the current `gh.m2.t1-homeassistant-mqtt-reconfigure-handoff/1` and `gh.m2.t1-homeassistant-mqtt-reconfigure-postcheck/1` contracts were frozen.

The bridge does **not** rewrite the original handoff or postcheck. It creates a new private compatibility package that is cryptographically bound to both original files and revalidates the live Home Assistant MQTT configuration.

## Accepted legacy inputs

- Handoff manifest schema: `gh.m2.t1-homeassistant-mqtt-postactivation-handoff/1`
- UI retry postcheck schema: `gh.m2.t1-homeassistant-mqtt-ui-retry-postcheck/1`
- Private handoff directory and mode `0600` evidence files
- All recorded file sizes, modes, and SHA-256 values must still match
- The five MQTT fields must all match: broker, port, username, password, and client ID
- Home Assistant MQTT socket, discovery, entry identity, storage transition, and service stability must all remain verified
- Anonymous compatibility must remain enabled

## Live behavior

The bridge performs read-only Docker inspection through the existing Home Assistant MQTT postcheck implementation. It does not:

- edit Home Assistant `.storage`
- restart or recreate Home Assistant
- change Broker configuration
- deliver manager or node credentials
- authorize manager migration
- close anonymous compatibility

## Output

The output schema is:

`gh.m2.t1-homeassistant-mqtt-legacy-evidence-bridge/1`

Each bridge directory contains:

- `homeassistant-reconfigure-handoff/manifest.json`
- `homeassistant-reconfigure-handoff/homeassistant/reconfigure-values.json`
- `postcheck-result.json`
- `operator-runbook.txt`
- `manifest.json`

The normalized handoff and postcheck are suitable only as inputs to the current Home Assistant MQTT postactivation handoff. They are not an authorization packet.

## Required safety state

The bridge must report:

- `read_only_live_services=true`
- `current_services_modified=false`
- `apply_enabled=false`
- `operator_action_authorized=false`
- `homeassistant_authenticated=true`
- `manager_identity_migrated=false`
- `node_credentials_delivered=false`
- `ready_for_postactivation_handoff=true`
- `ready_for_manager_migration_apply=false`
- `preserve_anonymous=true`
- `anonymous_closure_enabled=false`

## CLI

```bash
python3 \
  host/greenhouse-manager/tools/run_t1_homeassistant_mqtt_legacy_evidence_bridge.py \
  LEGACY_HANDOFF_DIRECTORY \
  LEGACY_UI_RETRY_POSTCHECK_FILE \
  --output PRIVATE_OUTPUT_DIRECTORY \
  --expected-retained-topic EXPECTED_RETAINED_TOPIC
```

The returned JSON is intentionally path-redacted. The generated directory name is returned as `bridge_name`; combine it with the operator-selected output directory.
