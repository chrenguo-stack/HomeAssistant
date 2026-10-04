# N3W AUTO SAFE FALLBACK Gate F R2 TLS identity closure — 2026-10-04

## Result

R2 stale-Broker address recovery has been physically proven through discovery, RAM-only Broker retarget, TCP establishment, and TLS startup. The remaining end-to-end failure is no longer in the wireless/address-recovery path.

## Physical timeline evidence

From the controlled reset marker:

- FIRST_DISCOVERY_REQUEST_SECONDS=15.492
- FIRST_DISCOVERY_RESPONSE_SECONDS=15.508
- FIRST_TCP_SYN_SECONDS=16.503
- FIRST_TCP_SYN_ACK_SECONDS=16.504
- FIRST_TCP_ACK_AFTER_SYN_SECONDS=16.509
- FIRST_BOARD_TCP_PAYLOAD_SECONDS=16.526
- FIRST_T1_TCP_PAYLOAD_SECONDS=16.559
- FIRST_TLS_HANDSHAKE_BOARD_SECONDS=16.526
- FIRST_TLS_HANDSHAKE_T1_SECONDS=16.559
- FIRST_TLS_APPLICATION_BOARD_SECONDS=17.035
- FIRST_TLS_APPLICATION_T1_SECONDS=17.05
- FIRST_TLS_ALERT_T1_SECONDS=17.047
- FIRST_TCP_FIN_SECONDS=17.049
- FIRST_TCP_RST_SECONDS=17.053

Manager canonical telemetry did not advance after the reset.

## Credential and Broker identity reconciliation

Manager credential lifecycle:

- state=active
- active_generation=3
- pending_generation=None

Broker Dynamic Security:

- target username present
- target clientid SHA256 exactly matches stable node_id SHA256
- encoded password present
- one role attached

TLS listener configuration:

- listener 8883 0.0.0.0
- allow_anonymous false
- cafile /mosquitto/tls/ca.pem
- certfile /mosquitto/tls/server.pem
- keyfile /mosquitto/tls/server.key
- tls_version tlsv1.2
- no require_certificate directive
- no use_identity_as_username directive

TLS identity check on the T1 host:

- GH_N3W_NODE_BROKER_TLS_SERVER_NAME=armbian
- server certificate subject CN=armbian
- SAN DNS:armbian
- HOST_CERT_MATCHES_ARMBIAN=true
- HOST_CERT_MATCHES_MQTT_GREENHOUSE_LOCAL=false
- Broker container and host server.pem SHA256 match exactly
- Broker container and host ca.pem SHA256 match exactly

Therefore the TLS server-name/certificate identity is not the current blocker.

## Current fault boundary

Closed / proven:

- DIRECT MQTT persistent-failure trigger
- Manager discovery request/response
- RAM-only Broker retarget to current T1 address
- TCP connection to current T1:8883
- Broker server certificate identity for `armbian`
- DynSec username existence
- DynSec client_id identity match

Open:

- exact TLS terminal reason versus immediate post-handshake MQTT authentication/protocol failure
- possible Board-side generation-3 MQTT password mismatch versus Broker DynSec current password

Do not modify the R2 discovery/retarget logic based on this failure. Next evidence should come from Board-side MQTT/esp-tls error reporting and/or exact TLS alert/MQTT authentication evidence.

## Mutation status

- BOARD_FLASH_WRITE=false
- BOARD_NVS_MUTATION=false
- T1_CONFIG_MUTATION=false
- PR_522_MERGE=false
