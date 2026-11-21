# N3-W OTA monitoring receipt

The OTA V1.2 Home Assistant acceptance path can correlate a new natural
telemetry delivery with the Manager's canonical cursor. The Home Assistant
integration subscribes through the existing HA MQTT client and keeps up to
16 message identities in a bounded, container-local `/dev/shm` receipt.
Only delivery to a live HA subscriber is eligible. The updater checks the
current Manager, Broker and HA instances, the cursor, and the receipt's age.

The predecessor and target must both include this component and load the
following integration configuration with the Manager's actual `GH_SYSTEM_ID`.

```yaml
n3w_ota_monitoring:
  system_id: greenhouse
```

The component uses the existing HA broker identity. It publishes no MQTT
messages and writes no Recorder state. The source integration is opt-in.
Enablement in an acceptance environment belongs to a later preflight and
deployment step. When no fresh natural telemetry is available, this method
returns evidence unavailable. Maintenance self-test and rollback monitoring
acceptance remain separate implementation work.
