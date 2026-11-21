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

The component uses the existing HA broker identity and writes no Recorder
state. Enablement in an acceptance environment belongs to a later preflight
and deployment step.

The maintenance path needs an OTA-enabled Manager with this source. If
the running predecessor has no eligible natural telemetry, the updater
can qualify the maintenance method before the first service stop. With that
method qualified, an upgrade or rollback worker can ask the running Manager
to publish one non-retained challenge on a dedicated state topic. HA's
receipt must match that specific live challenge. Neither the challenge
nor its receipt creates an entity, invokes discovery or writes sensor
history. A status query has no request path. During rollback, inconclusive
monitoring evidence leaves the restored services running and the journal
pending for a later check.

For the HA-only test candidate, the product installation intent is recorded
before the host runner is invoked. The recovery archive's
`--install-requested` mode admits a prepared transaction using a private
`ha-install-authority.json` in the transaction state directory. The
authority binds the prepared transaction and original media, the exact
predecessor launch, the authorized ID, expiry, and checked storage budgets.
The running predecessor must prove the configured monitoring path before
the first service stop. An interrupted install is handled by the existing
recovery entry.

Candidate preparation must supply the approved inputs and arrange host
worker invocation. The repository does not contain a live authority file.
