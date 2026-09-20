# PR437 Board B disconnect-context T1 read-only forensic R2

Status: PREPARED_FOR_OPERATOR_EXECUTION

The R1 gate stopped because it failed to rediscover an exact disconnect that the immediately preceding Broker-path gate had already proven. R1 changed the disconnect detector from a tolerant exact-client substring check to a stricter regex, so this STOP is classified as an oracle mismatch until proven otherwise; it is not new product evidence.

R2 restores the previous successful exact-client disconnect semantics, widens the historical Broker log query to 14:34:00Z..14:40:00Z, and does not require rediscovery of the already frozen exact disconnect in order to return the surrounding context. It records whether that disconnect is reobserved.

Frozen prior authority:

    LAST_CANONICAL_SEQ=49
    LAST_CANONICAL_UPDATED_AT=2026-09-20T14:35:06.070Z
    PRIOR_EXACT_BOARD_B_DISCONNECT=2026-09-20T14:35:30.732623821Z

R2 reports Board B reconnect evidence, Manager disconnect evidence, other-client churn, generic Broker error categories near the event, and current Manager-owned MQTT socket continuity.

Safety:

    BOARD_ACCESS=false
    BOARD_RESET=false
    BOARD_FLASH_WRITE=false
    PRODUCT_NVS_WRITE=false
    APPLICATION_SERIAL_OPEN=false
    MQTT_TEST_PUBLISH=false
    MQTT_EXTRA_SUBSCRIBER=false
    T1_ACCESS=SSH_READ_ONLY
    T1_MUTATION=false

Execution:

    python3 /tmp/n3w-pr437-177468e-disconnect-context-t1-forensic-r2.py       --t1-target <PRIVATE_T1_SSH_TARGET>       --output /tmp/n3w-pr437-177468e-disconnect-context-t1-forensic-r2.json
