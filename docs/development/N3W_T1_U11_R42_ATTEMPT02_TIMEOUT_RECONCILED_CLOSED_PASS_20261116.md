# N3W T1 U11 R42 Attempt 02 timeout-reconciled closure — 2026-11-16

## Result

```text
GATE=N3W_T1_HOMEASSISTANT_USB_MANDATORY_OTA_R7A_U11_POST_R40_SUCCESSOR_LIVE_RECOVERY_R42_20261116_01
R42_REPAIR_HEAD=cc38a8405927814b650ee41ef2d65372f502af8b
R42_EXECUTION_ID=u11-r42-live02-20261116T152940Z
LOCAL_RESULT=STOP_UNKNOWN
LOCAL_RC=2
LOCAL_REASON_CLASS=postinvoke_unknown:TimeoutExpired
AUTHORIZATION_CLAIMED=true
AUTHORIZATION_CONSUMED=true
REPLAY_PERMITTED=false

READONLY_FORENSIC=PASS
DURABLE_R42_SUCCESS_LEDGER=true
DURABLE_R42_FAILURE_LEDGER=false
LIVE_TRANSACTION_PHASE=U11_TARGET_INSTALLED_STARTED
LIVE_TRANSACTION_SHA256=33350ba47e0af43b4f0e11fac990e24924f22057da60d980b26453b4e80e0471
USB_TRANSACTION_PHASE=U11_TARGET_INSTALLED_STARTED
U11_RESULT=U11_R42_POST_R40_SUCCESSOR_RECOVERY_PASS
U12_ACCEPTANCE=false
U13_PLUS=false
```

## Interpretation

The local R42 executor timed out while waiting for the remote execute SSH command and therefore returned conservative `STOP_UNKNOWN`. That local result did not prove the remote operation failed.

A later strictly read-only forensic snapshot proved that the remote R42 execution completed successfully and durably after the local timeout:

- the one-shot R42 authorization claim exists and is claimed + consumed + no-replay;
- `success.json` exists and records `U11_R42_POST_R40_SUCCESSOR_RECOVERY_PASS`;
- no R42 failure ledger exists;
- the host transaction is active at `U11_TARGET_INSTALLED_STARTED`;
- the USB phase mirror is also `U11_TARGET_INSTALLED_STARTED`;
- all four USB mirror files are present and the R42 terminal verification recorded `usb_mirror_exact=true`;
- the target Home Assistant image/runtime is exact;
- Home Assistant is running with the production `/config` RW bind;
- Manager and Broker are running;
- the services owner is active/running;
- R42 performed no U12 acceptance and contains no U13+ path.

The observed Manager/Home Assistant container start time is about 47 minutes after the execution-id timestamp, exceeding the local R42 execute timeout of 2400 seconds (40 minutes). This explains the local timeout followed by a durable remote PASS.

## Exact durable evidence

```text
R42_CLAIM_SHA256=41644089e17cf0190faf5694180053e78dc4e7f5fc0e502388ca64e7659914e2
R42_SUCCESS_SHA256=a68199255967d63dd8f009aa71e254c16dee895649e57656d3da5c46ac011921
HOST_TRANSACTION_SHA256=33350ba47e0af43b4f0e11fac990e24924f22057da60d980b26453b4e80e0471
USB_MANIFEST_SHA256=3aa5e247636b1bb891aa151a8fb0219294d4803ea22dc7b66d821f6250d9e728
USB_PHASE_SHA256=8f2ba37e93577452ffd2b6dfc1cc5febbf717d1bf8c3ed2de8ec57ccf69e6921
USB_CONTENT_AUTHORITY_SHA256=3da14eb03447beaf38579a3fa5e4e076d4f3e806f7a787cbc0bba6b2cb1b8727
USB_CHECKSUMS_SHA256=2a21aa2b8fb362242fa087a49a2ebfb93caf65d1dd8a6f9c6da44edbb9f8c7f2
USB_FILESYSTEM_UUID=967cf065-abe5-49ee-8499-7c3f50d2c48f
TARGET_HOMEASSISTANT=local/n3w-homeassistant:2026.10.4-5881590f
TARGET_RUNTIME_IMAGE_ID=sha256:31bc185bfa185ed3dddce2f5bab867eb7d4ae96302bfd8b7f839fb0a9d5b7365
PRODUCTION_CONFIG_MOUNTED=true
BROKER_RUNNING=true
MANAGER_RUNNING=true
HOMEASSISTANT_RUNNING=true
SERVICES_OWNER_ACTIVE=true
```

The public USB fingerprint is intentionally session-scoped in source and includes path / major:minor. A changed value across device-node renumbering is not cross-session recovery authority and does not invalidate this closure. The filesystem UUID and durable transaction/mirror identities remain authoritative.

## Boundary

R42 is permanently consumed and must never be replayed.

U11 is now physically complete. U12 has not been entered or accepted. No U12/U13, board access, merge, or additional live mutation is authorized by this closure.

The next work item is a separate U12 target-acceptance gate. It must begin from fresh read-only preflight / design review and must not reuse R42 authorization.

Raw real-T1 evidence remains in the approved private evidence area and is not committed to the public repository.
