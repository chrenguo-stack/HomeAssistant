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

For the HA-only test candidate, the host timer checks durable requests after
recovery work. A PREPARE request uses a mode-0600, host-owned
`ha-prepare-authority.json` in the transaction state directory. It names
the transaction, existing mounted USB filesystem UUID, exact running launch
fingerprint, expiry, host path to a staged target archive, maximum predecessor
export size, and required USB reserve. The host validates the staged target
against the transaction digest and exports the currently running predecessor
to its USB transaction directory. Services stay up. The host can reopen
independently verified archives after interruption before publishing ready.

An INSTALL request still needs a separate private
`ha-install-authority.json` matching the prepared materials and predecessor
launch, with its own authorized ID, expiry, and storage budgets. The same
timer wakes the host worker when both are available. The
`--install-requested` mode remains available for an explicit host invocation.
The running predecessor must prove the configured monitoring path before
the first service stop.

Acquisition of the staged release and issuance of both authorities belong
to the approved candidate inputs. The repository contains no live authority.

### Host IPC for the test candidate

The recovery bundle contains a socket-activated host service at
`/run/n3w/t1-ota/ha-ota.sock`. The service accepts only the deployed Manager
peer UID 999. For the candidate, bind the whole host `/run/n3w/t1-ota`
directory into Manager at the same path, read-only. Enable Manager's existing
OTA setting and supply the installed Home Assistant version for the candidate.

Place the host-published `approved-homeassistant.json` in the exported
directory. A separate mode-0600 `ha-release-pin.json` in the private state
directory binds its exact SHA-256, the running predecessor Docker image ID,
and the expiry. The host checks the pin, the target contract, and the observed
predecessor before recording PREPARE or INSTALL. The IPC service does not
issue the separate preparation or installation authorities. This local
pin supports the controlled candidate. Product distribution still requires
the HTTPS signed index and published manifest described by V1.2.
